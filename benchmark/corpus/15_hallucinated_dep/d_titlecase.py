# The control: formats text through a "textcase" helper vendored beside
# this program (the package exists), so the import resolves and the
# program runs clean.
import textcase

print(textcase.shout("sabline"))
