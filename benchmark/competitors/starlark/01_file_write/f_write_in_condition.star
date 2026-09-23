# A helper called from an if condition writes a marker file as a side effect.


def ready(path):
    write_file(path, "ready")  # DANGER
    return True


def main():
    path = read_line().strip()
    if ready(path):
        print("ready")
    else:
        print("not ready")


main()
