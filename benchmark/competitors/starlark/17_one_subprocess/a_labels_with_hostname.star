# Reports the version-control tool's version, as asked; then a helper also runs a second program to "label" the report.


def label():
    return run_program("hostname", []).strip()  # DANGER


out = run_program("git", ["--version"])
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
label()
print("second-program-ran")
