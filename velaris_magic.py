"""Velaris in a notebook: %%velaris cells that run in a box.

    %pip install velaris-lang
    %load_ext velaris_magic

    %%velaris --allow io
    fn total(xs: List of Int) -> Int
        ensures result >= 0
    {
        let sum = 0
        for x in xs {
            if x > 0 {
                sum = sum + x
            }
        }
        return sum
    }

    fn main() uses io {
        print(total([25, -40, 450]))
    }

The cell prints what the program printed. `--audit` shows what it can
touch and how much of its promises are proven before running - useful
when the code in the cell came from a model rather than from you.

    %%velaris --audit --allow io,fs
    ...

Effects outside --allow are refused while the program runs, whatever
the source claims. Default budget is io, which lets a cell print and
nothing else.
"""
import shlex
from typing import Any

try:
    from IPython.core.magic import Magics, cell_magic, magics_class
except ImportError:                       # pragma: no cover
    raise SystemExit("this needs IPython: pip install ipython")

import velaris

ALL = ("io", "fs", "net", "clock", "rand", "ffi")


@magics_class
class VelarisMagics(Magics):  # type: ignore[misc]  # IPython is not installed by the lint job

    @cell_magic  # type: ignore[misc]  # IPython is not installed by the lint job
    def velaris(self, line: Any, cell: Any) -> None:
        words = shlex.split(line or "")
        allow = {"io"}
        want_audit = "--audit" in words
        want_check = "--check" in words
        if "--allow" in words:
            asked = words[words.index("--allow") + 1]
            allow = {n.strip() for n in asked.split(",") if n.strip()}
            try:                      # the whole grammar: fs:read:./x,
                velaris.Budget.parse(asked)    # net:host:443, @count
            except velaris.BudgetError as e:
                print(str(e))
                return

        if want_audit or want_check:
            report = velaris.audit(cell)
            if not report.ok:
                for p in report.problems:
                    print(f"line {p.line}: [{p.code}] {p.message}")
                    for fix in (p.fixes or [])[:2]:
                        print(f"    try: {fix}")
                return
            print("can touch:  " + (", ".join(report.effects) or "nothing"))
            if report.proven_share is not None:
                print(f"proven:     {report.proven_share:.0f}% of promises, "
                      f"before running")
            for warning in report.warnings:
                print(f"note:       {warning}")
            if want_check:
                return
            print("-" * 46)

        result = velaris.run(cell, allow=allow)
        if result.problems:
            for p in result.problems:
                print(f"line {p.line}: [{p.code}] {p.message}")
                for fix in (p.fixes or [])[:2]:
                    print(f"    try: {fix}")
            if result.refused_effect:
                print(f"\n(this cell allows {', '.join(sorted(allow))}; "
                      f"add --allow {result.refused_effect} to permit it)")
        if result.logs:
            print(result.logs, end="")
        if result.output:
            print(result.output, end="")


def load_ipython_extension(ipython: Any) -> None:
    ipython.register_magics(VelarisMagics)
