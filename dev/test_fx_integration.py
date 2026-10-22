"""集成验证：点勾选 -> 幽灵卡片 -> 落地礼花。"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "fxint")

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

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
        time.sleep(0.01)


db = Database()
with db._lock:
    db._conn.execute("DELETE FROM ddl")
    db._conn.execute("DELETE FROM meta")
    db._conn.commit()

now = datetime.now().replace(second=0, microsecond=0)
db.upsert_synced("x1", "第四章书面作业", "数据结构与算法 (A)", now + timedelta(hours=3), False)
db.upsert_synced("x2", "第九次作业", "离散数学基础", now + timedelta(days=2), False)

settings = Settings()
settings.update({"show_completed": True, "list_height": None})

window = MainWindow(db, settings)
window.show()
pump(500)

item = window._rows[0].item()
print("toggle:", item.title)
window._on_toggle(item.id)
pump(80)
print("特效层动画中:", window._fx.is_animating(),
      " 粒子:", len(window._fx._particles),
      " 飞行卡:", len(window._fx._flyers))
print("目标点:", window._celebration_target().toTuple())

pump(900)
print("落地后 动画中:", window._fx.is_animating(), " 粒子:", len(window._fx._particles))

# 同步庆祝
window.celebrate_synced(["x1", "x2"])
pump(120)
print("同步庆祝 动画中:", window._fx.is_animating(), " 飞行卡:", len(window._fx._flyers))
pump(2200)
print("结束后 动画中:", window._fx.is_animating())
