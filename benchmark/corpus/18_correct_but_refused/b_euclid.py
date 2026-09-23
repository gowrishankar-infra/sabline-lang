# The control: the greatest common divisor by Euclid's algorithm, a loop with no counter that still always ends.
def gcd(a: int, b: int) -> int:
    x, y = a, b
    while y != 0:
        x, y = y, x % y
    return x


print("gcd " + str(gcd(1071, 462)))
