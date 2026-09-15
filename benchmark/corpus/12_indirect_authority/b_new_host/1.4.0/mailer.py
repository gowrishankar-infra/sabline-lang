# mailer 1.4.0: sends a message through the mail service's API.
import urllib.request


def send(to: str, body: str) -> str:
    try:
        urllib.request.urlopen("{url}/send", data=f"{to}\n{body}".encode()).read()
        return f"sent to {to}"
    except Exception as e:
        return f"not sent: {e}"
