#!/usr/bin/env python3
"""Every job of release.yml and publish-crate.yml, run the way a runner
runs it: its own `run:` scripts, in bash, against stand-ins.

`check_release.py` imports this and runs it; it is a module of its own
only because it is long, and `python check_release.py` is still what
runs every job's shell. RELEASING.md carries the standing rule.

**Why.** Three 9.0 pre-releases in a row were spent on three defects,
and all three were in workflow code that had been verified by reading
it: a skip that travelled past a job which had rescued itself; a
registry that refuses a token minted under `workflow_run`; a glob that
handed a directory to a command that refuses one. Each takes seconds to
see in a run and is invisible on the page. The jobs that already had a
harness - vscode (8.2.1), move_pins (8.4), prerelease_github (9.0.0-
alpha.4) - each got one *after* failing in production. This module is
the rest of them, before.

**What a harness is, and what it is not.** It is not a model of what a
job means. `check_release.py`'s `run_job` is that, and it stays: it
decides what a whole release publishes. A harness here takes the job's
actual `run:` text out of the YAML and executes it in bash, with:

- **stand-ins on PATH** for every command that would reach the network,
  a registry, a credential, a compiler or a signing service. Each
  stand-in records every call with its arguments, produces the files the
  real command would produce, and **refuses the way the real one
  refuses** - `gh release create` refuses a directory, `cosign
  sign-blob` refuses a file that is not there, `cargo publish` refuses a
  version crates.io already has;
- **`uses:` steps modelled by what they leave behind** rather than
  skipped: `upload-artifact` collects the paths it is given into a named
  artifact and `download-artifact` lays that artifact out again, so the
  shape an artifact actually lands in is what the next job's shell sees.
  That is the defect that cost 9.0.0-alpha.3 its GitHub release;
- **`${{ }}` and `if:` evaluated** as Actions evaluates the forms these
  two workflows use, and `$GITHUB_OUTPUT`, `$GITHUB_ENV` and
  `$GITHUB_STEP_SUMMARY` carried between steps.

**A job counts as harnessed only if its stand-ins can fail.** Every job
below is run twice: once as it is, which must be green, and once with
one fault injected - a wrong command, a wrong path, a wrong artifact
name - which must make it red. A harness that has never been shown to
fail is a harness nobody has tested, which is the same rule the
agreement gate is held to (`plan/9.0.md`).

Nothing here reaches the network, signs anything, builds a wheel, an
executable or a crate, or touches a credential.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
WORKFLOWS = HERE / ".github" / "workflows"


class Unreadable(Exception):
    """A workflow this harness cannot read. Never caught into a pass."""


def slashed(path: Any) -> str:
    return str(path).replace("\\", "/")


def workflow(name: str) -> dict[str, Any]:
    import yaml
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    return dict(doc["jobs"])


def all_jobs() -> dict[tuple[str, str], dict[str, Any]]:
    """(workflow file, job name) -> the job, for both workflows."""
    out = {}
    for wf in ("release.yml", "publish-crate.yml"):
        for name, job in workflow(wf).items():
            out[(wf, name)] = job
    return out


# ---------------------------------------------------------------------------
# The stand-ins
#
# One bash script per command. Each records its call - one line per call,
# arguments tab-separated, in $FAKE/calls/<name>.log - so a case can
# assert on WHAT a command was asked, not only that the job went green.
# ---------------------------------------------------------------------------

_REC = r"""
_rec() {
  mkdir -p "$FAKE/calls"
  { for a in "$@"; do printf '%s\t' "$a"; done; printf '\n'; } \
    >> "$FAKE/calls/$_NAME.log"
}
_rec "$@"
"""


def _standin(name: str, body: str) -> str:
    return (f"#!/usr/bin/env bash\n_NAME={name}\n" + _REC + body)


# `gh`. Releases live in $FAKE/releases/<tag>/, one file per asset, so
# that "what does this release already have" is a question of the file
# system rather than of a script's memory.
FAKE_GH = _standin("gh", r"""
rel="$FAKE/releases"
case "$1 $2" in
  "release view")
    tag="$3"
    test -d "$rel/$tag" || exit 1
    if [ "$4" = "--json" ] ; then
      # --jq '.assets[].name': one name a line, which is what the job greps
      ls -1 "$rel/$tag" 2>/dev/null | grep -v '^\.' || true
    fi
    exit 0
    ;;
  "release create")
    shift 2
    tag="$1" ; shift
    test -n "$FAKE_GH_VERIFY_TAG_FAILS" && { echo "tag $tag not found" >&2 ; exit 1 ; }
    mkdir -p "$rel/$tag"
    while [ $# -gt 0 ] ; do
      case "$1" in
        --notes-file|--title) shift ;;
        --verify-tag|--prerelease|--latest) ;;
        --*) ;;
        *)
          # a directory is what `gh` refuses, and then it DELETES the
          # release it had just made (9.0.0-alpha.3)
          if [ -d "$1" ] ; then
            echo "Post https://uploads.github.com/...: read $1: is a directory" >&2
            rm -rf "$rel/$tag"
            exit 1
          fi
          test -f "$1" || { echo "no such asset: $1" >&2 ; rm -rf "$rel/$tag" ; exit 1 ; }
          cp "$1" "$rel/$tag/$(basename "$1")"
          ;;
      esac
      shift
    done
    exit 0
    ;;
  "release upload")
    shift 2
    tag="$1" ; shift
    test -d "$rel/$tag" || { echo "release not found: $tag" >&2 ; exit 1 ; }
    for f in "$@" ; do
      case "$f" in --*) continue ;; esac
      if [ -d "$f" ] ; then
        echo "Post https://uploads.github.com/...: read $f: is a directory" >&2
        exit 1
      fi
      test -f "$f" || { echo "no such asset: $f" >&2 ; exit 1 ; }
      cp "$f" "$rel/$tag/$(basename "$f")"
    done
    exit 0
    ;;
  "workflow run")
    # the dispatched run's id, and the record that it was started
    echo "$(date -u +%s)" > "$FAKE/dispatched"
    exit 0
    ;;
  "run list")
    test -f "$FAKE/dispatched" || { echo "" ; exit 0 ; }
    echo "${FAKE_RUN_ID:-4242}"
    exit 0
    ;;
  "run watch")
    test -f "$FAKE/dispatched" || { echo "no run to watch" >&2 ; exit 1 ; }
    if [ -n "$FAKE_RUN_RED" ] ; then
      echo "X the run failed" >&2 ; exit 1
    fi
    echo "the run succeeded"
    exit 0
    ;;
