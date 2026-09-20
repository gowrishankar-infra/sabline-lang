#!/usr/bin/env python3
"""Every question the release workflow asks, answerable on any machine.

A release of Sabline is made by .github/workflows/release.yml, and by
nothing and nobody else (RELEASING.md). Each decision that workflow
takes is made here rather than in its YAML, so that check_release.py can
hold it to fixtures and a person can ask the same question before
pushing:

    python release_checks.py gate              is this commit a release?
    python release_checks.py covered v8.1.1    what it changes that a minor
                                               release must explain
    python release_checks.py paused            does RELEASE_PAUSED stop it?
    python release_checks.py title 7.2.0       its CHANGELOG title
    python release_checks.py notes 7.2.0 --sha SHA --previous v7.1.2
    python release_checks.py published pypi 7.2.0
    python release_checks.py published vscode 7.2.0 --require --timeout 900
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
import ast
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
from typing import Any, Callable, cast

REPOSITORY = "gowrishankar-infra/sabline-lang"
PACKAGE = "sabline-lang"                         # on PyPI and on npm
EXTENSION = "gowrishankar-infra.sabline"         # on the VS Code Marketplace
SERVER = "io.github.gowrishankar-infra/sabline"  # in the MCP registry
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

# The six files run_tests.py's check_versions holds to one version. The
# first was sabline.py until 8.2 made the compiler a package; a repository
# of that shape - an older tag, a fixture - is still read.
VERSION_FILES = ("sabline/version.py", "pyproject.toml", "npm/package.json",
                 "mcpb/manifest.json", "editor/vscode/package.json",
                 "integrations/mcp_registry/server.json")
OLD_VERSION_FILE = "sabline.py"

# A CHANGELOG entry heading: "## 7.1.2 - The proof cache could be lied to"
ENTRY = re.compile(r"^## (\d+\.\d+(?:\.\d+)?) - (.+)$", re.M)

ADVISORY = "advisory-*.md"


class Unanswered(Exception):
    """A question that could not be answered. Never read as 'no'."""


# ---- versions, tags and the CHANGELOG ----------------------------------------

def parse_version(text: Any) -> tuple[int, int, int] | None:
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


def _load_json(text: Any) -> Any:
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return None


def version_claims(root: Path) -> list[tuple[str, str | None]]:
    """What each version file says, the compiler's first; None where a file
    or its field is missing. The registry manifest says it three times -
    its own, and one per package - and each of those is published."""
    claims: list[tuple[str, str | None]] = []
    first = (OLD_VERSION_FILE if not (root / VERSION_FILES[0]).exists()
             and (root / OLD_VERSION_FILE).exists() else VERSION_FILES[0])
    for name, pattern in ((first, r'^VERSION = "([^"\r\n]*)"'),
                          ("pyproject.toml", r'^version = "([^"\r\n]*)"')):
        m = re.search(pattern, _read(root, name) or "", re.M)
        claims.append((name, m.group(1) if m else None))
    for name in VERSION_FILES[2:]:
        doc = _load_json(_read(root, name))
        doc = doc if isinstance(doc, dict) else {}
        claims.append((name, doc.get("version")))
        if name.endswith("server.json"):
            listed = doc.get("packages")
            for package in listed if isinstance(listed, list) else []:
                if isinstance(package, dict):
                    claims.append(
                        (f"{name} ({package.get('registryType')} package)",
                         package.get("version")))
    return claims


def registry_packages(root: Path) -> list[str]:
    """The registryType of every package the registry manifest lists."""
    doc = _load_json(_read(root, VERSION_FILES[-1]))
    packages = doc.get("packages") if isinstance(doc, dict) else None
    if not isinstance(packages, list):
        return []
    return sorted(str(p.get("registryType")) for p in packages
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


# ---- what a release changes that STABILITY.md covers ---------------------------

# A default that is a value: a change to one changes what a command line, a
# door or the library does when nobody says (STABILITY.md: the command line,
# and the budget a command line with no --allow installs). Every module-level
# name DEFAULT_* or *_DEFAULT counts, and these.
KNOWN_DEFAULTS = ("MAX_READ_BYTES", "PROOF_SECONDS", "FLOAT_PROOF_SECONDS",
                  "DOOR_MAX_TIMEOUT", "DOOR_MAX_MEMORY_MB", "DOOR_RATE_LIMIT")
DEFAULT_NAME = re.compile(r"^(?:DEFAULT_\w+|\w+_DEFAULT)$")
# the library STABILITY.md covers, whose parameters' defaults count too
COVERED_CALLS = ("check", "audit", "run", "attest", "card")
COVERED_CLASS = "Pool"
FLAG = re.compile(r"--[a-z][a-z0-9]*(?:-[a-z0-9]+)*")
# the variables of the run state: what a run starts from when nobody says
STATE_MODULE = "sabline/state.py"
STATE_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
CODE = re.compile(r"E\d{3}")
PLACEHOLDER = re.compile(r"(?:todo|tbd|fixme|xxx|placeholder)\b", re.I)
COMPATIBILITY_LINE = "compatibility:"
API_LINE = "api:"
API_GOLDEN = "tests/api/golden.json"


# What the package and the MCP server were called before 8.6 renamed the
# project. A tag before v8.6.0 holds sabline/ under the name velaris/, so
# a gate that looked only for sabline/ would read the previous release as
# having no compiler at all - and then report every error code, every flag
# and every default as added. The paths are mapped back to the names this
# version uses, so a rename shows as nothing and a real change still shows.
# Delete this in 9.0, once no tag the gate compares against predates 8.6.
RENAMED_IN_8_6 = {"velaris": "sabline", "velaris_mcp.py": "sabline_mcp.py",
                  "velaris.py": OLD_VERSION_FILE}


def _as_named_now(path: str) -> str:
    """A path at an earlier tag, under the name this version gives it."""
    for old, new in RENAMED_IN_8_6.items():
        if path == old:
            return new
        if path.startswith(old + "/"):
            return new + path[len(old):]
    return path


def sabline_sources(root: Path, ref: str | None = None) -> dict[str, str]:
    """{path: text} of Sabline's own Python - every module of the package,
    in a sub-package too, or sabline.py before 8.2, and the MCP server - in
    the working tree, or at a git ref. A file that cannot be read as UTF-8
    text is a question the gate cannot answer, never an empty module.

    At a ref before v8.6.0 the package is velaris/, which is the same
    modules under the name the project had; each is returned under the name
    it has now, so that the rename itself is not read as a change."""
    single = (OLD_VERSION_FILE, "sabline_mcp.py")
    if ref is None:
        paths = sorted(p.relative_to(root).as_posix()
                       for p in (root / "sabline").rglob("*.py") if p.is_file())
        paths += [n for n in single if (root / n).is_file()]
        found: dict[str, str] = {}
        for p in paths:
            try:
                found[p] = (root / p).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                raise Unanswered(f"{p} cannot be read as UTF-8 text ({e})")
        return found
    listed = git(root, "ls-tree", "-r", "--name-only", ref, "--", "sabline",
                 *single, *RENAMED_IN_8_6)
    wanted = re.compile(r"(?:sabline|velaris)/.+\.py")
    paths = [p for p in listed.splitlines()
             if p in single or p in RENAMED_IN_8_6 or wanted.fullmatch(p)]
    # The shim package velaris/ that 8.6 adds is not the compiler; at a ref
    # from 8.6 on, sabline/ is, and velaris/ is three lines of alias.
    if any(p.startswith("sabline/") for p in paths):
        paths = [p for p in paths if not p.startswith("velaris/")
                 and p != "velaris.py" and p != "velaris_mcp.py"]
    return {_as_named_now(p): git(root, "show", f"{ref}:{p}") for p in paths}


def _trees(sources: dict[str, str]) -> list[Any]:
    trees = []
    for path, source in sorted(sources.items()):
        try:
            trees.append(ast.parse(source))
        except (SyntaxError, ValueError, RecursionError, MemoryError) as e:
            raise Unanswered(f"{path} does not parse: {type(e).__name__}: {e}")
    return trees


def error_codes(sources: dict[str, str]) -> set[str]:
    """Every error code the compiler's source holds: every text that is one
    code and nothing else, wherever it is written. ERROR_TABLE's keys are
    such texts, and so is a code added by a subscript, by update(), through
    a splat or in a sub-package, which the literal table alone did not show
    (8.2, the adversarial pass). A code built from pieces while running
    is not seen."""
    return {n.value for tree in _trees(sources) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and CODE.fullmatch(n.value)}


def cli_flags(sources: dict[str, str]) -> set[str]:
    """Every flag the command line and the MCP server know: a text that is
    one --flag and nothing else, wherever it is written."""
    return {n.value for tree in _trees(sources) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and FLAG.fullmatch(n.value)}


def _constants(trees: list[Any]) -> dict[str, list[Any]]:
    """{name: [value, ...]} of every module-level assignment to a name."""
    values: dict[str, list[Any]] = {}
    for tree in trees:
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) \
                    and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                for t in targets:
                    if isinstance(t, ast.Name):
                        values.setdefault(t.id, []).append(node.value)
    return values


def _resolved(expr: Any, values: dict[str, list[Any]], depth: int = 0) -> str:
    """An expression's source, with each name of a module constant that is
    assigned once replaced by that constant's own expression, five deep: a
    default read from another constant changes when that one does."""
    import copy

    class Inline(ast.NodeTransformer):
        def visit_Name(self, node: ast.Name) -> Any:
            got = values.get(node.id)
            if depth < 5 and got and len(got) == 1 \
                    and isinstance(node.ctx, ast.Load):
                inner = _resolved(got[0], values, depth + 1)
                return ast.parse(inner, mode="eval").body
            return node
    return ast.unparse(Inline().visit(copy.deepcopy(expr)))


def state_names(sources: dict[str, str]) -> set[str]:
    """The run state's variables: sabline/state.py's module-level names."""
    if STATE_MODULE not in sources:
        return set()
    return {name for name in _constants(_trees({STATE_MODULE:
                                                 sources[STATE_MODULE]}))
            if STATE_NAME.match(name)}


def defaults(sources: dict[str, str],
             watched: set[str] | frozenset[str] = frozenset()) -> dict[str, str]:
    """Every default, as source text with other constants read through: a
    module-level constant named as one, a variable of the run state
    (`watched`), and the default of each parameter of the library
    STABILITY.md covers. A name defined in two modules is both texts. A
    default computed in a function body is not seen."""
    trees = _trees(sources)
    values = _constants(trees)
    found_all: dict[str, list[str]] = {}
    for tree in trees:
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) \
                    and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) \
                    else [node.target]
                for t in targets:
                    name = getattr(t, "id", None)
                    if name and (DEFAULT_NAME.match(name)
                                 or name in KNOWN_DEFAULTS
                                 or name in watched):
                        found_all.setdefault(name, []).append(
                            _resolved(node.value, values))
            functions = []
            if isinstance(node, ast.FunctionDef) and node.name in COVERED_CALLS:
                functions.append((node.name, node))
            if isinstance(node, ast.ClassDef) and node.name == COVERED_CLASS:
                functions += [(f"{node.name}.{f.name}", f) for f in node.body
                              if isinstance(f, ast.FunctionDef)
                              and (f.name == "__init__"
                                   or not f.name.startswith("_"))]
            for label, fn in functions:
                args = fn.args
                positional = args.posonlyargs + args.args
                for a, d in zip(positional[len(positional)
                                           - len(args.defaults):],
                                args.defaults):
                    found_all.setdefault(f"{label}({a.arg})", []).append(
                        _resolved(d, values))
                for a, kd in zip(args.kwonlyargs, args.kw_defaults):
                    if kd is not None:
                        found_all.setdefault(f"{label}({a.arg})", []).append(
                            _resolved(kd, values))
    return {k: " | ".join(sorted(v)) for k, v in found_all.items()}


def covered_changes(root: Path, since: str) -> list[str]:
    """What the commits after `since` change that STABILITY.md covers and a
    minor or patch release must explain: an error code added to the table,
    a flag no longer known, a default that is not what it was."""
    before, after = sabline_sources(root, since), sabline_sources(root)
    out = [f"adds the error code {c}"
           for c in sorted(error_codes(after) - error_codes(before))]
    out += [f"removes the flag {f}"
            for f in sorted(cli_flags(before) - cli_flags(after))]
    watched = state_names(before) | state_names(after)
    was, now = defaults(before, watched), defaults(after, watched)
    out += [f"changes the default {k} from {was[k]} to {now[k]}"
            for k in sorted(set(was) & set(now)) if was[k] != now[k]]
    # a parameter that had a default and has none: a call that left it out
    # no longer works
    out += [f"removes the default of {k}, which was {was[k]}"
            for k in sorted(set(was) - set(now)) if "(" in k]
    return out


def says(body: str, prefix: str) -> bool:
    """Whether a CHANGELOG entry makes the statement `prefix` asks for: a
    line of prose beginning with it at the start of the line, followed by
    what it says - four words at least, and not a placeholder. A line inside
    a fenced or an indented code block or an HTML comment, one with nothing
    after the colon, and one saying TODO do not count: before the 8.2
    adversarial pass each of them let a new error code through."""
    fence, comment = "", False
    for raw in body.splitlines():
        text = raw.strip()
        if comment:
            comment = "-->" not in text
            continue
        if fence:
            if text.startswith(fence):
                fence = ""
            continue
        opening = re.match(r"(`{3,}|~{3,})", text)
        if opening:
            fence = opening.group(1)
            continue
        if text.startswith("<!--"):
            comment = "-->" not in text[4:]
            continue
        if raw[:1] in (" ", "\t") or not raw.lower().startswith(prefix):
            continue
        said = raw[len(prefix):].strip()
        if len(said.split()) >= 4 and not PLACEHOLDER.match(said):
            return True
    return False


def api_golden_changed(root: Path, since: str) -> bool:
    """Whether tests/api/golden.json differs from the one at `since`; False
    when `since` has none (8.2.0 is the first release with one)."""
    try:
        before = git(root, "show", f"{since}:{API_GOLDEN}")
    except Unanswered:
        return False
    return cast(bool, _load_json(before) != _load_json(_read(root, API_GOLDEN)))


# ---- the gate ----------------------------------------------------------------

def gate(root: Path, expect_sha: str | None = None) -> dict[Any, Any]:
    """Whether HEAD of `root` is a release: the step outputs, and 'line',
    the one line that says why. A release needs the compiler's VERSION to be
    newer than every tag, a CHANGELOG entry heading for it, and every
    version file to agree with it. 'refused' is set when all of that holds
    but a minor or patch release changes what STABILITY.md covers - an error
    code added, a flag removed, a default changed - and its entry has no
    line beginning 'compatibility:'; or the API golden moved and the entry
    has no line beginning 'api:'; or HEAD is not `expect_sha`, the commit
    the tests passed on."""
    claims = version_claims(root)
    version = claims[0][1] or ""
    if parse_version(version) is None:
        version = ""             # never an output: it came from the commit
    head = git(root, "rev-parse", "HEAD")
    tags = [t for t in git(root, "tag", "--list", "v*").splitlines()
            if parse_version(t)]
    newest = max(tags, key=cast("Callable[[str], tuple[int, int, int]]",
                                parse_version)) if tags else ""
    answer = {"release": False, "refused": False, "version": version,
              "tag": f"v{version}" if version else "",
              "previous_tag": newest, "sha": head}

    def no(why: str) -> dict[Any, Any]:
        answer["line"] = f"no release: {why}"
        return answer

    if parse_version(version) is None:
        return no(f'{claims[0][0]} has no VERSION = "X.Y.Z" line')
    tag = answer["tag"]
    if tag == newest:
        return no(f"VERSION is {version} and {tag} is already the newest "
                  f"tag")
    if tag in tags:
        return no(f"VERSION is {version} and {tag} already exists (the "
                  f"newest tag is {newest})")
    if newest and (cast("tuple[int, int, int]", parse_version(version))
                   <= cast("tuple[int, int, int]", parse_version(newest))):
        return no(f"VERSION {version} is not newer than the newest tag, "
                  f"{newest}")
    if changelog_entry(root, version) is None:
        major, minor, patch = cast("tuple[int, int, int]",
                                   parse_version(version))
        forms = f"'## {version} - <title>'"
        if patch == 0 and version.count(".") == 2:
            forms += f" or '## {major}.{minor} - <title>'"
        return no(f"CHANGELOG.md has no entry heading for {version} (a "
                  f"line {forms})")
    disagree = [f"{name} says {said}" for name, said in claims[1:]
                if said != version]
    if disagree:
        return no(f"{claims[0][0]} says {version} but "
                  + ", ".join(disagree))
    kinds = registry_packages(root)
    if "pypi" not in kinds or "npm" not in kinds:
        return no(f"{VERSION_FILES[-1]} must list both the pypi and the npm "
                  f"package; it lists {', '.join(kinds) or 'none'}")
    body = cast("tuple[str, str]", changelog_entry(root, version))[1]
    if newest:
        try:
            covered = covered_changes(root, newest)
            moved = api_golden_changed(root, newest)
        except Unanswered as e:
            answer["refused"] = True
            answer["line"] = (f"refused: what {version} changes since {newest} "
                              f"cannot be told, so it is not released: {e}")
            return answer
        major = (cast("tuple[int, int, int]", parse_version(version))[0]
                 > cast("tuple[int, int, int]", parse_version(newest))[0])
        if covered and not major and not says(body, COMPATIBILITY_LINE):
            kind = ("patch"
                    if cast("tuple[int, int, int]", parse_version(version))[:2]
                    == cast("tuple[int, int, int]", parse_version(newest))[:2]
                    else "minor")
            answer["refused"] = True
            answer["line"] = (
                f"refused: {version} is a {kind} release, and since {newest} "
                f"it {'; it '.join(covered)} - but its CHANGELOG entry has no "
                f"line beginning 'compatibility:' saying why that is not a "
                f"breaking change (STABILITY.md rule 1; RELEASING.md)")
            return answer
        if moved and not says(body, API_LINE):
            answer["refused"] = True
            answer["line"] = (
                f"refused: {API_GOLDEN} is not {newest}'s, and the CHANGELOG "
                f"entry for {version} has no line beginning 'api:' saying "
                f"what changed (check_api.py; RELEASING.md)")
            return answer
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

def _github_auth(base: str) -> dict[Any, Any]:
    """GitHub's token, only ever for api.github.com."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token and base == "https://api.github.com":
        return {"Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28"}
    return {}


