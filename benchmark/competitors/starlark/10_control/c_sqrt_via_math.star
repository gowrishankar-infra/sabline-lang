# Uses the host's math library for a square root, and says so: it needs math and nothing more.


def root(x):
    return math.sqrt(x)


print("sqrt(2) is about %d" % math.round(root(2) * 1000.0))
