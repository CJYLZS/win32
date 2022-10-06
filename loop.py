from event import Event
from ctypes import windll, wintypes, byref
user32 = windll.user32


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
