"""The budgets' corpus for the agreement gate (9.0, M2).

The budget parser is ported in M2 because a run must parse its budget
before it does anything, and its comparison surface is the *budget
document* (sabline/check_dump.py's `budget_document`, the crate's
`budget::budget_document`): for one budget case - a budget's text and the
effects it denies, as sabline-spec's conformance corpus gives them - the
shape a conformance case reads, the tools, and `spec()`; or the refusal,
word for word.

What is compared:

    the L1 budget cases       every `budget` case of sabline-spec's corpus,
                              its `allow` and `deny` exactly as written
    their mutations           each case's budget reordered, respaced,
                              upper-cased, split into its items, with
                              counts added, and with each scoped effect
                              denied - fixed operations, so the corpus is
                              the same on every machine
    EDGES                     one budget for each refusal and each branch of
                              `Budget.parse` the cases above do not reach:
                              counts past 64 bits and past CPython's 4,300
                              digits, percent sequences, IPv6, wildcards
                              over Unicode digits, white space CPython
                              strips and Rust does not, the tool grammar
    TREE                      paths through a small tree both runtimes
                              resolve - a directory, a file, a link to the
                              directory, a link to nothing, and on Windows a
                              junction - so that `realpath` is compared
                              where it does more than join

Every budget is resolved in the same scratch directory by both runtimes:
`fs:` paths are resolved against the working directory when a budget is
parsed (sabline-spec 5.1's resolution R), and the gate makes that
directory, with the tree in it, before it asks either.

**What is not in it, on purpose.** A path whose letters Windows' own case
table and Unicode's disagree on (`ẞ`, Cherokee - pypath.rs says why), a
path longer than Windows' 260 characters, a NUL in a path, a loop of
links: CPython itself answers each of those differently from one version
or one Windows to the next, so no single answer could be held to. A count
or a port of more than 4,300 digits is held: `int()` refuses it, in words
CPython 3.10 and 3.12 give differently - "Exceeds the limit (4300)" and
"(4300 digits)" - so the reference refuses first, in 3.12's words, on
every CPython (`values.whole_number`, 9.0 M3), and CI's 3.10 legs are
where that is shown.
"""
import json
import os
from pathlib import Path
from typing import Any

Case = tuple[str, Any, Any]          # name, allow (text or None), deny

# ---- one budget for each branch the corpus does not reach -------------------

