import time
import win32gui

while True:
    print(f'{str(win32gui.GetCursorPos()): <20}\r', end='')
    time.sleep(0.1)
