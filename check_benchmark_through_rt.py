#!/usr/bin/env python3
"""The benchmark's programs, as its harness runs them, in both runtimes
(9.0, M3).

    python check_benchmark_through_rt.py

benchmark/run.py runs every program of its corpus under the budget the
program's task needs (`needs`), with its input, the stand-in server that
counts what reaches it, its vendored library on the Python path, a secret
in the environment, a timeout and a memory cap - each program as it was
written to run - and records what Sabline made of it: the static step,
how the run ended (its status, the effect a refusal named, a limit, each
problem's code and message, the start of what it printed), what the
harness observed happen, and the verdict. The agreement gate runs these
programs under `io`; this runs them under their own budgets, through the
harness, once with SABLINE_REFERENCE_RUNTIME unset and once set to `rust`
(sabline/through_rt.py - every run there goes through sabline-rt, the
network, Python and tools relayed back to the package), and compares
Sabline's record of each program, field for field. Exit 1 on a difference.

The package's runs are made with `--no-native`: sabline-rt interprets, and
the reference the agreement gate holds it to is the package's interpreter
(sabline/run_dump.py). The package's native engine words two errors more
generally than its interpreter - E407 without the operator, E602 as the
slow path of `get` does, each at the function's line - which `fuzz_native.py`
does not see, since it compares the exit status and the output; that is the
package's own, and plan/9.0-m3-progress.md records it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
VARIABLE = "SABLINE_REFERENCE_RUNTIME"
# what is compared of each program's Sabline record
FIELDS = ("before", "during", "observed", "task", "verdict", "evidence")


def harness(runtime: str, out: Path) -> dict[str, Any]:
    """benchmark/run.py's results, with the runtime chosen."""
    env = dict(os.environ)
    env.pop(VARIABLE, None)
    if runtime == "rust":
        env[VARIABLE] = "rust"
    env["PYTHONIOENCODING"] = "utf-8"
    done = subprocess.run(
        [sys.executable, str(HERE / "benchmark" / "run.py"), "--no-native",
         "--json", str(out), "--md", str(out.with_suffix(".md"))],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, cwd=str(HERE), stdin=subprocess.DEVNULL, timeout=3600)
    if not out.exists():
        raise SystemExit(f"check_benchmark_through_rt: the harness wrote no "
                         f"results under {runtime} (status {done.returncode}):"
                         f"\n{done.stdout[-1500:]}\n{done.stderr[-1500:]}")
    results: dict[str, Any] = json.loads(out.read_text(encoding="utf-8"))
    return results


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sabline-bench-rt-") as tmp:
        work = Path(tmp)
        python = harness("python", work / "python.json")
        rust = harness("rust", work / "rust.json")
    mine = {p["id"]: p["tools"]["sabline"] for p in python["programs"]}
    theirs = {p["id"]: p["tools"]["sabline"] for p in rust["programs"]}
    found = []
    if sorted(mine) != sorted(theirs):
        found.append(f"the two runs hold different programs: "
                     f"{sorted(set(mine) ^ set(theirs))}")
    ran = 0
    for pid in sorted(set(mine) & set(theirs)):
        a, b = mine[pid], theirs[pid]
        ran += bool((a.get("during") or {}).get("ran"))
        for field in FIELDS:
            if a.get(field) != b.get(field):
                found.append(f"{pid}: {field}: python {json.dumps(a.get(field))[:400]}"
                             f"\n      sabline-rt {json.dumps(b.get(field))[:400]}")
                break
    for line in found[:40]:
        print("  " + line)
    print(f"check_benchmark_through_rt: {len(mine)} programs under their own "
          f"budgets, {ran} of them run, {len(found)} difference(s)")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
