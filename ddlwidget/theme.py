"""视觉主题：配色、字体、图标字形。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

# --- 文字 -------------------------------------------------------------
TEXT_PRIMARY = "#EAEDF7"
TEXT_SECONDARY = "#A6ADC4"
TEXT_TERTIARY = "#707691"
TEXT_DISABLED = "#4E5468"

# --- 强调色 -----------------------------------------------------------
ACCENT = "#7C8CFF"
ACCENT_SOFT = "#9AA6FF"
ACCENT_DEEP = "#5B6BE8"
VIOLET = "#A78BFA"

# --- 分组色 -----------------------------------------------------------
RED = "#FF5C6B"
RED_DEEP = "#F0455A"
AMBER = "#FFB35C"
BLUE = "#5CACFF"
SLATE = "#7C87A8"
GREEN = "#4ADE80"

# --- 背景 -------------------------------------------------------------
CARD_TOP = (30, 32, 44)
CARD_BOTTOM = (16, 17, 25)
BORDER = QColor(255, 255, 255, 22)
BORDER_STRONG = QColor(255, 255, 255, 34)
SHADOW = QColor(0, 0, 0, 160)

RADIUS = 18

# --- 字体 -------------------------------------------------------------
import sys as _sys

if _sys.platform == "darwin":
    UI_FAMILIES = ["SF Pro Text", "PingFang SC", "Helvetica Neue"]
elif _sys.platform.startswith("win"):
    UI_FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI"]
else:
    UI_FAMILIES = ["Noto Sans CJK SC", "DejaVu Sans"]


def font(size: int, weight: int = 400, letter_spacing: float = 0.0) -> QFont:
    f = QFont()
    f.setFamilies(UI_FAMILIES)
    f.setPixelSize(size)
    f.setWeight(QFont.Weight(weight))
    if letter_spacing:
        f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, letter_spacing)
    return f


def rgba(hex_color: str, alpha: float) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


MENU_QSS = """
QMenu {
    background-color: #1B1D27;
    border: 1px solid rgba(255,255,255,28);
    border-radius: 10px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 24px 7px 14px;
    border-radius: 7px;
    margin: 1px 2px;
    color: #CBD0E0;
}
QMenu::item:selected {
    background-color: rgba(124,140,255,0.22);
    color: #FFFFFF;
}
QMenu::item:disabled { color: #5A6076; }
QMenu::separator {
    height: 1px;
    background: rgba(255,255,255,16);
    margin: 5px 10px;
}
"""

DIALOG_QSS = """
QWidget { color: #DDE1EE; }
QLabel#fieldLabel { color: #8B93AC; font-size: 11px; }
QLabel#hint { color: #666D84; font-size: 11px; }
QLabel#error { color: #FF7A86; font-size: 11px; }
QLabel#dialogTitle { color: #F2F4FB; font-size: 15px; font-weight: 700; }
QLabel#sectionTitle { color: #7E87A2; font-size: 10px; font-weight: 700; letter-spacing: 1px; }

QLineEdit, QDateTimeEdit, QComboBox {
    background: rgba(255,255,255,11);
    border: 1px solid rgba(255,255,255,24);
    border-radius: 8px;
    padding: 7px 10px;
    color: #EAEDF7;
    selection-background-color: rgba(124,140,255,120);
    min-height: 18px;
}
QLineEdit:focus, QDateTimeEdit:focus, QComboBox:focus {
    border: 1px solid rgba(124,140,255,180);
    background: rgba(255,255,255,17);
}
QLineEdit::placeholder { color: #565C72; }
QDateTimeEdit::drop-down, QComboBox::drop-down {
    border: none; width: 26px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}
QDateTimeEdit::down-arrow, QComboBox::down-arrow {
    image: {CHEVRON_URL};
    width: 13px; height: 13px;
}
QComboBox QAbstractItemView {
    background: #1B1D27;
    border: 1px solid rgba(255,255,255,28);
    border-radius: 8px;
    padding: 4px;
    selection-background-color: rgba(124,140,255,0.22);
    outline: none;
}

QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8794FF, stop:1 #9B7BFF);
    color: #FFFFFF; border: none; border-radius: 9px;
    padding: 9px 20px; font-weight: 600; font-size: 12px;
}
QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #95A1FF, stop:1 #A98CFC);
}
QPushButton#primary:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7381F2, stop:1 #8A6BEF);
}
QPushButton#ghost {
    background: rgba(255,255,255,10); color: #C3C9DC;
    border: 1px solid rgba(255,255,255,20); border-radius: 9px;
    padding: 9px 18px; font-size: 12px;
}
QPushButton#ghost:hover { background: rgba(255,255,255,18); color: #FFFFFF; }
QPushButton#danger {
    background: rgba(255,92,107,0.12); color: #FF8C97;
    border: 1px solid rgba(255,92,107,0.24); border-radius: 9px;
    padding: 9px 14px; font-size: 12px;
}
QPushButton#danger:hover { background: rgba(255,92,107,0.2); }
QPushButton#chip {
    background: rgba(255,255,255,9); color: #9AA2BA;
    border: none; border-radius: 12px; padding: 5px 11px; font-size: 11px;
}
QPushButton#chip:hover { background: rgba(124,140,255,0.22); color: #EAEDF7; }

