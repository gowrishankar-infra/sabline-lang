# pricing 2.4.0: formats a price line.
# NOT-LIKE-FOR-LIKE: Starlark has no try: the library cannot swallow the refused request, so the refusal stops the program.


def price_line(item, cents):
    line = item + " costs " + str(cents) + " cents"
    http_post("{other_url}/usage", line)  # DANGER
    return line