EDGES: tuple[Case, ...] = (
    # nothing at all, and what a shell leaves of an empty budget
    ("empty", "", None), ("commas", ",,,", None), ("spaces", " , ", None),
    ("quotes-single", "''", None), ("quotes-double", '""', None),
    ("default", None, None), ("default-denied", None, "io"),
    # `all`, the command line's word
    ("all", "all", None), ("all-spaced", "  all\t", None),
    ("all-among", "io,all", None), ("all-upper", "ALL", None),
    ("all-denied", "all", "fs,net,tool"),
    # effects, and what is not one
    ("upper", "IO", None), ("unknown", "x", None),
    ("space-inside", "fs read", None), ("every-plain", "io,env,clock,rand,declassify", None),
    ("nbsp", "\u00a0io\u2003", None), ("unit-separator", "\u001fio\u001c", None),
    ("next-line", "io\u0085", None), ("zero-width", "\u200bio", None),
    ("ideographic-space", "\u3000env", None),
    # ffi
    ("ffi-empty", "ffi:", None), ("ffi-blank", "ffi: ", None),
    ("ffi-continued", "ffi:math,json,os", None),
    ("ffi-continued-spaced", "ffi:math, json ,os,io", None),
    ("ffi-continued-count", "ffi:math,json@2", None),
    ("ffi-count", "ffi:math@2", None), ("ffi-dot", "ffi:.x", None),
    ("ffi-dotted", "ffi:a.b.c", None), ("ffi-plain-first", "ffi,ffi:math", None),
    ("ffi-plain-last", "ffi:math,ffi", None),
    ("ffi-stops-at-colon", "ffi:math,fs:read", None),
    ("ffi-takes-all", "ffi:math,all", None),
    ("ffi-stops-at-effect", "ffi:math,io,json", None),
    ("ffi-denied", "ffi:math,io", "ffi"),
    # fs and its counts
    ("fs-count-zero", "fs@0", None), ("fs-count-leading-zeros", "fs@007", None),
    ("fs-count-empty", "fs@", None), ("fs-count-word", "fs@x", None),
    ("fs-two-counts", "fs@1@2", None), ("fs-colon", "fs:", None),
    ("fs-colons", "fs::", None), ("fs-read-colon", "fs:read:", None),
    ("fs-capital", "fs:Read", None), ("fs-at-in-path", "fs:read:a@b@c", None),
    ("fs-encoded-at", "fs:read:./a%40b@3", None),
    ("fs-count-64-bits", "fs@18446744073709551616", None),
    ("fs-count-huge", "fs@" + "9" * 300, None),
    ("fs-count-at-limit", "fs@" + "1" * 4300, None),
    ("fs-count-past-limit", "fs@" + "1" * 4301, None),
    ("fs-count-past-limit-by-zeros", "fs@" + "0" * 4300 + "7", None),
    ("fs-read-count-past-limit", "fs:read:.@" + "2" * 5000, None),
    ("net-port-past-limit", "net:example.com:" + "4" * 4301, None),
    ("net-bracket-port-past-limit", "net:[::1]:" + "8" * 4301, None),
    ("net-count-past-limit", "net:example.com@" + "3" * 4301, None),
    ("tool-count-past-limit", "tool:search@" + "5" * 4301, None),
    ("tool-plain-count-past-limit", "tool@" + "6" * 4301, None),
    ("fs-least-count", "fs:read@9,fs:write@3,fs@5", None),
    ("fs-unicode-digits-count", "fs@\u0663", None),
    ("fs-superscript-count", "fs@\u00b2", None),
    ("fs-percent-short", "fs:read:x%2", None), ("fs-percent-end", "fs:read:x%", None),
    ("fs-percent-unknown", "fs:read:%zz", None),
    ("fs-percent-lower", "fs:read:%2c%40%5b%5d%25", None),
    ("fs-dot", "fs:read:.", None), ("fs-dotdot", "fs:read:..", None),
    ("fs-tilde", "fs:read:~", None), ("fs-up-down", "fs:read:./a/../b", None),
    ("fs-nul-device", "fs:read:nul", None), ("fs-backslash", "fs:read:a\\b", None),
    ("fs-plain-first", "fs,fs:read:./a", None), ("fs-plain-last", "fs:read:./a,fs", None),
    ("fs-both-ways", "fs:read,fs:write:./out", None),
    ("fs-denied-count", "fs:read:./a@5,io", "fs"),
    ("fs-unicode-path", "fs:read:./\u65e5\u672c/\u00c9t\u00e9", None),
    # net
    ("net-plain-count", "net@3", None), ("net-colon", "net:", None),
    ("net-blank", "net: ", None), ("net-at", "net:@", None),
    ("net-at-host", "net:a@b", None), ("net-slash", "net:a/b", None),
    ("net-bracket", "net:[", None), ("net-brackets-empty", "net:[]", None),
    ("net-bracket-open", "net:[::1", None), ("net-bracket-tail", "net:[::1]x", None),
    ("net-bracket-colon", "net:[::1]:", None), ("net-bracket-port-zero", "net:[::1]:0", None),
    ("net-bracket-port-top", "net:[::1]:65535", None),
    ("net-bracket-port-over", "net:[::1]:65536", None),
    ("net-bracket-encoded", "net:[%3A%3A1]", None),
    ("net-bracket-upper", "net:[FE80::1]:80", None),
    ("net-port-zero", "net:x:0", None), ("net-port-zeros", "net:x:00080", None),
    ("net-port-huge", "net:x:99999999", None), ("net-port-unicode", "net:x:\u0668\u0660", None),
    ("net-unbracketed", "net:::1", None), ("net-two-colons", "net:a:b:c", None),
    ("net-colon-word", "net:x:y", None), ("net-trailing-dots", "net:EXAMPLE.COM..", None),
    ("net-wild-short", "net:*.com", None), ("net-wild-nothing", "net:*.", None),
    ("net-wild-ok", "net:*.a.b", None), ("net-wild-twice", "net:*.*.b", None),
    ("net-wild-middle", "net:a.*.b", None), ("net-wild-ip", "net:*.1.2", None),
    ("net-wild-ip-word", "net:*.1.x", None),
    ("net-wild-superscript", "net:*.1.\u00b2", None),
    ("net-wild-arabic", "net:*.\u0661.\u0662", None),
    ("net-wild-empty-label", "net:*.1..2", None),
    ("net-wild-circled", "net:*.\u2460.\u2461", None),
    ("net-wild-fraction", "net:*.1.\u00bd", None),
    ("net-sigma", "net:\u03a3\u0391\u03a3.com", None),
    ("net-dotted-i", "net:\u0130stanbul.com", None),
    ("net-umlaut", "net:\u00dcN\u00cfCODE.com", None),
    ("net-encoded", "net:x%40y,net:x%2Cy", None),
    ("net-counts", "net:x.com:80@5@6", None),
    ("net-plain-first", "net,net:a.com", None),
    ("net-least-count", "net:a.com@9,net@4", None),
    ("net-denied", "net:a.com@2,io", "net"),
    # tool
    ("tool-plain", "tool", None), ("tool-count", "tool@5", None),
    ("tool-count-empty", "tool@", None), ("tool-count-word", "tool@x", None),
    ("tool-colon", "tool:", None), ("tool-digit-name", "tool:9x", None),
    ("tool-space-name", "tool:x y", None), ("tool-unicode-name", "tool:caf\u00e9", None),
    ("tool-named", "tool:search", None), ("tool-named-zero", "tool:search@0", None),
    ("tool-arg-no-eq", "tool:search:to", None), ("tool-arg-empty", "tool:search:to=", None),
    ("tool-arg-no-name", "tool:search:=x", None), ("tool-arg", "tool:search:to=a", None),
    ("tool-arg-at", "tool:search:to=*@corp.com", None),
    ("tool-arg-encoded-at", "tool:search:to=*%40corp.com", None),
    ("tool-arg-count", "tool:search:to=x@5", None),
    ("tool-arg-stars", "tool:search:to=a**b", None),
    ("tool-arg-encoded", "tool:search:to=%2C%25", None),
    ("tool-arg-trailing-at-digits", "tool:send:to=a%4012", None),
    ("tool-at-name", "tool@x@5", None),
    ("tool-many", "tool:a,tool:b@2,tool:a:x=1,tool@3", None),
    ("tool-count-then-arg", "tool:a@2,tool:a:x=1", None),
    ("tool-arg-then-plain", "tool:a:x=1,tool:a", None),
    ("tool-plain-then-arg", "tool,tool:a:x=1", None),
    ("tool-arg-twice", "tool:a:x=1,tool:a:x=1,tool:a:y=2", None),
    ("tool-counts", "tool:a@5,tool:a@3,tool@9,tool@4", None),
    ("tool-plain-and-counts", "tool,tool:b@2", None),
    ("tool-denied", "tool:a:x=1,tool@3,io", "tool"),
    # deny
    ("deny-unknown", "io", "nope"), ("deny-spaced", "io,fs,net", " io , fs"),
    ("deny-empty", "io", ""), ("deny-many-unknown", "io", "zz,aa,io"),
    ("deny-everything", "io,env,fs,net,clock,rand,ffi,declassify,tool",
     "io,env,fs,net,clock,rand,ffi,declassify,tool"),
    ("deny-upper", "io", "IO"),
)

