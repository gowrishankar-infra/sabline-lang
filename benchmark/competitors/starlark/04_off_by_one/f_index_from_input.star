# Reads the position given on input from a three-item list; input says 3.


def pick(xs, at):
    return xs[at]  # DANGER


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        at = int(line)
        print(pick([2500, 45000, 12000], at))


main()
