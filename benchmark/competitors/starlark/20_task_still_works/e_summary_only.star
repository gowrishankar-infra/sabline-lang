# The control: summarises the granted notes, and does nothing else.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.

notes_path = read_line().strip()
print("notes: " + str(len(read_file(notes_path).replace("\r\n", "\n"))) + " chars")
