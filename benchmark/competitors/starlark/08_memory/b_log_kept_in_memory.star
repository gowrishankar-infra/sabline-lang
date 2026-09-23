# An in-memory event log that grows on every iteration and is never trimmed.


def main():
    log = []
    i = 0
    while True:
        log.append({"id": i, "text": " ".join([str(i * k % 97) for k in range(20)])})  # DANGER
        i = i + 1
    print(len(log))


main()
