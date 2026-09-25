#!/usr/bin/env python3
"""The CTF judge is well-formed, its observers catch a break, and every
claim holds on the pinned Sabline (8.7).

    python check_ctf.py            the checks that need no live run
    python check_ctf.py --live     also run the judge against Sabline

Without `--live` (every leg of CI, every OS): the claim table is well-formed,
`ctf/status.json` names exactly those claims, `docs/ctf.md` is what
`build_ctf.py` writes, `HALL_OF_FAME.md` has the CTF section, every holds
submission is well-formed and for the claim its directory names, and each
observer catches a break given to it directly - no Sabline is run.

With `--live` (one Linux job): the judge's self-test, and every holds
submission judged against the pinned Sabline, which must hold. The self-test
needs a build with the 8.1.1 double-dash hole to show the broken direction;
the job installs `velaris-lang==8.1.1` and points the judge at it with
`SABLINE_CTF_VULNERABLE`. `SABLINE_CTF_SABLINE` is the command for the
pinned package (default `sabline`).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ctf import claims, judge  # noqa: E402

PASSED = [0]
FAILED: list[str] = []


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
    base = HERE / "ctf" / "submissions" / "holds"
    for c in claims.CLAIMS:
        d = base / c.id
        expect(f"{c.id}: a holds submission exists", d.is_dir())
        if not d.is_dir():
            continue
        sub = judge.load_submission(d)
        expect(f"{c.id}: the submission is for {c.id}",
               sub.claim.id == c.id, sub.claim.id)
    self = HERE / "ctf" / "submissions" / "selftest-c1-holds"
    expect("the self-test submission is for C1",
           judge.load_submission(self).claim.id == "C1")


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


_STUB_DIRS: list[object] = []


def _canary_stub(listener: judge.Listener | None) -> judge.Canaries:
    # an empty directory for `work`, so scanning the files a run wrote reads
    # nothing but what a test puts there (never the repository itself)
    import tempfile
    td = tempfile.TemporaryDirectory(prefix="ctf-stub-")
    _STUB_DIRS.append(td)  # keep it alive until the process ends
    p = Path(td.name)
    return judge.Canaries(
        root=p, work=p, read_dir=p, write_dir=p, outside=p,
        receipt=p / "r.json",
        nonce_file="SECRET-file", nonce_env="ENV-var", nonce_out="OUT-x",
        listener=listener)


# --------------------------------------------------------------------------
# the live checks

def live() -> None:
    print("the live judge")
    if sys.platform != "linux":
        expect("live checks need Linux", False, sys.platform)
        return
    sabline = os.environ.get("SABLINE_CTF_SABLINE", "sabline").split()
    vuln = os.environ.get("SABLINE_CTF_VULNERABLE")
    rc = judge.self_test(sabline, vuln.split() if vuln else None)
    expect("the judge's self-test passes (holds pinned, broken on 8.1.1)",
           rc == 0)
    for c in claims.CLAIMS:
        d = HERE / "ctf" / "submissions" / "holds" / c.id
        rep = judge.judge(c.id, d, sabline, runs=2,
                          timeout=judge.DEFAULT_TIMEOUT,
                          memory_mb=judge.DEFAULT_MEMORY_MB)
        expect(f"{c.id}: holds on the pinned Sabline",
               rep.verdict == "holds", f"{rep.verdict} {rep.error}")


def main(argv: list[str]) -> int:
    structure()
    generated()
    submissions()
    observers()
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
