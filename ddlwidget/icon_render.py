"""图标后端：Windows 用系统字形，其它平台用矢量。

Windows 上的 Segoe Fluent Icons 是微软专门做过光学微调的，小尺寸下比手绘矢量更精神，
所以默认沿用系统字形；macOS 没有这套字体，自动回退到 vector_icons 里手绘的那套。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontDatabase, QPainter

from . import theme
from . import vector_icons

_glyph_checked = False
_glyph_ok = False


def glyph_available() -> bool:
    global _glyph_checked, _glyph_ok
    if _glyph_checked:
        return _glyph_ok
    _glyph_checked = True
    if not sys.platform.startswith("win"):
        _glyph_ok = False
        return _glyph_ok
    try:
        _glyph_ok = theme.ICON_FAMILY in QFontDatabase.families()
    except Exception:  # noqa: BLE001
        _glyph_ok = False
    return _glyph_ok


def icon_px(size: int) -> int:
    """字形与矢量在视觉重量上差 1px，按后端补偿。"""
    return size if glyph_available() else size + 1


def draw_icon(
    painter: QPainter,
    name: str,
    rect: QRectF,
    color: QColor,
    stroke: float = 2.2,
    rotation: float = 0.0,
) -> None:
    if glyph_available():
        _draw_glyph(painter, name, rect, color, rotation)
        return
    vector_icons.draw_icon(painter, name, rect, color, stroke, rotation)


def _draw_glyph(
    painter: QPainter, name: str, rect: QRectF, color: QColor, rotation: float
) -> None:
    glyph = theme.ICONS.get(name)
    if not glyph:
        vector_icons.draw_icon(painter, name, rect, color, 2.2, rotation)
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    if abs(rotation) > 0.01:
        center = rect.center()
        painter.translate(center)
        painter.rotate(rotation)
        painter.translate(-center)
    painter.setFont(theme.icon_font(rect.height()))
    painter.setPen(color)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, glyph)
    painter.restore()
