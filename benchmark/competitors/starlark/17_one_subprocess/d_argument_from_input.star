# The control: runs the version-control tool with the argument the input names, from a helper.


def vcs(argument):
    return run_program("git", [argument])


out = vcs(read_line().strip())
print("vcs: ok" if out.startswith("git version") else "vcs: missing")
