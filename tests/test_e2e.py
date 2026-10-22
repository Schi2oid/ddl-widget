"""端到端自检：真实子进程调用 + 解析 + 入库 + 自启注册表。"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ddlwidget import winutil
from ddlwidget.db import Database
from ddlwidget.models import URGENT_NONE, URGENT_TODAY, URGENT_WEEK
from ddlwidget.sync import sync_now

TMP = ROOT / ".tmp"
TMP.mkdir(exist_ok=True)

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


def fresh_db(name: str) -> Database:
    target = TMP / name
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(target) + suffix)
        if candidate.exists():
            candidate.unlink()
    return Database(target)


def test_sync_ok() -> None:
    print("[sync 成功路径]")
    db = fresh_db("e2e_ok.db")
    script = str(ROOT / "tests" / "fake_pku3b_ok.py")
    result = sync_now(db, sys.executable, [script], timeout=60)

    check("同步返回成功", result.ok, result.message)
    check("解析到 4 条", result.total == 4, f"total={result.total}")
    check("新增 4 条", result.added == 4, f"added={result.added}")

    items = {i.title: i for i in db.all_items()}
    check("课程名正确", items.get("第三次作业").course_name == "计算概论A")
    check("已完成入库", items.get("实验一").status == "completed")
    check("无截止入库", items.get("习题课").due_time is None)

    now = datetime.now()
    third = items["第三次作业"]
    check("倒计时换算≈4h20m", abs((third.due_time - now).total_seconds() - (4 * 3600 + 20 * 60)) < 120,
          str(third.due_time))
    check("紧急度=today", third.urgency(now) == URGENT_TODAY, third.urgency(now))
    check("大作业=week", items["大作业（含报告）"].urgency(now) == URGENT_WEEK)
    check("习题课=none", items["习题课"].urgency(now) == URGENT_NONE)
    check("last_sync_ok 已记录", db.get_meta("last_sync_ok") == "1")
    check("last_sync_at 已记录", bool(db.get_meta("last_sync_at")))

    # 第二次同步：不应重复新增
    again = sync_now(db, sys.executable, [script], timeout=60)
    check("二次同步无新增", again.added == 0, f"added={again.added}")
    check("二次同步无 stale", again.stale == 0, f"stale={again.stale}")
    check("条目总数仍为 4", len(db.all_items()) == 4, str(len(db.all_items())))
    db.close()


def test_sync_fail() -> None:
    print("[sync 失败路径]")
    db = fresh_db("e2e_fail.db")
    script = str(ROOT / "tests" / "fake_pku3b_fail.py")
    result = sync_now(db, sys.executable, [script], timeout=60)
    check("失败被捕获", not result.ok)
    check("错误信息可读", "OTP" in result.message or "tls" in result.message, result.message)
    check("last_sync_ok=0", db.get_meta("last_sync_ok") == "0")
    db.close()

    print("[pku3b 不存在]")
    db2 = fresh_db("e2e_missing.db")
    result2 = sync_now(db2, str(TMP / "nope.exe"), ["a"], timeout=10)
    check("路径缺失有提示", not result2.ok and "找不到" in result2.message, result2.message)
    db2.close()


def test_autostart() -> None:
    print("[开机自启注册表]")
    original = winutil.autostart_enabled()
    try:
        ok, message = winutil.set_autostart(True)
        if not ok:
            print(f"  skip 当前环境不允许写注册表：{message}")
            print(f"       待写入命令: {winutil.launch_command()}")
            return
        check("写入成功", ok)
        enabled = winutil.autostart_enabled()

        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, winutil.RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, winutil.RUN_VALUE)
        print(f"       注册表值: {value}")
        check("写入后已启用", enabled)
        check("启动命令含 run.pyw", "run.pyw" in value, value)
        check("启动命令用的是 pythonw", "pythonw" in value.lower(), value)

        winutil.set_autostart(False)
        check("关闭后已移除", not winutil.autostart_enabled())
    finally:
        if original:
            winutil.set_autostart(True)
        else:
            winutil.set_autostart(False)


if __name__ == "__main__":
    test_sync_ok()
    test_sync_fail()
    test_autostart()
    print(f"\n通过 {passed} / {passed + failed}")
    sys.exit(1 if failed else 0)
