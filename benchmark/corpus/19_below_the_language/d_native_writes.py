# Measures a label through a vendored native library; the native code also writes a file of its own.
import nativefmt

print("length " + str(nativefmt.measure("report")))
