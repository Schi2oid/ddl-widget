"""矢量图标。

原来用的是 Windows 自带的 Segoe Fluent Icons 字形，换到 macOS 上会变成豆腐块。
这里改成按网格手绘 QPainterPath，跨平台一致，也不依赖任何字体。

坐标约定：24x24 网格，图形大致占 3~21（即 18 个单位）。
draw_icon 会按 18 个单位去缩放，这样 14px 的图标就是实打实 14px 的视觉大小，
而不是缩到 24 格里的 13/24。
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

GRID = 24.0
SPAN = 18.0


def _pen(color: QColor, width: float = 2.2) -> QPen:
    return QPen(
        color,
        width,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )


def _arrow(p: QPainter, x: float, y: float, angle: float, size: float = 5.4) -> None:
    """实心箭头，angle 是箭头指向（0=向右，顺时针为正，屏幕坐标）。"""
    color = QColor(p.pen().color())
    p.save()
    p.translate(x, y)
    p.rotate(angle)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(color)
    tri = QPainterPath()
    tri.moveTo(1.6, 0)
    tri.lineTo(-size, -size * 0.66)
    tri.lineTo(-size * 0.62, 0)
    tri.lineTo(-size, size * 0.66)
    tri.closeSubpath()
    p.drawPath(tri)
    p.restore()
    p.setBrush(Qt.BrushStyle.NoBrush)


def _add(p: QPainter) -> None:
    p.drawLine(QPointF(12, 4.0), QPointF(12, 20.0))
    p.drawLine(QPointF(4.0, 12), QPointF(20.0, 12))


def _refresh(p: QPainter) -> None:
    cx, cy, r = 12.0, 12.0, 7.1
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    path = QPainterPath()
    # 从 100° 逆时针画 300°，缺口留在 40°~100°（右上方）
    path.arcMoveTo(rect, 100)
    path.arcTo(rect, 100, 300)
    p.drawPath(path)
    # 弧线终点在 40°，逆时针切线朝左上
    end_deg = 40.0
    angle = math.radians(end_deg)
    _arrow(
        p,
        cx + r * math.cos(angle),
        cy - r * math.sin(angle),
        -90.0 - end_deg,
        6.4,
    )


def _undo(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(18.6, 20.0)
    path.cubicTo(18.6, 10.4, 11.6, 6.2, 5.2, 8.6)
    p.drawPath(path)
    _arrow(p, 5.2, 8.6, 162, 7.0)


def _lock_body(p: QPainter) -> None:
    body = QPainterPath()
    body.addRoundedRect(QRectF(5.6, 10.8, 12.8, 9.8), 2.3, 2.3)
    p.drawPath(body)


def _lock(p: QPainter) -> None:
    _lock_body(p)
    shackle = QPainterPath()
    shackle.arcMoveTo(QRectF(7.9, 3.0, 8.2, 10.6), 0)
    shackle.arcTo(QRectF(7.9, 3.0, 8.2, 10.6), 0, 180)
    p.drawPath(shackle)
    p.setBrush(QColor(p.pen().color()))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(12.0, 15.7), 1.4, 1.4)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _unlock(p: QPainter) -> None:
    _lock_body(p)
    shackle = QPainterPath()
    shackle.arcMoveTo(QRectF(11.2, 2.2, 8.2, 10.6), 25)
    shackle.arcTo(QRectF(11.2, 2.2, 8.2, 10.6), 25, 155)
    p.drawPath(shackle)
    p.setBrush(QColor(p.pen().color()))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(12.0, 15.7), 1.4, 1.4)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _gear_path(cx: float, cy: float, teeth: int = 8) -> QPainterPath:
    r_root, r_tip = 6.0, 8.8
    path = QPainterPath()
    step = math.tau / teeth
    half_tip = step * 0.17
    half_root = step * 0.26
    for index in range(teeth):
        angle = index * step
        points = (
            (angle - half_root, r_root),
            (angle - half_tip, r_tip),
            (angle + half_tip, r_tip),
            (angle + half_root, r_root),
        )
        for point_index, (theta, radius) in enumerate(points):
            x = cx + radius * math.cos(theta)
            y = cy - radius * math.sin(theta)
            if index == 0 and point_index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        # 齿之间的根部圆弧，用直线近似足够
    path.closeSubpath()
    return path


def _settings(p: QPainter) -> None:
    p.drawPath(_gear_path(12.0, 12.0, teeth=8))
    p.setBrush(Qt.BrushStyle.NoBrush)


def _close(p: QPainter) -> None:
    p.drawLine(QPointF(5.5, 5.5), QPointF(18.5, 18.5))
    p.drawLine(QPointF(18.5, 5.5), QPointF(5.5, 18.5))


def _check(p: QPainter) -> None:
    p.drawLine(QPointF(4.0, 12.4), QPointF(9.8, 18.0))
    p.drawLine(QPointF(9.8, 18.0), QPointF(20.0, 5.8))


def _warning(p: QPainter) -> None:
    triangle = QPainterPath()
    triangle.moveTo(12.0, 2.8)
    triangle.lineTo(21.6, 20.4)
    triangle.lineTo(2.4, 20.4)
    triangle.closeSubpath()
    p.drawPath(triangle)
    p.drawLine(QPointF(12.0, 9.6), QPointF(12.0, 14.2))
    p.setBrush(QColor(p.pen().color()))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(12.0, 17.0), 1.15, 1.15)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _pin(p: QPainter) -> None:
    p.drawLine(QPointF(9.4, 14.6), QPointF(5.0, 19.0))
    path = QPainterPath()
    path.moveTo(8.0, 4.0)
    path.lineTo(16.0, 12.0)
    path.lineTo(13.4, 14.6)
    path.lineTo(5.4, 6.6)
    path.closeSubpath()
    p.drawPath(path)


def _edit(p: QPainter) -> None:
    path = QPainterPath()
    path.moveTo(4.0, 20.0)
    path.lineTo(5.0, 15.0)
    path.lineTo(15.8, 4.2)
    path.lineTo(19.8, 8.2)
    path.lineTo(9.0, 19.0)
    path.closeSubpath()
    p.drawPath(path)


def _trash(p: QPainter) -> None:
    p.drawLine(QPointF(4.0, 6.8), QPointF(20.0, 6.8))
    p.drawLine(QPointF(9.4, 6.8), QPointF(9.4, 3.4))
    p.drawLine(QPointF(9.4, 3.4), QPointF(14.6, 3.4))
    p.drawLine(QPointF(14.6, 3.4), QPointF(14.6, 6.8))
    body = QPainterPath()
    body.moveTo(6.0, 6.8)
    body.lineTo(7.2, 20.2)
    body.lineTo(16.8, 20.2)
    body.lineTo(18.0, 6.8)
    p.drawPath(body)


def _chevron_down(p: QPainter) -> None:
    p.drawLine(QPointF(7.0, 9.5), QPointF(12.0, 14.5))
    p.drawLine(QPointF(12.0, 14.5), QPointF(17.0, 9.5))


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
    stroke: float = 2.0,
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
    painter.scale(size / SPAN, size / SPAN)
    painter.translate(-GRID / 2, -GRID / 2)
    painter.setPen(_pen(color, stroke))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    draw(painter)
    painter.restore()
