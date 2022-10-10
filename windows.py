from ctypes import *
from ctypes import windll
from ctypes import wintypes
from cjutils.utils import *
import win32gui
import win32con

user32 = windll.user32
ole32 = windll.ole32
kernel32 = windll.kernel32
dwmapi = windll.dwmapi


class WINDOWPLACEMENT(Structure):
    # https://learn.microsoft.com/zh-cn/windows/win32/api/winuser/ns-winuser-windowplacement
    _fields_ = [
        ("length", wintypes.UINT),
        ("flags", wintypes.UINT),
        ("showCmd", wintypes.UINT),
        ("ptMinPosition", wintypes.POINT),
        ("ptMaxPosition", wintypes.POINT),
        ("rcNormalPosition", wintypes.RECT),
        ("rcDevice", wintypes.RECT),
    ]


class WindowInfo:
    def __init__(self, hwnd=None, file_name='', showCmd=0, rectangle=(0, 0, 0, 0), title='', process_id=-1) -> None:
        self.hwnd = hwnd
        self.file_name = file_name
        self.showCmd = showCmd
        self.rectangle = rectangle
        self.title = title
        self.process_id = process_id

    def __repr__(self):
        return f'{self.process_id: <10}{self.hwnd: <10}{self.showCmd: <5}{str(self.rectangle): <30}{self.title[:30]: <50}{self.file_name}'


class WindowsHook:
    def __callback(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread,
                   dwmsEventTime):
        if event in self.listenEvents_dict:
            self.listenEvents_dict[event](hwnd, event)

    def __setHook(self, WinEventProc, eventType):
        return user32.SetWinEventHook(
            eventType,
            eventType,
            0,
            WinEventProc,
            0,
            0,
            win32con.WINEVENT_OUTOFCONTEXT
        )

    def __init__(self, listenEvents=[]) -> None:
        # https://gist.github.com/keturn/6695625
        self.WinEventProcType = WINFUNCTYPE(
            None,
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.HWND,
            wintypes.LONG,
            wintypes.LONG,
            wintypes.DWORD,
            wintypes.DWORD
        )

        # The types of events we want to listen for, and the names we'll use for
        # them in the log output. Pick from
        # http://msdn.microsoft.com/en-us/library/windows/desktop/dd318066(v=vs.85).aspx
        self.eventTypes = {
            win32con.EVENT_SYSTEM_FOREGROUND: "Foreground",
            win32con.EVENT_SYSTEM_MOVESIZEEND: "Move",
            win32con.EVENT_OBJECT_LOCATIONCHANGE: "LocationChange",
            win32con.WM_HOTKEY: "Hotkey",
            win32con.EVENT_OBJECT_FOCUS: "Focus",
            win32con.EVENT_OBJECT_SHOW: "Show",
            win32con.EVENT_SYSTEM_DIALOGSTART: "Dialog",
            win32con.EVENT_SYSTEM_CAPTURESTART: "Capture",
            win32con.EVENT_SYSTEM_MINIMIZEEND: "MinimizeEnd",
            win32con.EVENT_SYSTEM_MINIMIZESTART: "MinimizeStart"
        }
        # limited information would be sufficient, but our platform doesn't have it.
        self.processFlag = getattr(win32con, 'PROCESS_QUERY_LIMITED_INFORMATION',
                                   win32con.PROCESS_QUERY_INFORMATION)
        self.listenEvents_dict = {}
        for event, callback in listenEvents:
            assert event in self.eventTypes
            self.listenEvents_dict[event] = callback
        self.WinEventProc = self.WinEventProcType(self.__callback)
        user32.SetWinEventHook.restype = wintypes.HANDLE

        hookIDs = [self.__setHook(self.WinEventProc, et)
                   for et in self.listenEvents_dict.keys()]
        assert any(hookIDs)

    def getProcessFilename(self, processID):
        hProcess = kernel32.OpenProcess(self.processFlag, 0, processID)
        if not hProcess:
            err("OpenProcess(%s) failed: %s" %
                (processID, WinError()))
            return None

        try:
            filenameBufferSize = wintypes.DWORD(4096)
            filename = create_unicode_buffer(filenameBufferSize.value)
            kernel32.QueryFullProcessImageNameW(hProcess, 0, byref(filename),
                                                byref(filenameBufferSize))

            return filename.value
        finally:
            kernel32.CloseHandle(hProcess)

    def get_window_rect(self, hwnd):
        # https://blog.csdn.net/See_Star/article/details/103940462
        rect = wintypes.RECT()
        DWMWA_EXTENDED_FRAME_BOUNDS = 9
        dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(DWMWA_EXTENDED_FRAME_BOUNDS),
            byref(rect),
            sizeof(rect)
        )
        return rect.left, rect.top, rect.right, rect.bottom

    def get_window_info(self, hwnd):
        processID = wintypes.DWORD()
        user32.GetWindowThreadProcessId(
            hwnd, byref(processID))
        if not processID:
            err(f'get window processID failed hwnd:{hwnd}')
            assert False
        file_name = self.getProcessFilename(processID)
        process_id = processID.value
        length = user32.GetWindowTextLengthW(hwnd)
        title = create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        title_value = title.value
        # rect = win32gui.GetWindowRect(hwnd)
        # https://stackoverflow.com/questions/3192232/getwindowrect-too-small-on-windows-7
        rect = self.get_window_rect(hwnd)

        data = WINDOWPLACEMENT()
        user32.GetWindowPlacement(hwnd, byref(data))
        return WindowInfo(hwnd, file_name, data.showCmd, rect, title_value, process_id)


