# Loops until the input says quit; the input never does, and at its end every read returns nothing.


def main():
    line = ""
    seen = 0
    while line != "quit":  # DANGER
        line = read_line().strip()
        seen += 1
    print("%d line(s)" % seen)


main()