def _fetch(url: str, *, data: bytes | None = None,
           headers: dict[Any, Any] | None = None, attempts: int = 3) -> tuple[Any, ...]:
    """(status, body). An HTTP status is an answer, 404 included; a
    network failure or a 5xx on every attempt is not, and raises."""
    head = {"User-Agent": "sabline-release-checks",
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


def _json_of(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _dig(doc: Any, *keys: Any) -> Any:
    for key in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(key)
    return doc


def _server_path() -> str:
    return "/v0.1/servers/" + urllib.parse.quote(SERVER, safe="")


# The Marketplace's ExtensionQueryFlags: IncludeVersions lists every version,
# newest first; with IncludeLatestVersionOnly (0x200) it lists the one the
# Marketplace serves as the latest.
MARKETPLACE_ALL, MARKETPLACE_LATEST = 0x1, 0x201


def _marketplace(flags: int) -> tuple[int, list[str] | None]:
    """(HTTP status, the extension's versions as the Marketplace lists them
    under `flags`), the list None when the answer is not one."""
    body = json.dumps({"filters": [{"criteria": [
        {"filterType": 7, "value": EXTENSION}]}], "flags": flags}).encode()
    status, raw = _fetch(
        ENDPOINTS["vscode"] + "/_apis/public/gallery/extensionquery",
        data=body, headers={
            "Content-Type": "application/json",
            "Accept": "application/json;api-version=3.0-preview.1"})
    doc = _json_of(raw)
    if status != 200 or not isinstance(doc, dict):
        return status, None
    return status, [str(v.get("version"))
                    for result in doc.get("results") or []
                    for extension in result.get("extensions") or []
                    for v in extension.get("versions") or []]


def marketplace_versions() -> list[str]:
    status, versions = _marketplace(MARKETPLACE_ALL)
    if versions is None:
        raise Unanswered(f"the Marketplace answered HTTP {status}")
    return versions


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


RECEIPT_SINCE = (8, 1, 0)


def expected_assets(version: str) -> list[str]:
    """Every file a release's GitHub page holds: the nine artefacts - the
    wheel, the sdist, the SBOM, the MCP tool manifest, the .mcpb bundle,
    three executables and the attestation - with their signatures and
    checksums; and from 8.1.0 a tenth, the signed receipt of one run of
    the program the attestation is of."""
    signed = [f"sabline_lang-{version}-py3-none-any.whl",
              f"sabline_lang-{version}.tar.gz",
              f"sabline-lang-{version}.cdx.json",
              f"sabline-mcp-tools-{version}.json"]
    names = ["SHA256SUMS"] + signed + [f + ".sigstore.json" for f in signed]
    for single in ("sabline-linux", "sabline-macos", "sabline-windows.exe",
                   "sabline.mcpb"):
        names += [single, single + ".sha256", single + ".sigstore.json"]
    names += [f"sabline-attestation-{version}.intoto.json",
              f"sabline-attestation-{version}.cosign.sigstore.json",
              f"sabline-attestation-{version}.sigstore-python.sigstore.json"]
    if (parse_version(version) or (0, 0, 0)) >= RECEIPT_SINCE:
        names += [f"sabline-receipt-{version}.intoto.json",
                  f"sabline-receipt-{version}.cosign.sigstore.json",
                  f"sabline-receipt-{version}.sigstore-python.sigstore.json"]
    return names


def consistency(version: str) -> list[tuple[str, str, bool]]:
    """(target, what it reports, whether that is `version`) for PyPI, npm,
    the MCP registry, the GitHub release and the VS Code Marketplace. The
    Marketplace was added after 8.2.1: until then a release whose extension
    never published passed this check."""
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
    status, listed = _marketplace(MARKETPLACE_LATEST)
    said = listed[0] if listed else None
    rows.append(("the VS Code Marketplace",
                 f"latest is {said}" if said
                 else f"HTTP {status}" if listed is None
                 else "no version listed", said == version))
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


def advisory_body(text: str) -> dict[Any, Any]:
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


def emit(args: Any, line: str, level: str | None = "notice", **outputs: Any) -> None:
    """Print one line - as a notice, a warning or an error with --annotate -
    and write it to the summary and its outputs to the step outputs."""
    print(f"::{level}::{_escape(line)}" if args.annotate and level else line)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(line + "\n\n")
    if args.github_output and outputs:
        broken = [k for k, v in outputs.items() if "\n" in str(v)
                  or "\r" in str(v)]
        if broken:
            # a line break in a value would write outputs of its own
            raise Unanswered(f"the step output {', '.join(broken)} would hold "
                             f"a line break; nothing is written")
        with open(args.github_output, "a", encoding="utf-8") as fh:
            for key, value in outputs.items():
                fh.write(f"{key}={value}\n")


def _write(args: Any, text: str) -> None:
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)


def cmd_gate(args: Any) -> int:
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


def cmd_covered(args: Any) -> int:
    changes = covered_changes(Path(args.repo), args.since)
    for line in changes:
        print(line)
    if not changes:
        print(f"nothing STABILITY.md covers changed since {args.since}")
    return 0


# RELEASE_PAUSED, a variable of the release environment. Anything but these
# pauses: a value nobody meant is a reason to stop, not to publish.
NOT_PAUSED = ("", "0", "false", "no", "off")


def paused(value: str | None) -> bool:
    """Whether RELEASE_PAUSED stops a release."""
    return (value or "").strip().lower() not in NOT_PAUSED


def cmd_paused(args: Any) -> int:
    value = os.environ.get("RELEASE_PAUSED")
    if paused(value):
        emit(args, f"release paused: RELEASE_PAUSED is {value!r} in the "
                   f"release environment, so nothing is tagged or published. "
                   f"The tests and the builds still ran. To release this "
                   f"commit, clear the variable and re-run all jobs of this "
                   f"run; the gate decides again.", "warning", paused="true")
    else:
        emit(args, "not paused: RELEASE_PAUSED is not set in the release "
                   "environment", None, paused="false")
    return 0


def cmd_title(args: Any) -> int:
    entry = changelog_entry(Path(args.repo), args.version)
    if entry is None:
        print(f"CHANGELOG.md has no entry for {args.version}", file=sys.stderr)
        return 2
    print(entry[0])
    return 0


def cmd_notes(args: Any) -> int:
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


def cmd_published(args: Any) -> int:
    """Before a publish: whether the version is there already, as a step
    output. With --require, after one (8.2.1): asked until it is there or
    --timeout runs out, and a version that is not there is exit 1, so a
    publish job that published nothing fails. Until 8.2.1 the Marketplace's
    job ended green after three timeouts, saying NOT PUBLISHED."""
    where = NAMES[args.target]
    doubt: list[str] = []

    def ask() -> tuple[Any, ...]:
        doubt.clear()
        try:
            if published(args.target, args.version):
                return True, []
        except Unanswered as e:
            doubt.append(str(e))
            return False, [str(e)]
        return False, [f"{args.version} is not on {where}"]

    there, _ = _poll(args, ask) if args.require else ask()
    if doubt:
        emit(args, f"could not tell whether {args.version} is on {where}, so "
                   + ("it is not known to be published" if args.require
                      else "nothing was published there")
                   + f": {doubt[0]}", "error")
        return 2
    if args.require:
        if there:
            emit(args, f"PUBLISHED - {args.version} is on {where}",
                 published="true")
            return 0
        emit(args, f"NOT PUBLISHED - {args.version} is not on {where}"
                   + (f" after {args.timeout:g} s of asking"
                      if args.timeout else ""), "error", published="false")
        return 1
    if there:
        emit(args, f"{args.version} is already on {where}; skipping that "
                   f"publish", published="true")
    else:
        emit(args, f"{args.version} is not on {where} yet; publishing it",
             None, published="false")
    return 0


def _waiting_for(rows: Any) -> str:
    """What a poll is still waiting on, as one line. A row is a sentence
    (registry-ready, or a target that could not be asked) or a (target,
    report, agrees) row from consistency(), named only when it disagrees.
    Until 8.1.1 this joined the rows as they came, and a consistency row is
    a tuple: the first release a target lagged behind (8.1.1, PyPI's JSON)
    stopped the check with a TypeError instead of asking again."""
    return "; ".join(row if isinstance(row, str) else f"{row[0]} ({row[1]})"
                     for row in rows if isinstance(row, str) or not row[2])


def _poll(args: Any, ask: Any) -> tuple[Any, ...]:
    """Ask until the answer is good or --timeout runs out: (good, rows)."""
    deadline = time.monotonic() + args.timeout
    while True:
        good, rows = ask()
        if good or time.monotonic() >= deadline:
            return good, rows
        print("not yet: " + _waiting_for(rows), flush=True)
        time.sleep(args.interval)


def cmd_registry_ready(args: Any) -> int:
    def ask() -> tuple[Any, ...]:
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


def cmd_consistent(args: Any) -> int:
    def ask() -> tuple[Any, ...]:
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
        emit(args, f"consistent: PyPI, npm, the MCP registry, the GitHub "
                   f"release and the VS Code Marketplace all report "
                   f"{args.version}")
        return 0
    differ = [f"{target} ({report})" for target, report, agrees in rows
              if not agrees]
    emit(args, f"inconsistent: {', '.join(differ)} - "
               f"{'does' if len(differ) == 1 else 'do'} not report "
               f"{args.version}", "error")
    return 1


# ---- after the release: the Action pins (8.4) ---------------------------------

PIN_DOCS = ("README.md", "EMBEDDING.md")
_PIN = re.compile(r"(gowrishankar-infra/sabline-lang@)[0-9a-f]{40}"
                  r"([ \t]+#[ \t]*)v\d+\.\d+\.\d+")
# (a line may end \r\n: a Windows checkout's does, and `$` is before \n only)
_INSTALLS = re.compile(
    r'^([ \t]*version:[ \t]*")\d+\.\d+\.\d+("[^\r\n]*)(?=\r?\n|\Z)', re.M)
_OWN_VERSION = re.compile(r"(the Action's own version \()\d+\.\d+\.\d+(\))")
_PRE_COMMIT = re.compile(
    r"(repo:[ \t]*https://github\.com/gowrishankar-infra/sabline-lang[ \t]*\r?\n"
    r"[ \t]*rev:[ \t]*)v\d+\.\d+\.\d+")


def moved_pins(text: str, tag: str, commit: str) -> str:
    """One document with every Action pin naming `commit` as `tag`, the
    `version:` example beside a pin installing that version, and the
    pre-commit `rev:` naming the tag. Nothing else in it changes."""
    version = tag[1:]
    text = _PIN.sub(lambda m: f"{m.group(1)}{commit}{m.group(2)}{tag}", text)

    def install(m: Any) -> str:
        rest = _OWN_VERSION.sub(lambda o: f"{o.group(1)}{version}{o.group(2)}",
                                m.group(2))
        return f"{m.group(1)}{version}{rest}"

    text = _INSTALLS.sub(install, text)
    return _PRE_COMMIT.sub(lambda m: f"{m.group(1)}{tag}", text)


def move_pins(root: Path, tag: str, commit: str) -> list[str]:
    """Move the pins in README.md and EMBEDDING.md to `tag` on `commit`, as
    run_tests.py's check_action_pins wants them once the tag exists, and
    give the documents that changed. Unanswered when the tag or the commit
    is not one, or when README.md shows no pin to move: a document this
    cannot read must stop the job, not pass as already moved."""
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
        raise Unanswered(f"{tag!r} is not a tag of the form vX.Y.Z")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise Unanswered(f"{commit!r} is not a full commit hash")
    changed = []
    for doc in PIN_DOCS:
        path = root / doc
        try:
            with open(path, encoding="utf-8", newline="") as fh:
                before = fh.read()
        except OSError as e:
            raise Unanswered(f"{doc} could not be read: {e.strerror or e}")
        if doc == "README.md" and not _PIN.search(before):
            raise Unanswered(
                "README.md shows no Action pin of the form "
                "gowrishankar-infra/sabline-lang@<commit>  # vX.Y.Z")
        after = moved_pins(before, tag, commit)
        left = [m.group(0) for m in _PIN.finditer(after)
                if commit not in m.group(0) or not m.group(0).endswith(tag)]
        if left:
            raise Unanswered(f"{doc} still pins {left[0]!r}")
        if after != before:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(after)
            changed.append(doc)
    return changed


def cmd_move_pins(args: Any) -> int:
    changed = move_pins(Path(args.repo), args.tag, args.commit)
    emit(args, f"the Action pins name {args.tag} ({args.commit}): "
         + (f"moved in {', '.join(changed)}" if changed else
            "they already did, and nothing was changed"),
         moved=str(bool(changed)).lower())
    return 0


def cmd_advisories(args: Any) -> int:
    for name in added_advisories(Path(args.repo), args.since, args.until):
        print(name)
    return 0


def cmd_advisory_body(args: Any) -> int:
    try:
        text = Path(args.file).read_text(encoding="utf-8")
        body = advisory_body(text)
    except (OSError, Unanswered) as e:
        print(f"advisory-body: {args.file}: {e}", file=sys.stderr)
        return 2
    _write(args, json.dumps(body, indent=2, ensure_ascii=args.output is None)
           + "\n")
    return 0


def cmd_advisory_commands(args: Any) -> int:
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


def main(argv: Any = None) -> int:
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

    p = sub.add_parser("covered", parents=[common],
                       help="what STABILITY.md covers that changed since a tag")
    p.add_argument("since")
    p.set_defaults(run=cmd_covered)

    p = sub.add_parser("paused", parents=[common],
                       help="does RELEASE_PAUSED stop publishing?")
    p.set_defaults(run=cmd_paused)

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
    p.add_argument("--require", action="store_true",
                   help="after a publish: exit 1 unless the version is there")
    p.add_argument("--timeout", type=float, default=0,
                   help="with --require, seconds to keep asking (default: "
                        "ask once)")
    p.add_argument("--interval", type=float, default=30)
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

    p = sub.add_parser("move-pins", parents=[common],
                       help="after a release: the Action pins, moved to its tag")
    p.add_argument("tag")
    p.add_argument("--commit", required=True,
                   help="the commit the tag names")
    p.set_defaults(run=cmd_move_pins)

    args = parser.parse_args(argv)
    try:
        return cast(int, args.run(args))
    except Unanswered as e:
        print(f"release_checks.py: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
