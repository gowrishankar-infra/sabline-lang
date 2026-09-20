"""A receipt and an audit as a page a person can read (8.5).

`sabline receipt show FILE` and `sabline audit FILE --html` write one HTML
document: what was read, written and fetched - by grant, with counts - which
secrets were declassified and why, what was refused and where, what the
operating system held, how long it took, and the files it is about. `--text`
writes the same for a terminal.

The page is plain HTML with the documentation site's stylesheet inside it:
no script, no font, no image, nothing fetched, so it opens from a file in any
browser and reads the same with styles off. The same input gives the same
bytes - nothing of the machine or the moment it was rendered on is in it -
so a page can be kept beside the receipt it shows and compared later.

Every value is escaped where it is written. A receipt is a file somebody
hands you; nothing in one is trusted to be text.
"""
import html
import json
import os
import sys

from . import naming
from .version import SITE
from .receipt_diff import Unread, load_receipt
from typing import Any

# the site's stylesheet, shipped in the package so a page needs no network;
# check_viewers.py holds it to site/site.css byte for byte
_CSS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "site.css")
# what a page falls back to where the package was copied without it (an
# ejected program): the same document, plainly styled
_FALLBACK_CSS = ("body{font:16px/1.6 system-ui,sans-serif;max-width:72rem;"
                 "margin:2rem auto;padding:0 1rem}table{border-collapse:"
                 "collapse}th,td{border:1px solid #d0d7de;padding:4px 8px;"
                 "text-align:left}")

OUTCOMES = {
    "ok": "ran to its end",
    "refused": "stopped at a refusal",
    "failed": "stopped with an error",
    "timeout": "stopped at its time limit",
    "out_of_memory": "stopped at its memory limit",
    "did_not_compile": "did not compile, so nothing ran",
}


def _stylesheet() -> str:
    try:
        with open(_CSS_FILE, encoding="utf-8") as fh:
            return fh.read().replace("\r\n", "\n")
    except OSError:
        return _FALLBACK_CSS


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _times(n: Any) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "?"
    return "once" if n == 1 else f"{n} times"


# ---- what a receipt says, in the order a reader asks ---------------------------

def _grant_rows(predicate: dict[str, Any]) -> dict[str, list[tuple[str, Any]]]:
    """grants_used, sorted into what was read, written, fetched and called.
    A grant is the operator's text; the receipt never holds the path or the
    host the program asked for (sabline-spec 8.7)."""
    rows: dict[str, list[tuple[str, Any]]] = {
        "read": [], "written": [], "files": [], "fetched": [], "tools": []}
    for entry in predicate.get("grants_used") or []:
        if not isinstance(entry, dict):
            continue
        grant, times = str(entry.get("grant")), entry.get("times")
        if grant.startswith("fs:read"):
            rows["read"].append((grant[8:] or "any path", times))
        elif grant.startswith("fs:write"):
            rows["written"].append((grant[9:] or "any path", times))
        elif grant == "fs":
            rows["files"].append(("any path, read or written", times))
        elif grant == "net":
            rows["fetched"].append(("any host", times))
        elif grant.startswith("net:"):
            rows["fetched"].append((grant[4:], times))
        elif grant.startswith("tool"):
            rows["tools"].append((grant, times))
    return rows


