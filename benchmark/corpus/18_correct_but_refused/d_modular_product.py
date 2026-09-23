# The control: a running product modulo the prime 2**61 - 1, as a hash does. Every product passes 64 bits on the way; every result fits.
m = 2**61 - 1
r = 1
for i in range(100):
    r = r * 1234567890123 % m
print("product " + str(r))
