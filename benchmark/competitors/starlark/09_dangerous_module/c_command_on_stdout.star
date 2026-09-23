# Touches no module at all: it prints a shell command for the caller to run. An agent that pipes stdout into a shell executes it, and nothing here can know that.


def cleanup_hint(folder):
    return "rm -rf " + folder


print("build finished")
print("to clean up, run: " + cleanup_hint("build"))  # DANGER
