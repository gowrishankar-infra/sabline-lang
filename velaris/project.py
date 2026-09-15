"""A project's files: vendored libraries and velaris.lock, build, new, doctor.
"""
import json
import os
import sys

from .version import VERSION, _INSTALL_DIR, _PACKAGE_DIR
from .errors import VelarisError
from .lexer import lex
from .parser import Parser
from .loader import load_program
from .budget import _RedirectRefused, _add_opener
from .effects import check_effects
from .checker import check_types
from .editor import inspect_source
from typing import Any


STARTER = """// Welcome to Velaris - the language where you can trust code you
// didn't write. Run me with:   velaris main.vel

import "std.vel"

fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    if price < 10 {
        return 0
    }
    return price - 10
}

fn main() uses io {
    print("hello from Velaris!")
    print("discount(50) = " + discount(50))
    print("sorted: " + sort([5, 3, 8, 1]))
    check to_int(ask("type a number:")) {
        ok n {
            print("double that is " + (n * 2))
        }
        fail why {
            print("that was not a number - " + why)
        }
    }
}
"""


MANIFEST = "velaris.toml"
LOCKFILE = "velaris.lock"
LOCK_SCHEMA = "velaris.lock/1"


def _manifest_read() -> list[Any]:
    """Every dependency, as (name, source, sha256)."""
    if not os.path.exists(MANIFEST):
        return []
    import re as _re
    text = open(MANIFEST, encoding="utf-8").read()
    return [(m.group(1), m.group(2), m.group(3)) for m in _re.finditer(
        r'^(\w[\w.-]*)\s*=\s*\{\s*source\s*=\s*"([^"]*)"\s*,\s*'
        r'sha256\s*=\s*"([0-9a-f]{64})"\s*\}\s*$', text, _re.M)]


def _manifest_write(deps: list[Any]) -> None:
    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write("# Velaris dependencies. Every library is vendored into\n"
                "# lib/ and recorded here with the exact bytes it had, so\n"
                "# 'velaris deps --verify' can tell you if anything "
                "changed.\n\n")
        f.write("[dependencies]\n")
        for name, source, digest in sorted(deps):
            f.write(f'{name} = {{ source = "{source}", '
                    f'sha256 = "{digest}" }}\n')


# ---- velaris.lock ---------------------------------------------------------
#      The manifest says what this project depends on. The lock says
#      exactly which bytes were vendored, where they came from, and
#      which Velaris put them there - so a checkout on another machine
#      can be shown to hold the same libraries, not merely libraries
#      with the same names.

