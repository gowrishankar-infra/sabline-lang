"""sabline conformance: sabline-spec's corpus, run against this implementation.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading

from .version import VERSION, _INSTALL_DIR, _launch_command
from . import naming
from .errors import SablineError
from .tables import ALL_EFFECTS
from .loader import load_program
from .budget import Budget
from .results import AUDIT_SCHEMA
from .library import _audit_here, _budget_from
from .ratchet import (
    CAPABILITIES_FILE,
    _as_count,
    _covers,
    _grant_parts,
    _operation_bounds,
    _reduce_grants,
    capabilities_compare,
    capabilities_document,
    capabilities_main,
    capabilities_text,
    capability_scan,
    read_capabilities,
)
from typing import Any

# ---------------------------------------------------------------------------
# 18. CONFORMANCE - sabline-spec's corpus, run against this implementation
#
#     sabline-spec's tests/ directory is a conformance corpus for the
#     capability format: JSON cases an implementation in any language runs
#     its own way (sabline-spec CONFORMANCE.md, tests/README.md). This
#     repository's build_conformance.py writes it from check_sandbox.py,
#     check_library.py and check_ratchet.py. `sabline conformance` reads it
#     back and holds this implementation to it through the doors another
#     implementation would use: the budget parser, the audit, a run under a
#     budget from the command line, and the baseline writer and check. It
#     computes nothing from the case but what the case says, and a case it
#     does not understand fails.
# ---------------------------------------------------------------------------


CONFORMANCE_SCHEMA = "sabline.conformance/1"

# The conformance corpus is the one document this project does NOT write
# under its new name yet, and the reason is the point of the corpus: it is
# published for an implementation in any language to run, and the
# implementations that exist are Sabline releases that are already
# published and frozen. Every one of them reads this field with `!=`
# against "velaris.conformance-corpus/1", so a corpus that said
# "sabline.conformance-corpus/1" would stop `velaris conformance` dead for
# everyone who has not upgraded - the exact break 8.6 exists to avoid.
#
# So the corpus keeps the name every released reader accepts, this reads
# both, and the name it is written under moves when a reader that accepts
# both is the norm rather than the newest release (sabline-spec 0.14.0
# says so, and names 0.15.0 as the earliest it could move).
CORPUS_FORMAT = "velaris.conformance-corpus/1"
CORPUS_FORMATS = (CORPUS_FORMAT, "sabline.conformance-corpus/1")

# The command an expected safe_command in the published corpus is written
# with. Section 8.3 defines the grant list and not this prefix, and this
# runner compares the grants (_grants_of) - but a runner from before 0.14.0
# compares the whole string, so the corpus carries the prefix those runners
# write, for the same reason it keeps the format name above. It moves when
# they do.
CORPUS_SAFE_COMMAND = "velaris <file> --allow "
# (level, name, the levels a claim at that level needs)
CONFORMANCE_LEVELS = ((1, "Declaration", (1,)), (2, "Enforcement", (1, 2)),
                      (3, "Ratchet", (1, 3)))
_CONF_REFUSAL = re.compile(r"error\[(E\d{3})\]")


class _Skip(Exception):
    """A case that cannot run here: `why`, and whether that is the case's
    own stated requirement (a symbolic link) or a tool this machine lacks
    (jsonschema), which leaves the level unshown."""

    def __init__(self, why: str, required: bool) -> None:
        super().__init__(why)
        self.why, self.required = why, required


def _conformance_corpus(given: Any) -> Any:
    """The corpus directory: --corpus, else $SABLINE_CONFORMANCE_CORPUS,
    else sabline-spec/tests beside the working directory or this file."""
    if given:
        return os.path.abspath(given)
    env = naming.env("SABLINE_CONFORMANCE_CORPUS")
    if env:
        return os.path.abspath(env)
    here = _INSTALL_DIR
    for where in (os.path.join("sabline-spec", "tests"),
                  os.path.join("..", "sabline-spec", "tests"),
                  os.path.join(here, "..", "sabline-spec", "tests")):
        if os.path.isfile(os.path.join(where, "index.json")):
            return os.path.abspath(where)
    return None


def _conf_files(root: str, files: dict[Any, Any]) -> None:
    """Write a case's files under root; None deletes one."""
    for name, text in files.items():
        path = os.path.join(root, *name.split("/"))
        if text is None:
            if os.path.exists(path):
                os.unlink(path)
            continue
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)


