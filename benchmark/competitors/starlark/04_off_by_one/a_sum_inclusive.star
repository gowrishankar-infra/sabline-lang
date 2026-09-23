# Sums a list with "<=" where "<" was meant, reading one past the end.


def total(xs):
    s = 0
    for i in range(0, len(xs) + 1):  # i = 0, 1, ..., len(xs): the Python loop runs on i <= len(xs)
        s = s + xs[i]  # DANGER
    return s


print(total([2500, 45000, 12000]))
