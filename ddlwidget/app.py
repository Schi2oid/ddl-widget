"""应用入口与控制器。"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from . import icons, paths, sync, theme, tips, sysutil
from .briefing import BriefingDialog
from .db import Database
from .dialogs import EditorDialog, SettingsDialog
from .main_window import MainWindow
from .settings import Settings
from .tray import TrayIcon

SERVER_NAME = "houyk.ddlwidget.single"


class SyncWorker(QThread):
    done = Signal(object)

    def __init__(self, db: Database, exe: str, args: list[str], timeout: int) -> None:
        super().__init__()
        self._db = db
        self._exe = exe
        self._args = args
        self._timeout = timeout

    def run(self) -> None:  # noqa: D401
        try:
            result = sync.sync_now(self._db, self._exe, self._args, self._timeout)
        except Exception as exc:  # 兜底，避免线程崩溃后界面卡在同步中
            result = sync.SyncResult(ok=False, message=f"同步异常：{exc}")
        self.done.emit(result)


class App(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.settings = Settings()
        self.db = Database()
        self.window = MainWindow(self.db, self.settings)
        self.tray = TrayIcon(self, qapp)
        self.tray.show()

        self._worker: SyncWorker | None = None
        self._await_briefing = False
        self._briefing_open = False
        self._last_wall = datetime.now()
        self._last_mono = _monotonic()
        self._last_date = datetime.now().date()

        self.window.sync_requested.connect(lambda: self.start_sync())
        self.window.reset_requested.connect(self.reset_synced_pending)
        self.window.notify.connect(self._notify)
        self.window.quit_requested.connect(self.quit)
        self.window.hide_requested.connect(self._on_hidden)
        self.window.settings_changed.connect(self._on_settings_changed)
        self.tray.messageClicked.connect(self.show_widget)

        self._watch = QTimer(self)
        self._watch.setInterval(20_000)
        self._watch.timeout.connect(self._on_watch_tick)
        self._watch.start()

    # ------------------------------------------------------------------
    # 启动
    # ------------------------------------------------------------------
    def start(self, autostart: bool = False, force_demo: bool = False) -> None:
        self.show_widget()
        QTimer.singleShot(900, self._startup_refresh)

    def _startup_refresh(self) -> None:
        self._await_briefing = self._needs_briefing()
        if self._await_briefing or bool(self.settings.get("sync_on_start")):
            self.start_sync()
        else:
            self.window.reload()

    def _needs_briefing(self) -> bool:
        if not bool(self.settings.get("daily_briefing")):
            return False
        today = datetime.now().strftime("%Y-%m-%d")
        return self.db.get_meta("last_daily_popup_date") != today

    # ------------------------------------------------------------------
    # 同步
    # ------------------------------------------------------------------
    def start_sync(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self.window.set_syncing(True)
        self.tray.set_busy(True)
        worker = SyncWorker(
            self.db,
            str(self.settings.get("pku3b_path")),
            list(self.settings.get("pku3b_args")),
            int(self.settings.get("pku3b_timeout")),
        )
        worker.done.connect(self._on_sync_done)
        worker.finished.connect(worker.deleteLater)
        self._worker = worker
        worker.start()

    def _on_sync_done(self, result) -> None:
        self._worker = None
        if result.ok:
            logging.info(
                "sync ok: total=%s added=%s updated=%s stale=%s %.1fs",
                result.total, result.added, result.updated, result.stale, result.duration,
            )
        else:
            logging.warning("sync failed: %s", result.message)
        self.window.on_sync_finished()
        self.tray.set_busy(False)
        self.tray.refresh()
        self._refresh_tooltip()

        if not result.ok:
            self._notify(
                "同步失败",
                result.message or "无法获取教学网作业",
                warning=True,
            )
            return

        if result.completed_ids:
            self.window.celebrate_synced(result.completed_ids)
            self._notify(
                "教学网有新完成",
                f"{len(result.completed_ids)} 项作业已标记为完成",
            )

        if self._await_briefing:
            self._await_briefing = False
            self._show_briefing()

    def sync_now_from_tray(self) -> None:
        self.show_widget()
        self.start_sync()

    def reset_synced_pending(self) -> None:
        """把教学网上仍未提交的作业全部恢复为待办（解除手动勾选）。"""
        changed = self.db.reset_remote_pending()
        self.window.reload()
        if changed:
            self._notify(
                "已恢复为待办",
                f"{changed} 条教学网作业已标记为未完成，正在同步确认…",
            )
            self.start_sync()
        else:
            self._notify("无需重置", "教学网上没有未提交的条目")

    # ------------------------------------------------------------------
    # 简报
    # ------------------------------------------------------------------
    def _show_briefing(self) -> None:
        if self._briefing_open:
            return
        items = sync.pending_for_briefing(self.db, days=7)
        today = datetime.now().date()
        urgent = [i for i in items if i.due_time and i.due_time.date() == today]

        today_str = datetime.now().strftime("%Y-%m-%d")
        self.db.set_meta("last_daily_popup_date", today_str)
        for item in urgent:
            # 记录每个条目今天已经提醒过，便于后续做更细的去重
            self.db.mark_notified(item.id, today_str)

        if urgent:
            self._notify(
                "今日 DDL 提醒",
                "今天有 %d 项作业截止：" % len(urgent)
                + "、".join(i.title for i in urgent[:3]),
                warning=True,
            )

        dialog = BriefingDialog(items, None)
        dialog.open_requested.connect(self.show_widget)
        self._briefing_open = True
        try:
            dialog.exec()
        finally:
            self._briefing_open = False
            self._refresh_tooltip()

    # ------------------------------------------------------------------
    # 调度：跨天 / 休眠唤醒
    # ------------------------------------------------------------------
    def _on_watch_tick(self) -> None:
        wall_gap = (datetime.now() - self._last_wall).total_seconds()
        mono_gap = _monotonic() - self._last_mono
        slept = wall_gap - mono_gap > 60
        day_changed = datetime.now().date() != self._last_date
        self._last_wall = datetime.now()
        self._last_mono = _monotonic()
        self._last_date = datetime.now().date()

        if slept or day_changed:
            if self._needs_briefing():
                self._await_briefing = True
                self.start_sync()

    # ------------------------------------------------------------------
    # 窗口
    # ------------------------------------------------------------------
    def show_widget(self) -> None:
        self.window.bring_to_front()
        self.tray.refresh()
        self._refresh_tooltip()

    def hide_widget(self) -> None:
        self.window.hide()
        self.tray.refresh()

    def window_visible(self) -> bool:
        return self.window.isVisible()

    def toggle_window(self) -> None:
        if self.window.isVisible() and not self.window.isMinimized():
            self.hide_widget()
        else:
            self.show_widget()

    def _on_hidden(self) -> None:
        self.tray.refresh()
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.quit()

    def _on_settings_changed(self) -> None:
        self.tray.refresh()
        self.window.reload(reset_geometry=True)
        self._refresh_tooltip()

    def open_settings(self) -> None:
        self.window.open_settings()

    def add_from_tray(self) -> None:
        self.show_widget()
        self.window.add_item()

    def _notify(self, title: str, body: str, warning: bool = False) -> None:
        """系统通知：macOS 走 osascript，Windows 用托盘气泡。"""
        if sysutil.system_notify(title, body):
            return
        icon = (
            QSystemTrayIcon.MessageIcon.Warning
            if warning
            else QSystemTrayIcon.MessageIcon.Information
        )
        self.tray.showMessage(title, body, icon, 6000)

    def toggle_autostart(self, checked: bool) -> None:
        ok, message = sysutil.set_autostart(checked)
        if not ok:
            self._notify("开机自启设置失败", message, warning=True)
        else:
            self.settings.set("autostart", checked)
        self.tray.refresh()

    def _refresh_tooltip(self) -> None:
        pending = self.db.pending_count()
        synced = self.db.get_meta("last_sync_at")
        when = ""
        if synced:
            try:
                when = datetime.fromisoformat(synced).strftime("%H:%M")
            except ValueError:
                when = ""
        text = f"DDL · {pending} 项待办"
        if when:
            text += f"\n最近同步 {when}"
        self.tray.update_tooltip(text)

    # ------------------------------------------------------------------
    def quit(self) -> None:
        self.window.set_quitting()
        self.settings.set("window_pos", [self.window.x(), self.window.y()])
        self.tray.hide()
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(1500)
        self.db.close()
        self.qapp.quit()


def _monotonic() -> float:
    import time

    return time.monotonic()


def setup_logging() -> None:
    """pythonw 下没有控制台，异常必须落到文件里。"""
    try:
        logging.basicConfig(
            filename=str(paths.log_path()),
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            encoding="utf-8",
        )
    except OSError:
        pass

    def hook(exc_type, exc, tb) -> None:
        logging.error("未捕获异常", exc_info=(exc_type, exc, tb))

    sys.excepthook = hook


def _signal_existing_instance() -> bool:
    """已有实例在跑就唤醒它并返回 True。"""
    for _attempt in range(4):
        socket = QLocalSocket()
        socket.connectToServer(SERVER_NAME)
        if socket.waitForConnected(250):
            socket.write(b"show")
            socket.flush()
            socket.waitForBytesWritten(250)
            socket.disconnectFromServer()
            return True
        socket.abort()
        time.sleep(0.12)
    return False


def _wake_existing() -> None:
    """已有实例在跑：叫它把窗口显示出来，然后本进程退出。"""
    if not _signal_existing_instance():
        sysutil.broadcast_show()
    logging.info("已有实例在运行，本次启动退出并唤醒旧窗口")


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    sysutil.set_app_user_model_id()

    qapp = QApplication(sys.argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setStyle("Fusion")
    qapp.setApplicationName("DDLWidget")
    qapp.setApplicationDisplayName("DDL · 作业截止日")
    qapp.setWindowIcon(icons.app_icon())

    if not sysutil.acquire_single_instance():
        _wake_existing()
        return 0

    server = QLocalServer(qapp)
    QLocalServer.removeServer(SERVER_NAME)
    listening = server.listen(SERVER_NAME)
    if not listening:
        if not sysutil.IS_WINDOWS:
            # macOS / Linux 上命名管道（Unix socket）是可靠的，连不上说明已有实例
            _wake_existing()
            return 0
        logging.debug("单实例管道不可用，已退化为窗口消息唤醒")

    tips.TipController(qapp)   # 用自绘提示替换系统 tooltip（避免黑色阴影窗）
    app = App(qapp)
    server.newConnection.connect(lambda: (app.show_widget(), server.nextPendingConnection()))

    autostart = "--autostart" in (argv or sys.argv)
    app.start(autostart=autostart)
    return qapp.exec()
