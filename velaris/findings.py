"""Findings as SARIF, and what the doors record: the invocation log.
"""
import json
import os
import sys

from .version import REFERENCE_URL, VERSION
from .errors import ERROR_TABLE
from .tables import ALL_EFFECTS, HAVE_Z3
from .recorder import REFUSAL_CODES
from .editor import contract_coverage, inspect_source
from .results import RunResult
from .library import _audit_here
from typing import Any

# ---------------------------------------------------------------------------
# 16. FINDINGS AS SARIF, AND WHAT THE DOORS RECORD
#
#     `check --sarif`, `proofs --sarif` and `audit --sarif` write SARIF
#     2.1.0, which GitHub code scanning, SonarQube and Azure DevOps read
#     without a plugin. The rules are the error table plus the findings
#     that are not errors, and nothing is written that SARIF cannot hold
#     as Velaris means it.
#
#     The HTTP door and the MCP server each write one JSON line per call
#     (InvocationLog), and the MCP server's tools can be held against a
#     manifest the release workflow signs (mcp-manifest, mcp-verify).
#     The verifier lives here and not in velaris_mcp.py, so a changed
#     server file cannot also change the code that checks it.
# ---------------------------------------------------------------------------


SARIF_SCHEMA_URI = ("https://docs.oasis-open.org/sarif/sarif/v2.1.0/"
                    "errata01/os/schemas/sarif-schema-2.1.0.json")
REPOSITORY = "https://github.com/gowrishankar-infra/velaris-lang"
ERRORS_PAGE = "https://gowrishankar-infra.github.io/velaris-lang/errors.html"

_EFFECT_WORDS = {"io": "the console", "env": "environment variables",
                 "fs": "files", "net": "the network", "clock": "the time",
                 "rand": "randomness",
                 "ffi": "Python, and so anything Python can do",
                 "declassify": "turning a Secret into an ordinary value, "
                               "which anything may then emit"}

# The findings that are not errors, as (rule id, level, meaning). The
# E-codes come from ERROR_TABLE and are all errors: each one stops a
# program from compiling or from running. An unproven promise is a
# warning; a function that promises nothing about its data, a loop not
# shown to end and a capability are notes.
SARIF_FINDINGS = (
    ("unproven-promise", "warning",
     "a requires or ensures that is checked while the program runs, not "
     "proven before it runs"),
    ("contract-coverage", "note",
     "a function that takes or returns data and promises nothing about "
     "it"),
    ("loop-not-shown-to-end", "note",
     "a loop the termination rule cannot show to end; check --strict "
     "refuses it as E612"),
    ("ffi-native", "note",
     "a granted Python module ships native code (a compiled extension: "
     ".so/.pyd/.dylib), found on disk without importing it; there is no "
     "source to read and a budget does not contain what it does"),
    ("secret-source", "note",
     "a builtin that hands the program a Secret (env, read_file_secret); "
     "the compiler will not let its result be printed, written or sent"),
    ("secret-declassified", "warning",
     "a declassify call turns a Secret into an ordinary value, with a "
     "stated reason; an error under check --strict unless the reason is "
     "listed in --allow-declassify-reasons"),
) + tuple((f"uses-{e}", "note",
           f"a function that may perform {e}: {_EFFECT_WORDS[e]}")
          for e in ALL_EFFECTS) + (
    ("capability-widened", "error",
     "code that needs a grant velaris.capabilities does not give: an "
     "effect, a Python module, a path outside the recorded ones, a host, "
     "a scoped grant made unscoped, or more fs or net operations in a run "
     "than recorded (capabilities check)"),
    ("capability-effect-gained", "error",
     "a function velaris.capabilities records now declares an effect it "
     "did not declare there (capabilities check)"),
    ("capability-narrowed", "note",
     "velaris.capabilities gives more than the code needs now; "
     "capabilities init --force records the narrower surface"),
    ("dependency-capability-widened", "error",
     "an upgraded Velaris dependency needs a grant its previous version "
     "did not: an effect, a Python module, a path, a host, or more fs or "
     "net operations in a run (deps-diff)"),
    ("dependency-effect-gained", "error",
     "a function of an upgraded Velaris dependency declares an effect it "
     "did not declare in the previous version (deps-diff)"),
    ("dependency-install-script", "error",
     "an upgraded dependency runs an install-time script its previous "
     "version did not, or a different one; what the script does is not "
     "derived (deps-diff)"),
    ("dependency-surface-unknown", "note",
     "an upgraded dependency holds code other than Velaris, or could not "
     "be read, so what it can do was not derived; unknown is not safe "
     "(deps-diff)"),
    ("dependency-added", "note",
     "a dependency the upgraded version declares that the previous one "
     "did not; its own surface was not examined (deps-diff)"),
    ("dependency-narrowed", "note",
     "an upgraded Velaris dependency needs less than its previous version "
     "did (deps-diff)"),
)


