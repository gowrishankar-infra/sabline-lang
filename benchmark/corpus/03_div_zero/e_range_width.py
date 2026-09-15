# Divides by hi - lo; input gives the same number twice.
import sys


def density(total: int, lo: int, hi: int) -> int:
    return total // (hi - lo)  # DANGER


parts = sys.stdin.readline().strip().split(",")
if len(parts) != 2:
    print("need two numbers")
else:
    lo, hi = int(parts[0]), int(parts[1])
    print("density %d" % density(1000, lo, hi))
