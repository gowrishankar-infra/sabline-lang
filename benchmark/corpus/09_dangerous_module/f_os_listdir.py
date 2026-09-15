# Lists the current directory through the os module from a helper named describe.
import os


def describe(folder: str) -> str:
    listing = os.listdir(folder)  # DANGER
    return "module-reached: listing came back (%s)" % str(len(listing) > 0).lower()


print(describe("."))
