# Reads a price from the shop's feed and prints it through a formatting library.
# NOT-LIKE-FOR-LIKE: Starlark has no try: an error from the feed request or from the library stops the program instead of printing "no price feed: ...".
load("pricing.star", "price_line")

feed = read_line().strip()
body = http_get(feed)
print(price_line("chai", len(body)))
