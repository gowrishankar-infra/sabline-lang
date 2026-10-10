"""A run through sabline-rt (9.0, M3): `sabline run` and `sabline.run`,
when `SABLINE_REFERENCE_RUNTIME` is `rust`.

decisions/0002: the commands stay in Python and the run inside them goes
through sabline-rt. Here that is literal. The command line still reads its
flags, builds the budget, and loads, checks and proves the program - the
prover stays in this package for good, and what it finds is what decides
whether a program runs - and then, instead of interpreting it, asks
`sabline-rt exec` to run it (rt/crates/sabline-rt/src/exec.rs says how the
two talk). What the program prints is written through this process's own
`sys.stdout`, what it logs through `sys.stderr`, and what it reads comes
from `sys.stdin` - or from the library's `stdin=` - so a run writes and
reads exactly what the same run in this package does. The receipt is
sabline-rt's, and says so: its producer is `sabline-rt`.

**What chooses it.** The variable MAINTENANCE.md reserved for 9.0, read
when a run starts: `rust` routes the run through sabline-rt, unset or
`python` leaves it to this package, as before, and anything else is
refused rather than guessed at. M7 is where its default flips and the call
moves from the binary to the C ABI; until then it is opt-in, and the
agreement gate reads nothing of it - the gate runs both runtimes whatever
it says (check_gate.py sets it both ways).

**What sabline-rt does not do yet**, and so what a run through it is not:

- *The network, Python and tools.* A run whose budget grants one of them
  to a program that can reach it - a function of the program uses it -
  is this package's, as it always was, and says so on the error channel.
  What such a run should do is a question for the maintainer
  (plan/9.0-m3-progress.md); this is the answer until there is one.
- *Confinement* (M4). Nothing is asked of the operating system, and the
  receipt's confinement says `none`, with the reason "nothing was asked of
  the operating system". Nothing else says so: whoever set the variable
  chose a runtime that does not confine yet, and a line on the error
  channel of every run would be a difference from the package's run that
  is not in the run.
- *Native code.* A run through sabline-rt is interpreted; what it does is
  the same, which is what `fuzz_native.py` holds.
"""
import json
import os
import shutil
import subprocess
from typing import Any, Callable

from .version import _INSTALL_DIR

VARIABLE = "SABLINE_REFERENCE_RUNTIME"
RUNTIMES = ("python", "rust")

# The effects whose work sabline-rt does not do yet, as a run's notice
# names them.
NOT_PORTED = (("net", "the network"), ("ffi", "Python"), ("tool", "a tool"))


class RuntimeChoiceError(ValueError):
    """SABLINE_REFERENCE_RUNTIME names no runtime."""


def chosen() -> str:
    """The runtime a run goes to: "python" or "rust". A value that is
    neither is refused - a typo that silently meant `python` would be a
    run in the runtime its user said not to use."""
    said = os.environ.get(VARIABLE, "").strip()
    if said in ("", "python"):
        return "python"
    if said == "rust":
        return "rust"
    raise RuntimeChoiceError(f"{VARIABLE} is {said!r}; it takes one of "
                             f"{', '.join(RUNTIMES)}, or nothing for python")


def binary() -> str | None:
    """sabline-rt: this checkout's own build (release, then debug), so that
    a checkout runs the crate beside it; else one on PATH (`cargo install
    sabline-rt`)."""
    exe = "sabline-rt.exe" if os.name == "nt" else "sabline-rt"
    for profile in ("release", "debug"):
        candidate = os.path.join(_INSTALL_DIR, "rt", "target", profile, exe)
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("sabline-rt")


def not_ported(funcs: list[Any], budget: Any) -> list[str]:
    """The effects whose work sabline-rt does not do that this run could
    reach: granted by the budget and used by a function of the program -
    none of the program's functions can call a builtin of an effect it does
    not declare (E300), so a run reaches no other."""
    used = set().union(*(set(f.effects) for f in funcs)) if funcs else set()
    return [e for e, _ in NOT_PORTED
            if e in used and e in getattr(budget, "effects", ())]


def fallback_notice(effects: list[str]) -> str:
    """What the command line says when a run that was to go through
    sabline-rt is this package's instead."""
    named = ", ".join(dict(NOT_PORTED)[e] for e in effects)
    return (f"sabline: this run is the Python package's, not sabline-rt's: "
            f"its budget grants {named}, which sabline-rt does not do yet "
            f"({VARIABLE}=rust)")


class Unavailable(RuntimeError):
    """sabline-rt cannot be found or cannot be started."""


def run(path: str, *, allow: str | None, seed: Any = None,
        freeze_time: Any = None, max_read: int | None = None,
        args: list[str] | None = None, name: str | None = None,
        source: str | None = None,
        out: Callable[[str], Any], err: Callable[[str], Any],
        read_line: Callable[[], str], ask: Callable[[str], str | None],
        event: Callable[[dict[str, Any]], Any] | None = None,
        cwd: str | None = None) -> tuple[dict[str, Any], Any]:
    """Run the program at `path` through `sabline-rt exec` and give back
    its run document and receipt. As it runs, `out` and `err` are handed
    what it writes, `read_line` and `ask` answer what it asks - `ask` with
    None for the end of the input - and `event`, when given, each event of
    its audit stream. `allow` is the budget as the command line writes it
    (`Budget.spec()`), so sabline-rt parses the budget this package did;
    `source`, when given, is the program's text, where the file at `path`
    is only where its imports resolve from."""
    exe = binary()
    if exe is None:
        raise Unavailable(f"{VARIABLE}=rust, and sabline-rt is neither built "
                          f"in this checkout nor on PATH (cargo install "
                          f"sabline-rt)")
    request = {"path": path, "allow": allow, "seed": seed,
               "freeze_time": freeze_time, "max_read": max_read,
               "args": list(args or []), "name": name, "source": source,
               "stream": event is not None}
    try:
        proc = subprocess.Popen([exe, "exec", "--install-dir", _INSTALL_DIR],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, cwd=cwd)
    except OSError as e:
        raise Unavailable(f"sabline-rt ({exe}) cannot be started: "
                          f"{e.strerror or e}") from None
    assert proc.stdin is not None and proc.stdout is not None

    def say(doc: dict[str, Any]) -> None:
        assert proc.stdin is not None
        proc.stdin.write(json.dumps(doc).encode("ascii") + b"\n")
        proc.stdin.flush()

    end = None
    try:
        say(request)
        for raw in proc.stdout:
            frame = json.loads(raw)
            if "out" in frame:
                out(frame["out"])
            elif "err" in frame:
                err(frame["err"])
            elif "read" in frame:
                say({"line": read_line()})
            elif "ask" in frame:
                say({"line": ask(frame["ask"])})
            elif "event" in frame:
                if event is not None:
                    event(frame["event"])
            elif "end" in frame:
                end = frame["end"]
                break
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass
        if end is None:            # we are leaving early: so is the run
            proc.kill()
        proc.wait()
        stderr = proc.stderr.read() if proc.stderr else b""
        if proc.stderr:
            proc.stderr.close()
        proc.stdout.close()
    if end is None:
        raise Unavailable(f"sabline-rt ended without finishing the run "
                          f"(status {proc.returncode}): "
                          f"{stderr.decode('utf-8', 'replace')[-2000:]}")
    return end["document"], end["receipt"]
