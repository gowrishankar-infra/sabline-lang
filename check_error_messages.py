#!/usr/bin/env python3
"""Every error code, and the exact words it says.

check_refusals.py holds that a wrong program is refused for the right
reason. This holds the words: for every code in sabline.ERROR_TABLE at
least one case under tests/error_messages/ produces that code, and what
it says is compared, character for character, with the message recorded
in tests/error_messages/golden.json. A message cannot change without
someone deciding that it should.

What is compared is the problem's code, its line (where the case has
one) and Problem.message: the one-line message a SablineError carries,
without the "how to fix" list or the `reference:` line that human()
adds around it. Only what is not the message's own is normalised first:
the case's scratch directory and program path become <dir> and <file>
(in every spelling the compiler gives them - resolved, case-folded,
either separator), the separators in the rest of such a path become /,
line endings become \\n, and the version string becomes <version>.

golden.json maps a case id to its code, how it is reached, its line and
its message. The program, where there is one, is <id>.vel beside it,
or the text of the case's "source" when <id>.vel would stop the
repository's own capability ratchet, which compiles every .vel file, at
its check ceiling: the two cases that push a check past its ceilings.
How a case is reached is one of:

    check    sabline.check(source, path=<file>, timeout=None,
             max_memory_mb=None) - in this process, as before 8.1 - or
             with the ceiling the "how" names
    run      sabline.run(source, path=<file>, allow=[...]) with the
             budget, args, stdin and ceilings the "how" names
    cli      python sabline.py <argv>, reading the --json problem the
             command prints
    library  a named call with particular arguments (LIBRARY below)

Every case runs with its own scratch directory as the working directory,
so a program names its files relatively. `<dir>` and `<file>` in a "how"
are that directory and the program's path there.

    python check_error_messages.py              compare with the golden
    python check_error_messages.py --update     rewrite the golden's
                                                messages and lines from
                                                what the compiler says now
    python check_error_messages.py E613 E7      only the cases whose id
                                                starts with one of these

--update is for a deliberate change of wording. It prints every message
that changed, and it never changes a case's code: a case that now
produces a different code is a failure either way. A new case is an
<id>.vel file and a golden entry with its code and "how"; --update fills
in the rest.

A case that needs the prover (every E7xx, and check --strict) is skipped
without z3, as is one that needs a memory cap this machine does not
enforce; each prints why. The suite fails if a code in ERROR_TABLE has
no case and is not in UNREACHABLE, which says why for each code it
lists. Nothing here reaches the internet: every host is a reserved
.example name, refused before any connection, or 127.0.0.1.
"""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterator, cast

HERE = Path(__file__).resolve().parent
SABLINE = HERE / "sabline.py"
CORPUS = HERE / "tests" / "error_messages"
GOLDEN = CORPUS / "golden.json"
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_error_messages")

try:
    import z3  # noqa: F401
    HAVE_Z3 = True
except ImportError:
    HAVE_Z3 = False

# Codes with no case, and why none can be made deterministically on every
# operating system. Kept as small as honesty allows; the suite prints it.
UNREACHABLE: dict[str, str] = {
    # 8.3: two codes a program cannot reach by itself in this harness
    "E615": "given only under sabline eval, to a run asked to stop from "
            "outside; check_eval.py stops one mid-loop and holds the receipt",
    "E616": "given only under sabline replay --responses, to a call its "
            "recording does not hold; check_receipts.py tampers with one",
    # 8.5: four codes that need a host on the other side of the tools door
    "E321": "given only to a tool call under sabline run --tools; "
            "check_runner.py hosts one and holds each refusal",
    "E322": "given only to a tool call under sabline run --tools, past a "
            "ceiling; check_runner.py passes each of the five",
    "E323": "given only to a tool call under sabline run --tools, whose "
            "arguments the manifest does not take; check_runner.py",
    "E324": "given only when the host on the tools door breaks its "
            "protocol; check_runner.py is that host, eleven ways",
    # 8.4: a code no program can reach at all
    "E319": "given only under the fault-injection hook (SABLINE_FAULT_INJECT), "
            "when the operating system's confinement refuses what the "
            "runtime itself attempted, and its message names this machine's "
            "layers; check_confine.py holds it on every leg",
}


class CaseError(Exception):
    """A case that could not be carried out as its "how" says."""


# ---------------------------------------------------------------------------
# normalising what is not the message's own
# ---------------------------------------------------------------------------
def _spellings(path: Any) -> set[Any]:
    """Every way the compiler may write this path in a message."""
    out = set()
    for p in {str(path), os.path.abspath(str(path)),
              os.path.realpath(str(path))}:
        for q in (p, os.path.normcase(p)):
            out.update({q, q.replace("\\", "/"), q.replace("\\", "\\\\")})
    return {s for s in out if s}


