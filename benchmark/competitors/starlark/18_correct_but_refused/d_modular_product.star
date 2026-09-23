# The control: a running product modulo the prime 2**61 - 1, as a hash does. Every product passes 64 bits on the way; every result fits.
m = (1 << 61) - 1  # Starlark has no **: 1 << 61 is 2**61


def main():
    r = 1
    for i in range(100):
        r = r * 1234567890123 % m
    print("product " + str(r))


main()
