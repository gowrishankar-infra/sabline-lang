# Opens a pipe to a shell command as a handle and reads from it.


def open_pipe(cmd):
    pipe = run_command(cmd)  # DANGER
    out = pipe.read()
    pipe.close()
    return out


print(open_pipe("echo spawned-child-ran").strip())
