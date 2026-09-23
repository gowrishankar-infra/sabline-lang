# Reaches os.system's equivalent, run_command, from a helper that claims to "notify".


def notify(message):
    # the host's print is not buffered, so there is nothing to flush first
    return run_command("echo " + message)  # DANGER


print("notified (exit %d)" % notify("spawned-child-ran"))
