"""A directory of its own for each test suite.

Two suites run at once from one checkout - two Python versions side by
side, or the same suite twice - must not write the same file. So each
suite asks for a directory under the system's temporary directory and
writes its scratch files there instead of beside the source. The
directory is removed when the suite exits.

    from suite_dirs import isolate
    WORK = isolate("check_money")

It is not part of Sabline: the wheel includes only what pyproject.toml
names.
"""
import atexit
import shutil
import tempfile
from pathlib import Path


def isolate(name: str) -> Path:
    """A fresh directory for the suite `name`, removed when it exits."""
    work = Path(tempfile.mkdtemp(prefix=f"sabline-{name}-"))
    atexit.register(shutil.rmtree, work, ignore_errors=True)
    return work
