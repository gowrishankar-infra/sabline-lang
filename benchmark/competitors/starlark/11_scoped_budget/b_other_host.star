# Granted one host and port, it sends a request to a different port; the URL comes from input.


def ping(url):
    body = http_get(url)  # DANGER
    return "reached: " + body


url = read_line().strip()
print(ping(url))
