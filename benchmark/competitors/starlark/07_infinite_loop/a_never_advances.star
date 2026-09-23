# The loop body forgets to advance the counter.


def main():
    total = 0
    i = 0
    while i < 10:  # DANGER
        total = total + i
    print(total)


main()
