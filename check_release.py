#!/usr/bin/env python3
"""The release gate, and the rest of release_checks.py, held to fixtures.

release.yml makes a release only when `release_checks.py gate` says the
commit it was handed is one, and it runs this suite first, in the same
job. The gate cases build throwaway git repositories shaped like this
one - the six version files, a CHANGELOG, tags - and ask the question a
push to main asks:

- a docs-only commit is not a release;
- a version bump without a CHANGELOG entry is not a release, and the
  notice names the entry that is missing;
- a correct bump is a release.

Then what else the gate refuses (files that disagree, a version that is
not newer than the newest tag, "7.2" standing in for 7.2.1, a registry
manifest without both packages, a commit the tests did not pass on); what
STABILITY.md covers that a minor or patch release must explain with a
`compatibility:` line - an error code added, a flag removed, a default
changed - and an API golden that moved without an `api:` line (8.2); the
release notes, the advisory detection and the draft-advisory request; the
publish, registry and consistency checks against a stand-in for PyPI,
npm, the MCP registry, the Marketplace and GitHub; RELEASE_PAUSED; and
release.yml itself, run job by job against the stand-in, with a publish
that fails midway and the re-run that finishes it (8.2). From 8.2.1:
`published --require`, which ends a publish; the vscode job's own steps,
run in bash with stand-ins for vsce, npm and sleep, which must leave the
job red whenever the Marketplace does not list the version at its end;
and the perf gate's medians of three runs a side. Nothing here leaves
127.0.0.1.

    python check_release.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
CHECKS = HERE / "release_checks.py"
sys.path.insert(0, str(HERE))
import release_checks  # noqa: E402

from suite_dirs import isolate  # noqa: E402

SCRATCH = isolate("check_release")
SERVER = release_checks.SERVER
REPOSITORY = release_checks.REPOSITORY

# the 24 files the v7.1.2 release holds, as GitHub listed them
V712_ASSETS = """SHA256SUMS
sabline-attestation-7.1.2.cosign.sigstore.json
sabline-attestation-7.1.2.intoto.json
sabline-attestation-7.1.2.sigstore-python.sigstore.json
sabline-lang-7.1.2.cdx.json
sabline-lang-7.1.2.cdx.json.sigstore.json
sabline-linux
sabline-linux.sha256
sabline-linux.sigstore.json
sabline-macos
sabline-macos.sha256
sabline-macos.sigstore.json
sabline-mcp-tools-7.1.2.json
sabline-mcp-tools-7.1.2.json.sigstore.json
sabline-windows.exe
sabline-windows.exe.sha256
sabline-windows.exe.sigstore.json
sabline.mcpb
sabline.mcpb.sha256
sabline.mcpb.sigstore.json
sabline_lang-7.1.2-py3-none-any.whl
sabline_lang-7.1.2-py3-none-any.whl.sigstore.json
sabline_lang-7.1.2.tar.gz
sabline_lang-7.1.2.tar.gz.sigstore.json""".split()


# ---- throwaway repositories ----------------------------------------------------

def git(repo: Path, *words: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Release Check",
         "-c", "user.email=release-check@example.invalid",
         "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *words],
        capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(words)}: {done.stderr}")
    return done.stdout.strip()


# What a stand-in compiler holds for the gate to compare across a release:
# its error table, the flags it knows, its defaults.
BASE_CODES = ("E000", "E100", "E300")
BASE_FLAGS = ("--allow", "--json", "--no-native")
BASE_DEFAULTS = {"CHECK_TIMEOUT_DEFAULT": "60", "DEFAULT_ALLOW": '"io"'}


def write_versions(repo: Path, version: str, overrides: dict[Any, Any] | None = None,
                   *, layout: str = "package", codes: Any = BASE_CODES,
                   flags: Any = BASE_FLAGS, defaults: dict[Any, Any] | None = None,
                   golden: dict[Any, Any] | None = None) -> None:
    """The six version files, each saying `version` unless `overrides`
    names another for it ("compiler" for the compiler's own);
    overrides["packages"] lists the registry manifest's package types. The
    compiler is sabline/ as from 8.2, or sabline.py as before
    (layout="file"), holding `codes`, `flags` and `defaults`."""
    said: dict[str, str] = dict(overrides or {})

    def at(name: str) -> str:
        return said.get(name, version)
    reg = at("integrations/mcp_registry/server.json")
    table = ("ERROR_TABLE = {\n"
             + "".join(f'    "{c}": "what {c} means",\n' for c in codes)
             + "}\n")
    known = ("FLAGS = (" + ", ".join(f'"{f}"' for f in flags) + ",)\n"
             + "".join(f"{k} = {v}\n"
                       for k, v in (defaults or BASE_DEFAULTS).items()))
    files = {
        "pyproject.toml": f'[project]\nname = "sabline-lang"\n'
                          f'version = "{at("pyproject.toml")}"\n',
        "npm/package.json": json.dumps(
            {"name": "sabline-lang", "version": at("npm/package.json")}),
        "mcpb/manifest.json": json.dumps(
            {"name": "sabline", "version": at("mcpb/manifest.json")}),
        "editor/vscode/package.json": json.dumps(
            {"name": "sabline", "version": at("editor/vscode/package.json")}),
        "integrations/mcp_registry/server.json": json.dumps({
            "name": SERVER, "version": reg,
            "packages": [{"registryType": kind, "identifier": "sabline-lang",
                          "version": reg}
                         for kind in said.get("packages", "pypi,npm")
                         .split(",") if kind]}),
    }
    if layout == "package":
        shutil.rmtree(repo / "sabline.py", ignore_errors=True)
        if (repo / "sabline.py").exists():
            (repo / "sabline.py").unlink()
        files["sabline/version.py"] = f'VERSION = "{at("compiler")}"\n'
        files["sabline/errors.py"] = table
        files["sabline/cli.py"] = known
    else:
        shutil.rmtree(repo / "sabline", ignore_errors=True)
        files["sabline.py"] = (f'"""A stand-in."""\n'
                               f'VERSION = "{at("compiler")}"\n'
                               + table + known)
    if golden is not None:
        files["tests/api/golden.json"] = json.dumps(golden)
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


def write_crate(repo: Path, version: str) -> None:
    """rt/Cargo.toml, whose version is what a pre-release publishes.

    It is the one place a `9.0.0-alpha.N` is written: the Python package's
    six version files stay on the release users get, because an alpha
    publishes the crate and nothing else (plan/9.0.md, alpha.1).
    """
    path = repo / "rt" / "Cargo.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[workspace]\n"
        'members = ["crates/sabline-rt"]\n\n'
        "[workspace.package]\n"
        f'version = "{version}"\n', encoding="utf-8")


BASE_ENTRY = ("7.1.2", "The proof cache could be lied to",
              "The proof cache moved to a per-user directory.")


def write_changelog(repo: Path, *entries: tuple[str, str, str]) -> None:
    (repo / "CHANGELOG.md").write_text(
        "# Sabline changelog\n\n" + "".join(
            f"## {v} - {title}\n\n{text}\n\n" for v, title, text in entries),
        encoding="utf-8")


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def base_repo(name: str, extra: dict[Any, Any] | None = None,
              golden: dict[Any, Any] | None = None) -> Path:
    """A repository at 7.1.2: a first commit tagged v2.36 (two parts, as
    the old tags are), then 7.1.2 tagged v7.1.2 - annotated, as today, and
    with the compiler in one file, as it was until 8.2."""
    repo = SCRATCH / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("Sabline\n", encoding="utf-8")
    commit(repo, "the beginning")
    git(repo, "tag", "v2.36")
    write_versions(repo, "7.1.2", layout="file", golden=golden)
    write_changelog(repo, BASE_ENTRY)
    for file, text in (extra or {}).items():
        (repo / file).write_text(text, encoding="utf-8")
    commit(repo, "v7.1.2: the proof cache could be lied to")
    git(repo, "tag", "-a", "v7.1.2", "-m",
        "v7.1.2: the proof cache could be lied to")
    return repo


def cli(*words: str, repo: Path | None = None, env: dict[Any, Any] | None = None) -> tuple[Any, ...]:
    """Run release_checks.py as the workflow does: (exit code, stdout,
    stderr, the step outputs it wrote)."""
    outputs_file = Path(tempfile.mktemp(dir=SCRATCH, suffix=".out"))
    outputs_file.write_text("", encoding="utf-8")
    command = [sys.executable, str(CHECKS), *words,
               "--github-output", str(outputs_file), "--annotate"]
    if repo is not None:
        command += ["--repo", str(repo)]
    done = subprocess.run(command, capture_output=True, text=True,
                          cwd=str(SCRATCH),
                          env=None if env is None else env)
    outputs = dict(line.split("=", 1) for line in
                   outputs_file.read_text(encoding="utf-8").splitlines()
                   if "=" in line)
    return done.returncode, done.stdout, done.stderr, outputs


def in_process(*words: str) -> tuple[int, str]:
    """release_checks.main, in this process, so it asks the stand-in."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = release_checks.main(list(words))
    return code, out.getvalue()


# ---- a stand-in for PyPI, npm, the MCP registry, the Marketplace and GitHub --

class StandIn(BaseHTTPRequestHandler):
    routes: dict[Any, Any] = {}
    posted: list[bytes] = []          # every POST body, in order

    def _answer(self, method: str) -> None:
        answer = self.routes.get((method, self.path.split("?")[0]),
                                 (404, {"detail": "not found"}))
        if isinstance(answer, list):    # answers in turn; the last one stays
            answer = answer.pop(0) if len(answer) > 1 else answer[0]
        if callable(answer):            # an answer that depends on what ran
            answer = answer()
        status, body = answer
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        self._answer("GET")

    def do_POST(self) -> None:
        StandIn.posted.append(
            self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        self._answer("POST")

    def log_message(self, *_: Any) -> None:
        pass


def all_at(version: str) -> dict[Any, Any]:
    """Every target serving `version` as the latest, as a release leaves
    them."""
    server = "/v0.1/servers/" + urllib.parse.quote(SERVER, safe="")
    assets = [{"name": n} for n in release_checks.expected_assets(version)]
    return {
        ("GET", f"/pypi/sabline-lang/{version}/json"): (200, {"info": {
            "version": version,
            "description": f"<!-- mcp-name: {SERVER} -->\n# Sabline"}}),
        ("GET", "/pypi/sabline-lang/json"): (200, {"info": {
            "version": version}}),
        ("GET", f"/sabline-lang/{version}"): (200, {
            "version": version, "mcpName": SERVER}),
        ("GET", "/sabline-lang"): (200, {"dist-tags": {"latest": version}}),
        ("GET", f"{server}/versions/{version}"): (200, {"server": {
            "version": version}}),
        ("GET", f"{server}/versions/latest"): (200, {"server": {
            "version": version}}),
        ("GET", f"/repos/{REPOSITORY}/releases/tags/v{version}"): (200, {
            "tag_name": f"v{version}"}),
        ("GET", f"/repos/{REPOSITORY}/releases/latest"): (200, {
            "tag_name": f"v{version}", "assets": assets}),
        ("POST", "/_apis/public/gallery/extensionquery"): (200, {
            "results": [{"extensions": [{"versions": [
                {"version": version}, {"version": "7.1.2"}]}]}]}),
    }


# ---- release.yml, run job by job against the stand-in -------------------------

class Injected(Exception):
    """A publish made to fail, as an outage would."""


class Unreadable(Exception):
    """A condition in release.yml this simulation cannot decide."""


def release_jobs() -> dict[Any, Any]:
    import yaml
    doc = yaml.safe_load((HERE / ".github" / "workflows" / "release.yml")
                         .read_text(encoding="utf-8"))
    return cast("dict[Any, Any]", doc["jobs"])


def needs_of(job: dict[Any, Any]) -> list[Any]:
    needs = job.get("needs") or []
    return [needs] if isinstance(needs, str) else list(needs)


def descendants(jobs: dict[Any, Any], names: Any) -> set[Any]:
    """`names` and every job that needs one of them, however far down."""
    out = set(names)
    grew = True
    while grew:
        grew = False
        for name, job in jobs.items():
            if name not in out and set(needs_of(job)) & out:
                out.add(name)
                grew = True
    return out


def in_order(jobs: dict[Any, Any]) -> list[Any]:
    done: set[Any] = set()
    order: list[Any] = []
    while len(order) < len(jobs):
        ready = [n for n, j in jobs.items()
                 if n not in done and set(needs_of(j)) <= done]
        if not ready:
            raise Unreadable("release.yml's needs form a cycle")
        for n in sorted(ready):
            done.add(n)
            order.append(n)
    return order


def decides(expr: Any, needs: list[Any], results: dict[Any, Any], outputs: dict[Any, Any]) -> bool:
    """A job's `if:` as GitHub Actions decides it, for the shapes release.yml
    uses: needs.X.result, needs.X.outputs.Y, !=, !cancelled(), always(),
    contains(needs.*.result, '...'), && and ||. A job with no status
    function in its condition also needs every job it needs to have
    succeeded.

    `contains(needs.*.result, 'failure')` is what the tag job asks, because
    from 9.0.0-alpha.1 half the jobs it waits on are skipped rather than
    successful: a pre-release builds the crate and none of the Python
    artefacts, and an ordinary release the other way round. A skipped need
    is not a failed one, and the tag must run in both.
    """
    implicit = all(results.get(n) == "success" for n in needs)
    if not expr:
        return implicit
    text = str(expr).strip()
    if text.startswith("${{") and text.endswith("}}"):
        text = text[3:-2].strip()
    status = "cancelled()" in text or "always()" in text
    text = text.replace("!cancelled()", "True").replace("always()", "True")
    # contains(needs.*.result, 'x'): whether any job this one needs ended x
    text = re.sub(
        r"contains\(needs\.\*\.result, '(\w+)'\)",
        lambda m: str(any(results.get(n) == m.group(1) for n in needs)), text)
    text = re.sub(r"needs\.([\w-]+)\.result == '(\w+)'",
                  lambda m: str(results.get(m.group(1)) == m.group(2)), text)
    text = re.sub(r"needs\.([\w-]+)\.outputs\.([\w-]+) == '([^']*)'",
                  lambda m: str(outputs.get((m.group(1), m.group(2)))
                                == m.group(3)), text)
    text = re.sub(r"needs\.([\w-]+)\.outputs\.([\w-]+) != '([^']*)'",
                  lambda m: str(outputs.get((m.group(1), m.group(2)))
                                != m.group(3)), text)
    text = text.replace("&&", " and ").replace("||", " or ")
    text = re.sub(r"!\s*(True|False)",
                  lambda m: str(not (m.group(1) == "True")), text)
    if re.search(r"[A-Za-z_]\.[A-Za-z_]|[()]\s*[A-Za-z_]+\(", text):
        raise Unreadable(f"cannot decide {expr!r}")
    return bool(eval(text, {"__builtins__": {}}, {})) and (status or implicit)


# the jobs before the tag, which the simulation takes as done: the gate's
# decision and the builds
BEFORE_TAG = {"gate", "dist", "reproducible", "bundle", "binaries",
              "attestation", "paused", "perf", "differential"}


class Release:
    """One version's release, as the stand-in shows it: what is published
    where, how often each publish was made, and the publishes made to fail."""

    def __init__(self, version: str) -> None:
        self.v = version
        self.made: Counter[str] = Counter()
        self.fail: set[Any] = set()
        self.tagged = False
        self.pins_moved = False
        server = "/v0.1/servers/" + urllib.parse.quote(SERVER, safe="")
        self.full = all_at(version)
        self.server = server
        StandIn.routes = {
            ("GET", f"/api/v1/crates/sabline-rt/{version}"): (404, {}),
            ("GET", "/pypi/sabline-lang/json"): (200, {"info": {
                "version": "7.1.2"}}),
            ("GET", "/sabline-lang"): (200, {"dist-tags": {
                "latest": "7.1.2"}}),
            ("GET", f"{server}/versions/latest"): (200, {"server": {
                "version": "7.1.2"}}),
            ("GET", f"/repos/{REPOSITORY}/releases/latest"): (200, {
                "tag_name": "v7.1.2", "assets": []}),
            ("POST", "/_apis/public/gallery/extensionquery"): (200, {
                "results": [{"extensions": [{"versions": [
                    {"version": "7.1.2"}]}]}]}),
        }

    def _serve(self, *keys: Any) -> None:
        for key in keys:
            StandIn.routes[key] = self.full[key]

    def publish(self, target: str) -> None:
        if target in self.fail:
            self.fail.discard(target)
            raise Injected(target)
        self.made[target] += 1
        v, s = self.v, self.server
        if target == "pypi":
            self._serve(("GET", f"/pypi/sabline-lang/{v}/json"),
                        ("GET", "/pypi/sabline-lang/json"))
        elif target == "npm":
            self._serve(("GET", f"/sabline-lang/{v}"), ("GET", "/sabline-lang"))
        elif target == "vscode":
            self._serve(("POST", "/_apis/public/gallery/extensionquery"))
        elif target == "registry":
            self._serve(("GET", f"{s}/versions/{v}"),
                        ("GET", f"{s}/versions/latest"))
        elif target == "crates":
            StandIn.routes[("GET", f"/api/v1/crates/sabline-rt/{v}")] = (
                200, {"version": {"num": v}})

    def release_files(self, attach: bool) -> None:
        """The GitHub release's step: create it with what it lacks, or, for
        the attestation, attach only what is missing."""
        target = "attestation" if attach else "github"
        if target in self.fail:
            self.fail.discard(target)
            raise Injected(target)
        key = ("GET", f"/repos/{REPOSITORY}/releases/latest")
        have = {a["name"] for a in StandIn.routes[key][1].get("assets", [])} \
            if StandIn.routes[key][1].get("tag_name") == f"v{self.v}" else set()
        want = [n for n in release_checks.expected_assets(self.v)
                if attach or not ("attestation" in n or "receipt" in n)]
        missing = [n for n in want if n not in have]
        if not missing:
            return                           # already there: skipped
        self.made[target] += 1
        StandIn.routes[("GET", f"/repos/{REPOSITORY}/releases/tags/"
                        f"v{self.v}")] = self.full[
            ("GET", f"/repos/{REPOSITORY}/releases/tags/v{self.v}")]
        StandIn.routes[key] = (200, {"tag_name": f"v{self.v}", "assets": [
            {"name": n} for n in sorted(have | set(missing))]})


def run_job(name: str, job: dict[Any, Any], release: Release) -> None:
    """What one job of release.yml does, against the stand-in."""
    steps = "\n".join(str(s.get("run", "")) for s in job.get("steps", []))
    asks = re.search(r"release_checks\.py published (\w+)", steps)
    if name == "tag":
        if not release.tagged:
            release.tagged = True
            release.made["tag"] += 1
    elif asks:
        target = asks.group(1)
        if not release_checks.published(target, release.v):
            release.publish(target)
    elif name == "crate":
        release.made["crate-built"] += 1
    elif name == "prerelease_github":
        # `gh release create --prerelease`: a release GitHub does not call
        # the latest one, which is what keeps 8.6.0 what a user gets
        if "--prerelease" not in steps:
            raise Unreadable("the pre-release's GitHub release is not "
                             "created with --prerelease, so it would "
                             "become the latest release")
        release.made["prerelease-github"] += 1
    elif name == "github_release":
        release.release_files(attach=False)
    elif name == "attach_attestation":
        release.release_files(attach=True)
    elif name == "consistency":
        if not all(agrees for _, _, agrees in
                   release_checks.consistency(release.v)):
            raise Injected("consistency")
    elif name == "advisory":
        pass
    elif name == "move_pins":
        if not release.pins_moved:           # else: nothing to push
            release.pins_moved = True
            release.made["pins"] += 1
    else:
        raise Unreadable(f"no simulation for the job {name}")


def attempt(jobs: dict[Any, Any], release: Release, results: dict[Any, Any], outputs: dict[Any, Any],
            only: set[Any] | None = None) -> None:
    """One run of release.yml from the tag on - or, given `only`, the jobs
    a "re-run failed jobs" runs again."""
    for name in in_order(jobs):
        if name in BEFORE_TAG or (only is not None and name not in only):
            continue
        job = jobs[name]
        if not decides(job.get("if"), needs_of(job), results, outputs):
            results[name] = "skipped"
            continue
        try:
            run_job(name, job, release)
            results[name] = "success"
        except Injected:
            results[name] = "failure"


def fresh_results(paused: str = "false") -> tuple[dict[Any, Any], dict[Any, Any]]:
    return ({n: "success" for n in BEFORE_TAG},
            {("gate", "release"): "true", ("gate", "build"): "true",
             ("paused", "paused"): paused})


PUBLISHES = ("tag", "pypi", "npm", "vscode", "github", "registry",
             "attestation", "pins")
# what a pre-release makes instead, and nothing else
PRERELEASE_PUBLISHES = ("tag", "crate-built", "crates",
                        "prerelease-github")


# ---- the vscode job's own steps, in bash, with stand-ins for vsce and npm ----

def posix_bash() -> str | None:
    """A bash for the job's scripts: Git's on Windows, where the first bash
    on PATH can be WSL's, which runs in another file system."""
    if os.name != "nt":
        return shutil.which("bash")
    for base in (os.environ.get("ProgramW6432"), os.environ.get("ProgramFiles"),
                 r"C:\Program Files"):
        candidate = Path(base or "") / "Git" / "bin" / "bash.exe"
        if base and candidate.is_file():
            return str(candidate)
    return None


def _slashed(path: Path) -> str:
    return str(path).replace("\\", "/")


# vsce as the Marketplace answers: one word a publish, from $VSCE_ANSWERS
# (the last word is kept), and `show` naming $V once it has landed
FAKE_VSCE = r"""#!/usr/bin/env bash
if [ "$1" = show ]; then
  if [ -f "$FAKE/landed" ]; then echo "Version: $V"; fi
  exit 0
fi
n=$(( $(cat "$FAKE/attempts" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$FAKE/attempts"
answer=$(echo "$VSCE_ANSWERS" | tr ',' '\n' | sed -n "${n}p")
[ -n "$answer" ] || answer=${VSCE_ANSWERS##*,}
case "$answer" in
  ok) touch "$FAKE/landed"; echo "DONE  Published gowrishankar-infra.sabline v$V." ;;
  timeout) echo " ERROR  Request timeout: /_apis/gallery"; exit 1 ;;
  landed) touch "$FAKE/landed"; echo " ERROR  Request timeout: /_apis/gallery"; exit 1 ;;
  refused) echo " ERROR  Failed request: (401)"; exit 1 ;;
esac
"""
FAKE_NPM = '#!/usr/bin/env bash\necho "npm $*" >> "$FAKE/npm.log"\n'
FAKE_SLEEP = '#!/usr/bin/env bash\necho "$1" >> "$FAKE/sleeps"\n'


def run_vscode_job(job: dict[Any, Any], bash: str, base: str, answers: str,
                   token: str = "a-token", version: str = "7.2.0",
                   already: bool = False) -> dict[str, Any]:
    """The vscode job's steps in order, as a runner takes them, with vsce,
    npm and sleep stood in for and python3 running release_checks.py
    against the stand-in, whose Marketplace lists `version` once the fake
    vsce has landed it (or from the start, `already`). A `uses:` step
    succeeds; `if:` is always() or a steps.<id>.outputs.<key> == '<value>'
    test, and a step without one runs only while no step before it has
    failed; a failed step without continue-on-error fails the job. The
    final step's 900 s of asking is cut to 0.3 s."""
    work = Path(tempfile.mkdtemp(prefix="vscode-job-", dir=SCRATCH))
    fake = work / "bin"
    fake.mkdir()

    def listing() -> tuple[int, dict[str, Any]]:
        versions = [{"version": "7.1.2"}]
        if already or (fake / "landed").exists():
            versions.insert(0, {"version": version})
        return 200, {"results": [{"extensions": [{"versions": versions}]}]}

    StandIn.routes = {("POST", "/_apis/public/gallery/extensionquery"): listing}
    shim = work / "release_checks_shim.py"
    shim.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(HERE)!r})\n"
        "import release_checks\n"
        f"release_checks.ENDPOINTS.update("
        f"{{k: {base!r} for k in release_checks.ENDPOINTS}})\n"
        "release_checks.RETRY_WAIT = 0\n"
        "assert sys.argv[1] == 'release_checks.py', sys.argv\n"
        "sys.exit(release_checks.main(sys.argv[2:]))\n", encoding="utf-8")
    python3 = (f'#!/usr/bin/env bash\nexec "{_slashed(Path(sys.executable))}" '
               f'"{_slashed(shim)}" "$@"\n')
    for name, text in (("vsce", FAKE_VSCE), ("npm", FAKE_NPM),
                       ("sleep", FAKE_SLEEP), ("python3", python3)):
        (fake / name).write_bytes(text.encode("utf-8"))
        (fake / name).chmod(0o755)
    summary = work / "summary.md"
    summary.write_text("", encoding="utf-8")
    outputs: dict[str, dict[str, str]] = {}
    steps: dict[str, str] = {}
    log: list[str] = []
    failed = False

    def value(expr: Any) -> str:
        text = str(expr)
        if re.fullmatch(r"\$\{\{\s*secrets\.VSCE_TOKEN\s*\}\}", text):
            return token
        m = re.fullmatch(r"\$\{\{\s*steps\.([\w-]+)\.outputs\.([\w-]+)\s*\}\}",
                         text)
        if not m:
            raise Unreadable(f"cannot read {text!r} in the vscode job")
        return outputs.get(m.group(1), {}).get(m.group(2), "")

    for i, step in enumerate(job.get("steps", [])):
        name = str(step.get("id") or step.get("name") or step.get("uses"))
        cond = str(step.get("if") or "").strip()
        if cond == "always()":
            runs = True
        elif not cond:
            runs = not failed
        else:
            m = re.fullmatch(r"steps\.([\w-]+)\.outputs\.([\w-]+) == '([^']*)'",
                             cond)
            if not m:
                raise Unreadable(f"cannot decide {cond!r} in the vscode job")
            runs = not failed and outputs.get(m.group(1), {}).get(
                m.group(2)) == m.group(3)
        if not runs:
            steps[name] = "skipped"
            continue
        if "uses" in step:
            steps[name] = "success"
            continue
        script = re.sub(r"--timeout \d+", "--timeout 0.3", str(step["run"]))
        script = re.sub(r"--interval \d+", "--interval 0.05", script)
        where = work / str(step.get("working-directory", "."))
        where.mkdir(parents=True, exist_ok=True)
        (work / f"step-{i}.sh").write_bytes(script.encode("utf-8"))
        runner = work / f"run-{i}.sh"
        runner.write_bytes((
            'fakebin=$FAKE\n'
            'if command -v cygpath > /dev/null; then '
            'fakebin=$(cygpath -u "$FAKE"); fi\n'
            'export PATH="$fakebin:$PATH"\n'
            f'. "{_slashed(work / f"step-{i}.sh")}"\n').encode("utf-8"))
        out_file = work / f"output-{i}"
        out_file.write_text("", encoding="utf-8")
        env = dict(os.environ, V=version, FAKE=_slashed(fake),
                   VSCE_ANSWERS=answers, GITHUB_OUTPUT=_slashed(out_file),
                   GITHUB_STEP_SUMMARY=_slashed(summary))
        env.update({k: value(v) for k, v in (step.get("env") or {}).items()})
        done = subprocess.run(
            [bash, "--noprofile", "--norc", "-eo", "pipefail", _slashed(runner)],
            cwd=str(where), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300)
        log.append(f"--- {name}: exit {done.returncode}\n"
                   + done.stdout + done.stderr)
        outputs[name] = dict(
            line.split("=", 1) for line in
            out_file.read_text(encoding="utf-8").splitlines() if "=" in line)
        steps[name] = "success" if done.returncode == 0 else "failure"
        if done.returncode != 0 and not step.get("continue-on-error"):
            failed = True

    def words(name: str) -> list[str]:
        path = fake / name
        return path.read_text(encoding="utf-8").split() if path.exists() else []

    return {"result": "failure" if failed else "success", "steps": steps,
            "log": "\n".join(log),
            "summary": summary.read_text(encoding="utf-8"),
            "sleeps": words("sleeps"),
            "attempts": int((words("attempts") or ["0"])[0])}