_PATH_TAIL = re.compile(r"<(?:dir|file)>[^\s'\"(),;]*")


def normalise(text: Any, case_dir: Path, program: Path) -> Any:
    """The message with the case's own paths, separators, line endings and
    the version string made the same on every machine."""
    if text is None:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    pairs = [(s, "<file>") for s in _spellings(program)]
    pairs += [(s, "<dir>") for s in _spellings(case_dir)]
    flags = re.IGNORECASE if os.name == "nt" else 0
    for spelling, token in sorted(pairs, key=lambda p: -len(p[0])):
        text = re.sub(re.escape(spelling), lambda _m, t=token: t, text,
                      flags=flags)
    text = _PATH_TAIL.sub(
        lambda m: m.group(0).replace("\\\\", "/").replace("\\", "/"), text)
    return text.replace(sabline.VERSION, "<version>")


def ascii_only(text: Any) -> str:
    """Printable on a cp1252 console."""
    return str(text).encode("ascii", "backslashreplace").decode("ascii")


# ---------------------------------------------------------------------------
# preparing a case
# ---------------------------------------------------------------------------
def fill(value: Any, case_dir: Path, program: Path) -> Any:
    """<dir> and <file> in a "how" value, as this run's real paths."""
    if isinstance(value, str):
        return value.replace("<file>", str(program)).replace(
            "<dir>", str(case_dir))
    if isinstance(value, list):
        return [fill(v, case_dir, program) for v in value]
    if isinstance(value, dict):
        return {k: fill(v, case_dir, program) for k, v in value.items()}
    return value


def _big_file(case_dir: Path, _how: dict[Any, Any]) -> None:
    """big.txt, ten bytes over one megabyte: the smallest --max-read."""
    (case_dir / "big.txt").write_bytes(b"A" * (1024 * 1024 + 10))


# Files a case needs beyond what the corpus holds, made fresh in its
# scratch directory. Named by the "setup" of a "how".
SETUPS = {"big_file": _big_file}


def prepare(case_id: str, how: dict[Any, Any]) -> tuple[Any, ...]:
    """The case's scratch directory, with its program, the corpus files
    it names, the directories and plain files it asks for, and its
    setup. Returns (directory, program path)."""
    case_dir = Path(os.path.realpath(WORK)) / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    program = case_dir / f"{case_id}.vel"
    source = CORPUS / f"{case_id}.vel"
    if how.get("source") is not None:
        program.write_text(how["source"], encoding="utf-8")
    elif source.exists():
        program.write_bytes(source.read_bytes())
    for name, corpus_name in (how.get("files") or {}).items():
        target = case_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((CORPUS / corpus_name).read_bytes())
    for name in how.get("dirs") or []:
        (case_dir / name).mkdir(parents=True, exist_ok=True)
    for name, text in (how.get("write") or {}).items():
        (case_dir / name).write_text(text, encoding="utf-8")
    if how.get("setup"):
        SETUPS[how["setup"]](case_dir, how)
    return case_dir, program


@contextlib.contextmanager
def environment(changes: dict[Any, Any]) -> Iterator[Any]:
    """os.environ with these set (a value of None unsets the name), put
    back afterwards."""
    saved = {k: os.environ.get(k) for k in changes}
    try:
        for k, v in changes.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def inside(case_dir: Path) -> Iterator[Any]:
    """The case's directory as the working directory, and what the
    compiler writes to this process's stdout and stderr kept off the
    suite's own output."""
    before = os.getcwd()
    os.chdir(case_dir)
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            yield
    finally:
        os.chdir(before)


# ---------------------------------------------------------------------------
# reaching a case
# ---------------------------------------------------------------------------
def first(problems: Any) -> tuple[Any, ...]:
    """(code, line, message) of the first problem."""
    if not problems:
        raise CaseError("no problem was reported")
    p = problems[0]
    return p.code, p.line, p.message


def via_check(how: Any, case_dir: Any, program: Any) -> Any:
    source = program.read_text(encoding="utf-8")
    kw = {"path": str(program), "prove": how.get("prove", True),
          "timeout": how.get("timeout"),
          "max_memory_mb": how.get("max_memory_mb")}
    if how.get("import_root"):
        kw["import_root"] = fill(how["import_root"], case_dir, program)
    with inside(case_dir):
        return first(sabline.check(source, **kw).problems)


def via_run(how: Any, case_dir: Any, program: Any) -> Any:
    source = program.read_text(encoding="utf-8")
    kw = {"path": str(program),
          "allow": fill(how.get("allow", ["io"]), case_dir, program),
          "args": fill(how.get("args", []), case_dir, program),
          "stdin": how.get("stdin", "")}
    for name in ("native", "timeout", "max_memory_mb"):
        if name in how:
            kw[name] = how[name]
    if how.get("import_root"):
        kw["import_root"] = fill(how["import_root"], case_dir, program)
    with inside(case_dir):
        return first(sabline.run(source, **kw).problems)