def sarif_rules() -> list[Any]:
    """Every rule a Velaris SARIF log can cite: one per entry of the
    error table, then the findings that are not errors. The help URI of
    each is its row on the published errors page."""
    rules = [{"id": code, "shortDescription": {"text": text},
              "helpUri": f"{ERRORS_PAGE}#{code}",
              "defaultConfiguration": {"level": "error"}}
             for code, text in sorted(ERROR_TABLE.items())]
    rules += [{"id": rid, "shortDescription": {"text": text},
               "helpUri": f"{ERRORS_PAGE}#{rid}",
               "defaultConfiguration": {"level": level}}
              for rid, level, text in SARIF_FINDINGS]
    return rules


class _SarifRun:
    """One SARIF run being filled in: results, and the rules they cite.

    What is deliberately not written: a Velaris fix is a sentence, and
    a SARIF `fix` must carry the exact bytes to change (artifactChanges
    is required), so the suggestions go in each result's property bag as
    `fixes` rather than as SARIF fixes with an edit made up to fill the
    slot. Findings with no place in a file (a proven share, the audit's
    safe_command) go in the run's property bag, not in results."""

    def __init__(self, command: str) -> None:
        self.command = command
        self.rules = sarif_rules()
        self.index = {r["id"]: i for i, r in enumerate(self.rules)}
        self.results: list[Any] = []
        self.notes: list[Any] = []
        self.properties: dict[Any, Any] = {"prover": bool(HAVE_Z3),
                                 "reference": REFERENCE_URL}
        self.root = os.getcwd()
        self.base_ids: dict[Any, Any] = {}      # more originalUriBaseIds (deps-diff)

    def add(self, rule: str, message: Any, path: Any, line: Any, level: Any = None,
            fixes: Any = None) -> None:
        if rule not in self.index:          # cannot happen while the
            self.index[rule] = len(self.rules)   # table is complete;
            self.rules.append({                  # check_library says so
                "id": rule, "shortDescription": {
                    "text": f"{rule}, which is not in the error table"},
                "defaultConfiguration": {"level": "error"}})
        rule_level = self.rules[self.index[rule]]["defaultConfiguration"]
        result = {"ruleId": rule, "ruleIndex": self.index[rule],
                  "level": level or rule_level["level"],
                  "message": {"text": str(message)},
                  "locations": [self._location(path, line)]}
        if fixes:
            result["properties"] = {"fixes": [str(f) for f in fixes]}
        self.results.append(result)

    def note(self, text: str) -> None:
        """Something that kept the tool from doing what was asked."""
        self.notes.append({"level": "error", "message": {"text": text}})

    def _location(self, path: Any, line: Any) -> dict[str, Any]:
        # a dict is an artifactLocation already: a file inside a package
        # deps-diff read, which is not a file of the checked tree
        where: dict[Any, Any] = {"artifactLocation": dict(path) if isinstance(path, dict)
                       else self._artifact(str(path))}
        if isinstance(line, int) and not isinstance(line, bool) \
                and line >= 1:
            where["region"] = {"startLine": line}
        return {"physicalLocation": where}

    def _artifact(self, path: str) -> dict[str, Any]:
        import pathlib
        import urllib.parse
        full = os.path.abspath(path)
        try:
            rel = os.path.relpath(full, self.root)
        except ValueError:                  # another drive, on Windows
            rel = None
        if rel is not None and rel.split(os.sep)[0] != "..":
            return {"uri": urllib.parse.quote(rel.replace(os.sep, "/")),
                    "uriBaseId": "%SRCROOT%"}
        return {"uri": pathlib.Path(full).as_uri()}

    def log(self) -> dict[str, Any]:
        import pathlib
        invocation: dict[Any, Any] = {"executionSuccessful": not self.notes}
        if self.notes:
            invocation["toolConfigurationNotifications"] = self.notes
        root = pathlib.Path(self.root).as_uri().rstrip("/") + "/"
        results = sorted(self.results, key=lambda r: (
            r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"],
            r["locations"][0]["physicalLocation"].get("region", {})
            .get("startLine", 0), r["ruleId"], r["message"]["text"]))
        return {"$schema": SARIF_SCHEMA_URI, "version": "2.1.0",
                "runs": [{
                    "tool": {"driver": {
                        "name": "Velaris", "version": VERSION,
                        "semanticVersion": VERSION,
                        "informationUri": REPOSITORY,
                        "rules": self.rules}},
                    "automationDetails": {"id": f"velaris/{self.command}/"},
                    "originalUriBaseIds": {"%SRCROOT%": {"uri": root},
                                           **self.base_ids},
                    "invocations": [invocation],
                    "results": results,
                    "properties": self.properties}]}


