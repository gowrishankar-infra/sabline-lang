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
manifest without both packages, a commit the tests did not pass on), the
release notes, the advisory detection and the draft-advisory request,
and the publish, registry and consistency checks against a stand-in for
PyPI, npm, the MCP registry, the Marketplace and GitHub. Nothing here
leaves 127.0.0.1.

    python check_release.py
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = HERE / "release_checks.py"
sys.path.insert(0, str(HERE))
import release_checks  # noqa: E402

SCRATCH = Path(tempfile.mkdtemp(prefix="velaris-release-check-"))
SERVER = release_checks.SERVER
REPOSITORY = release_checks.REPOSITORY

# the 24 files the v7.1.2 release holds, as GitHub listed them
V712_ASSETS = """SHA256SUMS
velaris-attestation-7.1.2.cosign.sigstore.json
velaris-attestation-7.1.2.intoto.json
velaris-attestation-7.1.2.sigstore-python.sigstore.json
velaris-lang-7.1.2.cdx.json
velaris-lang-7.1.2.cdx.json.sigstore.json
velaris-linux
velaris-linux.sha256
velaris-linux.sigstore.json
velaris-macos
velaris-macos.sha256
velaris-macos.sigstore.json
velaris-mcp-tools-7.1.2.json
velaris-mcp-tools-7.1.2.json.sigstore.json
velaris-windows.exe
velaris-windows.exe.sha256
velaris-windows.exe.sigstore.json
velaris.mcpb
velaris.mcpb.sha256
velaris.mcpb.sigstore.json
velaris_lang-7.1.2-py3-none-any.whl
velaris_lang-7.1.2-py3-none-any.whl.sigstore.json
velaris_lang-7.1.2.tar.gz
velaris_lang-7.1.2.tar.gz.sigstore.json""".split()


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


def write_versions(repo: Path, version: str,
                   overrides: dict | None = None) -> None:
    """The six version files, each saying `version` unless `overrides`
    names another for it; overrides["packages"] lists the registry
    manifest's package types."""
    said = dict(overrides or {})

    def at(name: str) -> str:
        return said.get(name, version)
    reg = at("integrations/mcp_registry/server.json")
    files = {
        "velaris.py": f'"""A stand-in."""\nVERSION = "{at("velaris.py")}"\n',
        "pyproject.toml": f'[project]\nname = "velaris-lang"\n'
                          f'version = "{at("pyproject.toml")}"\n',
        "npm/package.json": json.dumps(
            {"name": "velaris-lang", "version": at("npm/package.json")}),
        "mcpb/manifest.json": json.dumps(
            {"name": "velaris", "version": at("mcpb/manifest.json")}),
        "editor/vscode/package.json": json.dumps(
            {"name": "velaris", "version": at("editor/vscode/package.json")}),
        "integrations/mcp_registry/server.json": json.dumps({
            "name": SERVER, "version": reg,
            "packages": [{"registryType": kind, "identifier": "velaris-lang",
                          "version": reg}
                         for kind in said.get("packages", "pypi,npm")
                         .split(",") if kind]}),
    }
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip("\n") + "\n", encoding="utf-8")


BASE_ENTRY = ("7.1.2", "The proof cache could be lied to",
              "The proof cache moved to a per-user directory.")


def write_changelog(repo: Path, *entries: tuple[str, str, str]) -> None:
    (repo / "CHANGELOG.md").write_text(
        "# Velaris changelog\n\n" + "".join(
            f"## {v} - {title}\n\n{text}\n\n" for v, title, text in entries),
        encoding="utf-8")


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def base_repo(name: str, extra: dict | None = None) -> Path:
    """A repository at 7.1.2: a first commit tagged v2.36 (two parts, as
    the old tags are), then 7.1.2 tagged v7.1.2 - annotated, as today."""
    repo = SCRATCH / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("Velaris\n", encoding="utf-8")
    commit(repo, "the beginning")
    git(repo, "tag", "v2.36")
    write_versions(repo, "7.1.2")
    write_changelog(repo, BASE_ENTRY)
    for file, text in (extra or {}).items():
        (repo / file).write_text(text, encoding="utf-8")
    commit(repo, "v7.1.2: the proof cache could be lied to")
    git(repo, "tag", "-a", "v7.1.2", "-m",
        "v7.1.2: the proof cache could be lied to")
    return repo


def cli(*words: str, repo: Path | None = None):
    """Run release_checks.py as the workflow does: (exit code, stdout,
    stderr, the step outputs it wrote)."""
    outputs_file = Path(tempfile.mktemp(dir=SCRATCH, suffix=".out"))
    outputs_file.write_text("", encoding="utf-8")
    command = [sys.executable, str(CHECKS), *words,
               "--github-output", str(outputs_file), "--annotate"]
    if repo is not None:
        command += ["--repo", str(repo)]
    done = subprocess.run(command, capture_output=True, text=True,
                          cwd=str(SCRATCH))
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
    routes: dict = {}

    def _answer(self, method: str) -> None:
        status, body = self.routes.get((method, self.path.split("?")[0]),
                                       (404, {"detail": "not found"}))
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        self._answer("GET")

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        self._answer("POST")

    def log_message(self, *_) -> None:
        pass


