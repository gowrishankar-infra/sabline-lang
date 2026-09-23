# A helper named like a text utility runs a shell command.


def tidy(text):
    return run_command("echo " + text)  # DANGER


print(tidy("spawned-child-ran"))
