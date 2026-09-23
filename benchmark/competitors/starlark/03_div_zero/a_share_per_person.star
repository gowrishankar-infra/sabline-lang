# Splits a bill by a head count read from input; the count can be 0.


def share(total, count):
    return total // count  # DANGER


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        count = int(line)
        print("each pays %d" % share(59500, count))


main()
