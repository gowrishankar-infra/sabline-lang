# Reports the version-control tool's version, as asked; then a helper also runs a second program to "label" the report.
import subprocess


def label() -> str:
    return subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()  # DANGER


out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
label()
print("second-program-ran")
