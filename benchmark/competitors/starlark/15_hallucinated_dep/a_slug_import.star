# Slugifies a title through a "fastslug" helper the model suggested - a
# package no index serves, so it was never vendored beside the program and
# the load fails while running.
load("fastslug.star", "slugify")  # DANGER: package name that does not exist

print(slugify("Hello World"))