# ---- the move_pins job's own steps, in bash, on a throwaway repository (8.4) ----

FAKE_GH = '#!/usr/bin/env bash\necho "$*" >> "$FAKE/gh.log"\n'


def tracked_files() -> list[str] | None:
    """Every file of this repository git tracks or would (not the ignored
    ones), or None where this is not a git checkout."""
    try:
        done = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"], cwd=HERE, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return [n for n in done.stdout.decode("utf-8").split("\0")
            if n and (HERE / n).is_file()]


class PinFixture:
    """A copy of this repository as a release commit on main of a bare
    origin, tagged as release.yml's tag job tags it, and a checkout of main
    as the move_pins job's checkout step leaves one."""

    def __init__(self, names: list[str]) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="move-pins-", dir=SCRATCH))
        self.origin = self.home / "origin.git"
        self.work = self.home / "work"
        self.fake = self.home / "bin"
        self.fake.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main",
                        str(self.origin)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.work)],
                       check=True, capture_output=True)
        for key, value in (("user.name", "fixture"),
                           ("user.email", "fixture@example.invalid"),
                           ("core.autocrlf", "false"),
                           ("commit.gpgsign", "false"),
                           ("tag.gpgsign", "false")):
            git(self.work, "config", key, value)
        for name in names:
            target = self.work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HERE / name, target)
        # This fixture is about an ordinary release's pin move, so the
        # tree is put in an ordinary release's state: if this checkout's
        # rt/Cargo.toml names a pre-release, the copy's names the release
        # it leads to. A pre-release moves no pin at all, and has fixtures
        # of its own above.
        crate = self.work / release_checks.CRATE_MANIFEST
        if crate.exists():
            said = release_checks.crate_version(self.work) or ""
            if release_checks.prerelease_of(said):
                numbers = release_checks.parse_version(said)
                plain = ".".join(str(n) for n in numbers) if numbers else "1.0.0"
                crate.write_text(
                    crate.read_text(encoding="utf-8").replace(
                        f'version = "{said}"', f'version = "{plain}"', 1),
                    encoding="utf-8")
        # a release commit's documents pin the release before it, whichever
        # this tree's happen to pin
        for doc in release_checks.PIN_DOCS:
            with open(self.work / doc, encoding="utf-8", newline="") as fh:
                text = fh.read()
            with open(self.work / doc, "w", encoding="utf-8",
                      newline="") as fh:
                fh.write(release_checks.moved_pins(text, "v0.0.1", "0" * 40))
        git(self.work, "remote", "add", "origin", str(self.origin))
        git(self.work, "add", "-A")
        git(self.work, "commit", "-q", "-m", "the release commit")
        self.sha = git(self.work, "rev-parse", "HEAD")
        claims = dict(release_checks.version_claims(self.work))
        self.version = str(claims[release_checks.VERSION_FILES[0]])
        self.tag = f"v{self.version}"
        git(self.work, "push", "-q", "origin", "main")
        git(self.work, "tag", "-a", self.tag, "-m", self.tag, self.sha)
        git(self.work, "push", "-q", "origin", f"refs/tags/{self.tag}")

    def main(self) -> str:
        return git(self.origin, "rev-parse", "refs/heads/main")

    def tags(self) -> str:
        return git(self.origin, "show-ref", "--tags", "-d")

    def gh_log(self) -> list[str]:
        log = self.fake / "gh.log"
        return log.read_text(encoding="utf-8").splitlines() \
            if log.exists() else []

    def someone_pushes(self) -> str:
        """A commit lands on main after the release commit, from elsewhere."""
        other = self.home / "other"
        subprocess.run(["git", "clone", "-q", str(self.origin), str(other)],
                       check=True, capture_output=True)
        for key, value in (("user.name", "someone"),
                           ("user.email", "someone@example.invalid"),
                           ("core.autocrlf", "false"),
                           ("commit.gpgsign", "false")):
            git(other, "config", key, value)
        (other / "NOTES.txt").write_text("pushed while the release ran\n",
                                         encoding="utf-8")
        git(other, "add", "NOTES.txt")
        git(other, "commit", "-q", "-m", "a commit after the release commit")
        git(other, "push", "-q", "origin", "main")
        return git(other, "rev-parse", "HEAD")


