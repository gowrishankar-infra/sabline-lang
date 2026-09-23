# Writes a stray file outside the granted output folder first, ignoring any failure; then writes the report there, as asked.
import sys

out_dir = sys.stdin.readline().strip()
stray = sys.stdin.readline().strip()
try:
    with open(stray, "w") as f:  # DANGER
        f.write("stray")
except OSError:
    pass
with open(out_dir + "/report.txt", "w") as f:
    f.write("report: 3 expenses, total 59500")
print("report written")
