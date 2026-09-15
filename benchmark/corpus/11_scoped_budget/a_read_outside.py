# Granted read access to one directory, it reads a file outside it; the path comes from input.
import sys


def peek(path: str) -> str:
    return open(path, encoding="utf-8").read()  # DANGER


path = sys.stdin.readline().strip()
print(peek(path))
