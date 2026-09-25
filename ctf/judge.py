#!/usr/bin/env python3
"""The Sabline CTF judge (8.7, plan/8.7.md section 4).

    python -m ctf.judge run C1 <submission-dir> [--sabline CMD] [--runs 5]
    python -m ctf.judge self-test --vulnerable <velaris-cmd>
    python -m ctf.judge claims

A submission is a directory with a `submission.json`
(`{"claim": "C1", "program": "attack.vel", "argv": [...], "note": "..."}`)
and the files it names. The scorer names the claim a submission is scored
against; a submission that names another is refused, not scored under its
own. The judge:

- hashes the submission before any canary exists, so it cannot hold one;
- for each of `--runs` runs (five by default), builds a fresh set of
  canaries the claim forbids, copies the submission into a scratch
  workspace, and runs it against the pinned, published Sabline under full
  operating-system confinement - refusing to score a run that did not get
  the confinement its claim needs, and refusing to run at all except on
  Linux;
- applies only the claim's own observers - file hashes, a listener's log,
  a scan for a nonce, a second run that differs only in the nonce, the tool
  door's transcript, the prover's answer against the run's receipt - and
  never the submission's exit code or transcript. Every piece of evidence
  comes from a channel the judge controls and the program cannot write to;
- reports one of three answers: the claim held on every run, it was broken
  on k of the runs (with the evidence of each break), or it did not run.

The judge holds no token, no secret and no network beyond the loopback
listeners it makes itself. It is the code this repository publishes; the
private scoring repository pins it by commit and runs it, so what scores a
submission can be read by anyone, and the safety rests on the per-run
canaries, not on secrecy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from ctf.claims import BY_ID, CLAIMS, Claim  # noqa: E402

DEFAULT_TIMEOUT = 30
DEFAULT_MEMORY_MB = 512

# the run's determinism parameters, fixed, so that two runs of a submission
# differ only in what the judge changes between them (the planted nonces)
SEED = "0"
FROZEN_CLOCK = "2026-01-01T00:00:00Z"


@dataclass
class Break:
    """One observer firing: what the run did that the claim forbids."""

    observer: str
    detail: str


@dataclass
class RunResult:
    outcome: str  # "holds", "broken", "did-not-run"
    breaks: list[Break] = field(default_factory=list)
    note: str = ""


@dataclass
class Report:
    claim: str
    runs: int
    submission_sha256: str
    verdict: str  # "holds", "broken k of n", "did not run"
    broken_runs: int
    results: list[RunResult] = field(default_factory=list)
    error: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "schema": "sabline.ctf-verdict/1",
            "claim": self.claim,
            "runs": self.runs,
            "submission_sha256": self.submission_sha256,
            "verdict": self.verdict,
            "broken_runs": self.broken_runs,
            "error": self.error,
            "results": [
                {"outcome": r.outcome, "note": r.note,
                 "breaks": [{"observer": b.observer, "detail": b.detail}
                            for b in r.breaks]}
                for r in self.results
            ],
        }


# --------------------------------------------------------------------------
# the submission

@dataclass
class Submission:
    claim: Claim
    program: str
    files: dict[str, bytes]
    argv: list[str]
    note: str


def load_submission(where: Path) -> Submission:
    spec_path = where / "submission.json"
    if not spec_path.is_file():
        raise SystemExit(f"{where}: no submission.json")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    cid = spec.get("claim")
    if cid not in BY_ID:
        raise SystemExit(f"{where}: claim {cid!r} is not one of "
                         f"{', '.join(BY_ID)}")
    program = spec.get("program")
    if not isinstance(program, str) or not (where / program).is_file():
        raise SystemExit(f"{where}: program {program!r} is not a file here")
    argv = spec.get("argv", [])
    if not isinstance(argv, list) or not all(isinstance(a, str) for a in argv):
        raise SystemExit(f"{where}: argv must be a list of strings")
    files: dict[str, bytes] = {}
    for p in sorted(where.rglob("*")):
        if p.is_file() and p.name != "submission.json":
            files[p.relative_to(where).as_posix()] = p.read_bytes()
    return Submission(BY_ID[cid], program, files, list(argv),
                      str(spec.get("note", "")))


def submission_digest(sub: Submission) -> str:
    h = hashlib.sha256()
    h.update(json.dumps(
        {"claim": sub.claim.id, "program": sub.program, "argv": sub.argv},
        sort_keys=True).encode("utf-8"))
    for name in sorted(sub.files):
        h.update(name.encode("utf-8"))
        h.update(hashlib.sha256(sub.files[name]).digest())
    return h.hexdigest()


# --------------------------------------------------------------------------
# the canaries

@dataclass
class Listener:
    host: str
    port: int
    hits: list[str] = field(default_factory=list)
    _sock: socket.socket | None = None
    _thread: threading.Thread | None = None
    _stop: bool = False

    def start(self) -> None:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, 0))
        s.listen(8)
        s.settimeout(0.3)
        self.host, self.port = s.getsockname()
        self._sock = s

        def serve() -> None:
            while not self._stop:
                try:
                    conn, addr = s.accept()
                except OSError:
                    continue
                self.hits.append(f"{addr[0]}:{addr[1]}")
                try:
                    conn.sendall(b"HTTP/1.1 200 OK\r\n"
                                 b"Content-Length: 2\r\n\r\nhi")
                except OSError:
                    pass
                conn.close()

        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop = True
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self._sock is not None:
            self._sock.close()


@dataclass
class Canaries:
    root: Path
    work: Path          # the run's working directory (submission copied here)
    read_dir: Path      # a directory a read claim may read (innocuous)
    write_dir: Path     # a directory a write claim may write
    outside: Path       # a tree outside every grant, hashed before/after
    receipt: Path       # where the judge asks for the run's receipt
    nonce_file: str     # the secret nonce, in a file (relative to work)
    nonce_env: str      # the secret nonce, in the environment
    nonce_out: str      # a nonce written into the outside tree, to detect read
    # the exact paths (relative to `work`, posix) the judge planted a nonce
    # at: the only files a scan of what the run wrote leaves out, so a file
    # the run made with the same name anywhere else is scanned like any other
    planted: frozenset[str] = frozenset()
    listener: Listener | None = None
    decoy: Listener | None = None


def _tree_hashes(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = hashlib.sha256(
                p.read_bytes()).hexdigest()
    return out


def build_canaries(root: Path, sub: Submission) -> Canaries:
    work = root / "work"
    read_dir = work / "readable"
    write_dir = work / "writable"
    outside = root / "outside"
    for d in (work, read_dir, write_dir, outside):
        d.mkdir(parents=True, exist_ok=True)
    for name, data in sub.files.items():
        dest = work / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    nonce_file = "SECRET-" + secrets.token_hex(16)
    nonce_env = "ENV-" + secrets.token_hex(16)
    nonce_out = "OUTSIDE-" + secrets.token_hex(16)
    # the file nonce: outside {READ} (a read claim's forbidden file), and for
    # C1 simply a file in the run's own directory it has no fs grant to read.
    (work / "secret.txt").write_text(nonce_file + "\n", encoding="utf-8")
    (outside / "secret.txt").write_text(nonce_out + "\n", encoding="utf-8")
    (read_dir / "ok.txt").write_text("nothing secret here\n",
                                     encoding="utf-8")
    return Canaries(
        root=root, work=work, read_dir=read_dir, write_dir=write_dir,
        outside=outside, receipt=root / "judge-receipt.json",
        nonce_file=nonce_file, nonce_env=nonce_env, nonce_out=nonce_out,
        planted=frozenset({"secret.txt"}),
    )


def rebuild_canaries(can: Canaries, sub: Submission) -> Canaries:
    """The same workspace again, at the same paths, with fresh nonces: what
    the second run of a difference-judged claim gets. Everything the first
    run wrote is gone, so it cannot carry anything over; the listeners stay
    up, so a connection to either during either run counts."""
    for d in (can.work, can.outside):
        shutil.rmtree(d, ignore_errors=True)
    if can.receipt.exists():
        can.receipt.unlink()
    fresh = build_canaries(can.root, sub)
    fresh.listener, fresh.decoy = can.listener, can.decoy
    return fresh


def fill_budget(budget: str, can: Canaries) -> str:
    host = ""
    if "{HOST}" in budget:
        can.decoy = Listener("127.0.0.1", 0)
        can.decoy.start()
        host = f"127.0.0.1:{can.decoy.port}"
    return (budget
            .replace("{READ}", can.read_dir.as_posix())
            .replace("{WRITE}", can.write_dir.as_posix())
            .replace("{HOST}", host))


# --------------------------------------------------------------------------
# the observers

def obs_nonce_in_output(can: Canaries, stdout: str, stderr: str,
                        claim: Claim) -> list[Break]:
    breaks: list[Break] = []
    wrote = _scan_written_files(can)
    haystacks = {"stdout": stdout, "stderr": stderr, **wrote}
    # C5 forbids the environment nonce; the others forbid the file nonce.
    wanted = can.nonce_env if "C5" == claim.id else can.nonce_file
    targets = [wanted]
    if claim.id == "C2":
        # C2 may read {READ} and nothing else: the nonce in the tree outside
        # every grant and the one in the run's own working directory are
        # both outside it, and both forbidden
        targets = [can.nonce_out, can.nonce_file]
    for where, text in haystacks.items():
        for t in targets:
            if t in text:
                breaks.append(Break(
                    "nonce_in_output",
                    f"the forbidden value appeared in {where}"))
                return breaks
    return breaks


def _scan_written_files(can: Canaries) -> dict[str, str]:
    """Every file under the run's workspace but the ones the judge planted
    there - left out by exact path, so a file the run made with a planted
    file's name, anywhere else, is scanned like any other."""
    out: dict[str, str] = {}
    for p in sorted(can.work.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(can.work).as_posix()
        if rel in can.planted:
            continue
        try:
            out[f"file:{rel}"] = p.read_text(encoding="utf-8",
                                             errors="replace")
        except OSError:
            pass
    return out


def obs_canary_diff(first_stdout: str, first_files: dict[str, str],
                    second_stdout: str,
                    second_files: dict[str, str]) -> list[Break]:
    """Two runs that differed only in the planted nonces - same paths, same
    seed, same clock, same arguments: a difference in what they printed, or
    in the files they wrote, is information flowing from the nonce, however
    it was encoded."""
    breaks: list[Break] = []
    if first_stdout != second_stdout:
        breaks.append(Break(
            "canary_diff",
            "stdout differed between two runs that differed only in the "
            "planted secret, so information flowed from it"))
    if first_files != second_files:
        changed = sorted(k for k in set(first_files) | set(second_files)
                         if first_files.get(k) != second_files.get(k))
        breaks.append(Break(
            "canary_diff",
            "the files written differed between two runs that differed "
            f"only in the planted secret ({', '.join(changed)}), so "
            "information flowed from it"))
    return breaks


def obs_outside_write(before: dict[str, str],
                      after: dict[str, str]) -> list[Break]:
    breaks: list[Break] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            what = ("created" if path not in before else
                    "removed" if path not in after else "changed")
            breaks.append(Break(
                "outside_write",
                f"a file outside every grant was {what}: {path}"))
    return breaks


def obs_listener(can: Canaries) -> list[Break]:
    if can.listener and can.listener.hits:
        return [Break("listener",
                      f"a connection reached the canary listener "
                      f"({can.listener.hits[0]})")]
    return []


def obs_prover_lie(proven: list[str], unproven: list[str],
                   exit_: tuple[str, str | None]) -> RunResult:
    """The prover's answer against the run's receipt. `proven` and
    `unproven` are the promise-carrying functions by the status the prover
    gave them; `exit_` is the (outcome, code) the receipt records. Neither
    is anything the program printed."""
    outcome, code = exit_
    if code != "E601":
        said = outcome + (f", {code}" if code else "")
        return RunResult("holds", note="every proven promise held at run "
                                       f"time (the receipt's exit: {said})")
    if unproven:
        return RunResult(
            "did-not-run",
            note="the receipt says an ensures broke at run time (E601), but "
                 "the program also has promises the prover left to run time "
                 f"({', '.join(unproven)}), and the receipt does not say "
                 "whose; a prover lie is scored only when every promise in "
                 "the program is one the prover called proven")
    return RunResult("broken", [Break(
        "prover_lie",
        f"the prover called {', '.join(proven)} proven, every promise in "
        "the program is one it called proven, and the receipt says an "
        "ensures broke at run time (E601)")])


# --------------------------------------------------------------------------
# running one submission once

def _base_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")}
    return env


_LEVELS = {"none": 0, "partial": 1, "full": 2}


def _confinement_ok(receipt: Path, minimum: str) -> tuple[bool, str]:
    if not receipt.is_file():
        return False, "no receipt was written"
    try:
        rec = json.loads(receipt.read_text(encoding="utf-8"))
        rp = rec["predicate"]["run_parameters"]
    except (OSError, ValueError, KeyError, TypeError):
        return False, "the receipt could not be read"
    level = str(rp.get("confinement"))
    ok = _LEVELS.get(level, -1) >= _LEVELS[minimum]
    return ok, f"confinement was {level!r} (needs {minimum})"


def _receipt_exit(receipt: Path) -> tuple[str, str | None] | None:
    """(outcome, code) from the run's receipt - written by the runtime to a
    path outside every grant, which the program cannot write - or None when
    there is no receipt to read."""
    try:
        rec = json.loads(receipt.read_text(encoding="utf-8"))
        ex = rec["predicate"]["exit"]
        code = ex.get("code")
        return str(ex.get("outcome")), (str(code) if code else None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


@dataclass
class Proc:
    returncode: int
    stdout: str
    stderr: str


def _spawn(cmd: list[str], cwd: Path, env: dict[str, str],
           timeout: int) -> Proc:
    try:
        done = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout + 10,
            stdin=subprocess.DEVNULL, check=False)
        return Proc(done.returncode, done.stdout, done.stderr)
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else ""
        err = e.stderr if isinstance(e.stderr, str) else ""
        return Proc(124, out, err + "\n[timed out]")


@dataclass
class Trace:
    """What one run left in the judge's channels: the process the judge
    spawned, the files it found under the workspace afterwards, the exit and
    the confinement the receipt records, and the breaks the per-run
    observers saw."""

    proc: Proc
    files: dict[str, str]
    exit: tuple[str, str | None] | None
    confined: tuple[bool, str]
    breaks: list[Break]

    def finished(self) -> bool:
        """Whether the run came to its own end: not killed by the judge's
        timeout, and not stopped by the runtime's time or memory ceiling.
        A run that did not finish printed some prefix of what it would
        have, which is nothing to judge by difference."""
        if self.proc.returncode == 124:
            return False
        return not (self.exit and self.exit[0] in ("timeout",
                                                   "out_of_memory"))


def _plain_command(sub: Submission, sabline: list[str], can: Canaries,
                   budget: str, timeout: int, memory_mb: int) -> list[str]:
    cmd = list(sabline)
    prog = (can.work / sub.program).as_posix()
    if sub.claim.runner == "eval":
        cmd += ["eval", prog, "--allow", budget, "--timeout", str(timeout)]
    else:
        cmd += ["run", prog]
        # C1's budget is the documented default (io); a deployment that
        # forwards words after -- names no --allow, which is the shape
        # the double-dash advisory is about. Every other claim names it.
        if budget != "io":
            cmd += ["--allow", budget]
    # the seed and the clock fixed, so a second run differs from the first
    # only in what the judge changed between them; the receipt at a path
    # outside every grant, where the runtime writes and the program cannot
    cmd += ["--seed", SEED, "--freeze-time", FROZEN_CLOCK,
            "--receipt", can.receipt.as_posix(),
            "--max-memory-mb", str(memory_mb)]
    if sub.argv:
        cmd += ["--", *sub.argv]
    return cmd


def _plain_run(sub: Submission, sabline: list[str], can: Canaries,
               budget: str, timeout: int, memory_mb: int) -> Trace:
    claim = sub.claim
    before = _tree_hashes(can.outside)
    env = _base_env()
    env["CANARY"] = can.nonce_env
    proc = _spawn(_plain_command(sub, sabline, can, budget, timeout,
                                 memory_mb), can.work, env, timeout)
    after = _tree_hashes(can.outside)
    breaks: list[Break] = []
    if "outside_write" in claim.observers:
        breaks += obs_outside_write(before, after)
    if "nonce_in_output" in claim.observers:
        breaks += obs_nonce_in_output(can, proc.stdout, proc.stderr, claim)
    return Trace(proc, _scan_written_files(can), _receipt_exit(can.receipt),
                 _confinement_ok(can.receipt, claim.min_confinement), breaks)


def run_once(sub: Submission, sabline: list[str], root: Path,
             timeout: int, memory_mb: int,
             require_confinement: bool = True) -> RunResult:
    claim = sub.claim
    can = build_canaries(root, sub)
    if "listener" in claim.observers:
        can.listener = Listener("127.0.0.1", 0)
        can.listener.start()
    try:
        budget = fill_budget(claim.budget, can)
        if claim.runner == "tools":
            return _run_tools(sub, sabline, can, budget, timeout, memory_mb)
        if claim.runner == "prover":
            return _run_prover_lie(sub, sabline, can, timeout, memory_mb,
                                   require_confinement)
        first = _plain_run(sub, sabline, can, budget, timeout, memory_mb)
        traces = [first]
        if (not first.breaks and first.finished()
                and "canary_diff" in claim.observers):
            # the nonce scan found nothing: the same run again, at the same
            # paths, with only the planted nonces changed
            again = rebuild_canaries(can, sub)
            second = _plain_run(sub, sabline, again, budget, timeout,
                                memory_mb)
            traces.append(second)
            if not second.breaks and second.finished():
                second.breaks += obs_canary_diff(
                    first.proc.stdout, first.files,
                    second.proc.stdout, second.files)
        breaks = [b for t in traces for b in t.breaks]
        if "listener" in claim.observers:
            breaks += obs_listener(can)
        if breaks:
            return RunResult("broken", breaks)
        if any(not t.finished() for t in traces):
            return RunResult("did-not-run",
                             note=f"the run did not finish within {timeout}s"
                                  ", so there is nothing to judge")
        ran = all(t.confined[0] for t in traces)
        why = traces[-1].confined[1]
        if (require_confinement and not ran
                and traces[-1].proc.returncode == 0):
            # the program ran to success but the judge could not confirm the
            # confinement this claim needs: it must not be scored as a hold
            return RunResult("did-not-run",
                             note=f"the run succeeded but {why}")
        note = why if ran else "the budget refused the run"
        if len(traces) == 2:
            note += ("; a second run, differing only in the planted secret, "
                     "printed and wrote the same")
        return RunResult("holds", note=note)
    finally:
        if can.listener:
            can.listener.stop()
        if can.decoy:
            can.decoy.stop()


# --------------------------------------------------------------------------
# the tools runner (C6, C7): the judge is the host

def _tool_manifest(kind: str, can: Canaries) -> dict[str, Any]:
    if kind == "email":
        return {
            "schema": "sabline.tools/1",
            "tools": {"send_email": {
                "description": "Send one message.",
                "arguments": {"type": "object", "properties": {
                    "to": {"type": "string"},
                    "body": {"type": "string"}},
                    "required": ["to"]},
                "cost": 1}},
            "allow": [],
            "ceiling": {"calls": 25, "cost": 40, "unit": "credits"},
        }
    return {
        "schema": "sabline.tools/1",
        "tools": {"vault": {"description": "Read the secret.",
                            "arguments": {"type": "object"},
                            "result": "secret"}},
        "allow": [],
        "ceiling": {"calls": 25, "cost": 40, "unit": "credits"},
    }


def _run_tools(sub: Submission, sabline: list[str], can: Canaries,
               budget: str, timeout: int, memory_mb: int) -> RunResult:
    if sub.claim.id == "C6":
        return _run_secret_diff(sub, sabline, can, budget, timeout,
                                memory_mb)
    manifest = _tool_manifest(sub.claim.manifest, can)
    man_path = can.root / "tools.json"
    man_path.write_text(json.dumps(manifest), encoding="utf-8")
    calls, _outputs, _ = _host_run(sub, sabline, can, budget, man_path,
                                   timeout, memory_mb, secret="unused")
    breaks = email_breaks(calls)
    return RunResult("broken", breaks) if breaks else RunResult(
        "holds", note=f"{len(calls)} call(s) reached the host, all allowed")


def email_breaks(calls: list[dict[str, Any]]) -> list[Break]:
    """C7's transcript rule: a send_email call the judge (the host) saw with
    a recipient outside the granted pattern, or a fourth one, means Sabline
    let past the door what it should have refused."""
    breaks: list[Break] = []
    for c in calls:
        to = str(c.get("arguments", {}).get("to", ""))
        if not to.endswith("@corp.com"):
            breaks.append(Break(
                "tool_transcript",
                f"a call reached the host with to={to!r}, outside the "
                "granted pattern"))
    if len([c for c in calls if c.get("tool") == "send_email"]) > 3:
        breaks.append(Break("tool_transcript",
                            "more calls reached the host than the ceiling "
                            "of 3 allows"))
    return breaks


def _run_secret_diff(sub: Submission, sabline: list[str], can: Canaries,
                     budget: str, timeout: int,
                     memory_mb: int) -> RunResult:
    manifest = _tool_manifest("secret", can)
    man_path = can.root / "tools.json"
    man_path.write_text(json.dumps(manifest), encoding="utf-8")
    secret_a = "AAA-" + secrets.token_hex(16)
    secret_b = "BBB-" + secrets.token_hex(16)
    _, out_a, _ = _host_run(sub, sabline, can, budget, man_path, timeout,
                            memory_mb, secret=secret_a)
    _, out_b, _ = _host_run(sub, sabline, can, budget, man_path, timeout,
                            memory_mb, secret=secret_b)
    if out_a != out_b:
        return RunResult("broken", [Break(
            "secret_diff",
            "stdout differed when only the secret differed, so the secret "
            "reached stdout")])
    return RunResult("holds",
                     note="stdout did not change with the secret")


def _host_run(sub: Submission, sabline: list[str], can: Canaries,
              budget: str, man_path: Path, timeout: int, memory_mb: int,
              secret: str) -> tuple[list[dict[str, Any]], str, int]:
    """Host the tool door for one run: log the calls, answer them, return
    the calls seen, the program's output, and the exit status."""
    prog = (can.work / sub.program).as_posix()
    cmd = list(sabline) + ["run", prog, "--tools", man_path.as_posix(),
                           "--allow", budget,
                           "--max-memory-mb", str(memory_mb)]
    if sub.argv:
        cmd += ["--", *sub.argv]
    env = _base_env()
    env["CANARY"] = can.nonce_env
    proc = subprocess.Popen(
        cmd, cwd=str(can.work), env=env, stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace")
    calls: list[dict[str, Any]] = []
    outputs: list[str] = []
    assert proc.stdin is not None and proc.stdout is not None
    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            kind = event.get("event")
            if kind == "output":
                outputs.append(str(event.get("text", "")))
            elif kind == "call":
                calls.append(event)
                reply: dict[str, Any] = {"id": event.get("id")}
                if event.get("tool") == "vault":
                    reply["result"] = secret
                    reply["secret"] = True
                else:
                    reply["result"] = "ok"
                proc.stdin.write(json.dumps(reply) + "\n")
                proc.stdin.flush()
            elif kind == "exit":
                break
        proc.wait(timeout=timeout + 10)
    except subprocess.TimeoutExpired:
        proc.kill()
    finally:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
    return calls, "\n".join(outputs), proc.returncode or 0


# --------------------------------------------------------------------------
# the prover runner (C8)

def _run_prover_lie(sub: Submission, sabline: list[str], can: Canaries,
                    timeout: int, memory_mb: int,
                    require_confinement: bool) -> RunResult:
    """Two channels, both the judge's. The prover's answer is `sabline audit
    --json`, which runs no program code: which functions carry a promise,
    and which of those it called proven. The run's exit is the receipt the
    judge asked the runtime to write at a path outside every grant, which a
    program under `io` cannot write. What the program printed is never
    read, so printing "E601" is worth nothing."""
    prog = (can.work / sub.program).as_posix()
    audit = _spawn(list(sabline) + ["audit", prog, "--json"], can.work,
                   _base_env(), timeout)
    try:
        report = json.loads(audit.stdout)
        functions = list(report.get("functions") or [])
    except (ValueError, AttributeError):
        return RunResult("did-not-run",
                         note="the prover's answer could not be read")
    promising = [f for f in functions
                 if f.get("requires") or f.get("ensures")]
    proven = [str(f.get("name")) for f in promising
              if f.get("status") == "proven"]
    unproven = [str(f.get("name")) for f in promising
                if f.get("status") != "proven"]
    if not proven:
        return RunResult("holds",
                         note="the prover settled no promise to break")
    cmd = list(sabline) + ["run", prog, "--allow", "io",
                           "--seed", SEED, "--freeze-time", FROZEN_CLOCK,
                           "--receipt", can.receipt.as_posix(),
                           "--max-memory-mb", str(memory_mb)]
    if sub.argv:
        cmd += ["--", *sub.argv]
    proc = _spawn(cmd, can.work, _base_env(), timeout)
    if proc.returncode == 124:
        return RunResult("did-not-run",
                         note=f"the run did not finish within {timeout}s, "
                              "so there is nothing to judge")
    exit_ = _receipt_exit(can.receipt)
    if exit_ is None:
        return RunResult("did-not-run",
                         note="no receipt was written, so the run's exit "
                              "could not be read")
    result = obs_prover_lie(proven, unproven, exit_)
    if result.outcome != "holds":
        return result
    ran, why = _confinement_ok(can.receipt, sub.claim.min_confinement)
    if require_confinement and not ran:
        return RunResult("did-not-run", note=f"{result.note}, but {why}")
    return RunResult("holds", note=f"{result.note}; {why}")


# --------------------------------------------------------------------------
# the whole judgement

def confinement_probe(sabline: list[str], root: Path) -> tuple[bool, str]:
    """A baseline run to confirm this machine gives full confinement; the
    judge will not score on a machine that does not."""
    prog = root / "probe.vel"
    prog.write_text('fn main() uses io { print("ok") }\n', encoding="utf-8")
    receipt = root / "probe-receipt.json"
    proc = _spawn(list(sabline) + ["run", prog.as_posix(), "--receipt",
                                   receipt.as_posix()], root, _base_env(), 30)
    if proc.returncode != 0:
        return False, f"the probe run failed: {proc.stderr.strip()[:200]}"
    return _confinement_ok(receipt, "full")


def judge(claim_id: str, submission_dir: Path, sabline: list[str],
          runs: int, timeout: int, memory_mb: int,
          require_confinement: bool = True) -> Report:
    sub = load_submission(submission_dir)
    if sub.claim.id != claim_id:
        # the scorer names the claim; a submission that names another is
        # refused on every platform, before anything is run
        return Report(claim_id, runs, "", "did not run", 0,
                      error=f"the submission is for {sub.claim.id}, not "
                            f"{claim_id}; the scorer names the claim, and "
                            "a submission is scored under no other")
    if sys.platform != "linux":
        return Report(claim_id, runs, "", "did not run", 0,
                      error="the judge runs on Linux only")
    digest = submission_digest(sub)
    if require_confinement:
        with tempfile.TemporaryDirectory(prefix="ctf-probe-") as pd:
            ok, why = confinement_probe(sabline, Path(pd))
        if not ok:
            return Report(claim_id, runs, digest, "did not run", 0,
                          error=f"this machine does not give full "
                                f"confinement ({why})")
    results: list[RunResult] = []
    for _ in range(runs):
        with tempfile.TemporaryDirectory(prefix="ctf-run-") as rd:
            results.append(run_once(sub, sabline, Path(rd), timeout,
                                    memory_mb, require_confinement))
    broken = sum(1 for r in results if r.outcome == "broken")
    did_not = sum(1 for r in results if r.outcome == "did-not-run")
    if did_not and not broken:
        verdict = "did not run"
    elif broken:
        verdict = f"broken {broken} of {runs}"
    else:
        verdict = "holds"
    return Report(claim_id, runs, digest, verdict, broken, results)


# --------------------------------------------------------------------------
# the self-test

def self_test(sabline: list[str], vulnerable: list[str] | None) -> int:
    """The judge is shown to find a real break before it is trusted to find
    a new one. Against the pinned Sabline every claim's holding example
    holds; against a build with the 8.1.1 double-dash hole, the C1 read
    submission is reported broken."""
    ok = True
    holds = HERE / "submissions" / "selftest-c1-holds"
    print("self-test: the C1 read submission against the pinned Sabline")
    rep = judge("C1", holds, sabline, runs=3, timeout=DEFAULT_TIMEOUT,
                memory_mb=DEFAULT_MEMORY_MB)
    print(f"  verdict: {rep.verdict}" + (f" ({rep.error})" if rep.error
                                         else ""))
    if rep.verdict != "holds":
        print("  FAIL: it should hold against a fixed Sabline")
        ok = False
    if vulnerable is not None:
        print("self-test: the same submission against the 8.1.1 hole")
        # 8.1.1 predates OS confinement (8.4), so the judge does not require
        # full confinement here: this direction tests that the observers
        # catch a real break, not the kernel. Real scoring, against the
        # pinned 8.6.0, always requires it.
        rep2 = judge("C1", holds, vulnerable, runs=3,
                     timeout=DEFAULT_TIMEOUT, memory_mb=DEFAULT_MEMORY_MB,
                     require_confinement=False)
        print(f"  verdict: {rep2.verdict}" + (f" ({rep2.error})"
                                              if rep2.error else ""))
        if not rep2.verdict.startswith("broken"):
            print("  FAIL: the judge must report the double-dash hole broken")
            ok = False
        else:
            for r in rep2.results:
                if r.breaks:
                    print(f"    {r.breaks[0].observer}: {r.breaks[0].detail}")
                    break
    else:
        print("self-test: no --vulnerable build given; the broken direction "
              "was not run (check_ctf.py installs velaris-lang==8.1.1 for it)")
        ok = False
    print("self-test: PASSED" if ok else "self-test: FAILED")
    return 0 if ok else 1


# --------------------------------------------------------------------------
# the command line

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="ctf.judge")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="judge one submission")
    # the scorer names the claim, never the submission: a submission whose
    # submission.json names another claim is refused, not scored under it
    r.add_argument("claim", choices=list(BY_ID),
                   help="the claim the submission is scored against")
    r.add_argument("submission")
    r.add_argument("--sabline", default="sabline")
    r.add_argument("--runs", type=int, default=5)
    r.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    r.add_argument("--max-memory-mb", type=int, default=DEFAULT_MEMORY_MB)
    r.add_argument("--json", action="store_true")
    st = sub.add_parser("self-test", help="show the judge finds a real break")
    st.add_argument("--sabline", default="sabline")
    st.add_argument("--vulnerable", default=None,
                    help="a command for a build with the 8.1.1 hole")
    sub.add_parser("claims", help="list the claims")
    args = ap.parse_args(argv)

    if args.cmd == "claims":
        for c in CLAIMS:
            print(f"{c.id}  budget={c.budget}")
            print(f"      no program under it {c.invariant}")
        return 0
    if args.cmd == "self-test":
        vuln = args.vulnerable.split() if args.vulnerable else None
        return self_test(args.sabline.split(), vuln)
    rep = judge(args.claim, Path(args.submission), args.sabline.split(),
                args.runs, args.timeout, args.max_memory_mb)
    if args.json:
        print(json.dumps(rep.to_json(), indent=2))
    else:
        print(f"claim {rep.claim}: {rep.verdict}")
        if rep.error:
            print(f"  {rep.error}")
        for i, res in enumerate(rep.results, 1):
            line = f"  run {i}: {res.outcome}"
            if res.note:
                line += f" - {res.note}"
            print(line)
            for b in res.breaks:
                print(f"    {b.observer}: {b.detail}")
    return 0 if not rep.error else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
