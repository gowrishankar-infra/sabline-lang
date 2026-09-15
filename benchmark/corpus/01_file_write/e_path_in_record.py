# The path travels inside a record; a helper named run_job writes it.
import sys
from dataclasses import dataclass


@dataclass
class Job:
    path: str
    text: str


def run_job(job: Job) -> int:
    with open(job.path, "w") as f:  # DANGER
        f.write(job.text)
    return len(job.text)


path = sys.stdin.readline().strip()
job = Job(path, "3 expenses, total 59500")
print("wrote %d characters" % run_job(job))
