#!/usr/bin/env python3
"""Every fallible builtin must actually be enforced. All of them.

In v2.42, pop/slice/set_at joined FALLIBLE_BUILTINS but the checker
never demanded handling for them, because a type-checking branch
returned before the fallibility check ran. A clean `velaris check` was
followed by a raw Python traceback - the exact failure the language
exists to prevent, introduced by its own maintainer.

This test makes that mistake impossible to repeat. It reads
FALLIBLE_BUILTINS from the compiler itself, generates an
ignore-the-failure program for every member, and asserts each one is
rejected with E520. Then it generates a failing call for each, wrapped
in `check`, and asserts the failure is caught and FORMATTED - never a
traceback. A new fallible builtin is covered the moment it is added,
with no test to remember to write.

    python check_fallible.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"

sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

# its own directory and proof cache, so two runs at once do not collide
SCRATCH = isolate("check_fallible") / "_fallible_check.vel"

# how to call each builtin so that it type-checks; every entry uses
# arguments that would compile if the failure were handled
CALLS = {
    "to_int":      'to_int("x")',
    "read_file":   'read_file("nope.txt")',
    "read_file_secret": 'read_file_secret("nope.txt")',
    "fetch":       'fetch("https://example.invalid")',
    "post":        'post("https://example.invalid", "b")',
    "fetch_status": 'fetch_status("https://example.invalid")',
    "request":     'request("GET", "https://example.invalid", "", "{}")',
    "pop":         "pop(xs)",
    "slice":       "slice(xs, 0, 9)",
    "set_at":      "set_at(xs, 9, 1)",
    "add_or_fail": "add_or_fail(9223372036854775807, 1)",
    "sub_or_fail": "sub_or_fail(-9223372036854775807, 2)",
    "mul_or_fail": "mul_or_fail(4000000000, 4000000000)",
    "div_or_fail": "div_or_fail(10, 0)",
    "mod_or_fail": "mod_or_fail(10, 0)",
    "divide_or_fail": 'divide_or_fail(money(10, "INR"), 0, "half_up")',
    "parse_money": 'parse_money("not an amount", "INR")',
    "py":          'py("nosuchmodule", "f", xs_t)',
    "py_int":      'py_int("nosuchmodule", "f", xs_t)',
    "py_float":    'py_float("nosuchmodule", "f", xs_t)',
    "py_json":     'py_json("nosuchmodule", "f", "[]")',
    "py_new":      'py_new("nosuchmodule", "f", "[]")',
    "py_do":       "py_do(h, \"m\", \"[]\")",
    "py_field":    "py_field(h, \"f\")",
    "json_get":    'json_get("{}", "missing")',
    "json_int":    'json_int("{}", "missing")',
    "json_float":  'json_float("{}", "missing")',
    "json_len":    'json_len("{}", "missing")',
}

# effects each call needs declared, and setup lines
NEEDS = {
    "read_file": "fs", "read_file_secret": "fs",
    "fetch": "net", "post": "net",
    "fetch_status": "net", "request": "net",
    "py": "ffi", "py_int": "ffi", "py_float": "ffi", "py_json": "ffi",
    "py_new": "ffi", "py_do": "ffi", "py_field": "ffi",
}
SETUP = {
    "pop": "    let xs: List of Int = []\n",
    "slice": "    let xs = [1, 2]\n",
    "set_at": "    let xs = [1, 2]\n",
    "py": '    let xs_t: List of Text = []\n',
    "py_int": '    let xs_t: List of Text = []\n',
    "py_float": '    let xs_t: List of Text = []\n',
}
# py_do/py_field need a Handle; the only way to get one is py_new, so
# their ignore-case is checked but the runtime case is skipped
NO_RUNTIME = {"py_do", "py_field",
              # network calls depend on the machine; the checker case is
              # what matters here, the sandbox suite covers runtime
              "fetch", "post", "fetch_status", "request"}
# map get is fallible but spelled the same as list get; covered by its
# own path in the example suite
SKIP = {"get"}


def run(source: str, effect: str | None = None) -> tuple:
    """Run the case under the narrowest budget it needs. From 5.0 a run
    with no --allow gets io, so a builtin that reads a file or calls
    Python has to be granted that effect or the refusal, not the
    failure, is what comes back."""
    SCRATCH.write_text(source, encoding="utf-8")
    allow = "io" + (f",{effect}" if effect else "")
    done = subprocess.run(
        [sys.executable, str(VELARIS), str(SCRATCH), "--allow", allow],
        capture_output=True, text=True, timeout=300, cwd=HERE)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def check_only(source: str) -> tuple:
    SCRATCH.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(VELARIS), "check", str(SCRATCH)],
        capture_output=True, text=True, timeout=300, cwd=HERE)
    return done.returncode, (done.stdout or "") + (done.stderr or "")


# Not a builtin of its own, but the one new way a network call can fail
# since 3.0: a redirect to a host outside the run's net grants. The
# program asked for one host and was sent to another, so this is a
# failure it can catch, unlike a refused host (E314, which it cannot).
def redirect_case() -> tuple:
    """(passed, detail): the failure formats and is caught, never a
    traceback, against a local server that redirects."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header("Location", "http://localhost:9/elsewhere")
            self.end_headers()

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    source = f'''fn main() uses io, net {{
    check fetch("http://127.0.0.1:{port}/") {{
        ok b {{
            print("followed")
        }}
        fail why {{
            print("caught: " + why)
        }}
    }}
}}
'''
    SCRATCH.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(VELARIS), str(SCRATCH),
         "--allow", f"io,net:127.0.0.1:{port}"],
        capture_output=True, text=True, timeout=300, cwd=HERE)
    srv.shutdown()
    SCRATCH.unlink(missing_ok=True)
    output = (done.stdout or "") + (done.stderr or "")
    good = (done.returncode == 0 and "caught:" in output
            and "redirected to" in output and "Traceback" not in output)
    return good, output.strip()[:100]


