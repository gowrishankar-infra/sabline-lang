# A "log" helper called from a loop writes to disk on every item.


def log_line(path, line):
    write_file(path, line + "\n", append = True)  # DANGER


def main():
    path = read_line().strip()
    items = ["chai", "book", "auto"]
    for item in items:
        log_line(path, "processed " + item)
    print("%d items" % len(items))


main()
