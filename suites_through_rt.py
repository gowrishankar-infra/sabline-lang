#!/usr/bin/env python3
"""M3's fourth criterion, measured: the suites asked through sabline-rt and
counted per question (9.0, M3).

    python suites_through_rt.py [SUITE ...]

plan/9.0.md's M3 asks that check_library.py, check_fallible.py,
check_money.py, check_hostile.py, check_self_budget.py, check_pool.py and
check_receipts.py pass against sabline-rt, and that check_sandbox.py's
escapes are refused and its honest programs run, and M2's five suites
(suite_runtime.py) ask their run questions of it too. Each suite here is
run whole with SABLINE_REFERENCE_RUNTIME=rust - M2's five with
`--runtime rust` as well, so that their check questions go to sabline-rt
too - and every run it makes, in its own process or in any it starts, goes
through sabline-rt the way a user's would and writes one line saying who
answered it (sabline/through_rt.py's log): sabline-rt - a run of the
network, Python or a tool included, whose calls it relays back to the
package (decided on 2026-10-11); the checks or the prover, which refused
it before anything ran; or the Python package, and why - the eval
profile, `sabline trace`.

What a suite prints is written to the same log as it prints it, so each
run is counted against the question whose line comes after it: the
question it was made for. A suite prints a question's verdict after the
runs it made for it, in every suite here, threads included - each joins
its threads before it judges them.

For each suite it says how many questions passed and failed, and of the
questions that made a run, how many were answered by sabline-rt alone and
how many had a run the package made or the checks refused - and of every
run, who answered it. A question that made no run - a check, an audit, a
pool's bookkeeping - is counted as such, never as one sabline-rt answered.
Every question that failed is named, as a difference by design (BY_DESIGN,
with the rung that closes it) or not.

Exit 1 when a question fails that is not by design, or a suite ends with a
status its questions do not explain.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import suite_runtime  # noqa: E402

# (suite, its words) - M2's five ask their check questions of sabline-rt too
SUITES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("check_library.py", ()),
    ("check_money.py", ()),
    ("check_hostile.py", ()),
    ("check_self_budget.py", ()),
    ("check_pool.py", ()),
    ("check_receipts.py", ()),
    # M3's third criterion's own suite: its escapes and honest programs run
    # from the command line, under their budgets, against its servers
    ("check_sandbox.py", ()),
    ("check_fallible.py", ("--runtime", "rust")),
    ("check_termination.py", ("--runtime", "rust")),
    ("check_refusals.py", ("--runtime", "rust")),
    ("check_secret.py", ("--runtime", "rust")),
    ("check_error_messages.py", ("--runtime", "rust")),
)

# A question that fails against sabline-rt by design, until the rung named:
# (suite, the start of its label, why).
BY_DESIGN: tuple[tuple[str, str, str], ...] = (
    ("check_library.py",
     "a run returns its receipt: an in-toto Statement of receipt/v1",
     "it asks that the receipt's producer version is this package's, and a "
     "run through sabline-rt is sabline-rt's (decided on 2026-10-11: waits "
     "for M4)"),
    ("check_library.py",
     "...with the budget, the parameters, the declassification and its",
     "it asks that an unbounded sabline.run()'s confinement is none, which "
     "it is in this package - the run is in the caller's own process, which "
     "Sabline never confines. From 9.0's M4 a run through sabline-rt is in "
     "sabline-rt's process, which it does confine, so the same question "
     "answers the platform's level there. check_confine.py asks both"),
)

# A line that gives a question's verdict, in the words these suites use.
VERDICT = re.compile(r"^\s*(ok|PASS|FAIL|FINDING|WRONG|BROKEN|NOT ENFORCED|"
                     r"UNEXPECTED|RAW CRASH|ESCAPED|skip|not asked)\b")
FAILED = ("FAIL", "FINDING", "WRONG", "BROKEN", "NOT ENFORCED", "UNEXPECTED",
          "RAW CRASH", "ESCAPED")
PASSED = ("ok", "PASS")

# Run in the suite's process: its standard output, also written to the log
# a line at a time, and then the suite itself, as `python SUITE WORDS`.
TEE = r"""
import json, os, runpy, sys
LOG = os.environ["SABLINE_THROUGH_RT_LOG"]


class Tee:
    def __init__(self, real):
        self._real, self._held = real, ""

    def write(self, text):
        n = self._real.write(text)
        self._held += text
        while "\n" in self._held:
            line, self._held = self._held.split("\n", 1)
            with open(LOG, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"printed": line}) + "\n")
        return n

    def flush(self):
        self._real.flush()

    def __getattr__(self, name):
        return getattr(self._real, name)


