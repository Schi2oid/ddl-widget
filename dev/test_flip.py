"""验证 FLIP：勾选后其它行是滑过去，而不是瞬间跳；完成行先藏起来等幽灵卡片落地。"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "flip")

from ddlwidget.sysutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import QCoreApplication, QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from ddlwidget.db import Database  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402


def pump(ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


db = Database()
with db._lock:
    db._conn.execute("DELETE FROM ddl")
    db._conn.execute("DELETE FROM meta")
    db._conn.commit()

now = datetime.now().replace(second=0, microsecond=0)
db.upsert_synced("f1", "第一章", "数据结构与算法 (A)", now + timedelta(hours=2), False)
db.upsert_synced("f2", "第二章", "数据结构与算法 (A)", now + timedelta(days=1), False)
db.upsert_synced("f3", "第三章", "数据结构与算法 (A)", now + timedelta(days=3), False)
db.upsert_synced("f4", "第四次", "离散数学基础", now + timedelta(days=5), False)
db.upsert_synced("f5", "旧作业", "离散数学基础", now - timedelta(days=10), True)

settings = Settings()
settings.update({"show_completed": True, "list_height": None})

window = MainWindow(db, settings)
window.show()
pump(500)

target_item = window._rows[0].item()
others = [r for r in window._rows if r.item().id != target_item.id]
watch = others[0]
watch_id = watch.item().id
print("勾选:", target_item.title, " 观察行:", watch.item().title)

print("重排前:", {f"{r.item().title[:6]}({r.item().status[:4]})": r.y() for r in window._rows})

window._on_toggle(target_item.id)

samples = []
start = time.monotonic()
for _ in range(60):
    app.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    time.sleep(0.008)
    elapsed = (time.monotonic() - start) * 1000
    row = next((r for r in window._rows if r.item().id == watch_id), None)
    done = next((r for r in window._rows if r.item().id == target_item.id), None)
    samples.append((elapsed, row.y() if row else None, done.isVisible() if done else None))

for mark in (0, 100, 200, 300, 420, 600):
    closest = min(samples, key=lambda s: abs(s[0] - mark))
    print(f"  t={closest[0]:5.0f}ms  观察行 y={closest[1]}  完成行可见={closest[2]}")

print("重排后:", {f"{r.item().title[:6]}({r.item().status[:4]})": r.y() for r in window._rows})
print("已完成区顺序:", [r.item().title for r in window._rows if r.item().is_completed])

ys = [s[1] for s in samples if s[1] is not None]
moves = sum(1 for a, b in zip(ys, ys[1:]) if a != b)
print("位置变化次数:", moves, "(>3 说明是动画而非瞬移)")

after = next((r for r in window._rows if r.item().id == target_item.id), None)
print("完成行最终可见:", after.isVisible() if after else None)
pump(400)
print("动画结束后 布局启用:", window._list_layout.isEnabled())
