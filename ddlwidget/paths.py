"""应用路径与常量。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "DDLWidget"
APP_TITLE = "DDL · 作业截止日"

#: pku3b 默认位置（用户本机）
DEFAULT_PKU3B = r"D:\Softwares\pku3b\pku3b.exe"

PKU3B_CONFIG_DIR = Path(os.environ.get("APPDATA", "")) / "sshwy" / "pku3b" / "config"
PKU3B_CACHE_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "sshwy" / "pku3b" / "cache"


def project_root() -> Path:
    """包含 run.pyw / app.py 的目录。"""
    return Path(__file__).resolve().parent.parent


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
    """数据目录，优先 %APPDATA%\\DDLWidget。

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
        candidates = [
            Path(os.environ.get("APPDATA") or str(Path.home())) / APP_NAME,
            project_root() / "data",
        ]

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
    """优先返回无控制台的 pythonw.exe。"""
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.exists() else exe)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))
