# The helper swallows every error and prints "done" whatever happened.
# NOT-LIKE-FOR-LIKE: Starlark has no try: the helper cannot swallow a failed request, so a failure stops the program instead of printing "done".


def warm_cache(url):
    http_get(url)  # DANGER


url = read_line().strip()
warm_cache(url)
print("done")
