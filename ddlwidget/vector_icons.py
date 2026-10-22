"""矢量图标。

原来用的是 Windows 自带的 Segoe Fluent Icons 字形，换到 macOS 上会变成豆腐块。
这里改成按 24x24 网格手绘 QPainterPath，跨平台一致，也不依赖任何字体。
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

GRID = 24.0


def _pen(color: QColor, width: float = 2.2) -> QPen:
    pen = QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    return pen


def _add(p: QPainter) -> None:
    p.drawLine(QPointF(12, 5.5), QPointF(12, 18.5))
    p.drawLine(QPointF(5.5, 12), QPointF(18.5, 12))


def _arrow(p: QPainter, x: float, y: float, angle: float, size: float = 4.6) -> None:
    """在 (x, y) 处画一个实心箭头，angle 是箭头指向（0=向右）。"""
    color = QColor(p.pen().color())
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    tri = QPainterPath()
    tri.moveTo(1.2, 0)
    tri.lineTo(-size, -size * 0.72)
    tri.lineTo(-size, size * 0.72)
    tri.closeSubpath()
    p.drawPath(tri)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)


def _refresh(p: QPainter) -> None:
    rect = QRectF(4.8, 4.8, 14.4, 14.4)
    path = QPainterPath()
    path.arcMoveTo(rect, 90)
    path.arcTo(rect, 90, -280)
    p.drawPath(path)
    _arrow(p, 12.2, 5.0, 6, 4.8)


def _undo(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(17.6, 17.8)
    path.cubicTo(17.6, 10.2, 11.4, 7.6, 6.4, 9.4)
    p.drawPath(path)
    _arrow(p, 6.4, 9.4, 160, 4.8)


def _lock_body(p: QPainter) -> None:
    body = QPainterPath()
    body.addRoundedRect(QRectF(5.0, 11.0, 14.0, 9.5), 2.2, 2.2)
    p.drawPath(body)


def _lock(p: QPainter) -> None:
    _lock_body(p)
    shackle = QPainterPath()
    shackle.arcMoveTo(QRectF(8.0, 5.0, 8.0, 9.0), 0)
    shackle.arcTo(QRectF(8.0, 5.0, 8.0, 9.0), 0, 180)
    p.drawPath(shackle)


def _unlock(p: QPainter) -> None:
    _lock_body(p)
    shackle = QPainterPath()
    shackle.arcMoveTo(QRectF(11.6, 3.6, 8.0, 9.0), 30)
    shackle.arcTo(QRectF(11.6, 3.6, 8.0, 9.0), 30, 150)
    p.drawPath(shackle)


def _settings(p: QPainter) -> None:
    rows = ((6.6, 8.4), (12.0, 15.4), (17.4, 11.0))
    for y, knob in rows:
        p.drawLine(QPointF(4.0, y), QPointF(20.0, y))
        p.setBrush(QColor(p.pen().color()))
        p.drawEllipse(QPointF(knob, y), 2.0, 2.0)
        p.setBrush(Qt.BrushStyle.NoBrush)


def _close(p: QPainter) -> None:
    p.drawLine(QPointF(7.0, 7.0), QPointF(17.0, 17.0))
    p.drawLine(QPointF(17.0, 7.0), QPointF(7.0, 17.0))


def _check(p: QPainter) -> None:
    p.drawLine(QPointF(5.2, 12.6), QPointF(10.0, 17.2))
    p.drawLine(QPointF(10.0, 17.2), QPointF(18.8, 7.0))


def _warning(p: QPainter) -> None:
    triangle = QPainterPath()
    triangle.moveTo(12.0, 3.6)
    triangle.lineTo(21.0, 19.4)
    triangle.lineTo(3.0, 19.4)
    triangle.closeSubpath()
    p.drawPath(triangle)
    p.drawLine(QPointF(12.0, 9.4), QPointF(12.0, 13.8))
    p.setBrush(QColor(p.pen().color()))
    p.drawEllipse(QPointF(12.0, 16.6), 1.05, 1.05)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _pin(p: QPainter) -> None:
    p.drawLine(QPointF(9.0, 15.0), QPointF(5.0, 19.0))
    path = QPainterPath()
    path.moveTo(8.2, 4.6)
    path.lineTo(15.4, 11.8)
    path.lineTo(13.2, 14.0)
    path.lineTo(6.0, 6.8)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(13.6, 14.4), QPointF(17.4, 18.2))


def _edit(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(4.5, 19.5)
    path.lineTo(5.4, 15.0)
    path.lineTo(15.6, 4.8)
    path.lineTo(19.2, 8.4)
    path.lineTo(9.0, 18.6)
    path.closeSubpath()
    p.drawPath(path)


def _trash(p: QPainter) -> None:
    p.drawLine(QPointF(4.5, 7.5), QPointF(19.5, 7.5))
    p.drawLine(QPointF(9.5, 7.5), QPointF(9.5, 4.5))
    p.drawLine(QPointF(9.5, 4.5), QPointF(14.5, 4.5))
    p.drawLine(QPointF(14.5, 4.5), QPointF(14.5, 7.5))
    body = QPainterPath()
    body.moveTo(6.5, 7.5)
    body.lineTo(7.6, 19.6)
    body.lineTo(16.4, 19.6)
    body.lineTo(17.5, 7.5)
    p.drawPath(body)


def _chevron_down(p: QPainter) -> None:
    p.drawLine(QPointF(8.0, 10.5), QPointF(12.0, 14.5))
    p.drawLine(QPointF(12.0, 14.5), QPointF(16.0, 10.5))


_DRAW = {
    "add": _add,
    "refresh": _refresh,
    "undo": _undo,
    "lock": _lock,
    "unlock": _unlock,
    "settings": _settings,
    "close": _close,
    "check": _check,
    "warning": _warning,
    "pin": _pin,
    "unpin": _pin,
    "edit": _edit,
    "delete": _trash,
    "chevron_down": _chevron_down,
}


def draw_icon(
    painter: QPainter,
    name: str,
    rect: QRectF,
    color: QColor,
    stroke: float = 2.2,
    rotation: float = 0.0,
) -> None:
    draw = _DRAW.get(name)
    if draw is None:
        return
    size = min(rect.width(), rect.height())
    if size <= 0:
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.translate(rect.center())
    if abs(rotation) > 0.01:
        painter.rotate(rotation)
    painter.scale(size / GRID, size / GRID)
    painter.translate(-GRID / 2, -GRID / 2)
    painter.setPen(_pen(color, stroke))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    draw(painter)
    painter.restore()


def icon_size_for(px: int) -> float:
    """图标内容区大概占字号的多大——用来把字体尺寸换算成图形尺寸。"""
    return max(6.0, px * 1.05)
