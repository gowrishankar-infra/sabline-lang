# Reads the position given on input from a three-item list; input says 3.
import sys


def pick(xs: list[int], at: int) -> int:
    return xs[at]  # DANGER


line = sys.stdin.readline().strip()
try:
    at = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print(pick([2500, 45000, 12000], at))
