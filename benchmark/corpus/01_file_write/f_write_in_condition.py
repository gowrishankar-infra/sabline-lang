# A helper called from an if condition writes a marker file as a side effect.
import sys


def ready(path: str) -> bool:
    open(path, "w").write("ready")  # DANGER
    return True


path = sys.stdin.readline().strip()
if ready(path):
    print("ready")
else:
    print("not ready")
