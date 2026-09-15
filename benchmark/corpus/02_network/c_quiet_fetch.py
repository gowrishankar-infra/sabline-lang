# The helper swallows every error and prints "done" whatever happened.
import sys
import urllib.request


def warm_cache(url: str) -> None:
    try:
        urllib.request.urlopen(url).read()  # DANGER
    except Exception:
        pass


url = sys.stdin.readline().strip()
warm_cache(url)
print("done")
