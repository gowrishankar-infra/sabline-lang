"""textcase: small text helpers.

The library the Python control depends on, present beside the program as
an installed package would be. The hallucinated-name programs in this
category import modules that are not present, so they fail to import.
"""


def shout(s: str) -> str:
    return s.upper()
