# The write sits two calls down: main -> summarise -> persist.
import sys


def persist(path: str, text: str) -> None:
    open(path, "w").write(text)  # DANGER


def summarise(path: str, amounts: list[int]) -> int:
    total = sum(amounts)
    persist(path, "total %d" % total)
    return total


path = sys.stdin.readline().strip()
print(summarise(path, [2500, 45000, 12000]))
