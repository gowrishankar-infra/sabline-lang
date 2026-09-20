"""`velaris skill verify DIR` (8.5): what a skill would need, before it runs.

A skill here is a directory: the programs it runs (`*.vel`, anywhere under
it), the tool manifest its host offers them (`tools.json`, a velaris.tools/1
document, or the file --tools names), and whatever else it carries - a
SKILL.md, prompts - which this does not read beyond the `name:` of a
SKILL.md's front matter. Nothing is run. Each program is audited, and the
report is what a host has to decide on: the tools the programs name and
whether the manifest offers each, the budget that covers them all, the
secrets they declassify, the Python they call, and the manifest's own grants
and ceiling.

It fails (exit 1) when a program does not compile, names a tool the manifest
does not offer, names one with a value built while running, or calls through
`tool` a tool whose result the manifest marks secret. Exit 2 is a skill that
cannot be read. `--json` writes velaris.skill-verify/1, which is provisional
(STABILITY.md).
"""
import json
import os
import sys

from .nodes import Call, Str
from .tables import builtin_reached
from .loader import load_program
from .tools import ManifestError, read_manifest
from .library import _audit_here
from typing import Any

SKILL_VERIFY_SCHEMA = "velaris.skill-verify/1"


def _skill_name(root: str) -> str | None:
    try:
        with open(os.path.join(root, "SKILL.md"), encoding="utf-8") as fh:
            lines = fh.read(8192).split("\n")
    except OSError:
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if line.startswith("name:"):
            return line[5:].strip().strip("\"'") or None
    return None


