#!/usr/bin/env python3
"""A stand-in for the pinned Sabline whose run escapes its write grant (8.7).

    python ctf/escaping_runtime.py --real "<sabline command>" <sabline args...>

Every command is handed to the real Sabline unchanged, and the run is the
real one - same budget, same receipt, same confinement. The one difference
is that before a `run` or an `eval` this stand-in writes a file into the
run's own working directory, which is outside the one directory a C3 run
may write. That is what a write escaping a grant looks like from outside:
a file, under a tree the run could reach, that the grant did not allow.

`check_ctf.py --live` uses it to show the judge sees such a write. It is not
part of scoring; the judge never names it, and the pinned package writes no
such file, so the same submission holds against the real thing.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ESCAPED = "escaped-outside-the-grant.txt"


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "--real":
        print("usage: escaping_runtime.py --real '<sabline command>' "
              "<args...>", file=sys.stderr)
        return 2
    real = argv[1].split()
    rest = argv[2:]
    if rest[:1] in (["run"], ["eval"]):
        # fixed content, so two runs that differ only in a planted nonce
        # still print and write the same: this stand-in is about the write
        # escaping the grant, and nothing else
        Path(ESCAPED).write_text("escaped\n", encoding="utf-8")
    os.execvp(real[0], real + rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
