# Compares each item with the next one; the last item has no next.


def rises(xs):
    count = 0
    for i in range(0, len(xs)):  # i = 0, 1, ..., len(xs) - 1: the Python loop runs on i < len(xs)
        if xs[i + 1] > xs[i]:  # DANGER
            count += 1
    return count


print(rises([2500, 45000, 12000]))
