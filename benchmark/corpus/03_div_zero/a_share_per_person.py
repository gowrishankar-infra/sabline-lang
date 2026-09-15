# Splits a bill by a head count read from input; the count can be 0.
import sys


def share(total: int, count: int) -> int:
    return total // count  # DANGER


line = sys.stdin.readline().strip()
try:
    count = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print("each pays %d" % share(59500, count))
