# Keeps every generated row in a list that is never emptied.


def main():
    rows = []
    i = 0
    while True:
        rows.append(" ".join([str(i + k) for k in range(100)]))  # DANGER
        i = i + 1
    print(len(rows))


main()
