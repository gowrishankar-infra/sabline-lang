#!/usr/bin/env python3
"""Every question the release workflow asks, answerable on any machine.

A release of Velaris is made by .github/workflows/release.yml, and by
nothing and nobody else (RELEASING.md). Each decision that workflow
takes is made here rather than in its YAML, so that check_release.py can
hold it to fixtures and a person can ask the same question before
pushing:

    python release_checks.py gate              is this commit a release?
    python release_checks.py title 7.2.0       its CHANGELOG title
    python release_checks.py notes 7.2.0 --sha SHA --previous v7.1.2
    python release_checks.py published pypi 7.2.0
    python release_checks.py registry-ready 7.2.0 --timeout 900
    python release_checks.py consistent 7.2.0 --timeout 900
    python release_checks.py advisories v7.1.2 HEAD
    python release_checks.py advisory-body advisory-x.md -o advisory-x.json
    python release_checks.py advisory-commands advisory-x.md --tag v7.2.0

`--github-output FILE` also writes an answer as step outputs, `--summary
FILE` appends it to the job summary, and `--annotate` prints it as a
GitHub Actions notice. The standard library and git only; Python 3.10 or
later.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPOSITORY = "gowrishankar-infra/velaris-lang"
PACKAGE = "velaris-lang"                         # on PyPI and on npm
EXTENSION = "gowrishankar-infra.velaris"         # on the VS Code Marketplace
SERVER = "io.github.gowrishankar-infra/velaris"  # in the MCP registry
MCP_NAME = "mcp-name: " + SERVER                 # README.md, as PyPI serves it

# Where each target is asked. check_release.py points them at 127.0.0.1.
ENDPOINTS = {
    "pypi": "https://pypi.org",
    "npm": "https://registry.npmjs.org",
    "registry": "https://registry.modelcontextprotocol.io",
    "github": "https://api.github.com",
    "vscode": "https://marketplace.visualstudio.com",
}
NAMES = {"pypi": "PyPI", "npm": "npm", "registry": "the MCP registry",
         "github": "GitHub releases", "vscode": "the VS Code Marketplace"}
RETRY_WAIT = 10          # seconds between attempts at a target that failed

# The six files run_tests.py's check_versions holds to one version.
VERSION_FILES = ("velaris.py", "pyproject.toml", "npm/package.json",
                 "mcpb/manifest.json", "editor/vscode/package.json",
                 "integrations/mcp_registry/server.json")

# A CHANGELOG entry heading: "## 7.1.2 - The proof cache could be lied to"
ENTRY = re.compile(r"^## (\d+\.\d+(?:\.\d+)?) - (.+)$", re.M)

ADVISORY = "advisory-*.md"


class Unanswered(Exception):
    """A question that could not be answered. Never read as 'no'."""


# ---- versions, tags and the CHANGELOG ----------------------------------------

def parse_version(text) -> tuple[int, int, int] | None:
    """(major, minor, patch) of '7.2.0', 'v7.2.0' or '7.2'; None otherwise."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(text or "").strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)


def _read(root: Path, name: str) -> str | None:
    try:
        return (root / name).read_text(encoding="utf-8")
    except OSError:
        return None


def _load_json(text):
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return None


def version_claims(root: Path) -> list[tuple[str, str | None]]:
    """What each version file says, velaris.py first; None where a file
    or its field is missing. The registry manifest says it three times -
    its own, and one per package - and each of those is published."""
    claims: list[tuple[str, str | None]] = []
    for name, pattern in (("velaris.py", r'^VERSION = "([^"]*)"'),
                          ("pyproject.toml", r'^version = "([^"]*)"')):
        m = re.search(pattern, _read(root, name) or "", re.M)
        claims.append((name, m.group(1) if m else None))
    for name in VERSION_FILES[2:]:
        doc = _load_json(_read(root, name))
        doc = doc if isinstance(doc, dict) else {}
        claims.append((name, doc.get("version")))
        if name.endswith("server.json"):
            for package in doc.get("packages") or []:
                if isinstance(package, dict):
                    claims.append(
                        (f"{name} ({package.get('registryType')} package)",
                         package.get("version")))
    return claims


def registry_packages(root: Path) -> list[str]:
    """The registryType of every package the registry manifest lists."""
    doc = _load_json(_read(root, VERSION_FILES[-1]))
    packages = doc.get("packages") if isinstance(doc, dict) else None
    return sorted(str(p.get("registryType")) for p in packages or []
                  if isinstance(p, dict))


