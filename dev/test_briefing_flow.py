"""在真实平台上验证简报弹窗流程：构造 -> 强制确认 -> 记录日期。"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "brief")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from ddlwidget.app import App  # noqa: E402
from ddlwidget.db import Database  # noqa: E402

# 清库并造数据
db = Database()
with db._lock:
    db._conn.execute("DELETE FROM ddl")
    db._conn.execute("DELETE FROM meta")
    db._conn.commit()

now = datetime.now()
base = now.replace(second=0, microsecond=0)
db.upsert_synced("aaa111", "第三次作业", "计算概论A", base + timedelta(hours=2), False)
db.upsert_synced("bbb222", "实验二", "操作系统", base + timedelta(days=2), False)
db.upsert_synced("ccc333", "读书报告", "大学英语", base + timedelta(days=5), False)

controller = App(app)
print("meta before:", repr(db.get_meta("last_daily_popup_date")))

state = {"grabbed": False, "must_ack": None}


def ack_dialog() -> None:
    dialog = QApplication.activeModalWidget()
    if dialog is None:
        QTimer.singleShot(300, ack_dialog)
        return
    state["must_ack"] = getattr(dialog, "_must_ack", None)
    pixmap = dialog.grab()
    out = ROOT / "dev" / "shots" / "briefing_live.png"
    pixmap.save(str(out))
    print("grabbed briefing ->", out, pixmap.width(), "x", pixmap.height())
    state["grabbed"] = True
    dialog._ack()


QTimer.singleShot(800, ack_dialog)
controller._show_briefing()

print("must_ack:", state["must_ack"], "(True = 必须点已知晓)")
print("meta after:", repr(db.get_meta("last_daily_popup_date")))
print("today:", datetime.now().strftime("%Y-%m-%d"))
controller.quit()
