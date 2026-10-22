"""主窗口：无边框半透明圆角小挂件。"""

from __future__ import annotations

import ctypes
import os
import time
from datetime import datetime

try:  # ctypes.wintypes 在非 Windows 上不可用
    from ctypes import wintypes

    _HAS_WINTYPES = True
except Exception:  # noqa: BLE001
    wintypes = None
    _HAS_WINTYPES = False

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import theme, sysutil
from . import tips as tips_ref
from .fx import FxOverlay, solid_card
from .icon_render import icon_px
from .dialogs import EditorDialog, SettingsDialog
from .models import DDL, GROUP_COLOR, GROUP_LABEL, group_items
from .theme import font, rgba
from .widgets import (
    ROW_HEIGHT,
    DDLRow,
    EmptyState,
    GroupHeader,
    IconButton,
    LogoMark,
    pulse_wave,
)

SHADOW = 22
RADIUS = theme.RADIUS
WIDTH = 452
HEADER_H = 58
FOOTER_H = 42
SNAP_DIST = 26        # 距离屏幕边缘多少像素内松手即吸附
EDGE_HOT_ZONE = 5     # 完全收起后，屏幕边缘多少像素内算"想展开"
COLLAPSE_DELAY = 300  # 鼠标离开后多久收纳
MIN_VISIBLE_X = 140   # 至少保留这么多像素在屏幕内，避免抓不到
MIN_VISIBLE_Y = 100

FLIP_DURATION = 360   # 列表重排动画时长（ms）

MAX_LIST_H = 560
MIN_LIST_H = 96
GROUP_HEADER_H = 26
LIST_MARGIN_H = 12   # 上下内边距
LIST_SPACING = 2
EMPTY_STATE_H = 150


class Dot(QWidget):
    def __init__(self, color: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(7, 7)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._color)
        painter.drawEllipse(QRectF(0, 0, 7, 7))


def _done_order(item) -> tuple:
    """已完成区排序：刚完成的排最前面，其余按截止时间。"""
    if item.completed_at is not None:
        return (0, -item.completed_at.timestamp(), 0.0, item.title)
    due = item.due_time.timestamp() if item.due_time else float("inf")
    return (1, 0.0, due, item.title)


class _MSG(ctypes.Structure if _HAS_WINTYPES else object):
    if _HAS_WINTYPES:
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt_x", wintypes.LONG),
            ("pt_y", wintypes.LONG),
        ]


class ResizeGrip(QWidget):
    """窗口底部的高度拖拽把手。"""

    drag_started = Signal()
    dragged = Signal(int)
    drag_finished = Signal()
    reset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("上下拖动调整高度 · 双击恢复自适应")
        self._last_y: float | None = None
        self._active = False
        self._hover = False

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = 34.0, 3.0
        x = (self.width() - width) / 2
        y = self.height() - height - 4
        alpha = 120 if (self._active or self._hover) else 52
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, alpha))
        painter.drawRoundedRect(QRectF(x, y, width, height), 1.5, 1.5)

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        tips_ref.hover_enter(self)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        tips_ref.hover_leave(self)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_y = event.globalPosition().y()
            self._active = True
            self.drag_started.emit()
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if not self._active or self._last_y is None:
            return
        current = event.globalPosition().y()
        delta = current - self._last_y
        self._last_y = current
        if abs(delta) >= 1:
            self.dragged.emit(int(delta))

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._active:
            self._active = False
            self._last_y = None
            self.drag_finished.emit()
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.reset_requested.emit()


