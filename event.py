import threading
import win32con
from ctypes import wintypes
from ctypes import windll
user32 = windll.user32


class Event:

    def stop_loop(self):
        tid = wintypes.DWORD(threading.current_thread().ident)
        msg = wintypes.UINT(win32con.WM_QUIT)
        wparam = wintypes.WPARAM(0)
        lparam = wintypes.LPARAM(0)
        res = user32.PostThreadMessageW(tid, msg, wparam, lparam)
        assert res

    def __init__(self, event_callback: dict) -> None:
        self.event_callback = event_callback
