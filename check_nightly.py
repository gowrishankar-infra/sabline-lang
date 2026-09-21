#!/usr/bin/env python3
"""nightly.yml's probes, each run against a local install, on every push.

The first scheduled nightly run (34943901949, 2026-09-15) failed nine jobs,
and not one because an install was broken. check_install.py made the word
`sabline` absolute in `python -m sabline` and `sabline lsp`, since the
checkout it ran from holds sabline/, and it stopped with a traceback when
the pre-commit job's glob found nothing. Nothing ran a probe before a night
went by. This runs every line of nightly.yml that calls check_install.py:

- this checkout is installed into a new virtual environment (pip, with no
  dependencies; the running Python's own packages sit beside it, for the
  prover and the native backend where they are installed). pip fetches the
  build backend; nothing else here uses the network;
- each line runs in bash, as its job runs it, from a directory shaped like
  a checkout: a placeholder for every name at this checkout's top level,
  with check_install.py, examples/discount.vel and sabline/version.py
  copied in. What a job's earlier steps leave behind stands in: venv/ for
  $BIN, dist/sabline for the standalone executable, artefacts/ and bundle/
  from build_mcpb.py, an npm root holding npm/ for `npm root -g`, two hook
  environments under $RUNNER_TEMP/pre-commit, and on PATH a docker that
  runs the install in place of the image;
- `${{ matrix.* }}` takes each leg's values, on the legs of this system (a
  job that runs on ubuntu-latest alone runs on Linux); a variable, command
  or expression with no stand-in here fails, naming it;
- each line must exit 0 having checked something, and every job but the
  build and the report must hold one.

Then what check_install.py says with nothing to run - a program not on
PATH, a path that is not a file, a glob that matches nothing, a file that
is not a program, an empty command: exit 1, a BROKEN line naming what was
looked for and where, and no traceback.

    python check_nightly.py
"""
from __future__ import annotations

import contextlib
import io
import itertools
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_mcpb  # noqa: E402
from check_release import posix_bash  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORKFLOW = HERE / ".github" / "workflows" / "nightly.yml"
WORK = isolate("check_nightly")
WINDOWS = os.name == "nt"
SYSTEM = "windows" if WINDOWS else "macos" if sys.platform == "darwin" else "linux"
RUNNERS = {"ubuntu": "linux", "windows": "windows", "macos": "macos"}
# the jobs that hold no probe, and why
NO_PROBE = {"build": "builds what the other jobs install",
            "report": "opens and closes the issues"}
# what a probe line may name that its job provides and this stands in for
VARIABLES = {"BIN", "EXE", "RUNNER_TEMP", "GITHUB_WORKSPACE"}
COMMANDS = {"npm"}
NOWHERE = "sabline-is-installed-nowhere"
# docker run --rm -v HOST:INSIDE IMAGE WORDS..., as check_install.py sends
# it: the install runs WORDS, with INSIDE read as HOST
FAKE_DOCKER = """
import subprocess, sys
args = sys.argv[1:]
if args[:3] != ["run", "--rm", "-v"] or len(args) < 5:
    sys.exit("the stand-in docker takes what check_install.py sends, not %r" % args)
host, _, inside = args[3].rpartition(":")
words = [host + w[len(inside):] if w.startswith(inside + "/") else w
         for w in args[5:]]
sys.exit(subprocess.run([SABLINE, *words]).returncode)
"""
PASS = FAIL = 0


def ok(label: str, good: object, detail: str = "") -> None:
    global PASS, FAIL
    if good:
        PASS += 1
        print(f"  ok      {label}")
    else:
        FAIL += 1
        print(f"  BROKEN  {label}")
        if detail:
            print("          " + detail.strip()[-2500:].replace("\n", "\n          "))


def finish() -> int:
    print("-" * 62)
    print(f"{PASS} correct, {FAIL} wrong")
    return 1 if FAIL else 0


def slashed(path: Path) -> str:
    return str(path).replace("\\", "/")


