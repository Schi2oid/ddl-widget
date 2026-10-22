"""按标题查找顶层窗口，用于验证应用真的起来了。"""

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

found = []


def callback(hwnd, _lparam):
    length = user32.GetWindowTextLengthW(hwnd)
    if length:
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        if "DDL" in title or "作业截止日" in title:
            visible = bool(user32.IsWindowVisible(hwnd))
            found.append((hwnd, title, visible))
    return True


user32.EnumWindows(EnumWindowsProc(callback), 0)
for hwnd, title, visible in found:
    print(f"hwnd=0x{hwnd:08X} visible={visible} title={title!r}")
print("count:", len(found))