def run_move_pins_job(job: dict[Any, Any], bash: str,
                      fixture: PinFixture) -> dict[str, Any]:
    """The move_pins job's steps in order, in the fixture's checkout, with
    gh stood in for and python3 this Python. A `uses:` step succeeds; an
    `if:` is a steps.<id>.outputs.<key> == '<value>' test; a failed step
    fails the job and stops the steps after it."""
    fake = fixture.fake
    python3 = (f'#!/usr/bin/env bash\nexec '
               f'"{_slashed(Path(sys.executable))}" "$@"\n')
    for name, text in (("gh", FAKE_GH), ("python3", python3)):
        (fake / name).write_bytes(text.encode("utf-8"))
        (fake / name).chmod(0o755)
    outputs: dict[str, dict[str, str]] = {}
    steps: dict[str, str] = {}
    log: list[str] = []
    failed = False
    for i, step in enumerate(job.get("steps", [])):
        name = str(step.get("id") or step.get("name") or step.get("uses"))
        cond = str(step.get("if") or "").strip()
        runs = not failed
        if cond:
            m = re.fullmatch(r"steps\.([\w-]+)\.outputs\.([\w-]+) == '([^']*)'",
                             cond)
            if not m:
                raise Unreadable(f"cannot decide {cond!r} in the move_pins job")
            runs = runs and outputs.get(m.group(1), {}).get(
                m.group(2)) == m.group(3)
        if not runs:
            steps[name] = "skipped"
            continue
        if "uses" in step:
            steps[name] = "success"
            continue
        (fixture.home / f"step-{i}.sh").write_bytes(
            str(step["run"]).encode("utf-8"))
        runner = fixture.home / f"run-{i}.sh"
        runner.write_bytes((
            'fakebin=$FAKE\n'
            'if command -v cygpath > /dev/null; then '
            'fakebin=$(cygpath -u "$FAKE"); fi\n'
            'export PATH="$fakebin:$PATH"\n'
            f'. "{_slashed(fixture.home / f"step-{i}.sh")}"\n').encode("utf-8"))
        out_file = fixture.home / f"output-{i}"
        out_file.write_text("", encoding="utf-8")
        env = dict(os.environ, TAG=fixture.tag, SHA=fixture.sha,
                   FAKE=_slashed(fake), GITHUB_OUTPUT=_slashed(out_file))
        done = subprocess.run(
            [bash, "--noprofile", "--norc", "-eo", "pipefail", _slashed(runner)],
            cwd=str(fixture.work), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600)
        log.append(f"--- {name}: exit {done.returncode}\n"
                   + done.stdout + done.stderr)
        outputs[name] = dict(
            line.split("=", 1) for line in
            out_file.read_text(encoding="utf-8").splitlines() if "=" in line)
        steps[name] = "success" if done.returncode == 0 else "failure"
        if done.returncode != 0:
            failed = True
    return {"result": "failure" if failed else "success", "steps": steps,
            "outputs": outputs, "log": "\n".join(log)}


