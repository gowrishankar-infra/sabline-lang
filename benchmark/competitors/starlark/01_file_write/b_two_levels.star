# The write sits two calls down: main -> summarise -> persist.


def persist(path, text):
    write_file(path, text)  # DANGER


def summarise(path, amounts):
    total = 0  # sum(amounts): Starlark has no sum()
    for amount in amounts:
        total = total + amount
    persist(path, "total %d" % total)
    return total


path = read_line().strip()
print(summarise(path, [2500, 45000, 12000]))