def legs(job: dict[str, Any]) -> list[dict[str, str]]:
    """A job's matrix legs, [{}] without one. A matrix that both lists
    values and includes or excludes legs is refused: nightly.yml has none,
    and GitHub's way of merging them is not modelled here."""
    matrix = dict((job.get("strategy") or {}).get("matrix") or {})
    include = matrix.pop("include", None) or []
    if matrix.pop("exclude", None) or (matrix and include):
        raise ValueError(f"{job.get('name')}: a matrix this cannot expand")
    if include:
        return [{k: str(v) for k, v in leg.items()} for leg in include]
    keys = list(matrix)
    return [dict(zip(keys, (str(v) for v in values)))
            for values in itertools.product(*(matrix[k] for k in keys))]


def expand(text: str, leg: dict[str, str]) -> str:
    return re.sub(r"\$\{\{\s*matrix\.(\w+)\s*\}\}",
                  lambda m: leg.get(m.group(1), m.group(0)), text)


def probes(doc: dict[str, Any]) -> tuple[list[dict[str, str]], set[str]]:
    """Every line calling check_install.py, once per leg, and the jobs that
    hold one."""
    found: list[dict[str, str]] = []
    holding: set[str] = set()
    for key, job in doc["jobs"].items():
        lines = [line.strip() for step in job.get("steps") or []
                 for line in str(step.get("run", "")).splitlines()
                 if "check_install.py" in line]
        if not lines:
            continue
        holding.add(key)
        for leg in legs(job):
            runs_on = expand(str(job.get("runs-on", "")), leg)
            for line in lines:
                found.append({"job": key,
                              "name": expand(str(job.get("name", key)), leg),
                              "system": RUNNERS.get(runs_on.split("-")[0], runs_on),
                              "line": expand(line, leg)})
    return found, holding


def unknown(line: str) -> list[str]:
    """What a probe line names that nothing here stands in for."""
    return ([f"${n}" for n in re.findall(r"\$\{?([A-Za-z_]\w*)", line)
             if n not in VARIABLES]
            + [f"$({c} ...)" for c in re.findall(r"\$\(\s*([\w.-]+)", line)
               if c not in COMMANDS]
            + re.findall(r"\$\{\{[^}]*\}\}", line))


def shaped(root: Path) -> Path:
    """A directory shaped like this checkout's top level - sabline/ among
    it, which is what nightly #1 tripped over - holding the files
    check_install.py reads."""
    checkout = root / "checkout"
    checkout.mkdir()
    for entry in HERE.iterdir():
        if entry.name == ".git":
            continue
        if entry.is_dir():
            (checkout / entry.name).mkdir()
        else:
            (checkout / entry.name).touch()
    for rel in ("check_install.py", "examples/discount.vel", "sabline/version.py"):
        shutil.copy2(HERE / rel, checkout / rel)
    return checkout


