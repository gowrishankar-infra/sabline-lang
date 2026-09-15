"""The version, where Velaris is installed, and how to start it again.
"""
import os
import sys
from typing import Any


# The directory that holds this package - and, beside it, stdlib/ and
# LLM.md: the repository, site-packages, or an ejected runtime/.
_INSTALL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PACKAGE_DIR = os.path.join(_INSTALL_DIR, "velaris")


def _launch_command() -> list[Any]:
    """How another process starts this same Velaris: the child a check runs
    in under its ceiling, a pool worker, a conformance case. A frozen
    executable is its own command. Otherwise it is this package's
    __main__.py by path, which puts the directory holding this package
    first on the child's sys.path - so the child cannot import another
    Velaris installed elsewhere, as `python -m velaris` could."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.join(_PACKAGE_DIR, "__main__.py")]


VERSION = "8.2.1"


# Every compiler error and every runtime refusal ends with one line
# pointing here, so a person - or a model - who meets an error has a
# card to read (8.0). It is llms.txt, the language for a model, served
# at the documentation site; build_docs.py writes it from LLM.md, and a
# CI test fetches it to prove the card is really there. --json and SARIF
# carry it as a field rather than a trailing line.
REFERENCE_URL = "https://gowrishankar-infra.github.io/velaris-lang/llms.txt"
