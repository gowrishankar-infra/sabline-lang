# The control: measures a label through a vendored native library that does nothing else.
import nativefmt

print("length " + str(nativefmt.measure("report")))