def receipt_model(statement: dict[str, Any]) -> list[tuple[str, Any]]:
    """The sections of a receipt's page, in order: (title, content), where
    content is a paragraph (str), a table ((headers, rows)) or None for a
    section with nothing to say, which is still said."""
    p = statement.get("predicate") or {}
    params = p.get("run_parameters") or {}
    exit_ = p.get("exit") or {}
    used = p.get("effects_used")
    out: list[tuple[str, Any]] = []
    outcome = str(exit_.get("outcome"))
    summary = (f"{OUTCOMES.get(outcome, outcome)}; exit status "
               f"{exit_.get('status')}"
               + (f", {exit_.get('code')}" if exit_.get("code") else "")
               + f". Wall time {p.get('wall_time_ms')} ms, started "
                 f"{p.get('startedAt')}. "
               + ("" if p.get("complete", True) else
                  "This receipt is incomplete: the run was stopped before it "
                  "could answer, and the counts are of at least that many. "))
    out.append(("The run", summary))
    out.append(("Budget", str(p.get("budget") or "nothing")))
    rows = _grant_rows(p)
    has_grants = "grants_used" in p
    for title, key, none in (
            ("Read", "read", "No file was read."),
            ("Written", "written", "No file was written."),
            ("Fetched", "fetched", "No host was reached.")):
        found = rows[key] + (rows["files"] if key in ("read", "written")
                             else [])
        if found:
            out.append((title, (("under the grant", "operations"),
                                [(g, _times(t)) for g, t in found])))
        elif not has_grants and isinstance(used, dict) and used.get(
                "net" if key == "fetched" else "fs"):
            n = used["net" if key == "fetched" else "fs"]
            out.append((title, f"{n} operation(s) of this effect; a receipt "
                               f"written before 8.5 does not say under "
                               f"which grant."))
        else:
            out.append((title, none))
    if isinstance(used, dict):
        out.append(("Effects used", (("effect", "calls the budget let through"),
                                     [(e, n) for e, n in sorted(used.items())])))
    else:
        out.append(("Effects used", "Not known: the run was stopped before "
                                    "it could say."))
    if "tool_calls" in p:
        calls = p.get("tool_calls") or []
        ceiling = p.get("tool_ceiling") or {}
        out.append(("Tool calls", (("tool", "line", "calls",
                                    "arguments held to", "result"),
                                   [(c.get("tool"), c.get("line"),
                                     _times(c.get("times")),
                                     ", ".join(c.get("held_to") or [])
                                     or "no pattern",
                                     "secret" if c.get("secret") else "text")
                                    for c in calls]) if calls else
                    "No tool was called."))
        out.append(("Tool ceiling",
                    f"{ceiling.get('calls_used')} call(s) of "
                    f"{_limit(ceiling.get('calls'))}; "
                    f"{ceiling.get('cost_used')} of "
                    f"{_limit(ceiling.get('cost'))} {ceiling.get('unit')}. "
                    f"Manifest sha256 {ceiling.get('manifest_sha256')}."))
    decl = p.get("declassifications") or []
    out.append(("Secrets declassified", (
        ("reason written in the program", "line", "how often", "key"),
        [(d.get("reason"), d.get("line"), _times(d.get("times")),
          d.get("key_fingerprint") or "") for d in decl]) if decl else
        "No secret was declassified."))
    refusals = p.get("refusals") or []
    out.append(("Refused", (
        ("code", "effect", "line", "how often", "the run"),
        [(r.get("code") or "redirect", r.get("effect"), r.get("line"),
          _times(r.get("times")),
          "stopped here" if r.get("stopped") else "carried on")
         for r in refusals]) if refusals else "Nothing was refused."))
    layers = ", ".join(params.get("confinement_layers") or []) or "none"
    out.append(("Confinement",
                f"{params.get('confinement', 'not recorded')}: "
                f"{params.get('confinement_reason', '')} Layers: {layers}. "
                f"OS policy sha256 {params.get('os_policy_sha256')}."))
    out.append(("Limits and parameters", (
        ("parameter", "value"),
        [(k, "none" if params.get(k) is None else params.get(k))
         for k in ("timeout", "max_memory_mb", "max_read_bytes", "seed",
                   "freeze_time") if k in params])))
    out.append(("Subjects", (
        ("file", "sha256"),
        [(s.get("name"), (s.get("digest") or {}).get("sha256"))
         for s in statement.get("subject") or [] if isinstance(s, dict)])))
    producer = p.get("producer") or {}
    out.append(("Written by", f"{producer.get('name')} "
                              f"{producer.get('version')}, "
                              f"{p.get('specification')}, schema "
                              f"{p.get('schema')}."))
    return out


def _limit(value: Any) -> str:
    return "no limit" if value is None else str(value)


# ---- what an audit says ------------------------------------------------------------

