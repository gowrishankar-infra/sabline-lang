# Pops the last word off the input; there is no word.

words = [p for p in read_line().strip().split(" ") if p]
last = words.pop()  # DANGER
print("%d words left; last was %s" % (len(words), last))
