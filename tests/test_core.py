"""核心层自检：不依赖 pytest，直接 python tests/test_core.py 运行。"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ddlwidget.db import Database
from ddlwidget.models import DDL, group_items
from ddlwidget.sync import apply_sync, parse_list_output, strip_ansi

# clap 的 Style 会输出 ANSI 转义，这里模拟真实 stdout
CYAN = "\x1b[36m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"
RED = "\x1b[31m"
YELLOW = "\x1b[33m"
RESET = "\x1b[0m"

FIXTURE = f"""\
{DIM}>{RESET} {BOLD}未完成作业 (5){RESET} {DIM}<{RESET}

{CYAN}{BOLD}计算概论A{BOLD}{RESET} {DIM}>{RESET} {CYAN}{BOLD}第三次作业{RESET} ({RED}in 4h 20m 30s{RESET}) f4f30444c7485d49

作业描述第一段
{DIM}[附件]{RESET} handout.pdf

{CYAN}{BOLD}数据结构{BOLD}{RESET} {DIM}>{RESET} {CYAN}{BOLD}大作业（含报告）{RESET} ({YELLOW}in 3d 2h 5m 0s{RESET}) 9c1a7f30b2e54d18

{CYAN}{BOLD}线性代数{BOLD}{RESET} {DIM}>{RESET} {CYAN}{BOLD}习题课作业{RESET} ({DIM}无截止时间{RESET}) 1a2b3c4d5e6f7a8b

{CYAN}{BOLD}操作系统{BOLD}{RESET} {DIM}>{RESET} {CYAN}{BOLD}实验一{RESET} ({DIM}已完成: 尝试 26-9-14 下午8:17{RESET}) 2b3c4d5e6f7a8b9c

{CYAN}{BOLD}编译原理{BOLD}{RESET} {DIM}>{RESET} {CYAN}{BOLD}词法分析{RESET} ({RED}due{RESET}) 3c4d5e6f7a8b9c0d

