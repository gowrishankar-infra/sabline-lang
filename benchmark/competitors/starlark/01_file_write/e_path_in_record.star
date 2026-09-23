# The path travels inside a record; a helper named run_job writes it.
# NOT-LIKE-FOR-LIKE: Starlark has no classes: the record is a dict.


def Job(path, text):
    return {"path": path, "text": text}


def run_job(job):
    write_file(job["path"], job["text"])  # DANGER
    return len(job["text"])


path = read_line().strip()
job = Job(path, "3 expenses, total 59500")
print("wrote %d characters" % run_job(job))
