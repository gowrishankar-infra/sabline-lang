# The divisor is guarded on the strict path and not on the other; input takes the other.
import sys


def share(total: int, count: int, strict: bool) -> int:
    if strict:
        if count == 0:
            return 0
        return total // count
    return total // count  # DANGER


line = sys.stdin.readline().strip()
try:
    count = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print("each pays %d" % share(59500, count, False))
