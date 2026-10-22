"""平台相关能力：开机自启、窗口层级、单实例、DLL 修复、系统通知。

Windows 用注册表 + 命名互斥量 + SetWindowPos；
macOS 用 LaunchAgent + QLocalServer + 系统通知（osascript）。
不支持的平台一律降级，不抛异常。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import sysconfig
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from . import paths

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "DDLWidget"

LAUNCH_AGENT_LABEL = "com.houyk.ddlwidget"

HWND_TOPMOST = -1
HWND_BOTTOM = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200


def supports_desktop_layer() -> bool:
    """「贴桌面层」（把自己压到所有普通窗口下面）只有 Windows 有对应语义。"""
    return IS_WINDOWS


# ----------------------------------------------------------------------
# Qt DLL 冲突修复（仅 Windows：MikTeX 等自带的 Qt6Core.dll 会抢先加载）
# ----------------------------------------------------------------------
def sanitize_dll_path() -> list[str]:
    if not IS_WINDOWS:
        return []

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


def launch_command() -> str:
    """开机自启时执行的命令行（便于排查 / 手动添加）。"""
    return _launch_command()


def _launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _launch_agent_plist() -> str:
    entry = paths.project_root() / "run.pyw"
    log_dir = paths.app_data_dir()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        f"  <key>Label</key><string>{LAUNCH_AGENT_LABEL}</string>\n"
        "  <key>ProgramArguments</key>\n  <array>\n"
        f"    <string>{xml_escape(str(paths.pythonw()))}</string>\n"
        f"    <string>{xml_escape(str(entry))}</string>\n"
        "    <string>--autostart</string>\n"
        "  </array>\n"
        f"  <key>WorkingDirectory</key><string>{xml_escape(str(entry.parent))}</string>\n"
        "  <key>RunAtLoad</key><true/>\n"
        "  <key>KeepAlive</key><false/>\n"
        f"  <key>StandardOutPath</key><string>"
        f"{xml_escape(str(log_dir / 'launchd.out.log'))}</string>\n"
        f"  <key>StandardErrorPath</key><string>"
        f"{xml_escape(str(log_dir / 'launchd.err.log'))}</string>\n"
        "</dict>\n</plist>\n"
    )


def _launchctl(args: list[str]) -> bool:
    try:
        result = subprocess.run(
            ["launchctl", *args], capture_output=True, timeout=15
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def autostart_enabled() -> bool:
    if IS_MAC:
        return _launch_agent_path().exists()
    if not IS_WINDOWS:
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, RUN_VALUE)
            return bool(value)
    except (ImportError, FileNotFoundError, OSError):
        return False


def set_autostart(enabled: bool) -> tuple[bool, str]:
    """返回 (是否成功, 失败原因)。"""
    if IS_MAC:
        return _set_autostart_mac(enabled)
    if not IS_WINDOWS:
        return False, "当前平台暂不支持开机自启"
    return _set_autostart_windows(enabled)


def _set_autostart_mac(enabled: bool) -> tuple[bool, str]:
    plist = _launch_agent_path()
    uid = os.getuid() if hasattr(os, "getuid") else 501
    if enabled:
        try:
            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_text(_launch_agent_plist(), encoding="utf-8")
        except OSError as exc:
            return False, f"写入 LaunchAgent 失败：{exc}"
        if not (
            _launchctl(["bootstrap", f"gui/{uid}", str(plist)])
            or _launchctl(["load", "-w", str(plist)])
        ):
            return False, "launchctl 加载失败（可尝试手动执行 launchctl load -w）"
        return True, ""

    _launchctl(["bootout", f"gui/{uid}/{LAUNCH_AGENT_LABEL}"]) or _launchctl(
        ["unload", "-w", str(plist)]
    )
    try:
        plist.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        return False, f"删除 LaunchAgent 失败：{exc}"
    return True, ""


def _set_autostart_windows(enabled: bool) -> tuple[bool, str]:
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


# ----------------------------------------------------------------------
# 窗口层级
# ----------------------------------------------------------------------
def set_topmost(hwnd: int, on: bool) -> None:
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.user32.SetWindowPos(
            int(hwnd),
            HWND_TOPMOST if on else -2,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
        )
    except (OSError, AttributeError):
        pass


def send_to_bottom(hwnd: int) -> None:
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.user32.SetWindowPos(
            int(hwnd),
            HWND_BOTTOM,
            0, 0, 0, 0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
        )
    except (OSError, AttributeError):
        pass


# ----------------------------------------------------------------------
# 单实例
# ----------------------------------------------------------------------
ERROR_ALREADY_EXISTS = 183
HWND_BROADCAST = 0xFFFF

_single_instance_handle = 0
_show_message_id = 0


def acquire_single_instance(name: str = "Local\\DDLWidget_singleton_v1") -> bool:
    """Windows 用命名互斥量；其它平台返回 True，交给 QLocalServer 判断。"""
    if not IS_WINDOWS:
        return True
    global _single_instance_handle
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        _single_instance_handle = kernel32.CreateMutexW(None, False, name)
        return kernel32.GetLastError() != ERROR_ALREADY_EXISTS
    except (OSError, AttributeError):
        return True


def show_message_id() -> int:
    """Windows：注册自定义窗口消息，用于唤醒已有实例。"""
    if not IS_WINDOWS:
        return 0
    global _show_message_id
    if not _show_message_id:
        try:
            import ctypes

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
        import ctypes

        ctypes.windll.user32.PostMessageW(HWND_BROADCAST, message_id, 0, 0)
    except (OSError, AttributeError):
        pass


def set_app_user_model_id(app_id: str = "houyk.ddlwidget.1") -> None:
    if not IS_WINDOWS:
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (OSError, AttributeError):
        pass


# ----------------------------------------------------------------------
# 系统通知
# ----------------------------------------------------------------------
def system_notify(title: str, body: str) -> bool:
    """macOS 走 osascript 的原生通知；Windows 由调用方用托盘气泡。"""
    if not IS_MAC:
        return False
    script = (
        f"display notification {json.dumps(body, ensure_ascii=False)} "
        f"with title {json.dumps(title, ensure_ascii=False)}"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=8,
            check=False,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False