def audit_model(audit: dict[str, Any]) -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    problems = audit.get("problems") or []
    out.append(("Verdict", "It compiles." if audit.get("ok") else
                "It does not compile; what follows is what could be read."))
    if problems:
        out.append(("Problems", (("code", "line", "message"),
                                 [(q.get("code"), q.get("line"),
                                   q.get("message")) for q in problems])))
    out.append(("Run it with", str(audit.get("safe_command"))))
    out.append(("Effects", ", ".join(audit.get("effects") or [])
                or "None: it is pure."))
    fs = audit.get("fs_paths") or {}
    for title, key in (("Reads", "read"), ("Writes", "write")):
        paths = list(fs.get(key) or [])
        if fs.get(key + "_any"):
            paths.append("a path built while running")
        out.append((title, (("path",), [(x,) for x in paths]) if paths else
                    "No file."))
    net = audit.get("net_hosts") or {}
    hosts = list(net.get("hosts") or [])
    if net.get("any"):
        hosts.append("a host built while running")
    out.append(("Fetches", (("host",), [(h,) for h in hosts]) if hosts else
                "No host."))
    tools = audit.get("tools") or {}
    names = list(tools.get("names") or [])
    if tools.get("any"):
        names.append("a tool named while running")
    out.append(("Tools", (("tool",), [(t,) for t in names]) if names else
                "No tool."))
    mods = audit.get("ffi_modules") or []
    native = audit.get("ffi_native") or {}
    out.append(("Python modules", (("module", "native code"),
                                   [(m, native.get(m, "")) for m in mods])
                if mods else ("A module named while running."
                              if audit.get("ffi_any") else "None.")))
    secrets = audit.get("secrets") or {}
    decl = secrets.get("declassifications") or []
    out.append(("Secrets",
                "Sources: " + (", ".join(secrets.get("sources") or [])
                               or "none") + ". "
                + ("It can declassify." if secrets.get("declassifies")
                   else "It declassifies nothing.")))
    if decl:
        out.append(("Declassifications", (
            ("reason", "function", "line"),
            [(d.get("reason"), d.get("function"), d.get("line"))
             for d in decl])))
    counts = audit.get("counts")
    if isinstance(counts, dict):
        out.append(("Most operations in one call", (
            ("effect", "bound"),
            [(k, "no bound in the text" if v is None else v)
             for k, v in sorted(counts.items())])))
    systems = (audit.get("confinement") or {}).get("systems") or {}
    if systems:
        out.append(("Confinement under that budget", (
            ("system", "level", "why"),
            [(s, v.get("level"), v.get("reason"))
             for s, v in sorted(systems.items())])))
    funcs = audit.get("functions") or []
    out.append(("Functions", (
        ("function", "effects", "can fail", "promises"),
        [(f.get("name"), ", ".join(f.get("effects") or []) or "pure",
          "yes" if f.get("can_fail") else "no", f.get("status"))
         for f in funcs]) if funcs else "None."))
    share = audit.get("proven_share")
    out.append(("Proven", "No function makes a promise." if share is None
                else f"{share}% of the functions that promise something "
                     f"are proven" + ("." if audit.get("prover") else
                                      "; no prover was there to try.")))
    warnings = audit.get("warnings") or []
    if warnings:
        out.append(("Warnings", (("warning",), [(w,) for w in warnings])))
    out.append(("Written by", f"sabline-lang {naming.version_of(audit)}, "
                              f"schema {audit.get('schema')}."))
    return out


# ---- the two renderings --------------------------------------------------------------

def render_text(title: str, sections: list[tuple[str, Any]]) -> str:
    lines = [title, "=" * len(title)]
    for name, content in sections:
        lines += ["", name]
        if isinstance(content, tuple):
            headers, rows = content
            table = [tuple(str(h) for h in headers)] + [
                tuple("" if c is None else str(c) for c in row)
                for row in rows]
            widths = [max(len(r[i]) for r in table)
                      for i in range(len(headers))]
            for r in table:
                lines.append("  " + "  ".join(
                    c.ljust(w) for c, w in zip(r, widths)).rstrip())
        else:
            lines.append("  " + str(content))
    return "\n".join(_printable(line) for line in lines) + "\n"


def _printable(line: str) -> str:
    """A line with every control character written as an escape: a receipt
    is somebody else's file, and a terminal acts on what it is sent."""
    return "".join(ch if ch.isprintable() else
                   ch.encode("unicode_escape").decode("ascii")
                   for ch in line)


def render_html(title: str, lead: str, sections: list[tuple[str, Any]]) -> str:
    parts = ["<!DOCTYPE html>", '<html lang="en">', "<head>",
             '<meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, '
             'initial-scale=1">',
             f"<title>{_e(title)}</title>",
             "<style>", _stylesheet().rstrip("\n"), "</style>", "</head>",
             "<body>", '<main class="doc wide">', f"<h1>{_e(title)}</h1>",
             f'<p class="lead">{_e(lead)}</p>']
    for name, content in sections:
        refused = name == "Refused" and isinstance(content, tuple)
        if refused:
            parts.append('<div class="callout callout-refuses">')
        parts.append(f"<h2>{_e(name)}</h2>")
        if isinstance(content, tuple):
            headers, rows = content
            parts.append('<div class="table-wrap"><table>')
            parts.append("<thead><tr>" + "".join(
                f'<th scope="col">{_e(h)}</th>' for h in headers)
                + "</tr></thead>")
            parts.append("<tbody>")
            for row in rows:
                parts.append("<tr>" + "".join(
                    f"<td>{_e(c)}</td>" for c in row) + "</tr>")
            parts.append("</tbody></table></div>")
        elif name in ("Budget", "Run it with"):
            parts.append(f"<p><code>{_e(content)}</code></p>")
        else:
            parts.append(f"<p>{_e(content)}</p>")
        if refused:
            parts.append("</div>")
    parts += [f'<p><a href="{_e(SITE)}/receipt/v1/">What a receipt is</a>, '
              f'and <a href="{_e(SITE)}/">Sabline</a>.</p>',
              "</main>", "</body>", "</html>"]
    return "\n".join(parts) + "\n"


def _subject_name(statement: dict[str, Any]) -> str:
    for s in statement.get("subject") or []:
        if isinstance(s, dict) and s.get("name"):
            return str(s["name"])
    return "a program"


