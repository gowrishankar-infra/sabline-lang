# The control: runs the version-control tool once and reports it, which is all the task needs.
import subprocess

out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