def _tool_calls(path: str) -> list[tuple[str, str | None, int]]:
    """(builtin, the tool named as text or None, line) for each tool call in
    the program's own functions and everything it imports."""
    import dataclasses as _dc
    try:
        funcs, _ = load_program(path)
    except Exception:
        return []
    table = {f.name: f for f in funcs}
    found: list[tuple[str, str | None, int]] = []

    def visit(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            for x in node:
                visit(x)
            return
        if not _dc.is_dataclass(node):
            return
        if isinstance(node, Call):
            reached = builtin_reached(node.name, table)
            if reached in ("tool", "tool_secret"):
                named = node.args[0].value if node.args and isinstance(
                    node.args[0], Str) else None
                found.append((reached, named, node.line))
        for f in _dc.fields(node):
            visit(getattr(node, f.name))

    for fn in funcs:
        visit(fn.body)
    return found


def skill_report(root: str, manifest_path: str | None = None
                 ) -> dict[str, Any]:
    """The velaris.skill-verify/1 document of the skill at `root`.
    ValueError when the skill cannot be read at all."""
    if not os.path.isdir(root):
        raise ValueError(f"{root} is not a directory")
    manifest, manifest_name = None, None
    chosen = manifest_path or os.path.join(root, "tools.json")
    if manifest_path is not None or os.path.exists(chosen):
        try:
            with open(chosen, encoding="utf-8") as fh:
                manifest = read_manifest(fh.read())
        except (OSError, UnicodeDecodeError, ManifestError) as e:
            raise ValueError(f"the tool manifest {chosen} cannot be used: "
                             f"{getattr(e, 'strerror', None) or e}")
        manifest_name = os.path.relpath(chosen, root).replace(os.sep, "/")
    programs, problems = [], []
    grants: set[str] = set()
    needed: dict[str, dict[str, Any]] = {}
    files = []
    for dp, dirs, fns in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        files += [os.path.join(dp, f) for f in sorted(fns)
                  if f.endswith(".vel")]
    for path in sorted(files):
        shown = os.path.relpath(path, root).replace(os.sep, "/")
        with open(path, encoding="utf-8", errors="replace") as fh:
            audit = _audit_here(fh.read(), path=path).as_dict()
        budget = str(audit["safe_command"]).split("--allow ", 1)[-1]
        if budget != "''":
            grants.update(g for g in budget.split(",") if g)
        secrets = audit.get("secrets") or {}
        programs.append({
            "file": shown, "ok": audit["ok"], "effects": audit["effects"],
            "budget": budget, "tools": audit.get("tools"),
            "ffi_modules": audit["ffi_modules"],
            "declassifications": [d.get("reason") for d in
                                  secrets.get("declassifications") or []]})
        if not audit["ok"]:
            problems.append(f"{shown} does not compile: "
                            + "; ".join(str(p.get("message"))
                                        for p in audit["problems"][:3]))
            continue
        for builtin, named, line in _tool_calls(path):
            if named is None:
                problems.append(f"{shown}, line {line}: a tool is named with "
                                f"a value built while running, so what it "
                                f"calls cannot be read")
                continue
            entry = needed.setdefault(named, {"tool": named, "offered": None,
                                              "result": None, "cost": None,
                                              "called_from": []})
            entry["called_from"].append(f"{shown}:{line}")
            offered = (manifest or {}).get("tools", {}).get(named)
            if manifest is not None:
                entry["offered"] = offered is not None
                if offered is None:
                    problems.append(f"{shown}, line {line}: tool '{named}' "
                                    f"is not in {manifest_name}")
                else:
                    entry["result"], entry["cost"] = (offered["result"],
                                                      offered["cost"])
                    if offered["result"] == "secret" and builtin == "tool":
                        problems.append(
                            f"{shown}, line {line}: '{named}' gives a secret "
                            f"and is called through tool; tool_secret is "
                            f"what keeps it one (E323 when it runs)")
    if manifest is None and needed:
        problems.append("the programs call tools and the skill has no "
                        "tools.json: nothing says what they are")
    return {"schema": SKILL_VERIFY_SCHEMA, "skill": _skill_name(root),
            "ok": not problems, "problems": problems,
            "programs": programs,
            "tools": [needed[k] for k in sorted(needed)],
            "unused_tools": sorted(set((manifest or {}).get("tools", {}))
                                   - set(needed)),
            "budget": ",".join(sorted(grants)) or "''",
            "manifest": None if manifest is None else {
                "file": manifest_name, "allow": manifest["allow"],
                "ceiling": manifest["ceiling"]}}


def skill_main(argv: list[Any]) -> int:
    """velaris skill verify DIR [--tools MANIFEST] [--json]"""
    usage = "usage: velaris skill verify <dir> [--tools MANIFEST] [--json]"
    if argv[:1] != ["verify"]:
        print(usage, file=sys.stderr)
        return 2
    root, manifest, as_json = None, None, False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            as_json = True
        elif a == "--tools" and i + 1 < len(argv):
            manifest = argv[i + 1]
            i += 1
        elif a.startswith("-") or root is not None:
            print(usage, file=sys.stderr)
            return 2
        else:
            root = a
        i += 1
    if root is None:
        print(usage, file=sys.stderr)
        return 2
    try:
        report = skill_report(root, manifest)
    except ValueError as e:
        print(f"velaris skill verify: {e}", file=sys.stderr)
        return 2
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report["ok"] else 1
    print(f"skill: {report['skill'] or '(no SKILL.md name)'}  "
          f"{len(report['programs'])} program(s)")
    for p in report["programs"]:
        print(f"  {p['file']}: {'ok' if p['ok'] else 'DOES NOT COMPILE'}; "
              f"needs {p['budget']}")
        for reason in p["declassifications"]:
            print(f"      declassifies: {reason}")
        if p["ffi_modules"]:
            print(f"      calls Python: {', '.join(p['ffi_modules'])}")
    print("tools it would call:")
    for t in report["tools"]:
        where = ("no manifest" if t["offered"] is None else
                 "NOT OFFERED" if not t["offered"] else
                 f"offered, result {t['result']}, cost {t['cost']:g}")
        print(f"  {t['tool']}: {where}; called from "
              f"{', '.join(t['called_from'])}")
    if not report["tools"]:
        print("  none")
    if report["unused_tools"]:
        print(f"offered and never called: {', '.join(report['unused_tools'])}")
    print(f"budget that covers every program: {report['budget']}")
    m = report["manifest"]
    if m is not None:
        c = m["ceiling"]
        print(f"the manifest's own grants: {', '.join(m['allow']) or 'none'}")
        print(f"ceiling: {c['calls'] if c['calls'] is not None else 'no limit on'} "
              f"call(s), {c['cost'] if c['cost'] is not None else 'no limit on'} "
              f"{c['unit']}")
    for problem in report["problems"]:
        print(f"PROBLEM: {problem}")
    return 0 if report["ok"] else 1
