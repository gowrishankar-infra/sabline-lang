# The control: runs the version-control tool once and reports it, which is all the task needs.

out = run_program("git", ["--version"])
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
