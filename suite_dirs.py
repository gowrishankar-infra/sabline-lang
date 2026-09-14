"""A directory of its own for each test suite.

Two suites run at once from one checkout - two Python versions side by
side, or the same suite twice - must not write the same file. So each
suite asks for a directory under the system's temporary directory, points
VELARIS_CACHE_DIR inside it, which every velaris the suite starts reads for
its proof cache, and writes its scratch files there instead of beside the
source. The directory is removed when the suite exits.

    from suite_dirs import isolate
    WORK = isolate("check_money")

It is not part of Velaris: the wheel includes only the modules pyproject.toml
names.
"""
import atexit
import os
import shutil
import tempfile
from pathlib import Path


def isolate(name: str) -> Path:
    """A fresh directory for the suite `name`, with the proof cache of
    everything the suite starts inside it."""
    work = Path(tempfile.mkdtemp(prefix=f"velaris-{name}-"))
    cache = work / "cache"
    cache.mkdir()
    os.environ["VELARIS_CACHE_DIR"] = str(cache)
    atexit.register(shutil.rmtree, work, ignore_errors=True)
    return work
