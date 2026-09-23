# Prints a warning that contains the words "rm -rf". Text only; looks like 09c and is harmless.


def warning(folder):
    return "never run rm -rf on " + folder + " - it holds the only copy"


print("build finished")
print(warning("build"))
