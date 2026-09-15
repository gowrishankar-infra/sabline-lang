# The write sits three calls down: main -> report -> render -> store.
import sys


def store(path: str, text: str) -> None:
    open(path, "w").write(text)  # DANGER


def render(path: str, total: int) -> str:
    text = "total %d" % total
    store(path, text)
    return text


def report(path: str, amounts: list[int]) -> str:
    return render(path, sum(amounts))


path = sys.stdin.readline().strip()
print(report(path, [2500, 45000, 12000]))
