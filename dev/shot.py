"""离屏渲染预览：把小组件/弹窗画到模拟桌面上，输出 PNG 供检查。

用法: python dev/shot.py [main|briefing|editor|settings|all]
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "demo")

from ddlwidget.sysutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QLinearGradient, QPainter, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

qapp = QApplication(sys.argv)
qapp.setStyle("Fusion")

# 离屏平台不会自动加载系统字体，手动注册以便预览与实机一致
from PySide6.QtGui import QFontDatabase  # noqa: E402

if sys.platform.startswith("win"):
    for _font in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf", "seguisb.ttf", "SegoeIcons.ttf"):
        QFontDatabase.addApplicationFont("C:/Windows/Fonts/" + _font)
elif sys.platform == "darwin":
    for _font in ("/System/Library/Fonts/PingFang.ttc", "/System/Library/Fonts/HelveticaNeue.ttc"):
        if Path(_font).exists():
            QFontDatabase.addApplicationFont(_font)

from ddlwidget import paths  # noqa: E402
from ddlwidget.briefing import BriefingDialog  # noqa: E402
from ddlwidget.db import Database  # noqa: E402
from ddlwidget.dialogs import EditorDialog, SettingsDialog  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402
from ddlwidget.sync import pending_for_briefing  # noqa: E402

SHOTS = ROOT / "dev" / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)


_DB: Database | None = None


def reset_db() -> Database:
    global _DB
    if _DB is None:
        _DB = Database()
    with _DB._lock:
        _DB._conn.execute("DELETE FROM ddl")
        _DB._conn.execute("DELETE FROM meta")
        _DB._conn.commit()
    return _DB


def seed(db: Database) -> None:
    now = datetime.now()

    def at(delta: timedelta) -> datetime:
        value = (now + delta).replace(second=0, microsecond=0)
        return value

    db.upsert_synced("f4f30444c7485d49", "第三次作业", "计算概论A", at(timedelta(hours=3, minutes=25)), False)
    db.upsert_synced("9c1a7f30b2e54d18", "实验二：进程调度", "操作系统", at(timedelta(hours=27)), False)
    db.upsert_synced("1a2b3c4d5e6f7a8b", "大作业（含报告）", "数据结构与算法", at(timedelta(days=3, hours=2)), False)
    db.upsert_synced("2b3c4d5e6f7a8b9c", "读书报告", "大学英语", at(timedelta(days=6, hours=5)), False)
    db.upsert_synced("3c4d5e6f7a8b9c0d", "期中复习提纲", "线性代数", at(timedelta(days=12)), False)
    db.upsert_synced("4d5e6f7a8b9c0d1e", "第一次作业", "计算概论A", at(timedelta(days=-2)), False)
    db.upsert_synced("5e6f7a8b9c0d1e2f", "实验一", "操作系统", at(timedelta(days=-6)), True)

    db.add_manual("找导师签字确认开题", "毕业论文", at(timedelta(hours=20)))
    db.add_manual("提交奖学金材料", "个人事务", None)
    db.set_meta("last_sync_at", now.replace(microsecond=0).isoformat(sep="T"))
    db.set_meta("last_sync_ok", "1")


def wallpaper(width: int, height: int) -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor(38, 46, 74))
    grad.setColorAt(0.45, QColor(28, 34, 56))
    grad.setColorAt(1.0, QColor(18, 21, 34))
    painter.fillRect(0, 0, width, height, grad)

    glow = QRadialGradient(width * 0.24, height * 0.16, width * 0.62)
    glow.setColorAt(0.0, QColor(96, 122, 220, 78))
    glow.setColorAt(1.0, QColor(96, 122, 220, 0))
    painter.fillRect(0, 0, width, height, glow)

    glow2 = QRadialGradient(width * 0.86, height * 0.88, width * 0.5)
    glow2.setColorAt(0.0, QColor(150, 92, 190, 60))
    glow2.setColorAt(1.0, QColor(150, 92, 190, 0))
    painter.fillRect(0, 0, width, height, glow2)
    painter.end()
    return image


def compose(widget, name: str, pad: int = 48) -> None:
    widget.show()
    for _ in range(6):
        qapp.processEvents()
    pixmap = widget.grab()
    canvas = wallpaper(pixmap.width() + pad * 2, pixmap.height() + pad * 2)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(pad, pad, pixmap)
    painter.end()
    out = SHOTS / f"{name}.png"
    canvas.save(str(out))
    print(f"saved {out}  ({canvas.width()}x{canvas.height()})")


def shot_main() -> None:
    db = reset_db()
    seed(db)
    settings = Settings()
    settings.set("always_on_top", True, save=False)
    window = MainWindow(db, settings)
    compose(window, "main")


def shot_main_done() -> None:
    db = reset_db()
    seed(db)
    settings = Settings()
    settings.set("show_completed", True, save=False)
    window = MainWindow(db, settings)
    window.show()
    for _ in range(4):
        qapp.processEvents()
    bar = window._scroll.verticalScrollBar()
    bar.setValue(bar.maximum())
    for _ in range(4):
        qapp.processEvents()
    compose(window, "main_done")


def shot_briefing() -> None:
    db = reset_db()
    seed(db)
    items = pending_for_briefing(db, days=7)
    dialog = BriefingDialog(items, None)
    dialog.adjustSize()
    compose(dialog, "briefing", pad=60)


def shot_editor() -> None:
    db = reset_db()
    seed(db)
    item = next(i for i in db.all_items() if i.title == "第三次作业")
    dialog = EditorDialog(item, None)
    dialog.adjustSize()
    compose(dialog, "editor", pad=56)


def shot_settings() -> None:
    db = reset_db()
    settings = Settings()
    dialog = SettingsDialog(settings, None)
    dialog.adjustSize()
    compose(dialog, "settings", pad=56)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("main", "all"):
        shot_main()
    if mode in ("done", "all"):
        shot_main_done()
    if mode in ("briefing", "all"):
        shot_briefing()
    if mode in ("editor", "all"):
        shot_editor()
    if mode in ("settings", "all"):
        shot_settings()
