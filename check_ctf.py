#!/usr/bin/env python3
"""The CTF judge is well-formed, its observers catch a break, and every
claim holds on the pinned Sabline (8.7).

    python check_ctf.py            the checks that need no live run
    python check_ctf.py --live     also run the judge against Sabline

Without `--live` (every leg of CI, every OS): the claim table is well-formed,
`ctf/status.json` names exactly those claims, `docs/ctf.md` is what
`build_ctf.py` writes, `HALL_OF_FAME.md` has the CTF section, every holds
submission is well-formed and for the claim its directory names, each
observer catches a break given to it directly - no Sabline is run - and the
judge refuses a submission that names a claim other than the one the scorer
named.

With `--live` (one Linux job): the judge's self-test, every holds submission
judged against the pinned Sabline (which must hold), and the regressions
from the adversarial review of the judge: a proven promise beside a printed
"E601" holds 5 of 5; a stand-in whose prover lies is reported broken; the
self-test's read printed reversed, and hex-encoded, is broken on 8.1.1 and
holds on the pinned package; and a program using the clock and randomness
is not a false "broken". The self-test needs a build with the 8.1.1
double-dash hole to show the broken direction; the job installs
`velaris-lang==8.1.1` and points the judge at it with
`SABLINE_CTF_VULNERABLE`. `SABLINE_CTF_SABLINE` is the command for the
pinned package (default `sabline`).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctf import claims, judge  # noqa: E402

PASSED = [0]
FAILED: list[str] = []

SUBMISSIONS = HERE / "ctf" / "submissions"
# the judge's own submissions beside the holds examples, and the claim each
# is for; check_ctf judges them, live, for what its docstring says
SELFTESTS = {
    "selftest-c1-holds": "C1",
    "selftest-c1-reversed": "C1",
    "selftest-c1-hex": "C1",
    "selftest-c8-prints-e601": "C8",
    "selftest-c8-lie": "C8",
    "selftest-clock-rand": "C1",
}


def expect(what: str, ok: bool, detail: object = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != ""
                                     else ""))


# --------------------------------------------------------------------------
# the offline checks

def structure() -> None:
    print("the claim table")
    problems = claims.check_table()
    expect("every claim is well-formed", not problems, "; ".join(problems))
    st = json.loads((HERE / "ctf" / "status.json").read_text(
        encoding="utf-8"))
    listed = set(st["claims"])
    defined = {c.id for c in claims.CLAIMS}
    expect("status.json names exactly the defined claims",
           listed == defined, listed ^ defined)
    expect("the runs per submission is five",
           st["runs_per_submission"] == 5, st["runs_per_submission"])
    expect("it is pinned to a Linux, fully confined run",
           st["platform"] == "linux" and st["confinement"] == "full", st)
    pinned = (HERE / "ctf" / "pinned-linux.txt").read_text(encoding="utf-8")
    want = f"{st['package']}=={st['version']} " \
           f"--hash=sha256:{st['wheel_sha256']}"
    expect("pinned-linux.txt names the package and hash status.json does",
           want in pinned, want)
    # the claims that plant a secret are judged by difference, C6 included
    for cid in ("C1", "C2", "C5", "C9", "C10"):
        expect(f"{cid} is judged by difference as well as by the nonce scan",
               {"nonce_in_output", "canary_diff"}
               <= set(claims.BY_ID[cid].observers),
               claims.BY_ID[cid].observers)
    expect("C8 is run by the prover runner",
           claims.BY_ID["C8"].runner == "prover")


def wording() -> None:
    """A claim says what the judge observes, and no more."""
    print("the wording")
    c4 = claims.BY_ID["C4"]
    expect("C4 names the loopback listener the judge observes",
           "loopback listener" in c4.invariant, c4.invariant)
    expect("C4 does not claim what is not checked (any host)",
           "any host" not in c4.invariant, c4.invariant)
    expect("C4's note says broader egress observation is future work",
           "future work" in c4.note, c4.note)
    plan = (HERE / "plan" / "8.7.md").read_text(encoding="utf-8")
    expect("plan/8.7.md records broader egress observation as future work",
           "observe egress more broadly" in plan)


def generated() -> None:
    print("the generated page")
    import build_ctf
    expect("docs/ctf.md is what build_ctf.py writes",
           build_ctf.main(["--check"]) == 0)
    hall = (HERE / "HALL_OF_FAME.md").read_text(encoding="utf-8")
    expect("HALL_OF_FAME.md has the CTF section",
           "## The capture-the-flag" in hall, hall[:80])


def submissions() -> None:
    print("the holds submissions")
    base = SUBMISSIONS / "holds"
    for c in claims.CLAIMS:
        d = base / c.id
        expect(f"{c.id}: a holds submission exists", d.is_dir())
        if not d.is_dir():
            continue
        sub = judge.load_submission(d)
        expect(f"{c.id}: the submission is for {c.id}",
               sub.claim.id == c.id, sub.claim.id)
    for name, cid in SELFTESTS.items():
        d = SUBMISSIONS / name
        expect(f"{name} exists and is for {cid}",
               d.is_dir() and judge.load_submission(d).claim.id == cid)


def observers() -> None:
    """Each observer catches a break handed to it, with no Sabline run - so
    a green judge is one whose observers are known to fire, not one that
    never saw a break."""
    print("the observers")
    before = {"a.txt": "1"}
    expect("outside_write sees a created file",
           bool(judge.obs_outside_write(before, {"a.txt": "1", "b.txt": "2"})))
    expect("outside_write sees a changed file",
           bool(judge.obs_outside_write(before, {"a.txt": "2"})))
    expect("outside_write sees a removed file",
           bool(judge.obs_outside_write(before, {})))
    expect("outside_write is quiet when nothing changed",
           not judge.obs_outside_write(before, dict(before)))

    lst = judge.Listener("127.0.0.1", 0)
    lst.hits.append("127.0.0.1:5")
    can = _canary_stub(lst)
    expect("listener sees a connection", bool(judge.obs_listener(can)))
    can2 = _canary_stub(judge.Listener("127.0.0.1", 0))
    expect("listener is quiet with no connection",
           not judge.obs_listener(can2))

    c1 = claims.BY_ID["C1"]
    hit = _canary_stub(None)
    expect("nonce_in_output sees the file nonce in stdout",
           bool(judge.obs_nonce_in_output(hit, hit.nonce_file, "", c1)))
    expect("nonce_in_output is quiet without the nonce",
           not judge.obs_nonce_in_output(hit, "nothing here", "", c1))
    c5 = claims.BY_ID["C5"]
    expect("nonce_in_output sees the env nonce for C5",
           bool(judge.obs_nonce_in_output(hit, hit.nonce_env, "", c5)))
    c2 = claims.BY_ID["C2"]
    expect("nonce_in_output for C2 sees the nonce outside every grant",
           bool(judge.obs_nonce_in_output(hit, hit.nonce_out, "", c2)))
    expect("nonce_in_output for C2 sees the nonce in the working directory, "
           "which is outside the one directory C2 may read",
           bool(judge.obs_nonce_in_output(hit, hit.nonce_file, "", c2)))

    # the planted file is left out by exact path; a leak written to a new
    # file with the same name, anywhere else, is seen
    leak = _canary_stub(None)
    (leak.work / "secret.txt").write_text(leak.nonce_file + "\n",
                                          encoding="utf-8")
    expect("the planted secret.txt is not mistaken for a leak",
           not judge.obs_nonce_in_output(leak, "", "", c1))
    (leak.work / "sub").mkdir()
    (leak.work / "sub" / "secret.txt").write_text(
        "leaked: " + leak.nonce_file + "\n", encoding="utf-8")
    got = judge.obs_nonce_in_output(leak, "", "", c1)
    expect("a leak written to a new file named secret.txt is seen",
           bool(got) and "file:sub/secret.txt" in got[0].detail,
           [b.detail for b in got])

    same_files = {"file:out.txt": "same"}
    expect("canary_diff sees stdout that differs",
           bool(judge.obs_canary_diff("a", same_files, "b", same_files)))
    expect("canary_diff sees a written file that differs",
           bool(judge.obs_canary_diff("a", same_files, "a",
                                      {"file:out.txt": "other"})))
    expect("canary_diff is quiet when both runs printed and wrote the same",
           not judge.obs_canary_diff("a", same_files, "a", dict(same_files)))

    bad = [{"tool": "send_email", "arguments": {"to": "x@evil.com"}}]
    expect("tool_transcript sees a recipient outside the pattern",
           bool(judge.email_breaks(bad)))
    many = [{"tool": "send_email", "arguments": {"to": "a@corp.com"}}
            for _ in range(4)]
    expect("tool_transcript sees the ceiling passed",
           bool(judge.email_breaks(many)))
    ok = [{"tool": "send_email", "arguments": {"to": "a@corp.com"}}]
    expect("tool_transcript is quiet for an allowed call",
           not judge.email_breaks(ok))

    # prover_lie: the prover's answer against the receipt's exit, and
    # nothing the program printed is an input at all
    expect("prover_lie holds when the receipt records no E601",
           judge.obs_prover_lie(["double"], [], ("ok", None)).outcome
           == "holds")
    lie = judge.obs_prover_lie(["double"], [], ("failed", "E601"))
    expect("prover_lie is broken when every promise was called proven and "
           "the receipt says an ensures broke",
           lie.outcome == "broken" and lie.breaks[0].observer == "prover_lie",
           lie)
    mixed = judge.obs_prover_lie(["double"], ["tally"], ("failed", "E601"))
    expect("prover_lie does not score an E601 that may be a runtime-checked "
           "promise's", mixed.outcome == "did-not-run", mixed)
    with tempfile.TemporaryDirectory(prefix="ctf-receipt-") as td:
        rec = Path(td) / "r.json"
        rec.write_text(json.dumps({"predicate": {"exit": {
            "status": 1, "outcome": "failed", "code": "E601"}}}),
            encoding="utf-8")
        expect("the receipt's exit is read as (outcome, code)",
               judge._receipt_exit(rec) == ("failed", "E601"))
        expect("no receipt reads as None",
               judge._receipt_exit(Path(td) / "none.json") is None)


def refusals() -> None:
    """The scorer names the claim; a submission naming another is refused
    on every platform, and 'auto' is not a claim."""
    print("the claim is the scorer's")
    c1 = SUBMISSIONS / "holds" / "C1"
    rep = judge.judge("C2", c1, ["sabline"], runs=1,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    expect("a submission for C1 scored as C2 is refused",
           rep.verdict == "did not run" and "C1" in rep.error
           and "C2" in rep.error, (rep.verdict, rep.error))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc: int | None = judge.main(["run", "auto", str(c1)])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    expect("'auto' is not a claim the command line takes",
           rc == 2 and "invalid choice" in err.getvalue(), err.getvalue())
    with contextlib.redirect_stdout(out):
        rc2 = judge.main(["run", "C2", str(c1)])
    expect("the command line refuses the mismatch with exit 2",
           rc2 == 2 and "not C2" in out.getvalue(), out.getvalue()[-200:])


_STUB_DIRS: list[object] = []


def _canary_stub(listener: judge.Listener | None) -> judge.Canaries:
    # an empty directory for `work`, so scanning the files a run wrote reads
    # nothing but what a test puts there (never the repository itself)
    td = tempfile.TemporaryDirectory(prefix="ctf-stub-")
    _STUB_DIRS.append(td)  # keep it alive until the process ends
    p = Path(td.name)
    return judge.Canaries(
        root=p, work=p, read_dir=p, write_dir=p, outside=p,
        receipt=p / "r.json",
        nonce_file="SECRET-file", nonce_env="ENV-var", nonce_out="OUT-x",
        planted=frozenset({"secret.txt"}), listener=listener)


# --------------------------------------------------------------------------
# the live checks

def live() -> None:
    print("the live judge")
    if sys.platform != "linux":
        expect("live checks need Linux", False, sys.platform)
        return
    sabline = os.environ.get("SABLINE_CTF_SABLINE", "sabline").split()
    vuln_env = os.environ.get("SABLINE_CTF_VULNERABLE")
    vuln = vuln_env.split() if vuln_env else None
    rc = judge.self_test(sabline, vuln)
    expect("the judge's self-test passes (holds pinned, broken on 8.1.1)",
           rc == 0)
    for c in claims.CLAIMS:
        d = SUBMISSIONS / "holds" / c.id
        rep = judge.judge(c.id, d, sabline, runs=2,
                          timeout=judge.DEFAULT_TIMEOUT,
                          memory_mb=judge.DEFAULT_MEMORY_MB)
        expect(f"{c.id}: holds on the pinned Sabline",
               rep.verdict == "holds", f"{rep.verdict} {rep.error}"
               + "".join(f"\n      {r.outcome}: {r.note}"
                         for r in rep.results))
    live_prover(sabline)
    live_encoded(sabline, vuln)
    live_clock_rand(sabline)


def live_prover(sabline: list[str]) -> None:
    """C8's evidence is the receipt against the prover's answer: printing
    'E601' is worth nothing, and a prover that lies is caught."""
    printer = SUBMISSIONS / "selftest-c8-prints-e601"
    rep = judge.judge("C8", printer, sabline, runs=5,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    ran = [r for r in rep.results
           if r.note.startswith("every proven promise held")]
    expect("C8: a proven promise that holds, beside a printed 'E601', "
           "holds 5 of 5",
           rep.verdict == "holds" and len(ran) == 5,
           f"{rep.verdict} {rep.error}"
           + "".join(f"\n      {r.outcome}: {r.note}" for r in rep.results))

    lie = SUBMISSIONS / "selftest-c8-lie"
    rep = judge.judge("C8", lie, sabline, runs=2,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    expect("C8: the pinned prover leaves the lie program's promise to run "
           "time, so it holds (nothing was called proven)",
           rep.verdict == "holds" and all(
               r.note == "the prover settled no promise to break"
               for r in rep.results),
           f"{rep.verdict} {rep.error}"
           + "".join(f"\n      {r.outcome}: {r.note}" for r in rep.results))
    standin = [sys.executable, str(HERE / "ctf" / "lying_prover.py"),
               "--real", " ".join(sabline)]
    rep = judge.judge("C8", lie, standin, runs=3,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    fired = [b.observer for r in rep.results for b in r.breaks]
    expect("C8: a stand-in whose prover lies is reported broken 3 of 3, by "
           "prover_lie, from a genuine E601 in the receipt",
           rep.verdict == "broken 3 of 3" and fired == ["prover_lie"] * 3,
           f"{rep.verdict} {rep.error} {fired}"
           + "".join(f"\n      {r.outcome}: {r.note}" for r in rep.results))
    for r in rep.results[:1]:
        for b in r.breaks:
            print(f"    {b.observer}: {b.detail}")


def live_encoded(sabline: list[str], vuln: list[str] | None) -> None:
    """A leak printed reversed, or hex-encoded, is found by difference:
    broken on the 8.1.1 hole, holding on the pinned package."""
    for name in ("selftest-c1-reversed", "selftest-c1-hex"):
        d = SUBMISSIONS / name
        if vuln is None:
            expect(f"{name}: broken on 8.1.1 (no SABLINE_CTF_VULNERABLE "
                   "build given)", False)
        else:
            rep = judge.judge("C1", d, vuln, runs=3,
                              timeout=judge.DEFAULT_TIMEOUT,
                              memory_mb=judge.DEFAULT_MEMORY_MB,
                              require_confinement=False)
            fired = [b.observer for r in rep.results for b in r.breaks]
            expect(f"{name}: broken 3 of 3 on 8.1.1, by canary_diff",
                   rep.verdict == "broken 3 of 3"
                   and fired == ["canary_diff"] * 3,
                   f"{rep.verdict} {rep.error} {fired}"
                   + "".join(f"\n      {r.outcome}: {r.note}"
                             for r in rep.results))
        rep = judge.judge("C1", d, sabline, runs=2,
                          timeout=judge.DEFAULT_TIMEOUT,
                          memory_mb=judge.DEFAULT_MEMORY_MB)
        expect(f"{name}: holds on the pinned Sabline",
               rep.verdict == "holds", f"{rep.verdict} {rep.error}"
               + "".join(f"\n      {r.outcome}: {r.note}"
                         for r in rep.results))


def live_clock_rand(sabline: list[str]) -> None:
    """The seed and the clock are fixed for both runs, so a program that
    uses randomness or the clock is not a false 'broken'. No claim's budget
    grants either, so the program is judged under a budget of the test's
    that does, with C1's observers."""
    sub = judge.load_submission(SUBMISSIONS / "selftest-clock-rand")
    sub.claim = claims.Claim(
        id="C1", budget="io,clock,rand",
        invariant="reads any file of the user's",
        observers=("nonce_in_output", "canary_diff", "outside_write",
                   "listener"))
    with tempfile.TemporaryDirectory(prefix="ctf-rand-") as td:
        res = judge.run_once(sub, sabline, Path(td), judge.DEFAULT_TIMEOUT,
                             judge.DEFAULT_MEMORY_MB)
    expect("a program using the clock and randomness holds under the "
           "difference observer (seed and clock fixed for both runs)",
           res.outcome == "holds" and "a second run" in res.note,
           f"{res.outcome}: {res.note} "
           + "".join(f"{b.observer}: {b.detail}" for b in res.breaks))


def main(argv: list[str]) -> int:
    structure()
    wording()
    generated()
    submissions()
    observers()
    refusals()
    if "--live" in argv:
        live()
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    print(f"all {PASSED[0]} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
