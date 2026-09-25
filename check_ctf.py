#!/usr/bin/env python3
"""The CTF judge is well-formed, its observers catch a break, and every
claim holds on the pinned Sabline (8.7).

    python check_ctf.py            the checks that need no live run
    python check_ctf.py --live     also run the judge against Sabline

Without `--live` (every leg of CI, every OS): the claim table is well-formed,
`ctf/status.json` names exactly those claims and the confinement each one is
held to, `docs/ctf.md` is what `build_ctf.py` writes, `HALL_OF_FAME.md` has
the CTF section, every holds submission is well-formed and for the claim its
directory names, each observer catches a break given to it directly - no
Sabline is run - the judge refuses a submission that names a claim other than
the one the scorer named, and it refuses a `--sabline` that is not an
absolute path.

With `--live` (one Linux job): the judge's self-test, every holds submission
judged against the pinned Sabline (which must hold), and the regressions
from the two adversarial reviews of the judge: a proven promise beside a
printed "E601" holds 5 of 5; a stand-in whose prover lies is reported broken;
the self-test's read printed reversed, and hex-encoded, is broken on 8.1.1
and holds on the pinned package, and so is each of those written to stderr
with `log`; a two-file submission whose imported helper's unproven promise
breaks at run time holds; a stand-in whose run writes outside its grant is
reported broken; a tool-claim program that floods stderr is never a hold;
and a program using the clock and randomness is not a false "broken". The
self-test needs a build with the 8.1.1 double-dash hole to show the broken
direction; the job installs `velaris-lang==8.1.1` and points the judge at it
with `SABLINE_CTF_VULNERABLE`. `SABLINE_CTF_SABLINE` is the command for the
pinned package; both are required for the live leg, and both must be
absolute paths.
"""
from __future__ import annotations

import contextlib
import inspect
import io
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable, TypeVar

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctf import claims, judge  # noqa: E402

PASSED = [0]
FAILED: list[str] = []
T = TypeVar("T")


def within(seconds: float, work: Callable[[], T]) -> T | None:
    """`work`'s answer, or None if it did not come back in time. A judge
    that wedges is a check that fails here, not a job that hangs until the
    runner kills it an hour later - and two of the regressions below are
    about a judge that wedged."""
    box: list[Any] = []
    t = threading.Thread(target=lambda: box.append(work()), daemon=True)
    t.start()
    t.join(seconds)
    return box[0] if box else None

