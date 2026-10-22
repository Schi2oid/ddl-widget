"""自绘控件：图标按钮、分组标题、DDL 行、空状态。"""

from __future__ import annotations

import math
from datetime import datetime

from PySide6.QtCore import Property, QEasingCurve, QRect, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QAbstractButton, QSizePolicy, QWidget

from . import theme, tips
from .models import DDL, GROUP_COLOR, GROUP_LABEL
from .theme import font, rgba
from .vector_icons import draw_icon

ROW_HEIGHT = 64
RIGHT_BLOCK = 116


# ----------------------------------------------------------------------
class IconButton(QAbstractButton):
    """圆形/方角图标按钮，带 hover 过渡。"""

    def __init__(
        self,
        icon_name: str,
        size: int = 28,
        glyph_size: int = 14,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon_name = str(icon_name)
        self._glyph_size = glyph_size
        self._hover = 0.0
        self._rotation = 0.0
        self._checked_tint = False
        self._color = QColor(theme.TEXT_SECONDARY)
        self._active_color = QColor(theme.TEXT_PRIMARY)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    # -- hover 动画 -----------------------------------------------------
    def _on_anim(self, value: object) -> None:
        self._hover = float(value)
        self.update()

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._animate_to(1.0)
        tips.hover_enter(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._animate_to(0.0)
        tips.hover_leave(self)
        super().leaveEvent(event)

    # -- 外观 -----------------------------------------------------------
    def set_checked_tint(self, on: bool) -> None:
        self._checked_tint = on
        self.update()

    def set_colors(self, color: QColor, active: QColor) -> None:
        self._color = color
        self._active_color = active
        self.update()

    def set_glyph(self, icon_name: str) -> None:
        self._icon_name = str(icon_name)
        self.update()

    def set_rotation(self, degrees: float) -> None:
        self._rotation = float(degrees)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        if self._checked_tint:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(rgba(theme.ACCENT, 0.18 + 0.06 * self._hover))
            painter.drawRoundedRect(rect, 9, 9)
        elif self._hover > 0.01:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(12 + 14 * self._hover)))
            painter.drawRoundedRect(rect, 9, 9)

        if self.isDown():
            painter.setBrush(QColor(255, 255, 255, 24))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(rect, 9, 9)

        base = self._active_color if (self._hover > 0.4 or self._checked_tint) else self._color
        if not self.isEnabled():
            base = QColor(theme.TEXT_DISABLED)
        size = float(self._glyph_size)
        icon_rect = QRectF(
            (self.width() - size) / 2, (self.height() - size) / 2, size, size
        )
        draw_icon(painter, self._icon_name, icon_rect, base, 2.2, self._rotation)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.size()


