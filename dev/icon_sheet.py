"""把矢量图标铺成一张对照表，检查形状。"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from ddlwidget.sysutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ddlwidget.vector_icons import _DRAW, draw_icon  # noqa: E402

app = QApplication(sys.argv)

names = list(_DRAW.keys())
cell = 90
cols = 6
rows = (len(names) + cols - 1) // cols
pm = QPixmap(cols * cell, rows * cell + 30)
pm.fill(QColor(24, 26, 36))
p = QPainter(pm)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
font = QFont("Microsoft YaHei UI")
font.setPixelSize(10)
p.setFont(font)

for index, name in enumerate(names):
    cx = (index % cols) * cell
    cy = (index // cols) * cell
    for j, size in enumerate((14, 18, 22)):
        rect = QRectF(cx + 14 + j * 26, cy + 22, size, size)
        draw_icon(p, name, rect, QColor("#C8CEE0"), stroke=2.2)
    p.setPen(QColor("#8A90A6"))
    p.drawText(QRectF(cx, cy + 58, cell, 18), Qt.AlignmentFlag.AlignCenter, name)

p.end()
out = ROOT / "dev" / "shots" / "icon_sheet.png"
pm.save(str(out))
print("saved", out, pm.width(), "x", pm.height())
