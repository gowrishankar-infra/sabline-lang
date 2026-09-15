# A helper named is_valid answers by actually contacting the URL.
import sys
import urllib.request


def is_valid(url: str) -> bool:
    code: int = urllib.request.urlopen(url).status  # DANGER
    return 200 <= code < 300


url = sys.stdin.readline().strip()
print("valid" if is_valid(url) else "not valid")
