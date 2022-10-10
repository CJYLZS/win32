from event import Event
from ctypes import windll, wintypes, byref
from cjutils.utils import *
user32 = windll.user32


class EventLoop(Event):
    def __init__(self, objs=[]) -> None:
        super().__init__()
        self.event_callback = {}
        for obj in objs:
            assert isinstance(obj, Event), "obj must is instance of Event"
            for event, callback in obj.event_callback.items():
                self.event_callback[event] = callback

    def start(self):
        msg = wintypes.MSG()
        user32.GetMessageW(byref(msg), 0, 0, 0)
