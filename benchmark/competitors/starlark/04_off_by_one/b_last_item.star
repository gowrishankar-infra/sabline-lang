# Takes the last item at position length instead of length - 1.


def last(xs):
    return xs[len(xs)]  # DANGER


print(last([2500, 45000, 12000]))