def install(checkout: Path) -> Path:
    """This checkout, installed into checkout/venv as pip installs it: the
    directory holding the environment's python and sabline."""
    venv = checkout / "venv"
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)],
                   check=True, capture_output=True, text=True)
    bin_dir = venv / ("Scripts" if WINDOWS else "bin")
    python = bin_dir / ("python.exe" if WINDOWS else "python")
    done = subprocess.run(
        [sys.executable, "-m", "pip", "--python", str(python), "install",
         "--no-deps", "--quiet", "--disable-pip-version-check", str(HERE)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise RuntimeError("pip could not install this checkout into a new "
                           f"virtual environment:\n{done.stdout}{done.stderr}")
    purelib = subprocess.run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
        check=True, capture_output=True, text=True).stdout.strip()
    # after the install, so that pip saw an empty environment: the prover
    # and the native backend, where the running Python has them, as the
    # nightly installs [full]
    beside = dict.fromkeys(sysconfig.get_path(p) for p in ("purelib", "platlib"))
    Path(purelib, "running_python.pth").write_text("\n".join(beside) + "\n",
                                                   encoding="utf-8")
    return bin_dir


def stand_ins(checkout: Path, bin_dir: Path) -> dict[str, str]:
    """What the jobs' earlier steps leave behind, and the environment a
    probe line runs in."""
    exe = ".exe" if WINDOWS else ""
    sabline = bin_dir / f"sabline{exe}"
    # the standalone executable, where pyinstaller leaves one
    (checkout / "dist").mkdir(exist_ok=True)
    shutil.copy2(sabline, checkout / "dist" / f"sabline{exe}")
    # the MCP bundle, built as the build job builds it and unpacked as the
    # bundle's job unpacks it
    build_mcpb.OUT = checkout / "artefacts" / "sabline.mcpb"
    build_mcpb.STAGE = WORK / "_mcpb_build"
    build_mcpb.OUT.parent.mkdir(exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        build_mcpb.main()
    with zipfile.ZipFile(build_mcpb.OUT) as bundle:
        bundle.extractall(checkout / "bundle")
    # npm install -g sabline-lang: the package as npm/ holds it
    npm_root = WORK / "npm-root"
    shutil.copytree(HERE / "npm", npm_root / "sabline-lang")
    # the two hook environments pre-commit makes, sabline-check's and
    # sabline-fmt's
    runner_temp = WORK / "runner-temp"
    for repo in ("repo1check", "repo2fmt"):
        hook_bin = runner_temp / "pre-commit" / repo / "py_env-python3" / "bin"
        hook_bin.mkdir(parents=True)
        shutil.copy2(sabline, hook_bin / "sabline")
    fake = WORK / "fake-bin"
    fake.mkdir()
    (fake / "npm").write_bytes((
        '#!/usr/bin/env bash\n'
        f'if [ "$*" = "root -g" ]; then echo "{slashed(npm_root)}"; exit 0; fi\n'
        'echo "the stand-in npm answers root -g, not: $*" >&2\n'
        'exit 2\n').encode("utf-8"))
    (fake / "docker.py").write_text(f"SABLINE = {str(sabline)!r}\n" + FAKE_DOCKER,
                                    encoding="utf-8")
    (fake / "docker").write_bytes((
        f'#!/usr/bin/env bash\nexec "{slashed(Path(sys.executable))}" '
        f'"{slashed(fake / "docker.py")}" "$@"\n').encode("utf-8"))
    for name in ("npm", "docker"):
        (fake / name).chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in (
        "GITHUB_ACTIONS", "PYTHONPATH", "VIRTUAL_ENV", "PRE_COMMIT_HOME")}
    env.update(BIN=f"venv/{bin_dir.name}", EXE=exe,
               RUNNER_TEMP=slashed(runner_temp), GITHUB_WORKSPACE=slashed(checkout),
               PROBE_BIN=str(bin_dir), FAKE_BIN=str(fake))
    return env


def run_line(line: str, checkout: Path, env: dict[str, str], bash: str,
             i: int) -> tuple[int, str]:
    """A probe line in bash, from the checkout-shaped directory, with the
    install and the stand-ins first on PATH (Git's bash puts its own first
    when it starts, so they go on inside the script)."""
    script = WORK / f"probe-{i}.sh"
    script.write_bytes((
        'bin=$PROBE_BIN; fake=$FAKE_BIN\n'
        'if command -v cygpath > /dev/null; then '
        'bin=$(cygpath -u "$bin"); fake=$(cygpath -u "$fake"); fi\n'
        'export PATH="$bin:$fake:$PATH"\n' + line + "\n").encode("utf-8"))
    try:
        done = subprocess.run(
            [bash, "--noprofile", "--norc", "-eo", "pipefail", slashed(script)],
            cwd=checkout, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=900)
    except subprocess.TimeoutExpired:
        return -1, "still running after 900 s"
    return done.returncode, done.stdout + done.stderr


def main() -> int:
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    print("nightly.yml's probe lines")
    print("-" * 62)
    try:
        every, holding = probes(doc)
    except ValueError as e:
        ok("every matrix in nightly.yml is one this can expand", False, str(e))
        return finish()
    lacking = sorted(set(doc["jobs"]) - holding - set(NO_PROBE))
    ok("every job but the build and the report holds a line calling "
       "check_install.py", not lacking, f"none in: {lacking}")
    strange = {p["line"]: unknown(p["line"]) for p in every if unknown(p["line"])}
    ok("...and each line names nothing this has no stand-in for ("
       + ", ".join(f"${v}" for v in sorted(VARIABLES))
       + ", $(npm ...), the matrix)", not strange, str(strange))
    bash = posix_bash()
    if bash is None:
        ok("a POSIX bash to run them in, as their jobs do (Git's, on Windows)",
           False)
        return finish()

    print()
    print(f"each line of a job that runs on {SYSTEM}, against this checkout "
          f"installed")
    print("-" * 62)
    checkout = shaped(WORK)
    try:
        bin_dir = install(checkout)
        env = stand_ins(checkout, bin_dir)
    except (OSError, RuntimeError, subprocess.SubprocessError) as e:
        ok("this checkout installs into a new virtual environment, and the "
           "stand-ins are made", False, f"{e}\n{getattr(e, 'stderr', '') or ''}")
        return finish()
    ok("the directory the lines run from holds sabline/, as the checkout "
       "nightly #1 ran them from did", (checkout / "sabline").is_dir())
    seen: set[tuple[str, str, str]] = set()
    elsewhere: dict[str, int] = {}
    ran = 0
    for i, probe in enumerate(every):
        command = re.sub(r'^python check_install\.py --name "[^"]*" ', "",
                         probe["line"])
        if (probe["job"], probe["system"], command) in seen:
            continue
        seen.add((probe["job"], probe["system"], command))
        if probe["system"] != SYSTEM:
            elsewhere[probe["system"]] = elsewhere.get(probe["system"], 0) + 1
            continue
        if '"node ' in probe["line"] and shutil.which("node") is None:
            print(f"  skip    {probe['name']}: {command} (no node here)")
            continue
        code, out = run_line(probe["line"], checkout, env, bash, i)
        counted = re.search(r": (\d+) correct, (\d+) wrong\s*$", out)
        ran += 1
        ok(f"{probe['name']}: {command}",
           code == 0 and counted is not None and int(counted.group(1)) >= 3
           and counted.group(2) == "0" and "Traceback" not in out,
           f"exit {code}:\n{out}")
    ok(f"...{ran} line(s) ran here", ran > 0)
    for system, count in sorted(elsewhere.items()):
        print(f"  skip    {count} line(s) of jobs that run on {system}")

    print()
    print("check_install.py with nothing to run: exit 1, and no traceback")
    print("-" * 62)
    hooks = env["RUNNER_TEMP"] + "/pre-commit"
    for label, words, said in (
            ("a program not on PATH", ["--command", NOWHERE],
             [f"{NOWHERE} is not on PATH, which is these"]),
            ("a path that is not a file", ["--command", "venv/nowhere/python -m sabline"],
             ["venv/nowhere/python is not there: no file", "pyvenv.cfg"]),
            ("a glob that matches nothing",
             ["--find", f"{hooks}/repo*/py_env-*/bin/{NOWHERE}"],
             ["no file matches", NOWHERE, "holds sabline"]),
            ("a glob whose first directory is not there",
             ["--find", f"{env['RUNNER_TEMP']}/pre-commit-nowhere/repo*/bin/sabline"],
             ["no file matches", "holds pre-commit"]),
            ("a file that is not a program", ["--command", "examples/discount.vel"],
             ["could not be started"]),
            ("an empty command", ["--command", ""], ["the command is empty"]),
            ("a language server not on PATH", ["--lsp", f"{NOWHERE} lsp"],
             [f"{NOWHERE} is not on PATH"]),
            ("an MCP server whose python is not there",
             ["--mcp", "venv/nowhere/python server.py"],
             ["venv/nowhere/python is not there: no file"])):
        done = subprocess.run(
            [sys.executable, "check_install.py", "--name", label, *words],
            cwd=checkout, env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600)
        out = done.stdout + done.stderr
        ok(f"{label}: a BROKEN line naming what was looked for and where",
           done.returncode == 1 and "BROKEN" in out and "Traceback" not in out
           and all(s in out for s in said), f"exit {done.returncode}:\n{out}")
    return finish()


if __name__ == "__main__":
    sys.exit(main())
