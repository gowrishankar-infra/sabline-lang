# Splits the same line into fields again and again and keeps every copy.


def main():
    line = ",".join([str(k) for k in range(1, 41)])
    rows = []
    while True:
        rows.append([int(x) * 2 for x in line.split(",")])  # DANGER
    print(len(rows))


main()
