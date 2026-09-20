"""`velaris_mcp_install`, which is now `sabline_mcp_install`.

Velaris was renamed Sabline in 8.6.0. A script that calls
`python -m velaris_mcp_install` is in someone's setup, and a rename that
breaks it is a breaking change (STABILITY.md rule 1).
This module is the old name, kept so that a configuration written before
the rename keeps working, and removed no sooner than 9.0 (STABILITY.md).
It is an alias, not a copy: it hands back the `sabline_mcp_install` module itself, so
there is one implementation and it cannot drift.
"""
import sys

import sabline_mcp_install as _module
from sabline import naming as _naming

_naming.say_renamed("velaris_mcp_install", "sabline_mcp_install", "`velaris_mcp_install`")

if __name__ != "__main__":
    sys.modules[__name__] = _module
else:
    sys.exit(_module.main(sys.argv[1:]))
