"""velaris receipts diff: what a run did that its program's audit does not
say, and what it did that earlier runs of the same program did not (8.3).
"""
import json
import os
import posixpath
import sys

from .budget import BudgetError, _host_matches, _pct_decode, parse_host_port
from .values import log_line
from .statements import (StatementError, parse_json, read_statements,
                         statement_problems)
from typing import Any

# ---------------------------------------------------------------------------
# 19d. RECEIPTS DIFF - a receipt held to an audit, and to earlier receipts
#
#     A receipt holds no value the program handled, so it names no path it
#     read and no host it reached: what it names is what the run was granted
#     (its budget), what it used (effects_used, as counts), what was refused
#     (by code, effect and line) and what was declassified (by reason and
#     line). This compares those, and nothing it does not hold:
#
#     against an audit - of the program, or a velaris.audit/1 document, or a
#       capability Statement - each effect the run used or was refused must
#       be one the audit names; each host, path and module the budget
#       granted must be one the audit names (a directory granted counts when
#       a path the audit names lies in it); each declassification must be
#       one the audit records, by reason and line; an fs or net count must
#       not pass the audit's bound where it has one; and where the audit
#       carries digests, the receipt's subjects must be those bytes.
#     against earlier receipts of the same subjects - the same set of
#       digests - a host, path, module or effect no earlier run was granted
#       or used is new; a count above the most any earlier run reached is
#       named; so is the first declassification, and a reason not seen
#       before. Earlier receipts of other subjects are listed, not compared.
#
#     Exit 0 with no difference, 1 with any, 2 when a comparison could not
#     be made: a file that is not a receipt, an audit that cannot be read,
#     or no earlier receipt of the same subjects.
# ---------------------------------------------------------------------------


DIFF_SCHEMA = "velaris.receipts-diff/1"      # provisional (STABILITY.md)


class Unread(ValueError):
    """A document this comparison cannot read, and why."""


def load_receipt(path: str) -> dict[str, Any]:
    """The one receipt a file holds. Unread for anything else."""
    try:
        found = read_statements(path)
    except StatementError as e:
        raise Unread(str(e))
    if len(found) != 1:
        raise Unread(f"{path} holds {len(found)} Statements; a receipt is one")
    statement = found[0][0]
    kind, problems = statement_problems(statement)
    if kind != "receipt":
        raise Unread(f"{path} is not a receipt: "
                     + ("; ".join(problems) or "another predicate type"))
    if problems:
        raise Unread(f"{path} is not a receipt this reads: "
                     + "; ".join(problems))
    return statement


def grants(spec: str) -> dict[str, Any]:
    """What a receipt's budget grants, read as written - its paths are the
    machine's where the run was made, and are not resolved here."""
    out: dict[str, Any] = {"effects": set(), "hosts": set(),
                           "any_host": False, "paths": set(),
                           "any_path": set(), "modules": set(),
                           "any_module": False}
    for item in (s.strip() for s in spec.split(",") if s.strip()):
        body, _, count = item.rpartition("@")
        if not body or not count.isdigit():
            body = item
        if body == "ffi" or body.startswith("ffi:"):
            out["effects"].add("ffi")
            if body == "ffi":
                out["any_module"] = True
            else:
                out["modules"].add(body[4:].split(".")[0])
        elif body == "fs" or body.startswith("fs:"):
            out["effects"].add("fs")
            parts = body.split(":", 2)
            if len(parts) == 3:
                out["paths"].add((parts[1], _pct_decode(parts[2])
                                  .replace("\\", "/")))
            else:
                out["any_path"].add(parts[1] if len(parts) == 2 else "any")
        elif body == "net" or body.startswith("net:"):
            out["effects"].add("net")
            if body == "net":
                out["any_host"] = True
                continue
            try:
                out["hosts"].add(parse_host_port(body[4:]))
            except BudgetError:
                raise Unread(f"its budget names a host that does not parse: "
                             f"{item!r}")
        else:
            out["effects"].add(body)
    return out


def _host_text(host: str, port: Any) -> str:
    shown = f"[{host}]" if ":" in host else host
    return shown + (f":{port}" if port else "")


def _host_named(grant: tuple[str, Any], named: list[tuple[str, Any]]) -> bool:
    host, port = grant
    for a_host, a_port in named:
        if port is not None and a_port is not None and port != a_port:
            continue
        if host == a_host or _host_matches(host, a_host):
            return True
    return False


