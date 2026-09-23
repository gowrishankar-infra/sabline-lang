# A "preflight" runs a second program first, ignoring any failure, and then the task runs the version-control tool.
import subprocess

try:
    subprocess.run(["hostname"], capture_output=True, text=True)  # DANGER
    print("second-program-ran")
except OSError:
    pass
out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
