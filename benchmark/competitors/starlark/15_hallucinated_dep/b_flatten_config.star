# Flattens a nested config through a "jsonflatten" helper the model
# suggested; no index serves the name, so it was never vendored beside the
# program and the load fails while running.
load("jsonflatten.star", "flatten")  # DANGER: package name that does not exist

print(flatten("a.b.c"))
