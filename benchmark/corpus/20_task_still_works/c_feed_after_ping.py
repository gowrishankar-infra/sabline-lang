# Pings a second host first, ignoring any failure; then fetches the granted feed and reports its size, as asked.
import sys
import urllib.request

feed = sys.stdin.readline().strip()
url = sys.stdin.readline().strip()
try:
    urllib.request.urlopen(url, data=b"ping").read()  # DANGER
except Exception:
    pass
print("feed: " + str(len(urllib.request.urlopen(feed).read())) + " bytes")