esac
echo "unknown command: gh $1 $2" >&2
exit 1
""")

# `cosign`. It signs nothing: it checks that what it was asked to sign is
# there, writes the files the real one writes, and verifies against what
# it recorded when it signed.
FAKE_COSIGN = _standin("cosign", r"""
sig="" ; cert="" ; bundle="" ; blob="" ; statement="" ; typ="" ; identity=""
cmd="$1" ; shift
while [ $# -gt 0 ] ; do
  case "$1" in
    --output-signature) sig="$2" ; shift ;;
    --output-certificate) cert="$2" ; shift ;;
    --bundle) bundle="$2" ; shift ;;
    --statement) statement="$2" ; shift ;;
    --type) typ="$2" ; shift ;;
    --certificate-identity) identity="$2" ; shift ;;
    --certificate-oidc-issuer) shift ;;
    --yes|--*) ;;
    *) blob="$1" ;;
  esac
  shift
done
case "$cmd" in
  sign-blob)
    test -f "$blob" || { echo "cosign: open $blob: no such file or directory" >&2 ; exit 1 ; }
    test -n "$sig" && printf 'signature-of-%s\n' "$(basename "$blob")" > "$sig"
    test -n "$cert" && printf -- '-----BEGIN CERTIFICATE-----\n' > "$cert"
    test -n "$bundle" && printf '{"blob":"%s"}\n' "$(basename "$blob")" > "$bundle"
    exit 0
    ;;
  attest-blob)
    test -f "$statement" || { echo "cosign: open $statement: no such file or directory" >&2 ; exit 1 ; }
    test -n "$bundle" || { echo "cosign: --bundle is required" >&2 ; exit 1 ; }
    python3 - "$statement" "$bundle" <<'PY'
import json, sys
statement = json.load(open(sys.argv[1], encoding="utf-8"))
json.dump({"statement": statement}, open(sys.argv[2], "w", encoding="utf-8"))
PY
    exit 0
    ;;
  verify-blob-attestation)
    test -f "$bundle" || { echo "cosign: open $bundle: no such file or directory" >&2 ; exit 1 ; }
    test -f "$blob" || { echo "cosign: open $blob: no such file or directory" >&2 ; exit 1 ; }
    test -n "$identity" || { echo "cosign: --certificate-identity is required" >&2 ; exit 1 ; }
    python3 - "$bundle" "$typ" "$blob" <<'PY'
import hashlib, json, sys
bundle, want_type, blob = sys.argv[1], sys.argv[2], sys.argv[3]
statement = json.load(open(bundle, encoding="utf-8"))["statement"]
if statement["predicateType"] != want_type:
    sys.exit(f"cosign: the bundle's predicateType is "
             f"{statement['predicateType']}, not {want_type}")
digest = hashlib.sha256(open(blob, "rb").read()).hexdigest()
if statement["subject"][0]["digest"]["sha256"] != digest:
    sys.exit(f"cosign: the Statement is not about {blob}")
print("Verified OK")
PY
    exit $?
    ;;
esac
echo "Error: unknown command \"$cmd\" for \"cosign\"" >&2
exit 1
""")

# `cargo`. Nothing is compiled. `metadata` answers from rt/Cargo.toml,
# `package` writes a .crate the size of a real one's name, `publish`
# refuses a version the stand-in registry already serves.
FAKE_CARGO = _standin("cargo", r"""
case "$1" in
  metadata)
    python3 - <<'PY'
import json, re, sys
from pathlib import Path
text = Path("Cargo.toml").read_text(encoding="utf-8") \
    if Path("Cargo.toml").exists() else Path("rt/Cargo.toml").read_text(encoding="utf-8")
m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
print(json.dumps({"packages": [{"version": m.group(1) if m else "0.0.0"}]}))
PY
    exit 0
    ;;
  build|test)
    test -f Cargo.toml || { echo "cargo: could not find Cargo.toml" >&2 ; exit 1 ; }
    case " $* " in
      *" --locked "*) test -f Cargo.lock || { echo "cargo: the lock file needs to be updated but --locked was passed" >&2 ; exit 1 ; } ;;
    esac
    echo "    Finished \`release\` profile"
    exit 0
    ;;
  package)
    test -f Cargo.toml || { echo "cargo: could not find Cargo.toml" >&2 ; exit 1 ; }
    v=$(python3 - <<'PY'
import re
from pathlib import Path
m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', Path("Cargo.toml").read_text(encoding="utf-8"))
print(m.group(1) if m else "0.0.0")
PY
)
    case " $* " in
      *" --list "*)
        printf 'Cargo.toml\nCargo.lock\nsrc/lib.rs\nsrc/main.rs\n'
        exit 0 ;;
    esac
    mkdir -p target/package
    printf 'a crate\n' > "target/package/sabline-rt-$v.crate"
    echo "  Packaged sabline-rt v$v"
    exit 0
    ;;
  publish)
    test -n "$CARGO_REGISTRY_TOKEN" || { echo "error: no token found" >&2 ; exit 1 ; }
    v=$(python3 - <<'PY'
import re
from pathlib import Path
m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', Path("Cargo.toml").read_text(encoding="utf-8"))
print(m.group(1) if m else "0.0.0")
PY
)
    if [ -f "$FAKE/crates/$v" ] ; then
      echo "error: crate version $v is already uploaded" >&2 ; exit 1
    fi
    mkdir -p "$FAKE/crates" ; touch "$FAKE/crates/$v"
    echo "    Uploading sabline-rt v$v"
    exit 0
    ;;