# ----------------------------------------------------------------------
class LogoMark(QWidget):
    """左上角品牌标记：渐变圆角方块 + 对勾。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(30, 30)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, 30, 30)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(theme.ACCENT_SOFT))
        grad.setColorAt(1.0, QColor(theme.VIOLET))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(rect, 9, 9)

        painter.setPen(
            QPen(
                QColor(255, 255, 255, 240),
                2.0,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        path = QPainterPath()
        path.moveTo(8.5, 15.6)
        path.lineTo(13.2, 20.0)
        path.lineTo(21.6, 10.6)
        painter.drawPath(path)


# ----------------------------------------------------------------------
class GroupHeader(QWidget):
    """分组标题：彩色圆点 + 名称 + 数量 + 右侧细线。"""

    def __init__(self, key: str, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._count = count
        self.setFixedHeight(26)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def key(self) -> str:
        return self._key

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(GROUP_COLOR.get(self._key, theme.SLATE))
        label = GROUP_LABEL.get(self._key, self._key)

        cy = self.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(rgba(color.name(), 0.35))
        painter.drawEllipse(QRectF(9, cy - 4.5, 9, 9))
        painter.setBrush(color)
        painter.drawEllipse(QRectF(11, cy - 2.5, 5, 5))

        painter.setFont(font(11, 600, 0.6))
        painter.setPen(QColor(theme.TEXT_SECONDARY))
        metrics = QFontMetrics(painter.font())
        text_w = metrics.horizontalAdvance(label)
        painter.drawText(QRectF(25, 0, text_w + 6, self.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        painter.setFont(font(10, 600))
        painter.setPen(QColor(theme.TEXT_TERTIARY))
        painter.drawText(
            QRectF(25 + text_w + 8, 0, 40, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            str(self._count),
        )

        line_x = 25 + text_w + 8 + 22
        painter.setPen(QPen(QColor(255, 255, 255, 14), 1))
        painter.drawLine(int(line_x), int(cy), self.width() - 6, int(cy))


# ----------------------------------------------------------------------
class DDLRow(QWidget):
    """单条 DDL：左侧色条 + 完成勾选 + 课程/标题 + 倒计时。"""

    toggle_requested = Signal(str)
    edit_requested = Signal(str)

    def __init__(self, item: DDL, now: datetime | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item = item
        self._now = now or datetime.now()
        self._hover = 0.0
        self._pulse = 0.0
        self._placeholder = False
        self._urgency = item.urgency(self._now)
        self._color = QColor(GROUP_COLOR.get(self._urgency, theme.SLATE))
        self.setFixedHeight(ROW_HEIGHT)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._set_hover)
        self._update_tooltip()

    # -- 状态 -----------------------------------------------------------
    def item(self) -> DDL:
        return self._item

    def set_item(self, item: DDL, now: datetime | None = None) -> None:
        self._item = item
        self._now = now or datetime.now()
        self._urgency = item.urgency(self._now)
        self._color = QColor(GROUP_COLOR.get(self._urgency, theme.SLATE))
        self._update_tooltip()
        self.update()

    def set_placeholder(self, on: bool) -> None:
        """飞行期间把这个位置显示成"待落位"的虚线空槽。"""
        self._placeholder = on
        self.setCursor(
            Qt.CursorShape.ArrowCursor if on else Qt.CursorShape.PointingHandCursor
        )
        self.update()

    def set_pulse(self, value: float) -> None:
        if self._urgency in ("today", "overdue"):
            self._pulse = value
            self.update()

    def refresh_time(self, now: datetime) -> None:
        self._now = now
        new_urgency = self._item.urgency(now)
        if new_urgency != self._urgency:
            self._urgency = new_urgency
            self._color = QColor(GROUP_COLOR.get(self._urgency, theme.SLATE))
        self.update()

    def _update_tooltip(self) -> None:
        detail = " · ".join(
            part for part in (self._item.course_name, self._item.due_label(self._now)) if part
        )
        text = self._item.title
        if detail:
            text += "\n" + detail
        self.setToolTip(text)

    # -- 交互 -----------------------------------------------------------
    def _set_hover(self, value: object) -> None:
        self._hover = float(value)
        self.update()

    def _animate(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._hover)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._animate(1.0)
        tips.hover_enter(self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._animate(0.0)
        tips.hover_leave(self)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if self._placeholder:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            if pos.x() <= 42 and 14 <= pos.y() <= 50:
                self.toggle_requested.emit(self._item.id)
                return
            self.edit_requested.emit(self._item.id)
            return
        super().mousePressEvent(event)

    # -- 绘制 -----------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self._placeholder:
            self._paint_placeholder(painter)
            return

        w, h = self.width(), self.height()
        completed = self._item.is_completed
        urgent = self._urgency in ("today", "overdue")

        # 背景
        body = QRectF(0, 1, w, h - 2)
        painter.setPen(Qt.PenStyle.NoPen)
        if completed:
            base_alpha = 6
        elif urgent:
            base_alpha = 16
        else:
            base_alpha = 7
        tint = self._color if urgent else QColor(255, 255, 255)
        painter.setBrush(QColor(tint.red(), tint.green(), tint.blue(), base_alpha + int(10 * self._hover)))
        painter.drawRoundedRect(body, 12, 12)

        if self._hover > 0.02:
            painter.setBrush(QColor(255, 255, 255, int(6 * self._hover)))
            painter.drawRoundedRect(body, 12, 12)

        # 左侧色条
        if completed:
            bar_color = QColor(theme.GREEN)
            bar_color.setAlphaF(0.55)
        else:
            bar_color = QColor(self._color)
            bar_color.setAlphaF(0.95)
        painter.setBrush(bar_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(8, (h - 22) / 2, 3, 22), 1.5, 1.5)

        # 勾选圆圈
        self._draw_check(painter, completed)

        # 文本区
        text_left = 46.0
        text_width = max(40.0, w - text_left - RIGHT_BLOCK - 14)
        course = self._item.course_name or ("手动添加" if self._item.source == "manual" else "教学网")

        f_course = font(11, 500)
        painter.setFont(f_course)
        fm_course = QFontMetrics(f_course)
        painter.setPen(QColor(theme.TEXT_TERTIARY if not completed else theme.TEXT_DISABLED))
        painter.drawText(
            QRectF(text_left, 12, text_width, 16),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm_course.elidedText(course, Qt.TextElideMode.ElideRight, int(text_width)),
        )

        f_title = font(14, 600 if urgent else 500)
        f_title.setStrikeOut(completed)
        painter.setFont(f_title)
        fm_title = QFontMetrics(f_title)
        title_color = QColor(theme.TEXT_SECONDARY if completed else theme.TEXT_PRIMARY)
        painter.setPen(title_color)
        painter.drawText(
            QRectF(text_left, 31, text_width, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm_title.elidedText(self._item.title, Qt.TextElideMode.ElideRight, int(text_width)),
        )

        # 右侧：倒计时 + 截止
        right_x = w - RIGHT_BLOCK
        right_w = RIGHT_BLOCK - 16

        countdown = "已完成" if completed else self._item.countdown(self._now)
        f_cd = font(12, 600)
        painter.setFont(f_cd)
        cd_color = QColor(self._color) if not completed else QColor(theme.TEXT_DISABLED)
        if completed:
            cd_color = QColor(theme.TEXT_DISABLED)
        painter.setPen(cd_color)
        painter.drawText(
            QRectF(right_x, 13, right_w, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            countdown,
        )

        # 紧急项：倒计时左侧的呼吸圆点
        if urgent and not completed:
            fm_cd = QFontMetrics(f_cd)
            text_w = fm_cd.horizontalAdvance(countdown)
            dot_x = right_x + right_w - text_w - 12
            alpha = 0.35 + 0.6 * self._pulse
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(rgba(self._color.name(), alpha))
            painter.drawEllipse(QRectF(dot_x, 19, 5, 5))

        due_text = self._item.due_label(self._now)
        painter.setFont(font(11, 400))
        painter.setPen(QColor(theme.TEXT_TERTIARY if not completed else theme.TEXT_DISABLED))
        painter.drawText(
            QRectF(right_x, 33, right_w, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            due_text,
        )

        # 手动条目标记
        if self._item.source == "manual" and not completed:
            painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(0.5, 1.5, w - 1, h - 3), 12, 12)

    def _paint_placeholder(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        rect = QRectF(1, 2, w - 2, h - 4)
        pen = QPen(rgba(theme.ACCENT, 0.55), 1.2, Qt.PenStyle.DashLine)
        pen.setDashPattern([3, 3])
        painter.setPen(pen)
        painter.setBrush(rgba(theme.ACCENT, 0.06))
        painter.drawRoundedRect(rect, 12, 12)

        painter.setFont(font(11, 500))
        painter.setPen(rgba(theme.ACCENT_SOFT, 0.55))
        painter.drawText(
            rect,
            Qt.AlignmentFlag.AlignCenter,
            "落位中…",
        )

    def _draw_check(self, painter: QPainter, completed: bool) -> None:
        cx, cy, radius = 26.0, self.height() / 2.0, 8.5
        circle = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        if completed:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.GREEN))
            painter.drawEllipse(circle)
            painter.setPen(
                QPen(QColor(16, 20, 18, 255), 1.6, Qt.PenStyle.SolidLine,
                     Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            )
            painter.drawLine(
                int(cx - 3.6), int(cy + 0.2), int(cx - 0.8), int(cy + 3.0)
            )
            painter.drawLine(int(cx - 0.8), int(cy + 3.0), int(cx + 4.0), int(cy - 3.2))
            return

        if self._hover > 0.05:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(rgba(theme.ACCENT, 0.18 * self._hover))
            painter.drawEllipse(circle.adjusted(-3, -3, 3, 3))
            border = rgba(theme.ACCENT_SOFT, 0.55 + 0.4 * self._hover)
        else:
            border = QColor(255, 255, 255, 84)
            painter.setBrush(QColor(255, 255, 255, 8))

        painter.setPen(QPen(border, 1.4))
        painter.drawEllipse(circle)
        painter.setBrush(Qt.BrushStyle.NoBrush)


# ----------------------------------------------------------------------
class EmptyState(QWidget):
    """空列表占位。"""

    def __init__(self, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._subtitle = subtitle
        self.setMinimumHeight(150)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2

        circle = QRectF(cx - 26, cy - 56, 52, 52)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 10))
        painter.drawEllipse(circle)
        draw_icon(
            painter,
            "check",
            circle.adjusted(14, 14, -14, -14),
            rgba(theme.ACCENT, 0.9),
            stroke=2.0,
        )

        painter.setFont(font(14, 600))
        painter.setPen(QColor(theme.TEXT_SECONDARY))
        painter.drawText(
            QRectF(0, cy + 6, w, 22),
            Qt.AlignmentFlag.AlignCenter,
            self._title,
        )
        painter.setFont(font(11, 400))
        painter.setPen(QColor(theme.TEXT_TERTIARY))
        painter.drawText(
            QRectF(0, cy + 30, w, 20),
            Qt.AlignmentFlag.AlignCenter,
            self._subtitle,
        )


# ----------------------------------------------------------------------
class ToggleSwitch(QAbstractButton):
    """iOS 风格开关，替代深色主题下难看的 QCheckBox。"""

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(38, 21)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        self.toggled.connect(self._on_toggled)

    def _on_anim(self, value: object) -> None:
        self._pos = float(value)
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(0, 0, 38, 21)
        painter.setPen(Qt.PenStyle.NoPen)

        off = QColor(255, 255, 255, 30)
        on = QColor(theme.ACCENT)
        t = self._pos
        painter.setBrush(
            QColor(
                int(off.red() + (on.red() - off.red()) * t),
                int(off.green() + (on.green() - off.green()) * t),
                int(off.blue() + (on.blue() - off.blue()) * t),
                int(off.alpha() + (255 - off.alpha()) * t),
            )
        )
        painter.drawRoundedRect(track, 10.5, 10.5)

        knob_x = 3 + t * (38 - 21 + 3 - 3)
        painter.setBrush(QColor(255, 255, 255))
        painter.drawEllipse(QRectF(knob_x, 3, 15, 15))


# ----------------------------------------------------------------------
def pulse_wave(seconds: float, period: float = 2.6) -> float:
    """0..1 的呼吸曲线（正弦）。"""
    return 0.5 - 0.5 * math.cos(2 * math.pi * seconds / period)
