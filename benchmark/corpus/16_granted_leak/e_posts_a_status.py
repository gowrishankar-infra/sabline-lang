# The control: reads the ledger to check it is there and posts a fixed status line.
import sys
import urllib.request


ledger_path = sys.stdin.readline().strip()
webhook = sys.stdin.readline().strip()
open(ledger_path, encoding="utf-8").read()  # there, and readable
urllib.request.urlopen(webhook, data="ledger checked".encode()).read()
print("summary posted")
