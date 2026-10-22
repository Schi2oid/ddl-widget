"""验证悬停提示：真实 Enter 事件驱动 -> 延时弹出 -> 离开收起。"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DDL_WIDGET_DATA", str(ROOT / ".tmp" / "demo"))

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtGui import QCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from ddlwidget import tips  # noqa: E402
from ddlwidget.db import Database  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402


def pump(ms: int) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


controller = tips.TipController(app)

window = MainWindow(Database(), Settings())
window.move(160, 120)
window.show()
pump(600)

row = window._rows[0]
print("row.toolTip():", repr(row.toolTip()))
QCursor.setPos(window.x() + 220, window.y() + 250)
pump(60)

print("1) 发送 Enter 事件（模拟鼠标进入）")
QApplication.sendEvent(row, QEvent(QEvent.Type.Enter))
print("   立刻可见?", controller._tip.isVisible(), "(应为 False，有 450ms 延时)")
pump(700)
print("   延时后可见?", controller._tip.isVisible(), " rect:", controller._tip.geometry().getRect())
controller._tip.grab().save(str(ROOT / "dev" / "shots" / "tip_row.png"))

print("2) 发送 Leave（鼠标离开）")
QApplication.sendEvent(row, QEvent(QEvent.Type.Leave))
pump(120)
print("   可见?", controller._tip.isVisible(), "(应为 False)")

print("3) 按钮悬停")
button = window._btn_reset
print("   button.toolTip():", repr(button.toolTip()))
QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))
pump(700)
print("   可见?", controller._tip.isVisible())
controller._tip.grab().save(str(ROOT / "dev" / "shots" / "tip_button.png"))

print("4) 原生 ToolTip 事件应被压制")
QApplication.sendEvent(row, QEvent(QEvent.Type.ToolTip))
pump(100)
print("   仍可见?", controller._tip.isVisible(), "(应保持 False，不再弹原生)")

print("5) 拖动条提示")
grip = window._grip
QApplication.sendEvent(grip, QEvent(QEvent.Type.Enter))
pump(700)
print("   可见?", controller._tip.isVisible())
controller._tip.grab().save(str(ROOT / "dev" / "shots" / "tip_grip.png"))