SUBMISSIONS = HERE / "ctf" / "submissions"
# the judge's own submissions beside the holds examples, and the claim each
# is for; check_ctf judges them, live, for what its docstring says
SELFTESTS = {
    "selftest-c1-holds": "C1",
    "selftest-c1-reversed": "C1",
    "selftest-c1-hex": "C1",
    "selftest-c1-reversed-log": "C1",
    "selftest-c1-hex-log": "C1",
    "selftest-c3-escape": "C3",
    "selftest-c7-stderr-flood": "C7",
    "selftest-c7-stderr-drained": "C7",
    "selftest-c8-prints-e601": "C8",
    "selftest-c8-lie": "C8",
    "selftest-c8-imported-unproven": "C8",
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
    expect("it is pinned to Linux", st["platform"] == "linux", st)
    # the confinement is per claim, and status.json says the same as
    # claims.py does: nothing here says every run is fully confined
    expect("status.json does not state one confinement for every claim",
           "confinement" not in st, sorted(st))
    for c in claims.CLAIMS:
        expect(f"{c.id}: status.json names the confinement claims.py holds "
               f"it to ({c.min_confinement})",
               st["claims"][c.id].get("confinement") == c.min_confinement,
               st["claims"][c.id])
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
    # the judge runs C8 under the claim's own budget, so plan/8.7.md's
    # table, ctf/claims.py and the command built cannot drift
    plan = (HERE / "plan" / "8.7.md").read_text(encoding="utf-8")
    c8 = claims.BY_ID["C8"]
    expect("plan/8.7.md's C8 row names the budget claims.py gives it",
           f"| C8 | `{c8.budget}` |" in plan,
           [ln for ln in plan.splitlines() if ln.startswith("| C8 |")])
    expect("plan/8.7.md says why C8's budget is fixed",
           "C8 is judged under `io`" in plan)


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
    # the confinement a claim gets is stated per claim; no page of this
    # CTF's says every run is fully confined, because they are not
    page = (HERE / "docs" / "ctf.md").read_text(encoding="utf-8")
    for where, text in (("docs/ctf.md", page),
                        ("check_ctf.py", __doc__ or ""),
                        ("ctf/judge.py", judge.__doc__ or ""),
                        ("ctf/claims.py", claims.__doc__ or "")):
        expect(f"{where} does not say every run is fully confined",
               "under full operating-system confinement" not in text
               and "under full OS confinement" not in text,
               where)
    expect("docs/ctf.md states the confinement per claim",
           "| Confinement |" in page and "`partial`" in page
           and "`none`" in page)
    expect("ctf/claims.py says the confinement is per claim",
           "Confinement is per claim" in (claims.__doc__ or ""))
    expect("docs/ctf.md says every run passes --no-native",
           "--no-native" in page)


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
    two = judge.load_submission(SUBMISSIONS / "selftest-c8-imported-unproven")
    expect("the C8 two-file regression really brings two .vel files",
           sorted(n for n in two.files if n.endswith(".vel"))
           == ["helper.vel", "p.vel"], sorted(two.files))
    for name in ("selftest-c7-stderr-flood", "selftest-c7-stderr-drained"):
        flood = (SUBMISSIONS / name / "attack.vel").read_text(
            encoding="utf-8")
        expect(f"{name} writes more than 64 KiB to stderr, which is what a "
               "pipe holds",
               "log(" in flood and "while i < 4000" in flood, name)


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
           bool(judge.obs_canary_diff("a", "e", same_files,
                                      "b", "e", same_files)))
    expect("canary_diff sees a written file that differs",
           bool(judge.obs_canary_diff("a", "e", same_files, "a", "e",
                                      {"file:out.txt": "other"})))
    # `log` writes to stderr: the difference observer reads it too, or a
    # leak written with `log` is a leak the judge never sees
    expect("canary_diff sees stderr that differs",
           bool(judge.obs_canary_diff("a", "leak-AAA", same_files,
                                      "a", "leak-BBB", same_files)))
    expect("canary_diff is quiet when both runs printed and wrote the same",
           not judge.obs_canary_diff("a", "e", same_files, "a", "e",
                                     dict(same_files)))
    stderr_filter()

    watched_trees()

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
    # both ceilings the door promised are checked, not only the one the
    # grant names: at 15 credits a call against 40, the cost bites at the
    # third call, the grant's count of three at the fourth
    man = judge._tool_manifest("email", None)  # type: ignore[arg-type]
    expect("the manifest's cost is the one the judge scores by",
           man["tools"]["send_email"]["cost"] == judge.EMAIL_COST
           and man["ceiling"] == judge.EMAIL_CEILING, man)
    two = [{"tool": "send_email", "arguments": {"to": "a@corp.com"}}
           for _ in range(2)]
    expect("two calls are inside the cost ceiling",
           not judge.email_breaks(two),
           [b.detail for b in judge.email_breaks(two)])
    three = two + [{"tool": "send_email",
                    "arguments": {"to": "a@corp.com"}}]
    got = judge.email_breaks(three)
    expect("a third call is past the manifest's cost ceiling",
           any("ceiling of 40" in b.detail for b in got),
           [b.detail for b in got])
    got = judge.email_breaks(many)
    expect("a fourth call is past the grant's call ceiling too",
           any("ceiling of 3 allows" in b.detail for b in got),
           [b.detail for b in got])

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
    # an E601 that may be a runtime-checked promise's is no lie, and the
    # judge did see both its channels: that is a hold, not a run it could
    # not score
    mixed = judge.obs_prover_lie(["double"], ["tally"], ("failed", "E601"))
    expect("prover_lie does not score an E601 that may be a runtime-checked "
           "promise's", mixed.outcome == "holds", mixed)
    expect("and it says which promise left to run time it could have been",
           "tally" in mixed.note, mixed.note)
    with tempfile.TemporaryDirectory(prefix="ctf-receipt-") as td:
        rec = Path(td) / "r.json"
        rec.write_text(json.dumps({"predicate": {"exit": {
            "status": 1, "outcome": "failed", "code": "E601"}}}),
            encoding="utf-8")
        expect("the receipt's exit is read as (outcome, code)",
               judge._receipt_exit(rec) == ("failed", "E601"))
        expect("no receipt reads as None",
               judge._receipt_exit(Path(td) / "none.json") is None)


