"""程序图标（运行时绘制，无需外部资源文件）。"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap

from . import theme


def app_pixmap(size: int = 64) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    rect = QRectF(0.5, 0.5, size - 1, size - 1)
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor(theme.ACCENT_SOFT))
    grad.setColorAt(1.0, QColor(theme.VIOLET))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(grad)
    painter.drawRoundedRect(rect, size * 0.28, size * 0.28)

    scale = size / 30.0
    pen = QPen(
        QColor(255, 255, 255, 245),
        max(1.6, 2.1 * scale),
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    path = QPainterPath()
    path.moveTo(8.5 * scale, 15.6 * scale)
    path.lineTo(13.2 * scale, 20.0 * scale)
    path.lineTo(21.6 * scale, 10.6 * scale)
    painter.drawPath(path)

    painter.end()
    return pixmap


def chevron_down_path() -> str:
    """生成下拉箭头 PNG（QSS 里用 url(...) 引用），返回 posix 路径。"""
    from . import paths

    target = paths.app_data_dir() / "ui_chevron_down.png"
    if not target.exists():
        size = 28
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor(160, 168, 192),
                2.6,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        painter.drawLine(9, 12, 14, 17)
        painter.drawLine(14, 17, 19, 12)
        painter.end()
        pixmap.save(str(target))
    return target.as_posix()


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size))
    return icon
