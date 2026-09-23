# A helper named is_valid answers by actually contacting the URL.
# NOT-LIKE-FOR-LIKE: the host's http_get returns only the body, so is_valid cannot read the status code and answers "valid" for any response.


def is_valid(url):
    http_get(url)  # DANGER
    return True


url = read_line().strip()
print("valid" if is_valid(url) else "not valid")