def _corpus_schema(schemas: str, which: str) -> str:
    """The path to one of sabline-spec's schemas, under whichever name the
    corpus has it.

    These files are named for the documents they describe, and those were
    velaris.* until 8.6. The corpus keeps the old names for the same reason
    it keeps the old corpus format - a published implementation opens them
    by name, and none of them can be changed (see CORPUS_FORMAT above). The
    new name is looked for first, so that the day sabline-spec does rename
    them this release already reads them; the old name is what is there
    today, and both are tried before anything is opened."""
    for name in (f"sabline.{which}.schema.json", f"velaris.{which}.schema.json"):
        path = os.path.join(schemas, name)
        if os.path.exists(path):
            return path
    return os.path.join(schemas, f"sabline.{which}.schema.json")


def _conf_validator(schema_path: str) -> Any:
    """A JSON Schema validator for one of sabline-spec's schemas, or None
    when jsonschema is not installed."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        return None
    with open(schema_path, encoding="utf-8") as fh:
        return Draft202012Validator(json.load(fh))


def _conf_invalid(validator: Any, doc: Any, what: str, wrong: list[Any]) -> str:
    """The case's verdict: what is wrong, and then whether the document
    fails its schema. With no validator a case that is otherwise right is
    not shown right - it is skipped, and its level left unshown."""
    if wrong:
        return "; ".join(wrong)
    if validator is None:
        raise _Skip(f"jsonschema is not installed, so the {what} was not "
                    f"validated against sabline-spec's schema", False)
    return "; ".join(
        f"{what} fails the schema at "
        f"{'/'.join(str(p) for p in e.absolute_path) or 'the top'}: "
        f"{e.message}" for e in list(validator.iter_errors(doc))[:3])


# ---- level 1 ---------------------------------------------------------------

def _conf_budget_shape(b: "Budget") -> dict[Any, Any]:
    out: dict[str, Any] = {"effects": sorted(b.effects)}
    if "ffi" in b.effects:
        out["ffi"] = "any" if b.modules is None else sorted(b.modules)
    if "fs" in b.effects:
        out["fs"] = "any" if b.fs is None else [
            {"direction": d, "path": p} for d, p in b.fs]
    if "net" in b.effects:
        out["net"] = "any" if b.net is None else [
            {"host": h, "port": p} for h, p in b.net]
    out["counts"] = {e: n for e, n in b.limits.items()
                     if n is not None and e in b.effects}
    return out


def _conf_resolved(shape: dict[Any, Any]) -> dict[Any, Any]:
    """Grants with every path resolved as sabline-spec 5.1 says, and each
    scoped list as a set: the spelling of a path and the order of grants
    are not what a budget means."""
    out = dict(shape)
    if isinstance(out.get("fs"), list):
        out["fs"] = sorted({(g["direction"], None if g["path"] is None else
                             os.path.normcase(os.path.realpath(g["path"])))
                            for g in out["fs"]}, key=repr)
    if isinstance(out.get("net"), list):
        out["net"] = sorted({(g["host"], g["port"]) for g in out["net"]},
                            key=repr)
    return out


def _conf_budget(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    given, want = case["input"], case["expect"]
    try:
        budget = _budget_from(
            {given["allow"]} if "allow" in given else None,
            {n.strip() for n in given["deny"].split(",")}
            if "deny" in given else None)
    except ValueError as e:
        if want["valid"]:
            return f"refused ({e}); it must parse"
        return ""
    got = _conf_budget_shape(budget)
    if not want["valid"]:
        return f"parsed, to {got}; it must be refused"
    if _conf_resolved(got) != _conf_resolved(want["grants"]):
        return f"parsed to {got}, not {want['grants']}"
    return ""


def _grants_of(safe_command: Any) -> Any:
    """The grant list of a safe_command - what sabline-spec 8.3 defines.
    What comes before `--allow` is the name of the producer's own command,
    which the spec does not define and a corpus must not require."""
    if not isinstance(safe_command, str) or "--allow " not in safe_command:
        # There are no grants to compare. The case does not pass on that:
        # a safe_command without `--allow ` is already reported above as
        # one that does not parse, which is the check that catches it.
        # Returning the whole string instead would compare command names,
        # which is what this function exists to avoid doing.
        return None
    return safe_command.split("--allow ", 1)[1].strip()


def _conf_audit(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    given, want = case["input"], case["expect"]
    box = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        _conf_files(box, given["files"])
        entry = given["entry"]
        doc = _audit_here(given["files"][entry],
                    path=os.path.join(box, *entry.split("/"))).as_dict()
    finally:
        shutil.rmtree(box, ignore_errors=True)
    wrong = []
    if not naming.schema_matches(doc.get("schema"), AUDIT_SCHEMA):
        wrong.append(f"schema is {doc.get('schema')!r}")
    if doc["effects"] != sorted(set(doc["effects"])) or not set(
            doc["effects"]) <= set(ALL_EFFECTS):
        wrong.append(f"effects {doc['effects']} is not a sorted subset of "
                     f"{list(ALL_EFFECTS)}")
    try:
        Budget.parse(doc["safe_command"].split("--allow ", 1)[1])
    except (ValueError, IndexError) as e:
        wrong.append(f"safe_command {doc['safe_command']!r} does not "
                     f"parse: {e}")
    if doc["ok"] != want["ok"]:
        wrong.append(f"ok is {doc['ok']}"
                     + (f": {[p['code'] for p in doc['problems']]}"
                        if doc["problems"] else ""))
    elif not want["ok"]:
        codes = {p["code"] for p in doc["problems"]}
        wrong += [f"no {c} among the problems {sorted(codes)}"
                  for c in want["problems_include"] if c not in codes]
    else:
        # `secrets` was added to sabline.audit/1 in 6.0 and is compared
        # only where a case names it, so the cases written before it say
        # nothing about a field that did not exist (sabline-spec 8.6)
        for key in ("effects", "ffi_modules", "ffi_any", "fs_paths",
                    "net_hosts", "secrets"):
            if key in want and doc.get(key) != want[key]:
                wrong.append(f"{key} is {doc.get(key)!r}, not {want[key]!r}")
        # safe_command by what sabline-spec 8.3 defines, which is the grant
        # list: the text before `--allow` is the producer's own command,
        # and the corpus is published for an implementation in any language
        # to run. Comparing the whole string made every case require the
        # producer to be called `sabline` - which the reference itself was
        # not until 8.6, so 27 cases read as a changed verdict across the
        # rename when nothing about the grants had changed.
        if "safe_command" in want:
            if _grants_of(doc.get("safe_command")) != \
                    _grants_of(want["safe_command"]):
                wrong.append(f"safe_command is {doc.get('safe_command')!r}, "
                             f"whose grants are not those of "
                             f"{want['safe_command']!r}")
        fns = [{"name": f["name"], "effects": f["effects"],
                "can_fail": f["can_fail"]} for f in doc["functions"]]
        if fns != want["functions"]:
            wrong.append(f"functions are {fns}, not {want['functions']}")
    return _conf_invalid(ctx["audit_schema"], doc, "audit", wrong)


# ---- level 2 ---------------------------------------------------------------

def _conf_servers() -> tuple[Any, ...]:
    """The corpus's two local HTTP servers (tests/README.md): /go on the
    first answers 302 to http://localhost:PORT_B/landed; every other path
    on either answers 200 "hello"."""
    from http.server import BaseHTTPRequestHandler, HTTPServer
    ports: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.startswith("/go"):
                self.send_response(302)
                self.send_header("Location",
                                 f"http://localhost:{ports['b']}/landed")
                self.end_headers()
                return
            body = b"hello"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a: Any) -> None:
            pass

    servers = (HTTPServer(("127.0.0.1", 0), Handler),
               HTTPServer(("127.0.0.1", 0), Handler))
    ports["a"], ports["b"] = (servers[0].server_address[1],
                              servers[1].server_address[1])
    for srv in servers:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return servers, ports["a"], ports["b"]


def _conf_run(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    import subprocess
    given, want = case["input"], case["expect"]
    if given.get("fixture") != "sandbox":
        return f"this runner has no fixture {given.get('fixture')!r}"
    root = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        data = os.path.join(root, "box", "data")
        out = os.path.join(root, "box", "out")
        os.makedirs(data)
        os.makedirs(out)
        with open(os.path.join(data, "a.txt"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write("inside\n")
        with open(os.path.join(root, "outside.txt"), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write("outside\n")
        if "symlink" in case["requires"]:
            try:
                os.symlink(os.path.join(root, "outside.txt"),
                           os.path.join(data, "link.txt"))
            except (OSError, NotImplementedError):
                raise _Skip("needs a symbolic link, and this system would "
                            "not make one", True)
        slash = root.replace(os.sep, "/")
        values = (("{ROOT}", slash), ("{DATA}", slash + "/box/data"),
                  ("{OUT}", slash + "/box/out"),
                  ("{OUTSIDE}", slash + "/outside.txt"),
                  ("{PORT_A}", str(ctx["ports"][0])),
                  ("{PORT_B}", str(ctx["ports"][1])))

        def fill(text: Any) -> Any:
            for key, value in values:
                text = text.replace(key, value)
            return text

        prog = os.path.join(root, "case.vel")
        with open(prog, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(fill(given["source"]))
        cmd = _launch_command() + [prog]
        if "allow" in given:
            cmd += ["--allow", fill(given["allow"])]
        if "deny" in given:
            cmd += ["--deny", fill(given["deny"])]
        cmd += [fill(a) for a in given.get("args", [])]
        try:
            done = subprocess.run(cmd, cwd=root, capture_output=True,
                                  text=True, encoding="utf-8",
                                  errors="replace", timeout=120)
        except subprocess.TimeoutExpired:
            return "the run did not end in 120 seconds"
        stdout, stderr = done.stdout or "", done.stderr or ""
        found = _CONF_REFUSAL.search(stderr)
        code = found.group(1) if found else None
        wrong = []
        if want["outcome"] == "refused":
            if done.returncode == 0 or code != want["code"]:
                wrong.append(f"expected a refusal with {want['code']}, got "
                             + (f"{code}" if code else
                                f"exit {done.returncode} and no refusal"))
            wrong += [f"it printed {w!r}, so it got past the refusal"
                      for w in want.get("stdout_excludes", [])
                      if fill(w) in stdout]
            wrong += [f"{fill(p)} exists" for p in want.get(
                "must_not_exist", []) if os.path.exists(fill(p))]
        elif want["outcome"] == "completed":
            if done.returncode != 0:
                wrong.append(f"exit {done.returncode}"
                             + (f", refused with {code}" if code else "")
                             + f": {(stderr or stdout).strip()[:160]}")
        else:
            return f"this runner has no outcome {want['outcome']!r}"
        wrong += [f"it did not print {fill(s)!r}"
                  for s in want.get("stdout_includes", [])
                  if fill(s) not in stdout]
        return "; ".join(wrong)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---- level 3 ---------------------------------------------------------------

def _conf_edit(doc: dict[Any, Any], edit: Any) -> dict[Any, Any]:
    """A baseline as a person edits it (tests/README.md): each key given
    under surface and under a program's entry replaced, and
    sabline_version when given."""
    doc = json.loads(json.dumps(doc))
    if not edit:
        return doc
    if "sabline_version" in edit:
        doc["sabline_version"] = edit["sabline_version"]
    doc["surface"].update(edit.get("surface", {}))
    for file, fields in edit.get("programs", {}).items():
        for p in doc["programs"]:
            if p["file"] == file:
                p.update(fields)
    return doc


def _conf_write_baseline(target: str) -> None:
    doc = capabilities_document(capability_scan(target, use_git=False))
    with open(os.path.join(target, CAPABILITIES_FILE), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write(capabilities_text(doc))


def _conf_ratchet(target: str) -> tuple[Any, ...]:
    """(verdict, widenings as the corpus writes them) of the check."""
    path = os.path.join(target, CAPABILITIES_FILE)
    if not os.path.exists(path):
        return "cannot-compare", []
    try:
        baseline = read_capabilities(path)
    except ValueError:
        return "cannot-compare", []
    result = capabilities_compare(baseline,
                                  capability_scan(target, use_git=False))
    found = []
    for f in result["findings"]:
        if f["kind"] == "grant":
            found.append({"kind": "grant", "grant": f["grant"],
                          "rules": f["rules"], "programs": sorted(
                              q["file"] for q in f["programs"])})
        elif f["kind"] == "count":
            found.append({"kind": "count", "effect": f["effect"],
                          "program": f["file"], "current": f["current"],
                          "rules": f["rules"]})
        else:
            found.append({"kind": "function", "program": f["file"],
                          "function": f["function"], "gained": f["gained"],
                          "rules": f["rules"]})
    return ("widened" if result["widened"] else "pass"), found


def _conf_verdict_wrong(want: dict[Any, Any], verdict: str, found: list[Any]) -> str:
    if verdict != want["verdict"]:
        return (f"{verdict}, not {want['verdict']}"
                + (f": {found}" if found else ""))
    if verdict == "cannot-compare":
        return ""

    def key(x: Any) -> Any:
        return json.dumps(x, sort_keys=True)
    if sorted(found, key=key) != sorted(want["widenings"], key=key):
        return f"widenings {found}, not {want['widenings']}"
    return ""


def _conf_check(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    given = case["input"]
    box = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given["root"].split("/"))
        base = given["baseline"]
        if base.get("from_tree"):
            doc = capabilities_document(capability_scan(target,
                                                         use_git=False))
            with open(os.path.join(target, CAPABILITIES_FILE), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(capabilities_text(_conf_edit(doc,
                                                      base.get("edit"))))
        elif "text" in base:
            with open(os.path.join(target, CAPABILITIES_FILE), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(base["text"])
        elif not base.get("absent"):
            return f"this runner cannot read the baseline {base}"
        _conf_files(box, given["change"])
        return _conf_verdict_wrong(case["expect"], *_conf_ratchet(target))
    finally:
        shutil.rmtree(box, ignore_errors=True)


def _conf_sequence(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    given = case["input"]
    box = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given.get("root", ".").split("/"))
        _conf_write_baseline(target)
        path = os.path.join(target, CAPABILITIES_FILE)
        for n, (st, want) in enumerate(zip(given["steps"],
                                           case["expect"]["steps"]), 1):
            _conf_files(box, st.get("change") or {})
            if st.get("edit"):
                doc = _conf_edit(read_capabilities(path), st["edit"])
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(capabilities_text(doc))
            if st.get("rewrite"):
                _conf_write_baseline(target)
            if st.get("delete_baseline") and os.path.exists(path):
                os.unlink(path)
            wrong = _conf_verdict_wrong(want, *_conf_ratchet(target))
            if wrong:
                return f"step {n} ({st['description']}): {wrong}"
        if len(given["steps"]) != len(case["expect"]["steps"]):
            return "the case has a different number of steps and verdicts"
        return ""
    finally:
        shutil.rmtree(box, ignore_errors=True)


def _conf_derive(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    given = case["input"]
    box = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given["root"].split("/"))
        _conf_write_baseline(target)
        with open(os.path.join(target, CAPABILITIES_FILE),
                  encoding="utf-8") as fh:
            doc = json.load(fh)
    finally:
        shutil.rmtree(box, ignore_errors=True)
    got = {"surface": doc["surface"], "programs": doc["programs"]}
    wrong = [] if got == case["expect"] else [
        f"wrote {json.dumps(got)}"]
    return _conf_invalid(ctx["capabilities_schema"], doc, "baseline", wrong)


def _conf_write_guard(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    import contextlib
    import io as _io
    if case["expect"] != {"refuses": True, "unchanged": True}:
        return f"this runner knows no write-guard outcome {case['expect']}"
    given = case["input"]
    box = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        _conf_files(box, given["tree"])
        target = os.path.join(box, *given["root"].split("/"))
        quiet = _io.StringIO()
        with contextlib.redirect_stdout(quiet), \
                contextlib.redirect_stderr(quiet):
            first = capabilities_main(["init", target])
            with open(os.path.join(target, CAPABILITIES_FILE),
                      encoding="utf-8") as fh:
                before = fh.read()
            _conf_files(box, given["change"])
            again = capabilities_main(["init", target])
        with open(os.path.join(target, CAPABILITIES_FILE),
                  encoding="utf-8") as fh:
            after = fh.read()
    finally:
        shutil.rmtree(box, ignore_errors=True)
    if first != 0:
        return "the first baseline was not written"
    if again == 0 or after != before:
        return "it replaced the baseline without being asked to"
    return ""


def _conf_covers(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    try:
        got = _covers(_grant_parts(case["input"]["grant"]),
                      _grant_parts(case["input"]["other"]))
    except ValueError as e:
        return f"not a baseline grant: {e}"
    return "" if got == case["expect"]["covers"] else f"covers is {got}"


def _conf_reduce(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    got = _reduce_grants(case["input"]["grants"])
    return "" if got == case["expect"]["grants"] else f"reduced to {got}"


def _conf_bound(case: dict[Any, Any], ctx: dict[Any, Any]) -> str:
    box = tempfile.mkdtemp(prefix="sabline-conformance-")
    try:
        path = os.path.join(box, "bound.vel")
        _conf_files(box, {"bound.vel": case["input"]["source"]})
        funcs, _ = load_program(path)
        bounds, _ = _operation_bounds(funcs)
    except SablineError as e:
        return f"does not compile: {e.message}"
    finally:
        shutil.rmtree(box, ignore_errors=True)
    got = {e: _as_count(n) for e, n in
           bounds[case["input"]["function"]].items()}
    return "" if got == case["expect"] else f"bound {got}"


_CONFORMANCE_KINDS = (("budget", _conf_budget), ("audit", _conf_audit),
                      ("run", _conf_run), ("derive", _conf_derive),
                      ("check", _conf_check), ("sequence", _conf_sequence),
                      ("write-guard", _conf_write_guard),
                      ("covers", _conf_covers), ("reduce", _conf_reduce),
                      ("bound", _conf_bound))


def conformance(corpus: str, levels: Any = (1, 2, 3)) -> dict[str, Any]:
    """Run sabline-spec's conformance corpus at `corpus` (its tests/
    directory) against this implementation; the sabline.conformance/1
    report. ValueError when the corpus cannot be read."""
    try:
        with open(os.path.join(corpus, "index.json"), encoding="utf-8") as fh:
            index = json.load(fh)
    except (OSError, ValueError) as e:
        raise ValueError(f"cannot read {corpus}/index.json: {e}")
    if index.get("format") not in CORPUS_FORMATS:
        raise ValueError(f"{corpus}/index.json is not "
                         + " or ".join(CORPUS_FORMATS))
    schemas = os.path.join(corpus, "..", "schemas")
    ctx = {"audit_schema": _conf_validator(
               _corpus_schema(schemas, "audit.1")),
           "capabilities_schema": _conf_validator(
               _corpus_schema(schemas, "capabilities.1"))}
    kinds = dict(_CONFORMANCE_KINDS)
    wanted = sorted({n for lvl, _, needs in CONFORMANCE_LEVELS
                     if lvl in levels for n in needs})
    entries = [e for e in index["cases"] if e["level"] in wanted]
    servers = None
    if 2 in wanted:
        servers, port_a, port_b = _conf_servers()
        ctx["ports"] = (port_a, port_b)
    results = []
    here = os.getcwd()
    scratch = tempfile.mkdtemp(prefix="sabline-conformance-cwd-")
    os.chdir(scratch)            # relative paths in budgets resolve here
    try:
        for listed in entries:
            row = {"id": listed["id"], "level": listed["level"],
                   "kind": listed["kind"],
                   "known_limit": bool(listed.get("known_limit"))}
            try:
                with open(os.path.join(corpus, *listed["file"].split("/")),
                          encoding="utf-8") as fh:
                    case = json.load(fh)
                if case["id"] != listed["id"] or case["kind"] not in kinds:
                    raise ValueError(f"this runner cannot run "
                                     f"{case.get('id')!r} of kind "
                                     f"{case.get('kind')!r}")
                wrong = kinds[case["kind"]](case, ctx)
                row.update(result="fail" if wrong else "pass",
                           detail=wrong)
            except _Skip as s:
                row.update(result="skip", detail=s.why, required=s.required)
            except Exception as x:           # a case that crashes the runner
                row.update(result="fail",    # fails; it never passes
                           detail=f"{type(x).__name__}: {x}")
            results.append(row)
    finally:
        os.chdir(here)
        shutil.rmtree(scratch, ignore_errors=True)
        for srv in servers or ():
            srv.shutdown()
    summary = {}
    for lvl, name, _ in CONFORMANCE_LEVELS:
        if lvl not in wanted:
            continue
        rows = [r for r in results if r["level"] == lvl]
        summary[str(lvl)] = {
            "name": name, "cases": len(rows),
            "passed": sum(r["result"] == "pass" for r in rows),
            "failed": sum(r["result"] == "fail" for r in rows),
            "skipped": sum(r["result"] == "skip" for r in rows),
            "unshown": sum(r["result"] == "skip" and not r.get("required")
                           for r in rows)}
    shown = [lvl for lvl, _, needs in CONFORMANCE_LEVELS if lvl in levels
             and all(summary[str(n)]["failed"] == 0
                     and summary[str(n)]["unshown"] == 0 for n in needs)]
    return {"schema": CONFORMANCE_SCHEMA,
            "implementation": {"name": "sabline-lang", "version": VERSION},
            "corpus": corpus, "levels_run": wanted,
            "levels": summary, "conformant": shown,
            "results": results}


def _conformance_verdict(report: dict[Any, Any], asked: Any) -> str:
    names = dict((lvl, f"L{lvl}") for lvl, _, _ in CONFORMANCE_LEVELS)
    shown = [names[n] for n in report["conformant"]]
    missing = [names[n] for n in asked if n not in report["conformant"]]
    skipped = [r for r in report["results"] if r["result"] == "skip"]
    said = f"Sabline {VERSION} "
    if not missing:
        said += "is conformant at " + " and ".join(
            [", ".join(shown[:-1]), shown[-1]] if len(shown) > 1 else shown)
    else:
        said += "is NOT shown conformant at " + ", ".join(missing) + (
            "; conformant at " + ", ".join(shown) if shown else "")
    if skipped:
        said += (f" ({len(skipped)} case(s) not run here: "
                 + "; ".join(sorted({r['detail'] for r in skipped})) + ")")
    return said


def conformance_main(argv: list[Any]) -> int:
    """sabline conformance [--level 1|2|3] [--json] [--corpus DIR]"""
    usage = ("usage: sabline conformance [--level 1|2|3] [--json] "
             "[--corpus DIR]")
    levels: tuple[int, ...] = (1, 2, 3)
    as_json = False
    given: str | None = None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--level", "--corpus") and i + 1 < len(argv):
            if a == "--level":
                if argv[i + 1] not in ("1", "2", "3"):
                    print(usage, file=sys.stderr)
                    return 2
                levels = (int(argv[i + 1]),)
            else:
                given = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            as_json = True
        else:
            print(usage, file=sys.stderr)
            return 2
        i += 1
    corpus = _conformance_corpus(given)
    if corpus is None or not os.path.isfile(os.path.join(corpus,
                                                         "index.json")):
        print("sabline conformance: no corpus found. It is sabline-spec's "
              "tests/ directory: clone https://github.com/gowrishankar-infra/"
              "sabline-spec beside this directory, or pass --corpus "
              "sabline-spec/tests", file=sys.stderr)
        return 2
    try:
        report = conformance(corpus, levels)
    except ValueError as e:
        print(f"sabline conformance: {e}", file=sys.stderr)
        return 2
    report["verdict"] = _conformance_verdict(report, levels)
    ok = all(n in report["conformant"] for n in levels)
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if ok else 1
    total = sum(v["cases"] for v in report["levels"].values())
    print(f"sabline conformance: sabline-spec corpus at {corpus}, "
          f"{total} case(s) run")
    for lvl, v in sorted(report["levels"].items()):
        extra = (f"  {v['skipped']} skipped" if v["skipped"] else "")
        print(f"  L{lvl} {v['name']:<12} {v['cases']:>4} cases  "
              f"{v['passed']:>4} passed  {v['failed']:>3} failed{extra}")
    for r in report["results"]:
        if r["result"] == "fail":
            print(f"FAIL  {r['id']}: {r['detail'][:400]}")
    for r in report["results"]:
        if r["result"] == "skip":
            print(f"skip  {r['id']}: {r['detail']}")
    print(report["verdict"])
    return 0 if ok else 1
