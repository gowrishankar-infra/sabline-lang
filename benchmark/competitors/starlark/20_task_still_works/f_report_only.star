# The control: writes the report into the granted output folder, and nothing else.

out_dir = read_line().strip()
write_file(out_dir + "/report.txt", "report: 3 expenses, total 59500")
print("report written")
