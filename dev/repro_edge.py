"""验证贴边收纳：完全移出屏幕 + 边缘窄带触发 + 快速收起。"""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DDL_WIDGET_DATA"] = str(ROOT / ".tmp" / "edge")

from ddlwidget.winutil import sanitize_dll_path  # noqa: E402

sanitize_dll_path()

from PySide6.QtCore import QCoreApplication, QEvent, QPoint  # noqa: E402
from PySide6.QtGui import QCursor  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setStyle("Fusion")

from ddlwidget.db import Database  # noqa: E402
from ddlwidget.main_window import MainWindow  # noqa: E402
from ddlwidget.settings import Settings  # noqa: E402


def pump(ms: int = 320) -> None:
    end = time.monotonic() + ms / 1000.0
    while time.monotonic() < end:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        time.sleep(0.008)


settings = Settings()
settings.update(
    {"edge_dock_enabled": True, "edge_dock": "", "window_pos": [300, 200], "list_height": None}
)

window = MainWindow(Database(), settings)
window.show()
pump(300)
area = window._available_rect()
print("screen:", area.getRect(), " window:", window.width(), "x", window.height())

print("1) 拖到左边缘右侧 5px 处松手:")
window.move(area.left() + 5, 240)
window._on_move_settled()
pump()
print("   edge =", window._edge, " x =", window.x(), " 期望", area.left() - 22)

print("2) 鼠标移开 -> 收纳（应完全移出屏幕）:")
QCursor.setPos(700, 700)
window._collapse_now()
pump(500)
print("   collapsed =", window._collapsed, " x =", window.x(),
      " 右边界 =", window.x() + window.width(), " 屏幕左边界 =", area.left())
print("   完全在屏幕外:", window.x() + window.width() <= area.left())

print("3) 鼠标贴到屏幕左边缘 2px 处 -> 应自动展开:")
QCursor.setPos(area.left() + 2, 300)
print("   光标读回:", QCursor.pos().toTuple())
window._update_edge_state()
pump(400)
print("   collapsed =", window._collapsed, " x =", window.x(), " 期望", area.left() - 22)

print("4) 鼠标移到窗口外 -> 应收起:")
QCursor.setPos(700, 700)
window._update_edge_state()
print("   收起计时器运行中:", window._collapse_timer.isActive(),
      " 间隔 =", window._collapse_timer.interval(), "ms")
pump(500)
print("   collapsed =", window._collapsed, " x =", window.x())

print("5) 鼠标离边缘 8px（超出 5px 感应带）-> 不应展开:")
QCursor.setPos(area.center())
QCursor.setPos(area.left() + 8, 300)
window._update_edge_state()
pump(400)
print("   collapsed =", window._collapsed, " (应为 True)")

print("7) 模拟 Win+D 最小化后贴边唤起:")
window.move(window._dock_x("left", True), 300)
window._collapsed = True
from PySide6.QtCore import Qt  # noqa: E402

window.setWindowState(window.windowState() | Qt.WindowState.WindowMinimized)
pump(200)
print("   最小化状态 =", window.isMinimized())
QCursor.setPos(area.left() + 2, 300)
window._update_edge_state()
pump(450)
print("   唤起后 isMinimized =", window.isMinimized(),
      " collapsed =", window._collapsed, " x =", window.x())

print("6) 鼠标在感应带内但在窗口垂直范围外 -> 不应展开:")
QCursor.setPos(area.left() + 2, window.y() - 200)
window._update_edge_state()
pump(400)
print("   collapsed =", window._collapsed, " (应为 True)")