def changelog_entry(root: Path, version: str) -> tuple[str, str] | None:
    """(title, text) of CHANGELOG.md's entry for exactly `version`, or
    None. An X.Y.0 release may be headed X.Y, as every minor release in
    this CHANGELOG has been; X.Y never stands for X.Y.1."""
    text = _read(root, "CHANGELOG.md") or ""
    want = parse_version(version)
    if want is None:
        return None
    for m in ENTRY.finditer(text):
        if parse_version(m.group(1)) == want:
            rest = text[m.end():]
            following = re.search(r"^## ", rest, re.M)
            body = rest[:following.start()] if following else rest
            return m.group(2).strip(), body.strip()
    return None


def git(root: Path, *words: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *words],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise Unanswered(f"git {' '.join(words)}: {done.stderr.strip()}")
    return done.stdout.strip()


# ---- the gate ----------------------------------------------------------------

def gate(root: Path, expect_sha: str | None = None) -> dict:
    """Whether HEAD of `root` is a release: the step outputs, and 'line',
    the one line that says why. A release needs velaris.py's VERSION to be
    newer than every tag, a CHANGELOG entry heading for it, and every
    version file to agree with it. 'refused' is set when all of that holds
    but HEAD is not `expect_sha`, the commit the tests passed on."""
    claims = version_claims(root)
    version = claims[0][1] or ""
    head = git(root, "rev-parse", "HEAD")
    tags = [t for t in git(root, "tag", "--list", "v*").splitlines()
            if parse_version(t)]
    newest = max(tags, key=parse_version) if tags else ""
    answer = {"release": False, "refused": False, "version": version,
              "tag": f"v{version}" if version else "",
              "previous_tag": newest, "sha": head}

    def no(why: str) -> dict:
        answer["line"] = f"no release: {why}"
        return answer

    if parse_version(version) is None:
        return no('velaris.py has no VERSION = "X.Y.Z" line')
    tag = answer["tag"]
    if tag == newest:
        return no(f"VERSION is {version} and {tag} is already the newest "
                  f"tag")
    if tag in tags:
        return no(f"VERSION is {version} and {tag} already exists (the "
                  f"newest tag is {newest})")
    if newest and parse_version(version) <= parse_version(newest):
        return no(f"VERSION {version} is not newer than the newest tag, "
                  f"{newest}")
    if changelog_entry(root, version) is None:
        major, minor, patch = parse_version(version)
        forms = f"'## {version} - <title>'"
        if patch == 0 and version.count(".") == 2:
            forms += f" or '## {major}.{minor} - <title>'"
        return no(f"CHANGELOG.md has no entry heading for {version} (a "
                  f"line {forms})")
    disagree = [f"{name} says {said}" for name, said in claims[1:]
                if said != version]
    if disagree:
        return no(f"velaris.py says {version} but " + ", ".join(disagree))
    kinds = registry_packages(root)
    if "pypi" not in kinds or "npm" not in kinds:
        return no(f"{VERSION_FILES[-1]} must list both the pypi and the npm "
                  f"package; it lists {', '.join(kinds) or 'none'}")
    if expect_sha and head != expect_sha:
        answer["refused"] = True
        answer["line"] = (
            f"refused: the tests passed on {expect_sha[:12]}, but main is at "
            f"{head[:12]}; a release is only the commit its tests passed on, "
            f"so {head[:12]}'s own test run decides whether it is {tag}")
        return answer
    answer["release"] = True
    answer["line"] = (f"release: {version} - tagging {head[:12]} as {tag} "
                      f"(the newest tag was {newest or 'none'})")
    return answer


# ---- asking PyPI, npm, the registry, the Marketplace and GitHub --------------

