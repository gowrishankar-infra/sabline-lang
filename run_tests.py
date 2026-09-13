#!/usr/bin/env python3
"""Velaris test suite: runs every example and checks its expected verdict.

    python run_tests.py              # uses native compilation if available
    python run_tests.py --no-native  # force full interpretation
"""
import subprocess
import sys
from pathlib import Path

# every example, with its expected verdict
EXPECT = {
    "hello.vel": "RUNS",            "effects.vel": "RUNS",
    "sneaky_fixed.vel": "RUNS",     "loop.vel": "RUNS",
    "contract.vel": "RUNS",         "features.vel": "RUNS",
    "compose.vel": "RUNS",          "bench.vel": "RUNS",
    "loop_proof.vel": "RUNS",
    "list_proof.vel": "RUNS",
    "text_tools.vel": "RUNS",
    "records.vel": "RUNS",
    "uses_import.vel": "RUNS",
    "import_bad.vel": "REJECTED",
    "escapes.vel": "RUNS",
    "floats.vel": "RUNS",
    "maps.vel": "RUNS",
    "failing.vel": "RUNS",
    "funcs.vel": "RUNS",
    "generics.vel": "RUNS",
    "ledger.vel": "RUNS",
    "settlement.vel": "RUNS",
    "discount.vel": "RUNS",
    "secret.vel": "RUNS",
    "secret_bad.vel": "REJECTED",
    "rec_proof.vel": "RUNS",
    "native_float.vel": "RUNS",
    "qlist_proof.vel": "RUNS",
    "fail_proof.vel": "RUNS",
    "fp_proof.vel": "RUNS",
    "std_tour.vel": "RUNS",
    "lambdas.vel": "RUNS",
    "namespaces.vel": "RUNS",
    "div_proof.vel": "RUNS",
    "wordcount.vel": "RUNS",
    "map_proof.vel": "RUNS",
    "lambda_contract.vel": "RUNS",
    "inferred.vel": "RUNS",
    "grid_proof.vel": "RUNS",
    "native_list.vel": "RUNS",
    "native_text.vel": "RUNS",
    "native_build.vel": "RUNS",
    "forloops.vel": "RUNS",
    "rec_list_proof.vel": "RUNS",
    "trace_demo.vel": "RUNS",
    "text_list_proof.vel": "RUNS",
    "ffi.vel": "RUNS",
    "json_ffi.vel": "RUNS",
    "database.vel": "RUNS",
    "stdlib_tools.vel": "RUNS",
    "pipeline.vel": "RUNS",
    "edges.vel": "RUNS",
    "sandbox.vel": "RUNS",
    "rec_push.vel": "RUNS",
    "avg_bad.vel": "REJECTED",
    "stack.vel": "RUNS",
    "loop_lists.vel": "RUNS",
    "offbyone_bad.vel": "REJECTED",
    "report_fixes.vel": "RUNS",
    "conj_bad.vel": "REJECTED",
    "quantified.vel": "RUNS",
    "recursion.vel": "RUNS",
    "grid_bad.vel": "REJECTED",
    "lambda_contract_bad.vel": "REJECTED",
    "map_bad.vel": "REJECTED",
    "div_bad.vel": "REJECTED",
    "ns_bad.vel": "REJECTED",
    "tools.vel": "RUNS",
    "lambda_capture.vel": "RUNS",
    "builtin_unhandled.vel": "REJECTED",
    "std_bad.vel": "REJECTED",
    "fp_proof_bad.vel": "REJECTED",
    "discount_bad.vel": "REJECTED",
    "fail_proof_bad.vel": "REJECTED",
    "qlist_bad.vel": "REJECTED",
    "rec_proof_bad.vel": "REJECTED",
    "generics_bad.vel": "REJECTED",
    "funcs_bad.vel": "REJECTED",
    "failing_bad.vel": "REJECTED",
    "maps_bad.vel": "REJECTED",
    "floats_bad.vel": "REJECTED",
    "many_errors.vel": "REJECTED",
    "records_bad.vel": "REJECTED",
    "loop_proof_bad.vel": "REJECTED",
    "list_proof_bad.vel": "REJECTED",
    "sneaky.vel": "REJECTED",       "caught.vel": "REJECTED",
    "types_bad.vel": "REJECTED",    "loop_bad.vel": "REJECTED",
    "contract_broken.vel": "REJECTED",
    "contract_impure.vel": "REJECTED",
    "list_mixed.vel": "REJECTED",   "list_oob.vel": "REJECTED",
    "proof_catch.vel": "REJECTED",  "callsite_bad.vel": "REJECTED",
    # termination: both RUN; the _bad one is refused only by check --strict
    "termination.vel": "RUNS",
    "termination_bad.vel": "RUNS",
}

