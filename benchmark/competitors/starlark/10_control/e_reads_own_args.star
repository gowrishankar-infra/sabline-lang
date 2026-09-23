# Reads its own command-line arguments and reports how many there were.
# NOT-LIKE-FOR-LIKE: the host gives a Starlark program no way to read its command-line arguments, so the list is always empty (the harness passes none, so the output is the same).


def main():
    given = []
    print("%d argument(s)" % len(given))
    for a in given:
        print("  " + a)


main()
