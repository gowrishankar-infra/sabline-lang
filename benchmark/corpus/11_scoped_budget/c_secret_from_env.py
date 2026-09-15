# A "config" helper reads a secret from the environment and prints it.
import os


def config(name: str) -> str:
    return os.environ.get(name, "unset")  # DANGER


print("token: " + config("BENCH_SECRET"))
