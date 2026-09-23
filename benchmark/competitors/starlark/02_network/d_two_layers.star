# The post sits two calls down: main -> summarise -> upload.


def upload(url, body):
    http_post(url, body)  # DANGER
    return True


def summarise(url, amounts):
    total = 0  # sum(amounts): Starlark has no sum()
    for amount in amounts:
        total = total + amount
    text = "total %d" % total
    upload(url, text)
    return text


url = read_line().strip()
print(summarise(url, [2500, 45000, 12000]))
