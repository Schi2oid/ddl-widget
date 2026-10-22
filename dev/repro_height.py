"""复现「窗口只剩一条」的高度计算问题。"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "repro")

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from ddlwidget.db import Database  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402

db = Database()
with db._lock:
    db._conn.execute("DELETE FROM ddl")
    db._conn.execute("DELETE FROM meta")
    db._conn.commit()

settings = Settings()
window = MainWindow(db, settings)
pump = lambda: [app.processEvents() for _ in range(5)]

print("1) 空库启动:")
print("   list.sizeHint =", window._list.sizeHint().height(), " window.h =", window.height(),
      " scroll.h =", window._scroll.height())

now = datetime.now().replace(second=0, microsecond=0)
for i, delta in enumerate([timedelta(hours=5), timedelta(days=1), timedelta(days=3),
                           timedelta(days=5), timedelta(days=9), timedelta(days=14)]):
    db.upsert_synced(f"id{i}", f"作业{i}", f"课程{i}", now + delta, False)

window.reload()
pump()
print("2) 同步到 6 条后 reload:")
print("   list.sizeHint =", window._list.sizeHint().height(), " window.h =", window.height(),
      " scroll.h =", window._scroll.height())
print("   list.height =", window._list.height(), " layout.count =", window._list.layout().count())
print("   rows =", len(window._rows))

window.reload()
pump()
print("3) 再 reload 一次:")
print("   list.sizeHint =", window._list.sizeHint().height(), " window.h =", window.height(),
      " scroll.h =", window._scroll.height())

print("4) 拖拽把手 +120px:")
before = window.height()
window._on_grip_start()
for _ in range(12):
    window._on_grip_drag(10)
window._on_grip_end()
pump()
after = window.height()
print("   height", before, "->", after, " saved list_height =", settings.get("list_height"))


def read_settings():
    import json
    from ddlwidget import paths

    return json.loads(paths.settings_path().read_text(encoding="utf-8"))


print("   落盘 list_height =", read_settings().get("list_height"))

print("5) 恢复自适应:")
window.reset_height()
pump()
print("   height =", window.height(), " list_height =", read_settings().get("list_height"))

print("6) 把手几何:", window._grip.geometry().getRect(), " 可见:", window._grip.isVisible())

