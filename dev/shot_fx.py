"""把飞行/礼花与窗口合成一张真实比例的预览图。"""

import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "fxshot")

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import QCoreApplication, QEvent, QRect  # noqa: E402
from PySide6.QtGui import QColor, QFontDatabase, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")
for _f in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "seguisb.ttf", "SegoeIcons.ttf"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + _f)

from ddlwidget.db import Database  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402


def pump(ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        # 让 deleteLater 真正生效，否则旧行会和新行叠在一起
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.01)


db = Database()
with db._lock:
    db._conn.execute("DELETE FROM ddl")
    db._conn.execute("DELETE FROM meta")
    db._conn.commit()

now = datetime.now().replace(second=0, microsecond=0)
db.upsert_synced("g0", "第三次作业", "数据结构与算法 (A)", now - timedelta(days=4), True)
db.upsert_synced("g1", "第四章书面作业", "数据结构与算法 (A)", now + timedelta(hours=3), False)
db.upsert_synced("g2", "第九次作业", "离散数学基础", now + timedelta(days=2), False)
db.upsert_synced("g3", "第9-10讲作业", "计算机系统导论讨论班", now + timedelta(days=5), False)

settings = Settings()
settings.update({"show_completed": True, "list_height": None, "window_pos": [140, 90]})

window = MainWindow(db, settings)
window.move(140, 90)
window.show()
pump(600)

MARGIN = 130
geo = window.geometry()
canvas_w = geo.width() + MARGIN * 2
canvas_h = geo.height() + MARGIN * 2


def wallpaper(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor(42, 48, 74))
    grad.setColorAt(1.0, QColor(18, 20, 30))
    painter.fillRect(0, 0, width, height, grad)
    glow = QRadialGradient(width * 0.4, height * 0.3, width * 0.7)
    glow.setColorAt(0.0, QColor(96, 116, 210, 80))
    glow.setColorAt(1.0, QColor(96, 116, 210, 0))
    painter.fillRect(0, 0, width, height, glow)
    painter.end()
    return image


def composite(name: str) -> None:
    base = wallpaper(canvas_w, canvas_h)
    painter = QPainter(base)
    painter.drawPixmap(MARGIN, MARGIN, window.grab())
    overlay = window._fx.grab()
    painter.drawPixmap(
        0,
        0,
        overlay,
        geo.x() - MARGIN,
        geo.y() - MARGIN,
        canvas_w,
        canvas_h,
    )
    painter.end()
    out = ROOT / "dev" / "shots" / name
    base.save(str(out))
    print("saved", out)


pending_rows = [r for r in window._rows if not r.item().is_completed]
item = pending_rows[0].item()
print("完成:", item.title)
window._on_toggle(item.id)
pump(240)
composite("fx_flight_live.png")
pump(520)
composite("fx_land_live.png")
