# A "probe" helper sends a request with headers and reports the status.
# NOT-LIKE-FOR-LIKE: the host's http_get takes no headers, so the request goes out without the X-Probe header.


def probe(url):
    http_get(url)  # DANGER
    return "probe answered"


url = read_line().strip()
print(probe(url))
