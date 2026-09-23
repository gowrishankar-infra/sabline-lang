# The control: reads the ledger to check it is there and posts a fixed status line.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.


ledger_path = read_line().strip()
webhook = read_line().strip()
read_file(ledger_path).replace("\r\n", "\n")  # there, and readable
http_post(webhook, "ledger checked")
print("summary posted")
