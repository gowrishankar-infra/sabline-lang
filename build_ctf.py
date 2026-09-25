#!/usr/bin/env python3
"""docs/ctf.md, generated from the CTF's claims and status (8.7).

    python build_ctf.py            write docs/ctf.md
    python build_ctf.py --check    fail if it is not what the claims say

The page is the standing invitation: the claims, the rules a submission is
judged under, how it is scored, and where each claim stands. It is generated
from `ctf/claims.py` (the claims and their budgets) and `ctf/status.json`
(the pinned package and each claim's public status), so the page and the
judge cannot drift.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctf.claims import CLAIMS  # noqa: E402

OUT = HERE / "docs" / "ctf.md"
STATUS = HERE / "ctf" / "status.json"
REPO = "https://github.com/gowrishankar-infra/sabline-lang"


def page() -> str:
    st = json.loads(STATUS.read_text(encoding="utf-8"))
    claims_status = st["claims"]
    out: list[str] = []
    w = out.append

    w("# The Sabline capture-the-flag")
    w("")
    w("<!-- description: A standing invitation to get past a Sabline budget: "
      "ten claims, each a fixed budget and one thing no program under it may "
      "do, judged on free runners against the published package. -->")
    w("")
    w("A standing invitation to get past a Sabline budget, on infrastructure "
      "that already exists, with the people who succeed named. There is no "
      "money: it is not a bug bounty, and "
      "[SECURITY.md](" + REPO + "/blob/main/SECURITY.md) still says so.")
    w("")
    w("> [!NOTE]")
    w("> **A CTF that nobody attacks proves nothing, and this is not "
      "evidence that Sabline is secure.** The budget is not a security "
      "boundary on its own (SPEC.md section 6), whatever the CTF shows. This "
      "is a way to find the next defect earlier than the adversarial passes "
      "found the last four - and every break becomes a "
      "[test](" + REPO + "/blob/main/check_adversarial.py) the same week.")
    w("")

    w("## The claims")
    w("")
    w("Each claim is a **fixed budget**, one thing **no program under it can "
      "do**, and a **canary the judge controls**. You write the program (and, "
      "where a deployment would forward them, the words after `--`); "
      "everything else is fixed. The first version runs on **"
      f"{st['platform']} only**, against **{st['package']} {st['version']}** "
      "pinned by the hash of its wheel.")
    w("")
    w("The **confinement** column is the least operating-system confinement "
      "a scored run of that claim is held to, and a run that did not reach "
      "it is not scored. It is not `full` everywhere and the judge does not "
      "claim it is: a net grant names a host no kernel here holds by name, "
      "a program carrying a promise starts the prover's threads before the "
      "confinement is applied, and the runs scored by the tool door write "
      "no receipt to read a level from.")
    w("")
    w("| Claim | Budget | No program under it | Confinement | Status |")
    w("|---|---|---|---|---|")
    for c in CLAIMS:
        entry = claims_status.get(c.id, {})
        status = _status_text(entry)
        level = entry.get("confinement", c.min_confinement)
        w(f"| {c.id} | `{c.budget}` | {c.invariant} | `{level}` | "
          f"{status} |")
    w("")
    w("A claim broken through something "
      "[docs/known-open.md](known-open.md) already lists was a wrong claim: "
      "the claim is fixed, and the finder is credited. C9 is the strongest - "
      "`ffi:gc` widens no OS policy, so a run under it is held to the same "
      "kernel confinement as `io` alone, and what holds it is Landlock and "
      "seccomp, not the language.")
    w("")

    w("## How a submission is judged")
    w("")
    w("The judge's code is "
      "[`ctf/`](" + REPO + "/blob/main/ctf/) in this repository, so anyone "
      "can read what scores a submission. A private companion repository pins "
      "it by commit and runs it; the safety rests on the per-run canaries and "
      "nonces, made fresh each run, not on secrecy.")
    w("")
    w(f"- The submission is **hashed before the canaries exist**, so it "
      f"cannot contain them, and run **{st['runs_per_submission']} times** "
      "with fresh canaries each time.")
    w("- Each run is made against the pinned, published package under the "
      "operating-system confinement **its own claim needs** - the column "
      "above - and a run that does not reach it is **not scored**.")
    w("- Every run passes `--no-native`, and the judge **refuses to score "
      "at all** on a machine where native compilation is available anyway, "
      "so that no answer of its turns on whether `llvmlite` happens to be "
      "installed.")
    w("- **Only the judge's own observers count**: hashes of every tree the "
      "run can reach but the one directory its budget lets it write, a "
      "listener's log, a scan for a planted nonce, a second run that "
      "differs only in the nonce - compared on **stdout, stderr and the "
      "files written**, so a leak encoded, or written with `log`, counts - "
      "the tool door's transcript against both of its ceilings, and the "
      "prover's answer, for every file a submission brings, against the "
      "run's receipt. The receipt is written in a directory of the judge's "
      "own, outside the run's root entirely, and checked afterwards for "
      "having been changed. Every piece of evidence comes from a channel "
      "the judge controls and the program cannot write to; a submission's "
      "own exit code and transcript are **never** evidence.")
    w("- The judge reports one of three answers: the claim **held** on every "
      "run, it was **broken on k of the runs** (with the evidence of each), "
      "or it **did not run**.")
    w("- A `broken` verdict is replayed on a second runner and checked by a "
      "person before any credit. After the fix, the case goes into "
      "`check_adversarial.py` that week, and a public job in this repository "
      "replays it - broken on the version before, holding on the one after.")
    w("")
    w("The judge is shown to catch a real break before it is trusted to find "
      "a new one: its self-test runs the C1 read submission against a build "
      "with the 8.1.1 double-dash hole "
      "([advisory](" + REPO + "/blob/main/advisory-cli-double-dash.md)) and "
      "must report it broken, and against the pinned package it must hold.")
    w("")

    w("## Submitting")
    w("")
    w("A submission is a directory with a `submission.json` naming the claim, "
      "the program, and any words to forward after `--`, plus the program "
      "itself. Send it **privately** - by "
      "[SECURITY.md](" + REPO + "/blob/main/SECURITY.md)'s address or "
      "GitHub's private vulnerability reporting - so a live escape is not "
      "public before its fix. Submissions are scored in a private repository; "
      "what becomes public is what follows a fix.")
    w("")
    w("```json")
    w('{"claim": "C1", "program": "attack.vel", "argv": ["--allow", "all"],')
    w('  "note": "what you think it does"}')
    w("```")
    w("")
    w("The finders are named in "
      "[HALL_OF_FAME.md](" + REPO + "/blob/main/HALL_OF_FAME.md). No points, "
      "no ranking: each fix earns one entry, and the first private report of "
      "a break wins it.")
    w("")
    return "\n".join(out)


def _status_text(entry: dict[str, str]) -> str:
    status = entry.get("status", "open")
    if status == "open":
        return "open"
    if status == "broken":
        fixed = entry.get("fixed_in", "")
        return f"broken, fixed in {fixed}" if fixed else "broken"
    return status


def main(argv: list[str]) -> int:
    text = page()
    if "--check" in argv:
        if not OUT.is_file():
            print("docs/ctf.md is not written (python build_ctf.py)")
            return 1
        if OUT.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            print("docs/ctf.md is not what the claims say "
                  "(python build_ctf.py)")
            return 1
        print(f"docs/ctf.md is current: {len(CLAIMS)} claims")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote docs/ctf.md: {len(CLAIMS)} claims, {len(text)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
