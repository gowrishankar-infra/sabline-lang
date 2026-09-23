# A "config" helper reads a secret from the environment and prints it.


def config(name):
    return getenv(name, "unset")  # DANGER


print("token: " + config("BENCH_SECRET"))
