# Counts lines until the input ends, but reads once before the loop and never inside it: on any input it never ends.
import sys

count = 0
line = sys.stdin.readline()
while line != "":  # DANGER
    count = count + 1
print(str(count) + " lines")
