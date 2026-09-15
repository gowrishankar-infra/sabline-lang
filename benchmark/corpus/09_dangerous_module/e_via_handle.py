# Opens a pipe to a shell command as a handle and reads from it.
import os


def open_pipe(cmd: str) -> str:
    pipe = os.popen(cmd)  # DANGER
    out = pipe.read()
    pipe.close()
    return out


print(open_pipe("echo spawned-child-ran").strip())
