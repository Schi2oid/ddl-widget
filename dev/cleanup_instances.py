"""列出占用 DDL 窗口的进程，并只终止最近 N 秒内启动的（我自己的测试实例）。"""

import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
PROCESS_TERMINATE = 0x0001


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


def filetime_to_int(ft: FILETIME) -> int:
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


windows = []


def cb(hwnd, _l):
    length = user32.GetWindowTextLengthW(hwnd)
    if not length:
        return True
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    if "DDL" not in buf.value:
        return True
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    windows.append((hwnd, pid.value, buf.value))
    return True


user32.EnumWindows(EnumProc(cb), 0)

age_limit = float(sys.argv[1]) if len(sys.argv) > 1 else 180.0
now_ft = FILETIME()
kernel32.GetSystemTimeAsFileTime(ctypes.byref(now_ft))
now = filetime_to_int(now_ft)

print("now_ft =", now)
for hwnd, pid, title in windows:
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    age = None
    if handle:
        created, exited, kernel_t, user_t = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel_t), ctypes.byref(user_t)
        ):
            age = (now - filetime_to_int(created)) / 1e7
        kernel32.CloseHandle(handle)
    print(f"hwnd=0x{hwnd:08X} pid={pid} age={age if age is None else round(age)}s {title!r}")

    if age is not None and age < age_limit:
        term = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if term:
            ok = kernel32.TerminateProcess(term, 0)
            kernel32.CloseHandle(term)
            print(f"   -> terminated (age {age:.1f}s) ok={ok}")
        else:
            print("   -> open for terminate failed")
extra = [w for w in sys.argv[2:]]
for pid_text in extra:
    pid = int(pid_text)
    term = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if term:
        print(f"   -> terminated pid {pid} ok={kernel32.TerminateProcess(term, 0)}")
        kernel32.CloseHandle(term)