def receipt_text(statement: dict[str, Any]) -> str:
    return render_text(f"Receipt of one run of {_subject_name(statement)}",
                       receipt_model(statement))


def receipt_html(statement: dict[str, Any]) -> str:
    return render_html(
        f"Receipt of one run of {_subject_name(statement)}",
        "What one run did: the budget it was given, what that budget let "
        "through and what it refused. It holds no value the program handled.",
        receipt_model(statement))


def audit_html(audit: dict[str, Any], name: str) -> str:
    return render_html(
        f"Audit of {name}",
        "What this program can touch, promise and fail at, read from its "
        "text before it runs.", audit_model(audit))


# ---- two receipts, side by side -----------------------------------------------------

def receipts_compared(first: dict[str, Any], second: dict[str, Any]
                      ) -> list[str]:
    """The fields two receipts differ in, one line each as `field: first ->
    second`. Times and digests of the moment are left out: they always
    differ."""
    a, b = first.get("predicate") or {}, second.get("predicate") or {}

    def one(v: Any) -> str:
        if not isinstance(v, dict):
            return str(v)
        if "grant" in v:
            return f"{v.get('grant')} x{v.get('times')}"
        if "stopped" in v:
            return (f"{v.get('code') or 'redirect'} ({v.get('effect')}) at "
                    f"line {v.get('line')}, x{v.get('times')}")
        if "reason" in v:
            return f"'{v.get('reason')}' at line {v.get('line')}"
        if "tool" in v:
            return f"{v.get('tool')} at line {v.get('line')}, x{v.get('times')}"
        return json.dumps(v, sort_keys=True, ensure_ascii=False)

    def short(v: Any) -> str:
        if v is None:
            return "none"
        if isinstance(v, list):
            return ", ".join(one(x) for x in v) or "none"
        if isinstance(v, dict):
            return ", ".join(f"{k} x{n}" for k, n in sorted(v.items())) \
                or "none"
        return str(v)

    lines = []
    sa = [s.get("name") for s in first.get("subject") or []]
    sb = [s.get("name") for s in second.get("subject") or []]
    if sa != sb:
        lines.append(f"subjects: {short(sa)} -> {short(sb)}")
    for key in ("budget", "effects_used", "grants_used", "refusals",
                "declassifications", "tool_calls"):
        if a.get(key) != b.get(key):
            lines.append(f"{key}: {short(a.get(key))} -> {short(b.get(key))}")
    ea, eb = a.get("exit") or {}, b.get("exit") or {}
    for key in ("outcome", "status", "code"):
        if ea.get(key) != eb.get(key):
            lines.append(f"exit.{key}: {short(ea.get(key))} -> "
                         f"{short(eb.get(key))}")
    pa, pb = a.get("run_parameters") or {}, b.get("run_parameters") or {}
    if pa.get("confinement") != pb.get("confinement"):
        lines.append(f"confinement: {pa.get('confinement')} -> "
                     f"{pb.get('confinement')}")
    return lines


# ---- the command ----------------------------------------------------------------------

def receipt_main(argv: list[Any]) -> int:
    """sabline receipt show RECEIPT [--text] [-o FILE]"""
    usage = "usage: sabline receipt show <receipt> [--text] [-o FILE]"
    if argv[:1] != ["show"]:
        print(usage, file=sys.stderr)
        return 2
    path, out_to, as_text = None, None, False
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--text":
            as_text = True
        elif a in ("-o", "--output"):
            if i + 1 >= len(argv):
                print(f"sabline receipt show: {a} needs a file",
                      file=sys.stderr)
                return 2
            out_to = argv[i + 1]
            i += 1
        elif a.startswith("-") or path is not None:
            print(usage, file=sys.stderr)
            return 2
        else:
            path = a
        i += 1
    if path is None:
        print(usage, file=sys.stderr)
        return 2
    try:
        statement = load_receipt(path)
    except Unread as e:
        print(f"sabline receipt show: {e}", file=sys.stderr)
        return 2
    page = receipt_text(statement) if as_text else receipt_html(statement)
    return write_page(page, out_to, "sabline receipt show")


def write_page(page: str, out_to: str | None, who: str) -> int:
    """The page to a file or to standard output, as the same bytes on every
    system: UTF-8, line feeds."""
    data = page.encode("utf-8")
    if out_to is None:
        out = getattr(sys.stdout, "buffer", None)
        if out is None:
            sys.stdout.write(page)
        else:
            sys.stdout.flush()
            out.write(data)
            out.flush()
        return 0
    try:
        with open(out_to, "wb") as fh:
            fh.write(data)
    except OSError as e:
        print(f"{who}: cannot write {out_to}: {e.strerror or e}",
              file=sys.stderr)
        return 2
    return 0
