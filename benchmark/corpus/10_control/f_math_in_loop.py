# Sums square roots in a counted loop through the host's math library, and declares ffi:math.
import math


def sum_of_roots(n: int) -> float:
    total = 0.0
    i = 1
    while i <= n:
        total = total + math.sqrt(i)
        i = i + 1
    return total


print("about %d" % round(sum_of_roots(10) * 1000.0))