if __name__ == '__main__':
    from loop import EventLoop
    from keyboard import AnyKey
    info('press right alt to exit')

    def foreground_callback(hwnd):
        '''
        File "_ctypes/callbacks.c"
        result = PyObject_Vectorcall(callable, args, nargs, NULL);
        if (result == NULL) {
            _PyErr_WriteUnraisableMsg("on calling ctypes callback function",
                                    callable);
        }
        '''
        # any exception cannot be catched in callback !!!
        # try:
        #     raise KeyboardInterrupt
        # except Exception as e:
        #     print(e)
        info(wh.get_window_info(hwnd))
    a = AnyKey()

    wh = WindowsHook(
        listenEvents=[
            (win32con.EVENT_SYSTEM_FOREGROUND, foreground_callback),
            (win32con.EVENT_SYSTEM_MOVESIZEEND, foreground_callback)
        ]
    )
    el = EventLoop()
    el.start()

    # limited information would be sufficient, but our platform doesn't have it.
    # self.processFlag = getattr(win32con, 'PROCESS_QUERY_LIMITED_INFORMATION',
    #                            win32con.PROCESS_QUERY_INFORMATION)

    # self.threadFlag = getattr(win32con, 'THREAD_QUERY_LIMITED_INFORMATION',
    #                           win32con.THREAD_QUERY_INFORMATION)

    # # store last event time for displaying time between events
    # self.lastTime = 0

    # self.event_queue = Queue()

    # def getProcessID(self, dwEventThread, hwnd):
    #     # It's possible to have a window we can get a PID out of when the thread
    #     # isn't accessible, but it's also possible to get called with no window,
    #     # so we have two approaches.

    #     hThread = self.kernel32.OpenThread(self.threadFlag, 0, dwEventThread)

    #     if hThread:
    #         try:
    #             processID = self.kernel32.GetProcessIdOfThread(hThread)
    #             if not processID:
    #                 self.error("Couldn't get process for thread %s: %s" %
    #                            (hThread, ctypes.WinError()))
    #         finally:
    #             self.kernel32.CloseHandle(hThread)
    #     else:
    #         errors = ["No thread handle for %s: %s" %
    #                   (dwEventThread, ctypes.WinError(),)]

    #         if hwnd:
    #             processID = ctypes.wintypes.DWORD()
    #             threadID = self.user32.GetWindowThreadProcessId(
    #                 hwnd, ctypes.byref(processID))
    #             if threadID != dwEventThread:
    #                 self.error("Window thread != event thread? %s != %s" %
    #                            (threadID, dwEventThread))
    #             if processID:
    #                 processID = processID.value
    #             else:
    #                 errors.append(
    #                     "GetWindowThreadProcessID(%s) didn't work either: %s" % (
    #                         hwnd, ctypes.WinError()))
    #                 processID = None
    #         else:
    #             processID = None

    #         if not processID:
    #             for err in errors:
    #                 self.error(err)

    #     return processID

    # def callback(self, hWinEventHook, event, hwnd, idObject, idChild, dwEventThread,
    #              dwmsEventTime):
    #     # length = self.user32.GetWindowTextLengthW(hwnd)
    #     # title = ctypes.create_unicode_buffer(length + 1)
    #     # self.user32.GetWindowTextW(hwnd, title, length + 1)

    #     # processID = self.getProcessID(dwEventThread, hwnd)

    #     # shortName = '?'
    #     # if processID:
    #     #     filename = self.getProcessFilename(processID)
    #     #     if filename:
    #     #         shortName = '\\'.join(filename.rsplit('\\', 2)[-2:])

    #     # # if hwnd:
    #     # #     hwnd = hex(hwnd)
    #     # if idObject == win32con.OBJID_CURSOR:
    #     #     hwnd = '<Cursor>'

    #     # # info(u"%s:%04.2f\t%-10s\t"
    #     # #      u"W:%-8s\tP:%-8d\tT:%-8d\t"
    #     # #      u"%s\t%s" % (
    #     # #          dwmsEventTime, float(
    #     # #              dwmsEventTime - self.lastTime) / 1000, self.eventTypes.get(event, hex(event)),
    #     # #          hwnd, processID or -1, dwEventThread or -1,
    #     # #          shortName, title.value))
    #     # d = (hwnd, self.eventTypes.get(event, hex(event)), filename)
    #     # # info(*d)
    #     # self.event_queue.put(d)

    #     # self.lastTime = dwmsEventTime
    #     pass

    # def __run(self):
    #     self.ole32.CoInitialize(0)

    #     WinEventProc = self.WinEventProcType(self.callback)
    #     self.user32.SetWinEventHook.restype = ctypes.wintypes.HANDLE

    #     hookIDs = [self.setHook(WinEventProc, et)
    #                for et in self.eventTypes.keys()]
    #     if not any(hookIDs):
    #         sys.exit(1)

    #     msg = ctypes.wintypes.MSG()
    #     while self.user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0 and self.running:
    #         self.user32.TranslateMessageW(msg)
    #         self.user32.DispatchMessageW(msg)

    #     for hookID in hookIDs:
    #         self.user32.UnhookWinEvent(hookID)
    #     self.ole32.CoUninitialize()

    # def start(self):
    #     self.running = True
    #     _thread.start_new_thread(self.__run, ())

    # def stop(self):
    #     self.running = False

    # def get_event(self):
    #     # wait until window event happend
    #     return self.event_queue.get(block=self.running)
