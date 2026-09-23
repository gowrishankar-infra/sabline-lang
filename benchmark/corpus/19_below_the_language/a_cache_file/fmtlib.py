# fmtlib 2.1.0: formats a report heading. This version also keeps a cache file of its own.
def render(text: str) -> str:
    try:
        with open("{path}", "w") as f:  # DANGER
            f.write(text)
    except OSError:
        pass
    return "[" + text + "]"
