"""用户设置（JSON 持久化）。"""

from __future__ import annotations

import json
import threading
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    # --- pku3b ---
    "pku3b_path": paths.DEFAULT_PKU3B,
    "pku3b_args": ["a", "-f", "ls", "-a"],
    "pku3b_timeout": 180,
    # --- 窗口 ---
    "always_on_top": True,        # 置顶
    "desktop_layer": False,       # 贴桌面层（置于底层）
    "opacity": 0.96,              # 0.55 ~ 1.0
    "locked": False,              # 锁定位置（禁止拖动）
    "edge_dock_enabled": True,    # 拖到屏幕左右边缘时自动收纳
    "edge_dock": "",              # "" | "left" | "right"
    "window_pos": None,           # [x, y]
    "list_height": None,          # 手动拖拽后的列表高度；None = 按内容自适应
    # --- 行为 ---
    "autostart": False,
    "sync_on_start": True,
    "daily_briefing": True,       # 每日首次唤醒弹简报
    "show_completed": False,      # 时间线里显示已完成
    "confirm_delete": True,
}


class Settings:
    """线程安全的键值设置。写入立即落盘。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load()

    # ------------------------------------------------------------------
    def load(self) -> None:
        path = paths.settings_path()
        if not path.exists():
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(raw, dict):
            with self._lock:
                for key, value in raw.items():
                    if key in DEFAULTS or key.startswith("_"):
                        self._data[key] = value

    def save(self) -> None:
        with self._lock:
            snapshot = dict(self._data)
        path = paths.settings_path()
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

    # ------------------------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        with self._lock:
            self._data[key] = value
        if save:
            self.save()

    def update(self, values: dict[str, Any]) -> None:
        with self._lock:
            self._data.update(values)
        self.save()

    def as_dict(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._data)