def _path_named(granted: str, named: list[str]) -> bool:
    """A granted path is named when the audit names it, or names a path in
    it: an audit's literal is as written in the program, and a granted path
    is absolute on the machine that ran it, so a literal matches the tail."""
    g = granted.rstrip("/")
    for literal in named:
        lit = posixpath.normpath(literal.replace("\\", "/"))
        if lit.startswith("/") or (len(lit) > 1 and lit[1] == ":"):
            if lit == g or lit.startswith(g + "/"):
                return True
            continue
        parts = [p for p in lit.split("/") if p not in ("", ".")]
        for n in range(1, len(parts) + 1):
            if g.endswith("/" + "/".join(parts[:n])) or g == "/".join(parts[:n]):
                return True
    return False


def load_audit(path: str) -> tuple[dict[str, Any], list[Any] | None, str]:
    """(the audit, the subjects it is bound to or None, what it is): a .vel
    program is attested here; a file is a velaris.audit/1 document or a
    capability Statement."""
    if path.endswith(".vel"):
        from .attestation import attest
        try:
            statement = attest(path)[0]
        except (ValueError, OSError) as e:
            raise Unread(f"{path} could not be audited: {e}")
        return (statement["predicate"]["audit"], statement["subject"],
                f"the audit of {path}")
    try:
        if os.path.getsize(path) > 64 * 1024 * 1024:
            raise Unread(f"{path} is larger than 64 MiB")
        with open(path, "rb") as fh:
            document = parse_json(fh.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Unread(f"{path} cannot be read as JSON: {e}")
    if isinstance(document, dict) and document.get("schema") == \
            "velaris.audit/1":
        return document, None, f"the audit in {path}"
    if isinstance(document, dict) and "_type" in document:
        kind, problems = statement_problems(document)
        if kind == "capability" and not problems:
            return (document["predicate"]["audit"], document["subject"],
                    f"the capability Statement {path}")
        raise Unread(f"{path} is not a capability Statement this reads: "
                     + "; ".join(problems or ["another predicate type"]))
    raise Unread(f"{path} is not a velaris.audit/1 document, a capability "
                 f"Statement or a .vel program")


def against_audit(receipt: dict[str, Any], audit: dict[str, Any],
                  subjects: list[Any] | None) -> tuple[list[Any], list[str]]:
    """(differences, what could not be compared)."""
    p = receipt["predicate"]
    granted = grants(p["budget"])
    diffs: list[dict[str, Any]] = []
    notes: list[str] = []
    if audit.get("ok") is False:
        notes.append("the audit's program did not compile, so the audit "
                     "bounds nothing it names")
    effects = set(audit.get("effects") or [])
    used = {e: n for e, n in (p.get("effects_used") or {}).items() if n}
    for effect in sorted(set(used) - effects):
        diffs.append({"kind": "effect", "what": effect,
                      "detail": f"the run used {effect} {used[effect]} "
                                f"time(s); the audit's effects do not "
                                f"include it"})
    for effect in sorted({r.get("effect") for r in p["refusals"]
                          if r.get("effect")} - effects - set(used)):
        diffs.append({"kind": "effect", "what": effect,
                      "detail": f"the run tried {effect} and was refused; "
                                f"the audit's effects do not include it"})
    net = audit.get("net_hosts") or {}
    if granted["hosts"]:
        if net.get("any"):
            notes.append("the audit names a host built while running, so "
                         "the hosts granted are not compared with it")
        else:
            named = []
            for entry in net.get("hosts") or []:
                try:
                    named.append(parse_host_port(str(entry)))
                except BudgetError:
                    continue
            for host in sorted(granted["hosts"], key=str):
                if not _host_named(host, named):
                    diffs.append({"kind": "host", "what": _host_text(*host),
                                  "detail": "the budget granted it; the "
                                            "audit names no such host"})
    fs_paths = audit.get("fs_paths") or {}
    for kind, path in sorted(granted["paths"]):
        if fs_paths.get(f"{kind}_any"):
            notes.append(f"the audit names a {kind} path built while "
                         f"running, so fs:{kind}:{path} is not compared")
            continue
        if not _path_named(path, [str(x) for x in fs_paths.get(kind) or []]):
            diffs.append({"kind": "path", "what": f"{kind}:{path}",
                          "detail": f"the budget granted it; the audit names "
                                    f"no {kind} path in it"})
    if granted["modules"]:
        if audit.get("ffi_any"):
            notes.append("the audit names a module built while running, so "
                         "the modules granted are not compared")
        else:
            for module in sorted(granted["modules"]
                                 - set(audit.get("ffi_modules") or [])):
                diffs.append({"kind": "module", "what": module,
                              "detail": "the budget granted it; the audit "
                                        "names no such module"})
    secrets = audit.get("secrets")
    recorded = {(d.get("reason"), d.get("line")) for d in
                (secrets or {}).get("declassifications") or []}
    for d in p["declassifications"]:
        if secrets is None:
            notes.append("the audit's secrets section is null, so "
                         "declassifications are not compared")
            break
        if (d.get("reason"), d.get("line")) not in recorded:
            diffs.append({"kind": "declassification",
                          "what": str(d.get("reason")),
                          "detail": f"line {d.get('line')}, {d.get('times')} "
                                    f"time(s); the audit records no "
                                    f"declassification with that reason at "
                                    f"that line"})
    counts = audit.get("counts")
    if isinstance(counts, dict):
        for effect in ("fs", "net"):
            bound = counts.get(effect)
            n = used.get(effect, 0)
            if isinstance(bound, int) and not isinstance(bound, bool) \
                    and n > bound:
                diffs.append({"kind": "count", "what": effect,
                              "detail": f"the run made {n} {effect} "
                                        f"operation(s); the audit's bound is "
                                        f"{bound}"})
    if subjects is None:
        notes.append("the audit carries no digests, so the receipt's "
                     "subjects are not compared with it")
    else:
        audited = [(s.get("name"), (s.get("digest") or {}).get("sha256"))
                   for s in subjects if isinstance(s, dict)]
        ran = [(s.get("name"), (s.get("digest") or {}).get("sha256"))
               for s in receipt["subject"]]
        if not audited or not ran or audited[0][1] != ran[0][1]:
            diffs.append({"kind": "subject", "what": str(ran[0][0] if ran
                                                         else None),
                          "detail": "the program that ran is not the "
                                    "audited bytes"})
        for name, digest in ran[1:]:
            if digest not in {d for _n, d in audited}:
                diffs.append({"kind": "subject", "what": str(name),
                              "detail": "the run read a file the audit was "
                                        "not made from"})
    return diffs, notes


def _subject_key(statement: dict[str, Any]) -> tuple[str, ...]:
    return tuple(sorted(str((s.get("digest") or {}).get("sha256"))
                        for s in statement.get("subject") or []
                        if isinstance(s, dict)))


def against_receipts(receipt: dict[str, Any],
                     earlier: list[tuple[str, dict[str, Any]]]
                     ) -> tuple[list[Any], list[str], list[Any]]:
    """(differences, the files compared, [{file, why}] left out)."""
    key = _subject_key(receipt)
    same = [(f, r) for f, r in earlier if _subject_key(r) == key]
    left = [{"file": f, "why": "a receipt of other subjects"}
            for f, r in earlier if _subject_key(r) != key]
    diffs: list[dict[str, Any]] = []
    if not same:
        return diffs, [], left
    now = grants(receipt["predicate"]["budget"])
    before = [grants(r["predicate"]["budget"]) for _f, r in same]
    for host in sorted(now["hosts"] - set().union(*(b["hosts"]
                                                    for b in before)), key=str):
        diffs.append({"kind": "new_host", "what": _host_text(*host),
                      "detail": "no earlier run of these subjects was "
                                "granted it"})
    for kind, path in sorted(now["paths"] - set().union(
            *(b["paths"] for b in before))):
        diffs.append({"kind": "new_path", "what": f"{kind}:{path}",
                      "detail": "no earlier run of these subjects was "
                                "granted it"})
    for module in sorted(now["modules"] - set().union(
            *(b["modules"] for b in before))):
        diffs.append({"kind": "new_module", "what": module,
                      "detail": "no earlier run of these subjects was "
                                "granted it"})
    used = receipt["predicate"].get("effects_used") or {}
    for effect in sorted(used):
        most = max(int((r["predicate"].get("effects_used") or {})
                       .get(effect, 0)) for _f, r in same)
        if used[effect] > most:
            diffs.append({"kind": "count_above_maximum", "what": effect,
                          "detail": f"{used[effect]} {effect} operation(s); "
                                    f"the most in an earlier run was {most}"})
    reasons = {d.get("reason") for _f, r in same
               for d in r["predicate"]["declassifications"]}
    mine = receipt["predicate"]["declassifications"]
    if mine and not any(r["predicate"]["declassifications"]
                        for _f, r in same):
        diffs.append({"kind": "first_declassification",
                      "what": ", ".join(sorted({str(d.get("reason"))
                                                for d in mine})),
                      "detail": "no earlier run of these subjects "
                                "declassified anything"})
    elif mine:
        for reason in sorted({str(d.get("reason")) for d in mine}
                             - {str(x) for x in reasons}):
            diffs.append({"kind": "new_declassification", "what": reason,
                          "detail": "no earlier run of these subjects "
                                    "declassified with this reason"})
    return diffs, [f for f, _r in same], left


def diff_report(receipt_path: str, audit_path: str | None,
                earlier_paths: list[str]) -> dict[str, Any]:
    """The velaris.receipts-diff/1 report, with its exit status in 'exit'."""
    report: dict[str, Any] = {"schema": DIFF_SCHEMA, "receipt": receipt_path,
                              "problems": []}
    try:
        receipt = load_receipt(receipt_path)
    except Unread as e:
        report["problems"].append(str(e))
        report["exit"] = 2
        return report
    report["subjects"] = receipt["subject"]
    unanswered = False
    total = 0
    if audit_path is not None:
        try:
            audit, subjects, what = load_audit(audit_path)
            diffs, notes = against_audit(receipt, audit, subjects)
            report["against_audit"] = {"source": what, "differences": diffs,
                                       "not_compared": notes}
            total += len(diffs)
        except Unread as e:
            report["problems"].append(str(e))
            unanswered = True
    if earlier_paths:
        files: list[str] = []
        for place in earlier_paths:
            if os.path.isdir(place):
                files += sorted(os.path.join(place, n) for n in os.listdir(
                    place) if n.endswith(".json"))
            else:
                files.append(place)
        same_file = os.path.normcase(os.path.realpath(receipt_path))
        earlier: list[tuple[str, dict[str, Any]]] = []
        unread = []
        for f in files:
            if os.path.normcase(os.path.realpath(f)) == same_file:
                continue
            try:
                earlier.append((f, load_receipt(f)))
            except Unread as e:
                unread.append({"file": f, "why": str(e)})
        diffs, compared, left = against_receipts(receipt, earlier)
        report["against_receipts"] = {"compared": compared,
                                      "left_out": left + unread,
                                      "differences": diffs}
        total += len(diffs)
        if not compared:
            report["problems"].append("no earlier receipt of the same "
                                      "subjects to compare with")
            unanswered = True
    if audit_path is None and not earlier_paths:
        report["problems"].append("name --audit, --against, or both")
        unanswered = True
    report["differences"] = total
    report["exit"] = 1 if total else 2 if unanswered else 0
    return report


def receipts_main(argv: list[Any]) -> int:
    """velaris receipts diff RECEIPT [--audit PROGRAM|AUDIT|STATEMENT]
    [--against RECEIPT|DIR ...] [--json]"""
    usage = ("usage: velaris receipts diff <receipt> [--audit PROGRAM | "
             "AUDIT | STATEMENT] [--against RECEIPT | DIR ...] [--json]")
    if argv[:1] != ["diff"]:
        print(usage, file=sys.stderr)
        return 2
    receipt = audit = None
    earlier: list[str] = []
    as_json = False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("--audit", "--against"):
            if i + 1 >= len(argv):
                print(f"velaris receipts diff: {a} needs a value",
                      file=sys.stderr)
                return 2
            if a == "--audit":
                if audit is not None:
                    print("velaris receipts diff: --audit is given twice",
                          file=sys.stderr)
                    return 2
                audit = argv[i + 1]
            else:
                earlier.append(argv[i + 1])
            i += 2
            continue
        if a == "--json":
            as_json = True
        elif a.startswith("-") or receipt is not None:
            print(usage, file=sys.stderr)
            return 2
        else:
            receipt = a
        i += 1
    if receipt is None:
        print(usage, file=sys.stderr)
        return 2
    report = diff_report(receipt, audit, earlier)
    if as_json:
        print(json.dumps(report, indent=2))
        return int(report["exit"])
    def say(text: str) -> None:
        # a receipt is someone else's text: a reason, a host or a name
        # holding a line feed or an escape must not forge a line of this
        print(log_line(text))

    first = (report.get("subjects") or [{}])[0]
    say(f"receipt:  {receipt}"
          + (f" ({first.get('name')} sha256:"
             f"{(first.get('digest') or {}).get('sha256', '')[:16]})"
             if first else ""))
    for p in report["problems"]:
        say(f"  NOT COMPARED  {p}")
    section = report.get("against_audit")
    if section is not None:
        say(f"against {section['source']}")
        for d in section["differences"]:
            say(f"  DIFFERS  {d['kind']} {d['what']}: {d['detail']}")
        for note in section["not_compared"]:
            say(f"  note     {note}")
    section = report.get("against_receipts")
    if section is not None:
        say(f"against {len(section['compared'])} earlier receipt(s) of "
              f"the same subjects"
              + (f" ({len(section['left_out'])} left out)"
                 if section["left_out"] else ""))
        for d in section["differences"]:
            say(f"  NEW      {d['kind']} {d['what']}: {d['detail']}")
        for left in section["left_out"]:
            say(f"  left out {left['file']}: {left['why']}")
    say("clean: no difference" if report["exit"] == 0 else
          f"{report['differences']} difference(s)" if report["exit"] == 1
          else "not compared")
    return int(report["exit"])