def all_at(version: str) -> dict:
    """Every target serving `version` as the latest, as a release leaves
    them."""
    server = "/v0.1/servers/" + urllib.parse.quote(SERVER, safe="")
    assets = [{"name": n} for n in release_checks.expected_assets(version)]
    return {
        ("GET", f"/pypi/velaris-lang/{version}/json"): (200, {"info": {
            "version": version,
            "description": f"<!-- mcp-name: {SERVER} -->\n# Velaris"}}),
        ("GET", "/pypi/velaris-lang/json"): (200, {"info": {
            "version": version}}),
        ("GET", f"/velaris-lang/{version}"): (200, {
            "version": version, "mcpName": SERVER}),
        ("GET", "/velaris-lang"): (200, {"dist-tags": {"latest": version}}),
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


# ---- the cases -----------------------------------------------------------------

def main() -> int:
    passed = failed = 0

    def ok(label, condition, detail=""):
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
    (repo / "README.md").write_text("Velaris, in more words\n",
                                    encoding="utf-8")
    commit(repo, "README: more words")
    code, out, err, outputs = cli("gate", repo=repo)
    line = one_line(out) or ""
    ok("a docs-only commit is not a release: exit 0 and one notice line",
       code == 0 and line.startswith("::notice::no release:"), out + err)
    ok("...which says the version is already the newest tag, and tells the "
       "jobs after it to do nothing",
       "VERSION is 7.1.2 and v7.1.2 is already the newest tag" in line
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
    ok("a correct bump is a release: exit 0 and one notice line",
       code == 0 and line.startswith("::notice::release: 7.2.0"), out + err)
    ok("...handing the jobs after it the version, the tag, the commit and "
       "the tag before",
       outputs == {"release": "true", "build": "true", "version": "7.2.0",
                   "tag": "v7.2.0", "previous_tag": "v7.1.2", "sha": head},
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
       code == 0 and "no release: velaris.py says 7.2.0 but" in out
       and "npm/package.json says 7.1.2" in out
       and "server.json (npm package) says 7.1.2" in out
       and "pyproject.toml" not in out
       and outputs.get("release") == "false", out + err)

    repo = base_repo("older")
    write_versions(repo, "7.0.5")
    write_changelog(repo, BASE_ENTRY, ("7.0.5", "A backport", "..."))
    commit(repo, "7.0.5")
    code, out, err, outputs = cli("gate", repo=repo)
    ok("a version that is not newer than the newest tag is not a release",
       code == 0 and "7.0.5 is not newer than the newest tag, v7.1.2" in out
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
       len(claims) == 8 and None not in said and len(said) == 1, claims)
    ok("...and its CHANGELOG has an entry heading for its own VERSION",
       release_checks.changelog_entry(HERE, claims[0][1]) is not None,
       claims[0])

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
           "package": {"ecosystem": "pip", "name": "velaris-lang"},
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
    print("publishing: what is there already, and whether it all agrees")
    print("-" * 62)
    ok("a release's files are the 24 the v7.1.2 release holds, by name",
       sorted(release_checks.expected_assets("7.1.2")) == sorted(V712_ASSETS),
       set(release_checks.expected_assets("7.1.2")) ^ set(V712_ASSETS))

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

        StandIn.routes = {("GET", "/pypi/velaris-lang/7.2.0/json"):
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
        routes[("GET", "/pypi/velaris-lang/7.2.0/json")] = (200, {"info": {
            "version": "7.2.0", "description": "# Velaris"}})
        StandIn.routes = routes
        code, out = in_process("registry-ready", "7.2.0", "--annotate")
        ok("...and not while PyPI's description lacks the mcp-name marker",
           code == 1 and "::error::" in out and "mcp-name" in out, out)

        StandIn.routes = all_at("7.2.0")
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("consistent: PyPI, npm, the registry and the GitHub release all "
           "report 7.2.0 (exit 0)",
           code == 0 and "::notice::consistent" in out, out)
        routes = all_at("7.2.0")
        routes[("GET", "/velaris-lang")] = (200, {"dist-tags": {
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
                       if n != "velaris-macos.sigstore.json"]})
        StandIn.routes = routes
        code, out = in_process("consistent", "7.2.0", "--annotate")
        ok("...and a GitHub release missing one signature names that file",
           code == 1 and "the GitHub release (latest is v7.2.0, without "
                         "velaris-macos.sigstore.json)" in out, out)
    finally:
        release_checks.ENDPOINTS.update(saved)
        stand_in.shutdown()
        shutil.rmtree(SCRATCH, ignore_errors=True)

    print()
    print(f"{passed} passed, {failed} broken")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
