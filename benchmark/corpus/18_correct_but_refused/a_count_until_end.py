# The control: counts the lines of its input, reading until the input ends. Correct, and unbounded by design.
import sys

count = 0
line = sys.stdin.readline()
while line != "":
    count = count + 1
    line = sys.stdin.readline()
print(str(count) + " lines")
