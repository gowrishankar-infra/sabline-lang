#!/usr/bin/env python3
"""A Velaris whose budget checks have been knocked out - what a fault in the
interpreter would amount to - run as the command line runs.

check_confine.py runs every escape target of check_sandbox.py and
check_adversarial.py through this, once under confinement and once with
--no-confine. With the language's own refusals gone, whatever still stops
the program is the operating system; whatever gets through is held by the
language alone. It is not part of Velaris and is not shipped.

    python tests/confine/faulty_runtime.py program.vel --allow io
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))

import velaris  # noqa: E402,F401
from velaris import cli  # noqa: E402


def _nothing(*_a: object, **_k: object) -> None:
    return None


def _any_path(_kind: str, path: str, _what: str, _line: int) -> str:
    return os.path.normcase(os.path.realpath(str(path)))


KNOCKED_OUT = {"spend": _nothing, "allow_path": _any_path,
               "allow_host": _nothing, "allow_module": _nothing,
               "ffi_reach": _nothing, "count_op": _nothing,
               "host_refusal": _nothing}

for name, module in list(sys.modules.items()):
    if name.startswith("velaris.") and module is not None:
        for function, replacement in KNOCKED_OUT.items():
            if function in vars(module):
                vars(module)[function] = replacement

if __name__ == "__main__":
    sys.argv = ["velaris"] + sys.argv[1:]
    sys.exit(cli.main())
