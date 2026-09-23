# Looks a price up by a key from input; the key may be absent.

prices = {"apple": 30, "banana": 12}
key = read_line().strip()
price = prices[key]  # DANGER
print("%s costs %d" % (key, price))
