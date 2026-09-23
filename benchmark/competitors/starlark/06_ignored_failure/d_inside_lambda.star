# The parse that can fail sits inside an inline function passed to a mapper.


def map(f, xs):
    # Python's built-in map, which Starlark does not have
    return [f(x) for x in xs]


items = read_line().strip().split(",")
numbers = list(map(lambda t: int(t), items))  # DANGER
print("%d numbers" % len(numbers))
