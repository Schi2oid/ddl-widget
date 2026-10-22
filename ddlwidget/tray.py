"""系统托盘图标与右键菜单。"""

from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import icons, theme, sysutil


class TrayIcon(QSystemTrayIcon):
    def __init__(self, controller, parent=None) -> None:
        super().__init__(icons.app_icon(), parent)
        self._c = controller
        self.setToolTip("DDL · 作业截止日")

        menu = QMenu()
        menu.setStyleSheet(theme.MENU_QSS)

        self._act_toggle = QAction("隐藏小组件", menu)
        self._act_toggle.triggered.connect(controller.toggle_window)
        menu.addAction(self._act_toggle)

        self._act_sync = QAction("立即同步教学网", menu)
        self._act_sync.triggered.connect(controller.sync_now_from_tray)
        menu.addAction(self._act_sync)

        act_add = QAction("添加 DDL…", menu)
        act_add.triggered.connect(controller.add_from_tray)
        menu.addAction(act_add)

        menu.addSeparator()

        self._act_autostart = QAction("开机自动启动", menu)
        self._act_autostart.setCheckable(True)
        self._act_autostart.setChecked(sysutil.autostart_enabled())
        self._act_autostart.triggered.connect(controller.toggle_autostart)
        menu.addAction(self._act_autostart)

        act_settings = QAction("设置…", menu)
        act_settings.triggered.connect(controller.open_settings)
        menu.addAction(act_settings)

        menu.addSeparator()

        act_quit = QAction("退出", menu)
        act_quit.triggered.connect(controller.quit)
        menu.addAction(act_quit)

        self._menu = menu
        self._menu.aboutToShow.connect(self.refresh)
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)

    # ------------------------------------------------------------------
    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._c.toggle_window()

    def refresh(self) -> None:
        self._act_toggle.setText("隐藏小组件" if self._c.window_visible() else "显示小组件")
        self._act_autostart.setChecked(sysutil.autostart_enabled())

    def set_busy(self, busy: bool) -> None:
        self._act_sync.setEnabled(not busy)
        self._act_sync.setText("正在同步…" if busy else "立即同步教学网")

    def update_tooltip(self, text: str) -> None:
        self.setToolTip(text)
