"""`velaris_mcp`, which is now `sabline_mcp`.

Velaris was renamed Sabline in 8.6.0. An MCP client's config that says
`python -m velaris_mcp` is in a file on someone's machine, and a rename
that breaks it is a breaking change (STABILITY.md rule 1).
This module is the old name, kept so that a configuration written before
the rename keeps working, and removed no sooner than 9.0 (STABILITY.md).
It is an alias, not a copy: it hands back the `sabline_mcp` module itself, so
there is one implementation and it cannot drift.
"""
import sys

import sabline_mcp as _module
from sabline import naming as _naming

_naming.say_renamed("velaris_mcp", "sabline_mcp", "`velaris_mcp`")

if __name__ != "__main__":
    sys.modules[__name__] = _module
else:
    sys.exit(_module.main())
