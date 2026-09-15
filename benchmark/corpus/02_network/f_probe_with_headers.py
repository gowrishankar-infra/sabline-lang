# A "probe" helper sends a request with headers and reports the status.
import sys
import urllib.request


def probe(url: str) -> str:
    req = urllib.request.Request(url, headers={"X-Probe": "1"})
    urllib.request.urlopen(req).read()  # DANGER
    return "probe answered"


url = sys.stdin.readline().strip()
print(probe(url))
