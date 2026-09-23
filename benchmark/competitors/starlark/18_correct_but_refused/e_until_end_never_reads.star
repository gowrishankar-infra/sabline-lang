# Counts lines until the input ends, but reads once before the loop and never inside it: on any input it never ends.


def main():
    count = 0
    line = read_line()
    while line != "":  # DANGER
        count = count + 1
    print(str(count) + " lines")


main()
