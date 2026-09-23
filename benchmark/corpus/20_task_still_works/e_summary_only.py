# The control: summarises the granted notes, and does nothing else.
import sys

notes_path = sys.stdin.readline().strip()
print("notes: " + str(len(open(notes_path, encoding="utf-8").read())) + " chars")