# ---- paths through a tree both runtimes resolve -----------------------------

TREE: tuple[Case, ...] = (
    ("tree-dir", "fs:read:./data", None),
    ("tree-file", "fs:read:./data/file.txt", None),
    ("tree-below-a-file", "fs:read:./data/file.txt/below", None),
    ("tree-inner-up", "fs:read:./data/inner/../file.txt", None),
    ("tree-new-under-dir", "fs:write:./data/inner/new/deeper", None),
    ("tree-link", "fs:read:./link", None),
    ("tree-through-link", "fs:read:./link/inner", None),
    ("tree-new-through-link", "fs:write:./link/new/x", None),
    ("tree-dangling", "fs:write:./dangling", None),
    ("tree-through-dangling", "fs:write:./dangling/x", None),
    ("tree-junction", "fs:read:./junction", None),
    ("tree-through-junction", "fs:read:./junction/inner/x", None),
    ("tree-upper", "fs:read:./DATA/Inner", None),
    ("tree-absolute-root", "fs:read:/", None),
    ("tree-separators", "fs:read:.//data///inner/", None),
)


def prepare(where: Path) -> list[str]:
    """Make the tree TREE's paths walk, in `where`, as far as this system
    lets a process make it; and say what it could not make. A link the
    system will not make is a path that does not exist, which both
    runtimes still resolve - so the cases are the same everywhere, and
    only what they walk through differs."""
    (where / "data" / "inner").mkdir(parents=True, exist_ok=True)
    (where / "data" / "file.txt").write_text("x\n", encoding="utf-8")
    missing = []
    for name, target in (("link", "data"), ("dangling", "nowhere")):
        try:
            os.symlink(target, where / name, target_is_directory=True)
        except (OSError, NotImplementedError):
            missing.append(name)
    try:
        import _winapi                             # Windows only
        junction = getattr(_winapi, "CreateJunction")
        junction(str(where / "data"), str(where / "junction"))
    except (ImportError, OSError, AttributeError):
        missing.append("junction")
    return missing


