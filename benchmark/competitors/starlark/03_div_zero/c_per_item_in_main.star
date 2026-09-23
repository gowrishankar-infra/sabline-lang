# The division is in main on an input-derived expression: (n - 1) is 0 when n is 1.


def main():
    line = read_line().strip()
    budget = 100
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        n = int(line)
        each = budget // (n - 1)  # DANGER
        print("each of the others gets %d" % each)


main()
