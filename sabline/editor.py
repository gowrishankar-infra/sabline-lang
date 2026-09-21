"""What an editor asks: the inspection of a program, hovers, lenses, and the
language server.
"""
import json
import os
import sys

from .version import VERSION
from .errors import SablineError
from .parser import expr_str
from .tables import BUILTINS, FALLIBLE_BUILTINS, HAVE_Z3
from .loader import load_program
from .effects import check_effects
from .checker import check_main, check_types
from .termination import loop_termination
from .prover import check_proofs
from typing import Any


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def lsp_analyze(path: str, text: str, deep: bool) -> list[Any]:
    """Run the checkers on an editor buffer; return SablineErrors."""
    errors: list[Any] = []
    try:
        funcs, records = load_program(path, entry_source=text)
    except SablineError as e:
        return [e]
    check_effects(funcs, errors)
    check_types(funcs, records, errors)
    if deep and not errors:
        check_proofs(funcs, records, errors)
    return errors


def contract_coverage(functions: list[Any], records: list[Any]) -> list[Any]:
    """Names of the functions that take or return a List, a Map or a
    record and carry no requires or ensures: they transform data and
    promise nothing about it. A coverage note, not a defect - the audit
    lists them so a reader knows where no promise was even attempted.
    """
    def is_data(t: str) -> bool:
        return (t.startswith("List of") or t.startswith("Map of")
                or t in records)
    out = []
    for f in functions:
        if f["requires"] or f["ensures"]:
            continue
        types = [p["type"] for p in f["params"]] + [f["returns"] or ""]
        if any(is_data(t) for t in types):
            out.append(f["name"])
    return out


def inspect_source(path: str, source: str | None = None,
                   require_main: bool = False) -> dict[Any, Any]:
    """Everything a reader wants to know about a program, as data.

    Used by 'sabline explain' and the browser inspector: for each
    function, what it may do (effects), what it promises, whether the
    promises are proven or left to runtime, and every error in place.
    """
    running = require_main
    report: dict[Any, Any] = {"file": path, "functions": [], "errors": [],
                    "proofs": bool(HAVE_Z3), "version": VERSION}
    try:
        funcs, records = load_program(path, source)
    except SablineError as e:
        report["errors"].append(json.loads(e.machine(path)))
        return report
    errors: list[Any] = []
    try:
        check_main(funcs, errors, running=running)
        check_effects(funcs, errors)
        if not errors:
            check_types(funcs, records, errors)
    except SablineError as e:          # a raise instead of an append is
        errors.append(e)               # still one problem, not a crash
    except RecursionError:             # nested past Python's limit (8.2)
        from .errors import _too_deep_error
        errors.append(_too_deep_error(False))
    proved: set[Any] = set()
    abandoned: list[Any] = []
    if not errors:
        try:
            check_proofs(funcs, records, errors, proved,
                         timeouts_out=abandoned)
        except SablineError as e:
            errors.append(e)
    report["proof_timeouts"] = abandoned
    out_of_time = {t["name"] for t in abandoned}
    seen_e = set()
    for err in errors:              # one problem, one message, everywhere
        key = (err.code, err.file or path, err.line, err.message)
        if key in seen_e:
            continue
        seen_e.add(key)
        report["errors"].append(json.loads(err.machine(path)))
    bad_lines = {e.line for e in errors}
    # which loops provably end - syntactic, so it is the same answer
    # with and without the prover
    table_all = {f.name: f for f in funcs}
    loops_by = {f.name: loop_termination(f, table_all) for f in funcs}
    report["records"] = [r.name for r in records]
    report["inline_loops"] = []          # loops inside lifted lambdas
    for f in funcs:
        if f.name.startswith("fn#"):
            for lp in loops_by[f.name]:
                report["inline_loops"].append(
                    dict(lp, function=f.name, file=f.src_file or path))
            continue                     # lifted lambda: shown in place
        report["functions"].append({
            "loops": loops_by[f.name],
            "loops_unshown": sum(1 for lp in loops_by[f.name]
                                 if lp["verdict"] == "unshown"),
            "name": f.name,
            "line": f.line,
            "params": [{"name": n, "type": t} for n, t in f.params],
            "returns": f.return_type or "nothing",
            "effects": sorted(f.effects) or [],
            "can_fail": bool(f.can_fail),
            "generic": list(f.type_vars),
            "requires": [expr_str(e) for e, _ in f.requires],
            "ensures": [expr_str(e) for e, _ in f.ensures],
            "status": ("error" if f.line in bad_lines else
                       "proven" if f.name in proved and HAVE_Z3 else
                       "checked at runtime" if (f.requires or f.ensures)
                       else "no promises"),
            # the promise is checked while running either way; this says
            # the prover ran out of time rather than settling anything
            "proof_timeout": f.name in out_of_time,
            "file": f.src_file or path,
        })
    return report