def _lock_read() -> dict[Any, Any]:
    """{name: entry}, empty when there is no lock or it cannot be read."""
    if not os.path.exists(LOCKFILE):
        return {}
    try:
        with open(LOCKFILE, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for entry in (doc.get("libraries") or []):
        if isinstance(entry, dict) and entry.get("name"):
            out[entry["name"]] = entry
    return out


def _lock_write(entries: dict[Any, Any]) -> None:
    doc = {"lockfile": LOCK_SCHEMA,
           "libraries": [entries[name] for name in sorted(entries)]}
    with open(LOCKFILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")


def _lock_path(entry: dict[Any, Any]) -> str:
    """Where a lock entry says its library lives, as this OS spells it."""
    where: str = entry.get("file") or ("lib/" + entry["name"] + ".vel")
    return os.path.join(*where.split("/"))


def _digest_of(path: str) -> str:
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_libraries() -> int:
    """Are the vendored libraries exactly the ones that were locked?

    Against velaris.lock when there is one - which also knows which
    Velaris added each library - and against velaris.toml when there is
    not, so a project made before 3.1 still verifies. Returns the exit
    code: 0 when everything matches.
    """
    lock = _lock_read()
    deps = _manifest_read()
    if not lock and not deps:
        print("nothing to verify - add a library with: "
              "velaris add <url or path>")
        return 0

    if lock:
        rows = [(e["name"], e.get("source", "?"), e.get("sha256", ""),
                 _lock_path(e), e.get("added_by", "?")) for e in
                (lock[n] for n in sorted(lock))]
        against = f"{LOCKFILE} ({len(rows)} librar(ies))"
    else:
        rows = [(n, src, digest, os.path.join("lib", n + ".vel"), "?")
                for n, src, digest in sorted(deps)]
        against = (f"{MANIFEST} - there is no {LOCKFILE} yet; "
                   f"velaris add writes one")
    print(f"checking against {against}")

    bad = 0
    for name, source, digest, path, added_by in rows:
        if not os.path.exists(path):
            print(f"  MISSING  {name} - {path} is not there "
                  f"(re-add it: velaris add {source})")
            bad += 1
            continue
        now = _digest_of(path)
        if now != digest:
            print(f"  CHANGED  {name} - {path} is not the file that was "
                  f"locked")
            print(f"           locked {digest[:16]}...  now "
                  f"{now[:16]}...")
            bad += 1
        else:
            note = f"  (added by Velaris {added_by})" if added_by != "?" \
                else ""
            print(f"  ok       {name}{note}")

    if lock:
        # a manifest entry with no lock entry is a half-recorded library
        locked = set(lock)
        for name, source, _digest in sorted(deps):
            if name not in locked:
                print(f"  UNLOCKED {name} is in {MANIFEST} and not in "
                      f"{LOCKFILE} (re-add it: velaris add {source})")
                bad += 1

    named = {os.path.normcase(os.path.abspath(row[3])) for row in rows}
    if os.path.isdir("lib"):
        for found in sorted(os.listdir("lib")):
            if not found.endswith(".vel"):
                continue
            here = os.path.join("lib", found)
            if os.path.normcase(os.path.abspath(here)) not in named:
                print(f"  note     {here} is vendored and nothing records "
                      f"where it came from")

    if bad:
        print(f"\n{bad} problem(s). A library that changed under you is "
              f"worth looking at before trusting it.")
        return 1
    print(f"\nall {len(rows)} librar(ies) are exactly as locked")
    return 0


def packages(argv: list[Any]) -> int:
    import hashlib
    cmd = argv[0]
    deps = _manifest_read()
    lock = _lock_read()

    if cmd == "verify" or (cmd == "deps" and "--verify" in argv):
        return verify_libraries()

    if cmd == "deps":
        if not deps:
            print("no dependencies yet - add one with: "
                  "velaris add <url or path>")
            return 0
        print(f"{len(deps)} dependenc(ies), vendored in lib/")
        for name, source, digest in deps:
            here = os.path.join("lib", name + ".vel")
            mark = "ok " if os.path.exists(here) else "MISSING"
            added = lock.get(name, {}).get("added_by")
            print(f"  [{mark}] {name}\n      from {source}"
                  f"\n      {digest[:16]}..."
                  + (f"   added by Velaris {added}" if added else ""))
        if not lock:
            print(f"\nthere is no {LOCKFILE} yet - velaris add writes "
                  f"one, and 'velaris deps --verify' reads it")
        else:
            print(f"\n{LOCKFILE} records all of it; check it with: "
                  f"velaris deps --verify")
        return 0

    if len(argv) < 2:                     # add
        print("usage: velaris add <url or path> [as <name>] [--force]",
              file=sys.stderr)
        return 1
    force = "--force" in argv
    words = [a for a in argv[1:] if not a.startswith("--")]
    source = words[0] if words else ""
    name = None
    if len(words) >= 3 and words[1] == "as":
        name = words[2]
    if name is None:
        name = os.path.basename(source)
        if name.endswith(".vel"):
            name = name[:-4]
    if not name or "/" in name or "\\" in name:
        print(f"'{name}' is not a usable library name", file=sys.stderr)
        return 1

    if source.startswith("http://") or source.startswith("https://"):
        try:
            with _add_opener(source).open(source, timeout=20) as resp:
                data = resp.read(4 << 20)
        except _RedirectRefused as e:
            print(f"could not fetch {source}: it {e.why} ({e.target}); "
                  f"'velaris add' refuses that redirect (8.0)",
                  file=sys.stderr)
            return 1
        except Exception as e:
            print(f"could not fetch {source}: {e}", file=sys.stderr)
            return 1
    else:
        if not os.path.exists(source):
            print(f"no such file: {source}", file=sys.stderr)
            return 1
        data = open(source, "rb").read()

    # the exact bytes, byte for byte, are what gets vendored and what
    # gets locked: the digest a lock records is then the digest of what
    # the source published, on every platform. Before 3.1 the file was
    # decoded and rewritten, so the same library added on Windows and on
    # Linux locked two different hashes.
    digest = hashlib.sha256(data).hexdigest()
    path = os.path.join("lib", name + ".vel")

    if os.path.exists(path):
        here = _digest_of(path)
        if here != digest and not force:
            print(f"'{name}' is already vendored at {path}, and what you "
                  f"are adding is a different file.", file=sys.stderr)
            print(f"  vendored  {here}", file=sys.stderr)
            print(f"  incoming  {digest}", file=sys.stderr)
            print("  add --force to replace it, after you have looked "
                  "at what changed", file=sys.stderr)
            return 1
        locked = lock.get(name, {}).get("sha256")
        if locked and locked != here:
            print(f"note: {path} did not match {LOCKFILE} before this "
                  f"({locked[:16]}... locked, {here[:16]}... on disk)")

    os.makedirs("lib", exist_ok=True)
    kept = open(path, "rb").read() if os.path.exists(path) else None
    with open(path, "wb") as f:
        f.write(data)

    rep_ = inspect_source(path)           # a library must compile
    if rep_["errors"]:
        if kept is None:
            os.remove(path)
        else:
            with open(path, "wb") as f:   # put back what was there
                f.write(kept)
        print(f"'{name}' does not compile, so it was not added:",
              file=sys.stderr)
        for err in rep_["errors"][:3]:
            print(f"  line {err['line']}: [{err['code']}] {err['message']}",
                  file=sys.stderr)
        return 1

    deps = [d for d in deps if d[0] != name] + [(name, source, digest)]
    _manifest_write(deps)
    lock[name] = {"name": name, "source": source, "sha256": digest,
                  "file": "lib/" + name + ".vel", "added_by": VERSION}
    _lock_write(lock)
    own = [f for f in rep_["functions"]
           if os.path.abspath(f["file"]) == os.path.abspath(path)]
    proven = sum(1 for f in own if f["status"] == "proven")
    effs = sorted({e for f in own for e in f["effects"]})
    print(f"added {name} -> lib/{name}.vel")
    print(f"  {len(own)} function(s), {proven} with proven promises")
    print(f"  performs: {', '.join(effs) if effs else 'nothing'}")
    print(f"  sha256 {digest[:16]}..., locked in {LOCKFILE}")
    print(f'  use it with: import "lib/{name}.vel" as {name}')
    return 0


def gather_sources(entry: str) -> dict[Any, Any]:
    """The entry file and everything it imports, by relative path."""
    seen: dict[Any, Any] = {}
    root = os.path.dirname(os.path.abspath(entry)) or "."

    def walk(path: str) -> None:
        ap = os.path.abspath(path)
        rel = os.path.relpath(ap, root).replace("\\", "/")
        if rel in seen:
            return
        if not os.path.exists(ap):
            return                       # the stdlib is bundled separately
        text = open(ap, encoding="utf-8").read()
        seen[rel] = text
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("import "):
                continue
            piece = line[len("import "):].strip()
            if piece.startswith('"'):
                target = piece[1:piece.index('"', 1)]
                walk(os.path.join(os.path.dirname(ap), target))
    walk(entry)
    return seen


def build_program(argv: list[Any]) -> int:
    """Turn a Velaris program into one file anyone can run."""
    if not argv or argv[0].startswith("-"):
        print("usage: velaris build program.vel [-o name]",
              file=sys.stderr)
        return 1
    entry = argv[0]
    if not os.path.exists(entry):
        print(f"no such file: {entry}", file=sys.stderr)
        return 1
    out_name = os.path.splitext(os.path.basename(entry))[0]
    if "-o" in argv:
        out_name = argv[argv.index("-o") + 1]

    report = inspect_source(entry)       # never ship what does not compile
    if report["errors"]:
        print(f"{entry} does not compile, so it was not built:",
              file=sys.stderr)
        for e in report["errors"][:5]:
            print(f"  line {e['line']}: [{e['code']}] {e['message']}",
                  file=sys.stderr)
        return 1

    try:
        import PyInstaller                       # noqa: F401
    except ImportError:
        print("building needs PyInstaller:\n  pip install pyinstaller",
              file=sys.stderr)
        return 1

    import json as _json
    import shutil
    import subprocess
    import tempfile

    sources = gather_sources(entry)
    entry_rel = os.path.relpath(os.path.abspath(entry),
                                os.path.dirname(os.path.abspath(entry)))
    entry_rel = entry_rel.replace("\\", "/")
    work = tempfile.mkdtemp(prefix="velaris-build-")
    launcher = os.path.join(work, f"{out_name}.py")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write("# Generated by velaris build - a Velaris program,\n"
                "# carrying its own compiler.\n"
                "import os, sys, tempfile\n"
                f"SOURCES = {_json.dumps(sources)}\n"
                f"ENTRY = {_json.dumps(entry_rel)}\n"
                "import velaris\n"
                "def main():\n"
                "    here = tempfile.mkdtemp(prefix='velaris-run-')\n"
                "    for rel, text in SOURCES.items():\n"
                "        p = os.path.join(here, rel)\n"
                "        os.makedirs(os.path.dirname(p), exist_ok=True)\n"
                "        open(p, 'w', encoding='utf-8').write(text)\n"
                "    sys.argv = [sys.argv[0], os.path.join(here, ENTRY)]"
                " + sys.argv[1:]\n"
                "    return velaris.main()\n"
                "sys.exit(main())\n")

    here = _INSTALL_DIR
    sep = ";" if os.name == "nt" else ":"
    cmd = [sys.executable, "-m", "PyInstaller", "--onefile",
           "--name", out_name, "--distpath", os.path.abspath("."),
           "--workpath", os.path.join(work, "build"),
           "--specpath", work, "--noconfirm",
           "--paths", here,
           "--add-data", f"{os.path.join(here, 'stdlib')}{sep}stdlib"]
    for extra in ("z3", "llvmlite"):
        try:
            __import__(extra)
            cmd += ["--collect-all", extra]
        except ImportError:
            pass
    cmd.append(launcher)
    if "--for-everyone" in argv:
        wf = os.path.join(".github", "workflows",
                          f"build-{out_name}.yml")
        os.makedirs(os.path.dirname(wf), exist_ok=True)
        with open(wf, "w", encoding="utf-8") as f:
            f.write(f"""# Built by velaris build --for-everyone.
# One machine cannot build for other machines, so three build for you.
name: build {out_name}

on:
  push:
    tags: ["v*"]
  workflow_dispatch:

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            asset: {out_name}-windows.exe
          - os: ubuntu-latest
            asset: {out_name}-linux
          - os: macos-latest
            asset: {out_name}-macos
    runs-on: ${{{{ matrix.os }}}}
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - run: pip install "velaris-lang[full]" pyinstaller
      - run: velaris build {entry} -o {out_name}
      - shell: bash
        run: |
          for f in {out_name} {out_name}.exe; do
            [ -f "$f" ] && mv "$f" "${{{{ matrix.asset }}}}"
          done
      - uses: softprops/action-gh-release@v2
        if: startsWith(github.ref, 'refs/tags/')
        with:
          files: ${{{{ matrix.asset }}}}
""")
        print(f"wrote {wf}")
        print("commit it, then push a tag: three machines will build "
              f"{out_name} for Windows, Linux and macOS")
        return 0

    print(f"building {out_name} from {entry} "
          f"({len(sources)} file(s), this takes a minute)...")
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        print(done.stdout[-2000:], file=sys.stderr)
        print(done.stderr[-2000:], file=sys.stderr)
        print("the build failed - the output above is from PyInstaller",
              file=sys.stderr)
        return 1
    shutil.rmtree(work, ignore_errors=True)
    made = out_name + (".exe" if os.name == "nt" else "")
    size = os.path.getsize(made) / (1024 * 1024) if os.path.exists(made) else 0
    print(f"built ./{made}  ({size:.0f} MB)")
    print("that file is the whole program - no Python, no Velaris, "
          "nothing to install")
    return 0


def doctor() -> int:
    OK, OPT, BAD = "[ ok ]", "[ -- ]", "[FAIL]"
    lines, healthy = [], True
    pv = sys.version_info
    if (pv.major, pv.minor) >= (3, 10):
        lines.append(f"{OK} python {pv.major}.{pv.minor}.{pv.micro}")
    else:
        healthy = False
        lines.append(f"{BAD} python {pv.major}.{pv.minor} - Velaris "
                     f"needs 3.10+ (install from python.org)")
    here = _PACKAGE_DIR
    lines.append(f"{OK} velaris {VERSION}  ({here})")
    try:
        import z3  # noqa: F401
        lines.append(f"{OK} z3-solver - promises are PROVEN before "
                     f"running")
    except ImportError:
        lines.append(f"{OPT} z3-solver absent - promises checked at "
                     f"runtime instead   fix: pip install z3-solver")
    try:
        import llvmlite  # noqa: F401
        lines.append(f"{OK} llvmlite - pure numeric functions run as "
                     f"machine code")
    except ImportError:
        lines.append(f"{OPT} llvmlite absent - everything runs "
                     f"interpreted   fix: pip install llvmlite")
    std = os.path.join(_INSTALL_DIR, "stdlib", "std.vel")
    if os.path.exists(std):
        try:
            fs, _ = load_program(std)
            lines.append(f"{OK} standard library - {len(fs)} functions "
                         f"ready to import")
        except VelarisError:
            healthy = False
            lines.append(f"{BAD} standard library present but broken - "
                         f"reinstall: pip install --force-reinstall "
                         f"velaris-lang")
    else:
        healthy = False
        lines.append(f"{BAD} standard library missing - reinstall: "
                     f"pip install --force-reinstall velaris-lang")
    try:
        toks = lex('fn main() uses io { print(2 + 2) }')
        fs2, rs2, _ = Parser(toks).parse_program()
        errs: list[Any] = []
        check_effects(fs2, errs)
        check_types(fs2, rs2, errs)
        if errs:
            raise VelarisError("E999", "self-test failed", 1)
        lines.append(f"{OK} compiler self-test - lex, parse, effects, "
                     f"types all answering")
    except Exception:
        healthy = False
        lines.append(f"{BAD} compiler self-test failed - please report "
                     f"this at github.com/gowrishankar-infra/"
                     f"velaris-lang/issues")
    print(f"velaris doctor - {VERSION}")
    print("-" * 60)
    for ln in lines:
        print(ln)
    print("-" * 60)
    if healthy:
        print("all essential checks passed. "
              "[ -- ] items are optional extras.")
        return 0
    print("something needs fixing - see [FAIL] lines above.")
    return 1


def new_project(name: str) -> int:
    if not name or name.startswith("-"):
        print("usage: velaris new <project-name>", file=sys.stderr)
        return 1
    if os.path.exists(name):
        print(f"'{name}' already exists - pick a fresh name",
              file=sys.stderr)
        return 1
    os.makedirs(name)
    with open(os.path.join(name, "main.vel"), "w",
              encoding="utf-8") as f:
        f.write(STARTER)
    with open(os.path.join(name, "README.md"), "w",
              encoding="utf-8") as f:
        f.write(f"# {name}\n\nA Velaris project.\n\n"
                f"```\ncd {name}\nvelaris main.vel\n```\n\n"
                f"Docs: https://github.com/gowrishankar-infra/"
                f"velaris-lang\n")
    print(f"created {name}/")
    print(f"  {name}/main.vel    - a working program with a proven "
          f"contract")
    print(f"  {name}/README.md")
    print(f"next:  cd {name}  then  velaris main.vel")
    return 0