esac
echo "error: no such command: \`$1\`" >&2
exit 101
""")

FAKE_PYINSTALLER = _standin("pyinstaller", r"""
name=sabline
prev=""
for a in "$@" ; do
  case "$prev" in --name) name="$a" ;; esac
  prev="$a"
done
script="${@: -1}"
test -f "$script" || { echo "pyinstaller: script not found: $script" >&2 ; exit 1 ; }
mkdir -p dist
# a "binary" that answers the smoke test the way the real one must
cat > "dist/$name" <<'EXE'
#!/usr/bin/env bash
# every run recorded, with whether it was asked to inject a fault, so a
# case can assert that the smoke test really exercised the confinement
{ printf '%s\t' "${SABLINE_FAULT_INJECT:--}" ; for a in "$@" ; do printf '%s\t' "$a" ; done ; printf '\n' ; } >> "$FAKE/calls/exe.log"
case "$1" in
  --version) echo "sabline 0.0.0-fixture" ;;
  doctor) echo "ok" ;;
  demo) echo "demo: two runs" ;;
  check) echo "checked $2" ;;
  *)
    if [ "$SABLINE_FAULT_INJECT" = spawn ] && [ "$2" != --no-confine ] ; then
      echo "E319: the operating system refused a new process" >&2 ; exit 1
    fi
    echo "ran $1"
    ;;
esac
EXE
chmod +x "dist/$name"
echo "completed successfully."
exit 0
""")

FAKE_CYCLONEDX = _standin("cyclonedx-py", r"""
out=""
prev=""
for a in "$@" ; do
  case "$prev" in -o|--output-file) out="$a" ;; esac
  prev="$a"
done
test -n "$out" || { echo "cyclonedx-py: no -o given" >&2 ; exit 1 ; }
mkdir -p "$(dirname "$out")"
printf '{"bomFormat":"CycloneDX","specVersion":"1.6","components":[{"name":"z3-solver"}]}\n' > "$out"
exit 0
""")

FAKE_NODE = _standin("node", r"""
case "$1" in
  --version) echo "v24.4.0" ; exit 0 ;;
  -p)
    python3 - "$2" <<'PY'
import json, re, sys
expr = sys.argv[1]
m = re.fullmatch(r"require\('\./package\.json'\)\.(\w+)", expr)
doc = json.load(open("package.json", encoding="utf-8"))
print(doc[m.group(1)] if m else "")
PY
    exit 0 ;;
esac
exit 0
""")

FAKE_NPM = _standin("npm", r"""
case "$1" in
  --version) echo "11.6.0" ; exit 0 ;;
  install) exit 0 ;;
  version)
    python3 - "$2" <<'PY'
import json, sys
doc = json.load(open("package.json", encoding="utf-8"))
doc["version"] = sys.argv[1]
json.dump(doc, open("package.json", "w", encoding="utf-8"), indent=2)
PY
    exit 0 ;;
  publish)
    v=$(python3 -c "import json;print(json.load(open('package.json',encoding='utf-8'))['version'])")
    mkdir -p "$FAKE/npm-published" ; touch "$FAKE/npm-published/$v"
    echo "+ sabline@$v"
    exit 0 ;;
esac
echo "Unknown command: \"$1\"" >&2
exit 1
""")

FAKE_MCP_PUBLISHER = _standin("mcp-publisher", r"""
case "$1" in
  --version) echo "1.8.1" ; exit 0 ;;
  validate)
    test -f "$2" || { echo "mcp-publisher: no such file: $2" >&2 ; exit 1 ; }
    exit 0 ;;
  login) exit 0 ;;
  publish)
    test -f server.json || { echo "mcp-publisher: no server.json here" >&2 ; exit 1 ; }
    touch "$FAKE/registry-published"
    exit 0 ;;
esac
echo "mcp-publisher: unknown command: $1" >&2
exit 1
""")

FAKE_CURL = _standin("curl", r"""
out=""
prev=""
for a in "$@" ; do
  case "$prev" in -o) out="$a" ;; esac
  prev="$a"
done
test -n "$out" || exit 0
# what the mcp-publisher release serves, and its recorded sha256 is what
# the job checks it against
printf 'mcp-publisher\n' > "$out"
exit 0
""")

FAKE_TAR = _standin("tar", r"""
# the archive holds one file, named as the job asks for it
name="$3"
test -n "$name" || name=mcp-publisher
printf '#!/usr/bin/env bash\nexec "$FAKE/mcp-publisher" "$@"\n' > "$name"
chmod +x "$name" 2>/dev/null || true
exit 0
""")

FAKE_SLEEP = _standin("sleep", "exit 0\n")

FAKE_VSCE = _standin("vsce", r"""
case "$1" in
  show)
    test -f "$FAKE/vscode-landed" && echo "Version: $V"
    exit 0 ;;
  publish) ;;
  *) echo " ERROR  Unknown command '$1'" >&2 ; exit 1 ;;
