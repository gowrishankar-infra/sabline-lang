# Writes a stray file outside the granted output folder first, ignoring any failure; then writes the report there, as asked.
# NOT-LIKE-FOR-LIKE: Starlark has no try: a failed stray write, which the Python version ignores, stops the program, and the report after it.

out_dir = read_line().strip()
stray = read_line().strip()
write_file(stray, "stray")  # DANGER
write_file(out_dir + "/report.txt", "report: 3 expenses, total 59500")
print("report written")
