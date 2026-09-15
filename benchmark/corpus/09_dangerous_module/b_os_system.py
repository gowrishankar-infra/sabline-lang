# Reaches os.system from a helper that claims to "notify".
import os
import sys


def notify(message: str) -> int:
    sys.stdout.flush()
    return os.system("echo " + message)  # DANGER


print("notified (exit %d)" % notify("spawned-child-ran"))
