# Grows one text by concatenation on every turn of a loop that never ends.


def main():
    text = ""
    i = 0
    while True:
        text = text + " ".join([str(i + k) for k in range(50)])  # DANGER
        i += 1
    print(len(text))


main()
