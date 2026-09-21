"""`velaris_magic`, which is now `sabline_magic`.

Velaris was renamed Sabline in 8.6.0. A notebook cell that says
`%load_ext velaris_magic` is saved in someone's .ipynb, and a rename that
breaks it is a breaking change (STABILITY.md rule 1).
This module is the old name, kept so that a configuration written before
the rename keeps working, and removed no sooner than 9.0 (STABILITY.md).
It is an alias, not a copy: it hands back the `sabline_magic` module itself, so
there is one implementation and it cannot drift.
"""
import sys

import sabline_magic as _module
from sabline import naming as _naming

_naming.say_renamed("velaris_magic", "sabline_magic", "`velaris_magic`")

if __name__ != "__main__":
    sys.modules[__name__] = _module
else:
    raise SystemExit(
        "velaris_magic is a notebook extension: %load_ext sabline_magic")
