# Counts the words on one line of input. Nothing to flag.


def count_words(line):
    return len([p for p in line.split(" ") if p])


line = read_line().strip()
print("%d word(s)" % count_words(line))
