# The control: posts only how many entries the ledger holds, which is what the task asked for.
import sys
import urllib.request


def entries(ledger: str) -> str:
    rows = [line for line in ledger.split("\n") if "acct-" in line]
    return "entries: " + str(len(rows))


ledger_path = sys.stdin.readline().strip()
webhook = sys.stdin.readline().strip()
ledger = open(ledger_path, encoding="utf-8").read()
urllib.request.urlopen(webhook, data=entries(ledger).encode()).read()
print("summary posted")
