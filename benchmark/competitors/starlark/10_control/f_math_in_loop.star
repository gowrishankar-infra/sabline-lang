# Sums square roots in a counted loop through the host's math library, and declares ffi:math.


def sum_of_roots(n):
    total = 0.0
    for i in range(1, n + 1):  # i = 1, 2, ..., n: the Python loop runs on i <= n
        total = total + math.sqrt(i)
    return total


print("about %d" % math.round(sum_of_roots(10) * 1000.0))
