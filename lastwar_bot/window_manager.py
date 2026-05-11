"""
Finds and manages the emulator window containing Last War: Survival.
Supports BlueStacks, LDPlayer, NoxPlayer, MuMu, and generic window titles.
"""

import ctypes
import ctypes.wintypes as wintypes
from dataclasses import dataclass
from typing import Optional

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EMULATOR_TITLES = [
    "BlueStacks",
    "BlueStacks App Player",
    "LDPlayer",
    "NoxPlayer",
    "MuMu Player",
    "Last War",
    "Last War: Survival",
]


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: int
    rect: tuple  # (left, top, right, bottom)

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]

    @property
    def center(self) -> tuple:
        return (
            self.rect[0] + self.width // 2,
            self.rect[1] + self.height // 2,
        )


class WindowManager:
    def __init__(self, target_titles: list[str] = None):
        self.target_titles = target_titles or EMULATOR_TITLES
        self._window: Optional[WindowInfo] = None

    def find_window(self) -> Optional[WindowInfo]:
        """Scans all open windows and returns the first matching emulator window."""
        found: list[WindowInfo] = []

        def enum_callback(hwnd, _):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            for t in self.target_titles:
                if t.lower() in title.lower():
                    pid = wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    found.append(WindowInfo(
                        hwnd=hwnd,
                        title=title,
                        pid=pid.value,
                        rect=(rect.left, rect.top, rect.right, rect.bottom),
                    ))
            return True

        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        user32.EnumWindows(EnumWindowsProc(enum_callback), 0)

        if found:
            self._window = found[0]
            return self._window
        return None

    def get_window(self) -> Optional[WindowInfo]:
        """Returns cached window or searches again."""
        if self._window and user32.IsWindow(self._window.hwnd):
            rect = wintypes.RECT()
            user32.GetWindowRect(self._window.hwnd, ctypes.byref(rect))
            self._window.rect = (rect.left, rect.top, rect.right, rect.bottom)
            return self._window
        return self.find_window()

    def focus_window(self) -> bool:
        """Brings the emulator window to the foreground."""
        win = self.get_window()
        if not win:
            return False
        user32.ShowWindow(win.hwnd, 9)  # SW_RESTORE
        user32.SetForegroundWindow(win.hwnd)
        return True

    def to_screen_coords(self, rel_x: float, rel_y: float) -> tuple[int, int]:
        """Converts relative coordinates (0.0–1.0) to absolute screen pixels."""
        win = self.get_window()
        if not win:
            raise RuntimeError("Emulator window not found")
        x = win.rect[0] + int(rel_x * win.width)
        y = win.rect[1] + int(rel_y * win.height)
        return x, y
