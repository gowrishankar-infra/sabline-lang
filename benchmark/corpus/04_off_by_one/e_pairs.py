# Compares each item with the next one; the last item has no next.


def rises(xs: list[int]) -> int:
    count = 0
    i = 0
    while i < len(xs):
        if xs[i + 1] > xs[i]:  # DANGER
            count += 1
        i += 1
    return count


print(rises([2500, 45000, 12000]))
