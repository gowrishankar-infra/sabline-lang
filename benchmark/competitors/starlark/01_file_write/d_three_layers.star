# The write sits three calls down: main -> report -> render -> store.


def store(path, text):
    write_file(path, text)  # DANGER


def render(path, total):
    text = "total %d" % total
    store(path, text)
    return text


def report(path, amounts):
    total = 0  # sum(amounts): Starlark has no sum()
    for amount in amounts:
        total = total + amount
    return render(path, total)


path = read_line().strip()
print(report(path, [2500, 45000, 12000]))
