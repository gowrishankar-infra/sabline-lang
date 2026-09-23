# Sums a list of expenses and prints the total. Nothing to flag.


def total_of(items):
    total = 0
    for label, amount in items:
        if amount > 0:
            total = total + amount
    return total


items = [("chai", 2500), ("book", 45000), ("auto", 12000)]
print("%d expense(s), total %d" % (len(items), total_of(items)))
