"""在真实 Windows 平台上渲染一张截图（会短暂显示窗口）。"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

print("stripped from PATH:", sanitize_dll_path())
os.environ.setdefault("DDL_WIDGET_DATA", str(ROOT / ".tmp" / "demo"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from ddlwidget.db import Database  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402

window = MainWindow(Database(), Settings())
window.show()


def snap() -> None:
    pixmap = window.grab()
    out = ROOT / "dev" / "shots" / "live.png"
    pixmap.save(str(out))
    print("saved", out, pixmap.width(), "x", pixmap.height(), "dpr", window.devicePixelRatioF())
    app.quit()


QTimer.singleShot(1500, snap)
sys.exit(app.exec())
