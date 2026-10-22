"""自绘悬停提示。

不用 QToolTip 的原因：Windows 上 Qt 的原生 tooltip 会额外创建一个
SysShadow 阴影窗口，在部分 DWM 配置下整块渲染成黑色，看起来像凭空多出一个黑窗。
这里改成无边框、无阴影、自绘的圆角卡片。
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QFontMetrics, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QWidget

from . import theme
from .theme import font

TIP_FONT_SIZE = 11
TIP_PADDING_X = 11
TIP_PADDING_Y = 7
TIP_MAX_WIDTH = 320
TIP_OFFSET = (16, 22)
TIP_DURATION = 5000


def _wrap(metrics: QFontMetrics, text: str, max_width: int) -> list[str]:
    """按像素宽度折行（中文按字切，够用且不会把词切得很怪）。"""
    if max_width <= 0 or metrics.horizontalAdvance(text) <= max_width:
        return [text]
    lines: list[str] = []
    current = ""
    for ch in text:
        if current and metrics.horizontalAdvance(current + ch) > max_width:
            lines.append(current)
            current = ch
        else:
            current += ch
    if current:
        lines.append(current)
    return lines or [text]


class TipWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._lines: list[str] = []
        self._text_width = 0

    # ------------------------------------------------------------------
    def show_text(self, text: str, global_pos: QPoint) -> None:
        raw = [line for line in text.splitlines() if line.strip()]
        if not raw:
            self.hide()
            return

        f = font(TIP_FONT_SIZE, 500)
        metrics = QFontMetrics(f)
        inner_max = TIP_MAX_WIDTH - TIP_PADDING_X * 2
        lines: list[str] = []
        for line in raw:
            lines.extend(_wrap(metrics, line, inner_max))
        self._lines = lines

        inner_width = max(metrics.horizontalAdvance(line) for line in lines)
        inner_width = min(inner_width, inner_max)
        self._text_width = int(inner_width) + 2
        width = int(inner_width) + TIP_PADDING_X * 2 + 2
        height = int(metrics.height() * len(lines)) + TIP_PADDING_Y * 2 + 2

        self.setFixedSize(width, height)
        self._place(global_pos)
        self.show()
        self.raise_()
        self.update()

    def _place(self, cursor: QPoint) -> None:
        screen = QGuiApplication.screenAt(cursor) or QGuiApplication.primaryScreen()
        if screen is None:
            self.move(cursor.x() + TIP_OFFSET[0], cursor.y() + TIP_OFFSET[1])
            return
        area = screen.availableGeometry()
        x = cursor.x() + TIP_OFFSET[0]
        y = cursor.y() + TIP_OFFSET[1]
        if x + self.width() > area.right():
            x = cursor.x() - self.width() - 10
        if y + self.height() > area.bottom():
            y = cursor.y() - self.height() - 12
        x = max(area.left() + 2, min(x, area.right() - self.width() - 2))
        y = max(area.top() + 2, min(y, area.bottom() - self.height() - 2))
        self.move(x, y)

    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        painter.setPen(QPen(QColor(255, 255, 255, 36), 1))
        painter.setBrush(QColor(28, 30, 41, 248))
        painter.drawRoundedRect(rect, 8, 8)

        f = font(TIP_FONT_SIZE, 500)
        metrics = QFontMetrics(f)
        painter.setFont(f)
        y = TIP_PADDING_Y
        for index, line in enumerate(self._lines):
            color = theme.TEXT_PRIMARY if index == 0 else theme.TEXT_SECONDARY
            painter.setPen(QColor(color))
            available = max(10, self._text_width)
            painter.drawText(
                QRectF(TIP_PADDING_X, y, available, metrics.height()),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                metrics.elidedText(line, Qt.TextElideMode.ElideRight, available),
            )
            y += metrics.height()


HOVER_DELAY = 450


class TipController(QObject):
    """自己跟踪悬停，不依赖 Qt 的 ToolTip 事件。

    Qt 的原生 tooltip 只在特定条件下才发出 ToolTip 事件，且我们拦截后
    如果显示时机没对上就什么都不出现；这里改成控件自己上报 enter/leave。
    """

    def __init__(self, app) -> None:
        global _controller
        super().__init__(app)
        self._tip = TipWindow()
        self._hovered = None

        self._delay = QTimer(self)
        self._delay.setSingleShot(True)
        self._delay.setInterval(HOVER_DELAY)
        self._delay.timeout.connect(self._show_pending)

        self._auto_hide = QTimer(self)
        self._auto_hide.setSingleShot(True)
        self._auto_hide.setInterval(TIP_DURATION)
        self._auto_hide.timeout.connect(self._tip.hide)

        _controller = self
        app.installEventFilter(self)

    # -- 悬停 -----------------------------------------------------------
    def hover_enter(self, widget) -> None:
        if widget is self._hovered:
            return
        self._hovered = widget
        self._delay.start()

    def hover_leave(self, widget) -> None:
        if widget is not self._hovered:
            return
        self._hovered = None
        self._delay.stop()
        self._hide()

    def _show_pending(self) -> None:
        widget = self._hovered
        if widget is None:
            return
        try:
            text = widget.toolTip()
        except RuntimeError:
            return
        if not text:
            return
        self._tip.show_text(text, QCursor.pos())
        self._auto_hide.start()

    def _hide(self) -> None:
        self._auto_hide.stop()
        self._tip.hide()

    # -- 全局：压制原生 tooltip、点击时收起 ------------------------------
    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.ToolTip:
            return True
        if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.Wheel):
            self._hide()
        elif kind == QEvent.Type.Leave and obj is self._hovered:
            self.hover_leave(obj)
        return False


_controller: "TipController | None" = None


def hover_enter(widget) -> None:
    if _controller is not None:
        _controller.hover_enter(widget)


def hover_leave(widget) -> None:
    if _controller is not None:
        _controller.hover_leave(widget)
