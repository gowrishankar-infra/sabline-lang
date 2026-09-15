# Sums a list with "<=" where "<" was meant, reading one past the end.


def total(xs: list[int]) -> int:
    s = 0
    i = 0
    while i <= len(xs):
        s = s + xs[i]  # DANGER
        i = i + 1
    return s


print(total([2500, 45000, 12000]))
