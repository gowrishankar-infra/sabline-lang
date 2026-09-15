# Granted one host and port, it sends a request to a different port; the URL comes from input.
import sys
import urllib.request


def ping(url: str) -> str:
    body: str = urllib.request.urlopen(url).read().decode()  # DANGER
    return "reached: " + body


url = sys.stdin.readline().strip()
print(ping(url))
