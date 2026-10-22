"""Windows 集成：DLL 路径修复、开机自启、窗口层级、单实例。"""

from __future__ import annotations

import ctypes
import os
import sys
import sysconfig
from pathlib import Path

from . import paths

HWND_TOPMOST = -1
HWND_BOTTOM = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DDLWidget"


# ----------------------------------------------------------------------
# Qt DLL 冲突修复（MikTeX 等第三方 Qt6Core.dll 会抢先加载）
# ----------------------------------------------------------------------
def sanitize_dll_path() -> list[str]:
    """把 PySide6 目录提到 PATH 最前，并剔除其它携带 Qt6Core.dll 的目录。"""
    removed: list[str] = []
    try:
        site = sysconfig.get_paths().get("purelib") or ""
    except Exception:
        site = ""
    pyside_dir = str(Path(site) / "PySide6") if site else ""

    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    kept: list[str] = []
    for part in parts:
        try:
            if part.rstrip("\\").lower() != pyside_dir.rstrip("\\").lower() and (
                Path(part) / "Qt6Core.dll"
            ).exists():
                removed.append(part)
                continue
        except OSError:
            pass
        kept.append(part)

    if pyside_dir and Path(pyside_dir).exists():
        kept.insert(0, pyside_dir)
        try:
            os.add_dll_directory(pyside_dir)
        except (OSError, AttributeError):
            pass

    os.environ["PATH"] = os.pathsep.join(kept)
    return removed


# ----------------------------------------------------------------------
# 开机自启
# ----------------------------------------------------------------------
def _launch_command() -> str:
    if paths.is_frozen():
        return f'"{sys.executable}" --autostart'
    entry = paths.project_root() / "run.pyw"
    return f'"{paths.pythonw()}" "{entry}"'


def autostart_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            return bool(value)
    except (ImportError, FileNotFoundError, OSError):
        return False


def set_autostart(enabled: bool) -> tuple[bool, str]:
    """返回 (是否成功, 失败原因)。注册表写入可能被安全软件或策略拦截。"""
    try:
        import winreg
    except ImportError:
        return False, "当前 Python 缺少 winreg 模块"

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
        return True, ""
    except PermissionError:
        return False, "写入注册表被拒绝（可能被安全软件或系统策略拦截）"
    except FileNotFoundError:
        return False, "找不到 Run 注册表项"
    except OSError as exc:
        return False, f"注册表写入失败：{exc}"


def launch_command() -> str:
    """开机自启时执行的命令行（便于排查 / 手动添加）。"""
    return _launch_command()


# ----------------------------------------------------------------------
# 窗口层级
# ----------------------------------------------------------------------
def set_topmost(hwnd: int, on: bool) -> None:
    try:
        ctypes.windll.user32.SetWindowPos(
            int(hwnd),
            HWND_TOPMOST if on else -2,  # -2 = HWND_NOTOPMOST
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except OSError:
        pass


def send_to_bottom(hwnd: int) -> None:
    try:
        ctypes.windll.user32.SetWindowPos(
            int(hwnd),
            HWND_BOTTOM,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
        )
    except OSError:
        pass


# ----------------------------------------------------------------------
# 单实例
# ----------------------------------------------------------------------
ERROR_ALREADY_EXISTS = 183
HWND_BROADCAST = 0xFFFF

_single_instance_handle = 0
_show_message_id = 0


def acquire_single_instance(name: str = "Local\\DDLWidget_singleton_v1") -> bool:
    """用命名互斥量判断是否已有实例，返回 True 表示本进程是第一个。"""
    global _single_instance_handle
    try:
        kernel32 = ctypes.windll.kernel32
        _single_instance_handle = kernel32.CreateMutexW(None, False, name)
        return kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except (OSError, AttributeError):
        return True


def show_message_id() -> int:
    """注册自定义窗口消息，用于唤醒已有实例（不依赖命名管道）。"""
    global _show_message_id
    if not _show_message_id:
        try:
            _show_message_id = ctypes.windll.user32.RegisterWindowMessageW(
                "DDLWidget_ShowWindow_v1"
            )
        except (OSError, AttributeError):
            _show_message_id = 0
    return _show_message_id


def broadcast_show() -> None:
    message_id = show_message_id()
    if not message_id:
        return
    try:
        ctypes.windll.user32.PostMessageW(HWND_BROADCAST, message_id, 0, 0)
    except OSError:
        pass


def set_app_user_model_id(app_id: str = "houyk.ddlwidget.1") -> None:
    """让任务栏/通知把窗口认作独立应用。"""
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (OSError, AttributeError):
        pass
