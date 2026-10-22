"""SQLite 持久层。

表设计要点：
  * source 区分 pku3b 同步条目与手动条目，同步时绝不触碰 manual 行。
  * status_locked 记录用户对 pku3b 条目手动改过的完成状态，同步时不再回写。
  * deleted 作为墓碑，用户删除过的教学网作业不会被下次同步复活。
  * stale 标记教学网上已消失的条目，界面上隐藏但保留历史。
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

from . import paths
from .models import DDL, fmt_iso, parse_dt

SCHEMA = """
CREATE TABLE IF NOT EXISTS ddl (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    course_name   TEXT NOT NULL DEFAULT '',
    due_time      TEXT,
    source        TEXT NOT NULL DEFAULT 'manual',
    status        TEXT NOT NULL DEFAULT 'pending',
    ext_id        TEXT NOT NULL DEFAULT '',
    dedupe_key    TEXT NOT NULL DEFAULT '',
    status_locked    INTEGER NOT NULL DEFAULT 0,
    remote_completed INTEGER NOT NULL DEFAULT 0,
    user_edited      INTEGER NOT NULL DEFAULT 0,
    deleted       INTEGER NOT NULL DEFAULT 0,
    stale         INTEGER NOT NULL DEFAULT 0,
    notified_date TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    completed_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_ddl_due ON ddl(due_time);
CREATE INDEX IF NOT EXISTS idx_ddl_source ON ddl(source);
CREATE INDEX IF NOT EXISTS idx_ddl_dedupe ON ddl(dedupe_key);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""

COLUMNS = (
    "id, title, course_name, due_time, source, status, ext_id, dedupe_key, "
    "status_locked, remote_completed, user_edited, deleted, stale, notified_date, "
    "created_at, updated_at, completed_at"
)

INSERT_SQL = "INSERT INTO ddl(" + COLUMNS + ") VALUES(" + ",".join(["?"] * 17) + ")"

SEP = "\u001f"


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat(sep="T")


def row_to_ddl(row: sqlite3.Row) -> DDL:
    return DDL(
        id=row["id"],
        title=row["title"],
        course_name=row["course_name"],
        due_time=parse_dt(row["due_time"]),
        source=row["source"],
        status=row["status"],
        ext_id=row["ext_id"],
        dedupe_key=row["dedupe_key"],
        status_locked=row["status_locked"],
        remote_completed=row["remote_completed"],
        user_edited=row["user_edited"],
        deleted=row["deleted"],
        stale=row["stale"],
        notified_date=row["notified_date"],
        created_at=parse_dt(row["created_at"]),
        updated_at=parse_dt(row["updated_at"]),
        completed_at=parse_dt(row["completed_at"]),
    )


class Database:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else paths.db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
            self._migrate()
            self._conn.commit()

    def _migrate(self) -> None:
        """为旧库补列，保证升级不丢数据。"""
        cols = {row["name"] for row in self._conn.execute("PRAGMA table_info(ddl)")}
        if "user_edited" not in cols:
            self._conn.execute(
                "ALTER TABLE ddl ADD COLUMN user_edited INTEGER NOT NULL DEFAULT 0"
            )
        if "remote_completed" not in cols:
            self._conn.execute(
                "ALTER TABLE ddl ADD COLUMN remote_completed INTEGER NOT NULL DEFAULT 0"
            )
            # 旧库推断：已完成且不是用户手动改的，视为教学网本来就已完成
            self._conn.execute(
                "UPDATE ddl SET remote_completed = "
                "CASE WHEN status = 'completed' AND status_locked = 0 THEN 1 ELSE 0 END"
            )
        if "completed_at" not in cols:
            self._conn.execute("ALTER TABLE ddl ADD COLUMN completed_at TEXT")

    # -- 基础 ----------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _query(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            cur = self._conn.execute(sql, args)
            return cur.fetchall()

    def _execute(self, sql: str, args: tuple = ()) -> int:
        with self._lock:
            cur = self._conn.execute(sql, args)
            self._conn.commit()
            return cur.rowcount

    # -- meta ----------------------------------------------------------
    def get_meta(self, key: str, default: str = "") -> str:
        rows = self._query("SELECT v FROM meta WHERE k = ?", (key,))
        return rows[0]["v"] if rows else default

    def set_meta(self, key: str, value: str) -> None:
        self._execute(
            "INSERT INTO meta(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v",
            (key, value),
        )

    # -- 查询 ----------------------------------------------------------
    def all_items(self, include_deleted: bool = False) -> list[DDL]:
        where = "" if include_deleted else "WHERE deleted = 0"
        rows = self._query("SELECT " + COLUMNS + " FROM ddl " + where)
        return [row_to_ddl(r) for r in rows]

    def visible_items(self, show_completed: bool = False) -> list[DDL]:
        sql = "SELECT " + COLUMNS + " FROM ddl WHERE deleted = 0 AND stale = 0"
        if not show_completed:
            sql += " AND status = 'pending'"
        return [row_to_ddl(r) for r in self._query(sql)]

    def get(self, item_id: str) -> DDL | None:
        rows = self._query("SELECT " + COLUMNS + " FROM ddl WHERE id = ?", (item_id,))
        return row_to_ddl(rows[0]) if rows else None

    def pending_count(self) -> int:
        rows = self._query(
            "SELECT COUNT(*) AS n FROM ddl WHERE deleted = 0 AND stale = 0 "
            "AND status = 'pending' AND due_time IS NOT NULL"
        )
        return int(rows[0]["n"]) if rows else 0

    # -- 写入 ----------------------------------------------------------
    def add_manual(
        self,
        title: str,
        course_name: str = "",
        due_time: datetime | None = None,
    ) -> DDL:
        item_id = "manual:" + uuid.uuid4().hex[:12]
        stamp = _now()
        self._execute(
            INSERT_SQL,
            (
                item_id,
                title.strip(),
                course_name.strip(),
                fmt_iso(due_time),
                "manual",
                "pending",
                "",
                "",
                0,
                0,
                0,
                0,
                0,
                "",
                stamp,
                stamp,
                None,
            ),
        )
        item = self.get(item_id)
        assert item is not None
        return item

    def update_manual(
        self,
        item_id: str,
        title: str,
        course_name: str,
        due_time: datetime | None,
    ) -> None:
        self._execute(
            "UPDATE ddl SET title = ?, course_name = ?, due_time = ?, "
            "user_edited = CASE WHEN source = 'pku3b' THEN 1 ELSE user_edited END, "
            "updated_at = ? WHERE id = ?",
            (title.strip(), course_name.strip(), fmt_iso(due_time), _now(), item_id),
        )

    def set_status(self, item_id: str, status: str, lock: bool = True) -> None:
        """用户手动切换完成状态。lock=True 时禁止后续同步覆盖。"""
        row = self.get(item_id)
        if row is None:
            return
        locked = row.status_locked
        if lock and row.source == "pku3b":
            locked = 1
        stamp = _now()
        self._execute(
            "UPDATE ddl SET status = ?, status_locked = ?, completed_at = ?, updated_at = ? "
            "WHERE id = ?",
            (status, locked, stamp if status == "completed" else None, stamp, item_id),
        )

    def toggle_status(self, item_id: str) -> str:
        row = self.get(item_id)
        if row is None:
            return "pending"
        new_status = "pending" if row.status == "completed" else "completed"
        self.set_status(item_id, new_status)
        return new_status

    def delete(self, item_id: str) -> None:
        """软删除：保留墓碑，避免同步复活。"""
        self._execute(
            "UPDATE ddl SET deleted = 1, updated_at = ? WHERE id = ?", (_now(), item_id)
        )

    def mark_notified(self, item_id: str, date_str: str) -> None:
        self._execute("UPDATE ddl SET notified_date = ? WHERE id = ?", (date_str, item_id))

    # -- 同步专用 ------------------------------------------------------
    def find_synced(self, ext_id: str, dedupe_key: str) -> DDL | None:
        if ext_id:
            rows = self._query(
                "SELECT " + COLUMNS + " FROM ddl WHERE source = 'pku3b' AND ext_id = ?",
                (ext_id,),
            )
            if rows:
                return row_to_ddl(rows[0])
        if dedupe_key:
            rows = self._query(
                "SELECT " + COLUMNS + " FROM ddl WHERE source = 'pku3b' AND dedupe_key = ?",
                (dedupe_key,),
            )
            if rows:
                return row_to_ddl(rows[0])
        return None

    def upsert_synced(
        self,
        ext_id: str,
        title: str,
        course_name: str,
        due_time: datetime | None,
        completed: bool,
    ) -> tuple[str, str, bool]:
        """返回 (动作, 条目 id, 是否刚刚变为已完成)。

        动作属于 added / updated / restored / unchanged。
        """
        dedupe_key = (course_name + SEP + title).strip()
        existing = self.find_synced(ext_id, dedupe_key)
        stamp = _now()

        if existing is None:
            item_id = "pku3b:" + (ext_id or uuid.uuid4().hex[:12])
            self._execute(
                INSERT_SQL,
                (
                    item_id,
                    title,
                    course_name,
                    fmt_iso(due_time),
                    "pku3b",
                    "completed" if completed else "pending",
                    ext_id,
                    dedupe_key,
                    0,
                    1 if completed else 0,
                    0,
                    0,
                    0,
                    "",
                    stamp,
                    stamp,
                    None,
                ),
            )
            return "added", item_id, bool(completed)

        if existing.deleted:
            return "unchanged", existing.id, False

        became_completed = False
        sets: list[str] = []
        args: list[object] = []
        action = "unchanged"

        # 用户改过标题/课程后，同步不再覆盖这两个字段（截止时间仍跟随教学网）
        if not existing.user_edited:
            if title and title != existing.title:
                sets.append("title = ?")
                args.append(title)
                action = "updated"
            if course_name and course_name != existing.course_name:
                sets.append("course_name = ?")
                args.append(course_name)
                action = "updated"
        if due_time is not None and fmt_iso(due_time) != fmt_iso(existing.due_time):
            sets.append("due_time = ?")
            args.append(fmt_iso(due_time))
            action = "updated"
        if ext_id and ext_id != existing.ext_id:
            sets.append("ext_id = ?")
            args.append(ext_id)
            action = "updated"
        if dedupe_key and dedupe_key != existing.dedupe_key:
            sets.append("dedupe_key = ?")
            args.append(dedupe_key)
        if int(completed) != existing.remote_completed:
            sets.append("remote_completed = ?")
            args.append(1 if completed else 0)
            action = "updated"
        if existing.stale:
            sets.append("stale = 0")
            if action == "unchanged":
                action = "restored"

        # 状态：用户手动改过就绝不覆盖
        if completed and existing.status != "completed" and not existing.status_locked:
            sets.append("status = 'completed'")
            sets.append("completed_at = ?")
            args.append(stamp)
            action = "updated"
            became_completed = True

        if sets:
            sets.append("updated_at = ?")
            args.append(stamp)
            args.append(existing.id)
            self._execute("UPDATE ddl SET " + ", ".join(sets) + " WHERE id = ?", tuple(args))
        return action, existing.id, became_completed

    def mark_stale_except(self, keep_ids: set[str]) -> int:
        rows = self._query(
            "SELECT id FROM ddl WHERE source = 'pku3b' AND deleted = 0 AND stale = 0"
        )
        stale_ids = [r["id"] for r in rows if r["id"] not in keep_ids]
        if not stale_ids:
            return 0
        stamp = _now()
        with self._lock:
            self._conn.executemany(
                "UPDATE ddl SET stale = 1, updated_at = ? WHERE id = ?",
                [(stamp, i) for i in stale_ids],
            )
            self._conn.commit()
        return len(stale_ids)

    def reset_remote_pending(self) -> int:
        """把教学网上仍未提交的条目全部恢复为待办（解除用户手动勾选）。

        只影响 source='pku3b' 且 remote_completed=0 的行，手动条目完全不碰。
        """
        stamp = _now()
        with self._lock:
            cur = self._conn.execute(
                "UPDATE ddl SET status = 'pending', status_locked = 0, updated_at = ? "
                "WHERE source = 'pku3b' AND deleted = 0 AND stale = 0 "
                "AND remote_completed = 0 "
                "AND (status != 'pending' OR status_locked = 1)",
                (stamp,),
            )
            self._conn.commit()
            return cur.rowcount

    # -- 维护 ----------------------------------------------------------
    def counts(self) -> dict[str, int]:
        rows = self._query(
            "SELECT source, status, COUNT(*) AS n FROM ddl "
            "WHERE deleted = 0 AND stale = 0 GROUP BY source, status"
        )
        out: dict[str, int] = {}
        for r in rows:
            out[str(r["source"]) + ":" + str(r["status"])] = int(r["n"])
        return out
