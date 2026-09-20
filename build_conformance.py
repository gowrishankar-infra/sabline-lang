#!/usr/bin/env python3
"""Write sabline-spec's conformance corpus from this repository's suites.

The corpus is sabline-spec's tests/ directory: one JSON file per case,
for an implementation of the capability format that has never seen
sabline.py. Every case is transcribed from a table in one of three
suites - check_sandbox.py (level 2), check_library.py and
check_ratchet.py (levels 1 and 3) - where the same entry is asserted
against this implementation. Nothing here runs Sabline or computes an
expectation: what the corpus expects is what the suite expects, so the
two cannot say different things.

    python build_conformance.py ../sabline-spec/tests          # write it
    python build_conformance.py --check ../sabline-spec/tests  # drift test

--check writes nothing. It fails (exit 1) when the corpus on disk is not
what this would write - a file changed, missing or left over - which is
how CI keeps the committed corpus and the suites from diverging.
"""
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import check_library  # noqa: E402
import check_ratchet  # noqa: E402
import check_sandbox  # noqa: E402

FORMAT = "sabline.conformance-corpus/1"
LEVELS = {1: "Declaration", 2: "Enforcement", 3: "Ratchet"}


def short(*parts: Any) -> str:
    """A stable ten-character name for a case that has no id of its own."""
    text = json.dumps(parts, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def case(id: Any, level: Any, kind: Any, description: Any, source: Any, input: Any, expect: Any, *, spec: Any = (),
         requires: Any = (), known_limit: Any = None) -> dict[str, Any]:
    return {"id": id, "level": level, "kind": kind,
            "description": description, "spec": list(spec),
            "from": source, "requires": sorted(requires),
            "known_limit": known_limit, "input": input, "expect": expect}


# ---- level 1: the budget grammar and the effect surface ---------------------

# A denial with no grants narrows whatever budget the runtime gives a
# run that asked for none, and sabline-spec 4.6 leaves that to the
# runtime - it is io for this one from 5.0, and was all seven before.
# So such a case says something about this implementation, not about
# the format, and the corpus leaves it out.
DENY_WITHOUT_GRANTS = ("a denial with no grants narrows the runtime's "
                       "default budget, which sabline-spec 4.6 leaves "
                       "to the runtime")


def level1() -> tuple[Any, ...]:
    out, excluded = [], []
    for bid, what, allow, deny, want in check_library.BUDGETS:
        if allow is None and deny is not None and want is not None:
            excluded.append({"from": f"check_library.py BUDGETS {bid}",
                             "description": what,
                             "reason": DENY_WITHOUT_GRANTS})
            continue
        given = {}
        if allow is not None:
            given["allow"] = allow
        if deny is not None:
            given["deny"] = deny
        out.append(case(
            f"L1-budget-{bid}", 1, "budget", what,
            f"check_library.py BUDGETS {bid}", given,
            {"valid": False} if want is None else
            {"valid": True, "grants": want},
            spec=["4", "5"] if deny is None else ["4.4"]))
    for text in check_library.malformed_budgets():
        out.append(case(
            f"L1-budget-malformed-{short(text)}", 1, "budget",
            f"refused whole: {json.dumps(text, ensure_ascii=False)}",
            "check_library.py malformed_budgets()", {"allow": text},
            {"valid": False}, spec=["4.2"]))
    for a in check_library.AUDITS:
        files = dict(cast("dict[str, str]", a["files"]))
        out.append(case(
            f"L1-audit-{a['id']}", 1, "audit", a["description"],
            f"check_library.py AUDITS {a['id']}",
            {"files": files, "entry": next(iter(files))}, a["expect"],
            spec=["3.2", "8"]))
    return out, excluded


# ---- level 2: enforcement ---------------------------------------------------

def level2() -> tuple[Any, ...]:
    out, excluded = [], []
    for table, name in ((check_sandbox.ESCAPES, "ESCAPES"),
                        (check_sandbox.HONEST, "HONEST")):
        for c in table:
            where = f"check_sandbox.py {name} {c['id']}"
            if c["not_in_corpus"]:
                excluded.append({"from": where, "description": c["name"],
                                 "reason": c["not_in_corpus"]})
                continue
            given = {"fixture": "sandbox", "source": c["source"]}
            if c["allow"] is not None:
                given["allow"] = c["allow"]
            if c["deny"] is not None:
                given["deny"] = c["deny"]
            given["args"] = list(c["args"])
            if c["refused"]:
                expect = {"outcome": "refused", "code": c["refused"],
                          "stdout_includes": list(c["stdout"]),
                          "stdout_excludes": list(check_sandbox.MARKERS),
                          "must_not_exist": [c["creates"]] if c["creates"]
                          else []}
            else:
                expect = {"outcome": "completed",
                          "stdout_includes": list(c["stdout"])}
            out.append(case(f"L2-{c['id']}", 2, "run", c["name"], where,
                            given, expect, spec=c["spec"],
                            requires=c["requires"]))
    return out, excluded


# ---- level 3: the baseline, and the ratchet ----------------------------------

def level3() -> list[Any]:
    out = []
    r = check_ratchet
    for d in r.DERIVE:
        out.append(case(
            f"L3-derive-{d['id']}", 3, "derive", d["description"],
            f"check_ratchet.py DERIVE {d['id']}",
            {"tree": d["tree"], "root": d.get("root", ".")}, d["expect"],
            spec=d.get("spec", ["9.3"])))
    c: Any                     # a case of CHECKS, then a grant of COVERING
    for c in r.CHECKS:
        if c["baseline"] is None:
            base = {"from_tree": True, "edit": c["edit"]}
        else:
            base = dict(c["baseline"])
        out.append(case(
            f"L3-check-{c['id']}", 3, "check", c["description"],
            f"check_ratchet.py CHECKS {c['id']}",
            {"tree": c["tree"], "root": c["root"], "baseline": base,
             "change": c["change"]}, c["expect"], spec=c["spec"],
            requires=c["requires"], known_limit=c["known_limit"]))
    for s in r.SEQUENCES:
        steps = [{"description": st["description"], "change": st["change"],
                  "edit": st["edit"], "rewrite": st["rewrite"],
                  "delete_baseline": st["delete_baseline"]}
                 for st in cast("list[dict[str, Any]]", s["steps"])]
        out.append(case(
            f"L3-sequence-{s['id']}", 3, "sequence", s["description"],
            f"check_ratchet.py SEQUENCES {s['id']}",
            {"tree": s["tree"], "root": ".", "steps": steps},
            {"steps": [st["expect"] for st in
                       cast("list[dict[str, Any]]", s["steps"])]},
            spec=s["spec"]))
    for w in r.WRITE_GUARD:
        out.append(case(
            f"L3-write-{w['id']}", 3, "write-guard", w["description"],
            f"check_ratchet.py WRITE_GUARD {w['id']}",
            {"tree": w["tree"], "root": ".", "change": w["change"]},
            {"refuses": True, "unchanged": True}, spec=w["spec"]))
    want: Any                  # a bool, a list of grants, a bound: per table
    for b, c, want in r.COVERING:
        out.append(case(
            f"L3-covers-{short(b, c)}", 3, "covers",
            f"{b} {'covers' if want else 'does not cover'} {c}",
            "check_ratchet.py COVERING", {"grant": b, "other": c},
            {"covers": want}, spec=["9.5"]))
    for given, want in r.REDUCE:
        out.append(case(
            f"L3-reduce-{short(given)}", 3, "reduce",
            f"{', '.join(given)} reduced is {', '.join(want)}",
            "check_ratchet.py REDUCE", {"grants": given}, {"grants": want},
            spec=["9.2"]))
    for bid, what, source, want in r.BOUNDS:
        out.append(case(
            f"L3-bound-{bid}", 3, "bound", what,
            f"check_ratchet.py BOUNDS {bid}",
            {"source": source, "function": "main"}, want, spec=["9.4"]))
    return out


def corpus() -> dict[Any, Any]:
    """{relative path: text} - every file the corpus holds."""
    cases, excluded = level1()
    run_cases, more = level2()
    excluded += more
    cases += run_cases + level3()
    seen: set[str]
    files, seen = {}, set()
    for c in cases:
        assert c["id"] not in seen, f"two cases are called {c['id']}"
        assert c["id"].lower() not in {s.lower() for s in seen}
        seen.add(c["id"])
        files[f"L{c['level']}/{c['id']}.json"] = dump(c)
    index = {
        "format": FORMAT,
        "generated_by": "sabline-lang build_conformance.py, from "
                        "check_sandbox.py, check_library.py and "
                        "check_ratchet.py",
        "levels": {str(n): {"name": name,
                            "cases": sum(1 for c in cases
                                         if c["level"] == n)}
                   for n, name in LEVELS.items()},
        "cases": [{"id": c["id"], "level": c["level"], "kind": c["kind"],
                   "file": f"L{c['level']}/{c['id']}.json",
                   "known_limit": c["known_limit"] is not None,
                   "requires": c["requires"]} for c in cases],
        "excluded": excluded,
    }
    files["index.json"] = dump(index)
    return files


def dump(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def main(argv: list[Any]) -> int:
    check = "--check" in argv
    places = [a for a in argv if not a.startswith("-")]
    if len(places) != 1:
        print("usage: python build_conformance.py [--check] "
              "<sabline-spec>/tests", file=sys.stderr)
        return 2
    out = Path(places[0])
    want = corpus()
    # the case files and the index; README.md, the schema and anything
    # else a person wrote there are left alone
    have = {p.relative_to(out).as_posix(): p for p in out.rglob("*.json")
            if p.relative_to(out).parts[0] in ("L1", "L2", "L3")
            or p.name == "index.json" and p.parent == out} \
        if out.is_dir() else {}
    if check:
        wrong = []
        for rel, text in want.items():
            p = have.get(rel)
            if p is None:
                wrong.append(f"missing  {rel}")
            elif p.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
                wrong.append(f"differs  {rel}")
        wrong += [f"extra    {rel}" for rel in sorted(set(have) - set(want))]
        n = len(want) - 1
        if wrong:
            print(f"the corpus in {out} is not what the suites say "
                  f"({len(wrong)} file(s)):")
            for w in wrong[:40]:
                print(f"  {w}")
            if len(wrong) > 40:
                print(f"  and {len(wrong) - 40} more")
            print("regenerate it with: python build_conformance.py "
                  f"{out}, and commit it in sabline-spec")
            return 1
        print(f"the corpus in {out} matches the suites: {n} cases")
        return 0
    for rel in sorted(set(have) - set(want)):
        have[rel].unlink()
    for rel, text in want.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")
    levels = json.loads(want["index.json"])["levels"]
    print(f"wrote {len(want) - 1} cases to {out}: "
          + ", ".join(f"L{n} {v['cases']}" for n, v in levels.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
