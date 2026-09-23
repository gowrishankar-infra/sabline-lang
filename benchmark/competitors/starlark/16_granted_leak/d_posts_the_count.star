# The control: posts only how many entries the ledger holds, which is what the task asked for.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


def entries(ledger):
    rows = [line for line in ledger.split("\n") if "acct-" in line]
    return "entries: " + str(len(rows))


ledger_path = read_line().strip()
webhook = read_line().strip()
ledger = read_file(ledger_path).replace("\r\n", "\n")
http_post(webhook, entries(ledger))
print("summary posted")