def editor_answer(method: str, params: dict[Any, Any], text: str, uri: str) -> Any:
    """Hover, go-to-definition, proof lenses and an outline."""
    import urllib.parse
    path = urllib.parse.unquote(uri.replace("file://", ""))
    if os.name == "nt" and path.startswith("/"):
        path = path[1:]
    try:
        funcs, records = load_program(path, text)
    except SablineError:
        return None if "codeLens" not in method else []

    proven: set[Any] = set()
    if "codeLens" in method:
        errors: list[Any] = []
        check_effects(funcs, errors)
        check_types(funcs, records, errors)
        if not errors:
            try:
                check_proofs(funcs, records, errors, proven)
            except Exception:
                pass

    mine = [f for f in funcs
            if not f.src_file or os.path.abspath(f.src_file)
            == os.path.abspath(path)]

    def signature(f: Any) -> str:
        ps = ", ".join(f"{n}: {t}" for n, t in f.params)
        out = f"fn {f.name}({ps})"
        if f.return_type and f.return_type != "Unit":
            out += f" -> {f.return_type}"
        if f.type_vars:
            out += " for any " + ", ".join(f.type_vars)
        if f.can_fail:
            out += " or fail"
        if f.effects:
            out += " uses " + ", ".join(sorted(f.effects))
        return out

    if method == "textDocument/codeLens":
        lenses = []
        for f in mine:
            if f.name.startswith("fn#"):
                continue
            if f.requires or f.ensures:
                title = ("promises proven before running"
                         if f.name in proven
                         else "promises checked while running")
            elif f.effects:
                title = "may perform: " + ", ".join(sorted(f.effects))
            else:
                title = "pure"
            if f.can_fail:
                title += " - can fail"
            lenses.append({
                "range": {"start": {"line": max(f.line - 1, 0),
                                    "character": 0},
                          "end": {"line": max(f.line - 1, 0),
                                  "character": 1}},
                "command": {"title": title, "command": ""}})
        return lenses

    if method == "textDocument/rename":
        line_no = params["position"]["line"]
        col = params["position"]["character"]
        new_name = params.get("newName", "")
        lines = text.splitlines()
        if line_no >= len(lines) or not new_name:
            return None
        row = lines[line_no]
        start, end = col, col
        while start > 0 and (row[start - 1].isalnum()
                             or row[start - 1] == "_"):
            start -= 1
        while end < len(row) and (row[end].isalnum() or row[end] == "_"):
            end += 1
        old_name = row[start:end]
        if not old_name:
            return None
        here = {f.name for f in funcs
                if not f.src_file
                or os.path.abspath(f.src_file) == os.path.abspath(path)}
        if old_name not in here:
            return None            # only names this file owns
        import re as _re
        pattern = _re.compile(r"\b" + _re.escape(old_name) + r"\b")
        edits = []
        for i, row_text in enumerate(lines):
            code = row_text.split("//")[0]        # leave comments alone
            for m in pattern.finditer(code):
                edits.append({
                    "range": {"start": {"line": i, "character": m.start()},
                              "end": {"line": i, "character": m.end()}},
                    "newText": new_name})
        if not edits:
            return None
        return {"changes": {uri: edits}}

    if method == "textDocument/completion":
        items = []
        for f in funcs:
            if f.name.startswith("fn#"):
                continue
            items.append({"label": f.name, "kind": 3,
                          "detail": signature(f),
                          "documentation": " ".join(
                              [f"requires {expr_str(e)}"
                               for e, _ in f.requires]
                              + [f"ensures {expr_str(e)}"
                                 for e, _ in f.ensures]) or None})
        for name, info in BUILTINS.items():
            eff = ", ".join(sorted(info["effects"])) or "pure"
            fail = " (can fail)" if name in FALLIBLE_BUILTINS else ""
            items.append({"label": name, "kind": 3,
                          "detail": f"builtin -> {info['ret']}{fail}",
                          "documentation": f"effects: {eff}"})
        for word in ("fn", "let", "return", "if", "else", "while", "for",
                     "uses", "requires", "ensures", "invariant", "record",
                     "import", "fail", "check", "try", "or fail",
                     "for any T"):
            items.append({"label": word, "kind": 14})
        return {"isIncomplete": False, "items": items}

    if method == "textDocument/documentSymbol":
        return [{"name": f.name, "kind": 12,
                 "range": {"start": {"line": max(f.line - 1, 0),
                                     "character": 0},
                           "end": {"line": max(f.line - 1, 0),
                                   "character": 80}},
                 "selectionRange": {
                     "start": {"line": max(f.line - 1, 0), "character": 0},
                     "end": {"line": max(f.line - 1, 0), "character": 80}},
                 "detail": signature(f)}
                for f in mine if not f.name.startswith("fn#")]

    # hover and definition both need the word under the cursor
    line_no = params["position"]["line"]
    col = params["position"]["character"]
    lines = text.splitlines()
    if line_no >= len(lines):
        return None
    row = lines[line_no]
    start = col
    while start > 0 and (row[start - 1].isalnum()
                         or row[start - 1] in "_."):
        start -= 1
    end = col
    while end < len(row) and (row[end].isalnum() or row[end] in "_."):
        end += 1
    word = row[start:end]
    if not word:
        return None

    table = {f.name: f for f in funcs}
    found = table.get(word)

    if method == "textDocument/definition":
        if found is None or found.name.startswith("fn#"):
            return None
        target = found.src_file or path
        return {"uri": "file://" + os.path.abspath(target).replace(
                    "\\", "/"),
                "range": {"start": {"line": max(found.line - 1, 0),
                                    "character": 0},
                          "end": {"line": max(found.line - 1, 0),
                                  "character": 1}}}

    if found is not None:
        parts = [signature(found)]
        for e, _ in found.requires:
            parts.append(f"    requires {expr_str(e)}")
        for e, _ in found.ensures:
            parts.append(f"    ensures {expr_str(e)}")
        body = ["```sabline", "\n".join(parts), "```"]
        if found.src_file and os.path.abspath(found.src_file) != \
                os.path.abspath(path):
            body.append(f"from `{os.path.basename(found.src_file)}`")
        return {"contents": {"kind": "markdown",
                             "value": "\n".join(body)}}

    if word in BUILTINS:
        info = BUILTINS[word]
        eff = ", ".join(sorted(info["effects"])) or "pure"
        fail = " (can fail)" if word in FALLIBLE_BUILTINS else ""
        return {"contents": {"kind": "markdown", "value":
                f"**{word}**{fail}\n\n"
                f"takes: {', '.join(info['types']) or 'nothing'}  \n"
                f"gives: {info['ret']}  \n"
                f"effects: {eff}"}}
    return None