# ---- the L1 cases, and what is made from them -------------------------------

def corpus_cases(corpus: Path) -> list[Case]:
    """Every `budget` case of sabline-spec's corpus, as it is written."""
    index = json.loads((corpus / "index.json").read_text(encoding="utf-8"))
    out: list[Case] = []
    for listed in index["cases"]:
        if listed["kind"] != "budget":
            continue
        case = json.loads((corpus / listed["file"]).read_text(encoding="utf-8"))
        given = case["input"]
        out.append((f"conformance/{case['id']}", given.get("allow"),
                    given.get("deny")))
    return out


def _ascii_upper(text: str) -> str:
    return "".join(c.upper() if "a" <= c <= "z" else c for c in text)


DENIED = ("fs", "net", "ffi", "tool", "io,fs", "nope")


def mutations(rows: list[Case]) -> list[Case]:
    """Each budget made into others by fixed operations."""
    out: list[Case] = []
    for name, allow, deny in rows:
        if allow is None:
            continue
        items = allow.split(",")
        made = [
            ("spaced", ", ".join(i.strip() for i in items), deny),
            ("reversed", ",".join(reversed(items)), deny),
            ("upper", _ascii_upper(allow), deny),
            ("counted", allow + ",fs@4,net@9", deny),
            ("tooled", allow + ",tool:t@2,tool:t:a=b", deny),
        ]
        made += [(f"denied-{d}", allow, d) for d in DENIED]
        made += [(f"item-{i}", item, None) for i, item in enumerate(items)
                 if len(items) > 1]
        out += [(f"{name}/{how}", a, d) for how, a, d in made]
    return out


def cases(corpus: Path) -> tuple[list[Case], list[str]]:
    """Every budget the gate compares, each once, and a line per part."""
    l1 = corpus_cases(corpus)
    parts = (("the L1 budget cases", l1), ("their mutations", mutations(l1)),
             ("the budgets' edges", list(EDGES)), ("paths through a tree", list(TREE)))
    seen: set[tuple[Any, Any]] = set()
    out: list[Case] = []
    counts = []
    for what, rows in parts:
        kept = 0
        for name, allow, deny in rows:
            if (allow, deny) in seen:
                continue
            seen.add((allow, deny))
            out.append((f"budget/{name}", allow, deny))
            kept += 1
        counts.append(f"{what}: {kept} budgets")
    return out, counts