def _own_functions(report: dict[Any, Any], path: str) -> list[Any]:
    here = os.path.abspath(path)
    return [f for f in report["functions"]
            if os.path.abspath(f["file"]) == here]


def _sarif_errors(run: "_SarifRun", report: dict[Any, Any], path: str) -> None:
    for e in report["errors"]:
        run.add(e.get("code") or "E000", e.get("message") or "",
                e.get("file") or path, e.get("line"), fixes=e.get("fixes"))


def _sarif_unproven(run: "_SarifRun", own: list[Any], prover: bool,
                    level: Any = None) -> list[Any]:
    """A result for every promise-carrying function not proven; returns
    those functions."""
    unproven = [f for f in own if (f["requires"] or f["ensures"])
                and f["status"] != "proven"]
    for f in unproven:
        said = "; ".join([f"requires {r}" for r in f["requires"]]
                         + [f"ensures {e}" for e in f["ensures"]])
        why = ("" if prover else
               " (the prover, z3-solver, is not installed)")
        if f.get("proof_timeout"):      # abandoned, not settled
            why = (" (the proof ran out of time and was abandoned - "
                   "nothing was proven and nothing was refuted)")
        run.add("unproven-promise",
                f"'{f['name']}': {said} - not proven before running; "
                f"checked while the program runs{why}",
                f["file"], f["line"], level=level)
    return unproven


def _sarif_coverage(run: "_SarifRun", own: list[Any], report: dict[Any, Any]) -> None:
    by_name = {f["name"]: f for f in own}
    for name in contract_coverage(own, report.get("records", [])):
        f = by_name[name]
        run.add("contract-coverage",
                f"'{name}' takes or returns data and promises nothing "
                f"about it", f["file"], f["line"])


def _unshown_loops(own: list[Any], report: dict[Any, Any], path: str) -> list[Any]:
    """(function name, loop, file) for every loop not shown to end."""
    here = os.path.abspath(path)
    found = [(f["name"], lp, f["file"]) for f in own
             for lp in f.get("loops", []) if lp["verdict"] == "unshown"]
    found += [("an inline function", lp, lp["file"])
              for lp in report.get("inline_loops", [])
              if lp["verdict"] == "unshown"
              and os.path.abspath(lp["file"]) == here]
    return found


def sarif_check(targets: list[Any], strict: bool = False) -> tuple[dict[Any, Any], int]:
    """`velaris check --sarif`: (the SARIF log, the exit code the plain
    check would give). Errors are errors; a promise left to runtime is a
    warning, and an error under --strict, as is a loop not shown to end
    (E612); a function promising nothing about its data is a note."""
    run = _SarifRun("check")
    bad = 0
    for target in targets:
        report = inspect_source(target)
        if report["errors"]:
            bad += 1
            _sarif_errors(run, report, target)
            continue
        own = _own_functions(report, target)
        if strict and not report["proofs"]:
            bad += 1
            run.note(f"{target}: --strict needs the prover "
                     f"(pip install z3-solver)")
            continue
        unproven = _sarif_unproven(run, own, report["proofs"],
                                   "error" if strict else None)
        loops = _unshown_loops(own, report, target) if strict else []
        for _name, lp, file in loops:
            run.add("E612", "this loop may never end - --strict needs a "
                            "counter that moves toward the limit",
                    file, lp["line"], fixes=[lp["why"]])
        if strict and (unproven or loops):
            bad += 1
        _sarif_coverage(run, own, report)
    return run.log(), (1 if bad else 0)


