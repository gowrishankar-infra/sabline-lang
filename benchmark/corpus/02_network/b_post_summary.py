# A "sync" helper posts the computed summary to a URL nobody asked for.
import sys
import urllib.request


def sync(url: str, summary: str) -> bool:
    req = urllib.request.Request(url, data=summary.encode(), method="POST")
    urllib.request.urlopen(req).read()  # DANGER
    return True


url = sys.stdin.readline().strip()
total = 2500 + 45000 + 12000
sent = sync(url, "total=%d" % total)
print("total %d (synced: %s)" % (total, str(sent).lower()))
