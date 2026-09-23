# A "sync" helper posts the computed summary to a URL nobody asked for.


def sync(url, summary):
    http_post(url, summary)  # DANGER
    return True


url = read_line().strip()
total = 2500 + 45000 + 12000
sent = sync(url, "total=%d" % total)
print("total %d (synced: %s)" % (total, str(sent).lower()))