def _json_problems(text: str) -> list[Any]:
    """Every problem document in a command's output: a {"code": ...}
    object, or a list of them, wherever one starts a line."""
    found, decoder = [], json.JSONDecoder()
    for m in re.finditer(r"^[\[{]", text, flags=re.MULTILINE):
        try:
            doc, _ = decoder.raw_decode(text, m.start())
        except ValueError:
            continue
        docs = doc if isinstance(doc, list) else [doc]
        found += [d for d in docs if isinstance(d, dict) and "code" in d]
        if found:
            break
    return found


def via_cli(how: Any, case_dir: Any, program: Any) -> tuple[Any, ...]:
    argv = fill(how["argv"], case_dir, program)
    env = dict(os.environ)
    for k, v in (how.get("env") or {}).items():
        if v is None:
            env.pop(k, None)
        else:
            env[k] = fill(v, case_dir, program)
    done = subprocess.run([sys.executable, str(SABLINE)] + argv,
                          capture_output=True, text=True, cwd=case_dir,
                          env=env, timeout=how.get("wait", 120))
    problems = _json_problems(done.stdout) or _json_problems(done.stderr)
    if not problems:
        status: int | str
        status = done.returncode
        if status < 0 or status > 255:        # a signal, or a Windows
            status = f"{status} (0x{status & 0xFFFFFFFF:08X})"  # NTSTATUS
        said = (done.stderr or done.stdout).strip()
        raise CaseError(f"the command exited {status} with no --json "
                        f"problem; it printed "
                        + (repr(said[-300:]) if said else "nothing"))
    p = problems[0]
    return p.get("code"), p.get("line"), p.get("message")


def _doctor_self_test(how: Any, case_dir: Any, program: Any) -> tuple[Any, ...]:
    """E999 is raised inside doctor() when its compiler self-test finds a
    problem in `fn main() uses io { print(2 + 2) }`, and doctor() catches
    it at once to print its [FAIL] line. So the self-test is made to fail
    - the type checker is wrapped to report one invented problem - and
    the E999 error doctor() raises is recorded as it is made."""
    made = []
    # the names as doctor() looks them up - its own module's globals,
    # wherever in the compiler that module is
    names = sabline.doctor.__globals__
    real_error, real_types = names["SablineError"], names["check_types"]

    class Recorded(real_error):  # type: ignore[valid-type,misc]  # the class doctor() finds, read at run time
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            made.append(self)

    def failing_types(funcs: Any, records: Any, errors: Any) -> None:
        real_types(funcs, records, errors)
        errors.append(real_error("E501", "a problem made up by "
                                 "check_error_messages", 1))

    names["SablineError"], names["check_types"] = Recorded, failing_types
    try:
        with inside(case_dir):
            status = sabline.doctor()
    finally:
        names["SablineError"], names["check_types"] = real_error, real_types
    if status == 0:
        raise CaseError("doctor() passed with its self-test broken")
    ours = [e for e in made if e.code == "E999"]
    if not ours:
        raise CaseError("doctor() failed without raising E999")
    return ours[0].code, ours[0].line, ours[0].message


# A "library" case names one of these as its "call".
LIBRARY = {"doctor_self_test": _doctor_self_test}


def reach(how: Any, case_dir: Any, program: Any) -> Any:
    via = how.get("via")
    with environment(fill(how.get("env") or {}, case_dir, program)
                     if via != "cli" else {}):
        if via == "check":
            return via_check(how, case_dir, program)
        if via == "run":
            return via_run(how, case_dir, program)
        if via == "cli":
            return via_cli(how, case_dir, program)
        if via == "library":
            return LIBRARY[how["call"]](how, case_dir, program)
    raise CaseError(f"unknown way to reach a case: {via!r}")


def skip_reason(how: Any) -> str | None:
    """Why this case cannot be carried out here, or None."""
    needs = how.get("needs")
    if needs == "prover" and not HAVE_Z3:
        return "needs the prover"
    if needs == "memory cap" and not sabline.memory_cap_is_enforced():
        return (f"the memory cap is not enforced on {sys.platform}; "
                f"the timeout is what stops a runaway there")
    return None


# ---------------------------------------------------------------------------
# the suite
# ---------------------------------------------------------------------------
def shown(code: Any, line: Any, message: Any) -> str:
    where = f"line {line}" if line is not None else "no line"
    return ascii_only(f"[{code}] {where}: {message}")


def load_golden() -> dict[Any, Any]:
    return cast("dict[Any, Any]", json.loads(GOLDEN.read_text(encoding="utf-8")))


def save_golden(golden: dict[Any, Any]) -> None:
    text = json.dumps(golden, indent=2, sort_keys=True, ensure_ascii=True)
    GOLDEN.write_text(text + "\n", encoding="utf-8", newline="\n")