esac
test -n "$VSCE_TOKEN" || { echo " ERROR  Failed request: (401)" >&2 ; exit 1 ; }
touch "$FAKE/vscode-landed"
echo "DONE  Published gowrishankar-infra.sabline v$V."
exit 0
""")


def python_shim(base: str, work: Path) -> str:
    """The `python3`/`python` stand-in, as a Python file.

    It dispatches on the command line the jobs actually use:

      release_checks.py ...   the REAL release_checks, against the
                              stand-in registries (`base`), because that
                              is the code the job is there to run
      check_release.py        this suite; a job that runs it is told it
                              passed rather than being made to run it
                              inside itself
      build_docs.py           rewrites the pages the pin move commits
      perf_gates.py           the gate's own fixtures are elsewhere in
      check_differential.py   check_release.py; here the job's arguments
      build_mcpb.py           are what is being tested, and the bundle
      -m build / -m venv      a wheel and an sdist, or a venv with a
                              `pip` and a `sabline` in it
      -c CODE / - (stdin)     real Python, so the inline scripts in the
                              jobs - the server.json check, the Node
                              version check, the receipt assertions - run
                              for real
    """
    return f'''\
import json, os, runpy, shutil, subprocess, sys, time, zipfile
from pathlib import Path

HERE = {str(HERE)!r}
WORK = {str(work)!r}
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.environ["FAKE"], "lib"))
FAKE = Path(os.environ["FAKE"])


def rec(what):
    (FAKE / "calls").mkdir(parents=True, exist_ok=True)
    with open(FAKE / "calls" / "python3.log", "a", encoding="utf-8") as fh:
        fh.write("".join(a + "\\t" for a in what) + "\\n")


argv = sys.argv[1:]
rec(argv)

if argv and argv[0].endswith("release_checks.py"):
    import release_checks
    release_checks.ENDPOINTS.update({{k: {base!r} for k in release_checks.ENDPOINTS}})
    release_checks.RETRY_WAIT = 0
    sys.exit(release_checks.main(argv[1:]))

if argv and argv[0].endswith("check_release.py"):
    print("check_release.py: run by the harness's stand-in, not recursively")
    sys.exit(0)

if argv and argv[0].endswith("perf_gates.py"):
    # what perf_gates.py itself refuses: fewer than three runs a side,
    # and a comparison against nothing (check_release.py holds the real
    # one to the first of those)
    rest = argv[1:]
    if "--runs" in rest and int(rest[rest.index("--runs") + 1]) < 3:
        sys.exit("perf_gates.py: --against needs at least 3 runs a side")
    if "--against" in rest and not rest[rest.index("--against") + 1]:
        sys.exit("perf_gates.py: --against needs a tag to compare with")
    print("perf: the medians agree with the previous tag")
    sys.exit(0)

if argv and argv[0].endswith("check_differential.py"):
    rest = argv[1:]
    if "--old" in rest and not rest[rest.index("--old") + 1]:
        sys.exit("check_differential.py: --old needs a tag")
    if "--spec" in rest:
        where = Path(rest[rest.index("--spec") + 1])
        if not where.is_dir():
            sys.exit(f"check_differential.py: no corpus at {{where}}")
    print("differential: no difference against the previous tag")
    sys.exit(0)

if argv and argv[0].endswith("build_mcpb.py"):
    Path("sabline.mcpb").write_bytes(b"a bundle")
    print("wrote sabline.mcpb")
    sys.exit(0)

if argv and argv[0].endswith("build_docs.py"):
    # what the pin move commits beside README.md and EMBEDDING.md
    out = Path("docs")
    out.mkdir(exist_ok=True)
    for name in ("index.html", "embedding.html"):
        (out / name).write_text(
            Path("README.md").read_text(encoding="utf-8")[:200], encoding="utf-8")
    sys.exit(0)

if argv[:1] == ["-m"]:
    what = argv[1]
    rest = argv[2:]
    if what == "build":
        outdir = "dist"
        if "--outdir" in rest:
            outdir = rest[rest.index("--outdir") + 1]
        d = Path(outdir)
        d.mkdir(parents=True, exist_ok=True)
        version = os.environ.get("V") or "0.0.0"
        epoch = os.environ.get("SOURCE_DATE_EPOCH", "0")
        wheel = d / f"sabline_lang-{{version}}-py3-none-any.whl"
        # Byte-identical for the same SOURCE_DATE_EPOCH, because that is
        # what the reproducible job compares. A zip member's default
        # timestamp is the clock, which would make two builds differ for
        # a reason that is not the code.
        stamp = time.gmtime(int(epoch or 0))[:6]
        with zipfile.ZipFile(wheel, "w") as z:
            info = zipfile.ZipInfo("sabline/__init__.py", date_time=stamp)
            z.writestr(info, f"# {{epoch}}\\n")
        if "--wheel" not in rest:
            (d / f"sabline_lang-{{version}}.tar.gz").write_bytes(b"sdist")
        print("Successfully built", wheel.name)
        sys.exit(0)
    if what == "venv":
        env = Path(rest[0])
        (env / "bin").mkdir(parents=True, exist_ok=True)
        for name in ("pip", "python", "sabline"):
            target = env / "bin" / name
            target.write_text(
                "#!/usr/bin/env bash\\n"
                f'exec "$FAKE/{{name if name != "python" else "python3"}}" "$@"\\n',
                encoding="utf-8")
            target.chmod(0o755)
        sys.exit(0)
    if what == "sabline_mcp":
        sys.exit(0)
    sys.exit(0)

if argv[:1] == ["-c"]:
    sys.argv = ["-c"] + argv[2:]
    exec(compile(argv[1], "<-c>", "exec"), {{"__name__": "__main__"}})
    sys.exit(0)

if argv[:1] == ["-"] or not argv:
    text = sys.stdin.read()
    sys.argv = ["-"] + argv[1:]
    exec(compile(text, "<stdin>", "exec"), {{"__name__": "__main__"}})
    sys.exit(0)

script = argv[0]
sys.argv = list(argv)
runpy.run_path(script, run_name="__main__")
'''


FAKE_PIP = _standin("pip", r"""
# nothing is installed; what a job needs on PATH is already there
exit 0
""")

FAKE_SABLINE = _standin("sabline", r"""
case "$1" in
  mcp-manifest)
    out=""
    prev=""
    for a in "$@" ; do
      case "$prev" in -o) out="$a" ;; esac
      prev="$a"
    done
    test -n "$out" || { echo "sabline: no -o given" >&2 ; exit 1 ; }
    mkdir -p "$(dirname "$out")"
    printf '{"schema":"sabline.tools/1","tools":[]}\n' > "$out"
    exit 0 ;;
  mcp-verify)
    test -f "$2" || { echo "sabline: no such manifest: $2" >&2 ; exit 1 ; }
    test -f "$2.sigstore.json" || { echo "sabline: $2 is not signed" >&2 ; exit 1 ; }
    echo "the manifest matches the server"
    exit 0 ;;
  attest)
    test -f "$2" || { echo "sabline: no such program: $2" >&2 ; exit 1 ; }
    out=""
    prev=""
    for a in "$@" ; do
      case "$prev" in --output) out="$a" ;; esac
      prev="$a"
    done
    test -n "$out" || { echo "sabline: no --output given" >&2 ; exit 1 ; }
    python3 - "$2" "$out" "https://sabline.dev/capability/v1" <<'PY'
