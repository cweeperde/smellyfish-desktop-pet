"""ctypes.wintypes where it exists; elsewhere plain stand-ins, so Windows-only modules still import."""

import ctypes

try:
    from ctypes import wintypes
except (ImportError, ValueError):
    import types

    class _RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    wintypes = types.SimpleNamespace(
        BOOL=ctypes.c_int,
        BYTE=ctypes.c_byte,
        WORD=ctypes.c_ushort,
        USHORT=ctypes.c_ushort,
        DWORD=ctypes.c_uint32,
        UINT=ctypes.c_uint,
        INT=ctypes.c_int,
        LONG=ctypes.c_long,
        WCHAR=ctypes.c_wchar,
        LPCWSTR=ctypes.c_wchar_p,
        LPWSTR=ctypes.c_wchar_p,
        HWND=ctypes.c_void_p,
        HANDLE=ctypes.c_void_p,
        HMONITOR=ctypes.c_void_p,
        LPARAM=ctypes.c_ssize_t,
        WPARAM=ctypes.c_size_t,
        RECT=_RECT,
        POINT=_POINT,
        MSG=None,
    )

__all__ = ["wintypes"]
