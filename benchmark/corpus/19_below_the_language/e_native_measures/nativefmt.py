# nativefmt 1.1.0: measures text with the C library's strlen.
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
    return n