QSlider::groove:horizontal {
    height: 3px; background: rgba(255,255,255,22); border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8794FF, stop:1 #A78BFA);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #FFFFFF; width: 12px; height: 12px;
    margin: -5px 0; border-radius: 6px;
}

QCalendarWidget QWidget { background-color: #1B1D27; color: #DDE1EE; }
QCalendarWidget QWidget#qt_calendar_navigationbar { background-color: #22242F; }
QCalendarWidget QToolButton {
    color: #DDE1EE; background: transparent; border: none;
    padding: 4px 8px; font-size: 12px;
}
QCalendarWidget QToolButton:hover { background: rgba(255,255,255,20); border-radius: 6px; }
QCalendarWidget QAbstractItemView:enabled {
    background-color: #171922; color: #C8CEDF;
    selection-background-color: #7C8CFF; selection-color: #FFFFFF;
    outline: none;
}
QCalendarWidget QAbstractItemView:disabled { color: #4E5468; }
QCalendarWidget QSpinBox { background: #22242F; color: #DDE1EE; border: none; }
"""


def dialog_qss() -> str:
    """注入运行时生成的下拉箭头图片路径。"""
    from .icons import chevron_down_path

    return DIALOG_QSS.replace("{CHEVRON_URL}", "url(" + chevron_down_path() + ")")


def paint_dialog_bg(painter, width: int, height: int, shadow: int, radius: int, opacity: float = 1.0) -> None:
    """对话框共用的阴影 + 玻璃卡片。"""
    from PySide6.QtCore import QRectF
    from PySide6.QtGui import QLinearGradient, QPainterPath, QPen

    card = QRectF(shadow, shadow, width - shadow * 2, height - shadow * 2)
    steps = 14
    for i in range(steps, 0, -1):
        frac = i / steps
        alpha = int(30 * (1.0 - frac) ** 2.0) + 1
        pad = i * 0.8
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.drawRoundedRect(card.adjusted(-pad, -pad + 5, pad, pad + 5), radius + pad, radius + pad)

    path = QPainterPath()
    path.addRoundedRect(card, radius, radius)
    alpha = int(255 * max(0.4, min(1.0, opacity)))
    grad = QLinearGradient(card.topLeft(), card.bottomLeft())
    grad.setColorAt(0.0, QColor(31, 33, 45, alpha))
    grad.setColorAt(1.0, QColor(18, 19, 27, alpha))
    painter.fillPath(path, grad)

    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(255, 255, 255, 26), 1))
    painter.drawRoundedRect(card.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)


def mix(a: str, b: str, t: float) -> QColor:
    ca, cb = QColor(a), QColor(b)
    return QColor(
        int(ca.red() + (cb.red() - ca.red()) * t),
        int(ca.green() + (cb.green() - ca.green()) * t),
        int(ca.blue() + (cb.blue() - ca.blue()) * t),
    )