# The budget each example needs, narrowest first. From 5.0 a run with
# no --allow gets io, so every example that touches a file, a host, the
# clock, randomness, the environment or Python has to say so - and says
# exactly what it needs, never `all`. `velaris migrate --to 5.0 examples`
# derives this list from each program's own audit; an example missing
# from it runs under the 5.0 default.
ALLOW = {
    # _sqlite3 as well as sqlite3: sqlite3.connect belongs to the C
    # extension, and 3.3's reach check binds a grant to the module a
    # call actually reaches, which the audit reading the source cannot
    # see. Still named modules, never plain ffi.
    "database.vel": "ffi:_sqlite3,builtins,sqlite3,io",
    "edges.vel": "ffi:datetime,io",
    "effects.vel": "clock,fs:read:report.txt,fs:write:report.txt,io,rand",
    "ffi.vel": "ffi:base64,builtins,datetime,io",
    "json_ffi.vel": "ffi:math,io",
    "ledger.vel": "fs:read:ledger.txt,fs:write:ledger.txt,io",
    "report_fixes.vel": "ffi:math,io",
    "sandbox.vel": "ffi:builtins,fs:read,io,net",
    "secret.vel": "env,io",
    "secret_bad.vel": "env,io",
    "stdlib_tools.vel": "declassify,env,ffi:_sqlite3,builtins,sqlite3,io",
    "wordcount.vel": "fs:read,io",
    # the ones that reach the network are not run by this suite with a
    # net grant: fetcher, linkcheck, net and stress are RUNS only where
    # there is a network, and the suite that exercises them is
    # check_library.py's door and pool cases
}

# scripted keyboard input for interactive examples
ARGS = {
    "wordcount.vel": ["examples/sample.txt", "3"],
}

STDIN = {
    "ledger.vel": ("add\nchai\n2500\n1\nadd\nbook\n45000\n2\n"
                   "add\nauto\n12000\n2\n"
                   "list\ntotal\nreport\nsave\nload\nreport\n"
                   "add\npen\nabc\nquit\n"),
}


