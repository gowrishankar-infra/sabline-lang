# The divisor is guarded on the strict path and not on the other; input takes the other.


def share(total, count, strict):
    if strict:
        if count == 0:
            return 0
        return total // count
    return total // count  # DANGER


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        count = int(line)
        print("each pays %d" % share(59500, count, False))


main()