sys.stdout = Tee(sys.stdout)
suite = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(suite)))
runpy.run_path(suite, run_name="__main__")
"""


def ask(suite: str, words: tuple[str, ...]) -> tuple[int, list[dict[str, Any]], str]:
    """Run one suite through sabline-rt: (its status, the log, its output)."""
    fd, log = tempfile.mkstemp(prefix="sabline-suite-", suffix=".jsonl")
    os.close(fd)
    env = dict(os.environ)
    env[suite_runtime.VARIABLE] = "rust"
    env[suite_runtime.RUN_LOG] = log
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        done = subprocess.run([sys.executable, "-c", TEE, str(HERE / suite), *words],
                              cwd=str(HERE), env=env, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=7200)
        entries = []
        with open(log, encoding="utf-8") as fh:
            for line in fh:
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue
    finally:
        os.unlink(log)
    return done.returncode, entries, done.stdout + done.stderr


def by_question(entries: list[dict[str, Any]]) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """(verdict, the line, the runs made for it) for each question, in order;
    runs after the last question are the suite's own, under ''."""
    out, pending = [], []
    for entry in entries:
        if "answered_by" in entry:
            pending.append(entry)
            continue
        line = str(entry.get("printed", ""))
        found = VERDICT.match(line)
        if found:
            out.append((found.group(1), line.strip(), pending))
            pending = []
    if pending:
        out.append(("", "(after the last question)", pending))
    return out


def counted(runs: list[dict[str, Any]]) -> dict[str, int]:
    """How many runs each answered, as suite_runtime.Tally.answered counts."""
    out: dict[str, int] = {}
    for r in runs:
        key = r["answered_by"] if r["answered_by"] == "sabline-rt" \
            else f"package: {r.get('why')}"
        out[key] = out.get(key, 0) + 1
    return out


def kind(runs: list[dict[str, Any]]) -> str:
    """A question's runs, in one word: `package` when the Python package made
    one of them, `checks` when the checks refused one and sabline-rt made the
    rest, `sabline-rt` when it made every one."""
    whys = {r.get("why") for r in runs if r["answered_by"] != "sabline-rt"}
    if whys - {"checks"}:
        return "package"
    return "checks" if whys else "sabline-rt"


def by_design(suite: str, line: str) -> str | None:
    for name, start, why in BY_DESIGN:
        words = line.split(None, 1)
        label = words[1].strip() if len(words) > 1 else ""
        if name == suite and label.startswith(start):
            return why
    return None


def measure(suite: str, words: tuple[str, ...]) -> tuple[bool, list[str]]:
    """(whether it passed but for its differences by design, what it says)."""
    status, entries, output = ask(suite, words)
    questions = by_question(entries)
    said = [f"{suite}{' ' + ' '.join(words) if words else ''}"]
    verdicts = [v for v, _, _ in questions if v]
    passed = sum(1 for v in verdicts if v in PASSED)
    failed = [(line, runs) for v, line, runs in questions if v in FAILED]
    skipped = sum(1 for v in verdicts if v in ("skip", "not asked"))
    designed = [(line, by_design(suite, line)) for line, _ in failed]
    unexplained = [line for line, why in designed if why is None]
    ran = [kind(runs) for v, _, runs in questions if v and runs]
    alone, refused = ran.count("sabline-rt"), ran.count("checks")
    kept = len(ran) - alone - refused
    runs = counted([r for _, _, rs in questions for r in rs])
    said.append(f"  questions: {len(verdicts)} - {passed} passed, {len(failed)} "
                f"failed ({len(failed) - len(unexplained)} by design), "
                f"{skipped} skipped or not asked")
    said.append(f"  of the {len(ran)} that ran a program: {alone} answered by "
                f"sabline-rt alone, {refused} with a run the checks refused, "
                f"{kept} with a run the Python package made; "
                f"{len(verdicts) - len(ran)} ran none")
    said.append(f"  runs: {sum(runs.values())} - "
                + suite_runtime.answered_line(runs))
    for (line, rs), (_, why) in zip(failed, designed):
        said.append(f"  {'by design' if why else 'FAILED'}: {line[:160]}")
        if why:
            said.append(f"      {why}")
        if rs:
            said.append("      its runs: " + suite_runtime.answered_line(counted(rs)))
    explained = (status == 0) == (not failed)
    if not verdicts:
        said.append("  no question's verdict was read: " + output.strip()[-600:])
        explained = False
    elif not explained:
        said.append(f"  it ended with status {status}: " + output.strip()[-600:])
    return explained and not unexplained and bool(verdicts), said


def main(argv: list[str]) -> int:
    import check_agreement
    check_agreement.rt_binary()          # built, as the gate builds it
    chosen = [s for s in SUITES if not argv or s[0] in argv]
    bad = []
    for suite, words in chosen:
        good, said = measure(suite, words)
        for line in said:
            print(line)
        if not good:
            bad.append(suite)
    print(f"suites_through_rt: {len(chosen)} suites asked through sabline-rt, "
          f"{len(chosen) - len(bad)} with no question failing that is not by design"
          + (f"; not: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
