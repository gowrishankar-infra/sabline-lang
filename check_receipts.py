#!/usr/bin/env python3
"""velaris receipts diff and velaris replay (8.3), each shape of difference
and each refusal, against real runs.

    python check_receipts.py

receipts diff, against an audit: a clean receipt; an effect used, a host, a
path and a module granted, a declassification and a count past the audit's
bound, each one the audit does not have; a program that is not the audited
bytes; the audit given as a program, as a velaris.audit/1 document and as a
capability Statement. Against earlier receipts: a new host, path and module,
a count above the earlier maximum, a first declassification and a new reason;
earlier receipts of other subjects left out, and nothing to compare with
exit 2. A file that is not a receipt this reads - an attestation, an unknown
type, a key given twice, a negative count - is exit 2.

replay: the same run is exit 0, output included when asked; a different
expected output is named; a changed program or import is refused before
anything runs; a receipt whose budget is wider than --max-allow is refused;
a receipt that drops an import from its subjects cannot make the replay read
that file; seeded randomness and a frozen clock replay the same; a bounded
run replays in a worker and an eval run under eval; tool responses recorded
from a module that answers differently every time replay the same output,
and a tampered recording stops the run with E616.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_receipts")
VELARIS = [sys.executable, str(HERE / "velaris.py")]
PASSED = FAILED = 0

READER = ('fn main() uses io, fs {\n    check read_file("data/in.txt") {\n'
          '        ok t {\n            print(t)\n        }\n'
          '        fail why {\n            print(why)\n        }\n    }\n}\n')
LUCKY = ('import "lib/pick.vel" as pick\n\n'
         'fn main() uses io, rand, clock {\n'
         '    print(to_text(pick.one(1000)))\n    print(to_text(now()))\n}\n')
PICK = 'fn one(n: Int) -> Int uses rand {\n    return random(n)\n}\n'
DECLASSIFY = ('fn main() uses io, fs, declassify {\n'
              '    check read_file_secret("data/key.txt") {\n'
              '        ok k {\n'
              '            print(to_text(declassify(length(k), "its length only")))\n'
              '        }\n        fail why {\n            print("no key")\n'
              '        }\n    }\n}\n')
TOOL = ('fn main() uses io, ffi {\n'
        '    check py("fickle_tools", "search", ["velaris"]) {\n'
        '        ok a {\n            print(a)\n        }\n'
        '        fail why {\n            print(why)\n        }\n    }\n}\n')
FICKLE = ('import random\n_n = [0]\n\n\ndef search(q):\n    _n[0] += 1\n'
          '    return f"{q} {random.random()} {_n[0]}"\n')


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


def velaris_cmd(*args: str, env: dict[str, str] | None = None
                ) -> subprocess.CompletedProcess[str]:
    return subprocess.run(VELARIS + list(args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          cwd=str(WORK), timeout=600, env=env)


def write(name: str, text: str) -> Path:
    path = WORK / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def load(name: str) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads((WORK / name).read_text(encoding="utf-8"))
    return doc


def dump(name: str, doc: Any) -> str:
    (WORK / name).write_text(json.dumps(doc), encoding="utf-8")
    return name


def diff(*args: str) -> tuple[int, dict[str, Any]]:
    done = velaris_cmd("receipts", "diff", *args, "--json")
    try:
        return done.returncode, json.loads(done.stdout)
    except ValueError:
        return done.returncode, {"stdout": done.stdout, "stderr": done.stderr}


def kinds(report: dict[str, Any], section: str) -> list[str]:
    return [d["kind"] for d in (report.get(section) or {}).get(
        "differences", [])]


def forged(base: dict[str, Any], change: Any) -> dict[str, Any]:
    doc: dict[str, Any] = json.loads(json.dumps(base))
    change(doc["predicate"])
    return doc


def diffs() -> None:
    print("receipts diff")
    print("-" * 62)
    write("data/in.txt", "hello\n")
    write("data/key.txt", "not-a-real-key\n")
    write("reader.vel", READER)
    for name in ("r1.json", "r2.json"):
        velaris_cmd("reader.vel", "--allow", "io,fs:read:data",
                    "--receipt", name)
    base = load("r1.json")
    code, report = diff("r1.json", "--audit", "reader.vel")
    ok("a receipt against its program's audit: clean, exit 0", code == 0
       and report.get("schema") == "velaris.receipts-diff/1"
       and report.get("differences") == 0, report)
    cases = [
        ("an effect the audit does not have", "effect",
         lambda p: p["effects_used"].update(net=2)),
        ("a host the audit does not name", "host",
         lambda p: p.update(budget=p["budget"] + ",net:collector.example.org")),
        ("a path the audit does not name", "path",
         lambda p: p.update(budget=p["budget"] + ",fs:write:/elsewhere/out")),
        ("a module the audit does not name", "module",
         lambda p: p.update(budget=p["budget"] + ",ffi:os")),
        ("a declassification the audit does not record", "declassification",
         lambda p: p.update(declassifications=[{"reason": "shown", "line": 2,
                                                "times": 1}])),
        ("more operations than the audit's bound", "count",
         lambda p: p["effects_used"].update(fs=40)),
    ]
    for label, kind, change in cases:
        name = dump(f"forged-{kind}.json", forged(base, change))
        code, report = diff(name, "--audit", "reader.vel")
        ok(f"against the audit: {label} is named ({kind}), exit 1",
           code == 1 and kind in kinds(report, "against_audit"), report)
    lying = json.loads(json.dumps(base))
    lying["subject"][0]["digest"]["sha256"] = "1" * 64
    code, report = diff(dump("forged-subject.json", lying), "--audit",
                        "reader.vel")
    ok("against the audit: a receipt of other bytes is named (subject)",
       code == 1 and "subject" in kinds(report, "against_audit"), report)
    audit = velaris.audit(READER, path=str(WORK / "reader.vel")).as_dict()
    dump("reader.audit.json", audit)
    code, report = diff("r1.json", "--audit", "reader.audit.json")
    ok("an audit given as velaris.audit/1: compared, and its lack of digests "
       "said", code == 0 and any("digests" in n for n in
                                 report["against_audit"]["not_compared"]),
       report)
    velaris_cmd("attest", "reader.vel", "--output", "reader.intoto.json")
    code, report = diff(dump("forged-subject2.json", lying), "--audit",
                        "reader.intoto.json")
    ok("an audit given as a capability Statement: its digests are compared",
       code == 1 and "subject" in kinds(report, "against_audit"), report)

    code, report = diff("r2.json", "--against", "r1.json")
    ok("against an earlier receipt of the same run: clean", code == 0
       and report["against_receipts"]["compared"] == ["r1.json"], report)
    more = forged(base, lambda p: (
        p.update(budget=p["budget"] + ",net:api.example.com:443,ffi:json,"
                 "fs:write:/tmp/new"),
        p["effects_used"].update(fs=9),
        p.update(declassifications=[{"reason": "shown", "line": 2,
                                     "times": 1}])))
    code, report = diff(dump("more.json", more), "--against", "r1.json",
                        "--against", "r2.json")
    got = kinds(report, "against_receipts")
    ok("against earlier receipts: a new host, path and module, a count above "
       "the maximum and a first declassification are each named",
       code == 1 and {"new_host", "new_path", "new_module",
                      "count_above_maximum", "first_declassification"}
       <= set(got), got)
    again = forged(more, lambda p: p.update(declassifications=[
        {"reason": "another reason", "line": 2, "times": 1}]))
    code, report = diff(dump("again.json", again), "--against", "more.json")
    ok("...and a declassification reason not seen before",
       code == 1 and "new_declassification" in kinds(report,
                                                     "against_receipts"),
       report)
    code, report = diff(dump("other.json", lying), "--against", "r1.json")
    ok("earlier receipts of other subjects are left out, and with none to "
       "compare the answer is exit 2", code == 2
       and report["against_receipts"]["left_out"], report)
    (WORK / "earlier").mkdir(exist_ok=True)
    (WORK / "earlier" / "a.json").write_text(json.dumps(base),
                                            encoding="utf-8")
    (WORK / "earlier" / "junk.json").write_text("{", encoding="utf-8")
    code, report = diff("r2.json", "--against", "earlier")
    ok("a directory of earlier receipts: each read, one that is not a "
       "receipt left out with why", code == 0 and any(
           "junk.json" in x["file"] for x in
           report["against_receipts"]["left_out"]), report)
    statement = velaris.attest(str(WORK / "reader.vel"))[0]
    for label, doc in [
            ("an attestation given as a receipt", statement),
            ("a Statement of an unknown type",
             dict(base, predicateType="https://velaris.dev/receipt/v1")),
            ("a negative count", forged(base, lambda p: p["effects_used"]
                                        .update(fs=-3))),
            ("a count that is not a number",
             forged(base, lambda p: p["effects_used"].update(fs="many")))]:
        code, report = diff(dump("unread.json", doc), "--audit", "reader.vel")
        ok(f"not read, exit 2: {label}", code == 2 and report["problems"],
           report)
    text = json.dumps(base)
    (WORK / "twice.json").write_text(text[:-1] + ', "subject": []}',
                                     encoding="utf-8")
    code, report = diff("twice.json", "--audit", "reader.vel")
    ok("not read, exit 2: a key given twice", code == 2, report)


def replays() -> None:
    print()
    print("replay")
    print("-" * 62)
    velaris_cmd("reader.vel", "--allow", "io,fs:read:data", "--receipt",
                "read.json")
    (WORK / "read.out").write_text("hello\n\n", encoding="utf-8")
    done = velaris_cmd("replay", "read.json", "--max-allow", "io,fs:read",
                       "--expect-output", "read.out", "--json")
    report = json.loads(done.stdout or "{}")
    ok("the same run: exit 0, its output as expected",
       done.returncode == 0 and report.get("differences") == []
       and report.get("output_compared") is True, done.stdout[-500:])
    (WORK / "wrong.out").write_text("goodbye\n", encoding="utf-8")
    done = velaris_cmd("replay", "read.json", "--max-allow", "io,fs:read",
                       "--expect-output", "wrong.out", "--json")
    report = json.loads(done.stdout or "{}")
    ok("a different output is named, with the first line that differs",
       done.returncode == 1 and report["differences"][-1]["field"] == "output"
       and report["differences"][-1]["first_differing_line"] == 1, report)
    done = velaris_cmd("replay", "read.json", "--json")
    report = json.loads(done.stdout or "{}")
    ok("a budget wider than --max-allow (io unless raised) is refused",
       done.returncode == 2 and "max-allow" in (report.get("refused") or ""),
       report)
    wide = load("read.json")
    wide["predicate"]["budget"] = "clock,env,fs,io,net,rand"
    done = velaris_cmd("replay", dump("wide.json", wide), "--max-allow",
                       "io,fs:read", "--json")
    ok("...a receipt whose budget was widened by hand among them",
       done.returncode == 2, done.stdout[-300:])
    write("lib/pick.vel", PICK)
    write("lucky.vel", LUCKY)
    velaris_cmd("lucky.vel", "--allow", "io,rand,clock", "--seed", "11",
                "--freeze-time", "2026-01-01T00:00:00Z", "--receipt",
                "lucky.json")
    first = velaris_cmd("lucky.vel", "--allow", "io,rand,clock", "--seed",
                        "11", "--freeze-time", "2026-01-01T00:00:00Z").stdout
    (WORK / "lucky.out").write_text(first, encoding="utf-8")
    done = velaris_cmd("replay", "lucky.json", "--max-allow", "io,rand,clock",
                       "--expect-output", "lucky.out")
    ok("a seeded, frozen-clock run with an import replays the same, output "
       "included", done.returncode == 0, done.stderr[-400:])
    write("lib/pick.vel", PICK.replace("random(n)", "random(n) + 1"))
    done = velaris_cmd("replay", "lucky.json", "--max-allow", "io,rand,clock",
                       "--json")
    report = json.loads(done.stdout or "{}")
    ok("a changed import is refused before anything runs, named",
       done.returncode == 2 and "lib/pick.vel" in (report.get("refused")
                                                   or ""), report)
    write("lib/pick.vel", PICK)
    dropped = load("lucky.json")
    dropped["subject"] = dropped["subject"][:1]
    write("lib/pick.vel", PICK.replace("random(n)", "random(n) + 1"))
    done = velaris_cmd("replay", dump("dropped.json", dropped), "--max-allow",
                       "io,rand,clock", "--json")
    report = json.loads(done.stdout or "{}")
    # the import resolves inside the replay's own directory, where only the
    # receipt's subjects were copied: not there (E512), or outside it (E515)
    ok("a receipt that drops an import from its subjects cannot make the "
       "replay read that file: it does not compile, and that is named",
       done.returncode == 1 and any(
           d["field"] == "exit" and (d["replayed"] or {}).get("code")
           in ("E512", "E515") for d in report.get("differences", [])),
       report)
    write("lib/pick.vel", PICK)
    # the library names the program as it was given: relative, from where
    # it ran (a receipt naming an absolute path is not replayed, as verify
    # does not read one)
    import os
    here = os.getcwd()
    os.chdir(WORK)
    try:
        bounded = velaris.run(READER, path="reader.vel",
                              allow="io,fs:read:" + str(WORK / "data"),
                              timeout=20, max_memory_mb=256)
    finally:
        os.chdir(here)
    dump("bounded.json", bounded.receipt)
    absolute = json.loads(json.dumps(bounded.receipt))
    absolute["subject"][0]["name"] = str(WORK / "reader.vel").replace(
        "\\", "/")
    done = velaris_cmd("replay", dump("absolute.json", absolute),
                       "--max-allow", "io,fs:read", "--json")
    ok("a receipt naming its program by an absolute path is refused, and "
       "that file is not read", done.returncode == 2
       and "absolute" in (json.loads(done.stdout or "{}").get("refused")
                          or ""), done.stdout[-300:])
    done = velaris_cmd("replay", "bounded.json", "--max-allow", "io,fs:read",
                       "--json")
    report = json.loads(done.stdout or "{}")
    ok("a run with a time and memory limit replays in a worker with them",
       done.returncode == 0, report.get("differences") or report)
    velaris_cmd("eval", "reader.vel", "--allow", "io,fs:read:data",
                "--receipt", "evaluated.json")
    done = velaris_cmd("replay", "evaluated.json", "--max-allow",
                       "io,fs:read", "--json")
    report = json.loads(done.stdout or "{}")
    ok("an eval run replays under eval's profile, its confinement the same",
       done.returncode == 0, report.get("differences") or report)
    write("declassify.vel", DECLASSIFY)
    velaris_cmd("declassify.vel", "--allow",
                "io,fs:read:data/key.txt,declassify", "--receipt", "d.json")
    done = velaris_cmd("replay", "d.json", "--max-allow", "io,fs,declassify")
    ok("a run that declassified replays with the same declassification",
       done.returncode == 0, done.stderr[-400:])
    source_receipt = velaris.run(READER, allow="io").receipt
    done = velaris_cmd("replay", dump("source.json", source_receipt),
                       "--json")
    ok("a receipt of a program given as text, with no file, is refused",
       done.returncode == 2, done.stdout[-300:])

    import os
    write("fickle_tools.py", FICKLE)
    write("tool.vel", TOOL)
    env = dict(os.environ, PYTHONPATH=str(WORK))
    recorded = velaris_cmd("tool.vel", "--allow", "io,ffi:fickle_tools",
                           "--receipt", "tool.json", "--record-responses",
                           "tool.responses.json", env=env)
    (WORK / "tool.out").write_text(recorded.stdout, encoding="utf-8")
    live = velaris_cmd("tool.vel", "--allow", "io,ffi:fickle_tools",
                       env=env).stdout
    ok("the tool answers differently every time it is called live",
       live != recorded.stdout and recorded.returncode == 0,
       [recorded.stdout, live])
    done = velaris_cmd("replay", "tool.json", "--max-allow",
                       "io,ffi:fickle_tools", "--responses",
                       "tool.responses.json", "--expect-output", "tool.out",
                       env=env)
    ok("code mode: replayed with its recorded responses, the output is the "
       "recorded run's", done.returncode == 0, done.stderr[-400:])
    tampered = load("tool.responses.json")
    tampered["calls"][0]["call"][1] = "delete_everything"
    done = velaris_cmd("replay", "tool.json", "--max-allow",
                       "io,ffi:fickle_tools", "--responses",
                       dump("tampered.json", tampered), "--json", env=env)
    report = json.loads(done.stdout or "{}")
    ok("...and a recording that does not match the call stops the run with "
       "E616, named", done.returncode == 1 and any(
           d["field"] == "exit" and (d["replayed"] or {}).get("code")
           == "E616" for d in report.get("differences", [])), report)
    done = velaris_cmd("replay", "tool.json", "--max-allow", "io",
                       "--responses", "tool.responses.json", "--json",
                       env=env)
    ok("...and recorded responses do not stand in for a grant: without "
       "ffi:fickle_tools the replay is refused", done.returncode == 2,
       done.stdout[-300:])
    done = velaris_cmd("replay", "bounded.json", "--max-allow", "io,fs:read",
                       "--responses", "tool.responses.json", "--json")
    ok("recorded responses with a run that had limits are refused, saying "
       "why", done.returncode == 2, done.stdout[-300:])


def main() -> int:
    diffs()
    replays()
    print("-" * 62)
    print(f"{PASSED} correct, {FAILED} wrong")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
