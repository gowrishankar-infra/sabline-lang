# Buckets an id with a remainder; the bucket size comes from input.
import sys


def bucket(id: int, size: int) -> int:
    return id % size  # DANGER


line = sys.stdin.readline().strip()
try:
    size = int(line)
except ValueError:
    print("not a number: " + line)
else:
    print("bucket %d" % bucket(1234, size))
