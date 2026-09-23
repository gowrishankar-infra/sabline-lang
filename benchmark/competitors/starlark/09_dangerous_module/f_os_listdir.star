# Lists the current directory through os.listdir's equivalent, list_dir, from a helper named describe.


def describe(folder):
    listing = list_dir(folder)  # DANGER
    return "module-reached: listing came back (%s)" % str(len(listing) > 0).lower()


print(describe("."))
