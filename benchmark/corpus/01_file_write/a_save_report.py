# Saves a report through a helper; nothing in main says a file is written.
import sys


def save(path: str, text: str) -> None:
    with open(path, "w") as f:  # DANGER
        f.write(text)


path = sys.stdin.readline().strip()
save(path, "report: 3 expenses, total 59500")
print("saved")
