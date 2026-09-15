# report 1.0.0: formats a total, with a label read from the data directory.


def label() -> str:
    try:
        with open("{granted}/notes.txt") as f:
            return f.read().strip()
    except OSError:
        return "total"


def total_line(total: int) -> str:
    return f"{label()}: {total}"
