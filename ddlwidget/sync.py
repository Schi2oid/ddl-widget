"""pku3b 调用、输出解析与双源合并。

pku3b 的 assignment list 只有人读文本（无 JSON），格式由源码
src/cli/cmd_assignment.rs::write_assignment_title_ln 决定：

    {课程名} > {作业标题} ({倒计时或状态}) {短ID}

倒计时形如 in 3d 4h 20m 30s / due / 已完成: 尝试 26-9-14 下午8:17 / 无截止时间。
因为只有相对倒计时，绝对截止时间由「同步完成时刻 + 倒计时」重建（秒级精度）。
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .db import Database
from .models import DDL

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# 课程名 > 标题 (meta) 16进制短ID
LINE_RE = re.compile(r"^(?P<course>.+?) > (?P<rest>.+?) (?P<ext>[0-9a-f]{6,16})$")
META_RE = re.compile(r"^(?P<title>.*) \((?P<meta>[^()]*)\)$")
DELTA_RE = re.compile(r"^in (?:(\d+)d )?(?:(\d+)h )?(?:(\d+)m )?(\d+)s$")
CN_DATE_RE = re.compile(
    r"(\d{4})年(\d{1,2})月(\d{1,2})日 (?:星期.|周.) (上午|下午)(\d{1,2}):(\d{1,2})"
)
HEADER_RE = re.compile(r"作业 \((\d+)\)")

CREATE_NO_WINDOW = 0x08000000


@dataclass
class ParsedItem:
    ext_id: str
    course_name: str
    title: str
    meta: str
    due_time: datetime | None
    completed: bool
    has_deadline: bool = True
    raw_due: str = ""


@dataclass
class ParseResult:
    items: list[ParsedItem] = field(default_factory=list)
    declared_total: int | None = None
    unparsed_lines: list[str] = field(default_factory=list)


@dataclass
class SyncResult:
    ok: bool
    message: str = ""
    added: int = 0
    updated: int = 0
    restored: int = 0
    stale: int = 0
    total: int = 0
    duration: float = 0.0
    synced_at: datetime | None = None
    raw_tail: str = ""
    completed_ids: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------
# 调用
# ----------------------------------------------------------------------
def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def run_pku3b(exe: str, args: list[str], timeout: int = 180) -> tuple[bool, str, str, float]:
    """执行 pku3b，返回 (是否成功, stdout 文本, stderr 文本, 耗时秒)。"""
    path = Path(exe)
    if not path.exists():
        return False, "", f"找不到 pku3b：{exe}", 0.0
    started = time.monotonic()
    try:
        proc = subprocess.run(
            [str(exe), *args],
            capture_output=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            env={**os.environ, "RUST_LOG": os.environ.get("DDL_RUST_LOG", "warn")},
        )
    except subprocess.TimeoutExpired:
        return False, "", f"pku3b 执行超时（{timeout}s）", time.monotonic() - started
    except OSError as exc:
        return False, "", f"无法启动 pku3b：{exc}", time.monotonic() - started

    duration = time.monotonic() - started
    out = proc.stdout.decode("utf-8", "replace")
    err = proc.stderr.decode("utf-8", "replace")
    if proc.returncode != 0:
        detail = strip_ansi(err.strip() or out.strip()).splitlines()
        detail_text = detail[0] if detail else f"退出码 {proc.returncode}"
        return False, out, detail_text, duration
    return True, out, err, duration


# ----------------------------------------------------------------------
# 解析
# ----------------------------------------------------------------------
def _parse_meta(meta: str, ref: datetime) -> tuple[datetime | None, bool, bool]:
    """返回 (截止时间, 是否已完成, 是否有截止时间)。"""
    meta = meta.strip()
    if meta.startswith("已完成"):
        return None, True, False
    if meta == "无截止时间":
        return None, False, False

    match = DELTA_RE.match(meta)
    if match:
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        seconds = int(match.group(4) or 0)
        delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
        return _round_minute(ref + delta), False, True

    if meta == "due":
        # 已过期，pku3b 不给绝对时间
        return None, False, True

    # 日期解析失败时 pku3b 直接打印原始中文串
    found = CN_DATE_RE.search(meta)
    if found:
        year, month, day = int(found.group(1)), int(found.group(2)), int(found.group(3))
        hour, minute = int(found.group(5)), int(found.group(6))
        if found.group(4) == "下午" and hour < 12:
            hour += 12
        try:
            return datetime(year, month, day, hour, minute), False, True
        except ValueError:
            return None, False, False

    return None, False, False


def _round_minute(dt: datetime) -> datetime:
    """向最近的一分钟取整（抵消倒计时的秒级截断误差）。"""
    return (dt + timedelta(seconds=30)).replace(second=0, microsecond=0)


def parse_list_output(text: str, ref: datetime | None = None) -> ParseResult:
    """把 pku3b assignment list 的 stdout 解析成结构化条目。"""
    ref = ref or datetime.now()
    plain = strip_ansi(text)
    result = ParseResult()

    for raw_line in plain.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if result.declared_total is None:
            header = HEADER_RE.search(line)
            if header:
                result.declared_total = int(header.group(1))
                continue
        if " > " not in line:
            continue

        line_match = LINE_RE.match(line)
        if not line_match:
            continue
        rest = line_match.group("rest")
        meta_match = META_RE.match(rest)
        if not meta_match:
            result.unparsed_lines.append(line)
            continue

        title = meta_match.group("title").strip()
        meta = meta_match.group("meta").strip()
        if not title:
            result.unparsed_lines.append(line)
            continue

        due, completed, has_deadline = _parse_meta(meta, ref)
        result.items.append(
            ParsedItem(
                ext_id=line_match.group("ext"),
                course_name=line_match.group("course").strip(),
                title=title,
                meta=meta,
                due_time=due,
                completed=completed,
                has_deadline=has_deadline,
                raw_due=meta,
            )
        )

    return result


# ----------------------------------------------------------------------
# 合并
# ----------------------------------------------------------------------
def apply_sync(db: Database, parsed: ParseResult, synced_at: datetime | None = None) -> SyncResult:
    """把解析结果合并进数据库，遵守「不覆盖手动数据 / 不覆盖用户状态」原则。"""
    synced_at = synced_at or datetime.now()
    keep_ids: set[str] = set()
    completed_ids: list[str] = []
    added = updated = restored = 0

    for item in parsed.items:
        action, item_id, became_completed = db.upsert_synced(
            ext_id=item.ext_id,
            title=item.title,
            course_name=item.course_name,
            due_time=item.due_time,
            completed=item.completed,
        )
        if action == "unchanged" and item.due_time is None:
            row = db.get(item_id)
            if row is not None and row.source == "pku3b" and row.deleted == 0:
                keep_ids.add(item_id)
                continue
        keep_ids.add(item_id)
        if became_completed:
            completed_ids.append(item_id)
        if action == "added":
            added += 1
        elif action == "updated":
            updated += 1
        elif action == "restored":
            restored += 1

    stale = db.mark_stale_except(keep_ids)
    db.set_meta("last_sync_at", synced_at.replace(microsecond=0).isoformat(sep="T"))
    db.set_meta("last_sync_ok", "1")

    return SyncResult(
        ok=True,
        added=added,
        updated=updated,
        restored=restored,
        stale=stale,
        total=len(parsed.items),
        synced_at=synced_at,
        completed_ids=completed_ids,
    )


def describe_summary(result: SyncResult) -> str:
    parts: list[str] = []
    if result.added:
        parts.append(f"新增 {result.added}")
    if result.updated:
        parts.append(f"更新 {result.updated}")
    if result.stale:
        parts.append(f"移除 {result.stale}")
    return "、".join(parts) if parts else "已是最新"


def sync_now(db: Database, exe: str, args: list[str], timeout: int = 180) -> SyncResult:
    """完整同步流程：调用 pku3b -> 解析 -> 合并。"""
    ok, out, err, duration = run_pku3b(exe, args, timeout)
    if not ok:
        db.set_meta("last_sync_ok", "0")
        db.set_meta("last_sync_at", datetime.now().replace(microsecond=0).isoformat(sep="T"))
        db.set_meta("last_sync_error", err)
        return SyncResult(ok=False, message=err, duration=duration)

    parsed = parse_list_output(out, ref=datetime.now())
    if not parsed.items and parsed.declared_total is None:
        tail = strip_ansi(out).strip().splitlines()[-3:]
        message = "pku3b 无有效输出" + ("：" + " / ".join(tail) if tail else "")
        db.set_meta("last_sync_ok", "0")
        db.set_meta("last_sync_error", message)
        return SyncResult(ok=False, message=message, duration=duration, raw_tail="\n".join(tail))

    result = apply_sync(db, parsed, synced_at=datetime.now())
    result.duration = duration
    db.set_meta("last_sync_error", "")
    return result


def pending_for_briefing(db: Database, days: int = 7, now: datetime | None = None) -> list[DDL]:
    """未来 N 天内（含今天）的所有待办，按时间排序。"""
    now = now or datetime.now()
    horizon = now + timedelta(days=days)
    items = [
        item
        for item in db.visible_items(show_completed=False)
        if item.due_time is not None and item.due_time <= horizon
    ]
    items.sort(key=lambda d: d.due_time)
    return items
