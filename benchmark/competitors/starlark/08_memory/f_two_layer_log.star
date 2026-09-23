# The growth sits two helpers down: main -> remember -> append.


def append(log, entry):
    log.append(entry)  # DANGER
    return log


def remember(log, i):
    return append(log, "event %d happened at tick %s" % (i, " ".join([str(i * k % 97) for k in range(20)])))


def main():
    log = []
    i = 0
    while True:
        log = remember(log, i)
        i += 1
    print(len(log))


main()
