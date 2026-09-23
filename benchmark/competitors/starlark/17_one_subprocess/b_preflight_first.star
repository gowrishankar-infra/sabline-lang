# A "preflight" runs a second program first, ignoring any failure, and then the task runs the version-control tool.
# NOT-LIKE-FOR-LIKE: Starlark has no try: a failed preflight, which the Python version ignores, stops the program, and the git task after it.

run_program("hostname", [])  # DANGER
print("second-program-ran")
out = run_program("git", ["--version"])
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
