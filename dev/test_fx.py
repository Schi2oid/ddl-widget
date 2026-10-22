"""离屏渲染特效帧，检查礼花与飞行卡片的观感。"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import QPoint, QRect  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from PySide6.QtGui import QFontDatabase  # noqa: E402

for _f in ("msyh.ttc", "segoeui.ttf", "SegoeIcons.ttf"):
    QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + _f)

from ddlwidget.fx import FxOverlay, check_chip  # noqa: E402

overlay = FxOverlay()
overlay.setGeometry(0, 0, 800, 800)
overlay.show()
app.processEvents()


def frames(count: int, dt: float = 0.016) -> None:
    for _ in range(count):
        overlay._last = time.monotonic() - dt
        overlay._step()


def wallpaper(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor(40, 46, 70))
    grad.setColorAt(1.0, QColor(20, 22, 34))
    painter.fillRect(0, 0, width, height, grad)
    glow = QRadialGradient(width * 0.5, height * 0.35, width * 0.6)
    glow.setColorAt(0.0, QColor(90, 110, 200, 70))
    glow.setColorAt(1.0, QColor(90, 110, 200, 0))
    painter.fillRect(0, 0, width, height, glow)
    painter.end()
    return image


def compose(widget, region: QRect, name: str) -> None:
    grabbed = widget.grab()
    canvas = wallpaper(region.width(), region.height())
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(0, 0, grabbed, region.x(), region.y(), region.width(), region.height())
    painter.end()
    out = ROOT / "dev" / "shots" / name
    canvas.save(str(out))
    print("saved", out)


# 1) 礼花：爆开中段
overlay.burst(QPoint(400, 470), 120, 1.2)
frames(11)
compose(overlay, QRect(80, 150, 640, 480), "fx_burst.png")

# 2) 飞行卡片：四个时刻拼成一条
for p in list(overlay._particles):
    pass
overlay._particles.clear()
overlay._rings.clear()
overlay._flyers.clear()
overlay.fly(check_chip(), QPoint(110, 620), QPoint(650, 300), 0.62)
strip = QImage(1600, 250, QImage.Format.Format_ARGB32)
painter = QPainter(strip)
bg = wallpaper(400, 250)
for index, step in enumerate((6, 6, 6, 7)):
    frames(step)
    grabbed = overlay.grab()
    painter.drawImage(index * 400, 0, bg)
    painter.drawPixmap(QRect(index * 400, 0, 400, 250), grabbed, QRect(0, 190, 800, 500))
    painter.setPen(QColor(255, 255, 255, 170))
    label = f"t={overlay._flyers[0].age:.2f}s" if overlay._flyers else "landed"
    painter.drawText(index * 400 + 10, 20, label)
painter.end()
out = ROOT / "dev" / "shots" / "fx_flight.png"
strip.save(str(out))
print("saved", out)
