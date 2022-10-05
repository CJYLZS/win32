import win32gui
import win32con
from cjutils.utils import *
from ctypes import *
from ctypes import wintypes
from ctypes import windll

user32 = windll.user32
kernel32 = windll.kernel32


class KeyCode(dict):
    def __set_vcode(self, vkCode, keyName):
        self.vkCode_Key[vkCode] = keyName
        self.__dict__[keyName] = vkCode

    def __init__(self) -> None:
        self['a'] = 1
        self.vkCode_Key = {}
        for i in range(26):
            self.__set_vcode(
                vkCode=65 + i, keyName=c_char(97 + i).value.decode())
        self.__set_vcode(8, 'backspace')
        self.__set_vcode(13, 'enter')
        self.__set_vcode(27, 'esc')
        self.__set_vcode(32, 'space')
        self.__set_vcode(160, 'lshift')
        self.__set_vcode(161, 'rshift')
        self.__set_vcode(162, 'lctrl')
        self.__set_vcode(163, 'lctrl')
        self.__set_vcode(164, 'lalt')
        self.__set_vcode(165, 'ralt')


keycode = KeyCode()


class KBDLLHOOKSTRUCT(Structure):
    # https://learn.microsoft.com/zh-cn/windows/win32/api/winuser/ns-winuser-kbdllhookstruct
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", POINTER(wintypes.ULONG))
    ]


class Event:
    def __init__(self, event_callback: dict) -> None:
        self.event_callback = event_callback


class AnyKey(Event):
    actions = {
        256:'down',
        260:'down',
        257:'up'
    }
    def __log(self, wParam, lParam):
        kbdllhook = cast(lParam, POINTER(KBDLLHOOKSTRUCT)).contents
        info(f'{self.actions.get(wParam, wParam): <5}key: {keycode.vkCode_Key.get(kbdllhook.vkCode, kbdllhook.vkCode): <5}')

    def __callback(self, nCode, wParam, lParam):
        self.__log(wParam, lParam)
        kbdllhook = cast(lParam, POINTER(KBDLLHOOKSTRUCT)).contents
        if kbdllhook.vkCode == keycode.esc:
            sys.exit(0)
        return user32.CallNextHookEx(0, nCode, wParam, lParam)

    def __init__(self) -> None:
        super().__init__(event_callback={})
        user32.SetWindowsHookExW.restype = wintypes.LONG
        user32.SetWindowsHookExW.argtypes = [
            c_int, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.DWORD]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        callback_type = WINFUNCTYPE(
            c_long,
            c_int,
            c_uint,
            POINTER(wintypes.LPARAM)
        )  # https://learn.microsoft.com/zh-cn/previous-versions/windows/desktop/legacy/ms644985(v=vs.85)
        # callback_ptr can't use local variable either gc will clean this ptr!! process will crash!!
        self.__callback_ptr = callback_type(self.__callback)
        user32.SetWindowsHookExW(
            win32con.WH_KEYBOARD_LL,
            self.__callback_ptr,
            kernel32.GetModuleHandleW(None),
            0
        )


class HotKey(Event):
    def __RegisterHotKey(self, args: tuple, callback):
        '''
            BOOL WINAPI RegisterHotKey(
                __in_opt HWND hWnd,
                __in int id,
                __in UINT fsModifiers,
                __in UINT vk
            );
        '''
        win32gui.RegisterHotKey(args[0], args[1], args[2], args[3])
        self.registered_keys[(args[2], args[3])] = callback

    def callback(self, msg: wintypes.MSG):
        mod = msg.lParam & 0b1111111111111111
        key = msg.lParam >> 16
        self.registered_keys[(mod, key)]()

    def __init__(self, hot_keys=()):
        super().__init__(event_callback={
            win32con.WM_HOTKEY: self.callback
        })
        self.keycode = KeyCode()
        self.registered_keys = {}
        for hwnd, id, fsModifiers, vk, callback in hot_keys:
            self.__RegisterHotKey((hwnd, id, fsModifiers, vk), callback)

    def __del__(self):
        windll.user32.UnregisterHotKey(None, 1)


class EventLoop:
    def __init__(self, objs=[]) -> None:
        self.running_state = ''
        self.event_callback = {}
        for obj in objs:
            assert isinstance(obj, Event), "obj must is instance of Event"
            for event, callback in obj.event_callback.items():
                self.event_callback[event] = callback

    def stop(self):
        self.running_state = ''

    def start(self):
        self.running_state = 'running'
        msg = wintypes.MSG()
        while user32.GetMessageW(byref(msg), 0, 0, 0) != 0 and self.running_state == 'running':
            if msg.message in self.event_callback.keys():
                self.event_callback[msg.message](msg)
            user32.TranslateMessage(msg)
            user32.DispatchMessageW(msg)


if __name__ == '__main__':
    info(cyan('global logging key press esc exit'))
    def hello():
        info('hello')
    keycode = KeyCode()
    hotkey = HotKey(
        hot_keys=(
            (0, 0, win32con.MOD_ALT, keycode.h, hello),
        )
    )
    a = AnyKey()
    eventloop = EventLoop(objs=[hotkey])
    eventloop.start()
