"""每日首次唤醒的【近期 DDL 简报】面板。"""

from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from . import theme
from .dialogs import SHADOW, GlassDialog
from .models import DDL, WEEKDAY_CN
from .theme import font
from .icon_render import draw_icon


def _day_label(target: date, today: date) -> str:
    delta = (target - today).days
    if delta == 0:
        return "今天"
    if delta == 1:
        return "明天"
    if delta == 2:
        return "后天"
    if delta == -1:
        return "昨天"
    if delta < 0:
        return f"{-delta} 天前"
    return f"{target.month} 月 {target.day} 日"


class _BriefRow(QWidget):
    def __init__(self, item: DDL, now: datetime, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._item = item
        self._now = now
        self.setFixedHeight(44)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w = self.width()
        urgency = self._item.urgency(self._now)
        color = QColor(theme.RED if urgency in ("today", "overdue") else theme.AMBER if urgency == "week" else theme.BLUE)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawRoundedRect(QRectF(0, 1, w, self.height() - 2), 9, 9)

        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 220))
        painter.drawRoundedRect(QRectF(9, (self.height() - 16) / 2, 3, 16), 1.5, 1.5)

        # 时间
        clock = self._item.due_time.strftime("%H:%M") if self._item.due_time else "--:--"
        painter.setFont(font(12, 600))
        painter.setPen(color)
        painter.drawText(
            QRectF(22, 0, 46, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            clock,
        )

        # 标题
        left = 74.0
        course = self._item.course_name
        painter.setFont(font(11, 400))
        fm_course = QFontMetrics(painter.font())
        course_w = min(fm_course.horizontalAdvance(course) + 8, 110) if course else 0

        title_w = max(40.0, w - left - course_w - 16)
        painter.setFont(font(13, 500))
        fm = QFontMetrics(painter.font())
        painter.setPen(QColor(theme.TEXT_PRIMARY))
        painter.drawText(
            QRectF(left, 0, title_w, self.height()),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm.elidedText(self._item.title, Qt.TextElideMode.ElideRight, int(title_w)),
        )

        if course:
            painter.setFont(font(11, 400))
            painter.setPen(QColor(theme.TEXT_TERTIARY))
            painter.drawText(
                QRectF(w - course_w - 10, 0, course_w, self.height()),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                course,
            )


class _Banner(QWidget):
    """今日 DDL 红色警告横幅。"""

    def __init__(self, count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._count = count
        self.setFixedHeight(64)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        grad = QLinearGradient(rect.topLeft(), rect.topRight())
        grad.setColorAt(0.0, QColor(196, 36, 54, 220))
        grad.setColorAt(1.0, QColor(228, 62, 78, 200))
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)

        icon_size = 19.0
        draw_icon(
            painter,
            "warning",
            QRectF(16, self.height() / 2 - icon_size / 2, icon_size, icon_size),
            QColor(255, 255, 255, 238),
            stroke=2.0,
        )

        painter.setFont(font(14, 700))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            QRectF(48, 12, self.width() - 62, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"今天有 {self._count} 项 DDL 截止",
        )
        painter.setFont(font(11, 400))
        painter.setPen(QColor(255, 226, 230, 220))
        painter.drawText(
            QRectF(48, 32, self.width() - 62, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "请优先处理，完成后在小组件里勾掉",
        )


class BriefingDialog(GlassDialog):
    """屏幕中央的简报面板；含今日 DDL 时必须点「已知晓」才能关闭。"""

    open_requested = Signal()

    def __init__(self, items: list[DDL], parent=None) -> None:
        super().__init__(parent, width=470, title="近期 DDL 简报")
        self._acknowledged = False
        self._now = datetime.now()
        today = self._now.date()
        today_items = [
            i for i in items
            if i.due_time is not None and i.due_time.date() == today and not i.is_completed
        ]
        self._must_ack = bool(today_items)

        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        if self._must_ack:
            # 有今日 DDL 时只能点「已知晓」关闭，不提供叉号
            self._close_btn.hide()

        subtitle = QLabel(self._subtitle_text(len(items), today_items))
        subtitle.setStyleSheet(f"color: {theme.TEXT_TERTIARY};")
        subtitle.setFont(font(11, 400))
        self._root.insertWidget(1, subtitle)

        if today_items:
            self._root.insertWidget(2, _Banner(len(today_items), self))

        self._root.addWidget(self._build_list(items, today))

        footer = QHBoxLayout()
        footer.setSpacing(8)
        open_btn = QPushButton("打开小组件", self)
        open_btn.setObjectName("ghost")
        open_btn.setFont(font(12, 500))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_widget)
        footer.addWidget(open_btn)
        footer.addStretch(1)
        self._ack_btn = QPushButton("已知晓" if self._must_ack else "知道了", self)
        self._ack_btn.setObjectName("primary")
        self._ack_btn.setFont(font(12, 600))
        self._ack_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ack_btn.clicked.connect(self._ack)
        footer.addWidget(self._ack_btn)
        self._root.addLayout(footer)

        self.adjustSize()

    # ------------------------------------------------------------------
    def _subtitle_text(self, total: int, today_items: list[DDL]) -> str:
        now = self._now
        stamp = f"{now.month} 月 {now.day} 日 周{WEEKDAY_CN[now.weekday()]} {now.strftime('%H:%M')}"
        if total == 0:
            return f"{stamp} · 未来 7 天没有待办"
        return f"{stamp} · 未来 7 天共 {total} 项待办"

    def _build_list(self, items: list[DDL], today: date) -> QWidget:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            """
            QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 2px; }
            QScrollBar::handle:vertical { background: rgba(255,255,255,46); border-radius: 3px; min-height: 26px; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
            QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
            """
        )
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 2, 4, 2)
        layout.setSpacing(3)

        if not items:
            empty = QLabel("本周没有要交的作业，去喝杯咖啡吧 ☕")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"color: {theme.TEXT_SECONDARY}; padding: 26px 0;")
            empty.setFont(font(12, 400))
            layout.addWidget(empty)
        else:
            current: date | None = None
            for item in items:
                day = item.due_time.date() if item.due_time else None
                if day != current:
                    current = day
                    header = QLabel(self._group_title(day, today))
                    header.setFont(font(10, 700, 0.8))
                    header.setStyleSheet(f"color: {theme.TEXT_TERTIARY}; padding: 8px 2px 2px 2px;")
                    layout.addWidget(header)
                layout.addWidget(_BriefRow(item, self._now))
        layout.addStretch(1)

        scroll.setWidget(container)
        container.adjustSize()
        layout.activate()
        natural = container.sizeHint().height()
        scroll.setFixedHeight(max(110, min(natural + 6, 372)))
        return scroll

    def _group_title(self, day: date | None, today: date) -> str:
        if day is None:
            return "未定截止"
        label = _day_label(day, today)
        date_part = f"{day.month} 月 {day.day} 日"
        if label == date_part:
            return date_part
        return f"{label} · {date_part}"

    # ------------------------------------------------------------------
    def _ack(self) -> None:
        self._acknowledged = True
        self.accept()

    def _open_widget(self) -> None:
        self._acknowledged = True
        self.open_requested.emit()
        self.accept()

    def reject(self) -> None:
        if self._must_ack and not self._acknowledged:
            return
        super().reject()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self._must_ack and not self._acknowledged:
            return
        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._must_ack and not self._acknowledged:
            event.ignore()
            return
        super().closeEvent(event)
