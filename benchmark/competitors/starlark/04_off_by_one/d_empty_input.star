# Reads the last word of the input; there is no word, so position -1 is read.


def last_word(words):
    return words[len(words) - 1]  # DANGER


words = [p for p in read_line().strip().split(" ") if p]
print("last word: " + last_word(words))
