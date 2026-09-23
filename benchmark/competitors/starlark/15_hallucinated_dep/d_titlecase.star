# The control: formats text through a "textcase" helper vendored beside
# this program (the package exists), so the load resolves and the
# program runs clean.
load("textcase.star", "shout")

print(shout("sabline"))
