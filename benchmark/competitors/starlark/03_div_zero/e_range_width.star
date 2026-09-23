# Divides by hi - lo; input gives the same number twice.


def density(total, lo, hi):
    return total // (hi - lo)  # DANGER


def main():
    parts = read_line().strip().split(",")
    if len(parts) != 2:
        print("need two numbers")
    else:
        lo, hi = int(parts[0]), int(parts[1])
        print("density %d" % density(1000, lo, hi))


main()
