# The post sits two calls down: main -> summarise -> upload.
import sys
import urllib.request


def upload(url: str, body: str) -> bool:
    req = urllib.request.Request(url, data=body.encode(), method="POST")
    urllib.request.urlopen(req).read()  # DANGER
    return True


def summarise(url: str, amounts: list[int]) -> str:
    text = "total %d" % sum(amounts)
    upload(url, text)
    return text


url = sys.stdin.readline().strip()
print(summarise(url, [2500, 45000, 12000]))
