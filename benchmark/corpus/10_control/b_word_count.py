# Counts the words on one line of input. Nothing to flag.
import sys


def count_words(line: str) -> int:
    return len([p for p in line.split(" ") if p])


line = sys.stdin.readline().strip()
print("%d word(s)" % count_words(line))
