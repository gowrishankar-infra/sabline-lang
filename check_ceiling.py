#!/usr/bin/env python3
"""The organisation ceiling (9.0, M3; decisions/0007, item 32c), at every
entry point, in both runtimes.

    python check_ceiling.py

A ceiling is a file whoever administers a machine installs, capping what
any budget on it may grant (sabline/ceiling.py). The system's own is at a
path this suite cannot write without being an administrator, so it
installs one where SABLINE_CEILING points - which is held as well as the
system's, never instead of it - and asks, at each entry point the decision
names, with SABLINE_REFERENCE_RUNTIME unset and set to `rust`:

  refused    a budget past the ceiling is E325 before the program is read,
             naming the file, the first grant past it and what it allows -
             the command line, `sabline test`, `sabline.run` with and
             without limits, a Pool and a PoolRegistry (the HTTP door's and
             the MCP server's runs), `sabline eval` and `sabline replay`
  runs       a budget inside it runs as it would without it
  receipt    the receipt names every ceiling the run was held to - path,
             sha256, what it allows - refused or not, and a refused run's
             receipt lists the refusal, E325, with the effect it is about
  broken     a ceiling that is not one refuses every run, saying why
  shown      `sabline ceiling` shows it, `--json` too, and `sabline audit`
             names it and the effect a program needs that it does not grant
  narrows    a wider ceiling widens nothing, and two ceilings give the same
             verdict in either order; the system's path is not one the
             environment moves

What the gate holds of it is the rest: both runtimes read a ceiling from
its text, hold a budget to it and word the refusal the same, over its rows
(agreement_runs.CEILING_RUNS).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from sabline import ceiling as _ceiling  # noqa: E402
from sabline import through_rt  # noqa: E402
from sabline.budget import Budget  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_ceiling")
SABLINE = [sys.executable, str(HERE / "sabline.py")]
PASSED = FAILED = 0
RUNTIMES = ("python", "rust")

READS = ('fn main() uses io, fs {\n    check read_file("data/in.txt") {\n'
         '        ok t {\n            print(t)\n        }\n'
         '        fail why {\n            print(why)\n        }\n    }\n}\n')
TESTS = ('fn test_reads() -> Bool uses fs {\n'
         '    check read_file("data/in.txt") {\n'
         '        ok t {\n            return true\n        }\n'
         '        fail why {\n            return false\n        }\n    }\n}\n')
PYTHON = ('fn main() uses io, ffi {\n    check py("math", "sqrt", ["4"]) {\n'
          '        ok t {\n            print(t)\n        }\n'
          '        fail why {\n            print(why)\n        }\n    }\n}\n')


def ok(label: str, good: object, detail: Any = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok      {label}")
    else:
        FAILED += 1
        print(f"  WRONG   {label}")
        if detail:
            print(f"          {str(detail)[:700]}")


def write_ceiling(name: str, allow: Any = None, raw: str | None = None) -> Path:
    path = WORK / name
    text = raw if raw is not None else json.dumps(
        {"schema": _ceiling.CEILING_SCHEMA, "allow": allow})
    path.write_text(text, encoding="utf-8")
    return path


class Env:
    """SABLINE_CEILING and SABLINE_REFERENCE_RUNTIME for as long as the block
    runs, put back after."""

    def __init__(self, ceiling: Path | None, runtime: str) -> None:
        self.set = {_ceiling.CEILING_ENV: None if ceiling is None else str(ceiling),
                    through_rt.RUNTIME_ENV: "rust" if runtime == "rust" else None}

    def __enter__(self) -> None:
        self.saved = {k: os.environ.get(k) for k in self.set}
        for k, v in self.set.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *_exc: Any) -> None:
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def cli(args: list[str], ceiling: Path | None, runtime: str
        ) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop(_ceiling.CEILING_ENV, None)
    env.pop(through_rt.RUNTIME_ENV, None)
    if ceiling is not None:
        env[_ceiling.CEILING_ENV] = str(ceiling)
    if runtime == "rust":
        env[through_rt.RUNTIME_ENV] = "rust"
    env["PYTHONIOENCODING"] = "utf-8"
    # an empty input: eval reads its program's input from standard input
    return subprocess.run(SABLINE + args, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env,
                          cwd=str(WORK), timeout=300, input="")


def named(receipt: Any, ceiling: Path) -> bool:
    """Does the receipt name `ceiling` - its path, its digest, what it
    allows - in its run parameters?"""
    try:
        said = receipt["predicate"]["run_parameters"]["ceilings"]
    except (KeyError, TypeError):
        return False
    digest = _ceiling.read_file(str(ceiling)).sha256
    return any(c.get("path") == str(ceiling) and c.get("sha256") == digest
               for c in said)


def refused_e325(receipt: Any, effect: str | None) -> bool:
    try:
        p = receipt["predicate"]
    except (KeyError, TypeError):
        return False
    return (p["exit"]["code"] == "E325" and p["exit"]["outcome"] == "refused"
            and any(r["code"] == "E325" and r["effect"] == effect
                    and r["stopped"] for r in p["refusals"]))


def command_line(ceiling: Path, wide: Path, broken: Path) -> None:
    program = WORK / "reads.vel"
    program.write_text(READS, encoding="utf-8")
    for runtime in RUNTIMES:
        receipt = WORK / f"r-{runtime}.json"
        done = cli([str(program), "--allow", "io,fs", "--receipt", str(receipt)],
                   ceiling, runtime)
        said = json.loads(receipt.read_text(encoding="utf-8")) \
            if receipt.exists() else None
        ok(f"[{runtime}] the command line: a budget past the ceiling is E325, "
           f"naming the file and the grant",
           done.returncode == 1 and "E325" in done.stderr
           and str(ceiling).replace(os.sep, "/") in done.stderr.replace(os.sep, "/")
           and "the budget's 'fs' grant" in done.stderr and done.stdout == "",
           done.stderr)
        ok(f"[{runtime}] its receipt is the refusal's, and names the ceiling",
           refused_e325(said, "fs") and named(said, ceiling), said)
        done = cli([str(program), "--allow", "io,fs:read:data", "--receipt",
                    str(receipt)], ceiling, runtime)
        said = json.loads(receipt.read_text(encoding="utf-8")) \
            if receipt.exists() else None
        ok(f"[{runtime}] a budget inside it runs, and its receipt names it",
           done.returncode == 0 and done.stdout == "inside\n"
           and said is not None and named(said, ceiling)
           and said["predicate"]["producer"]["name"]
           == ("sabline-rt" if runtime == "rust" else "sabline-lang"),
           (done.stdout, done.stderr, said))
        done = cli([str(program), "--allow", "io,fs:read:data"], broken, runtime)
        ok(f"[{runtime}] a ceiling that is not one refuses every run, saying why",
           done.returncode == 1 and "E325" in done.stderr
           and "is not one" in done.stderr and "it is not JSON" in done.stderr,
           done.stderr)
        done = cli([str(program), "--allow", "all"], wide, runtime)
        ok(f"[{runtime}] a ceiling of all caps nothing",
           done.returncode == 0 and done.stdout == "inside\n", done.stderr)
        tests = WORK / "tests.vel"
        tests.write_text(TESTS, encoding="utf-8")
        done = cli(["test", str(tests), "--allow", "io,fs"], ceiling, runtime)
        ok(f"[{runtime}] sabline test: E325 before a test is called",
           done.returncode == 1 and "E325" in done.stderr
           and "PASS" not in done.stdout, (done.stdout, done.stderr))
        done = cli(["test", str(tests), "--allow", "fs:read:data,io"], ceiling,
                   runtime)
        ok(f"[{runtime}] sabline test: inside it, the tests run",
           done.returncode == 0 and "1/1 passed" in done.stdout,
           (done.stdout, done.stderr))


def library(ceiling: Path) -> None:
    program = WORK / "reads.vel"
    source = READS
    # the library resolves a relative path where its caller is; this one
    # names the directory whole
    inside = f"io,fs:read:{os.path.realpath(WORK / 'data')}"
    for runtime in RUNTIMES:
        with Env(ceiling, runtime):
            routes: tuple[tuple[str, dict[str, Any]], ...] = (
                ("sabline.run", {}), ("sabline.run with limits", {"timeout": 60}))
            for how, limits in routes:
                r = sabline.run(source, path=str(program), allow="io,fs", **limits)
                ok(f"[{runtime}] {how}: E325, the receipt naming the ceiling",
                   not r.ok and r.problems and r.problems[0].code == "E325"
                   and refused_e325(r.receipt, "fs") and named(r.receipt, ceiling),
                   (r.problems, r.receipt))
                r = sabline.run(source, path=str(program),
                                allow=inside, **limits)
                ok(f"[{runtime}] {how}: inside it, it runs and is named",
                   r.ok and r.output == "inside\n" and named(r.receipt, ceiling),
                   (r.problems, r.output, r.receipt))
            with sabline.Pool(1, allow="io,fs") as pool:
                r = pool.run(source, path=str(program))
                ok(f"[{runtime}] a Pool: E325 for each run, named",
                   r.problems and r.problems[0].code == "E325"
                   and named(r.receipt, ceiling), (r.problems, r.receipt))
            with sabline.PoolRegistry(size=1) as pools:
                r = pools.run(source, path=str(program), allow="io,fs")
                ok(f"[{runtime}] a PoolRegistry - the doors' runs: E325",
                   r.problems and r.problems[0].code == "E325"
                   and named(r.receipt, ceiling), (r.problems, r.receipt))
                r = pools.run(source, path=str(program), allow=inside)
                ok(f"[{runtime}] a PoolRegistry: inside it, it runs",
                   r.ok and r.output == "inside\n" and named(r.receipt, ceiling),
                   (r.problems, r.receipt))


def eval_and_replay(ceiling: Path) -> None:
    program = WORK / "reads.vel"
    data = (WORK / "data").as_posix()
    for runtime in RUNTIMES:
        receipt = WORK / f"eval-{runtime}.json"
        done = cli(["eval", str(program), "--receipt", str(receipt),
                    "--allow", f"io,fs:read:{data},fs:write:{data}"], ceiling,
                   runtime)
        said = json.loads(receipt.read_text(encoding="utf-8")) \
            if receipt.exists() else None
        ok(f"[{runtime}] sabline eval: E325 in the receipt, named",
           refused_e325(said, "fs") and named(said, ceiling),
           (done.returncode, done.stderr[-400:], said))
        # a run recorded where no ceiling was, replayed where one is
        recorded = WORK / f"recorded-{runtime}.json"
        # named relatively, as a receipt replay reads must name it
        done = cli(["reads.vel", "--allow", "io,fs", "--receipt", str(recorded)],
                   None, runtime)
        done = cli(["replay", str(recorded), "--max-allow", "io,fs", "--json"],
                   ceiling, runtime)
        try:
            report = json.loads(done.stdout)
        except ValueError:
            report = {}
        replayed = report.get("replayed_receipt")
        ok(f"[{runtime}] sabline replay: E325 where a ceiling now is, named",
           refused_e325(replayed, "fs") and named(replayed, ceiling),
           (done.returncode, done.stderr[-400:], report))


def shown(ceiling: Path, broken: Path) -> None:
    done = cli(["ceiling"], ceiling, "python")
    ok("sabline ceiling shows the file and what it allows",
       done.returncode == 0 and str(ceiling) in done.stdout
       and "allows: fs:read" in done.stdout, done.stdout)
    done = cli(["ceiling", "--json"], ceiling, "python")
    try:
        doc = json.loads(done.stdout)
    except ValueError:
        doc = {}
    ok("sabline ceiling --json says the same",
       any(c.get("path") == str(ceiling) and c.get("broken") is None
           for c in doc.get("ceilings", [])), done.stdout)
    done = cli(["ceiling"], broken, "python")
    ok("sabline ceiling says a broken one is broken, and exits 1",
       done.returncode == 1 and "BROKEN" in done.stdout, done.stdout)
    py = WORK / "python.vel"
    py.write_text(PYTHON, encoding="utf-8")
    done = cli(["audit", str(py)], ceiling, "python")
    ok("sabline audit names the ceiling, and the effect it does not grant",
       str(ceiling) in done.stdout and "needs ffi" in done.stdout
       and "(E325)" in done.stdout, done.stdout)


def narrows() -> None:
    first = _ceiling.read("a.json", json.dumps(
        {"schema": _ceiling.CEILING_SCHEMA, "allow": "io,fs,net:*.corp.com"}))
    second = _ceiling.read("b.json", json.dumps(
        {"schema": _ceiling.CEILING_SCHEMA, "allow": "io,net@5,fs:read"}))
    wide = _ceiling.read("w.json", json.dumps(
        {"schema": _ceiling.CEILING_SCHEMA, "allow": "all"}))
    agree = True
    for spec in ("io", "io,fs", "io,fs:read", "io,net:api.corp.com",
                 "io,net:api.corp.com@3", "io,ffi", "io,net:x.other.com@1"):
        budget = Budget.parse(spec)
        verdicts = {_ceiling.refusal(order, budget) is None for order in
                    ([first, second], [second, first], [first, second, wide],
                     [wide, second, first])}
        agree = agree and len(verdicts) == 1
    ok("two ceilings give one verdict in any order, and a wider one widens "
       "nothing", agree)
    if os.name == "nt":
        saved = os.environ.get("ProgramData")
        os.environ["ProgramData"] = str(WORK)
        try:
            moved = _ceiling.system_path()
        finally:
            if saved is None:
                os.environ.pop("ProgramData", None)
            else:
                os.environ["ProgramData"] = saved
        ok("the system's path is the system's, whatever the environment says",
           not moved.startswith(str(WORK)), moved)
    else:
        ok("the system's path is fixed", _ceiling.system_path().startswith("/"))


def main() -> int:
    if through_rt.binary() is None:
        __import__("check_agreement").rt_binary()
    (WORK / "data").mkdir(exist_ok=True)
    (WORK / "data" / "in.txt").write_text("inside", encoding="utf-8")
    data = os.path.realpath(WORK / "data")
    ceiling = write_ceiling("ceiling.json", f"io,fs:read:{data}")
    wide = write_ceiling("wide.json", "all")
    broken = write_ceiling("broken.json", raw="{not json")
    command_line(ceiling, wide, broken)
    # a library run reads a relative path where its caller is
    os.chdir(WORK)
    try:
        library(ceiling)
    finally:
        os.chdir(HERE)
    eval_and_replay(ceiling)
    shown(ceiling, broken)
    narrows()
    print("-" * 62)
    print(f"{PASSED} correct, {FAILED} wrong")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