def stderr_filter() -> None:
    """The stderr two runs are compared on. Only lines the judge can point
    at in the runtime's own source are touched, and the prover's timing
    note is normalised rather than dropped, so that a program imitating it
    with a secret in the part that is not the timing is still caught."""
    llvm = ("note: llvmlite is not installed - running fully interpreted "
            "(for native speed: pip install llvmlite)")
    z3 = ("note: z3-solver is not installed, so promises are checked while "
          "running instead of proven beforehand (install with: pip install "
          "z3-solver)")

    def timed_out(who: str, secs: str) -> str:
        return (f"note: the proof of {who} ran out of time after {secs}s "
                "and was abandoned - nothing was proven and nothing was "
                "refuted, so its promises are checked while running "
                "instead. This is not 'the prover found nothing wrong'. "
                "Give it longer with --proof-timeout 6 (or "
                "SABLINE_PROOF_TIMEOUT=6).")

    expect("the llvmlite note is filtered out",
           judge.normalise_stderr(llvm) == "")
    expect("the z3 note is filtered out", judge.normalise_stderr(z3) == "")
    expect("the prover's timing note is the same however long it took",
           judge.normalise_stderr(timed_out("tally", "3"))
           == judge.normalise_stderr(timed_out("tally", "11.5")),
           judge.normalise_stderr(timed_out("tally", "3")))
    expect("the prover's timing note still carries the function's name, so "
           "a secret put where the name goes is not filtered away",
           judge.normalise_stderr(timed_out("SECRET-aaa", "3"))
           != judge.normalise_stderr(timed_out("SECRET-bbb", "3")))
    expect("an ordinary line is left alone",
           judge.normalise_stderr("leaked SECRET-1") == "leaked SECRET-1")
    expect("a line that only looks like a known note is left alone",
           judge.normalise_stderr("note: llvmlite is not installed - "
                                  "SECRET-1").endswith("SECRET-1"))


def watched_trees() -> None:
    """outside_write hashes every tree the run can reach but the one
    directory its budget lets it write: a write that escapes no further
    than the run's own working directory is outside the grant as surely as
    one that lands in the tree further out, and the judge sees both."""
    print("the watched trees")
    sub_ = judge.load_submission(SUBMISSIONS / "holds" / "C3")
    with tempfile.TemporaryDirectory(prefix="ctf-watch-") as rd, \
            tempfile.TemporaryDirectory(prefix="ctf-watchj-") as jd:
        root = Path(rd)
        can = judge.build_canaries(root, sub_, judge.JudgeDir(Path(jd)))
        c3 = claims.BY_ID["C3"]
        before = judge.watched_hashes(can, c3)
        (can.write_dir / "out.txt").write_text("in the grant",
                                               encoding="utf-8")
        expect("a write inside the grant is not a break",
               not judge.obs_outside_write(before,
                                           judge.watched_hashes(can, c3)))
        (can.work / "escaped.txt").write_text("out of it", encoding="utf-8")
        got = judge.obs_outside_write(before,
                                      judge.watched_hashes(can, c3))
        expect("a write escaping into the run's own directory is a break",
               bool(got) and "work/escaped.txt" in got[0].detail,
               [b.detail for b in got])
        (can.outside / "further.txt").write_text("further", encoding="utf-8")
        got = judge.obs_outside_write(before,
                                      judge.watched_hashes(can, c3))
        expect("a write into the tree outside every grant is a break too",
               any("outside/further.txt" in b.detail for b in got),
               [b.detail for b in got])
        # a claim with no write grant at all: the writable directory the
        # judge made is watched like anywhere else, and only the claim that
        # grants it has it left out
        c1 = claims.BY_ID["C1"]
        expect("with no write grant, the writable directory is watched too",
               "work/writable/out.txt" in judge.watched_hashes(can, c1),
               sorted(judge.watched_hashes(can, c1)))
        expect("C3's own write grant is the one tree left out",
               "work/writable/out.txt" not in judge.watched_hashes(can, c3),
               sorted(judge.watched_hashes(can, c3)))
        expect("the receipt is not under the run's root, so it is not a "
               "tree the run can reach",
               not can.receipt.is_relative_to(can.root), can.receipt)