def sarif_proofs(reports: dict[Any, Any], totals: dict[Any, Any], share: float,
                 minimum: Any) -> dict[Any, Any]:
    """`velaris proofs --sarif`: what did not compile, and every promise
    left to runtime; the totals and the proven share in the run's
    property bag."""
    run = _SarifRun("proofs")
    for path, report in reports.items():
        if report["errors"]:
            _sarif_errors(run, report, path)
            continue
        _sarif_unproven(run, _own_functions(report, path),
                        report["proofs"])
    run.properties.update({"totals": totals, "proven_share": round(share, 1)})
    if minimum is not None:
        run.properties["min_proven"] = minimum
        run.properties["below_min"] = share < minimum
    return run.log()


def sarif_audit(files: list[Any], strict: bool = False,
                allow_reasons: Any = ()) -> dict[Any, Any]:
    """`velaris audit --sarif`: the audit of each file as findings - what
    each function may perform, promises left to runtime, loops not shown
    to end, functions promising nothing about their data, native code a
    granted module ships (ffi-native), and its secrets (secret-source,
    secret-declassified) - and the velaris.audit/1 document of each file,
    unchanged, in the run's property bag for what has no line
    (safe_command, proven_share).

    A declassification is a warning; under `strict` it is an error unless
    its stated reason is in `allow_reasons` (from
    --allow-declassify-reasons), so a reviewed reason passes and a new one
    does not (8.0)."""
    run = _SarifRun("audit")
    reasons = {r.strip() for r in allow_reasons if r.strip()}
    audits = []
    for path in files:
        report = inspect_source(path)
        with open(path, encoding="utf-8") as fh:
            doc = _audit_here(fh.read(), path=path).as_dict()
        audits.append(doc)
        # native code a granted module ships, and secrets - both from the
        # audit document, so they hold whether or not the file compiles
        for m, verdict in sorted((doc.get("ffi_native") or {}).items()):
            if verdict == "native":
                run.add("ffi-native",
                        f"the granted Python module '{m}' ships native code "
                        f"(a compiled extension); there is no source to read",
                        path, None)
        secrets = doc.get("secrets") or {}
        for src in secrets.get("sources", []):
            run.add("secret-source",
                    f"'{src}' hands this program a Secret; the compiler will "
                    f"not let its result be printed, written or sent", path,
                    None)
        for d in secrets.get("declassifications", []):
            listed = d["reason"] in reasons
            level = ("error" if strict and not listed else "warning")
            note = (" (reason is in --allow-declassify-reasons)" if listed
                    else " (add its reason to --allow-declassify-reasons to "
                    "accept it under --strict)" if strict else "")
            run.add("secret-declassified",
                    f"'{d['function']}' declassifies a Secret: "
                    f"{d['reason']}{note}", path, d["line"], level=level)
        if report["errors"]:
            _sarif_errors(run, report, path)
            continue
        own = _own_functions(report, path)
        for f in own:
            for e in f["effects"]:
                if e in _EFFECT_WORDS:
                    run.add(f"uses-{e}", f"'{f['name']}' may perform {e} "
                                         f"({_EFFECT_WORDS[e]})",
                            f["file"], f["line"])
        _sarif_unproven(run, own, report["proofs"])
        for name, lp, file in _unshown_loops(own, report, path):
            who = name if name.startswith("an ") else f"'{name}'"
            run.add("loop-not-shown-to-end",
                    f"a loop in {who} is not shown to end: {lp['why']}",
                    file, lp["line"])
        _sarif_coverage(run, own, report)
    run.properties["audits"] = audits
    return run.log()


