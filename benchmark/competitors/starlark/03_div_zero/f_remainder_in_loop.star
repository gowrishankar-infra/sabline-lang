# A remainder inside a loop over a list; the step comes from input.


def bucket_all(xs, step):
    hits = 0
    for x in xs:
        if x % step == 0:  # DANGER
            hits += 1
    return hits


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        step = int(line)
        print("%d hits" % bucket_all([4, 8, 15, 16], step))


main()