def lsp_serve() -> int:
    import urllib.parse

    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    docs: dict[str, str] = {}          # uri -> latest text
    published: set[Any] = set()             # uris we have diagnostics on

    def read_message() -> Any:
        length = None
        while True:
            line = stdin.readline()
            if not line:
                return None
            line = line.strip()
            if not line:
                break
            key, _, val = line.partition(b":")
            if key.lower() == b"content-length":
                length = int(val)
        if length is None:
            return None
        return json.loads(stdin.read(length))

    def send(payload: dict[Any, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        stdout.write(f"Content-Length: {len(body)}\r\n\r\n".encode())
        stdout.write(body)
        stdout.flush()

    def uri_to_path(uri: str) -> str:
        p = urllib.parse.unquote(uri[len("file://"):])
        if len(p) > 2 and p[0] == "/" and p[2] == ":":
            p = p[1:]                   # windows: /C:/... -> C:/...
        return p

    def path_to_uri(p: str) -> str:
        p = os.path.abspath(p).replace("\\", "/")
        if not p.startswith("/"):
            p = "/" + p
        return "file://" + urllib.parse.quote(p)

    def diag_of(e: SablineError) -> dict[str, Any]:
        msg = f"[{e.code}] {e.message}"
        if e.fixes:
            msg += "".join(f"\nfix: {f}" for f in e.fixes)
        line = max(e.line - 1, 0)
        return {"range": {"start": {"line": line, "character": 0},
                          "end": {"line": line, "character": 500}},
                "severity": 1, "source": "sabline", "message": msg}

    def publish(uri: str, deep: bool) -> None:
        path = uri_to_path(uri)
        errors = lsp_analyze(path, docs.get(uri, ""), deep)
        by_file: dict[str, list[Any]] = {uri: []}
        for e in errors:
            target = uri if e.file in (None, path) else path_to_uri(e.file)
            by_file.setdefault(target, []).append(diag_of(e))
        for target, ds in by_file.items():
            send({"jsonrpc": "2.0",
                  "method": "textDocument/publishDiagnostics",
                  "params": {"uri": target, "diagnostics": ds}})
            published.add(target)
        for old in list(published):
            if old not in by_file:
                send({"jsonrpc": "2.0",
                      "method": "textDocument/publishDiagnostics",
                      "params": {"uri": old, "diagnostics": []}})
                published.discard(old)

    while True:
        msg = read_message()
        if msg is None:
            return 0
        method = msg.get("method", "")
        params = msg.get("params", {})
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": msg["id"], "result": {
                "capabilities": {
                    "textDocumentSync": {
                        "openClose": True, "change": 1,
                        "save": {"includeText": True}},
                    "hoverProvider": True,
                    "renameProvider": {"prepareProvider": False},
                    "completionProvider": {
                        "triggerCharacters": [".", " "]},
                    "definitionProvider": True,
                    "codeLensProvider": {"resolveProvider": False},
                    "documentSymbolProvider": True},
                "serverInfo": {"name": "sabline", "version": VERSION}}})
        elif method in ("textDocument/hover", "textDocument/definition",
                        "textDocument/codeLens", "textDocument/completion",
                        "textDocument/rename",
                        "textDocument/documentSymbol"):
            uri = params["textDocument"]["uri"]
            text = docs.get(uri, "")
            result = editor_answer(method, params, text, uri)
            send({"jsonrpc": "2.0", "id": msg["id"], "result": result})
        elif method == "shutdown":
            send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
        elif method == "exit":
            return 0
        elif method == "textDocument/didOpen":
            uri = params["textDocument"]["uri"]
            docs[uri] = params["textDocument"]["text"]
            publish(uri, deep=True)
        elif method == "textDocument/didChange":
            uri = params["textDocument"]["uri"]
            docs[uri] = params["contentChanges"][0]["text"]
            publish(uri, deep=False)
        elif method == "textDocument/didSave":
            uri = params["textDocument"]["uri"]
            if "text" in params:
                docs[uri] = params["text"]
            publish(uri, deep=True)
        elif method == "textDocument/didClose":
            uri = params["textDocument"]["uri"]
            docs.pop(uri, None)
            send({"jsonrpc": "2.0",
                  "method": "textDocument/publishDiagnostics",
                  "params": {"uri": uri, "diagnostics": []}})
        elif "id" in msg:               # any other request: empty result
            send({"jsonrpc": "2.0", "id": msg["id"], "result": None})
