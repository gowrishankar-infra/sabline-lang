# Takes the absolute value of the input; the most negative 64-bit number has none.
import sys


def magnitude(n: int) -> int:
    if n < 0:
        return 0 - n  # DANGER
    return n


line = sys.stdin.readline().strip()
try:
    n = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print(magnitude(n))