{CYAN}{BOLD}人工智能{BOLD}{RESET} {DIM}>{RESET} {CYAN}{BOLD}论文阅读{RESET} (2026年11月20日 星期五 下午11:59) 4d5e6f7a8b9c0d1e
"""

passed = 0
failed = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {extra}")


def test_parse() -> None:
    print("[parse]")
    ref = datetime(2026, 10, 22, 19, 0, 0)
    res = parse_list_output(FIXTURE, ref=ref)

    check("头部计数解析", res.declared_total == 5, f"got {res.declared_total}")
    check("条目数量", len(res.items) == 6, f"got {len(res.items)}")

    by_title = {i.title: i for i in res.items}
    third = by_title.get("第三次作业")
    check("课程名", third is not None and third.course_name == "计算概论A", str(third))
    check("短 ID", third is not None and third.ext_id == "f4f30444c7485d49")
    check(
        "24h 内倒计时换算",
        third is not None and third.due_time == datetime(2026, 10, 22, 23, 21),
        str(third.due_time if third else None),
    )

    big = by_title.get("大作业（含报告）")
    check("标题含全角括号不被截断", big is not None, str(list(by_title)))
    check(
        "3 天倒计时换算",
        big is not None and big.due_time == datetime(2026, 10, 25, 21, 5),
        str(big.due_time if big else None),
    )

    none_item = by_title.get("习题课作业")
    check("无截止时间", none_item is not None and none_item.due_time is None)

    done = by_title.get("实验一")
    check("已完成识别", done is not None and done.completed)

    overdue = by_title.get("词法分析")
    check("已逾期识别", overdue is not None and overdue.has_deadline and overdue.due_time is None)

    raw = by_title.get("论文阅读")
    check(
        "中文原始日期兜底",
        raw is not None and raw.due_time == datetime(2026, 11, 20, 23, 59),
        str(raw.due_time if raw else None),
    )
    check("ANSI 已剥离", "\x1b" not in strip_ansi(FIXTURE))


def test_merge() -> None:
    print("[merge]")
    tmp_dir = ROOT / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    tmp = tmp_dir / "t.db"
    if tmp.exists():
        tmp.unlink()
    db = Database(tmp)
    ref = datetime(2026, 10, 22, 19, 0, 0)
    parsed = parse_list_output(FIXTURE, ref=ref)

    manual = db.add_manual("手动：读论文", "自学", datetime(2026, 10, 23, 12, 0))
    res = apply_sync(db, parsed, synced_at=ref)
    check("首次同步新增", res.added == 6, f"added={res.added} total={res.total}")
    check("手动条目仍在", db.get(manual.id) is not None)

    items = db.visible_items()
    check("visible 不含已完成", all(not i.is_completed for i in items))

    pku_item = next(i for i in db.all_items() if i.title == "第三次作业")
    db.set_status(pku_item.id, "completed")
    after = db.get(pku_item.id)
    check("手动标记完成后 status_locked", after is not None and after.status_locked == 1)

    # 再同步一次：教学网仍是未完成，但不能把用户标记翻回去
    apply_sync(db, parsed, synced_at=ref)
    again = db.get(pku_item.id)
    check("同步不覆盖用户完成状态", again is not None and again.status == "completed")

    # 手动条目永不被 pku3b 同步触碰
    manual_after = db.get(manual.id)
    check("同步不触碰手动条目", manual_after is not None and manual_after.status == "pending")

    # 删除的教学网条目不会被复活
    other = next(i for i in db.all_items() if i.title == "大作业（含报告）")
    db.delete(other.id)
    apply_sync(db, parsed, synced_at=ref)
    deleted_row = db.get(other.id)
    check("删除后不复活", deleted_row is not None and deleted_row.deleted == 1)

    # 教学网上消失的条目 -> stale
    partial = parse_list_output(
        "\x1b[1m未完成作业 (1)\x1b[0m\n\n"
        "\x1b[36m\x1b[1m计算概论A\x1b[0m > \x1b[1m第三次作业\x1b[0m "
        "(\x1b[31min 2h 0m 0s\x1b[0m) f4f30444c7485d49\n",
        ref=ref,
    )
    res2 = apply_sync(db, partial, synced_at=ref)
    check("消失条目置 stale", res2.stale >= 1, f"stale={res2.stale}")
    check("stale 条目不显示", all(i.title != "习题课作业" for i in db.visible_items()))

    db.close()


def test_reset_remote_pending() -> None:
    print("[重置为待办]")
    tmp_dir = ROOT / ".tmp"
    tmp_dir.mkdir(exist_ok=True)
    tmp = tmp_dir / "reset.db"
    if tmp.exists():
        tmp.unlink()
    db = Database(tmp)
    ref = datetime(2026, 10, 22, 19, 0, 0)
    parsed = parse_list_output(FIXTURE, ref=ref)
    apply_sync(db, parsed, synced_at=ref)

    items = {i.title: i for i in db.all_items()}
    pending_item = items["第三次作业"]
    done_item = items["实验一"]
    check("同步后已提交项标记 remote_completed",
          done_item.remote_completed == 1 and done_item.status == "completed")

    # 用户手动把未提交的作业勾成完成
    db.set_status(pending_item.id, "completed")
    locked = db.get(pending_item.id)
    check("手动勾选后 status_locked=1", locked.status_locked == 1)
    check("手动勾选不改变 remote_completed", locked.remote_completed == 0)

    # 一键重置：只影响教学网未提交的
    changed = db.reset_remote_pending()
    check("重置影响 1 条", changed == 1, f"changed={changed}")
    after = db.get(pending_item.id)
    check("被我勾掉的变回待办", after.status == "pending" and after.status_locked == 0)
    check("教学网已提交的不受影响", db.get(done_item.id).status == "completed")

    # 再点一次不应有变化
    check("重复重置无副作用", db.reset_remote_pending() == 0)
    db.close()


def test_grouping() -> None:
    print("[grouping]")
    now = datetime(2026, 10, 22, 19, 0, 0)
    rows = [
        DDL(id="a", title="A", due_time=now + timedelta(hours=2)),
        DDL(id="b", title="B", due_time=now + timedelta(hours=30)),
        DDL(id="c", title="C", due_time=now + timedelta(days=10)),
        DDL(id="d", title="D", due_time=now - timedelta(hours=1)),
        DDL(id="e", title="E", due_time=None),
    ]
    groups = group_items(rows, now)
    keys = [k for k, _ in groups]
    check("分组顺序", keys == ["overdue", "today", "week", "later", "none"], str(keys))
    check("今日倒计时文案", rows[0].countdown(now).startswith("剩 2 小时"), rows[0].countdown(now))
    check("逾期文案", rows[3].countdown(now).startswith("已逾期"), rows[3].countdown(now))
    check("今日显示", rows[0].due_label(now).startswith("今天 "), rows[0].due_label(now))


if __name__ == "__main__":
    test_parse()
    test_merge()
    test_reset_remote_pending()
    test_grouping()
    print(f"\n通过 {passed} / {passed + failed}")
    sys.exit(1 if failed else 0)
