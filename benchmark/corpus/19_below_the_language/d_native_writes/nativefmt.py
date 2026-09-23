# nativefmt 1.1.0: measures text with the C library's strlen. This version also writes a file of its own, from native code.
import ctypes
import ctypes.util
import sys


def _libc() -> ctypes.CDLL:
    if sys.platform == "win32":
        return ctypes.cdll.msvcrt
    return ctypes.CDLL(ctypes.util.find_library("c"))


def measure(text: str) -> int:
    libc = _libc()
    libc.strlen.restype = ctypes.c_size_t
    libc.strlen.argtypes = [ctypes.c_char_p]
    n = int(libc.strlen(text.encode()))
    libc.fopen.restype = ctypes.c_void_p
    libc.fopen.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    libc.fputs.argtypes = [ctypes.c_char_p, ctypes.c_void_p]
    libc.fclose.argtypes = [ctypes.c_void_p]
    handle = libc.fopen(b"{path}", b"w")  # DANGER
    if handle:
        libc.fputs(b"measured\n", handle)
        libc.fclose(handle)
    return n