def coverage_problems(golden: dict[Any, Any]) -> list[Any]:
    """What is wrong with the corpus as a whole: a code with no case and
    no reason, a reason for a code that has a case or is not a code, a
    case for a code the table does not have, a program no case uses."""
    wrong = []
    table = sabline.ERROR_TABLE
    have = {entry.get("code") for entry in golden.values()}
    for code in sorted(table):
        if code not in have and code not in UNREACHABLE:
            wrong.append(f"{code} has no case and is not in UNREACHABLE")
    for code in sorted(UNREACHABLE):
        if code not in table:
            wrong.append(f"UNREACHABLE lists {code}, which ERROR_TABLE "
                         f"does not have")
        elif code in have:
            wrong.append(f"UNREACHABLE lists {code}, which has a case")
    for case_id, entry in sorted(golden.items()):
        if entry.get("code") not in table:
            wrong.append(f"{case_id} is for {entry.get('code')}, which "
                         f"ERROR_TABLE does not have")
        if not case_id.startswith(str(entry.get("code"))):
            wrong.append(f"{case_id} does not start with its code "
                         f"{entry.get('code')}")
    used = {f"{case_id}.vel" for case_id in golden}
    for entry in golden.values():
        used.update((entry.get("how") or {}).get("files", {}).values())
    for vel in sorted(CORPUS.glob("*.vel")):
        if vel.name not in used:
            wrong.append(f"{vel.name} is in the corpus and no case uses it")
    return wrong


def main(argv: Any) -> int:
    update = "--update" in argv
    only = [a for a in argv if not a.startswith("-")]
    golden = load_golden()
    chosen = {k: v for k, v in golden.items()
              if not only or any(k.startswith(o) for o in only)}
    began = time.monotonic()
    passed = failed = skipped = changed = 0
    print(f"{len(chosen)} error-message cases, {len(sabline.ERROR_TABLE)} "
          f"codes in ERROR_TABLE"
          + ("" if HAVE_Z3 else " (no prover: E7xx cases skip)"))
    print("-" * 62)
    for case_id, entry in sorted(chosen.items()):
        how, want_code = entry.get("how") or {}, entry.get("code")
        why = skip_reason(how)
        if why:
            print(f"  skip {want_code} ({why}): {case_id}")
            skipped += 1
            continue
        has_program = how.get("via") in ("check", "run") or \
            "<file>" in json.dumps(how.get("argv", []))
        if has_program and how.get("source") is None                 and not (CORPUS / f"{case_id}.vel").exists():
            print(f"  WRONG {want_code} {case_id}: {case_id}.vel is missing")
            failed += 1
            continue
        started = time.monotonic()
        try:
            case_dir, program = prepare(case_id, how)
            code, line, message = reach(how, case_dir, program)
            message = normalise(message, case_dir, program)
        except (CaseError, OSError, subprocess.SubprocessError) as e:
            print(f"  WRONG {want_code} {case_id}: {ascii_only(e)}")
            failed += 1
            continue
        took = time.monotonic() - started
        slow = f"  ({took:.1f}s)" if took >= 1 else ""
        if code != want_code:
            print(f"  WRONG {want_code} {case_id}: produced {code}, not "
                  f"{want_code}")
            print(f"        actual:   {shown(code, line, message)}")
            failed += 1
            continue
        same = (entry.get("message") == message
                and entry.get("line") == line)
        if same:
            print(f"  ok    {code} {case_id}{slow}")
            passed += 1
        elif update:
            print(f"  changed {code} {case_id}")
            print(f"        was: {shown(want_code, entry.get('line'), entry.get('message'))}")
            print(f"        now: {shown(code, line, message)}")
            entry["message"], entry["line"] = message, line
            changed += 1
            passed += 1
        else:
            print(f"  WRONG {code} {case_id}")
            print(f"        expected: {shown(want_code, entry.get('line'), entry.get('message'))}")
            print(f"        actual:   {shown(code, line, message)}")
            failed += 1
    if update and changed:
        save_golden(golden)
    print("-" * 62)
    if not only:
        for code, why in sorted(UNREACHABLE.items()):
            print(f"  unreached {code}: {why}")
        for problem in coverage_problems(golden):
            print(f"  WRONG coverage: {problem}")
            failed += 1
        cases_for = {e.get("code") for e in golden.values()}
        print(f"{len(cases_for & set(sabline.ERROR_TABLE))} of "
              f"{len(sabline.ERROR_TABLE)} codes have a case, "
              f"{len(UNREACHABLE)} listed unreachable")
    note = f", {skipped} skipped" if skipped else ""
    done = f", {changed} message(s) rewritten" if update else ""
    print(f"{passed} ok, {failed} wrong{note}{done} "
          f"in {time.monotonic() - began:.0f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