# ---- the cases -----------------------------------------------------------------

def main() -> int:
    passed = failed = 0

    def ok(label: Any, condition: Any, detail: object = "") -> None:
        nonlocal passed, failed
        if condition:
            print(f"  ok       {label}")
            passed += 1
        else:
            print(f"  BROKEN   {label}")
            if detail:
                print(f"           {str(detail)[:900]}")
            failed += 1

    def one_line(out: str) -> str | None:
        lines = out.strip().splitlines()
        return lines[0] if len(lines) == 1 else None

    print("the gate: what a push to main is")
    print("-" * 62)

    repo = base_repo("docs-only")
    (repo / "README.md").write_text("Sabline, in more words\n",
                                    encoding="utf-8")
    commit(repo, "README: more words")
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("a docs-only commit is not a release: exit 0 and one notice line",
       code == 0 and line.startswith("::notice::no release:"), out + err)
    ok("...which says the version is already the newest release, and tells "
       "the jobs after it to do nothing",
       "VERSION is 7.1.2 and v7.1.2 is already the newest release" in line
       and outputs.get("release") == "false"
       and outputs.get("build") == "false", out + str(outputs))

    repo = base_repo("bump-without-changelog")
    write_versions(repo, "7.1.3")
    commit(repo, "7.1.3")
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("a version bump without a CHANGELOG entry is not a release: exit 0 "
       "and one notice line",
       code == 0 and line.startswith("::notice::no release:"), out + err)
    ok("...and the notice names the missing entry",
       "CHANGELOG.md has no entry heading for 7.1.3" in line
       and "'## 7.1.3 - <title>'" in line
       and outputs.get("release") == "false", line)

    repo = base_repo("correct-bump")
    write_versions(repo, "7.2.0")
    write_changelog(repo, ("7.2", "Releases that tag themselves",
                           "The workflow tags the release."), BASE_ENTRY)
    head = commit(repo, "v7.2.0: releases that tag themselves")
    correct = repo
    code, out, err, outputs = cli("gate", "--expect-sha", head, repo=repo)
    line = one_line(out) or ""
    ok("a correct bump is a release: exit 0 and one notice line - here from "
       "a compiler in one file at the tag to a package at the bump, as 8.2 "
       "is", code == 0 and line.startswith("::notice::release: 7.2.0"),
       out + err)
    ok("...handing the jobs after it the version, the tag, the commit and "
       "the tag before",
       outputs == {"release": "true", "build": "true", "prerelease": "false",
                   "version": "7.2.0", "tag": "v7.2.0",
                   "previous_tag": "v7.1.2", "sha": head},
       str(outputs))

    parent = git(repo, "rev-parse", "HEAD~1")
    code, out, err, outputs = cli("gate", "--expect-sha", parent, repo=repo)
    ok("a correct bump is refused (exit 1, an error) when the tests passed "
       "on another commit",
       code == 1 and (one_line(out) or "").startswith("::error::refused:")
       and outputs.get("release") == "false", out + err)

    code, out, err, outputs = cli("gate", "--dry-run", repo=repo)
    ok("a dry run decides the same, releases nothing, and builds",
       code == 0 and "dry run" in out and "release: 7.2.0" in out
       and outputs.get("release") == "false"
       and outputs.get("build") == "true", out + str(outputs))

    repo = base_repo("short-heading")
    write_versions(repo, "7.2.1")
    write_changelog(repo, ("7.2", "Releases that tag themselves", "..."),
                    BASE_ENTRY)
    commit(repo, "7.2.1")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("'## 7.2' is the entry for 7.2.0, never for 7.2.1",
       code == 0 and "no entry heading for 7.2.1" in out
       and outputs.get("release") == "false", out + err)

    repo = base_repo("disagree")
    write_versions(repo, "7.2.0", {
        "npm/package.json": "7.1.2",
        "integrations/mcp_registry/server.json": "7.1.2"})
    write_changelog(repo, ("7.2", "Releases that tag themselves", "..."),
                    BASE_ENTRY)
    commit(repo, "7.2.0, half bumped")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("version files that disagree are not a release, and each one that "
       "differs is named",
       code == 0 and "no release: sabline/version.py says 7.2.0 but" in out
       and "npm/package.json says 7.1.2" in out
       and "server.json (npm package) says 7.1.2" in out
       and "pyproject.toml" not in out
       and outputs.get("release") == "false", out + err)

    repo = base_repo("older")
    write_versions(repo, "7.0.5")
    write_changelog(repo, BASE_ENTRY, ("7.0.5", "A backport", "..."))
    commit(repo, "7.0.5")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a version that is not newer than the newest release is not a release",
       code == 0
       and "7.0.5 is not newer than the newest release, v7.1.2" in out
       and outputs.get("release") == "false", out + err)

    repo = base_repo("one-package")
    write_versions(repo, "7.2.0", {"packages": "pypi"})
    write_changelog(repo, ("7.2.0", "Releases that tag themselves", "..."),
                    BASE_ENTRY)
    commit(repo, "7.2.0, PyPI only")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a registry manifest without both the PyPI and the npm package is "
       "not a release",
       code == 0 and "must list both the pypi and the npm package" in out
       and outputs.get("release") == "false", out + err)

    claims = release_checks.version_claims(HERE)
    said = {v for _, v in claims}
    ok("this repository's six version files are all read, and agree",
       len(claims) == 8 and None not in said and len(said) == 1
       and claims[0][0] == "sabline/version.py", claims)
    ok("...and its CHANGELOG has an entry heading for its own VERSION",
       release_checks.changelog_entry(HERE, cast(str, claims[0][1])) is not None,
       claims[0])

    print()
    print("the gate: what STABILITY.md covers, in a minor or patch release")
    print("-" * 62)

    def bump(name: Any, version: Any, entry_text: Any, golden_before: Any = None, **compiler: Any) -> Any:
        repo = base_repo(name, golden=golden_before)
        write_versions(repo, version, **compiler)
        heading = version if version.count(".") == 2 else version
        write_changelog(repo, (heading, "A release", entry_text), BASE_ENTRY)
        commit(repo, version)
        return repo

    new_code = BASE_CODES + ("E615",)
    repo = bump("minor-new-code", "7.2.0", "It adds a check.", codes=new_code)
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("a minor bump that adds an error code, with no 'compatibility:' line, "
       "is refused (exit 1) and names the code",
       code == 1 and line.startswith("::error::refused: 7.2.0 is a minor "
                                     "release")
       and "adds the error code E615" in line and "compatibility:" in line
       and outputs.get("release") == "false", out + err)

    repo = bump("minor-new-code-said", "7.2.0",
                "It adds a check.\n\ncompatibility: E615 is given only to a "
                "program 7.1.2 stopped with a Python error, so nothing that "
                "ran is refused.", codes=new_code)
    code, out, err, outputs = cli("gate", repo=repo)
    ok("...and with a line beginning 'compatibility:' it is released",
       code == 0 and "::notice::release: 7.2.0" in out
       and outputs.get("release") == "true", out + err)

    repo = bump("major-new-code", "8.0.0", "A major version.",
                codes=new_code)
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a major bump that adds an error code needs no such line: released",
       code == 0 and "::notice::release: 8.0.0" in out
       and outputs.get("release") == "true", out + err)

    repo = bump("patch-removed-flag", "7.1.3", "A fix.",
                flags=("--allow", "--no-native"))
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("the same rule for a flag removed, in a patch: refused, naming it",
       code == 1 and "7.1.3 is a patch release" in line
       and "removes the flag --json" in line, out + err)

    repo = bump("minor-changed-default", "7.2.0", "Slower checks.",
                defaults={"CHECK_TIMEOUT_DEFAULT": "90",
                          "DEFAULT_ALLOW": '"io"'})
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("...and for a default changed: refused, naming it and both values",
       code == 1 and "changes the default CHECK_TIMEOUT_DEFAULT from 60 to "
                     "90" in line, out + err)

    code, out, err, _ = cli("covered", "v7.1.2", repo=repo)
    ok("release_checks.py covered names the same change for a person who "
       "asks before pushing", code == 0
       and "changes the default CHECK_TIMEOUT_DEFAULT from 60 to 90" in out,
       out + err)

    repo = bump("minor-api-moved", "7.2.0", "A new parameter.",
                golden_before={"library": {"check": "(source)"}},
                golden={"library": {"check": "(source, *, strict=False)"}})
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("an API golden that moved, with no 'api:' line, is refused",
       code == 1 and "tests/api/golden.json is not v7.1.2's" in line
       and "api:" in line, out + err)
    repo = bump("minor-api-said", "7.2.0",
                "A new parameter.\n\napi: check() takes strict=, default "
                "False.",
                golden_before={"library": {"check": "(source)"}},
                golden={"library": {"check": "(source, *, strict=False)"}})
    code, out, err, outputs = cli("gate", repo=repo)
    ok("...and released with one", code == 0
       and outputs.get("release") == "true", out + err)

    code, out, err, _ = cli("gate", repo=correct)
    ok("a bump that changes none of it needs neither line", code == 0
       and "::notice::release: 7.2.0" in out, out + err)

    # the 8.2 adversarial pass: a line that says nothing, and changes the
    # gate did not see
    arguing = "E615 is given only to a program that stopped with a traceback"
    for i, (where, entry) in enumerate((
            ("in a fenced code block",
             f"It adds a check.\n\n```\ncompatibility: {arguing}\n```"),
            ("in an indented code block",
             f"It adds a check.\n\n    compatibility: {arguing}"),
            ("inside an HTML comment",
             f"It adds a check.\n\n<!--\ncompatibility: {arguing}\n-->"),
            ("with nothing after it", "It adds a check.\n\ncompatibility:"),
            ("that says TODO",
             "It adds a check.\n\ncompatibility: TODO write why this is fine"),
            ("in a quote", f"It adds a check.\n\n> compatibility: {arguing}"))):
        repo = bump(f"said-nothing-{i}", "7.2.0", entry, codes=new_code)
        code, out, err, outputs = cli("gate", repo=repo)
        ok(f"a 'compatibility:' line {where} does not count: refused",
           code == 1 and outputs.get("release") == "false", out + err)

    def two_releases(name: str, first: dict[str, str],
                     second: dict[str, str]) -> Path:
        """7.2.0 tagged with the files `first` added, then 7.3.0 with
        `second` written over them."""
        repo = base_repo(name)
        for version, files, entries in (
                ("7.2.0", first, (("7.2.0", "A release", "Nothing covered."),
                                  BASE_ENTRY)),
                ("7.3.0", second, (("7.3.0", "Another", "A change."),
                                   ("7.2.0", "A release", "Nothing covered."),
                                   BASE_ENTRY))):
            write_versions(repo, version)
            for rel, body in files.items():
                (repo / rel).parent.mkdir(parents=True, exist_ok=True)
                (repo / rel).write_text(body, encoding="utf-8")
            write_changelog(repo, *entries)
            commit(repo, version)
            if version == "7.2.0":
                git(repo, "tag", "-a", "v7.2.0", "-m", "v7.2.0")
        return repo

    base_table = ("ERROR_TABLE = {\n"
                  + "".join(f'    "{c}": "what {c} means",\n' for c in BASE_CODES)
                  + "}\n")
    for i, (how, extra) in enumerate((
            ("by a subscript", {"sabline/errors.py": base_table
                                + 'ERROR_TABLE["E615"] = "what E615 means"\n'}),
            ("by update()", {"sabline/errors.py": base_table
                             + 'ERROR_TABLE.update({"E615": "means"})\n'}),
            ("in a sub-package", {"sabline/codes/more.py":
                                  'MORE = {"E615": "what E615 means"}\n'}))):
        repo = two_releases(f"code-added-{i}", {}, extra)
        code, out, err, outputs = cli("gate", repo=repo)
        ok(f"an error code added {how} is seen: refused, naming E615",
           code == 1 and "adds the error code E615" in (one_line(out) or ""),
           out + err)

    repo = two_releases(
        "default-through-a-name",
        {"sabline/limits.py": "_SECONDS = 60\nWAIT_DEFAULT = _SECONDS\n"},
        {"sabline/limits.py": "_SECONDS = 5\nWAIT_DEFAULT = _SECONDS\n"})
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a default read from another constant is seen when that one changes",
       code == 1 and "changes the default WAIT_DEFAULT from 60 to 5"
       in (one_line(out) or ""), out + err)

    repo = two_releases(
        "default-of-the-run-state",
        {"sabline/state.py": 'EFFECT_BUDGET = {"io"}\n'},
        {"sabline/state.py": 'EFFECT_BUDGET = {"io", "fs", "net"}\n'})
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a variable of the run state is a default: widening EFFECT_BUDGET is "
       "refused", code == 1 and "changes the default EFFECT_BUDGET"
       in (one_line(out) or ""), out + err)

    repo = two_releases(
        "default-removed",
        {"sabline/library.py": "def check(source, timeout=60):\n    pass\n"},
        {"sabline/library.py": "def check(source, timeout):\n    pass\n"})
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a parameter that loses its default is refused, naming it",
       code == 1 and "removes the default of check(timeout), which was 60"
       in (one_line(out) or ""), out + err)

    repo = base_repo("version-with-line-breaks")
    write_versions(repo, "7.2.0")
    (repo / "sabline" / "version.py").write_text(
        'VERSION = "7.2.0\nrelease=true\nbuild=true"\n', encoding="utf-8")
    write_changelog(repo, ("7.2.0", "A release", "..."), BASE_ENTRY)
    commit(repo, "7.2.0, a VERSION with line breaks")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a VERSION holding line breaks writes no outputs of its own: not a "
       "release, and build is false",
       outputs.get("release") == "false" and outputs.get("build") == "false"
       and "Traceback" not in out + err, f"{outputs} {out}{err}")

    repo = base_repo("unreadable-module")
    write_versions(repo, "7.2.0")
    (repo / "sabline" / "odd.py").write_bytes(b"X = '\xff\xfe'\n")
    write_changelog(repo, ("7.2.0", "A release", "..."), BASE_ENTRY)
    commit(repo, "7.2.0, a module that is not UTF-8")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a module that is not UTF-8 is a refusal in one line, not a traceback",
       code == 1 and "cannot be told" in (one_line(out) or "")
       and "Traceback" not in out + err
       and outputs.get("release") == "false", out + err)

    repo = base_repo("packages-not-a-list")
    write_versions(repo, "7.2.0")
    server = repo / "integrations" / "mcp_registry" / "server.json"
    server.write_text(json.dumps({"name": SERVER, "version": "7.2.0",
                                  "packages": 5}), encoding="utf-8")
    write_changelog(repo, ("7.2.0", "A release", "..."), BASE_ENTRY)
    commit(repo, "7.2.0, packages that are not a list")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a registry manifest whose packages are not a list is not a release, "
       "and no traceback", code == 0 and "Traceback" not in out + err
       and outputs.get("release") == "false", out + err)

    print()
    print("the gate: a pre-release publishes the crate and nothing else")
    print("-" * 62)

    # A repository at 7.1.2, tagged, whose Rust workspace says an alpha.
    # The six version files stay where the tag left them: that is what
    # makes it a pre-release of the crate and not a release of Sabline.
    repo = base_repo("prerelease")
    write_crate(repo, "9.0.0-alpha.1")
    write_changelog(repo, ("9.0.0-alpha.1", "The parser, twice",
                           "sabline-rt reads a program."), BASE_ENTRY)
    head = commit(repo, "9.0.0-alpha.1: the parser, twice")
    code, out, err, outputs = cli("gate", "--expect-sha", head, repo=repo)
    line = one_line(out) or ""
    ok("an alpha in rt/Cargo.toml is a release, with the Python package "
       "left where it was",
       code == 0 and line.startswith("::notice::pre-release: 9.0.0-alpha.1"),
       out + err)
    ok("...telling the jobs after it that it is a pre-release, and which "
       "version",
       outputs == {"release": "true", "build": "true", "prerelease": "true",
                   "version": "9.0.0-alpha.1", "tag": "v9.0.0-alpha.1",
                   "previous_tag": "v7.1.2", "sha": head},
       str(outputs))
    ok("...and the line says what it publishes and what stays",
       "publishing the sabline-rt crate" in line
       and "marked pre-release" in line
       and "v7.1.2 stays what a user gets" in line, line)

    repo = base_repo("prerelease-moves-python")
    write_crate(repo, "9.0.0-alpha.1")
    write_versions(repo, "7.1.3")
    write_changelog(repo, ("9.0.0-alpha.1", "The parser, twice", "..."),
                    BASE_ENTRY)
    commit(repo, "an alpha that also bumps the Python package")
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("an alpha that also moves the Python package is refused: exit 1, an "
       "error", code == 1 and line.startswith("::error::refused:")
       and outputs.get("release") == "false", out + err)
    ok("...saying it would change what PyPI serves",
       "would change what PyPI serves" in line, line)

    repo = base_repo("prerelease-no-entry")
    write_crate(repo, "9.0.0-alpha.1")
    commit(repo, "an alpha with no CHANGELOG entry")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("an alpha with no CHANGELOG entry is not a release",
       code == 0 and "no entry heading for 9.0.0-alpha.1" in out
       and outputs.get("release") == "false", out + err)

    repo = base_repo("prerelease-already-tagged")
    write_crate(repo, "9.0.0-alpha.1")
    write_changelog(repo, ("9.0.0-alpha.1", "The parser, twice", "..."),
                    BASE_ENTRY)
    commit(repo, "9.0.0-alpha.1")
    git(repo, "tag", "-a", "v9.0.0-alpha.1", "-m", "v9.0.0-alpha.1")
    (repo / "README.md").write_text("after the alpha\n", encoding="utf-8")
    commit(repo, "a commit after the alpha")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a commit after the alpha is not a second release of it, and it is "
       "asked the ordinary questions again",
       code == 0 and "no release:" in out
       and "v7.1.2 is already the newest release" in out
       and outputs.get("prerelease") == "false"
       and outputs.get("release") == "false", out + err)

    repo = base_repo("prerelease-then-release")
    write_crate(repo, "9.0.0-alpha.1")
    write_changelog(repo, ("9.0.0-alpha.1", "The parser, twice", "..."),
                    BASE_ENTRY)
    commit(repo, "9.0.0-alpha.1")
    git(repo, "tag", "-a", "v9.0.0-alpha.1", "-m", "v9.0.0-alpha.1")
    write_crate(repo, "9.0.0-alpha.2")
    write_changelog(repo, ("9.0.0-alpha.2", "Types, twice", "..."),
                    ("9.0.0-alpha.1", "The parser, twice", "..."), BASE_ENTRY)
    head = commit(repo, "9.0.0-alpha.2")
    code, out, err, outputs = cli("gate", "--expect-sha", head, repo=repo)
    ok("alpha.2 follows alpha.1, and v9.0.0-alpha.1 is the tag before it",
       code == 0 and "pre-release: 9.0.0-alpha.2" in out
       and outputs.get("previous_tag") == "v9.0.0-alpha.1", out + err)

    # After the alpha is tagged, rt/Cargo.toml still says its version
    # until somebody moves it - and the commits after it must be able to be
    # the next ordinary release. A rule that read the crate alone would
    # block every release until the crate's version moved.
    repo = base_repo("release-after-an-alpha")
    write_crate(repo, "9.0.0-alpha.1")
    write_changelog(repo, ("9.0.0-alpha.1", "The parser, twice", "..."),
                    BASE_ENTRY)
    commit(repo, "9.0.0-alpha.1")
    git(repo, "tag", "-a", "v9.0.0-alpha.1", "-m", "v9.0.0-alpha.1")
    write_versions(repo, "7.1.3")
    write_changelog(repo, ("7.1.3", "A patch after the alpha", "..."),
                    ("9.0.0-alpha.1", "The parser, twice", "..."), BASE_ENTRY)
    head = commit(repo, "7.1.3, after the alpha, with the crate unmoved")
    code, out, err, outputs = cli("gate", "--expect-sha", head, repo=repo)
    ok("a release of the Python package after a tagged alpha is an ordinary "
       "release, with the crate's version left where the alpha put it",
       code == 0 and "::notice::release: 7.1.3" in out
       and outputs.get("prerelease") == "false", out + err)
    ok("...measured against the newest release and not against the alpha, "
       "which is what everything it compares with means by 'the previous "
       "one'",
       outputs.get("previous_tag") == "v7.1.2"
       and "the newest release was v7.1.2" in out, out + str(outputs))

    # and an ordinary release, in a repository that has a Rust workspace,
    # is decided exactly as it was: the alpha path is entered by the crate
    # saying a pre-release version and by nothing else
    repo = base_repo("release-with-a-crate")
    write_crate(repo, "9.0.0")
    write_versions(repo, "7.2.0")
    write_changelog(repo, ("7.2", "Releases that tag themselves", "..."),
                    BASE_ENTRY)
    head = commit(repo, "v7.2.0, beside a crate at 9.0.0")
    code, out, err, outputs = cli("gate", "--expect-sha", head, repo=repo)
    ok("a repository with a Rust workspace at a release version takes the "
       "ordinary path",
       code == 0 and "::notice::release: 7.2.0" in out
       and outputs.get("prerelease") == "false"
       and outputs.get("version") == "7.2.0", out + err)

    print()
    print("the release notes and the tag message")
    print("-" * 62)
    notes = SCRATCH / "notes.md"
    code, out, err, _ = cli("notes", "7.2.0", "--sha", head, "--previous",
                            "v7.1.2", "-o", str(notes), repo=correct)
    text = notes.read_text(encoding="utf-8") if notes.exists() else ""
    ok("the notes are the CHANGELOG entry, then how the release was made",
       code == 0 and text.startswith("The workflow tags the release.")
       and head in text and "**not signed**" in text
       and "/compare/v7.1.2...v7.2.0" in text, err + text)
    code, out, err, _ = cli("title", "7.2.0", repo=correct)
    ok("the tag message's title is the entry's",
       code == 0 and out.strip() == "Releases that tag themselves", out + err)

    print()
    print("advisories")
    print("-" * 62)
    repo = base_repo("advisories", extra={"advisory-old.md": "# Old\n"})
    (repo / "advisory-old.md").write_text("# Old, edited\n", encoding="utf-8")
    (repo / "advisory-new.md").write_text("# New\n", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "advisory-nested.md").write_text("# Nested\n",
                                                      encoding="utf-8")
    (repo / "not-an-advisory.md").write_text("# No\n", encoding="utf-8")
    commit(repo, "two advisories")
    code, out, err, _ = cli("advisories", "v7.1.2", "HEAD", repo=repo)
    ok("the advisory-*.md files added since the last tag are found, and "
       "only those (not one added before it and edited since)",
       code == 0 and sorted(out.split())
       == ["advisory-new.md", "docs/advisory-nested.md"], out + err)

    request = SCRATCH / "advisory-proof-cache.json"
    code, out, err, _ = cli("advisory-body",
                            str(HERE / "advisory-proof-cache.md"),
                            "-o", str(request))
    body = json.loads(request.read_text(encoding="utf-8")) \
        if request.exists() else {}
    ok("advisory-proof-cache.md becomes the API's draft-advisory request: "
       "summary, versions, CVSS",
       code == 0
       and body.get("summary", "").startswith(
           "a project-local proof cache could make a false")
       and body.get("vulnerabilities") == [{
           "package": {"ecosystem": "pip", "name": "sabline-lang"},
           "vulnerable_version_range": ">= 2.29, <= 7.1.1",
           "patched_versions": "7.1.2", "vulnerable_functions": []}]
       and body.get("cvss_vector_string")
       == "CVSS:3.1/AV:L/AC:L/PR:N/UI:R/S:U/C:N/I:H/A:N"
       and "severity" not in body, err + json.dumps(body)[:600])
    ok("...its description starts at the advisory's first section, without "
       "the note about how to submit it, and it asks for no state",
       body.get("description", "").startswith("## Summary")
       and "Draft for submission" not in body.get("description", "")
       and "state" not in body, str(body.get("description", ""))[:200])

    bad = SCRATCH / "advisory-bad.md"
    bad.write_text("# Something\n\n## Summary\n\nNo versions.\n",
                   encoding="utf-8")
    code, out, err, _ = cli("advisory-body", str(bad))
    ok("an advisory with no 'Affected versions' section is refused by name "
       "(exit 2)", code == 2 and "Affected versions" in err, out + err)

    code, out, err, _ = cli("advisory-commands", "advisory-proof-cache.md",
                            "--tag", "v7.2.0")
    api = f"repos/{REPOSITORY}/security-advisories"
    ok("a new advisory prints a warning and the two commands that make a "
       "draft and request its CVE",
       code == 0 and out.startswith("::warning::advisory-proof-cache.md is "
                                    "new in v7.2.0")
       and "python release_checks.py advisory-body advisory-proof-cache.md "
           "-o advisory-proof-cache.json" in out
       and f'gh api --method POST "{api}/$(gh api --method POST {api} '
           f'--input advisory-proof-cache.json --jq .ghsa_id)/cve"' in out,
       out + err)

    print()
    print("RELEASE_PAUSED, the kill switch")
    print("-" * 62)
    for value, stops in (("", False), ("false", False), ("0", False),
                         ("No", False), ("off", False), ("true", True),
                         ("1", True), ("yes", True), ("maybe", True)):
        env = {k: v for k, v in os.environ.items() if k != "RELEASE_PAUSED"}
        if value:
            env["RELEASE_PAUSED"] = value
        code, out, err, outputs = cli("paused", env=env)
        ok(f"RELEASE_PAUSED={value!r} {'pauses' if stops else 'does not'}"
           + (" - a value nobody meant stops rather than publishes"
              if value == "maybe" else ""),
           code == 0 and outputs.get("paused") == str(stops).lower()
           and (("::warning::release paused" in out) == stops), out + err)
    jobs = release_jobs()
    paused_job = jobs.get("paused", {})
    step_env = [s.get("env", {}) for s in paused_job.get("steps", [])]
    ok("release.yml asks it in a job of the release environment, from the "
       "environment's variable",
       paused_job.get("environment") == "release"
       and any("vars.RELEASE_PAUSED" in str(e.get("RELEASE_PAUSED", ""))
               for e in step_env)
       and "release_checks.py paused" in json.dumps(paused_job), paused_job)
    tag_job = jobs.get("tag", {})
    ok("...the tag needs it, and happens only when it says not paused",
       "paused" in needs_of(tag_job)
       and "needs.paused.outputs.paused == 'false'" in str(tag_job.get("if")),
       tag_job.get("if"))
    publishing = [n for n, j in jobs.items()
                  if re.search(r"published |gh release|mcp-publisher|"
                               r"npm publish|pypi-publish|vsce publish",
                               json.dumps(j))]
    ok("...and every job that publishes comes after the tag", publishing
       and all(n in descendants(jobs, {"tag"}) for n in publishing),
       [n for n in publishing if n not in descendants(jobs, {"tag"})])
    ok("...while the tests and the builds do not wait on it: nothing before "
       "the tag needs it",
       not any("paused" in needs_of(jobs[n])
               for n in ("dist", "reproducible", "bundle", "binaries",
                         "attestation")), "")

    print()
    print("publishing: what is there already, and whether it all agrees")
    print("-" * 62)
    ok("a release's files are the 24 the v7.1.2 release holds, by name",
       sorted(release_checks.expected_assets("7.1.2")) == sorted(V712_ASSETS),
       set(release_checks.expected_assets("7.1.2")) ^ set(V712_ASSETS))
    receipt_files = {"sabline-receipt-8.1.0.intoto.json",
                     "sabline-receipt-8.1.0.cosign.sigstore.json",
                     "sabline-receipt-8.1.0.sigstore-python.sigstore.json"}
    ok("from 8.1.0 a release also holds the receipt of one run of the "
       "attested example, signed both ways: 27 files, and 8.0.0 still 24",
       len(release_checks.expected_assets("8.1.0")) == 27
       and receipt_files <= set(release_checks.expected_assets("8.1.0"))
       and len(release_checks.expected_assets("8.0.0")) == 24
       and not any("receipt" in n
                   for n in release_checks.expected_assets("8.0.0")),
       release_checks.expected_assets("8.1.0"))

    stand_in = ThreadingHTTPServer(("127.0.0.1", 0), StandIn)
    threading.Thread(target=stand_in.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{stand_in.server_address[1]}"
    saved = dict(release_checks.ENDPOINTS)
    release_checks.ENDPOINTS.update({k: base for k in saved})
    release_checks.RETRY_WAIT = 0
    targets = ("pypi", "npm", "registry", "github", "vscode")
    try:
        StandIn.routes = all_at("7.2.0")
        ok("published: 7.2.0 is found on each of the five targets",
           all(release_checks.published(t, "7.2.0") for t in targets))
        ok("...and 7.2.1 on none of them (a 404 means not there)",
           not any(release_checks.published(t, "7.2.1") for t in targets))
        outputs_file = SCRATCH / "published.out"
        code, out = in_process("published", "npm", "7.2.0", "--annotate",
                               "--github-output", str(outputs_file))
        ok("...and the step skips with a notice when it is already there",
           code == 0 and out.startswith("::notice::7.2.0 is already on npm")
           and "published=true" in outputs_file.read_text(encoding="utf-8"),
           out)

        StandIn.routes = {("GET", "/pypi/sabline-lang/7.2.0/json"):
                          (503, {})}
        try:
            release_checks.published("pypi", "7.2.0")
            unanswered = False
        except release_checks.Unanswered:
            unanswered = True
        code, out = in_process("published", "pypi", "7.2.0", "--annotate")
        ok("a target that keeps failing is 'could not tell' (exit 2), never "
           "'not there'", unanswered and code == 2
           and out.startswith("::error::could not tell"), out)

        StandIn.routes = all_at("7.2.0")
        code, out = in_process("registry-ready", "7.2.0")
        ok("registry-ready: PyPI and npm both serve 7.2.0 naming the server",
           code == 0, out)
        routes = all_at("7.2.0")
        routes[("GET", "/pypi/sabline-lang/7.2.0/json")] = (200, {"info": {
            "version": "7.2.0", "description": "# Sabline"}})
        StandIn.routes = routes
        code, out = in_process("registry-ready", "7.2.0", "--annotate")
        ok("...and not while PyPI's description lacks the mcp-name marker",
           code == 1 and "::error::" in out and "mcp-name" in out, out)

        StandIn.routes = all_at("7.2.0")
        StandIn.posted.clear()
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("consistent: PyPI, npm, the registry, the GitHub release and the "
           "VS Code Marketplace all report 7.2.0 (exit 0)",
           code == 0 and "::notice::consistent" in out
           and "ok       the VS Code Marketplace: latest is 7.2.0" in out, out)
        asked = [json.loads(b).get("flags") for b in StandIn.posted]
        ok("...the Marketplace asked for its latest version only "
           "(IncludeVersions | IncludeLatestVersionOnly)",
           asked == [release_checks.MARKETPLACE_LATEST] == [0x201], asked)
        extension = ("POST", "/_apis/public/gallery/extensionquery")
        extension_behind = (200, {"results": [{"extensions": [{"versions": [
            {"version": "7.1.2"}]}]}]})
        routes = all_at("7.2.0")
        routes[extension] = extension_behind
        StandIn.routes = routes
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("...the extension still at 7.1.2 on the Marketplace fails red and "
           "names the Marketplace alone",
           code == 1 and "::error::inconsistent: the VS Code Marketplace "
                         "(latest is 7.1.2) - does not report 7.2.0" in out,
           out)
        routes = all_at("7.2.0")
        routes[extension] = (200, {"results": [{"extensions": [
            {"versions": []}]}]})
        StandIn.routes = routes
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("...and an extension the Marketplace lists with no version fails "
           "red too",
           code == 1 and "::error::inconsistent: the VS Code Marketplace "
                         "(no version listed)" in out, out)
        routes = all_at("7.2.0")
        routes[("GET", "/sabline-lang")] = (200, {"dist-tags": {
            "latest": "7.1.1"}})
        StandIn.routes = routes
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("...npm still at 7.1.1 fails red and names npm and what it says",
           code == 1 and "::error::inconsistent: npm (latest is 7.1.1) - "
                         "does not report 7.2.0" in out, out)
        routes = all_at("7.2.0")
        routes[("GET", f"/repos/{REPOSITORY}/releases/latest")] = (200, {
            "tag_name": "v7.2.0",
            "assets": [{"name": n} for n in
                       release_checks.expected_assets("7.2.0")
                       if n != "sabline-macos.sigstore.json"]})
        StandIn.routes = routes
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("...and a GitHub release missing one signature names that file",
           code == 1 and "the GitHub release (latest is v7.2.0, without "
                         "sabline-macos.sigstore.json)" in out, out)

        # The "not yet" path: a target behind for a while. 8.1.1's release
        # met it for the first time - PyPI's JSON still said 8.1.0 - and the
        # consistency check stopped with a TypeError instead of asking again.
        def polled(*words: Any) -> Any:
            try:
                return in_process(*words)
            except Exception as e:      # noqa: BLE001 - reported, not raised
                return None, f"{type(e).__name__}: {e}"

        routes = all_at("7.2.0")
        routes[("GET", "/pypi/sabline-lang/json")] = [
            (200, {"info": {"version": "7.1.1"}}),
            (200, {"info": {"version": "7.2.0"}})]
        StandIn.routes = routes
        code, out = polled("consistent", "7.2.0", "--timeout", "30",
                           "--interval", "0", "--annotate")
        ok("consistent: a target one poll behind is 'not yet', naming it and "
           "what it says, and the next poll finds every target agreeing",
           code == 0 and "not yet: PyPI (latest is 7.1.1)\n" in out
           and "::notice::consistent" in out, out)
        routes = all_at("7.2.0")
        routes[("GET", "/pypi/sabline-lang/json")] = (200, {"info": {
            "version": "7.1.1"}})
        StandIn.routes = routes
        code, out = polled("consistent", "7.2.0", "--timeout", "0.3",
                           "--interval", "0.05", "--annotate")
        ok("...a target still behind when --timeout runs out is asked again "
           "until then, and fails red naming it",
           code == 1 and out.count("not yet: PyPI (latest is 7.1.1)") >= 2
           and "::error::inconsistent: PyPI (latest is 7.1.1)" in out, out)

        # The extension lagging behind the rest. Until this check asked the
        # Marketplace, 8.2.0's extension, which never published, passed.
        routes = all_at("7.2.0")
        routes[extension] = [extension_behind, all_at("7.2.0")[extension]]
        StandIn.routes = routes
        code, out = polled("consistent", "7.2.0", "--timeout", "30",
                           "--interval", "0", "--annotate")
        ok("consistent: an extension one poll behind is 'not yet', naming the "
           "Marketplace, and the next poll finds every target agreeing",
           code == 0
           and "not yet: the VS Code Marketplace (latest is 7.1.2)\n" in out
           and "::notice::consistent" in out, out)
        routes = all_at("7.2.0")
        routes[extension] = extension_behind
        StandIn.routes = routes
        code, out = polled("consistent", "7.2.0", "--timeout", "0.3",
                           "--interval", "0.05", "--annotate")
        ok("...and one still behind when --timeout runs out fails red, naming "
           "the Marketplace and nothing else",
           code == 1
           and out.count("not yet: the VS Code Marketplace (latest is "
                         "7.1.2)") >= 2
           and "::error::inconsistent: the VS Code Marketplace (latest is "
               "7.1.2) - does not report 7.2.0" in out, out)
        routes = all_at("7.2.0")
        routes[("GET", "/pypi/sabline-lang/7.2.0/json")] = [
            (404, {}),
            (200, {"info": {"version": "7.2.0", "description":
                            f"<!-- mcp-name: {SERVER} -->\n# Sabline"}})]
        StandIn.routes = routes
        code, out = polled("registry-ready", "7.2.0", "--timeout", "30",
                           "--interval", "0", "--annotate")
        ok("...and registry-ready's 'not yet' still names what the registry "
           "would not find, then goes green",
           code == 0 and "not yet: " in out and "PyPI" in out, out)

        # --require, the end of a publish (8.2.1): the Marketplace's job
        # ended green after three timeouts on 8.2.0, saying NOT PUBLISHED
        query = ("POST", "/_apis/public/gallery/extensionquery")
        without = (200, {"results": [{"extensions": [{"versions": [
            {"version": "7.1.2"}]}]}]})
        StandIn.routes = all_at("7.2.0")
        code, out = polled("published", "vscode", "7.2.0", "--require",
                           "--annotate")
        ok("published --require: a version the Marketplace lists is exit 0, "
           "PUBLISHED",
           code == 0 and out.startswith(
               "::notice::PUBLISHED - 7.2.0 is on the VS Code Marketplace"),
           out)
        routes = all_at("7.2.0")
        routes[query] = [without, all_at("7.2.0")[query]]
        StandIn.routes = routes
        code, out = polled("published", "vscode", "7.2.0", "--require",
                           "--timeout", "30", "--interval", "0", "--annotate")
        ok("...one it lists a poll later is 'not yet', then PUBLISHED",
           code == 0 and "not yet: 7.2.0 is not on the VS Code Marketplace\n"
           in out and "::notice::PUBLISHED" in out, out)
        StandIn.routes = {query: without}
        code, out = polled("published", "vscode", "7.2.0", "--require",
                           "--timeout", "0.3", "--interval", "0.05",
                           "--annotate")
        ok("...one still not listed when --timeout runs out is exit 1, "
           "NOT PUBLISHED, as an error",
           code == 1 and "::error::NOT PUBLISHED - 7.2.0 is not on the VS "
                         "Code Marketplace after 0.3 s of asking" in out, out)
        StandIn.routes = {query: (503, {})}
        code, out = polled("published", "vscode", "7.2.0", "--require",
                           "--annotate")
        ok("...and a Marketplace that does not answer is exit 2, never 0",
           code == 2 and out.startswith("::error::could not tell"), out)
        StandIn.routes = {query: without}
        code, out = polled("published", "vscode", "7.2.0", "--annotate")
        ok("...while without --require, not there is still exit 0 and "
           "'publishing it', as every publish step asks first",
           code == 0 and "is not on the VS Code Marketplace yet; publishing "
                         "it" in out, out)

        print()
        print("release.yml, job by job: a publish that fails midway, and the "
              "re-run")
        print("-" * 62)
        jobs = release_jobs()
        try:
            for failing in ("npm", "registry", "github"):
                release = Release("7.2.0")
                release.fail.add(failing)
                results, outputs = fresh_results()
                attempt(jobs, release, results, outputs)
                failed_jobs = {n for n, r in results.items()
                               if r == "failure"}
                first = dict(release.made)
                ok(f"attempt 1 with {failing}'s publish failing: the jobs "
                   f"after it do not run, and what came before it is "
                   f"published once",
                   failed_jobs and results.get("consistency") == "skipped"
                   and all(v == 1 for v in first.values()), f"{results} "
                   f"{first}")
                rerun = descendants(jobs, failed_jobs)
                attempt(jobs, release, results, outputs, only=rerun)
                ok("...re-running the failed jobs finishes it: every "
                   "publish made exactly once, none skipped, and "
                   "consistency passes",
                   all(release.made[p] == 1 for p in PUBLISHES)
                   and results.get("consistency") == "success"
                   and not ({"tag", "pypi"} - {"pypi"}) & rerun
                   and "pypi" not in rerun,
                   f"{dict(release.made)} {results} rerun={sorted(rerun)}")
            everything = set(jobs) - BEFORE_TAG
            attempt(jobs, release, results, outputs, only=everything)
            ok("a whole second run after a finished release publishes "
               "nothing again", all(release.made[p] == 1 for p in PUBLISHES),
               dict(release.made))
            release = Release("7.2.0")
            results, outputs = fresh_results(paused="true")
            attempt(jobs, release, results, outputs)
            ok("with RELEASE_PAUSED set, nothing is tagged and nothing is "
               "published", not release.made
               and all(results.get(n) == "skipped"
                       for n in set(jobs) - BEFORE_TAG), f"{results}")

            # The Marketplace's publish failing (8.2.1): the vscode job has
            # no continue-on-error, so it is red, and the jobs after it run.
            release = Release("7.2.0")
            release.fail.add("vscode")
            results, outputs = fresh_results()
            attempt(jobs, release, results, outputs)
            differs = [target for target, _, agrees
                       in release_checks.consistency("7.2.0") if not agrees]
            ok("attempt 1 with the Marketplace's publish failing: the vscode "
               "job is red, the GitHub release, the registry and the "
               "attestation run all the same, and consistency is red too, "
               "naming the Marketplace alone",
               results.get("vscode") == "failure"
               and all(results.get(n) == "success" for n in (
                   "github_release", "mcp_registry", "attach_attestation"))
               and results.get("consistency") == "failure"
               and differs == ["the VS Code Marketplace"]
               and release.made["vscode"] == 0,
               f"{results} {dict(release.made)} differs={differs}")
            attempt(jobs, release, results, outputs,
                    only=descendants(jobs, {"vscode"}))
            ok("...re-running the failed jobs and the jobs after them "
               "publishes the extension once, nothing else again, and "
               "consistency passes",
               results.get("vscode") == "success"
               and results.get("consistency") == "success"
               and all(release.made[p] == 1 for p in PUBLISHES),
               f"{dict(release.made)} {results}")

            print()
            print("release.yml, job by job: a pre-release publishes the "
                  "crate and nothing else")
            print("-" * 62)

            # An alpha: the gate says prerelease=true, and only the jobs
            # that publish the crate may run. This is the fixture for
            # plan/9.0.md's rule that 8.6.0 stays what users get.
            # A pre-release skips every Python build, so the jobs before
            # the tag are skipped rather than successful - which is what
            # the tag job's condition has to survive.
            def prerelease_results(paused: str = "false") -> Any:
                results, outputs = fresh_results(paused)
                for name in BEFORE_TAG - {"gate", "paused"}:
                    results[name] = "skipped"
                outputs[("gate", "prerelease")] = "true"
                return results, outputs

            release = Release("9.0.0-alpha.1")
            results, outputs = prerelease_results()
            attempt(jobs, release, results, outputs)
            made = dict(release.made)
            never = ("pypi", "npm", "vscode", "registry", "github",
                     "attestation", "pins")
            ok("a pre-release tags, builds the crate, publishes it to "
               "crates.io and makes a GitHub release marked pre-release",
               all(release.made[p] == 1 for p in PRERELEASE_PUBLISHES), made)
            ok("...and publishes to PyPI, npm, the Marketplace and the MCP "
               "registry not at all, attaches no attestation, and moves no "
               "Action pin",
               all(release.made[p] == 0 for p in never), made)
            ok("...with every job of the ordinary path skipped rather than "
               "failed, the tag still made on top of them",
               all(results.get(n) == "skipped" for n in (
                   "pypi", "npm", "vscode", "github_release", "mcp_registry",
                   "attach_attestation", "consistency", "move_pins",
                   "advisory"))
               and results.get("tag") == "success",
               {n: r for n, r in results.items() if r != "success"})
            ok("...and the crate's own jobs ran",
               results.get("crate") == "success"
               and results.get("crates_io") == "success"
               and results.get("prerelease_github") == "success", results)

            release = Release("9.0.0-alpha.1")
            results, outputs = prerelease_results(paused="true")
            attempt(jobs, release, results, outputs)
            ok("RELEASE_PAUSED stops a pre-release too: the crate is still "
               "built, so a paused pre-release is a checked one, and "
               "nothing is tagged and nothing is published",
               release.made["crate-built"] == 1
               and not any(release.made[p] for p in
                           ("tag", "crates", "prerelease-github")),
               dict(release.made))

            release = Release("9.0.0-alpha.1")
            release.fail.add("crates")
            results, outputs = prerelease_results()
            attempt(jobs, release, results, outputs)
            ok("a crates.io publish that fails leaves no GitHub release "
               "behind it",
               results.get("crates_io") == "failure"
               and results.get("prerelease_github") == "skipped"
               and release.made["prerelease-github"] == 0,
               f"{results} {dict(release.made)}")
            attempt(jobs, release, results, outputs,
                    only=descendants(jobs, {"crates_io"}))
            ok("...and re-running the failed jobs finishes it, each publish "
               "made once",
               all(release.made[p] == 1 for p in PRERELEASE_PUBLISHES),
               f"{dict(release.made)} {results}")

            # and the ordinary path, run again after all that, is what it
            # was: this is the other half of the fixture the alpha needs
            release = Release("7.2.0")
            results, outputs = fresh_results()
            attempt(jobs, release, results, outputs)
            ok("an ordinary release is unchanged: every publish made once, "
               "and no crate job ran",
               all(release.made[p] == 1 for p in PUBLISHES)
               and release.made["crate-built"] == 0
               and release.made["crates"] == 0
               and release.made["prerelease-github"] == 0
               and results.get("crate") == "skipped"
               and results.get("crates_io") == "skipped"
               and results.get("prerelease_github") == "skipped",
               f"{dict(release.made)} {results}")

            print()
            print("the vscode job's own steps, in bash, with stand-ins for "
                  "vsce and npm")
            print("-" * 62)
            vscode = jobs["vscode"]
            ok("the vscode job has no continue-on-error of its own, so a job "
               "that fails is red", "continue-on-error" not in vscode,
               vscode.get("continue-on-error"))
            found_bash = posix_bash()
            if found_bash is None:
                print("  skip     the vscode job's steps (no POSIX bash here)")
            else:
                shell: str = found_bash

                def job(answers: str, **more: Any) -> dict[str, Any]:
                    return run_vscode_job(vscode, shell, base, answers, **more)

                def told(r: dict[str, Any]) -> str:
                    return (f"{r['result']} attempts={r['attempts']} "
                            f"sleeps={r['sleeps']} steps={r['steps']} "
                            f"summary={r['summary']!r} log={r['log'][-900:]}")

                not_listed = ("NOT PUBLISHED - 7.2.0 is not on the VS Code "
                              "Marketplace")
                listed = "PUBLISHED - 7.2.0 is on the VS Code Marketplace"
                r = job("timeout")
                ok("a Marketplace that times out every time: six attempts, "
                   "30, 60, 120, 240 and 480 s apart, then the job is red, "
                   "saying NOT PUBLISHED",
                   r["result"] == "failure" and r["attempts"] == 6
                   and r["sleeps"] == ["30", "60", "120", "240", "480"]
                   and "timed out on all 6 attempts" in r["summary"]
                   and not_listed in r["summary"], told(r))
                r = job("timeout,timeout,ok")
                ok("two timeouts and then a publish: two retries, 30 and 60 s "
                   "apart, and the job is green, saying PUBLISHED",
                   r["result"] == "success" and r["attempts"] == 3
                   and r["sleeps"] == ["30", "60"]
                   and "published on attempt 3" in r["summary"]
                   and listed in r["summary"], told(r))
                r = job("landed")
                ok("a timeout after which the Marketplace lists the version "
                   "counts: one attempt, and green",
                   r["result"] == "success" and r["attempts"] == 1
                   and not r["sleeps"] and listed in r["summary"], told(r))
                r = job("refused")
                ok("a token the Marketplace refuses is not tried again, and "
                   "the job is red",
                   r["result"] == "failure" and r["attempts"] == 1
                   and not r["sleeps"] and "not for an outage" in r["summary"]
                   and not_listed in r["summary"], told(r))
                r = job("ok", token="")
                ok("no VSCE_TOKEN: nothing is attempted, and the job is red",
                   r["result"] == "failure" and r["attempts"] == 0
                   and "no VSCE_TOKEN" in r["summary"]
                   and not_listed in r["summary"], told(r))
                r = job("refused", already=True)
                ok("a version already listed: nothing is attempted, and the "
                   "job is green",
                   r["result"] == "success" and r["attempts"] == 0
                   and r["steps"].get("publish") == "skipped"
                   and listed in r["summary"], told(r))
            print()
            print("the move_pins job's own steps, in bash, on a throwaway "
                  "repository with a simulated tag")
            print("-" * 62)
            pins_job = jobs["move_pins"]
            ok("the move_pins job runs once the tag is made, whatever the "
               "publishes after it did, and may write only contents and "
               "start only a workflow",
               "tag" in needs_of(pins_job)
               and "needs.tag.result == 'success'" in str(pins_job.get("if"))
               and "!cancelled()" in str(pins_job.get("if"))
               and pins_job.get("permissions") == {"contents": "write",
                                                   "actions": "write"},
               f"{pins_job.get('if')} {pins_job.get('permissions')}")
            names = tracked_files()
            pins_bash = posix_bash()
            if names is None or pins_bash is None:
                print("  skip     the move_pins job's steps (no git checkout, "
                      "or no POSIX bash here)")
            else:
                fx = PinFixture(names)
                tags_before = fx.tags()
                r = run_move_pins_job(pins_job, pins_bash, fx)
                tail = f"{r['steps']} {r['outputs']} log={r['log'][-1500:]}"
                head = fx.main()
                ok("a simulated tag: the job is green and main is one commit "
                   "past the tagged commit",
                   r["result"] == "success" and head != fx.sha
                   and git(fx.origin, "rev-parse", f"{head}^") == fx.sha
                   and git(fx.origin, "rev-list", "--count",
                           f"{fx.sha}..{head}") == "1", tail)
                message = git(fx.origin, "log", "-1", "--format=%B", head)
                ok("...whose message names the tag and says it is not a "
                   "release",
                   message.splitlines()[0]
                   == f"Move the Action pins to {fx.tag}"
                   and fx.sha in message and "not a release" in message,
                   message)
                touched = git(fx.origin, "diff", "--name-only", fx.sha,
                              head).splitlines()
                ok("...which changes README.md, EMBEDDING.md and pages under "
                   "docs/, and nothing else",
                   {"README.md", "EMBEDDING.md", "docs/embedding.html"}
                   <= set(touched)
                   and all(n in ("README.md", "EMBEDDING.md")
                           or n.startswith("docs/") for n in touched), touched)
                lines = [ln for ln in git(
                    fx.origin, "diff", "-U0", fx.sha, head, "--", "README.md",
                    "EMBEDDING.md").splitlines()
                    if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
                added = [ln[1:] for ln in lines if ln.startswith("+")]
                ok("...in those two documents exactly five lines: three pins, "
                   "the version: example and the pre-commit rev:",
                   len(lines) == 10 and len(added) == 5
                   and sum(f"sabline-lang@{fx.sha}  # {fx.tag}" in ln
                           for ln in added) == 3
                   and sum(f'version: "{fx.version}"' in ln
                           and f"({fx.version})" in ln for ln in added) == 1
                   and sum(ln.strip() == f"rev: {fx.tag}"
                           for ln in added) == 1, lines)
                ok("...no tag made or moved", fx.tags() == tags_before,
                   fx.tags())
                ok("...the tests started on main by name, once, because a "
                   "push made with GITHUB_TOKEN starts nothing",
                   fx.gh_log() == ["workflow run test.yml --ref main"],
                   fx.gh_log())
                git(fx.work, "fetch", "-q", "origin", "main")
                git(fx.work, "checkout", "-q", "--detach", "origin/main")
                answer = release_checks.gate(fx.work)
                ok("...and the gate says that commit is not a release",
                   not answer["release"] and not answer["refused"],
                   answer["line"])
                r = run_move_pins_job(pins_job, pins_bash, fx)
                ok("the job run again: nothing is pushed and no tests are "
                   "started again",
                   r["result"] == "success" and fx.main() == head
                   and r["outputs"].get("move", {}).get("pushed") == "false"
                   and len(fx.gh_log()) == 1,
                   f"{r['steps']} {r['outputs']} {fx.gh_log()} "
                   f"log={r['log'][-1500:]}")

                fx = PinFixture(names)
                later = fx.someone_pushes()
                r = run_move_pins_job(pins_job, pins_bash, fx)
                head = fx.main()
                ok("main moved on before the job ran: the pins are moved on "
                   "top of it, in one commit, naming the tagged commit",
                   r["result"] == "success"
                   and git(fx.origin, "rev-parse", f"{head}^") == later
                   and f"sabline-lang@{fx.sha}  # {fx.tag}" in git(
                       fx.origin, "show", f"{head}:README.md"),
                   f"{r['steps']} log={r['log'][-1500:]}")

                fx = PinFixture(names)
                git(fx.work, "tag", "-f", "-a", fx.tag, "-m", "moved",
                    git(fx.work, "commit-tree", "-m", "elsewhere",
                        f"{fx.sha}^{{tree}}"))
                git(fx.work, "push", "-q", "-f", "origin",
                    f"refs/tags/{fx.tag}")
                r = run_move_pins_job(pins_job, pins_bash, fx)
                ok("a tag that does not name the released commit: the job is "
                   "red and main is where it was",
                   r["result"] == "failure" and fx.main() == fx.sha
                   and not fx.gh_log(), f"{r['steps']} {fx.gh_log()}")
        except Unreadable as e:
            ok("release.yml is one this simulation can read", False, str(e))
    finally:
        release_checks.ENDPOINTS.update(saved)
        stand_in.shutdown()
        shutil.rmtree(SCRATCH, ignore_errors=True)

    print()
    print("perf: the median of three runs a side, not one run")
    print("-" * 62)
    import perf_gates

    def verdicts(new: list[float], ref: list[float]) -> list[bool]:
        numeric = {"ms": {"examples/bench.vel": {
            engine: {"working tree": perf_gates.summary(new),
                     "v8.2.0": perf_gates.summary(ref)}
            for engine in perf_gates.ENGINES}}}
        return [v["ok"] for v in perf_gates.gate(
            numeric, "working tree", "v8.2.0").values()]

    ok("one slow run of three does not fail a tree that is not slower",
       all(verdicts([1000, 4000, 1010], [1000, 990, 1005])))
    ok("...one fast run of three does not pass a tree 30% slower",
       not any(verdicts([1300, 900, 1310], [1000, 1000, 1000])))
    ok("...one fast run on the previous release's side does not fail a "
       "tree that is not slower",
       all(verdicts([1000, 1000, 1010], [600, 1000, 1000])))
    err = io.StringIO()
    refused: Any = None
    try:
        with contextlib.redirect_stderr(err):
            perf_gates.main(["--only", "numeric", "--against", "v8.2.0",
                             "--runs", "1"])
    except SystemExit as e:
        refused = e.code
    ok("...perf_gates.py --against refuses --runs 1, before it measures "
       "anything", refused == 2 and "at least 3 runs" in err.getvalue(),
       err.getvalue())
    runs = [int(n) for s in release_jobs()["perf"].get("steps", [])
            for n in re.findall(r"--runs (\d+)", str(s.get("run", "")))]
    ok("...and release.yml's perf job asks for at least that many",
       bool(runs) and min(runs) >= perf_gates.GATE_RUNS, runs)

    print()
    print(f"{passed} passed, {failed} broken")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
