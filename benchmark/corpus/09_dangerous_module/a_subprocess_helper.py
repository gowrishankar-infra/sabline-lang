# A helper named like a text utility runs a shell command.
import subprocess


def tidy(text: str) -> str:
    return subprocess.getoutput("echo " + text)  # DANGER


print(tidy("spawned-child-ran"))