class FadeOverlay(QWidget):
    """列表底部渐隐，让滚动截断看起来是有意为之。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, -30, self.width(), self.height() + 30), RADIUS, RADIUS)
        painter.setClipPath(path)
        grad = QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0.0, QColor(*theme.CARD_BOTTOM, 0))
        grad.setColorAt(0.6, QColor(*theme.CARD_BOTTOM, 96))
        grad.setColorAt(1.0, QColor(*theme.CARD_BOTTOM, 178))
        painter.fillRect(self.rect(), grad)


class MainWindow(QWidget):
    sync_requested = Signal()
    reset_requested = Signal()
    notify = Signal(str, str)
    quit_requested = Signal()
    hide_requested = Signal()
    settings_changed = Signal()

    def __init__(self, db, settings) -> None:
        super().__init__()
        self.db = db
        self.settings = settings
        self._rows: list[DDLRow] = []
        self._header_widgets: list[GroupHeader] = []
        self._layout_anims: list[QPropertyAnimation] = []
        self._flip_token = 0
        self._header_count = 0
        self._empty_state = False
        self._bg: QPixmap | None = None
        self._bg_key: tuple | None = None
        self._drag_origin: QPoint | None = None
        self._reveal_grace_until = 0.0
        self._quitting = False
        self._syncing = False
        self._spin = 0.0
        self._elapsed = 0.0
        self._last_second = -1
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(400)
        self._save_timer.timeout.connect(self._on_move_settled)

        # 贴边收纳
        self._edge: str = ""
        self._dock_geo: QRect | None = None
        self._collapsed = False
        self._base_x = 0
        self._animating = False
        self._edge_anim = QPropertyAnimation(self, b"pos", self)
        self._edge_anim.setDuration(190)
        self._edge_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._edge_anim.finished.connect(self._on_edge_anim_done)
        self._collapse_timer = QTimer(self)
        self._collapse_timer.setSingleShot(True)
        self._collapse_timer.setInterval(COLLAPSE_DELAY)
        self._collapse_timer.timeout.connect(self._collapse_now)

        desktop = bool(settings.get("desktop_layer")) and sysutil.supports_desktop_layer()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | (
                Qt.WindowType.WindowStaysOnTopHint
                if settings.get("always_on_top") and not desktop
                else Qt.WindowType(0)
            )
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if sysutil.IS_MAC:
            # macOS 上 Qt.Tool 窗口在 App 失焦时会自动隐藏，桌面挂件必须常驻
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFixedWidth(WIDTH)
        self.setWindowTitle("DDL · 作业截止日")

        self._build_ui()
        self._fx = FxOverlay()
        self._fade = FadeOverlay(self)
        self._fade.hide()
        self._manual_view: int | None = None
        self._grip = ResizeGrip(self)
        self._grip.drag_started.connect(self._on_grip_start)
        self._grip.dragged.connect(self._on_grip_drag)
        self._grip.drag_finished.connect(self._on_grip_end)
        self._grip.reset_requested.connect(self.reset_height)
        self._last_heal = 0.0
        self._scroll.verticalScrollBar().valueChanged.connect(lambda _v: self._update_fade())
        self._scroll.verticalScrollBar().rangeChanged.connect(lambda _a, _b: self._update_fade())
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(150)
        self._tick_timer.timeout.connect(self._on_tick)
        self._tick_timer.start()

        self._bottom_timer = QTimer(self)
        self._bottom_timer.setInterval(900)
        self._bottom_timer.timeout.connect(self._enforce_bottom)

        self.reload(reset_geometry=True)
        self._restore_position()
        self._apply_lock(bool(settings.get("locked")))

    # ==================================================================
    # 构建
    # ==================================================================
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SHADOW, SHADOW, SHADOW, SHADOW)
        root.setSpacing(0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_scroll(), 1)
        root.addWidget(self._build_footer())

    def _build_header(self) -> QWidget:
        header = QWidget(self)
        header.setFixedHeight(HEADER_H)
        header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(header)
        lay.setContentsMargins(16, 10, 12, 4)
        lay.setSpacing(10)

        lay.addWidget(LogoMark(header), 0, Qt.AlignmentFlag.AlignVCenter)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(1)
        self._title = QLabel("DDL", header)
        self._title.setFont(font(16, 700, 0.2))
        self._title.setStyleSheet(f"color: {theme.TEXT_PRIMARY};")
        self._subtitle = QLabel("作业截止日", header)
        self._subtitle.setFont(font(11, 400))
        self._subtitle.setStyleSheet(f"color: {theme.TEXT_TERTIARY};")
        texts.addWidget(self._title)
        texts.addWidget(self._subtitle)
        lay.addLayout(texts)
        lay.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(3)

        self._btn_sync = IconButton("refresh", 27, icon_px(14), "立即同步教学网")
        self._btn_sync.clicked.connect(self.sync_requested.emit)
        self._btn_reset = IconButton(
            "undo", 27, icon_px(14), "把教学网上未提交的作业全部恢复为待办（会解除手动勾选）"
        )
        self._btn_reset.clicked.connect(self.reset_requested.emit)
        self._btn_add = IconButton("add", 27, icon_px(15), "添加 DDL")
        self._btn_add.clicked.connect(self.add_item)
        self._btn_lock = IconButton("unlock", 27, icon_px(13), "锁定位置")
        self._btn_lock.setCheckable(True)
        self._btn_lock.clicked.connect(self._toggle_lock)
        self._btn_settings = IconButton("settings", 27, icon_px(13), "设置")
        self._btn_settings.clicked.connect(self.open_settings)
        self._btn_close = IconButton("close", 27, icon_px(11), "隐藏到托盘")
        self._btn_close.clicked.connect(self._on_close_clicked)

        for btn in (
            self._btn_sync,
            self._btn_reset,
            self._btn_add,
            self._btn_lock,
            self._btn_settings,
            self._btn_close,
        ):
            buttons.addWidget(btn)
        lay.addLayout(buttons)
        return header

    def _build_scroll(self) -> QWidget:
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet(
            """
            QScrollArea { background: transparent; border: none; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 2px 0 2px 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,46); border-radius: 3px; min-height: 28px;
            }
            QScrollBar::handle:vertical:hover { background: rgba(255,255,255,86); }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px; background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            """
        )
        self._list = QWidget()
        self._list.setStyleSheet("background: transparent;")
        self._list_layout = QVBoxLayout(self._list)
        self._list_layout.setContentsMargins(12, 2, 12, 10)
        self._list_layout.setSpacing(2)
        self._list_layout.addStretch(1)
        self._scroll.setWidget(self._list)
        return self._scroll

    def _build_footer(self) -> QWidget:
        footer = QWidget(self)
        footer.setFixedHeight(FOOTER_H)
        footer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(footer)
        lay.setContentsMargins(18, 0, 16, 8)
        lay.setSpacing(7)

        self._dot = Dot(theme.GREEN, footer)
        lay.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignVCenter)
        self._status = QLabel("尚未同步", footer)
        self._status.setFont(font(11, 400))
        self._status.setStyleSheet(f"color: {theme.TEXT_TERTIARY};")
        lay.addWidget(self._status, 1)
        self._counts = QLabel("", footer)
        self._counts.setFont(font(11, 400))
        self._counts.setStyleSheet(f"color: {theme.TEXT_TERTIARY};")
        lay.addWidget(self._counts, 0, Qt.AlignmentFlag.AlignRight)
        return footer

    # ==================================================================
    # 数据渲染
    # ==================================================================
    def reload(self, reset_geometry: bool = False) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                # 立刻隐藏，否则 deleteLater 生效前旧行会和新行叠在一起
                widget.hide()
                widget.deleteLater()
        self._rows.clear()
        self._header_widgets.clear()
        self._header_count = 0
        self._empty_state = False

        now = datetime.now()
        show_completed = bool(self.settings.get("show_completed"))
        items = self.db.visible_items(show_completed=show_completed)
        pending = [i for i in items if not i.is_completed]
        completed = [i for i in items if i.is_completed]

        groups = group_items(pending, now)
        if not groups and not completed:
            empty = EmptyState("未来没有待办 DDL", "点右上角 ＋ 添加，或 ⟳ 同步教学网")
            self._list_layout.addWidget(empty)
            empty.show()
            self._empty_state = True
        else:
            for key, rows in groups:
                header = GroupHeader(key, len(rows))
                self._header_widgets.append(header)
                self._list_layout.addWidget(header)
                header.show()
                self._header_count += 1
                for item in rows:
                    self._add_row(item, now)
            if completed:
                header = GroupHeader("done", len(completed))
                self._header_widgets.append(header)
                self._list_layout.addWidget(header)
                header.show()
                self._header_count += 1
                for item in sorted(completed, key=_done_order):
                    self._add_row(item, now)

        self._list_layout.addStretch(1)
        self._update_header_counts()
        self._update_status()
        self._adjust_height()
        QTimer.singleShot(0, self._update_fade)

    def _add_row(self, item: DDL, now: datetime) -> None:
        row = DDLRow(item, now)
        row.toggle_requested.connect(self._on_toggle)
        row.edit_requested.connect(self._on_edit)
        self._rows.append(row)
        self._list_layout.addWidget(row)
        row.show()

    # -- 高度 ----------------------------------------------------------
    def _content_height(self) -> int:
        """按行数显式算出列表需要的像素高度，不依赖 QLayout.sizeHint()。"""
        if self._empty_state or (self._header_count + len(self._rows)) == 0:
            return LIST_MARGIN_H + EMPTY_STATE_H
        count = self._header_count + len(self._rows)
        gaps = max(0, count - 1)
        return (
            LIST_MARGIN_H
            + self._header_count * GROUP_HEADER_H
            + len(self._rows) * ROW_HEIGHT
            + gaps * LIST_SPACING
        )

    def _screen_available_height(self) -> int:
        screen = self.screen() or QApplication.primaryScreen()
        return screen.availableGeometry().height() if screen is not None else 900

    def _max_view_height(self) -> int:
        """列表最大高度：既不超过屏幕，也不让窗口下边缘跑出屏幕。"""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return MAX_LIST_H
        area = screen.availableGeometry()
        chrome = SHADOW * 2 + HEADER_H + FOOTER_H
        top = max(area.top(), self.y())
        room_below = area.bottom() - top - chrome - 8
        room_full = area.height() - chrome - 72
        return max(MIN_LIST_H, min(room_below, room_full))

    def _auto_view_height(self) -> int:
        wanted = self._content_height()
        cap = min(MAX_LIST_H, self._max_view_height())
        return max(MIN_LIST_H, min(wanted, cap))

    def _target_view_height(self) -> int:
        manual = self.settings.get("list_height")
        if manual:
            try:
                return max(MIN_LIST_H, min(int(manual), self._max_view_height()))
            except (TypeError, ValueError):
                pass
        return self._auto_view_height()

    def _apply_height(self, view_h: int | None = None) -> None:
        height = int(view_h) if view_h is not None else self._target_view_height()
        height = max(MIN_LIST_H, min(height, self._max_view_height()))
        self._scroll.setFixedHeight(height)
        self.setFixedHeight(SHADOW * 2 + HEADER_H + height + FOOTER_H)
        self._invalidate_bg()
        self._position_grip()
        QTimer.singleShot(0, self._update_fade)

    def _adjust_height(self) -> None:
        self._apply_height()

    def _position_grip(self) -> None:
        if not hasattr(self, "_grip"):
            return
        width = 92
        self._grip.setGeometry(
            (self.width() - width) // 2, self.height() - SHADOW - 12, width, 12
        )
        self._grip.raise_()

    def _on_grip_start(self) -> None:
        self._manual_view = self._scroll.height()

    def _on_grip_drag(self, dy: int) -> None:
        if self._manual_view is None:
            self._manual_view = self._scroll.height()
        self._manual_view = max(
            MIN_LIST_H, min(self._manual_view + dy, self._max_view_height())
        )
        self._apply_height(self._manual_view)

    def _on_grip_end(self) -> None:
        if self._manual_view:
            self.settings.set("list_height", int(self._manual_view))
        self._manual_view = None

    def reset_height(self) -> None:
        self.settings.set("list_height", None)
        self.reload()

    def _update_fade(self) -> None:
        bar = self._scroll.verticalScrollBar()
        if bar.maximum() <= 4 or bar.value() >= bar.maximum() - 4:
            self._fade.hide()
            return
        geo = self._scroll.geometry()
        height = 26
        self._fade.setGeometry(geo.left() + 2, geo.bottom() - height + 1, geo.width() - 4, height)
        self._fade.show()
        self._fade.raise_()

    def _update_header_counts(self) -> None:
        counts = self.db.counts()
        pending = sum(v for k, v in counts.items() if k.endswith(":pending"))
        total_synced = sum(v for k, v in counts.items() if k.startswith("pku3b:"))
        manual = sum(v for k, v in counts.items() if k.startswith("manual:"))
        if pending:
            self._subtitle.setText(f"作业截止日 · {pending} 项待办")
        else:
            self._subtitle.setText("作业截止日 · 全部清空")
        parts = []
        if total_synced:
            parts.append(f"教学网 {total_synced}")
        if manual:
            parts.append(f"手动 {manual}")
        self._counts.setText(" · ".join(parts))

    def _update_status(self) -> None:
        last = self.db.get_meta("last_sync_at")
        ok = self.db.get_meta("last_sync_ok", "1") != "0"
        err = self.db.get_meta("last_sync_error")
        if self._syncing:
            self._dot.set_color(theme.AMBER)
            self._status.setText("正在同步教学网…")
            return
        if not last:
            self._dot.set_color(theme.SLATE)
            self._status.setText("尚未同步 · 点 ⟳ 获取教学网作业")
            return
        when = self._format_when(last)
        if ok:
            self._dot.set_color(theme.GREEN)
            self._status.setText(f"已同步 · {when}")
        else:
            self._dot.set_color(theme.RED)
            short = (err or "").strip()
            if len(short) > 42:
                short = short[:41] + "…"
            self._status.setText(f"同步失败 · {short or when}")
            self._status.setToolTip(err or "")

    @staticmethod
    def _format_when(iso: str) -> str:
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            return iso
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        return f"{dt.month}/{dt.day} {dt.strftime('%H:%M')}"

    # ==================================================================
    # 交互
    # ==================================================================
    def _on_toggle(self, item_id: str) -> None:
        row = next((r for r in self._rows if r.item().id == item_id), None)
        pixmap = None
        click_point = None
        fly_from = None
        if row is not None:
            click_point = row.mapToGlobal(QPoint(26, row.height() // 2))
            fly_from = row.mapToGlobal(row.rect().center())
            pixmap = solid_card(row.grab())

        before = self._snapshot_layout()
        completed = self.db.toggle_status(item_id) == "completed"
        self.reload()

        viewport = self._scroll.viewport()
        fallback = viewport.mapToGlobal(QPoint(viewport.width() // 2, viewport.height() - 20))
        landed_row = next((r for r in self._rows if r.item().id == item_id), None)
        skip: set = set()
        if completed and landed_row is not None:
            # 这个位置先显示成虚线空槽，等卡片飞进来再复原
            landed_row.set_placeholder(True)
            skip.add(("row", item_id))

        self._animate_layout(before, skip)

        target = fallback
        if completed and landed_row is not None:
            target = self._row_global_center(landed_row) or fallback

        if not completed:
            return

        self._toast("已完成", self._row_title(item_id))
        if click_point is not None:
            self._fx.sparkle(click_point, 12)
        if fly_from is None:
            return
        self._fx.fly(
            pixmap,
            fly_from,
            target,
            0.58,
            on_done=lambda: self._land(item_id, target),
        )

    def _land(self, item_id: str, target: QPoint) -> None:
        row = next((r for r in self._rows if r.item().id == item_id), None)
        if row is not None:
            row.set_placeholder(False)
            row.show()
        self._fx.burst(target, 100, 1.15)

    # -- 列表重排动画（FLIP） ---------------------------------------------
    def _snapshot_layout(self) -> dict[tuple[str, str], QPoint]:
        snapshot: dict[tuple[str, str], QPoint] = {}
        for header in self._header_widgets:
            snapshot[("hdr", header.key())] = QPoint(header.x(), header.y())
        for item_row in self._rows:
            snapshot[("row", item_row.item().id)] = QPoint(item_row.x(), item_row.y())
        return snapshot

    def _animate_layout(self, before: dict, skip: set) -> None:
        # 先让新布局真正落位，否则读到的是过期坐标（动画终点会算错）
        self._list_layout.activate()
        widgets: dict[tuple[str, str], QWidget] = {}
        after: dict[tuple[str, str], QPoint] = {}
        for header in self._header_widgets:
            key = ("hdr", header.key())
            widgets[key] = header
            after[key] = QPoint(header.x(), header.y())
        for item_row in self._rows:
            key = ("row", item_row.item().id)
            widgets[key] = item_row
            after[key] = QPoint(item_row.x(), item_row.y())

        if os.environ.get("DDL_DEBUG_FLIP"):
            print("[flip] before:", {k[1][-4:]: (v.x(), v.y()) for k, v in before.items()})
            print("[flip] after :", {k[1][-4:]: (v.x(), v.y()) for k, v in after.items()})
            print("[flip] list.h =", self._list.height(), " scroll.h =", self._scroll.height(),
                  " hint =", self._list.sizeHint().height())
            print("[flip] list.visible =", self._list.isVisible(),
                  " rows =", len(self._rows),
                  " count =", self._list_layout.count(),
                  " enabled =", self._list_layout.isEnabled(),
                  " row0.visible =", self._rows[0].isVisible() if self._rows else None,
                  " row0.geo =", self._rows[0].geometry().getRect() if self._rows else None)

        self._flip_token += 1
        token = self._flip_token
        self._list_layout.setEnabled(False)
        self._layout_anims = []
        for key, widget in widgets.items():
            if key in skip:
                continue
            start = before.get(key)
            end = after[key]
            if start is None or start == end:
                continue
            widget.move(start)
            anim = QPropertyAnimation(widget, b"pos", widget)
            anim.setDuration(FLIP_DURATION)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.start()
            self._layout_anims.append(anim)
        QTimer.singleShot(FLIP_DURATION + 40, lambda: self._finish_flip(token))

    def _finish_flip(self, token: int) -> None:
        if token != self._flip_token:
            return
        self._list_layout.setEnabled(True)
        self._list_layout.activate()
        QTimer.singleShot(0, self._update_fade)

    def _row_global_center(self, row: QWidget) -> QPoint | None:
        viewport = self._scroll.viewport()
        center = row.mapTo(viewport, row.rect().center())
        if viewport.rect().contains(center):
            return viewport.mapToGlobal(center)
        return None

    # -- 完成特效 --------------------------------------------------------
    def _celebration_target(self) -> QPoint:
        """落点：已完成的可见行 / 已完成分组 / 列表底部。"""
        viewport = self._scroll.viewport()
        bounds = viewport.rect()
        candidates = []
        for index in range(self._list_layout.count()):
            widget = self._list_layout.itemAt(index).widget()
            if isinstance(widget, GroupHeader) and widget.key() == "done":
                candidates.append(widget)
            elif isinstance(widget, DDLRow) and widget.item().is_completed:
                candidates.insert(0, widget)
        for widget in candidates:
            center = widget.mapTo(viewport, widget.rect().center())
            if bounds.contains(center):
                return viewport.mapToGlobal(center)
        return viewport.mapToGlobal(QPoint(bounds.width() // 2, bounds.height() - 18))

    def _celebrate(self, pixmap, source: QPoint | None) -> None:
        target = self._celebration_target()
        start = source or target
        self._fx.sparkle(start, 14)
        self._fx.fly(
            pixmap,
            start,
            target,
            0.62,
            on_done=lambda: self._fx.burst(target, 110, 1.2),
        )

    def celebrate_synced(self, item_ids: list[str]) -> None:
        """同步发现作业已完成时的庆祝。"""
        if not item_ids or not self.isVisible():
            return
        source = self._btn_sync.mapToGlobal(self._btn_sync.rect().center())
        for index in range(min(len(item_ids), 4)):
            QTimer.singleShot(index * 150, lambda: self._celebrate(None, source))

    def _row_title(self, item_id: str) -> str:
        item = self.db.get(item_id)
        return item.title if item else ""

    def _on_edit(self, item_id: str) -> None:
        item = self.db.get(item_id)
        if item is None:
            return
        dialog = EditorDialog(item, self)
        if not dialog.exec():
            return
        data = dialog.result_data()
        if not data:
            return
        if data.get("__delete__"):
            self.db.delete(item.id)
            self.reload()
            return
        # 教学网条目也允许本地改标题/课程：只写本地库，且标记 user_edited，
        # 后续同步不会把标题改回去（截止时间仍跟随教学网）。
        self.db.update_manual(item.id, data["title"], data["course"], data["due"])
        self.reload()

    def add_item(self) -> None:
        dialog = EditorDialog(None, self)
        if dialog.exec():
            data = dialog.result_data()
            if not data:
                return
            self.db.add_manual(data["title"], data["course"], data["due"])
            self.reload()

    def _toggle_lock(self) -> None:
        locked = bool(self._btn_lock.isChecked())
        self._apply_lock(locked)
        self.settings.set("locked", locked)

    def _apply_lock(self, locked: bool) -> None:
        self._btn_lock.setChecked(locked)
        self._btn_lock.set_glyph("lock" if locked else "unlock")
        self._btn_lock.setToolTip("解锁位置" if locked else "锁定位置")
        self._btn_lock.set_checked_tint(locked)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings.update(dialog.result_data())
            if not bool(self.settings.get("edge_dock_enabled", True)):
                self._clear_edge()
            self.apply_window_mode()
            self.reload()
            self.settings_changed.emit()

    def _on_close_clicked(self) -> None:
        self.hide()
        self.hide_requested.emit()

    def _toast(self, title: str, body: str) -> None:
        self.notify.emit(title, body)

    # ==================================================================
    # 窗口层级 / 位置
    # ==================================================================
    def apply_window_mode(self) -> None:
        desktop = bool(self.settings.get("desktop_layer")) and sysutil.supports_desktop_layer()
        top = bool(self.settings.get("always_on_top")) and not desktop
        visible = self.isVisible()
        geo = self.geometry()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        if sysutil.IS_MAC:
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setGeometry(geo)
        if visible:
            self.show()
        if self._edge:
            self.move(self._dock_x(self._edge, self._collapsed), self.y())
        if desktop:
            sysutil.set_topmost(int(self.winId()), False)
            self._bottom_timer.start()
            self._enforce_bottom()
        else:
            self._bottom_timer.stop()

    def _enforce_bottom(self) -> None:
        if not self.settings.get("desktop_layer") or not self.isVisible():
            return
        if not sysutil.supports_desktop_layer():
            return
        if self.isActiveWindow():
            return
        if self.geometry().contains(QCursor.pos()):
            # 鼠标正停在窗口上时不要往下压，否则会用着用着沉到别的窗口后面
            return
        sysutil.send_to_bottom(int(self.winId()))

    def _restore_position(self) -> None:
        area = self._available_rect()
        pos = self.settings.get("window_pos")
        saved = None
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            saved = (int(pos[0]), int(pos[1]))

        y = saved[1] if saved else area.top() + 72
        if y < area.top() - 50 or y > area.bottom() - MIN_VISIBLE_Y:
            y = area.top() + 72

        edge = str(self.settings.get("edge_dock") or "")
        if edge in ("left", "right") and bool(self.settings.get("edge_dock_enabled", True)):
            self._edge = edge
            self._dock_geo = area
            self._base_x = self._dock_x(edge, False)
            self._collapsed = True
            self.move(self._dock_x(edge, True), y)
            return

        x = saved[0] if saved else area.right() - self.width() - 28
        if x < area.left() - self.width() + MIN_VISIBLE_X or x > area.right() + 1 - MIN_VISIBLE_X:
            x = area.right() - self.width() - 28
            if x < area.left():
                x = area.left() + 12
        self.move(x, y)

    # -- 贴边收纳 / 位置保护 ---------------------------------------------
    def _available_rect(self) -> QRect:
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return QRect(0, 0, 1920, 1080)
        return screen.availableGeometry()

    def _dock_rect(self) -> QRect:
        """吸附时记住的那块屏幕，避免整块移出屏幕后 self.screen() 认错屏。"""
        return self._dock_geo if self._dock_geo is not None else self._available_rect()

    def _dock_x(self, side: str, collapsed: bool) -> int:
        area = self._dock_rect()
        if side == "left":
            # 收起时整块移出屏幕，只剩屏幕边缘一条看不见的感应带
            return area.left() - self.width() if collapsed else area.left() - SHADOW
        return area.right() + 1 if collapsed else area.right() + 1 - self.width() + SHADOW

    def _move_to_x(self, x: int, animate: bool) -> None:
        target = QPoint(int(x), int(self.y()))
        self._edge_anim.stop()
        if not animate:
            self._animating = False
            self.move(target)
            return
        self._edge_anim.setStartValue(self.pos())
        self._edge_anim.setEndValue(target)
        self._animating = True
        self._edge_anim.start()

    def _on_edge_anim_done(self) -> None:
        self._animating = False
        if self._edge and not self._collapsed:
            # 从屏幕外滑回来之后，确保在最前面并且重绘一次
            self.raise_()
            self.update()

    def _set_edge(self, side: str) -> None:
        if self._edge == side:
            return
        self._edge = side
        self._dock_geo = self._available_rect()
        self._collapsed = False
        self._collapse_timer.stop()
        self._base_x = self._dock_x(side, False)
        self.settings.set("edge_dock", side, save=False)
        if self.x() != self._base_x:
            self.move(self._base_x, self.y())

    def _clear_edge(self) -> None:
        if not self._edge:
            return
        self._edge = ""
        self._dock_geo = None
        self._collapsed = False
        self._collapse_timer.stop()
        self.settings.set("edge_dock", "", save=False)

    def _evaluate_edge_dock(self) -> bool:
        if not bool(self.settings.get("edge_dock_enabled", True)):
            self._clear_edge()
            return False
        area = self._available_rect()
        if self.x() <= area.left() + SNAP_DIST:
            self._set_edge("left")
            return True
        if self.x() + self.width() >= area.right() + 1 - SNAP_DIST:
            self._set_edge("right")
            return True
        self._clear_edge()
        return False

    def _collapse_now(self) -> None:
        if not self._edge or self._collapsed or self._animating:
            return
        if QApplication.activeModalWidget() is not None:
            return
        if QApplication.activePopupWidget() is not None:
            return
        if self.geometry().contains(QCursor.pos()):
            return
        self._collapsed = True
        self._move_to_x(self._dock_x(self._edge, True), True)

    def _restore_window(self) -> None:
        """把被系统最小化 / 隐藏的窗口恢复出来。

        Win+D、触控板"回到桌面"会把窗口最小化；最小化的窗口 isVisible() 仍是 True，
        如果不主动恢复，滑出动画照样在跑，但屏幕上什么都看不到。
        """
        state = self.windowState()
        if state & Qt.WindowState.WindowMinimized:
            self.setWindowState(state & ~Qt.WindowState.WindowMinimized)
        if not self.isVisible():
            self.show()

    def is_effectively_visible(self) -> bool:
        return self.isVisible() and not self.isMinimized() and not self._collapsed

    def bring_to_front(self) -> None:
        """托盘 / 二次启动 唤起窗口。"""
        self._reveal_grace_until = time.monotonic() + 2.5
        self._restore_window()
        self.reveal_docked()
        self.raise_()
        self.activateWindow()
        self.update()

    def _reveal_now(self) -> None:
        if not self._edge or not self._collapsed:
            return
        self._restore_window()
        self._collapsed = False
        self._collapse_timer.stop()
        self._move_to_x(self._dock_x(self._edge, False), True)
        self.raise_()

    def reveal_docked(self) -> None:
        """外部（托盘/双击）唤起时若处于收纳状态则展开。"""
        if self._edge and self._collapsed:
            self._reveal_now()

    def _in_hot_zone(self, pos: QPoint, area: QRect) -> bool:
        """收起后，鼠标贴到屏幕边缘的那条窄带里就算"想展开"。"""
        if self._edge == "left":
            near = pos.x() <= area.left() + EDGE_HOT_ZONE
        else:
            near = pos.x() >= area.right() - EDGE_HOT_ZONE
        if not near:
            return False
        top = self.y()
        return top - 20 <= pos.y() <= top + self.height() + 20

    def _update_edge_state(self) -> None:
        if not self._edge or not self.isVisible():
            return
        if not bool(self.settings.get("edge_dock_enabled", True)):
            self._clear_edge()
            return
        cursor = QCursor.pos()
        area = self._dock_rect()
        if self._collapsed:
            if self._in_hot_zone(cursor, area) and not self._animating:
                self._collapse_timer.stop()
                self._reveal_now()
            return

        if self.isMinimized():
            # 被 Win+D / 回桌面 最小化了：鼠标还在窗口范围就先恢复，
            # 否则当它已经收起，下次贴边自然会把状态纠正回来
            if self.geometry().contains(cursor):
                self._restore_window()
            else:
                self._collapsed = True
                self._move_to_x(self._dock_x(self._edge, True), False)
            return

        if self.geometry().contains(cursor) or time.monotonic() < self._reveal_grace_until:
            self._collapse_timer.stop()
        elif not self._animating and not self._collapse_timer.isActive():
            self._collapse_timer.start()

    def _clamp_to_screen(self) -> None:
        """把跑出屏幕的窗口拉回来，保证还能抓得到。"""
        area = self._available_rect()
        width = self.width()
        min_x = area.left() - width + MIN_VISIBLE_X
        max_x = area.right() + 1 - MIN_VISIBLE_X
        min_y = area.top() - 6
        max_y = area.bottom() + 1 - MIN_VISIBLE_Y
        x = min(max(self.x(), min_x), max_x)
        y = min(max(self.y(), min_y), max_y)
        if x != self.x() or y != self.y():
            self.move(x, y)

    def _on_move_settled(self) -> None:
        if self._animating or self._collapsed:
            return
        if not self._evaluate_edge_dock():
            self._clamp_to_screen()
        self._persist_position()

    def _persist_position(self) -> None:
        x = self._base_x if self._edge else self.x()
        self.settings.update(
            {"window_pos": [int(x), int(self.y())], "edge_dock": self._edge}
        )

    # ==================================================================
    # 事件
    # ==================================================================
    def paintEvent(self, event) -> None:  # noqa: N802
        key = (self.size(), self.devicePixelRatioF())
        if self._bg is None or self._bg_key != key:
            self._render_bg()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._bg is not None:
            painter.drawPixmap(0, 0, self._bg)

    def _invalidate_bg(self) -> None:
        self._bg = None
        self._bg_key = None
        self.update()

    def _render_bg(self) -> None:
        dpr = self.devicePixelRatioF()
        pixmap = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(SHADOW, SHADOW, self.width() - SHADOW * 2, self.height() - SHADOW * 2)

        # 柔和外阴影
        steps = 16
        for i in range(steps, 0, -1):
            frac = i / steps
            alpha = int(34 * (1.0 - frac) ** 2.2) + 1
            pad = i * 0.75
            rect = card.adjusted(-pad, -pad + 4, pad, pad + 4)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.drawRoundedRect(rect, RADIUS + pad, RADIUS + pad)

        path = QPainterPath()
        path.addRoundedRect(card, RADIUS, RADIUS)

        opacity = float(self.settings.get("opacity", 0.96))
        alpha = int(255 * max(0.35, min(1.0, opacity)))
        grad = QLinearGradient(card.topLeft(), card.bottomLeft())
        grad.setColorAt(0.0, QColor(*theme.CARD_TOP, alpha))
        grad.setColorAt(1.0, QColor(*theme.CARD_BOTTOM, alpha))
        painter.fillPath(path, grad)

        # 左上角冷光
        painter.save()
        painter.setClipPath(path)
        glow = QRadialGradient(card.left() + 70, card.top() - 30, 260)
        glow.setColorAt(0.0, QColor(124, 140, 255, 40))
        glow.setColorAt(0.55, QColor(124, 140, 255, 12))
        glow.setColorAt(1.0, QColor(124, 140, 255, 0))
        painter.fillRect(card, glow)
        painter.restore()

        # 顶部高光 + 描边
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 16), 1))
        painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
        painter.setPen(QPen(theme.BORDER, 1))
        painter.drawRoundedRect(card, RADIUS, RADIUS)

        highlight = QLinearGradient(card.left(), card.top(), card.right(), card.top())
        highlight.setColorAt(0.0, QColor(255, 255, 255, 0))
        highlight.setColorAt(0.35, QColor(255, 255, 255, 40))
        highlight.setColorAt(0.65, QColor(255, 255, 255, 26))
        highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
        painter.setPen(QPen(highlight, 1))
        painter.drawLine(
            int(card.left() + RADIUS),
            int(card.top() + 0.6),
            int(card.right() - RADIUS),
            int(card.top() + 0.6),
        )

        painter.end()
        self._bg = pixmap
        self._bg_key = (self.size(), dpr)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._invalidate_bg()
        self._position_grip()
        QTimer.singleShot(0, self._update_fade)
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # 首次显示后再算一次，避免某些环境下初始化阶段尺寸未就绪
        QTimer.singleShot(0, self._apply_height)

    def moveEvent(self, event) -> None:  # noqa: N802
        if (
            self.isVisible()
            and not self._animating
            and not self._collapsed
            and self._drag_origin is None
            and not self._save_timer.isActive()
        ):
            self._save_timer.start()
        super().moveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < SHADOW + HEADER_H and not self.settings.get("locked"):
                if sysutil.IS_WINDOWS:
                    handle = self.windowHandle()
                    if handle is not None and handle.startSystemMove():
                        return
                self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_origin is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            self._drag_origin = None
            self._on_move_settled()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        self._show_menu(event.globalPos())

    def _show_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(theme.MENU_QSS)

        act_sync = menu.addAction("立即同步教学网")
        act_reset = menu.addAction("把未提交的恢复为待办")
        act_add = menu.addAction("添加 DDL…")
        menu.addSeparator()
        act_lock = menu.addAction("锁定位置")
        act_lock.setCheckable(True)
        act_lock.setChecked(bool(self.settings.get("locked")))
        desktop_active = bool(self.settings.get("desktop_layer")) and sysutil.supports_desktop_layer()
        act_top = menu.addAction("置顶显示")
        act_top.setCheckable(True)
        act_top.setChecked(bool(self.settings.get("always_on_top")) and not desktop_active)
        act_desktop = None
        if sysutil.supports_desktop_layer():
            act_desktop = menu.addAction("贴桌面层（置于底层）")
            act_desktop.setCheckable(True)
            act_desktop.setChecked(desktop_active)
        act_done = menu.addAction("显示已完成")
        act_done.setCheckable(True)
        act_done.setChecked(bool(self.settings.get("show_completed")))
        act_height = menu.addAction("高度自适应")
        act_height.setEnabled(bool(self.settings.get("list_height")))
        act_edge = menu.addAction("贴边自动收纳")
        act_edge.setCheckable(True)
        act_edge.setChecked(bool(self.settings.get("edge_dock_enabled", True)))
        menu.addSeparator()
        act_settings = menu.addAction("设置…")
        act_hide = menu.addAction("隐藏到托盘")
        menu.addSeparator()
        act_quit = menu.addAction("退出")

        chosen = menu.exec(pos)
        if chosen is None:
            return
        if chosen is act_sync:
            self.sync_requested.emit()
        elif chosen is act_reset:
            self.reset_requested.emit()
        elif chosen is act_edge:
            enabled = act_edge.isChecked()
            self.settings.set("edge_dock_enabled", enabled)
            if not enabled:
                self._clear_edge()
            self._persist_position()
        elif chosen is act_add:
            self.add_item()
        elif chosen is act_lock:
            self._apply_lock(act_lock.isChecked())
            self.settings.set("locked", act_lock.isChecked())
        elif chosen is act_top:
            value = act_top.isChecked()
            self.settings.update({"always_on_top": value, "desktop_layer": False if value else self.settings.get("desktop_layer")})
            self.apply_window_mode()
        elif act_desktop is not None and chosen is act_desktop:
            value = act_desktop.isChecked()
            self.settings.update({"desktop_layer": value})
            self.apply_window_mode()
        elif chosen is act_done:
            self.settings.set("show_completed", act_done.isChecked())
            self.reload()
        elif chosen is act_height:
            self.reset_height()
        elif chosen is act_settings:
            self.open_settings()
        elif chosen is act_hide:
            self._on_close_clicked()
        elif chosen is act_quit:
            self.quit_requested.emit()

    def nativeEvent(self, eventType, message):  # noqa: N802
        """响应其它实例发来的「唤醒窗口」广播。"""
        if bytes(eventType) not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return super().nativeEvent(eventType, message)
        try:
            msg = _MSG.from_address(int(message))
            message_id = sysutil.show_message_id()
            if message_id and msg.message == message_id:
                self.showNormal()
                self.raise_()
                self.activateWindow()
                return True, 0
        except (ValueError, OSError):
            pass
        return super().nativeEvent(eventType, message)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.hide()
        self.hide_requested.emit()

    def set_quitting(self) -> None:
        self._quitting = True

    # ==================================================================
    # 定时刷新
    # ==================================================================
    def _on_tick(self) -> None:
        self._elapsed += 0.15
        self._update_edge_state()
        self._heal_height()
        now = datetime.now()
        second = now.second
        if second != self._last_second:
            self._last_second = second
            for row in self._rows:
                row.refresh_time(now)
        pulse = pulse_wave(self._elapsed)
        for row in self._rows:
            row.set_pulse(pulse)
        if self._syncing:
            self._spin = (self._spin + 12) % 360
            self._btn_sync.set_rotation(self._spin)

    def _heal_height(self) -> None:
        """兜底：若窗口高度与目标不一致（例如某些环境下布局算错），自动纠正。"""
        if self._manual_view is not None or not self.isVisible():
            return
        now = time.monotonic()
        if now - self._last_heal < 2.0:
            return
        target = self._target_view_height()
        if abs(self._scroll.height() - target) > 4:
            self._last_heal = now
            self._apply_height(target)

    # ==================================================================
    # 同步状态
    # ==================================================================
    def set_syncing(self, syncing: bool) -> None:
        self._syncing = syncing
        self._btn_sync.setEnabled(not syncing)
        if not syncing:
            self._spin = 0.0
            self._btn_sync.set_rotation(0.0)
        self._update_status()

    def on_sync_finished(self) -> None:
        self.set_syncing(False)
        self.reload()


