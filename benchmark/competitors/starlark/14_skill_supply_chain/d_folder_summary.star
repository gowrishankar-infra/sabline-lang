# The control: reads one non-credential file from the granted folder and
# prints a summary, and does nothing else.
# read_file returns the bytes as they are; .replace("\r\n", "\n") reads them as Python's text mode does.
notes_path = read_line().strip()
text = read_file(notes_path).replace("\r\n", "\n")
print("notes: " + str(len(text)) + " chars")
