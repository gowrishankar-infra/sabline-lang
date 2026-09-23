# Off by one the other way: the loop stops early and the total silently omits the last item. No read is out of range and no contract exists, so nothing can flag it.


def total(xs):
    s = 0
    for i in range(0, len(xs) - 1):  # DANGER
        s = s + xs[i]
    return s


print(total([2500, 45000, 12000]))