def check_versions() -> None:
    """The packaged version and the compiler's version must agree."""
    import re as _re
    root = Path(__file__).parent
    src = (root / "velaris.py").read_text(encoding="utf-8")
    tom = (root / "pyproject.toml").read_text(encoding="utf-8")
    a = _re.search(r'VERSION = "([\d.]+)"', src).group(1)
    b = _re.search(r'version = "([\d.]+)"', tom).group(1)
    if a != b:
        print(f"VERSION MISMATCH: velaris.py says {a}, "
              f"pyproject.toml says {b}")
        raise SystemExit(1)
    # every other place a version lives: an npm package or an .mcpb
    # manifest claiming a different version than the compiler is a lie
    # a user would meet, so the guard covers them too
    import json as _j
    for label, path, read in (
            ("the npm package", root / "npm" / "package.json",
             lambda p: _j.loads(p.read_text(encoding="utf-8"))["version"]),
            ("the .mcpb manifest", root / "mcpb" / "manifest.json",
             lambda p: _j.loads(p.read_text(encoding="utf-8"))["version"])):
        if path.exists():
            got = read(path)
            if got != a:
                print(f"VERSION MISMATCH: velaris.py says {a}, "
                      f"{label} says {got}")
                raise SystemExit(1)

    ext = root / "editor" / "vscode" / "package.json"
    if ext.exists():
        import json as _json
        c = _json.loads(ext.read_text(encoding="utf-8"))["version"]
        if c != a:
            print(f"VERSION MISMATCH: velaris.py says {a}, "
                  f"the VS Code extension says {c}")
            raise SystemExit(1)

    # the registry manifest carries the version three times - its own and
    # one per package - and every one of them is published
    reg = root / "integrations" / "mcp_registry" / "server.json"
    if reg.exists():
        doc = _j.loads(reg.read_text(encoding="utf-8"))
        said = [doc["version"]] + [p["version"] for p in doc["packages"]]
        if any(v != a for v in said):
            print(f"VERSION MISMATCH: velaris.py says {a}, "
                  f"the MCP registry manifest says {said}")
            raise SystemExit(1)

    # the Action a reader copies out of the README pins a release, and so
    # does the version it installs. 7.0.0 still showed v5.0.1 in both, two
    # majors late; every pin in the README and EMBEDDING.md must be this
    # release.
    for doc in ("README.md", "EMBEDDING.md"):
        text = (root / doc).read_text(encoding="utf-8")
        pins = _re.findall(r"gowrishankar-infra/velaris-lang@v([\w.]+)", text)
        installs = _re.findall(r'^\s*version:\s*"([^"]*)"', text, _re.M)
        if doc == "README.md" and not pins:
            print("VERSION MISMATCH: README.md no longer pins the Action "
                  "(gowrishankar-infra/velaris-lang@v...), which this "
                  "check reads")
            raise SystemExit(1)
        wrong = sorted({v for v in pins + installs if v != a})
        if wrong:
            print(f"VERSION MISMATCH: velaris.py says {a}, {doc} pins the "
                  f"Action or its version at {', '.join(wrong)}")
            raise SystemExit(1)

    # CITATION.cff had lagged for releases (it said 4.3.1 at 7.2.0), so it
    # is held to VERSION too from 8.0: the citation a reader copies names
    # the version they cite. Its line is `version: X.Y.Z`.
    cff = root / "CITATION.cff"
    if cff.exists():
        m = _re.search(r'^version:\s*"?([\d.]+)"?', cff.read_text(
            encoding="utf-8"), _re.M)
        got = m.group(1) if m else None
        if got != a:
            print(f"VERSION MISMATCH: velaris.py says {a}, CITATION.cff "
                  f"says {got}")
            raise SystemExit(1)

    # and what the compiler says it is when it is run with no arguments.
    # Until 4.4 that line was frozen at the version its docstring was
    # written in, and said 2.36 however old that became.
    printed = subprocess.run([sys.executable, str(root / "velaris.py")],
                             capture_output=True, text=True).stdout
    first = next((ln for ln in printed.splitlines() if ln.strip()), "")
    if f"Velaris {a}" not in first:
        print(f"VERSION MISMATCH: velaris.py with no arguments opens "
              f"{first!r}, not 'Velaris {a}'")
        raise SystemExit(1)


def main() -> int:
    check_versions()
    here = Path(__file__).parent
    examples = here / "examples"
    extra = [a for a in sys.argv[1:] if a.startswith("--")]
    expect = dict(EXPECT)
    try:
        import z3  # noqa: F401
    except ImportError:
        # Without the prover, proof_catch's bug is only reachable for
        # years > 30, which its main deliberately never calls - that IS
        # the demo's point. It runs clean under runtime checks.
        proof_only = ["proof_catch.vel", "fail_proof_bad.vel",
                      "avg_bad.vel",
                      "div_bad.vel", "grid_bad.vel"]
        for name in proof_only:
            expect[name] = "RUNS"
        print("note: z3-solver absent - " + ", ".join(proof_only)
              + " expected to RUN (their bugs are only findable "
                "by proof)")
    failed = 0
    for name, want in expect.items():
        path = examples / name
        if not path.exists():
            print(f"MISSING   {name}")
            failed += 1
            continue
        budget = (["--allow", ALLOW[name]] if name in ALLOW else [])
        r = subprocess.run(
            [sys.executable, str(here / "velaris.py"), str(path)]
            + budget + ARGS.get(name, []) + extra,
            capture_output=True, text=True, timeout=300,
            input=STDIN.get(name))
        got = "RUNS" if r.returncode == 0 else "REJECTED"
        ok = got == want
        print(f"{'PASS' if ok else 'FAIL':4}  {name:22} expected {want:8} got {got}")
        if not ok:
            failed += 1
    total = len(EXPECT)
    print(f"\n{total - failed}/{total} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
