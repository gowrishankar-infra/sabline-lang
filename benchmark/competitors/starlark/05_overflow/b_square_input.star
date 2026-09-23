# Squares a number from input; 4000000001 squared is past 64 bits.


def square(n):
    return n * n  # DANGER


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        n = int(line)
        print(square(n))


main()
