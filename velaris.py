#!/usr/bin/env python3
"""Start Velaris from a checkout: `python velaris.py program.vel`.

Until 8.2 this file was the compiler. It is now the `velaris` package
beside this file (decisions/0001-split-the-file.md), and this file only
starts it, so the commands the documents show - and the suites that run
velaris by this path - keep working here. pip installs the package and its
`velaris` command; this file is not installed.
"""
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if not sys.path or os.path.abspath(sys.path[0] or os.curdir) != _here:
    sys.path.insert(0, _here)

from velaris.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
