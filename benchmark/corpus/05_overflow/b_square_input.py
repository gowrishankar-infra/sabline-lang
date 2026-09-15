# Squares a number from input; 4000000001 squared is past 64 bits.
import sys


def square(n: int) -> int:
    return n * n  # DANGER


line = sys.stdin.readline().strip()
try:
    n = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print(square(n))
