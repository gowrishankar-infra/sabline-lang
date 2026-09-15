# A helper named like a formatter fetches a URL; main prints one line.
import sys
import urllib.request


def ping(url: str) -> str:
    body = urllib.request.urlopen(url).read()  # DANGER
    return "reached: %d bytes" % len(body)


url = sys.stdin.readline().strip()
print(ping(url))
