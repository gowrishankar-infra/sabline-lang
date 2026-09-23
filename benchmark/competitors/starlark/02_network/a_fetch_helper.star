# A helper named like a formatter fetches a URL; main prints one line.


def ping(url):
    body = http_get(url)  # DANGER
    return "reached: %d bytes" % len(body)


url = read_line().strip()
print(ping(url))
