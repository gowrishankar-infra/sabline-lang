# The control: runs the version-control tool with the argument the input names, from a helper.
import subprocess
import sys


def vcs(argument: str) -> str:
    return subprocess.run(["git", argument], capture_output=True, text=True).stdout


out = vcs(sys.stdin.readline().strip())
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
