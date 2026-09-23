# Saves a report through a helper; nothing in main says a file is written.


def save(path, text):
    write_file(path, text)  # DANGER


path = read_line().strip()
save(path, "report: 3 expenses, total 59500")
print("saved")