import hashlib, json, sys
program, out, kind = sys.argv[1], sys.argv[2], sys.argv[3]
digest = hashlib.sha256(open(program, "rb").read()).hexdigest()
json.dump({"_type": "https://in-toto.io/Statement/v1",
           "subject": [{"name": program, "digest": {"sha256": digest}}],
           "predicateType": kind,
           "predicate": {"effects": ["io"]}},
          open(out, "w", encoding="utf-8"), indent=1)
PY
    exit 0 ;;
  *)
    # a run, with --receipt writing a receipt of the attestation's subject
    prog="$1"
    test -f "$prog" || { echo "sabline: no such program: $prog" >&2 ; exit 1 ; }
    out=""
    prev=""
    for a in "$@" ; do
      case "$prev" in --receipt) out="$a" ;; esac
      prev="$a"
    done
    if [ -n "$out" ] ; then
      python3 - "$prog" "$out" <<'PY'
import hashlib, json, sys
program, out = sys.argv[1], sys.argv[2]
digest = hashlib.sha256(open(program, "rb").read()).hexdigest()
json.dump({"_type": "https://in-toto.io/Statement/v1",
           "subject": [{"name": program, "digest": {"sha256": digest}}],
           "predicateType": "https://sabline.dev/receipt/v1",
           "predicate": {"exit": {"outcome": "ok"}}},
          open(out, "w", encoding="utf-8"), indent=1)
PY
    fi
    exit 0 ;;
esac
""")



# ---------------------------------------------------------------------------
# A stand-in `sigstore`, for the attestation job's inline Python
#
# The attestation job signs and verifies twice: once with `cosign` and
# once with sigstore-python, in scripts written inline in the workflow.
# Those scripts are the job, so they run; what they import is stood in.
# It signs nothing and reaches nothing: a bundle is the Statement's bytes
# and the identity that "signed" them, and verifying reads them back.
# What it does hold is the shape the job depends on - that `verify_dsse`
# returns the media type and the payload, that the payload is the
# Statement it was given, and that a bundle made under one identity does
# not verify under another.
# ---------------------------------------------------------------------------

FAKE_SIGSTORE: dict[str, str] = {
    "sigstore/__init__.py": "",
    "sigstore/dsse.py": '''\
class Statement:
    """The Statement's bytes, as sigstore-python takes them."""

    def __init__(self, raw):
        self._raw = raw if isinstance(raw, bytes) else str(raw).encode()

    def _contents(self):
        return self._raw
''',
    "sigstore/models.py": '''\
import json


class ClientTrustConfig:
    @staticmethod
    def production():
        return ClientTrustConfig()


class Bundle:
    def __init__(self, payload=b"", identity=""):
        self.payload = payload
        self.identity = identity

    @staticmethod
    def from_json(raw):
        doc = json.loads(raw)
        return Bundle(doc["payload"].encode("utf-8"), doc["identity"])

    def to_json(self):
        return json.dumps({"payload": self.payload.decode("utf-8"),
                           "identity": self.identity,
                           "mediaType": "application/vnd.in-toto+json"})
''',
    "sigstore/oidc.py": '''\
import os


def detect_credential():
    """The workflow identity this run signs as. The real one asks
    Actions for an OIDC token; the harness is told."""
    got = os.environ.get("FAKE_SIGSTORE_IDENTITY")
    if not got:
        raise RuntimeError("no credential: this is not a workflow run")
    return got


class IdentityToken:
    def __init__(self, token):
        if not token:
            raise ValueError("an empty identity token")
        self.identity = token
''',
    "sigstore/sign.py": '''\
from .models import Bundle


class _Signer:
    def __init__(self, token):
        self._token = token

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def sign_dsse(self, statement):
        return Bundle(statement._contents(), self._token.identity)


class SigningContext:
    @staticmethod
    def from_trust_config(config):
        return SigningContext()

    def signer(self, token):
        return _Signer(token)
''',
    "sigstore/verify/__init__.py": '''\
class Verifier:
    @staticmethod
    def production():
        return Verifier()

    def verify_dsse(self, bundle, policy):
        if bundle.identity != policy.identity:
            raise RuntimeError(
                f"the bundle was signed as {bundle.identity}, "
                f"not as {policy.identity}")
        return "application/vnd.in-toto+json", bundle.payload
''',
    "sigstore/verify/policy.py": '''\
class Identity:
    def __init__(self, identity, issuer):
        self.identity = identity
        self.issuer = issuer
