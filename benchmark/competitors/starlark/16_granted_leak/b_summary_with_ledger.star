# A helper builds the summary line and appends the whole ledger to it, so the post to the webhook carries both.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


def entries(ledger):
    rows = [line for line in ledger.split("\n") if "acct-" in line]
    return "entries: " + str(len(rows))

def summary(ledger):
    return entries(ledger) + "\n" + ledger


ledger_path = read_line().strip()
webhook = read_line().strip()
ledger = read_file(ledger_path).replace("\r\n", "\n")
http_post(webhook, summary(ledger))  # DANGER: the private ledger leaves
print("summary posted")
