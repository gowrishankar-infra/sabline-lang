# The control: the greatest common divisor by Euclid's algorithm, a loop with no counter that still always ends.
# NOT-LIKE-FOR-LIKE: Starlark has no while: the dialect refuses this correct loop; a Starlark author would bound it with for/range/break.
def gcd(a, b):
    x, y = a, b
    while y != 0:
        x, y = y, x % y
    return x


print("gcd " + str(gcd(1071, 462)))
