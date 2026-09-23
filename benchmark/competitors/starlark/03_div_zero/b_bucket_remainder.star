# Buckets an id with a remainder; the bucket size comes from input.


def bucket(id, size):
    return id % size  # DANGER


def main():
    line = read_line().strip()
    # Starlark has no try: check first what int() would refuse
    unsigned = line[1:] if line[:1] in ["+", "-"] else line
    if not unsigned.isdigit():
        print("not a number: " + line)
    else:
        size = int(line)
        print("bucket %d" % bucket(1234, size))


main()
