"""textcase: small text helpers.

The library the Starlark control depends on, present beside the program as
a vendored package would be. The hallucinated-name programs in this
category load modules that are not present, so their load fails.
"""


def shout(s):
    return s.upper()