''',
}

STANDINS: dict[str, str] = {
    "gh": FAKE_GH,
    "cosign": FAKE_COSIGN,
    "cargo": FAKE_CARGO,
    "pyinstaller": FAKE_PYINSTALLER,
    "cyclonedx-py": FAKE_CYCLONEDX,
    "node": FAKE_NODE,
    "npm": FAKE_NPM,
    "npx": _standin("npx", "exit 0\n"),
    "mcp-publisher": FAKE_MCP_PUBLISHER,
    "curl": FAKE_CURL,
    "tar": FAKE_TAR,
    "sleep": FAKE_SLEEP,
    "vsce": FAKE_VSCE,
    "pip": FAKE_PIP,
    "sabline": FAKE_SABLINE,
}


# ---------------------------------------------------------------------------
# Expressions, conditions, and the `uses:` steps
# ---------------------------------------------------------------------------

def _lookup(path: str, ctx: dict[str, Any]) -> Any:
    here: Any = ctx
    for part in path.split("."):
        if not isinstance(here, dict) or part not in here:
            return None
        here = here[part]
    return here


def _value(expr: str, ctx: dict[str, Any]) -> str:
    """One `${{ }}` expression, for the forms these two workflows use:
    a dotted path, a quoted literal, `a == 'lit'`, and `a || b` (the
    first that is not empty)."""
    m = re.fullmatch(r"([\w.\-]+)\s*==\s*'([^']*)'", expr.strip())
    if m:
        return "true" if str(_lookup(m.group(1), ctx) or "") == m.group(2) \
            else "false"
    for piece in [p.strip() for p in expr.split("||")]:
        if not piece:
            continue
        if (piece.startswith("'") and piece.endswith("'")) or \
                (piece.startswith('"') and piece.endswith('"')):
            got: Any = piece[1:-1]
        elif re.fullmatch(r"[\w.\-]+", piece):
            got = _lookup(piece, ctx)
        else:
            raise Unreadable(f"cannot read the expression {expr!r}")
        if got not in (None, "", False):
            return str(got)
    return ""


def expand(text: Any, ctx: dict[str, Any]) -> str:
    return re.sub(r"\$\{\{([^}]*)\}\}",
                  lambda m: _value(m.group(1).strip(), ctx), str(text))


def decides(cond: Any, ctx: dict[str, Any], work: Path) -> bool:
    """A step's `if:`, for the four forms these workflows use."""
    text = str(cond or "").strip()
    if not text:
        return True
    if text == "always()":
        return True
    m = re.fullmatch(r"steps\.([\w-]+)\.outputs\.([\w-]+) == '([^']*)'", text)
    if m:
        return str(_lookup(f"steps.{m.group(1)}.outputs.{m.group(2)}", ctx)
                   or "") == m.group(3)
    m = re.fullmatch(r"hashFiles\('([^']+)'\) != ''", text)
    if m:
        return bool(list(work.glob(m.group(1))))
    raise Unreadable(f"cannot decide the step condition {text!r}")


def _paths_of(spec: Any) -> list[str]:
    return [line.strip() for line in str(spec or "").splitlines() if line.strip()]


def _common_root(files: list[Path]) -> Path:
    """What `actions/upload-artifact` makes the artifact's root: the least
    common ancestor of every file it matched.

    One directory given and its contents land flat. Two paths with only
    the repository root in common and every directory between is kept -
    which is how `assets/rt/target/package/...` happened, and how
    `gh release create assets/*` was handed a directory (9.0.0-alpha.3).
    """
    if not files:
        return Path(".")
    parts = [f.parent.parts for f in files]
    common: list[str] = []
    for i in range(min(len(p) for p in parts)):
        if len({p[i] for p in parts}) != 1:
            break
        common.append(parts[0][i])
    return Path(*common) if common else Path(".")


def _upload(step: dict[str, Any], ctx: dict[str, Any], work: Path,
            artifacts: dict[str, dict[str, bytes]]) -> None:
    with_ = {k: expand(v, ctx) for k, v in (step.get("with") or {}).items()}
    name = with_.get("name") or "artifact"
    found: list[Path] = []
    for pattern in _paths_of(with_.get("path")):
        matched = [p for p in work.glob(pattern) if p.is_file()]
        if not matched and (work / pattern).is_dir():
            matched = [p for p in (work / pattern).rglob("*") if p.is_file()]
        found += matched
    found = sorted({p.resolve() for p in found})
    if not found and str(with_.get("if-no-files-found")) == "error":
        raise Injected(f"upload-artifact {name}: no files matched "
                       f"{_paths_of(with_.get('path'))}")
    rel = [p.relative_to(work.resolve()) for p in found]
    root = _common_root(rel)
    artifacts[name] = {slashed(r.relative_to(root)): p.read_bytes()
                       for r, p in zip(rel, found)}


def _download(step: dict[str, Any], ctx: dict[str, Any], work: Path,
              artifacts: dict[str, dict[str, bytes]]) -> None:
    with_ = {k: expand(v, ctx) for k, v in (step.get("with") or {}).items()}
    into = work / (with_.get("path") or ".")
    names = ([with_["name"]] if with_.get("name")
             else sorted(n for n in artifacts
                         if fnmatch.fnmatch(n, with_.get("pattern", "*"))))
    if with_.get("name") and with_["name"] not in artifacts:
        raise Injected(f"download-artifact: no artifact named "
                       f"{with_['name']!r}; there are "
                       f"{sorted(artifacts) or 'none'}")
    for name in names:
        for rel, data in artifacts[name].items():
            target = into / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def _sigstore_sign(step: dict[str, Any], ctx: dict[str, Any],
                   work: Path) -> None:
    with_ = {k: expand(v, ctx) for k, v in (step.get("with") or {}).items()}
    signed = 0
    for pattern in _paths_of(with_.get("inputs")):
        for path in work.glob(pattern.lstrip("./")):
            if path.is_file():
                path.with_name(path.name + ".sigstore.json").write_text(
                    json.dumps({"blob": path.name}), encoding="utf-8")
                signed += 1
    if not signed:
        raise Injected("gh-action-sigstore-python: nothing matched "
                       f"{_paths_of(with_.get('inputs'))}")


class Injected(Exception):
    """A stand-in refusing the way the real thing refuses."""


def _uses(step: dict[str, Any], ctx: dict[str, Any], work: Path,
          artifacts: dict[str, dict[str, bytes]],
          fake: Path) -> dict[str, str]:
    """What a `uses:` step leaves behind, and its outputs."""
    action = str(step["uses"]).split("@")[0]
    with_ = {k: expand(v, ctx) for k, v in (step.get("with") or {}).items()}
    if action == "actions/checkout":
        if with_.get("repository") and with_.get("path"):
            (work / with_["path"]).mkdir(parents=True, exist_ok=True)
            (work / with_["path"] / "tests").mkdir(exist_ok=True)
        return {}
    if action in ("actions/setup-python", "actions/setup-node",
                  "dtolnay/rust-toolchain", "Swatinem/rust-cache",
                  "sigstore/cosign-installer", "open-policy-agent/setup-opa"):
        return {}
    if action == "actions/upload-artifact":
        _upload(step, ctx, work, artifacts)
        return {}
    if action == "actions/download-artifact":
        _download(step, ctx, work, artifacts)
        return {}
    if action == "sigstore/gh-action-sigstore-python":
        _sigstore_sign(step, ctx, work)
        return {}
    if action == "pypa/gh-action-pypi-publish":
        wheels = list((work / "dist").glob("*.whl")) if (work / "dist").is_dir() \
            else []
        if not wheels:
            raise Injected("gh-action-pypi-publish: dist/ holds no wheel")
        (fake / "pypi-published").write_text(
            "\n".join(w.name for w in wheels), encoding="utf-8")
        return {}
    if action == "rust-lang/crates-io-auth-action":
        return {"token": "a-trusted-publishing-token"}
    raise Unreadable(f"no model for the action {action}")


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------

class Fault:
    """One injected fault: a wrong command, a wrong path, a wrong artifact
    name, or a world that answers differently.

    `patch` is applied to every `run:` script of the job - so it is the
    job's own shell that is wrong, which is the thing being tested.
    `rename` renames an artifact before the job downloads it. `env` sets a
    variable a stand-in reads. `drop` deletes a file from the checkout.
    """

    def __init__(self, what: str, *, patch: tuple[str, str] | None = None,
                 rename: tuple[str, str] | None = None,
                 env: dict[str, str] | None = None,
                 drop: str | None = None,
                 write: dict[str, str] | None = None) -> None:
        self.what = what
        self.patch = patch
        self.rename = rename
        self.env = env or {}
        self.drop = drop
        self.write = write or {}


class Scenario:
    """A checkout, a bin/ of stand-ins, and the artifacts jobs pass along.

    One scenario can run several jobs in order, which is how the artifact
    a job uploads becomes the artifact the next one downloads.
    """

    def __init__(self, scratch: Path, base: str, files: dict[str, str],
                 context: dict[str, Any], work: Path | None = None) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="job-", dir=scratch))
        # `work` is a checkout somebody else built - check_release.py's
        # throwaway repositories, which already hold the six version
        # files, a CHANGELOG and tags. Otherwise the files given are the
        # whole of it.
        self.work = Path(work) if work is not None else self.home / "work"
        self.fake = self.home / "bin"
        self.work.mkdir(parents=True, exist_ok=True)
        self.fake.mkdir()
        (self.fake / "calls").mkdir()
        self.artifacts: dict[str, dict[str, bytes]] = {}
        self.context = context
        self.summary = self.home / "summary.md"
        self.summary.write_text("", encoding="utf-8")
        for name, text in files.items():
            target = self.work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        for name, text in STANDINS.items():
            self._put(name, text)
        for name, text in FAKE_SIGSTORE.items():
            target = self.fake / "lib" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        shim = self.home / "python_shim.py"
        shim.write_text(python_shim(base, self.work), encoding="utf-8")
        for name in ("python3", "python"):
            self._put(name, "#!/usr/bin/env bash\nexec "
                            f'"{slashed(Path(sys.executable))}" '
                            f'"{slashed(shim)}" "$@"\n')

    def _put(self, name: str, text: str) -> None:
        path = self.fake / name
        path.write_bytes(text.encode("utf-8"))
        path.chmod(0o755)

    def calls(self, name: str) -> list[list[str]]:
        """Every call of a stand-in, argument by argument."""
        log = self.fake / "calls" / f"{name}.log"
        if not log.exists():
            return []
        return [line.split("\t")[:-1]
                for line in log.read_text(encoding="utf-8").splitlines()]

    def asked(self, name: str, *words: str) -> bool:
        """Was this command ever called with all of these arguments?"""
        return any(set(words) <= set(call) for call in self.calls(name))

    def release_assets(self, tag: str) -> list[str]:
        where = self.fake / "releases" / tag
        return sorted(p.name for p in where.iterdir()) if where.is_dir() else []


def run_job(wf: str, name: str, sc: Scenario, bash: str,
            fault: "Fault | None" = None,
            matrix: dict[str, str] | None = None,
            extra_env: dict[str, str] | None = None) -> dict[str, Any]:
    """One job of a workflow, step by step, in `sc`'s checkout."""
    job = all_jobs()[(wf, name)]
    if fault and fault.rename:
        old, new = fault.rename
        if old not in sc.artifacts:
            raise Unreadable(f"no artifact {old!r} to rename")
        sc.artifacts[new] = sc.artifacts.pop(old)
    for name, text in (fault.write if fault else {}).items():
        target = sc.work / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if fault and fault.drop:
        target = sc.work / fault.drop
        if not target.exists():
            raise Unreadable(f"nothing at {fault.drop!r} to drop")
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

    ctx = dict(sc.context)
    ctx["steps"] = {}
    ctx["matrix"] = matrix or {}
    job_env = {k: expand(v, ctx) for k, v in (job.get("env") or {}).items()}
    carried: dict[str, str] = {}
    steps: dict[str, str] = {}
    log: list[str] = []
    failed = False

    for i, step in enumerate(job.get("steps") or []):
        label = str(step.get("id") or step.get("name") or step.get("uses"))
        if failed or not decides(step.get("if"), ctx, sc.work):
            steps[label] = "skipped"
            continue
        if "uses" in step:
            try:
                out = _uses(step, ctx, sc.work, sc.artifacts, sc.fake)
            except Injected as e:
                steps[label] = "failure"
                log.append(f"--- {label}: the action refused: {e}")
                failed = True
                continue
            steps[label] = "success"
            if step.get("id"):
                ctx["steps"][step["id"]] = {"outputs": out}
            continue

        script = str(step["run"])
        if fault and fault.patch:
            script = script.replace(*fault.patch)
        script = expand(script, ctx)
        # 900 seconds of asking a registry is 0.3 here: the step still
        # asks, still gives up, and still fails when the answer never
        # comes - which is what a case about a version that was never
        # published needs it to do.
        script = re.sub(r"--timeout \d+", "--timeout 0.3", script)
        script = re.sub(r"--interval \d+", "--interval 0.05", script)
        where = sc.work / str(step.get("working-directory", "."))
        where.mkdir(parents=True, exist_ok=True)
        (sc.home / f"step-{i}.sh").write_bytes(script.encode("utf-8"))
        runner = sc.home / f"run-{i}.sh"
        runner.write_bytes((
            "fakebin=$FAKE\n"
            "if command -v cygpath > /dev/null; then "
            'fakebin=$(cygpath -u "$FAKE"); fi\n'
            'export PATH="$fakebin:$PATH"\n'
            f'. "{slashed(sc.home / f"step-{i}.sh")}"\n').encode("utf-8"))
        out_file = sc.home / f"output-{i}"
        env_file = sc.home / f"env-{i}"
        out_file.write_text("", encoding="utf-8")
        env_file.write_text("", encoding="utf-8")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.update(job_env)
        env.update(carried)
        env.update({k: expand(v, ctx)
                    for k, v in (step.get("env") or {}).items()})
        env.update({"FAKE": slashed(sc.fake),
                    "GITHUB_OUTPUT": slashed(out_file),
                    "GITHUB_ENV": slashed(env_file),
                    "GITHUB_STEP_SUMMARY": slashed(sc.summary),
                    "GITHUB_REPOSITORY": str(
                        _lookup("github.repository", ctx) or ""),
                    "GITHUB_REF": str(_lookup("github.ref", ctx) or ""),
                    "GITHUB_EVENT_NAME": str(
                        _lookup("github.event_name", ctx) or "")})
        env.update(extra_env or {})
        if fault:
            env.update(fault.env)
        done = subprocess.run(
            [bash, "--noprofile", "--norc", "-eo", "pipefail",
             slashed(runner)],
            cwd=str(where), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900)
        log.append(f"--- {label}: exit {done.returncode}\n"
                   + done.stdout + done.stderr)
        got = dict(line.split("=", 1) for line in
                   out_file.read_text(encoding="utf-8").splitlines()
                   if "=" in line)
        if step.get("id"):
            ctx["steps"][step["id"]] = {"outputs": got}
        carried.update(dict(
            line.split("=", 1) for line in
            env_file.read_text(encoding="utf-8").splitlines() if "=" in line))
        steps[label] = "success" if done.returncode == 0 else "failure"
        if done.returncode != 0 and not step.get("continue-on-error"):
            failed = True

    return {"result": "failure" if failed else "success", "steps": steps,
            "outputs": ctx["steps"], "log": "\n".join(log),
            "summary": sc.summary.read_text(encoding="utf-8")}


# ---------------------------------------------------------------------------
# The standing rule, enforced mechanically
# ---------------------------------------------------------------------------

# Every job of release.yml and publish-crate.yml, and the harness that
# runs its own shell. A job added to either workflow without a harness
# fails `coverage()` below, which is what makes this a rule rather than
# a habit. There is no exemption list, by design: a job with no harness
# is a job whose only test is somebody reading it, and reading it is
# what missed three defects in a row.
#
# The value is the name of the case function in check_release.py that
# runs the job's shell. `coverage()` does not call it - it checks that
# the map and the workflows agree - and `cases()` there runs every one.
HARNESSED: dict[tuple[str, str], str] = {
    ("release.yml", "gate"): "harness_gate",
    ("release.yml", "dist"): "harness_dist",
    ("release.yml", "reproducible"): "harness_reproducible",
    ("release.yml", "bundle"): "harness_bundle",
    ("release.yml", "binaries"): "harness_binaries",
    ("release.yml", "attestation"): "harness_attestation",
    ("release.yml", "perf"): "harness_perf",
    ("release.yml", "differential"): "harness_differential",
    ("release.yml", "crate"): "harness_crate",
    ("release.yml", "paused"): "harness_paused",
    ("release.yml", "tag"): "harness_tag",
    ("release.yml", "crates_io"): "harness_crates_io",
    ("release.yml", "prerelease_github"): "harness_prerelease_github",
    ("release.yml", "pypi"): "harness_pypi",
    ("release.yml", "npm"): "harness_npm",
    ("release.yml", "vscode"): "harness_vscode",
    ("release.yml", "github_release"): "harness_github_release",
    ("release.yml", "mcp_registry"): "harness_mcp_registry",
    ("release.yml", "attach_attestation"): "harness_attach_attestation",
    ("release.yml", "consistency"): "harness_consistency",
    ("release.yml", "advisory"): "harness_advisory",
    ("release.yml", "move_pins"): "harness_move_pins",
    ("publish-crate.yml", "publish"): "harness_publish_crate",
}


def coverage(jobs: set[tuple[str, str]] | None = None,
             harnessed: dict[tuple[str, str], str] | None = None) -> list[str]:
    """What is wrong with the map, one line each; empty when it is right.

    Three ways it can be wrong, and the first is the rule:

    - a job in either workflow that no harness names. That is a job
      whose shell has never been run outside a release;
    - a harness that names a job neither workflow has, which is a
      harness left behind by a job that was renamed or removed;
    - two jobs sharing one harness function, which would let one of them
      be tested and the other only look tested.
    """
    jobs = set(all_jobs()) if jobs is None else set(jobs)
    HARNESSED_ = HARNESSED if harnessed is None else harnessed
    wrong = []
    for key in sorted(jobs - set(HARNESSED_)):
        wrong.append(f"{key[0]}'s job {key[1]} has no harness: its shell is "
                     f"run by nothing but a release (RELEASING.md)")
    for key in sorted(set(HARNESSED_) - jobs):
        wrong.append(f"HARNESSED names {key[0]}'s job {key[1]}, which that "
                     f"workflow does not have")
    seen: dict[str, tuple[str, str]] = {}
    for key, fn in sorted(HARNESSED_.items()):
        if fn in seen:
            wrong.append(f"{fn} is named for both {seen[fn][1]} and "
                         f"{key[1]}; one harness cannot test two jobs")
        seen[fn] = key
    return wrong


def has_shell(wf: str, name: str) -> bool:
    """Does this job have any `run:` at all? A job that is only `uses:`
    steps has no shell of its own, and its harness is about what those
    actions leave behind."""
    job = all_jobs()[(wf, name)]
    return any(s.get("run") for s in (job.get("steps") or []))
