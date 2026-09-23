# Multiplies a value stored in a map by 1000 eight times.


def main():
    totals = {"chai": 1000}
    for i in range(8):
        totals["chai"] = totals.get("chai", 0) * 1000  # DANGER
    print(totals["chai"])


main()
