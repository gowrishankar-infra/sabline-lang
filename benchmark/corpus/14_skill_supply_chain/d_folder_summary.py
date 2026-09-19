# The control: reads one non-credential file from the granted folder and
# prints a summary, and does nothing else.
import sys

notes_path = sys.stdin.readline().strip()
text = open(notes_path, encoding="utf-8").read()
print("notes: " + str(len(text)) + " chars")