def print_sarif_summary(log: dict[Any, Any]) -> None:
    """The findings in a SARIF log, one line each on stderr, so a CI log
    still says what was found while stdout carries the SARIF."""
    import urllib.parse
    for r in log["runs"][0]["results"]:
        where = r["locations"][0]["physicalLocation"]
        uri = urllib.parse.unquote(where["artifactLocation"]["uri"])
        line = where.get("region", {}).get("startLine")
        at = f"{uri}:{line}" if line else uri
        print(f"{at}: {r['level']} [{r['ruleId']}] {r['message']['text']}",
              file=sys.stderr)
    for n in log["runs"][0]["invocations"][0].get(
            "toolConfigurationNotifications", []):
        print(n["message"]["text"], file=sys.stderr)


def run_outcome(result: "RunResult") -> str:
    """One word for how a run ended, as the doors log it."""
    if result.timed_out:
        return "timeout"
    if result.out_of_memory:
        return "out_of_memory"
    if result.refused_effect:
        return "refused"
    return "ok" if result.ok else "failed"


def run_refusals(result: "RunResult") -> list[Any]:
    """The budget's refusal of a run, as the doors log it, or []."""
    if not result.refused_effect:
        return []
    code = next((p.code for p in result.problems
                 if p.code in REFUSAL_CODES), None)
    return [{"by": "budget", "code": code, "what": result.refused_effect}]


INVOCATION_SCHEMA = "velaris.invocation/1"


class InvocationLog:
    """One JSON line per call through a door - the HTTP door or the MCP
    server - on stderr, or appended to a file.

    A full line holds when the call arrived (UTC), the door, the tool or
    endpoint, the outcome, how long it took, the budget the program ran
    under, the effects it performed (RunResult.effects_used), what was
    refused and by what, the caller's address (HTTP), and the sha256 of
    the source. Never the source itself, the program's output, its
    stdin or arguments, a request header, or the door's token - and any
    secret handed to `redact` is replaced by [redacted] should it ever
    be part of a line. `detail="minimal"` keeps when, the door, what was
    called, the outcome and the duration. Nothing turns the log off.
    """

    DETAILS = ("full", "minimal")

    def __init__(self, path: str | None = None, detail: str = "full",
                 redact: Any = ()) -> None:
        import threading as _threading
        if detail not in self.DETAILS:
            raise ValueError("the invocation log is 'full' or 'minimal'; "
                             "it cannot be turned off")
        self.detail = detail
        self.path = path
        self._redact = [s for s in redact if s]
        self._lock = _threading.Lock()
        # opened now, so a path that cannot be written stops the door
        # before it answers anyone
        self._file = open(path, "a", encoding="utf-8") if path else None

    @staticmethod
    def started() -> tuple[Any, ...]:
        import datetime
        import time as _t
        return datetime.datetime.now(datetime.timezone.utc), _t.monotonic()

    def record(self, started: tuple[Any, ...], *, door: str, outcome: str,
               tool: str | None = None, endpoint: str | None = None,
               client: str | None = None, budget: Any = None, effects: Any = None,
               refusals: Any = (), source: Any = None, run_params: Any = None) -> dict[Any, Any]:
        import hashlib
        import time as _t
        when, t0 = started
        line: dict[Any, Any] = {"schema": INVOCATION_SCHEMA,
                      "ts": when.isoformat(timespec="milliseconds")
                      .replace("+00:00", "Z"),
                      "door": door}
        if tool is not None:
            line["tool"] = tool
        if endpoint is not None:
            line["endpoint"] = endpoint
        line["outcome"] = outcome
        line["duration_ms"] = round((_t.monotonic() - t0) * 1000, 1)
        if self.detail == "full":
            if client is not None:
                line["client"] = client
            line["budget"] = budget
            line["effects"] = effects
            line["refusals"] = list(refusals)
            if run_params is not None:      # --seed / --freeze-time (8.0)
                line["run_params"] = run_params
            line["source_sha256"] = (
                hashlib.sha256(source.encode("utf-8", "surrogatepass"))
                .hexdigest() if isinstance(source, str) else None)
        text = json.dumps(line)
        for secret in self._redact:
            for form in (secret, json.dumps(secret)[1:-1]):
                text = text.replace(form, "[redacted]")
        with self._lock:
            try:
                out = self._file or sys.stderr
                out.write(text + "\n")
                out.flush()
            except (OSError, ValueError):
                # the file failed; the line goes to stderr rather than
                # nowhere, since a door that cannot log still logs
                sys.stderr.write(text + "\n")
                sys.stderr.flush()
        return line

    def close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
