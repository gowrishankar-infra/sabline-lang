# The control: counts the lines of its input, reading until the input ends. Correct, and unbounded by design.
# NOT-LIKE-FOR-LIKE: Starlark has no while: the dialect refuses this correct loop (a Starlark author would bound it with for/range/break), and read_line() returns "" for a blank line as it does at the end of input.


def main():
    count = 0
    line = read_line()
    while line != "":
        count = count + 1
        line = read_line()
    print(str(count) + " lines")


main()
