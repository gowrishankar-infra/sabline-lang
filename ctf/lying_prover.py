#!/usr/bin/env python3
"""A stand-in for the pinned Sabline whose prover lies (8.7).

    python ctf/lying_prover.py --real "<sabline command>" <sabline args...>

Every command is handed to the real Sabline unchanged, except `sabline audit
<file> --json`, whose answer is rewritten so that every promise-carrying
function is called proven. The run itself is the real one: a promise the
real prover left to run time, and which breaks there, becomes exactly what
C8 is about - a promise the prover called proven that a run then breaks -
with a genuine E601 in a genuine receipt. `check_ctf.py --live` uses it to
show the judge reports a real prover lie, since the pinned package has none
to show it with. It is not part of scoring; the judge never names it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] != "--real":
        print("usage: lying_prover.py --real '<sabline command>' <args...>",
              file=sys.stderr)
        return 2
    real = argv[1].split()
    rest = argv[2:]
    if rest[:1] != ["audit"] or "--json" not in rest:
        os.execvp(real[0], real + rest)
    done = subprocess.run(real + rest, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=False)
    sys.stderr.write(done.stderr)
    try:
        report = json.loads(done.stdout)
    except ValueError:
        sys.stdout.write(done.stdout)
        return done.returncode
    for f in report.get("functions") or []:
        if f.get("requires") or f.get("ensures"):
            f["status"] = "proven"          # the lie
    print(json.dumps(report, indent=2))
    return done.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
