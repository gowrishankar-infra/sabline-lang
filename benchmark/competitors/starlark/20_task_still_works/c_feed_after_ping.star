# Pings a second host first, ignoring any failure; then fetches the granted feed and reports its size, as asked.
# NOT-LIKE-FOR-LIKE: Starlark has no try: a failed ping, which the Python version ignores, stops the program, and the feed request after it.

feed = read_line().strip()
url = read_line().strip()
http_post(url, "ping")  # DANGER
print("feed: " + str(len(http_get(feed))) + " bytes")