def _github_auth(base: str) -> dict:
    """GitHub's token, only ever for api.github.com."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token and base == "https://api.github.com":
        return {"Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28"}
    return {}


def _fetch(url: str, *, data: bytes | None = None,
           headers: dict | None = None, attempts: int = 3):
    """(status, body). An HTTP status is an answer, 404 included; a
    network failure or a 5xx on every attempt is not, and raises."""
    head = {"User-Agent": "velaris-release-checks",
            "Accept": "application/json"}
    head.update(headers or {})
    last = ""
    for attempt in range(attempts):
        request = urllib.request.Request(url, data=data, headers=head)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                return e.code, e.read()
            last = f"HTTP {e.code}"
        except (urllib.error.URLError, OSError) as e:
            last = str(e)
        if attempt + 1 < attempts:
            time.sleep(RETRY_WAIT)
    raise Unanswered(f"no answer from {url}: {last}")


def _json_of(raw: bytes):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _dig(doc, *keys):
    for key in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(key)
    return doc


def _server_path() -> str:
    return "/v0.1/servers/" + urllib.parse.quote(SERVER, safe="")


def marketplace_versions() -> list[str]:
    body = json.dumps({"filters": [{"criteria": [
        {"filterType": 7, "value": EXTENSION}]}], "flags": 1}).encode()
    status, raw = _fetch(
        ENDPOINTS["vscode"] + "/_apis/public/gallery/extensionquery",
        data=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json;api-version=3.0-preview.1"})
    doc = _json_of(raw)
    if status != 200 or not isinstance(doc, dict):
        raise Unanswered(f"the Marketplace answered HTTP {status}")
    return [str(v.get("version"))
            for result in doc.get("results") or []
            for extension in result.get("extensions") or []
            for v in extension.get("versions") or []]


def published(target: str, version: str) -> bool:
    """Whether `version` is already at `target`."""
    base = ENDPOINTS[target]
    if target == "vscode":
        return version in marketplace_versions()
    url = {"pypi": f"{base}/pypi/{PACKAGE}/{version}/json",
           "npm": f"{base}/{PACKAGE}/{version}",
           "registry": f"{base}{_server_path()}/versions/{version}",
           "github": f"{base}/repos/{REPOSITORY}/releases/tags/v{version}",
           }[target]
    status, _ = _fetch(url, headers=_github_auth(base)
                       if target == "github" else None)
    if status == 200:
        return True
    if status == 404:
        return False
    raise Unanswered(f"{NAMES[target]} answered HTTP {status} about "
                     f"{version}")


def registry_prerequisites(version: str) -> list[str]:
    """What the MCP registry checks before it accepts this version and
    would not find yet: each package, at exactly this version, naming
    the server. Empty when it would find both."""
    missing = []
    status, raw = _fetch(f"{ENDPOINTS['pypi']}/pypi/{PACKAGE}/{version}/json")
    if status != 200:
        missing.append(f"PyPI does not serve {PACKAGE} {version} yet")
    elif MCP_NAME not in str(_dig(_json_of(raw), "info", "description")):
        missing.append(f"PyPI's {version} description lacks '{MCP_NAME}'")
    status, raw = _fetch(f"{ENDPOINTS['npm']}/{PACKAGE}/{version}")
    if status != 200:
        missing.append(f"npm does not serve {PACKAGE}@{version} yet")
    elif _dig(_json_of(raw), "mcpName") != SERVER:
        missing.append(f"npm's {version} package.json does not have "
                       f"mcpName {SERVER}")
    return missing


def expected_assets(version: str) -> list[str]:
    """Every file a release's GitHub page holds: the nine artefacts - the
    wheel, the sdist, the SBOM, the MCP tool manifest, the .mcpb bundle,
    three executables and the attestation - with their signatures and
    checksums."""
    signed = [f"velaris_lang-{version}-py3-none-any.whl",
              f"velaris_lang-{version}.tar.gz",
              f"velaris-lang-{version}.cdx.json",
              f"velaris-mcp-tools-{version}.json"]
    names = ["SHA256SUMS"] + signed + [f + ".sigstore.json" for f in signed]
    for single in ("velaris-linux", "velaris-macos", "velaris-windows.exe",
                   "velaris.mcpb"):
        names += [single, single + ".sha256", single + ".sigstore.json"]
    names += [f"velaris-attestation-{version}.intoto.json",
              f"velaris-attestation-{version}.cosign.sigstore.json",
              f"velaris-attestation-{version}.sigstore-python.sigstore.json"]
    return names


def consistency(version: str) -> list[tuple[str, str, bool]]:
    """(target, what it reports, whether that is `version`) for PyPI, npm,
    the MCP registry and the GitHub release."""
    rows = []
    status, raw = _fetch(f"{ENDPOINTS['pypi']}/pypi/{PACKAGE}/json")
    said = _dig(_json_of(raw), "info", "version") if status == 200 else None
    rows.append(("PyPI", f"latest is {said}" if said else f"HTTP {status}",
                 said == version))
    status, raw = _fetch(f"{ENDPOINTS['npm']}/{PACKAGE}", headers={
        "Accept": "application/vnd.npm.install-v1+json"})
    said = _dig(_json_of(raw), "dist-tags", "latest") \
        if status == 200 else None
    rows.append(("npm", f"latest is {said}" if said else f"HTTP {status}",
                 said == version))
    status, raw = _fetch(
        f"{ENDPOINTS['registry']}{_server_path()}/versions/latest")
    said = _dig(_json_of(raw), "server", "version") \
        if status == 200 else None
    rows.append(("the MCP registry",
                 f"latest is {said}" if said else f"HTTP {status}",
                 said == version))
    base = ENDPOINTS["github"]
    status, raw = _fetch(f"{base}/repos/{REPOSITORY}/releases/latest",
                         headers=_github_auth(base))
    doc = _json_of(raw) if status == 200 else None
    tag = _dig(doc, "tag_name")
    held = {str(_dig(a, "name")) for a in _dig(doc, "assets") or []}
    lacks = [n for n in expected_assets(version) if n not in held]
    if tag is None:
        report = f"HTTP {status}"
    elif lacks:
        report = f"latest is {tag}, without {', '.join(lacks)}"
    else:
        report = f"latest is {tag}, with all {len(held)} files"
    rows.append(("the GitHub release", report,
                 tag == f"v{version}" and not lacks))
    return rows


# ---- advisories --------------------------------------------------------------

def added_advisories(root: Path, since: str, until: str = "HEAD") -> list[str]:
    """The advisory-*.md files the commits after `since`, up to `until`,
    add - wherever they are. One that is only edited or renamed is not
    new."""
    if since:
        names = git(root, "diff", "--find-renames", "--diff-filter=A",
                    "--name-only", since, until)
    else:
        names = git(root, "ls-tree", "-r", "--name-only", until)
    return [n for n in names.splitlines()
            if fnmatch.fnmatch(n.rsplit("/", 1)[-1], ADVISORY)]


def _section(text: str, title: str) -> str | None:
    m = re.search(rf"^## {re.escape(title)}\s*$", text, re.M | re.I)
    if not m:
        return None
    rest = text[m.end():]
    following = re.search(r"^## ", rest, re.M)
    return rest[:following.start()] if following else rest


def advisory_body(text: str) -> dict:
    """The request body for POST /repos/{owner}/{repo}/security-advisories,
    which makes a draft. From an advisory written like
    advisory-proof-cache.md: its '# ' title is the summary, everything from
    its first '## ' section is the description, '## Affected versions' says
    'A through B' and 'Fixed in C', and a CVSS vector string, if there is
    one, gives the severity. A '## CWE' section may name CWE ids."""
    title = next((line[2:].strip() for line in text.splitlines()
                  if line.startswith("# ")), "")
    if not title:
        raise Unanswered("the advisory has no '# ' title line to use as its "
                         "summary")
    summary = re.sub(r"^security advisory:\s*", "", title, flags=re.I)
    first = re.search(r"^## ", text, re.M)
    if not first:
        raise Unanswered("the advisory has no '## ' section to use as its "
                         "description")
    affected = _section(text, "Affected versions")
    if affected is None:
        raise Unanswered("the advisory has no '## Affected versions' section")
    span = re.search(r"(\d+(?:\.\d+)*)\**\s+through\s+\**(\d+(?:\.\d+)*)",
                     affected)
    fixed = re.search(r"fixed in\s+\**(\d+(?:\.\d+)*)", affected, re.I)
    if not (span and fixed):
        raise Unanswered("the '## Affected versions' section must say "
                         "'A through B' and 'Fixed in C'")
    body = {
        "summary": summary[:1024],
        "description": text[first.start():].strip(),
        "vulnerabilities": [{
            "package": {"ecosystem": "pip", "name": PACKAGE},
            "vulnerable_version_range":
                f">= {span.group(1)}, <= {span.group(2)}",
            "patched_versions": fixed.group(1),
            "vulnerable_functions": [],
        }],
    }
    cvss = re.search(r"CVSS:(?:3\.[01]|4\.0)(?:/[A-Za-z]+:[A-Za-z])+", text)
    if cvss:
        body["cvss_vector_string"] = cvss.group(0)
    cwes = sorted(set(re.findall(r"\bCWE-\d+\b", _section(text, "CWE") or "")))
    if cwes:
        body["cwe_ids"] = cwes
    return body


def advisory_commands(path: str) -> list[str]:
    """What a maintainer runs, from a checkout of the release, to make the
    draft advisory and request its CVE. The same line works in bash and in
    PowerShell."""
    request = Path(path).with_suffix(".json").name
    api = f"repos/{REPOSITORY}/security-advisories"
    return [
        f"python release_checks.py advisory-body {path} -o {request}",
        f'gh api --method POST "{api}/$(gh api --method POST {api} '
        f'--input {request} --jq .ghsa_id)/cve"',
    ]


# ---- the command line --------------------------------------------------------

def _escape(line: str) -> str:
    return line.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit(args, line: str, level: str | None = "notice", **outputs) -> None:
    """Print one line - as a notice, a warning or an error with --annotate -
    and write it to the summary and its outputs to the step outputs."""
    print(f"::{level}::{_escape(line)}" if args.annotate and level else line)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(line + "\n\n")
    if args.github_output and outputs:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            for key, value in outputs.items():
                fh.write(f"{key}={value}\n")


def _write(args, text: str) -> None:
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def cmd_gate(args) -> int:
    answer = gate(Path(args.repo), args.expect_sha)
    line = answer["line"]
    if args.dry_run:
        line = "dry run, nothing is tagged or published - " + line
    release = answer["release"] and not args.dry_run
    emit(args, line, "error" if answer["refused"] and not args.dry_run
         else "notice",
         release=str(release).lower(),
         build=str(answer["release"] or args.dry_run).lower(),
         version=answer["version"], tag=answer["tag"],
         previous_tag=answer["previous_tag"], sha=answer["sha"])
    return 1 if answer["refused"] and not args.dry_run else 0


def cmd_title(args) -> int:
    entry = changelog_entry(Path(args.repo), args.version)
    if entry is None:
        print(f"CHANGELOG.md has no entry for {args.version}", file=sys.stderr)
        return 2
    print(entry[0])
    return 0


def cmd_notes(args) -> int:
    entry = changelog_entry(Path(args.repo), args.version)
    if entry is None:
        print(f"CHANGELOG.md has no entry for {args.version}", file=sys.stderr)
        return 2
    tag, sha = f"v{args.version}", args.sha
    at = f"https://github.com/{REPOSITORY}/blob/{sha}"
    parts = [
        entry[1], "", "---", "",
        f"Made by [release.yml]({at}/.github/workflows/release.yml) after "
        f"every leg of the tests passed on {sha}. Nobody tagged it by hand "
        f"([RELEASING.md]({at}/RELEASING.md)).",
        "",
        f"`{tag}` is an annotated tag and is **not signed**: the workflow "
        f"holds no signing key, and a keyless signature made in Actions "
        f"(gitsign) is one GitHub does not show as verified. Every file "
        f"below is signed with sigstore as `release.yml@refs/heads/main`, "
        f"and its certificate names this commit; "
        f"[SECURITY.md]({at}/SECURITY.md#verifying-a-download) says how to "
        f"check one.",
    ]
    if args.previous:
        parts += ["", f"**Full Changelog**: https://github.com/{REPOSITORY}"
                      f"/compare/{args.previous}...{tag}"]
    _write(args, "\n".join(parts) + "\n")
    return 0


def cmd_published(args) -> int:
    where = NAMES[args.target]
    try:
        there = published(args.target, args.version)
    except Unanswered as e:
        emit(args, f"could not tell whether {args.version} is on {where}, so "
                   f"nothing was published there: {e}", "error")
        return 2
    if there:
        emit(args, f"{args.version} is already on {where}; skipping that "
                   f"publish", published="true")
    else:
        emit(args, f"{args.version} is not on {where} yet; publishing it",
             None, published="false")
    return 0


def _poll(args, ask):
    """Ask until the answer is good or --timeout runs out: (good, rows)."""
    deadline = time.monotonic() + args.timeout
    while True:
        good, rows = ask()
        if good or time.monotonic() >= deadline:
            return good, rows
        print("not yet: " + "; ".join(rows), flush=True)
        time.sleep(args.interval)


def cmd_registry_ready(args) -> int:
    def ask():
        try:
            missing = registry_prerequisites(args.version)
        except Unanswered as e:
            missing = [str(e)]
        return not missing, missing
    good, missing = _poll(args, ask)
    if good:
        emit(args, f"PyPI and npm both serve {args.version} naming {SERVER}",
             None)
        return 0
    emit(args, "the MCP registry would refuse this publish: "
               + "; ".join(missing), "error")
    return 1


def cmd_consistent(args) -> int:
    def ask():
        try:
            rows = consistency(args.version)
        except Unanswered as e:
            return False, [str(e)]
        return all(agrees for _, _, agrees in rows), rows
    good, rows = _poll(args, ask)
    if rows and isinstance(rows[0], str):
        emit(args, f"could not check that every target reports "
                   f"{args.version}: {rows[0]}", "error")
        return 1
    for target, report, agrees in rows:
        print(f"  {'ok' if agrees else 'DIFFERS':8} {target}: {report}")
    if good:
        emit(args, f"consistent: PyPI, npm, the MCP registry and the GitHub "
                   f"release all report {args.version}")
        return 0
    differ = [f"{target} ({report})" for target, report, agrees in rows
              if not agrees]
    emit(args, f"inconsistent: {', '.join(differ)} - "
               f"{'does' if len(differ) == 1 else 'do'} not report "
               f"{args.version}", "error")
    return 1


def cmd_advisories(args) -> int:
    for name in added_advisories(Path(args.repo), args.since, args.until):
        print(name)
    return 0


def cmd_advisory_body(args) -> int:
    try:
        text = Path(args.file).read_text(encoding="utf-8")
        body = advisory_body(text)
    except (OSError, Unanswered) as e:
        print(f"advisory-body: {args.file}: {e}", file=sys.stderr)
        return 2
    _write(args, json.dumps(body, indent=2, ensure_ascii=args.output is None)
           + "\n")
    return 0


def cmd_advisory_commands(args) -> int:
    tag = args.tag or "the release"
    emit(args, f"{args.file} is new in {tag}. No advisory was created: "
               f"GITHUB_TOKEN cannot be given the permission to create one. "
               f"From a checkout of {tag}, run the two commands below; they "
               f"make a DRAFT advisory and request its CVE, and publish "
               f"nothing", "warning")
    commands = advisory_commands(args.file)
    for command in commands:
        print(command)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write("```\n" + "\n".join(commands) + "\n```\n\n")
    return 0


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo", default=".",
                        help="the repository (default: here)")
    common.add_argument("--github-output", metavar="FILE",
                        help="also write the answer as step outputs")
    common.add_argument("--summary", metavar="FILE",
                        help="also append the answer to a job summary")
    common.add_argument("--annotate", action="store_true",
                        help="print as a GitHub Actions notice")
    parser = argparse.ArgumentParser(
        prog="release_checks.py",
        description="The questions release.yml asks. RELEASING.md.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("gate", parents=[common],
                       help="is HEAD a release?")
    p.add_argument("--expect-sha", help="the commit the tests passed on")
    p.add_argument("--dry-run", action="store_true",
                   help="decide, but release nothing")
    p.set_defaults(run=cmd_gate)

    p = sub.add_parser("title", parents=[common],
                       help="the CHANGELOG title of a version")
    p.add_argument("version")
    p.set_defaults(run=cmd_title)

    p = sub.add_parser("notes", parents=[common],
                       help="the GitHub release notes of a version")
    p.add_argument("version")
    p.add_argument("--sha", required=True)
    p.add_argument("--previous", default="")
    p.add_argument("-o", "--output")
    p.set_defaults(run=cmd_notes)

    p = sub.add_parser("published", parents=[common],
                       help="is a version already at a target?")
    p.add_argument("target", choices=sorted(ENDPOINTS))
    p.add_argument("version")
    p.set_defaults(run=cmd_published)

    for name, run, what in (
            ("registry-ready", cmd_registry_ready,
             "do PyPI and npm serve a version the registry will accept?"),
            ("consistent", cmd_consistent,
             "do PyPI, npm, the registry and the release all report it?")):
        p = sub.add_parser(name, parents=[common], help=what)
        p.add_argument("version")
        p.add_argument("--timeout", type=float, default=0,
                       help="seconds to keep asking (default: ask once)")
        p.add_argument("--interval", type=float, default=30)
        p.set_defaults(run=run)

    p = sub.add_parser("advisories", parents=[common],
                       help="advisory-*.md files added since a tag")
    p.add_argument("since")
    p.add_argument("until", nargs="?", default="HEAD")
    p.set_defaults(run=cmd_advisories)

    p = sub.add_parser("advisory-body", parents=[common],
                       help="the draft-advisory request for an advisory")
    p.add_argument("file")
    p.add_argument("-o", "--output")
    p.set_defaults(run=cmd_advisory_body)

    p = sub.add_parser("advisory-commands", parents=[common],
                       help="the gh commands that make that draft")
    p.add_argument("file")
    p.add_argument("--tag", default="")
    p.set_defaults(run=cmd_advisory_commands)

    args = parser.parse_args(argv)
    try:
        return args.run(args)
    except Unanswered as e:
        print(f"release_checks.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