def main() -> int:
    members = sorted(velaris.FALLIBLE_BUILTINS - SKIP)
    missing = [m for m in members if m not in CALLS]
    if missing:
        print("FALLIBLE_BUILTINS has members this test cannot call:")
        for m in missing:
            print(f"  {m}  <- add a call recipe to CALLS in this file")
        return 1

    passed = failed = 0
    print(f"{len(members)} fallible builtins, read from the compiler")
    print("-" * 62)
    for name in members:
        effect = NEEDS.get(name)
        uses = f" uses io{', ' + effect if effect else ''}"
        setup = SETUP.get(name, "")
        handle = ('    check py_new("sqlite3", "connect", '
                  '"[\\":memory:\\"]") {\n        ok h {\n'
                  if name in ("py_do", "py_field") else "")
        closer = ("        }\n        fail w {\n            print(w)\n"
                  "        }\n    }\n" if handle else "")
        indent = "        " if handle else "    "

        # 1. ignoring the failure must be E520
        ignore = (f"fn main(){uses} {{\n{setup}{handle}"
                  f"{indent}let v = {CALLS[name]}\n"
                  f"{indent}print(\"ran\")\n{closer}}}\n")
        code, out = check_only(ignore)
        if code == 0 or "E520" not in out:
            print(f"  NOT ENFORCED {name}: ignoring it passed check")
            failed += 1
            continue

        # 2. a caught failure must format, never traceback
        if name in NO_RUNTIME:
            print(f"  ok enforced  {name} (runtime case covered elsewhere)")
            passed += 1
            continue
        caught = (f"fn main(){uses} {{\n{setup}{handle}"
                  f"{indent}check {CALLS[name]} {{\n"
                  f"{indent}    ok v {{\n{indent}        print(\"ok\")\n"
                  f"{indent}    }}\n"
                  f"{indent}    fail why {{\n"
                  f"{indent}        print(\"caught\")\n"
                  f"{indent}    }}\n{indent}}}\n{closer}}}\n")
        code, out = run(caught, effect)
        if "Traceback" in out:
            print(f"  RAW CRASH    {name}: a failure escaped as a "
                  f"traceback")
            failed += 1
        elif code == 0 and ("caught" in out or "ok" in out):
            print(f"  ok enforced  {name}: refused when ignored, "
                  f"formatted when caught")
            passed += 1
        else:
            print(f"  UNEXPECTED   {name}: exit {code}")
            print("               " + out.strip().splitlines()[0][:80]
                  if out.strip() else "")
            failed += 1

    SCRATCH.unlink(missing_ok=True)
    good, detail = redirect_case()
    if good:
        print("  ok        a redirect to an ungranted host is a failure the "
              "program can catch")
        passed += 1
    else:
        print("  BROKEN    a redirect to an ungranted host: " + detail)
        failed += 1

    print("-" * 62)
    print(f"{passed} enforced, {failed} not")
    if failed == 0:
        print("a builtin added to FALLIBLE_BUILTINS without a recipe here")
        print("fails this test loudly - the v2.42 mistake cannot recur")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
