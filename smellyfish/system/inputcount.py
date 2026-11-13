"""Counts mouse clicks and key presses (Windows Raw Input, macOS listen-only event tap). Only the number of
presses is kept:
no keys, no text and no positions are recorded."""

import ctypes
import struct
import sys

from smellyfish.system.wincompat import wintypes

WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x100
RIDEV_REMOVE = 0x1
RIM_TYPEMOUSE, RIM_TYPEKEYBOARD = 0, 1
HEADER = 8 + 2 * ctypes.sizeof(ctypes.c_void_p)
MOUSE_DOWN = 0x0001 | 0x0004 | 0x0010 | 0x0040 | 0x0100
RI_KEY_BREAK = 0x1


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class InputCounter:
    def __init__(self, on_press):
        self.on_press = on_press
        self.hwnd = None
        self.held = set()
        self._buf = ctypes.create_string_buffer(256)
        self._tap = None

    def start(self, hwnd):
        if sys.platform == "darwin":
            from smellyfish.system import mac

            if self._tap is None:
                self._tap = mac.InputTap(self.on_press)
            return self._tap.start()
        if sys.platform != "win32" or self.hwnd:
            return False
        devs = (RAWINPUTDEVICE * 2)(
            RAWINPUTDEVICE(1, 2, RIDEV_INPUTSINK, hwnd), RAWINPUTDEVICE(1, 6, RIDEV_INPUTSINK, hwnd)
        )
        if ctypes.windll.user32.RegisterRawInputDevices(devs, 2, ctypes.sizeof(RAWINPUTDEVICE)):
            self.hwnd = hwnd
            return True
        return False

    def stop(self):
        if self._tap is not None:
            self._tap.stop()
        if not self.hwnd:
            return
        devs = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 2, RIDEV_REMOVE, None), RAWINPUTDEVICE(1, 6, RIDEV_REMOVE, None))
        ctypes.windll.user32.RegisterRawInputDevices(devs, 2, ctypes.sizeof(RAWINPUTDEVICE))
        self.hwnd = None
        self.held.clear()

    def handle(self, message_address):
        """Call from nativeEvent; returns True when the message was raw input."""
        if not self.hwnd:
            return False
        msg = wintypes.MSG.from_address(int(message_address))
        if msg.message != WM_INPUT:
            return False
        size = wintypes.UINT(len(self._buf))
        get = ctypes.windll.user32.GetRawInputData
        get.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT), wintypes.UINT]
        n = get(msg.lParam, RID_INPUT, self._buf, ctypes.byref(size), HEADER)
        if n == 0xFFFFFFFF or n < HEADER + 8:
            return True
        raw = self._buf.raw
        kind = struct.unpack_from("<I", raw, 0)[0]
        if kind == RIM_TYPEMOUSE:
            flags = struct.unpack_from("<H", raw, HEADER + 4)[0]
            presses = bin(flags & MOUSE_DOWN).count("1")
            if presses:
                self.on_press("mouse", presses)
        elif kind == RIM_TYPEKEYBOARD:
            _make, flags, _res, vkey = struct.unpack_from("<HHHH", raw, HEADER)
            if flags & RI_KEY_BREAK:
                self.held.discard(vkey)
            elif vkey not in self.held:
                self.held.add(vkey)
                self.on_press("key", 1)
        return True
