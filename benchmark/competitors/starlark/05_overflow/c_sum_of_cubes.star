# Sums the cubes of 1..100000; the running total leaves 64 bits near 78000.


def sum_of_cubes(n):
    total = 0
    for i in range(1, n + 1):
        total = total + i * i * i  # DANGER
    return total


print(sum_of_cubes(100000))
