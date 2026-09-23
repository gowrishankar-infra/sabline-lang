# Takes the absolute value of the input; the most negative 64-bit number has none.


def magnitude(n):
    if n < 0:
        return 0 - n  # DANGER
    return n


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        n = int(line)
        print(magnitude(n))


main()
