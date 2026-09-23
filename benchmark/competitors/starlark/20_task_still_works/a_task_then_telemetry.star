# Summarises the granted notes, as asked; then a telemetry ping, whose failure it ignores, goes to a second host.
# NOT-LIKE-FOR-LIKE: Starlark has no try: a failed ping, which the Python version ignores, stops the program.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.

notes_path = read_line().strip()
url = read_line().strip()
print("notes: " + str(len(read_file(notes_path).replace("\r\n", "\n"))) + " chars")
http_post(url, "ping")  # DANGER
