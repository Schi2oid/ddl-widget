"""应用路径与常量（Windows / macOS）。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "DDLWidget"
APP_TITLE = "DDL · 作业截止日"

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

#: pku3b 可执行文件默认位置（Windows 常见装法），macOS 走 PATH 查找
if IS_WINDOWS:
    DEFAULT_PKU3B = r"D:\Softwares\pku3b\pku3b.exe"
else:
    DEFAULT_PKU3B = "pku3b"


def _pku3b_dirs() -> tuple[Path, Path]:
    """pku3b 自己的配置 / 缓存目录（仅用于展示与文档）。"""
    home = Path.home()
    if IS_WINDOWS:
        appdata = Path(os.environ.get("APPDATA", home))
        local = Path(os.environ.get("LOCALAPPDATA", home))
        return appdata / "sshwy" / "pku3b" / "config", local / "sshwy" / "pku3b" / "cache"
    if IS_MAC:
        support = home / "Library" / "Application Support" / "org.sshwy.pku3b"
        return support, home / "Library" / "Caches" / "org.sshwy.pku3b"
    return home / ".config" / "pku3b", home / ".cache" / "pku3b"


PKU3B_CONFIG_DIR, PKU3B_CACHE_DIR = _pku3b_dirs()


def project_root() -> Path:
    """包含 run.pyw / app.py 的目录。"""
    return Path(__file__).resolve().parent.parent


def _platform_data_dir() -> Path:
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / APP_NAME
    if IS_MAC:
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


_cached_data_dir: Path | None = None


def _writable(base: Path) -> bool:
    try:
        base.mkdir(parents=True, exist_ok=True)
        probe = base / ".write_probe"
        probe.write_text("1", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def app_data_dir() -> Path:
    """数据目录，优先系统标准位置。

    若该目录不可写（受限环境 / 便携使用），自动降级到程序目录下的 data/，
    避免启动直接崩溃。
    """
    global _cached_data_dir
    if _cached_data_dir is not None:
        return _cached_data_dir

    override = os.environ.get("DDL_WIDGET_DATA")
    if override:
        candidates = [Path(override)]
    else:
        candidates = [_platform_data_dir(), project_root() / "data"]

    for base in candidates:
        if _writable(base):
            _cached_data_dir = base
            return base

    _cached_data_dir = candidates[-1]
    try:
        _cached_data_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return _cached_data_dir


def db_path() -> Path:
    return app_data_dir() / "ddl.db"


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def log_path() -> Path:
    return app_data_dir() / "app.log"


def assets_dir() -> Path:
    return project_root() / "assets"


def pythonw() -> str:
    """无控制台的解释器：Windows 是 pythonw.exe，macOS 直接用当前 python3。"""
    if IS_WINDOWS:
        exe = Path(sys.executable)
        candidate = exe.with_name("pythonw.exe")
        return str(candidate if candidate.exists() else exe)
    return sys.executable


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
