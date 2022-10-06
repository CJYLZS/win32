import win32gui
import win32con
from ctypes import *
from ctypes import wintypes
from ctypes import windll

from cjutils.utils import *
from event import Event
from loop import EventLoop

user32 = windll.user32
kernel32 = windll.kernel32


class KeyCode(dict):
    def __set_vcode(self, vkCode, keyName):
        self.vkCode_Key[vkCode] = keyName
        self.__dict__[keyName] = vkCode
        self[keyName] = vkCode

    def __init__(self) -> None:
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


class AnyKey(Event):
    # use SetWindowsHookEx hook all keys event
    actions = {
        256: 'down',
        260: 'down',
        257: 'up'
    }
    downs = (256, 260)
    ups = (257, 261)

    def __log(self, wParam, lParam):
        kbdllhook = cast(lParam, POINTER(KBDLLHOOKSTRUCT)).contents
        info(f'{self.actions.get(wParam, wParam): <5}key: {keycode.vkCode_Key.get(kbdllhook.vkCode, kbdllhook.vkCode): <5}')

    def __handle_hotkey(self):
        eat = False
        for hotkey in self.__hotkeys:
            values = self.__hotkeys[hotkey]  # shallow copy
            # deep copy
            onHotKeyDown, onHotKeyUp, status, lastActivate, timeout = self.__hotkeys[hotkey]
            activate = True
            for vkCode in hotkey:
                activate = activate and self.__keys_state_map[vkCode]
            if activate:
                if time.time() - lastActivate > timeout:
                    values[2] = True
                    values[3] = time.time()
                    eat = True
                    onHotKeyDown()
            elif status:
                values[2] = False
                onHotKeyUp()
        return eat

    def __callback(self, nCode, wParam, lParam):
        # ctype callback !!
        # self.__log(wParam, lParam)
        kbdllhook = cast(lParam, POINTER(KBDLLHOOKSTRUCT)).contents
        if kbdllhook.vkCode == keycode.ralt:
            sys.exit(0)
        if wParam in self.downs:
            self.__keys_state_map[kbdllhook.vkCode] = True
        elif wParam in self.ups:
            self.__keys_state_map[kbdllhook.vkCode] = False

        eat = self.__handle_hotkey()
        if eat:
            user32.CallNextHookEx(0, win32con.HC_SKIP, wParam, lParam)
            return win32con.HC_SKIP
        return user32.CallNextHookEx(0, nCode, wParam, lParam)

    def register_hotkey(self, keys: tuple, onHotKeyDown, onHotKeyUp, timeout=0.5):
        # onHotKeyDown and onHotKeyUp cannot use python catch exceptions
        '''
        File "_ctypes/callbacks.c"
        result = PyObject_Vectorcall(callable, args, nargs, NULL);
        if (result == NULL) {
            _PyErr_WriteUnraisableMsg("on calling ctypes callback function",
                                    callable);
        }
        '''
        # any exception cannot be catched in callback !!!
        vkCodes = tuple([keycode[key] for key in keys])
        # down up activating last_activate timeout
        self.__hotkeys[vkCodes] = [onHotKeyDown, onHotKeyUp, False, 0, timeout]

    def __init__(self) -> None:
        super().__init__(event_callback={})
        self.__hotkeys = {}
        self.__keys_state_map = {}
        for _, vkCode in keycode.items():
            self.__keys_state_map[vkCode] = False
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
    # RegisterHotKey can't use key up callback
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

    def __callback(self, msg: wintypes.MSG):
        mod = msg.lParam & 0b1111111111111111
        key = msg.lParam >> 16
        self.registered_keys[(mod, key)]()

    def __init__(self, hot_keys=()):
        super().__init__(event_callback={
            win32con.WM_HOTKEY: self.__callback
        })
        self.keycode = KeyCode()
        self.registered_keys = {}
        for hwnd, id, fsModifiers, vk, callback in hot_keys:
            self.__RegisterHotKey((hwnd, id, fsModifiers, vk), callback)

    def __del__(self):
        windll.user32.UnregisterHotKey(None, 1)


if __name__ == '__main__':
    def activate():
        info('activate')

    def deactivate():
        info('deactivate')
    # keycode = KeyCode()
    # hotkey = HotKey(
    #     hot_keys=(
    #         (0, 0, win32con.MOD_ALT, keycode.h, activate),
    #     )
    # )
    a = AnyKey()
    a.register_hotkey(('lalt', 'h'), activate, deactivate, timeout=0)
    eventloop = EventLoop(objs=[])
    eventloop.start()
