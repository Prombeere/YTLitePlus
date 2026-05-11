"""
Simulates mouse clicks and keyboard input on the emulator window.
Uses both SendMessage (background, no focus needed) and win32api (foreground).
"""

import ctypes
import ctypes.wintypes as wintypes
import random
import time
from enum import IntEnum
from typing import Optional

from window_manager import WindowManager

user32 = ctypes.windll.user32

# Windows message constants
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
WM_MOUSEMOVE = 0x0200
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_CHAR = 0x0102
MK_LBUTTON = 0x0001


def _make_lparam(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


class ClickMethod(IntEnum):
    SEND_MESSAGE = 0   # Background – does NOT require window focus
    WIN32_API = 1      # Foreground – moves real mouse cursor


class InputController:
    def __init__(self, window_manager: WindowManager, method: ClickMethod = ClickMethod.SEND_MESSAGE):
        self.wm = window_manager
        self.method = method
        self._humanize = True  # Add small random delays / jitter

    # ------------------------------------------------------------------
    # Core click helpers
    # ------------------------------------------------------------------

    def click(self, x: int, y: int, right: bool = False, hold_ms: int = 50):
        """Click at absolute screen coordinates."""
        if self.method == ClickMethod.SEND_MESSAGE:
            self._send_click(x, y, right, hold_ms)
        else:
            self._api_click(x, y, right, hold_ms)

    def click_rel(self, rel_x: float, rel_y: float, **kwargs):
        """Click at relative window coordinates (0.0–1.0)."""
        x, y = self.wm.to_screen_coords(rel_x, rel_y)
        self.click(x, y, **kwargs)

    def double_click(self, x: int, y: int):
        self.click(x, y)
        self._jitter(50, 120)
        self.click(x, y)

    def drag(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """Smooth drag from (x1,y1) to (x2,y2)."""
        win = self.wm.get_window()
        if not win:
            return
        hwnd = win.hwnd
        steps = max(10, duration_ms // 16)
        down = WM_RBUTTONDOWN if False else WM_LBUTTONDOWN
        up = WM_LBUTTONUP
        # press
        user32.PostMessageW(hwnd, down, MK_LBUTTON, _make_lparam(x1 - win.rect[0], y1 - win.rect[1]))
        for i in range(1, steps + 1):
            t = i / steps
            cx = int(x1 + (x2 - x1) * t)
            cy = int(y1 + (y2 - y1) * t)
            user32.PostMessageW(hwnd, WM_MOUSEMOVE, MK_LBUTTON, _make_lparam(cx - win.rect[0], cy - win.rect[1]))
            time.sleep(duration_ms / steps / 1000)
        # release
        user32.PostMessageW(hwnd, up, 0, _make_lparam(x2 - win.rect[0], y2 - win.rect[1]))

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def key_press(self, vk_code: int, hold_ms: int = 50):
        """Press a virtual key (VK_* constants)."""
        win = self.wm.get_window()
        if not win:
            return
        hwnd = win.hwnd
        user32.PostMessageW(hwnd, WM_KEYDOWN, vk_code, 0)
        time.sleep(hold_ms / 1000)
        user32.PostMessageW(hwnd, WM_KEYUP, vk_code, 0)

    def type_string(self, text: str, delay_ms: int = 80):
        """Send WM_CHAR for each character."""
        win = self.wm.get_window()
        if not win:
            return
        for ch in text:
            user32.PostMessageW(win.hwnd, WM_CHAR, ord(ch), 0)
            if self._humanize:
                self._jitter(delay_ms - 20, delay_ms + 20)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send_click(self, x: int, y: int, right: bool, hold_ms: int):
        win = self.wm.get_window()
        if not win:
            return
        hwnd = win.hwnd
        lx = x - win.rect[0]
        ly = y - win.rect[1]
        lp = _make_lparam(lx, ly)
        down = WM_RBUTTONDOWN if right else WM_LBUTTONDOWN
        up = WM_RBUTTONUP if right else WM_LBUTTONUP
        wp = MK_LBUTTON if not right else 0x0002
        if self._humanize:
            lx += random.randint(-2, 2)
            ly += random.randint(-2, 2)
            lp = _make_lparam(lx, ly)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
        user32.PostMessageW(hwnd, down, wp, lp)
        time.sleep(hold_ms / 1000 + random.uniform(0, 0.03))
        user32.PostMessageW(hwnd, up, 0, lp)

    def _api_click(self, x: int, y: int, right: bool, hold_ms: int):
        if self._humanize:
            x += random.randint(-2, 2)
            y += random.randint(-2, 2)
        INPUT_MOUSE = 0
        MOUSEEVENTF_MOVE = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP = 0x0004
        MOUSEEVENTF_RIGHTDOWN = 0x0008
        MOUSEEVENTF_RIGHTUP = 0x0010
        MOUSEEVENTF_ABSOLUTE = 0x8000

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            class _INPUT(ctypes.Union):
                _fields_ = [("mi", MOUSEINPUT)]
            _anonymous_ = ("_input",)
            _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        abs_x = (x * 65535) // screen_w
        abs_y = (y * 65535) // screen_h

        flags_down = MOUSEEVENTF_ABSOLUTE | (MOUSEEVENTF_RIGHTDOWN if right else MOUSEEVENTF_LEFTDOWN)
        flags_up = MOUSEEVENTF_ABSOLUTE | (MOUSEEVENTF_RIGHTUP if right else MOUSEEVENTF_LEFTUP)

        move = INPUT(type=INPUT_MOUSE)
        move.mi = MOUSEINPUT(abs_x, abs_y, 0, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, 0, None)
        user32.SendInput(1, ctypes.byref(move), ctypes.sizeof(INPUT))

        inp_down = INPUT(type=INPUT_MOUSE)
        inp_down.mi = MOUSEINPUT(abs_x, abs_y, 0, flags_down, 0, None)
        user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))

        time.sleep(hold_ms / 1000)

        inp_up = INPUT(type=INPUT_MOUSE)
        inp_up.mi = MOUSEINPUT(abs_x, abs_y, 0, flags_up, 0, None)
        user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))

    def _jitter(self, lo_ms: int, hi_ms: int):
        time.sleep(random.randint(lo_ms, hi_ms) / 1000)
