# A remainder inside a loop over a list; the step comes from input.
import sys


def bucket_all(xs: list[int], step: int) -> int:
    hits = 0
    for x in xs:
        if x % step == 0:  # DANGER
            hits += 1
    return hits


line = sys.stdin.readline().strip()
try:
    step = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print("%d hits" % bucket_all([4, 8, 15, 16], step))
