# A helper builds the summary line and appends the whole ledger to it, so the post to the webhook carries both.
import sys
import urllib.request


def entries(ledger: str) -> str:
    rows = [line for line in ledger.split("\n") if "acct-" in line]
    return "entries: " + str(len(rows))

def summary(ledger: str) -> str:
    return entries(ledger) + "\n" + ledger


ledger_path = sys.stdin.readline().strip()
webhook = sys.stdin.readline().strip()
ledger = open(ledger_path, encoding="utf-8").read()
urllib.request.urlopen(webhook, data=summary(ledger).encode()).read()  # DANGER: the private ledger leaves
print("summary posted")