def receipts() -> None:
    """The receipt is the judge's channel: it lives in a directory of the
    judge's own, outside the run's root, and the judge checks afterwards
    that what it read is what is still there."""
    print("the judge's own directory")
    with tempfile.TemporaryDirectory(prefix="ctf-jd-") as jd:
        d = judge.JudgeDir(Path(jd))
        d.receipt.write_text('{"predicate": {"exit": {"code": "E601"}}}',
                             encoding="utf-8")
        d.keep()
        ok, why = d.intact()
        expect("a receipt the judge read and kept is intact", ok, why)
        kept = next(iter(d.kept))
        (Path(jd) / kept).write_text("changed", encoding="utf-8")
        ok, why = d.intact()
        expect("a receipt changed after the judge read it is not intact",
               not ok and "changed" in why, why)
        (Path(jd) / kept).write_text(
            '{"predicate": {"exit": {"code": "E601"}}}', encoding="utf-8")
        (Path(jd) / "planted.json").write_text("{}", encoding="utf-8")
        ok, why = d.intact()
        expect("a file the judge did not ask for is not intact",
               not ok and "planted.json" in why, why)


def refusals() -> None:
    """The scorer names the claim; a submission naming another is refused
    on every platform, and 'auto' is not a claim."""
    print("the claim is the scorer's")
    c1 = SUBMISSIONS / "holds" / "C1"
    # an absolute path that exists, so the refusal under test is the one
    # about the claim and not the one about --sabline; nothing is run
    here = [sys.executable]
    rep = judge.judge("C2", c1, here, runs=1,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    expect("a submission for C1 scored as C2 is refused",
           rep.verdict == "did not run" and "C1" in rep.error
           and "C2" in rep.error, (rep.verdict, rep.error))
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc: int | None = judge.main(["run", "auto", str(c1),
                                         "--sabline", sys.executable])
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 1
    expect("'auto' is not a claim the command line takes",
           rc == 2 and "invalid choice" in err.getvalue(), err.getvalue())
    with contextlib.redirect_stdout(out):
        rc2 = judge.main(["run", "C2", str(c1), "--sabline", sys.executable])
    expect("the command line refuses the mismatch with exit 2",
           rc2 == 2 and "not C2" in out.getvalue(), out.getvalue()[-200:])

    # --sabline is required, and names an absolute path: a judge that found
    # its Sabline on PATH would score against whatever build was there
    print("the Sabline the judge is pointed at")
    expect("a bare name is refused, not looked up on PATH",
           "absolute path" in judge.sabline_refusal(["sabline"]),
           judge.sabline_refusal(["sabline"]))
    expect("a relative path is refused",
           "absolute path" in judge.sabline_refusal(["./sabline"]))
    # absolute on whatever runs this, and not a file: Windows stopped
    # calling a bare leading separator absolute in 3.13
    nowhere = str(Path(sys.executable).parent / "no-such-sabline-here")
    expect("an absolute path that is not there is refused",
           "not a file to run" in judge.sabline_refusal([nowhere]),
           judge.sabline_refusal([nowhere]))
    expect("no command at all is refused",
           "required" in judge.sabline_refusal([]))
    expect("an absolute path to a real program is taken",
           judge.sabline_refusal([sys.executable]) == "",
           judge.sabline_refusal([sys.executable]))
    rep = judge.judge("C1", c1, ["sabline"], runs=1,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    expect("the judge refuses to score against a PATH lookup",
           rep.verdict == "did not run" and "absolute path" in rep.error,
           (rep.verdict, rep.error))
    out2, err2 = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out2), contextlib.redirect_stderr(err2):
        try:
            rc3: int | None = judge.main(["run", "C1", str(c1)])
        except SystemExit as e:
            rc3 = e.code if isinstance(e.code, int) else 1
    expect("the command line will not run without --sabline",
           rc3 == 2 and "--sabline" in err2.getvalue(), err2.getvalue())

    # every run the judge builds forces the interpreter
    print("the backend is the same on every machine")
    sub_ = judge.load_submission(c1)
    with tempfile.TemporaryDirectory(prefix="ctf-nat-") as rd, \
            tempfile.TemporaryDirectory(prefix="ctf-natj-") as jd:
        can = judge.build_canaries(Path(rd), sub_, judge.JudgeDir(Path(jd)))
        cmd = judge._plain_command(sub_, ["/x/sabline"], can, "io", 30, 512)
    expect("the plain runner passes --no-native",
           judge.NO_NATIVE in cmd, cmd)
    for who in (judge._host_run, judge._run_prover_lie,
                judge.confinement_probe):
        body = inspect.getsource(who)
        expect(f"{who.__name__} passes --no-native", "NO_NATIVE" in body)
    expect("the judge has a native-availability check it refuses on",
           "def native_available" in inspect.getsource(judge)
           and "scores nothing where native" in inspect.getsource(judge))
    # the tool door's two runs differ only in the secret, so they are
    # fixed the way the difference observer's two runs are
    host = inspect.getsource(judge._host_run)
    expect("the tool door's runs fix the seed and the clock, as the "
           "difference observer's two runs do",
           '"--seed", SEED' in host and '"--freeze-time", FROZEN_CLOCK'
           in host)
    expect("the tool door's runs drain stderr as well as stdout",
           "proc.stderr.read()" in host and "threading.Thread" in host)
    expect("the tool door's runner reports a run that did not finish",
           "finished" in host
           and "did-not-run" in inspect.getsource(judge._run_tools)
           and "did-not-run" in inspect.getsource(judge._run_secret_diff))


_STUB_DIRS: list[object] = []


def _canary_stub(listener: judge.Listener | None) -> judge.Canaries:
    # an empty directory for `work`, so scanning the files a run wrote reads
    # nothing but what a test puts there (never the repository itself), and
    # a second one for the judge's own channel, which is never under it
    td = tempfile.TemporaryDirectory(prefix="ctf-stub-")
    jd = tempfile.TemporaryDirectory(prefix="ctf-stubj-")
    _STUB_DIRS.extend((td, jd))  # keep them alive until the process ends
    p = Path(td.name)
    return judge.Canaries(
        root=p, work=p, read_dir=p, write_dir=p, outside=p,
        judge_dir=judge.JudgeDir(Path(jd.name)),
        nonce_file="SECRET-file", nonce_env="ENV-var", nonce_out="OUT-x",
        planted=frozenset({"secret.txt"}), listener=listener)


# --------------------------------------------------------------------------
# the live checks

def live() -> None:
    print("the live judge")
    if sys.platform != "linux":
        expect("live checks need Linux", False, sys.platform)
        return
    sabline = os.environ.get("SABLINE_CTF_SABLINE", "").split()
    refused = judge.sabline_refusal(sabline)
    if refused:
        expect("SABLINE_CTF_SABLINE names the pinned Sabline by absolute "
               "path", False, refused)
        return
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
    live_escaping_write(sabline)
    live_stderr_flood(sabline)
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
    # the imported helper's promise, left to run time by the prover and
    # broken there: asking the prover about the entry file alone makes this
    # a lie that never happened
    two = SUBMISSIONS / "selftest-c8-imported-unproven"
    rep = judge.judge("C8", two, sabline, runs=3,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    expect("C8: an E601 raised by an imported helper's unproven promise is "
           "not a prover lie, and holds 3 of 3",
           rep.verdict == "holds"
           and all("left to run time" in r.note for r in rep.results),
           f"{rep.verdict} {rep.error}"
           + "".join(f"\n      {r.outcome}: {r.note}" for r in rep.results))
    for r in rep.results[:1]:
        print(f"    {r.outcome}: {r.note}")

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
    broken on the 8.1.1 hole, holding on the pinned package. The same two
    leaks written with `log`, which goes to stderr and never touches stdout
    or a file, must be found the same way - a judge that compared stdout
    and the files written alone called both of those a hold."""
    for name in ("selftest-c1-reversed", "selftest-c1-hex",
                 "selftest-c1-reversed-log", "selftest-c1-hex-log"):
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


def live_escaping_write(sabline: list[str]) -> None:
    """C3's observer watches every tree the run can reach but its write
    grant. A stand-in whose run writes into the run's own working
    directory - outside the grant, but no further out than the workspace -
    must be reported broken; the pinned package, which writes no such
    file, must hold."""
    d = SUBMISSIONS / "selftest-c3-escape"
    standin = [sys.executable, str(HERE / "ctf" / "escaping_runtime.py"),
               "--real", " ".join(sabline)]
    rep = judge.judge("C3", d, standin, runs=3,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    fired = [b.observer for r in rep.results for b in r.breaks]
    expect("C3: a run that writes into its own working directory, outside "
           "the one directory it may write, is reported broken 3 of 3",
           rep.verdict == "broken 3 of 3"
           and fired == ["outside_write"] * 3,
           f"{rep.verdict} {rep.error} {fired}"
           + "".join(f"\n      {r.outcome}: {r.note}"
                     for r in rep.results))
    for r in rep.results[:1]:
        for b in r.breaks:
            print(f"    {b.observer}: {b.detail}")
    rep = judge.judge("C3", d, sabline, runs=2,
                      timeout=judge.DEFAULT_TIMEOUT,
                      memory_mb=judge.DEFAULT_MEMORY_MB)
    expect("C3: the same submission holds on the pinned Sabline",
           rep.verdict == "holds", f"{rep.verdict} {rep.error}"
           + "".join(f"\n      {r.outcome}: {r.note}"
                     for r in rep.results))


def live_stderr_flood(sabline: list[str]) -> None:
    """The tool door's host drains both of the program's pipes and holds
    the run to a deadline of its own.

    The first program writes 256 KiB to stderr - four times what a pipe
    holds - makes its one entirely allowed call, and then never ends. A
    host that read stdout and left stderr to fill would wedge on it for
    ever; one that ignored how the run ended would call the killed run a
    hold, since the transcript holds one allowed call and nothing against
    it. It must be did-not-run, and the judge must come back at all. The
    second writes the same flood and then finishes: the stderr the judge
    hands back must be all of it, and the call must be in the transcript,
    which is what a host that stopped reading at 64 KiB would not have."""
    d = SUBMISSIONS / "selftest-c7-stderr-flood"
    rep = within(240, lambda: judge.judge(
        "C7", d, sabline, runs=1, timeout=20,
        memory_mb=judge.DEFAULT_MEMORY_MB))
    if rep is None:
        expect("C7: a program that floods stderr and never ends does not "
               "wedge the judge", False, "the judge did not come back")
        return
    expect("C7: a program that floods stderr and never ends is did-not-run, "
           "never a hold",
           rep.verdict == "did not run"
           and all("did not finish" in r.note for r in rep.results),
           f"{rep.verdict} {rep.error}"
           + "".join(f"\n      {r.outcome}: {r.note}"
                     for r in rep.results))
    for r in rep.results[:1]:
        print(f"    run 1: {r.outcome} - {r.note}")

    sub_ = judge.load_submission(SUBMISSIONS / "selftest-c7-stderr-drained")
    got = within(240, lambda: _drained(sub_, sabline))
    if got is None:
        expect("C7: the host drains stderr past the 64 KiB a pipe holds",
               False, "the judge did not come back")
        return
    calls, err, finished = got
    expect("C7: the host reads every byte of a 256 KiB stderr, and the run "
           "finishes",
           finished and len(err) > 200000, (finished, len(err)))
    expect("C7: and the call after the flood still reaches the transcript",
           len(calls) == 1 and not judge.email_breaks(calls),
           [c.get("tool") for c in calls])
    print(f"    {len(err)} bytes of stderr drained, {len(calls)} call(s) "
          "seen after it")


def _drained(sub_: judge.Submission,
             sabline: list[str]) -> tuple[list[Any], str, bool]:
    claim = sub_.claim
    with tempfile.TemporaryDirectory(prefix="ctf-flood-") as rd, \
            tempfile.TemporaryDirectory(prefix="ctf-floodj-") as jd:
        can = judge.build_canaries(Path(rd), sub_, judge.JudgeDir(Path(jd)))
        man = Path(rd) / "tools.json"
        man.write_text(json.dumps(judge._tool_manifest(claim.manifest, can)),
                       encoding="utf-8")
        calls, _out, err, finished = judge._host_run(
            sub_, sabline, can, judge.fill_budget(claim.budget, can), man,
            judge.DEFAULT_TIMEOUT, judge.DEFAULT_MEMORY_MB, secret="unused")
    return calls, err, finished


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
    with tempfile.TemporaryDirectory(prefix="ctf-rand-") as td, \
            tempfile.TemporaryDirectory(prefix="ctf-randj-") as jd:
        res = judge.run_once(sub, sabline, Path(td), Path(jd),
                             judge.DEFAULT_TIMEOUT,
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
    receipts()
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
