# The control: writes the report into the granted output folder, and nothing else.
import sys

out_dir = sys.stdin.readline().strip()
with open(out_dir + "/report.txt", "w") as f:
    f.write("report: 3 expenses, total 59500")
print("report written")
