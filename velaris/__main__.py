"""`python -m velaris`, and the command another process starts this
Velaris with (velaris.version._launch_command): by path, for the check
ceiling's child, a pool worker and a conformance case."""
import os
import sys

if not __package__:
    # Started by its path. Then sys.path[0] is this directory, where the
    # package's modules would be found under their bare names; the
    # directory that holds the package goes there instead.
    _here = os.path.dirname(os.path.abspath(__file__))
    if sys.path and os.path.abspath(sys.path[0] or os.curdir) == _here:
        sys.path[0] = os.path.dirname(_here)
    else:
        sys.path.insert(0, os.path.dirname(_here))

from velaris.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
