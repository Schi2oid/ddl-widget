"""对话框：添加/编辑 DDL、设置。"""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QDesktopServices, QPainter, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from . import paths, theme, sysutil
from .models import DDL, GROUP_COLOR
from .theme import font
from .widgets import IconButton, ToggleSwitch

SHADOW = 20


class GlassDialog(QDialog):
    """无边框半透明圆角对话框基类。"""

    def __init__(self, parent=None, width: int = 404, title: str = "") -> None:
        super().__init__(parent)
        self._card_width = width
        self._bg: QPixmap | None = None
        self._bg_key: tuple | None = None
        self._drag_origin: QPoint | None = None
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        if sysutil.IS_MAC or (
            parent is not None
            and bool(parent.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        ):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(width + SHADOW * 2)
        self.setStyleSheet(theme.dialog_qss())

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(SHADOW + 22, SHADOW + 16, SHADOW + 22, SHADOW + 18)
        self._root.setSpacing(14)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._title_label = QLabel(title)
        self._title_label.setObjectName("dialogTitle")
        self._title_label.setFont(font(15, 700))
        header.addWidget(self._title_label, 1)
        self._close_btn = IconButton("close", 26, 11, "关闭")
        self._close_btn.clicked.connect(self.reject)
        header.addWidget(self._close_btn, 0, Qt.AlignmentFlag.AlignTop)
        self._root.addLayout(header)

    # ------------------------------------------------------------------
    def card_width(self) -> int:
        return self._card_width

    def paintEvent(self, event) -> None:  # noqa: N802
        key = (self.size(), self.devicePixelRatioF())
        if self._bg is None or self._bg_key != key:
            self._render_bg()
        painter = QPainter(self)
        if self._bg is not None:
            painter.drawPixmap(0, 0, self._bg)

    def _render_bg(self) -> None:
        dpr = self.devicePixelRatioF()
        pixmap = QPixmap(int(self.width() * dpr), int(self.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.paint_dialog_bg(painter, self.width(), self.height(), SHADOW, 16, 1.0)
        painter.end()
        self._bg = pixmap
        self._bg_key = (self.size(), dpr)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._bg = None
        self._bg_key = None
        super().resizeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            geo = parent.geometry()
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
        else:
            screen = self.screen() or QApplication.primaryScreen()
            geo = screen.availableGeometry() if screen is not None else None
            if geo is None:
                self._bg = None
                self._bg_key = None
                return
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
        self.move(x, y)
        self._bg = None
        self._bg_key = None
        self.raise_()
        self.activateWindow()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < SHADOW + 60:
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
            event.accept()
            return
        super().mouseReleaseEvent(event)


# ----------------------------------------------------------------------
def _field_label(text: str, parent: QWidget | None = None) -> QLabel:
    label = QLabel(text, parent)
    label.setObjectName("fieldLabel")
    label.setFont(font(11, 600, 0.3))
    return label


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("sectionTitle")
    label.setFont(font(10, 700, 1.0))
    return label


class EditorDialog(GlassDialog):
    """新增 / 编辑一条 DDL。"""

    def __init__(self, item: DDL | None, parent=None) -> None:
        title = "编辑 DDL" if item else "添加 DDL"
        super().__init__(parent, width=404, title=title)
        self._item = item
        self._result: dict | None = None
        self._delete_armed = False

        # 标题
        self._root.addWidget(_field_label("标题"))
        self._title_edit = QLineEdit(self)
        self._title_edit.setPlaceholderText("例如：第三次作业")
        self._title_edit.setFont(font(13, 400))
        if item:
            self._title_edit.setText(item.title)
        self._root.addWidget(self._title_edit)

        # 课程
        self._root.addWidget(_field_label("课程 / 分类（可留空）"))
        self._course_edit = QLineEdit(self)
        self._course_edit.setPlaceholderText("例如：计算概论A")
        self._course_edit.setFont(font(13, 400))
        if item:
            self._course_edit.setText(item.course_name)
        self._root.addWidget(self._course_edit)

        # 截止时间
        due_row = QHBoxLayout()
        due_row.setSpacing(8)
        due_row.addWidget(_field_label("截止时间"), 1)
        self._no_due_label = QLabel("无截止时间")
        self._no_due_label.setObjectName("hint")
        self._no_due_label.setFont(font(11, 400))
        due_row.addWidget(self._no_due_label, 0, Qt.AlignmentFlag.AlignVCenter)
        self._no_due = ToggleSwitch(item is not None and item.due_time is None, self)
        due_row.addWidget(self._no_due, 0, Qt.AlignmentFlag.AlignVCenter)
        self._root.addLayout(due_row)

        self._due_edit = QDateTimeEdit(self)
        self._due_edit.setDisplayFormat("yyyy-MM-dd  HH:mm")
        self._due_edit.setCalendarPopup(True)
        self._due_edit.setFont(font(13, 400))
        initial = item.due_time if (item and item.due_time) else _default_due()
        self._due_edit.setDateTime(QDateTime(initial))
        self._root.addWidget(self._due_edit)
        self._no_due.toggled.connect(lambda checked: self._due_edit.setEnabled(not checked))
        self._due_edit.setEnabled(not self._no_due.isChecked())

        # 快捷时间
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for text, target in (
            ("今天 23:59", _today_2359()),
            ("明天 23:59", _today_2359() + timedelta(days=1)),
            ("下周一", _next_monday_2359()),
            ("一周后", _today_2359() + timedelta(days=7)),
        ):
            chip = QPushButton(text, self)
            chip.setObjectName("chip")
            chip.setFont(font(11, 500))
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.clicked.connect(lambda _=False, dt=target: self._set_due(dt))
            chips.addWidget(chip)
        chips.addStretch(1)
        self._root.addLayout(chips)

        # 提示
        self._hint = QLabel("", self)
        self._hint.setObjectName("hint")
        self._hint.setFont(font(11, 400))
        self._hint.setWordWrap(True)
        if item is not None and item.source == "pku3b":
            self._hint.setText("这是教学网同步来的作业，修改只保存在本地，不会写回教学网。")
            self._hint.show()
        else:
            self._hint.hide()
        self._root.addWidget(self._hint)

        self._error = QLabel("", self)
        self._error.setObjectName("error")
        self._error.setFont(font(11, 500))
        self._error.hide()
        self._root.addWidget(self._error)

        # 按钮
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        if item is not None:
            self._delete_btn = QPushButton("删除", self)
            self._delete_btn.setObjectName("danger")
            self._delete_btn.setFont(font(12, 500))
            self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._delete_btn.clicked.connect(self._on_delete)
            buttons.addWidget(self._delete_btn)
        buttons.addStretch(1)
        cancel = QPushButton("取消", self)
        cancel.setObjectName("ghost")
        cancel.setFont(font(12, 500))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("保存", self)
        save.setObjectName("primary")
        save.setFont(font(12, 600))
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.setDefault(True)
        save.clicked.connect(self._on_save)
        buttons.addWidget(save)
        self._root.addLayout(buttons)

        self._title_edit.returnPressed.connect(self._on_save)
        self._course_edit.returnPressed.connect(self._on_save)
        self.adjustSize()
        self._title_edit.setFocus()

    # ------------------------------------------------------------------
    def _set_due(self, target: datetime) -> None:
        self._no_due.setChecked(False)
        self._due_edit.setDateTime(QDateTime(target))

    def _on_delete(self) -> None:
        if not self._delete_armed:
            self._delete_armed = True
            self._delete_btn.setText("再点一次确认删除")
            return
        self._result = {"__delete__": True}
        self.accept()

    def _on_save(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            self._error.setText("标题不能为空")
            self._error.show()
            self._title_edit.setFocus()
            return
        due = None if self._no_due.isChecked() else self._due_edit.dateTime().toPython()
        self._result = {
            "title": title,
            "course": self._course_edit.text().strip(),
            "due": due,
        }
        self.accept()

    def result_data(self) -> dict | None:
        return self._result


# ----------------------------------------------------------------------
class SettingsDialog(GlassDialog):
    """设置面板。"""

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent, width=430, title="设置")
        self._settings = settings
        self._result = settings.as_dict()

        # 教学网
        self._root.addWidget(_section("教学网"))
        self._root.addWidget(_field_label("pku3b 可执行文件"))
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._path_edit = QLineEdit(self)
        self._path_edit.setFont(font(12, 400))
        self._path_edit.setText(str(settings.get("pku3b_path")))
        path_row.addWidget(self._path_edit, 1)
        browse = QPushButton("浏览", self)
        browse.setObjectName("ghost")
        browse.setFont(font(12, 500))
        browse.setCursor(Qt.CursorShape.PointingHandCursor)
        browse.clicked.connect(self._browse)
        path_row.addWidget(browse)
        self._root.addLayout(path_row)

        self._sync_on_start = self._toggle_row("启动时自动同步", settings.get("sync_on_start"))
        self._daily = self._toggle_row("每日首次唤醒弹出简报", settings.get("daily_briefing"))

        # 行为
        self._root.addWidget(_section("系统"))
        self._autostart = self._toggle_row("开机自动启动", sysutil.autostart_enabled())

        # 外观
        self._root.addWidget(_section("外观"))
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_row.addWidget(_field_label("窗口层级"), 1)
        self._mode = QComboBox(self)
        self._mode.setFont(font(12, 400))
        self._mode_keys = [("top", "置顶显示"), ("normal", "普通窗口")]
        if sysutil.supports_desktop_layer():
            self._mode_keys.append(("desktop", "贴桌面层（置于底层）"))
        self._mode.addItems([label for _key, label in self._mode_keys])
        current = (
            "desktop"
            if settings.get("desktop_layer") and sysutil.supports_desktop_layer()
            else ("top" if settings.get("always_on_top") else "normal")
        )
        for index, (key, _label) in enumerate(self._mode_keys):
            if key == current:
                self._mode.setCurrentIndex(index)
                break
        self._mode.setFixedWidth(190)
        mode_row.addWidget(self._mode, 0)
        self._root.addLayout(mode_row)

        opacity_row = QHBoxLayout()
        opacity_row.setSpacing(10)
        opacity_row.addWidget(_field_label("不透明度"), 0)
        self._opacity = QSlider(Qt.Orientation.Horizontal, self)
        self._opacity.setRange(60, 100)
        self._opacity.setValue(int(float(settings.get("opacity", 0.96)) * 100))
        self._opacity.valueChanged.connect(self._on_opacity)
        opacity_row.addWidget(self._opacity, 1)
        self._opacity_value = QLabel(f"{self._opacity.value()}%", self)
        self._opacity_value.setObjectName("hint")
        self._opacity_value.setFont(font(11, 500))
        self._opacity_value.setFixedWidth(34)
        self._opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        opacity_row.addWidget(self._opacity_value, 0)
        self._root.addLayout(opacity_row)

        self._show_completed = self._toggle_row("在时间线里显示已完成", settings.get("show_completed"))
        self._edge_dock = self._toggle_row(
            "贴边自动收纳（拖到左右屏幕边缘时收起）", settings.get("edge_dock_enabled", True)
        )

        # 数据
        self._root.addWidget(_section("数据"))
        data_row = QHBoxLayout()
        data_row.setSpacing(8)
        data_label = QLabel(str(paths.app_data_dir()))
        data_label.setObjectName("hint")
        data_label.setFont(font(11, 400))
        data_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        data_row.addWidget(data_label, 1)
        open_btn = QPushButton("打开目录", self)
        open_btn.setObjectName("ghost")
        open_btn.setFont(font(11, 500))
        open_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        open_btn.clicked.connect(self._open_data_dir)
        data_row.addWidget(open_btn)
        self._root.addLayout(data_row)

        self._error = QLabel("", self)
        self._error.setObjectName("error")
        self._error.setFont(font(11, 500))
        self._error.setWordWrap(True)
        self._error.hide()
        self._root.addWidget(self._error)

        # 按钮
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("取消", self)
        cancel.setObjectName("ghost")
        cancel.setFont(font(12, 500))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("保存", self)
        save.setObjectName("primary")
        save.setFont(font(12, 600))
        save.setCursor(Qt.CursorShape.PointingHandCursor)
        save.clicked.connect(self._on_save)
        buttons.addWidget(save)
        self._root.addLayout(buttons)

        self.adjustSize()

    # ------------------------------------------------------------------
    def _toggle_row(self, text: str, value) -> ToggleSwitch:
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(text)
        label.setFont(font(12, 400))
        label.setStyleSheet(f"color: {theme.TEXT_SECONDARY};")
        row.addWidget(label, 1)
        toggle = ToggleSwitch(bool(value), self)
        row.addWidget(toggle, 0)
        self._root.addLayout(row)
        return toggle

    def _on_opacity(self, value: int) -> None:
        self._opacity_value.setText(f"{value}%")

    def _browse(self) -> None:
        title = "选择 pku3b.exe" if sysutil.IS_WINDOWS else "选择 pku3b 可执行文件"
        filt = "可执行文件 (*.exe);;所有文件 (*)" if sysutil.IS_WINDOWS else "所有文件 (*)"
        file_name, _ = QFileDialog.getOpenFileName(
            self, title, str(paths.project_root()), filt
        )
        if file_name:
            self._path_edit.setText(file_name)

    def _open_data_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(paths.app_data_dir())))

    def _on_save(self) -> None:
        mode = self._mode_keys[self._mode.currentIndex()][0]
        autostart = self._autostart.isChecked()
        current = sysutil.autostart_enabled()
        if autostart != current:
            ok, message = sysutil.set_autostart(autostart)
            if not ok:
                self._error.setText(message)
                self._error.show()
                return
        self._result = {
            "pku3b_path": self._path_edit.text().strip(),
            "sync_on_start": self._sync_on_start.isChecked(),
            "daily_briefing": self._daily.isChecked(),
            "autostart": autostart,
            "always_on_top": mode == "top",
            "desktop_layer": mode == "desktop",
            "opacity": round(self._opacity.value() / 100.0, 2),
            "show_completed": self._show_completed.isChecked(),
            "edge_dock_enabled": self._edge_dock.isChecked(),
        }
        self.accept()

    def result_data(self) -> dict:
        return self._result


# ----------------------------------------------------------------------
def _today_2359() -> datetime:
    now = datetime.now()
    return now.replace(hour=23, minute=59, second=0, microsecond=0)


def _default_due() -> datetime:
    target = _today_2359()
    if target <= datetime.now():
        target += timedelta(days=1)
    return target


def _next_monday_2359() -> datetime:
    base = _today_2359()
    days = (7 - base.weekday()) % 7 or 7
    return base + timedelta(days=days)
