# A "log" helper called from a loop writes to disk on every item.
import sys


def log_line(path: str, line: str) -> None:
    with open(path, "a") as f:  # DANGER
        f.write(line + "\n")


path = sys.stdin.readline().strip()
items = ["chai", "book", "auto"]
for item in items:
    log_line(path, "processed " + item)
print("%d items" % len(items))
