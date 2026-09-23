# Retries a step through a "retrywrap" helper the model suggested; no
# index serves the name, so it was never vendored beside the program and
# the load fails while running.
load("retrywrap.star", "retry")  # DANGER: package name that does not exist

print(retry("sync"))
