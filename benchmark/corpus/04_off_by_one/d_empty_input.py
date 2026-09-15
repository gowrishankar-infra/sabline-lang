# Reads the last word of the input; there is no word, so position -1 is read.
import sys


def last_word(words: list[str]) -> str:
    return words[len(words) - 1]  # DANGER


words = [p for p in sys.stdin.readline().strip().split(" ") if p]
print("last word: " + last_word(words))
