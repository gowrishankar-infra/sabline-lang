"""velaris deps-diff: what one dependency's newer version gained.
"""
import json
import os
import re
import sys

from .version import VERSION
from .findings import _SarifRun, print_sarif_summary
from .ratchet import (
    _git,
    _grant_parts,
    capabilities_compare,
    capabilities_document,
    capability_scan,
)
from typing import Any, cast

# ---------------------------------------------------------------------------
# 20. WHAT AN UPGRADE GAINED - one dependency, two versions
#
#     `velaris deps-diff <package> <old> <new>` reads both versions of a
#     dependency and reports what the newer one can do that the older one
#     could not. For the .vel files a version holds, that is section 17's
#     comparison with the older version as the baseline: effects, hosts,
#     paths, modules, operation counts and functions, in the shape
#     `capabilities check` reports them. For anything else a version
#     holds it is almost nothing, and the report says so. What Python or
#     JavaScript code can do is not written in its text in any form that
#     can be checked, so no effect is inferred from it; what can be read
#     is read - the install-time scripts a version declares and the
#     dependencies it declares - and the capability surface is reported
#     as unknown.
#
#     `velaris deps-diff --against REF` does the same for every dependency
#     the lockfiles changed since REF upgrade, and `--comment` puts the
#     answer in one pull-request comment that later runs edit.
# ---------------------------------------------------------------------------


DEPS_DIFF_SCHEMA = "velaris.deps-diff/1"
DEPS_LOCKFILES_SCHEMA = "velaris.deps-diff-lockfiles/1"
DEPS_COMMENT_MARKER = "<!-- velaris-deps-diff-comment -->"
DEPS_SOURCES = ("pypi", "npm", "git", "dir")
_DEPS_ARTIFACT_LIMIT = 64 << 20        # bytes read for one archive
_DEPS_TREE_LIMIT = 256 << 20           # bytes unpacked from one version
_DEPS_MAX_UPGRADES = 30                # upgrades compared in one review
_NPM_INSTALL_SCRIPTS = ("preinstall", "install", "postinstall")
_CODE_LANGUAGES = (
    ((".py", ".pyw"), "Python"),
    ((".pyc", ".pyo"), "compiled Python"),
    ((".js", ".mjs", ".cjs", ".jsx"), "JavaScript"),
    ((".ts", ".mts", ".cts", ".tsx"), "TypeScript"),
    ((".so", ".pyd", ".dll", ".dylib", ".node"), "native libraries"),
    ((".wasm",), "WebAssembly"),
    ((".sh", ".bash", ".bat", ".cmd", ".ps1"), "shell scripts"),
    ((".exe",), "executables"),
)
# lockfiles by name: (format, ecosystem). The second set is recognised as
# a lockfile and reported as changed, and nothing in it is read.
_LOCKFILES = {
    "package-lock.json": ("npm-lock", "npm"),
    "npm-shrinkwrap.json": ("npm-lock", "npm"),
    "Pipfile.lock": ("pipfile-lock", "pypi"),
    "poetry.lock": ("toml-packages", "pypi"),
    "uv.lock": ("toml-packages", "pypi"),
    "pdm.lock": ("toml-packages", "pypi"),
    "velaris.lock": ("velaris-lock", "velaris"),
}
_LOCKFILES_NOT_READ = ("yarn.lock", "pnpm-lock.yaml", "bun.lock", "bun.lockb",
                       "Cargo.lock", "go.sum", "Gemfile.lock", "composer.lock",
                       "packages.lock.json", "gradle.lockfile",
                       "Package.resolved", "mix.lock", "pubspec.lock")


class DepsError(Exception):
    """A dependency, or a version of it, that could not be read."""


def _sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def _ver_key(v: str) -> tuple[Any, ...]:
    """A version as something to sort by: numbers as numbers."""
    return tuple((0, int(x)) if x.isdigit() else (1, x)
                 for x in re.split(r"[.+\-_]", str(v)) if x != "")


def _deps_source(package: str) -> tuple[Any, ...]:
    """(kind, where) for a package argument: pypi:NAME, npm:NAME, git:URL
    or git:PATH, dir:PATH - and @scope/name, which only npm writes."""
    kind, sep, where = package.partition(":")
    if sep and kind in DEPS_SOURCES and where and not where.startswith("-"):
        return kind, where
    if package.startswith("@") and package.count("/") == 1:
        return "npm", package
    raise DepsError(f"'{package}' does not say where to read it: write "
                    f"pypi:NAME, npm:NAME, git:URL (or a path to a git "
                    f"repository), or dir:PATH, a directory holding one "
                    f"subdirectory per version")


def _deps_get(url: str, limit: int = _DEPS_ARTIFACT_LIMIT,
              accept: str | None = None) -> Any:
    """The bytes at url, or None when the server says it has nothing
    there (404, 410); DepsError for anything else, and for a body larger
    than limit."""
    import urllib.error
    import urllib.request
    headers = {"User-Agent": f"velaris/{VERSION} (deps-diff)"}
    if accept:
        headers["Accept"] = accept
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read(limit + 1)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return None
        raise DepsError(f"{url}: HTTP {e.code}")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise DepsError(f"{url}: {getattr(e, 'reason', None) or e}")
    if len(data) > limit:
        raise DepsError(f"{url} is larger than {limit >> 20} MB, which "
                        f"deps-diff does not read")
    return data


_RESERVED_NAMES = frozenset({"con", "prn", "aux", "nul",
                             *(f"com{i}" for i in range(1, 10)),
                             *(f"lpt{i}" for i in range(1, 10))})


def _clean_tree(files: dict[Any, Any], strip_top: bool) -> dict[Any, Any]:
    """'/'-separated paths, none climbing out, none absolute; with the one
    top-level directory every path shares removed when strip_top (an
    sdist's name-1.0/, an npm tarball's package/). A part holding ':' is
    left out wherever it is - on Windows `a/C:x` joined under a directory
    is a path on drive C - and so is a device name Windows reserves."""
    out = {}
    for raw, body in files.items():
        text = raw.replace("\\", "/")
        parts = [p for p in text.split("/") if p not in ("", ".")]
        if not parts or text.startswith("/") or ".." in parts or any(
                ":" in p or p.split(".")[0].lower() in _RESERVED_NAMES
                for p in parts):
            continue
        out["/".join(parts)] = body
    if strip_top and out and all("/" in p for p in out) \
            and len({p.split("/", 1)[0] for p in out}) == 1:
        out = {p.split("/", 1)[1]: b for p, b in out.items()}
    return out


def _archive_files(data: bytes, name: str, strip_top: bool = True) -> dict[Any, Any]:
    """{path: bytes} for the regular files of a tar (gzip or not), zip or
    wheel archive. Links are not followed and are left out."""
    import io
    import tarfile
    import zipfile
    found: dict[Any, Any] = {}
    total = 0
    try:
        if name.lower().endswith((".zip", ".whl")):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    total += info.file_size
                    if total > _DEPS_TREE_LIMIT:
                        raise DepsError(f"{name} unpacks to more than "
                                        f"{_DEPS_TREE_LIMIT >> 20} MB")
                    found[info.filename] = z.read(info)
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as t:
                for m in t.getmembers():
                    if not m.isfile():
                        continue
                    total += m.size
                    if total > _DEPS_TREE_LIMIT:
                        raise DepsError(f"{name} unpacks to more than "
                                        f"{_DEPS_TREE_LIMIT >> 20} MB")
                    fh = t.extractfile(m)
                    if fh is not None:
                        found[m.name] = fh.read()
    except (tarfile.TarError, zipfile.BadZipFile, OSError, EOFError,
            ValueError) as e:
        raise DepsError(f"{name} is not an archive deps-diff can read ({e})")
    return _clean_tree(found, strip_top)


def _code_counts(files: dict[Any, Any]) -> dict[Any, Any]:
    """{language: number of files} for the code a version holds that is
    not Velaris. Type declarations (.d.ts) are not code."""
    out: dict[Any, Any] = {}
    for p in files:
        low = p.lower()
        if low.endswith((".d.ts", ".d.mts", ".d.cts")):
            continue
        ext = os.path.splitext(low)[1]
        for suffixes, language in _CODE_LANGUAGES:
            if ext in suffixes:
                out[language] = out.get(language, 0) + 1
    return dict(sorted(out.items()))


def _describe_code(counts: dict[Any, Any]) -> str:
    return ", ".join(f"{lang} ({n} file{'' if n == 1 else 's'})"
                     for lang, n in counts.items())


def _toml_value(text: str, table: str, key: str) -> Any:
    """A string, or a list of strings, written as `key = ...` under
    [table] - the part of TOML pyproject.toml uses for these keys - or
    None. Not a TOML parser; a value in any other form is None."""
    strings = r'"((?:[^"\\]|\\.)*)"|\'([^\']*)\''
    current = None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        i += 1
        if s.startswith("["):
            current = s.strip("[] \t")
            continue
        if current != table:
            continue
        m = re.match(r'^"?([A-Za-z0-9_.-]+)"?\s*=\s*(.*)$', s)
        if not m or m.group(1) != key:
            continue
        rest = m.group(2)
        if rest.startswith("["):
            buf = rest

            def depth(b: Any) -> Any:
                bare = re.sub(strings, "", b)
                return bare.count("[") - bare.count("]")
            while depth(buf) > 0 and i < len(lines):
                buf += "\n" + lines[i]
                i += 1
            return [a or b for a, b in re.findall(strings, buf)]
        sm = re.match(strings, rest)
        return (sm.group(1) or sm.group(2)) if sm else None
    return None


def _pep508_name(requirement: str) -> Any:
    m = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", requirement)
    return re.sub(r"[-_.]+", "-", m.group(1)).lower() if m else None


def _requirements_map(reqs: Any) -> dict[Any, Any]:
    """{normalised name: the requirement text(s)} for PEP 508 strings."""
    out: dict[Any, Any] = {}
    for r in reqs or []:
        if not isinstance(r, str):
            continue
        name = _pep508_name(r)
        if name:
            out.setdefault(name, []).append(r.strip())
    return {n: " | ".join(sorted(v)) for n, v in sorted(out.items())}


def _named_files(command: str, files: dict[Any, Any]) -> dict[Any, Any]:
    """{path: sha256} for the files of a version an install command names
    - `node setup.js`, `sh ./install.sh` - as node or a shell would find
    them in the package's own directory. What the command does is not
    derived; that the file it runs changed is a fact."""
    out = {}
    for token in re.split(r"[\s;&|()<>`'\"=]+", command):
        t = token[2:] if token.startswith("./") else token
        for cand in (t, t + ".js", t + ".cjs", t + ".mjs"):
            if cand and cand in files:
                out[cand] = _sha256(files[cand])
                break
    return dict(sorted(out.items()))


def _npm_hooks(manifest: dict[Any, Any], files: dict[Any, Any], source: str) -> list[Any]:
    """The scripts npm runs when it installs a package from a registry:
    preinstall, install and postinstall - and `node-gyp rebuild`, npm's
    install script for a package with a binding.gyp that names no install
    or preinstall script of its own - each marked with where it was read."""
    scripts = manifest.get("scripts")
    scripts = scripts if isinstance(scripts, dict) else {}
    hooks: list[dict[str, Any]] = []
    for name in _NPM_INSTALL_SCRIPTS:
        cmd = scripts.get(name)
        if isinstance(cmd, str) and cmd.strip():
            hooks.append({"kind": "npm-script", "name": name, "command": cmd,
                          "source": source,
                          "files": _named_files(cmd, files)})
    if "binding.gyp" in files and not any(
            isinstance(scripts.get(n), str) and scripts[n].strip()
            for n in ("install", "preinstall")):
        hooks.append({"kind": "npm-script", "name": "install",
                      "command": "node-gyp rebuild", "implicit": True,
                      "source": source,
                      "files": {"binding.gyp": _sha256(files["binding.gyp"])}})
    return hooks


def _npm_declared(manifest: dict[Any, Any]) -> dict[Any, Any]:
    out = {}
    for kind in ("dependencies", "optionalDependencies", "peerDependencies"):
        d = manifest.get(kind)
        if isinstance(d, dict):
            out[kind] = {str(k): str(v) for k, v in sorted(d.items())}
    return out


def _python_hooks(files: dict[Any, Any], source: str) -> list[Any]:
    """What runs when pip installs a version: setup.py and the build
    backend when it builds from the source distribution, and a .pth file
    with an `import` line at every start of Python once it is installed."""
    hooks: list[dict[str, Any]] = []
    if "setup.py" in files:
        hooks.append({"kind": "setup.py", "name": "setup.py",
                      "source": source,
                      "sha256": _sha256(files["setup.py"])})
    py = files.get("pyproject.toml")
    if py is not None:
        text = py.decode("utf-8", "replace")
        backend = _toml_value(text, "build-system", "build-backend")
        requires = _toml_value(text, "build-system", "requires")
        in_tree = _toml_value(text, "build-system", "backend-path")
        if backend is not None or requires is not None:
            inside = {}
            for d in (in_tree if isinstance(in_tree, list) else []):
                d = d.strip("./") + "/"
                inside.update({p: _sha256(b) for p, b in files.items()
                               if p.startswith(d) and p.endswith(".py")})
            hooks.append({"kind": "build-backend", "source": source,
                          "name": backend if isinstance(backend, str)
                          else "(none named)",
                          "requires": sorted(requires)
                          if isinstance(requires, list) else [],
                          "files": dict(sorted(inside.items()))})
    for p, body in sorted(files.items()):
        top = "/" not in p or re.match(r"^[^/]+\.data/(purelib|platlib)/"
                                       r"[^/]+$", p)
        if p.endswith(".pth") and top and any(
                ln.startswith(("import ", "import\t"))
                for ln in body.decode("utf-8", "replace").splitlines()):
            hooks.append({"kind": "pth", "name": p, "source": source,
                          "sha256": _sha256(body)})
    return hooks


def _tree_declared(files: dict[Any, Any]) -> tuple[Any, ...]:
    """(hooks, declared dependencies or None, notes) from a version's own
    files, for a source with no registry: package.json, setup.py,
    pyproject.toml."""
    hooks, declared, notes = [], None, []
    pkg = files.get("package.json")
    if pkg is not None:
        try:
            man = json.loads(pkg.decode("utf-8-sig"))
        except ValueError:
            man = None
            notes.append("package.json is not JSON, so its scripts and "
                         "dependencies were not read")
        if isinstance(man, dict):
            hooks += _npm_hooks(man, files, "package.json")
            declared = _npm_declared(man)
    hooks += _python_hooks(files, "files")
    py = files.get("pyproject.toml")
    if py is not None:
        deps = _toml_value(py.decode("utf-8", "replace"), "project",
                           "dependencies")
        if isinstance(deps, list):
            declared = dict(declared or {})
            declared["project.dependencies"] = _requirements_map(deps)
    return hooks, declared, notes


def _missing(what: str, version: str, have: list[Any], why: str = "") -> None:
    have = sorted(have, key=_ver_key)
    listed = (f"; the latest it lists: {', '.join(have[-8:])}" if have
              else "; it lists no versions")
    raise DepsError(f"{what} has no version {version}{listed}{why}")


def _read_pypi(name: str, version: str) -> dict[str, Any]:
    import urllib.parse
    base = os.environ.get("VELARIS_PYPI_URL", "https://pypi.org").rstrip("/")
    q = urllib.parse.quote(name, safe="")
    raw = _deps_get(f"{base}/pypi/{q}/{urllib.parse.quote(version, safe='')}"
                    f"/json", 32 << 20)
    if raw is None:
        whole = _deps_get(f"{base}/pypi/{q}/json", 64 << 20)
        if whole is None:
            raise DepsError(f"PyPI ({base}) has no package '{name}'; for an "
                            f"npm package write npm:{name}")
        _missing(f"pypi:{name}", version,
                 list(json.loads(whole).get("releases") or {}))
    try:
        doc = json.loads(raw)
    except ValueError:
        raise DepsError(f"PyPI's answer for {name} {version} is not JSON")
    info = doc.get("info") or {}
    listed = doc.get("urls") or []
    sdists = [u for u in listed if u.get("packagetype") == "sdist"]
    wheels = sorted((u for u in listed if u.get("packagetype") == "bdist_wheel"),
                    key=lambda u: (not u.get("filename", "").endswith(
                        "-none-any.whl"), u.get("filename", "")))
    read, notes, trees = [], [], {}
    for label, chosen in (("sdist", sdists[:1]), ("wheel", wheels[:1])):
        for u in chosen:
            data = _deps_get(u["url"])
            if data is None:
                raise DepsError(f"{u['url']} is listed by PyPI and not there")
            want = (u.get("digests") or {}).get("sha256")
            if want and _sha256(data) != want:
                raise DepsError(f"{u.get('filename')}: the bytes downloaded "
                                f"are not the ones PyPI lists (sha256)")
            trees[label] = _archive_files(data, u.get("filename", "x.tar.gz"),
                                          strip_top=(label == "sdist"))
            read.append({"artifact": label, "file": u.get("filename"),
                         "url": u["url"], "sha256": _sha256(data)})
    if len(wheels) > 1:
        notes.append(f"{version} has {len(wheels)} wheels; "
                     f"{wheels[0].get('filename')} was read")
    if not listed:
        notes.append(f"PyPI lists no files for {version}, so none was read")
    if doc.get("info", {}).get("yanked") or any(u.get("yanked")
                                                for u in listed):
        why = info.get("yanked_reason")
        notes.append(f"{version} is yanked on PyPI"
                     + (f": {why}" if why else ""))
    # what is installed is the wheel; the sdist is what pip builds when no
    # wheel matches, running setup.py or the build backend as it does
    files = trees.get("wheel") or trees.get("sdist") or {}
    hooks = _python_hooks(trees.get("sdist", {}), "sdist")
    hooks += [h for h in _python_hooks(trees.get("wheel", {}), "wheel")
              if h["kind"] == "pth"]
    return {"version": version, "files": files, "read": read,
            "surface_from": "wheel" if "wheel" in trees else
            "sdist" if "sdist" in trees else None,
            "hooks": hooks,
            "declared": {"requires_dist": _requirements_map(
                info.get("requires_dist"))},
            "notes": notes}


def _read_npm(name: str, version: str) -> dict[str, Any]:
    import base64
    import hashlib
    import urllib.parse
    base = os.environ.get("VELARIS_NPM_REGISTRY",
                          "https://registry.npmjs.org").rstrip("/")
    q = urllib.parse.quote(name, safe="@")
    raw = _deps_get(f"{base}/{q}/{urllib.parse.quote(version, safe='')}",
                    32 << 20)
    if raw is None:
        whole = _deps_get(f"{base}/{q}", 64 << 20,
                          accept="application/vnd.npm.install-v1+json")
        if whole is None:
            raise DepsError(f"npm ({base}) has no package '{name}'; for a "
                            f"Python package write pypi:{name}")
        doc = json.loads(whole)
        gone = (doc.get("time") or {}).get("unpublished")
        why = ""
        if isinstance(gone, dict):
            why = (f" - every version was unpublished on "
                   f"{str(gone.get('time', '?'))[:10]}, and an unpublished "
                   f"version cannot be read")
        _missing(f"npm:{name}", version, list(doc.get("versions") or {}), why)
    try:
        manifest = json.loads(raw)
    except ValueError:
        raise DepsError(f"npm's answer for {name} {version} is not JSON")
    dist = manifest.get("dist") or {}
    files, read, notes = {}, [], []
    tarball = dist.get("tarball")
    if tarball:
        data = _deps_get(tarball)
        if data is None:
            raise DepsError(f"{tarball} is listed by npm and not there")
        integrity = str(dist.get("integrity") or "")
        if integrity.startswith("sha512-"):
            got = base64.b64encode(hashlib.sha512(data).digest()).decode()
            if got != integrity[7:]:
                raise DepsError(f"{tarball}: the bytes downloaded are not "
                                f"the ones npm lists (integrity)")
        elif dist.get("shasum") and hashlib.sha1(data).hexdigest() \
                != dist["shasum"]:
            raise DepsError(f"{tarball}: the bytes downloaded are not the "
                            f"ones npm lists (shasum)")
        files = _archive_files(data, "package.tgz")
        read.append({"artifact": "tarball", "url": tarball,
                     "sha256": _sha256(data)})
    else:
        notes.append(f"npm lists no tarball for {version}, so none was read")
    # The registry's manifest and the package.json inside the tarball are
    # published separately, and nothing checks one against the other. npm
    # builds a fresh tree from the manifest; which copy's install scripts
    # it runs has differed between npm versions, and depends on whether it
    # installs from a lockfile. So the scripts of both are reported, each
    # marked with where it was read, and a difference is said.
    hooks = _npm_hooks(manifest, files, "registry manifest")
    inner = files.get("package.json")
    if inner is not None:
        try:
            packaged = json.loads(inner.decode("utf-8-sig"))
        except ValueError:
            packaged = None
            notes.append(f"the package.json in the tarball of {version} is "
                         f"not JSON, so its scripts were not read")
        if isinstance(packaged, dict):
            in_tarball = _npm_hooks(packaged, files, "tarball package.json")
            if [(h["name"], h["command"]) for h in hooks] \
                    != [(h["name"], h["command"]) for h in in_tarball]:
                notes.append(f"the registry's manifest for {version} and the "
                             f"package.json in its tarball list different "
                             f"install scripts; which one npm runs has "
                             f"differed between npm versions and depends on "
                             f"whether it installs from a lockfile, so both "
                             f"are reported")
            hooks = hooks + in_tarball
            if _npm_declared(packaged) != _npm_declared(manifest):
                notes.append(f"the registry's manifest for {version} and the "
                             f"package.json in its tarball declare different "
                             f"dependencies; npm resolves a fresh install from "
                             f"the manifest, which is what this report shows, "
                             f"and an install from a tree already on disk can "
                             f"read the tarball's")
    elif tarball:
        notes.append(f"the tarball of {version} holds no package.json")
    return {"version": version, "files": files, "read": read,
            "surface_from": "tarball" if tarball else None,
            "hooks": hooks, "declared": _npm_declared(manifest),
            "notes": notes}


def _git_repository(where: str, scratch: str) -> str:
    if os.path.isdir(where):
        return where
    dest = os.path.join(scratch, "repository.git")
    if not os.path.isdir(dest):
        try:
            _git(["clone", "--quiet", "--bare", where, dest], scratch)
        except (RuntimeError, OSError) as e:
            raise DepsError(f"git:{where} could not be cloned: {e}")
    return dest


def _read_git(where: str, version: str, scratch: str) -> dict[str, Any]:
    repo = _git_repository(where, scratch)
    if version.startswith("-"):
        raise DepsError(f"'{version}' is not a version")
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{version}^{{commit}}"], repo).strip()
    except (RuntimeError, OSError):
        try:
            tags = _git(["tag", "--list"], repo).split()
        except (RuntimeError, OSError):
            tags = []
        _missing(f"git:{where}", version, tags,
                 " (no tag, branch or commit of that name)")
    data = _git(["archive", "--format=tar", commit], repo, binary=True)
    files = _archive_files(data, "version.tar", strip_top=False)
    hooks, declared, notes = _tree_declared(files)
    return {"version": version, "files": files,
            "read": [{"artifact": "git", "commit": commit}],
            "surface_from": "git", "hooks": hooks, "declared": declared,
            "notes": notes}


def _read_dir(where: str, version: str) -> dict[str, Any]:
    if not os.path.isdir(where):
        raise DepsError(f"dir:{where}: no such directory")
    here = os.path.join(where, version)
    if version in ("", ".", "..") or "/" in version or "\\" in version \
            or not os.path.isdir(here):
        _missing(f"dir:{where}", version,
                 [d for d in os.listdir(where)
                  if os.path.isdir(os.path.join(where, d))],
                 f" (no directory {here})")
    files, total = {}, 0
    for dp, dirs, names in os.walk(here):
        dirs[:] = sorted(d for d in dirs if d != ".git")
        for n in names:
            full = os.path.join(dp, n)
            if os.path.islink(full):
                continue
            total += os.path.getsize(full)
            if total > _DEPS_TREE_LIMIT:
                raise DepsError(f"{here} holds more than "
                                f"{_DEPS_TREE_LIMIT >> 20} MB")
            with open(full, "rb") as fh:
                files[os.path.relpath(full, here).replace(os.sep, "/")] = \
                    fh.read()
    hooks, declared, notes = _tree_declared(files)
    return {"version": version, "files": files,
            "read": [{"artifact": "directory",
                      "path": os.path.abspath(here)}],
            "surface_from": "directory", "hooks": hooks,
            "declared": declared, "notes": notes}


def _deps_scan(files: dict[Any, Any], into: str) -> dict[Any, Any]:
    """capability_scan of a version's .vel files, written out under into."""
    os.makedirs(into, exist_ok=True)
    for p, body in files.items():
        if p.endswith(".vel"):
            dest = os.path.join(into, *p.split("/"))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(body)
    return capability_scan(into, use_git=False)


def _deps_gained(findings: list[Any]) -> dict[Any, Any]:
    """What the findings add up to, by kind of scope."""
    out: dict[Any, Any] = {"effects": [], "grants": [], "hosts": [],
                 "paths": {"read": [], "write": []}, "modules": [],
                 "counts": [], "functions": []}
    for f in findings:
        if f["kind"] == "grant":
            g = f["grant"]
            out["grants"].append(g)
            if f["new_effect"]:
                out["effects"].append(f["effect"])
            parts = _grant_parts(g)
            if parts[0] == "net" and parts[1] is not None:
                out["hosts"].append(g[4:])
            elif parts[0] == "fs" and parts[2] is not None:
                out["paths"][parts[1]].append(parts[2])
            elif parts[0] == "ffi" and parts[1] is not None:
                out["modules"].append(parts[1])
        elif f["kind"] == "count":
            out["counts"].append({
                "effect": f["effect"], "file": f["file"],
                "old": f["surface_allows"] if f["outside_surface"]
                else f["entry_allows"], "new": f["current"]})
        else:
            out["functions"].append({"file": f["file"],
                                     "function": f["function"],
                                     "gained": f["gained"]})
    for k in ("effects", "grants", "hosts", "modules"):
        out[k] = sorted(set(out[k]))
    for d in ("read", "write"):
        out["paths"][d] = sorted(set(out["paths"][d]))
    return out


def _deps_velaris(a: dict[Any, Any], b: dict[Any, Any], scratch: str) -> dict[str, Any] | None:
    """Section 17's comparison of the .vel files of two versions, the
    older one as the baseline; None when neither holds one."""
    vel_a = sorted(p for p in a["files"] if p.endswith(".vel"))
    vel_b = sorted(p for p in b["files"] if p.endswith(".vel"))
    if not vel_a and not vel_b:
        return None
    scan_a = _deps_scan(a["files"], os.path.join(scratch, "old"))
    scan_b = _deps_scan(b["files"], os.path.join(scratch, "new"))
    check = capabilities_compare(capabilities_document(scan_a, ""), scan_b,
                                 a["version"])
    # the check's own findings, less the edit to velaris.capabilities that
    # would accept each one - there is no such file here to edit
    findings = [{k: v for k, v in f.items() if k != "accept"}
                for f in check["findings"]]
    return {"files": {"old": vel_a, "new": vel_b},
            "compiles": {"old": sum(1 for p in scan_a["programs"].values()
                                    if p["compiles"]),
                         "new": sum(1 for p in scan_b["programs"].values()
                                    if p["compiles"])},
            "before": scan_a["surface"], "after": scan_b["surface"],
            "widened": bool(findings), "findings": findings,
            "narrowed": check["narrowed"], "notes": check["notes"],
            "gained": _deps_gained(findings)}


def _hook_key(h: dict[Any, Any]) -> tuple[Any, ...]:
    return (h["kind"], h["name"], h.get("source", ""))


def _hooks_diff(old: list[Any], new: list[Any]) -> dict[str, Any]:
    A = {_hook_key(h): h for h in old}
    B = {_hook_key(h): h for h in new}
    changed = []
    for k in sorted(set(A) & set(B)):
        a, b = A[k], B[k]
        what = []
        if a.get("command") != b.get("command"):
            what.append(f"the command was {a.get('command')!r} and is "
                        f"{b.get('command')!r}")
        if a.get("sha256") != b.get("sha256"):
            what.append(f"{a['name']} is not the same file")
        if a.get("requires") != b.get("requires"):
            what.append(f"what it requires was {a.get('requires')} and is "
                        f"{b.get('requires')}")
        fa, fb = a.get("files") or {}, b.get("files") or {}
        for p in sorted(set(fa) | set(fb)):
            if p not in fa:
                what.append(f"it now runs {p}")
            elif p not in fb:
                what.append(f"it no longer names {p}")
            elif fa[p] != fb[p]:
                what.append(f"{p}, which it runs, is not the same file")
        if what:
            changed.append({"kind": b["kind"], "name": b["name"],
                            "source": b.get("source", ""),
                            "old": a, "new": b, "what": what})
    moved = {(c["kind"], c["name"], c["source"]) for c in changed}
    return {"added": [B[k] for k in sorted(set(B) - set(A))],
            "removed": [A[k] for k in sorted(set(A) - set(B))],
            "changed": changed,
            "unchanged": [B[k] for k in sorted(set(A) & set(B))
                          if k not in moved]}


def _grouped(items: list[Any], hook_of: Any) -> list[Any]:
    """[(item, [the places it was read])]: an install script that the
    registry's manifest and the tarball both declare, alike, is said
    once."""
    out: dict[Any, Any] = {}
    for it in items:
        h = hook_of(it)
        k = json.dumps([h["kind"], h["name"], h.get("command"),
                        h.get("sha256"), h.get("requires"), h.get("files"),
                        it.get("what")], sort_keys=True, default=str)
        out.setdefault(k, (it, []))[1].append(h.get("source") or "")
    return list(out.values())


def _declared_diff(old: Any, new: Any) -> Any:
    if old is None and new is None:
        return None
    old, new = old or {}, new or {}
    out: dict[Any, Any] = {"added": [], "removed": [], "changed": [], "unchanged": 0}
    for kind in sorted(set(old) | set(new)):
        a, b = old.get(kind, {}), new.get(kind, {})
        for n in sorted(set(b) - set(a)):
            out["added"].append({"kind": kind, "name": n, "spec": b[n]})
        for n in sorted(set(a) - set(b)):
            out["removed"].append({"kind": kind, "name": n, "spec": a[n]})
        for n in sorted(set(a) & set(b)):
            if a[n] != b[n]:
                out["changed"].append({"kind": kind, "name": n,
                                       "old": a[n], "new": b[n]})
            else:
                out["unchanged"] += 1
    return out


def _deps_result(package: str, kind: str, where: str, a: dict[Any, Any], b: dict[Any, Any],
                 scratch: str) -> dict[str, Any]:
    code_a, code_b = _code_counts(a["files"]), _code_counts(b["files"])
    vel = _deps_velaris(a, b, scratch)
    capability = ("unknown" if vel is None
                  else "partial" if code_a or code_b else "derived")
    hooks = _hooks_diff(a["hooks"], b["hooks"])
    declared = _declared_diff(a["declared"], b["declared"])
    not_derived = []
    if vel is None:
        held = _describe_code(code_b) or _describe_code(code_a)
        not_derived.append(
            f"Neither {a['version']} nor {b['version']} holds a .vel file, so "
            f"there is no declared capability surface to compare. "
            + (f"What this package holds is {held}, and what that code can "
               f"do when it runs - files, network, processes, the "
               f"environment - is not derived from it: nothing in it states "
               f"that in a form that can be checked. " if held else
               "It holds no code deps-diff recognises either. ")
            + "Nothing here says the upgrade is safe.")
    elif code_a or code_b:
        before = "" if code_a == code_b else (
            f" ({a['version']} held {_describe_code(code_a) or 'none'})")
        not_derived.append(
            f"The surface above is of the .vel files alone. {b['version']} "
            f"also holds {_describe_code(code_b) or 'no other code'}{before}, "
            f"and what that code can do is not derived and is not in it.")
    if hooks["added"] or hooks["changed"] or hooks["unchanged"]:
        not_derived.append("What an install-time script does is not derived: "
                           "the report says that one was added or changed, "
                           "not what it does.")
    gained =bool((vel and vel["findings"]) or hooks["added"]
                  or hooks["changed"])
    exit_code = 1 if gained else 0 if capability == "derived" else 3

    def side(v: Any, code: Any) -> dict[str, Any]:
        return {"version": v["version"], "read": v["read"],
                "surface_from": v["surface_from"],
                "files": len(v["files"]),
                "velaris_files": sum(1 for p in v["files"]
                                     if p.endswith(".vel")),
                "other_code": code, "notes": v["notes"]}

    return {"schema": DEPS_DIFF_SCHEMA, "velaris_version": VERSION,
            "package": package, "source": kind, "name": where,
            "old": side(a, code_a), "new": side(b, code_b),
            "capability": capability, "velaris": vel,
            "install_time": hooks, "dependencies": declared,
            "not_derived": not_derived, "gained": gained,
            "exit": exit_code}


def deps_diff(package: str, old: str, new: str) -> dict[Any, Any]:
    """What version `new` of a dependency can do that `old` could not, as
    a velaris.deps-diff/1 document. DepsError when either version cannot
    be read."""
    import shutil
    import tempfile
    kind, where = _deps_source(package)
    for v in (old, new):
        if not v or v.startswith("-") or any(ch.isspace() for ch in v):
            raise DepsError(f"'{v}' is not a version")
    scratch = tempfile.mkdtemp(prefix="velaris-deps-")
    try:
        if kind == "pypi":
            a, b = _read_pypi(where, old), _read_pypi(where, new)
        elif kind == "npm":
            a, b = _read_npm(where, old), _read_npm(where, new)
        elif kind == "git":
            a = _read_git(where, old, scratch)
            b = _read_git(where, new, scratch)
        else:
            a, b = _read_dir(where, old), _read_dir(where, new)
        return _deps_result(package, kind, where, a, b, scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


# ---- saying it ----------------------------------------------------------------

def _deps_finding_lines(item: dict[Any, Any], old: str) -> list[Any]:
    """A finding of deps-diff as the report prints it: what the newer
    version gained, where, and through which calls."""
    out = []
    if item["kind"] == "grant":
        what = (f"a new effect, {item['effect']}" if item["new_effect"]
                else f"not in {old}'s surface" if item["outside_surface"]
                else f"in {old}'s surface, not in this file's entry there")
        out.append(f"GAINED  {item['grant']} - {what}")
        for q in item["programs"]:
            out.append(f"    in {q['file']}")
            for s in q["origins"][:4]:
                lit = f'("{s["literal"]}")' if s.get("literal") else ""
                call = f" calls {s['call']}{lit}" if s.get("call") \
                    else " declares it"
                out.append(f"      {s['file']}:{s['line']}  "
                           f"{s['function']}{call}")
            if q["reached_from"]:
                out.append(f"      reached from "
                           f"{' -> '.join(q['reached_from'])}")
    elif item["kind"] == "count":
        now = ("no bound" if item["current"] is None
               else f"at most {item['current']}")
        had = item["surface_allows"] if item["outside_surface"] \
            else item["entry_allows"]
        out.append(f"GAINED  {item['effect']} operations in {item['file']}: "
                   f"{now} in a run; {old} had at most {had}")
        out.append(f"    {item['function']} (line {item['line']})"
                   + (f": {item['why']}" if item.get("why") else ""))
    else:
        out.append(f"GAINED  {item['file']}: {item['function']} now declares "
                   f"{', '.join(item['gained'])} (in {old} it declared "
                   f"{', '.join(item['had']) or 'nothing'})")
        for b in item["because"]:
            effect, _, rest = b.partition(": ")
            out.append(f"    {effect}: {item['function']} {rest}")
    return out


def _hook_text(h: dict[Any, Any], where: Any = None) -> str:
    if h["kind"] == "npm-script":
        return (f"npm {h['name']}: {h['command']}"
                + (" (npm's default for binding.gyp)" if h.get("implicit")
                   else "")
                + (f" [{', '.join(where)}]" if where
                   and where != ["package.json"] else ""))
    if h["kind"] == "setup.py":
        return "setup.py, run when pip builds the sdist"
    if h["kind"] == "build-backend":
        return (f"build backend {h['name']}"
                + (f", requiring {', '.join(h['requires'])}"
                   if h.get("requires") else "")
                + ", run when pip builds the sdist")
    return f"{h['name']}, a .pth file run at every start of Python"


def deps_diff_lines(result: dict[Any, Any]) -> list[Any]:
    """velaris deps-diff's report, as text."""
    old, new = result["old"]["version"], result["new"]["version"]
    L = [f"velaris deps-diff: {result['package']} {old} -> {new}"]
    for side in (result["old"], result["new"]):
        for r in side["read"]:
            where = r.get("url") or r.get("path") or r.get("commit")
            L.append(f"  read {side['version']}: {r['artifact']} {where}")
    vel = result["velaris"]
    if vel is not None:
        state = ("widened" if vel["widened"] else
                 "narrowed" if vel["narrowed"] else "unchanged")
        L.append(f"  capability surface of the .vel files "
                 f"({len(vel['files']['old'])} in {old}, "
                 f"{len(vel['files']['new'])} in {new}): {state}")
        for f in vel["findings"]:
            L.extend("    " + line for line in _deps_finding_lines(f, old))
        for n in vel["narrowed"]:
            L.append(f"    narrowed: {n}")
        for n in vel["notes"]:
            L.append(f"    note: {n}")
    else:
        L.append("  capability surface: UNKNOWN")
    for text in result["not_derived"]:
        L.append(f"  not derived: {text}")
    hooks = result["install_time"]
    if not any(hooks[k] for k in ("added", "changed", "removed", "unchanged")):
        L.append("  install-time scripts: none in either version")
    else:
        L.append("  install-time scripts:")
        for h, where in _grouped(hooks["added"], lambda x: x):
            L.append(f"    ADDED    {_hook_text(h, where)}")
        for c, where in _grouped(hooks["changed"], lambda x: x["new"]):
            L.append(f"    CHANGED  {_hook_text(c['new'], where)}: "
                     + "; ".join(c["what"]))
        for h, where in _grouped(hooks["removed"], lambda x: x):
            L.append(f"    removed  {_hook_text(h, where)}")
        for h, where in _grouped(hooks["unchanged"], lambda x: x):
            L.append(f"    same     {_hook_text(h, where)}")
    d = result["dependencies"]
    if d is None:
        L.append("  declared dependencies: none read - neither version has "
                 "a manifest that declares them (a Velaris library names "
                 "what it imports in its source)")
    elif not (d["added"] or d["removed"] or d["changed"]):
        L.append(f"  declared dependencies: unchanged ({d['unchanged']})")
    else:
        L.append("  declared dependencies:")
        for x in d["added"]:
            L.append(f"    + {x['name']} {x['spec']} ({x['kind']})")
        for x in d["changed"]:
            L.append(f"    ~ {x['name']} {x['old']} -> {x['new']} "
                     f"({x['kind']})")
        for x in d["removed"]:
            L.append(f"    - {x['name']} ({x['kind']})")
    for side in (result["old"], result["new"]):
        for n in side["notes"]:
            L.append(f"  note: {n}")
    if result["gained"]:
        L.append(f"{new} gained what is marked above.")
    elif result["capability"] == "derived":
        L.append(f"nothing gained: {new} needs nothing {old} did not")
    else:
        L.append(f"nothing gained that could be seen, and the capability "
                 f"surface was not derived: this is not a finding that "
                 f"{new} is safe")
    return L


def _md(text: Any) -> str:
    """Text a pull request controls - a package name, a version, a
    script - for the inside of a code span in a comment, where GitHub
    renders no HTML and links no mention: only a backtick or a line
    break could get out."""
    return str(text).replace("`", "'").replace("\r", " ").replace("\n", " ")


def _md_text(text: Any) -> str:
    """The same, for the prose of a comment: no HTML, no @mention, no
    line break. The mention is broken with an entity for a zero-width
    space rather than the character, so the text stays ASCII: 7.1.0 wrote
    the character, and a console that is not UTF-8 - Windows' cp1252 -
    stopped printing at it."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("@", "@&#8203;")
            .replace("\r", " ").replace("\n", " "))


def _deps_sarif_add(run: "_SarifRun", result: dict[Any, Any], at: Any) -> None:
    """The findings of one deps-diff result, each placed by at(file in the
    package or None, line) -> (path or artifactLocation, line)."""
    pkg = f"{result['package']} {result['old']['version']} -> " \
          f"{result['new']['version']}"
    vel = result["velaris"]
    for f in (vel or {}).get("findings", []):
        if f["kind"] == "grant":
            q = f["programs"][0]
            s = (q["origins"] or [{"file": q["file"], "line": None}])[0]
            where, line = at(s["file"], s.get("line"))
            run.add("dependency-capability-widened",
                    f"{pkg}: {f['grant']} is needed by {q['file']}"
                    + (f" (a new effect, {f['effect']})" if f["new_effect"]
                       else f", not in {result['old']['version']}'s surface"
                       if f["outside_surface"] else ""),
                    where, line)
        elif f["kind"] == "count":
            now = "no bound" if f["current"] is None \
                else f"at most {f['current']}"
            where, line = at(f["file"], f["line"])
            run.add("dependency-capability-widened",
                    f"{pkg}: {f['file']} performs {now} {f['effect']} "
                    f"operations in a run, more than before", where, line)
        else:
            where, line = at(f["file"], f["line"])
            run.add("dependency-effect-gained",
                    f"{pkg}: '{f['function']}' now declares "
                    f"{', '.join(f['gained'])}: " + "; ".join(f["because"]),
                    where, line)
    for n in (vel or {}).get("narrowed", []):
        where, line = at(None, None)
        run.add("dependency-narrowed", f"{pkg}: {n}", where, line)
    hooks = result["install_time"]
    for h, sources in _grouped(hooks["added"], lambda x: x):
        where, line = at("package.json" if h["kind"] == "npm-script"
                         else h["name"] if h["kind"] in ("setup.py", "pth")
                         else "pyproject.toml", None)
        run.add("dependency-install-script",
                f"{pkg}: an install-time script was added: "
                f"{_hook_text(h, sources)}; what it does is not derived",
                where, line)
    for c, sources in _grouped(hooks["changed"], lambda x: x["new"]):
        h = c["new"]
        where, line = at("package.json" if h["kind"] == "npm-script"
                         else h["name"] if h["kind"] in ("setup.py", "pth")
                         else "pyproject.toml", None)
        run.add("dependency-install-script",
                f"{pkg}: an install-time script changed: "
                f"{_hook_text(h, sources)} - " + "; ".join(c["what"])
                + "; what it does is not derived", where, line)
    if result["capability"] != "derived":
        where, line = at(None, None)
        state = "unknown" if result["capability"] == "unknown" \
            else "only partly derived"
        run.add("dependency-surface-unknown",
                f"{pkg}: capability surface {state}. "
                + " ".join(result["not_derived"][:1]), where, line)
    for x in (result["dependencies"] or {}).get("added", []):
        where, line = at(None, None)
        run.add("dependency-added",
                f"{pkg}: now declares {x['name']} {x['spec']} ({x['kind']}); "
                f"its own surface was not examined", where, line)


def _package_base_uri(result: dict[Any, Any]) -> str:
    import pathlib
    r = (result["new"]["read"] or [{}])[0]
    if r.get("path"):
        return pathlib.Path(r["path"]).as_uri().rstrip("/") + "/"
    if r.get("url"):
        return cast(str, r["url"]).rstrip("/") + "/"
    if result["source"] == "git" and os.path.isdir(result["name"]):
        return pathlib.Path(os.path.abspath(result["name"])).as_uri() + "/"
    return "urn:velaris-deps-diff:" + re.sub(r"[^A-Za-z0-9._@-]+", "-",
                                             result["package"]) + "/"


def sarif_deps_diff(result: dict[Any, Any]) -> dict[Any, Any]:
    """`velaris deps-diff PACKAGE OLD NEW --sarif`: each finding at the
    file inside the newer version that holds it, relative to a base URI
    naming that version; the whole result in the run's property bag."""
    run = _SarifRun("deps-diff")
    run.base_ids["DEPENDENCY"] = {
        "uri": _package_base_uri(result),
        "description": {"text": f"{result['package']} "
                                f"{result['new']['version']}"}}

    def at(file: Any, line: Any) -> tuple[Any, ...]:
        return ({"uri": file or "", "uriBaseId": "DEPENDENCY"},
                line if file else None)

    _deps_sarif_add(run, result, at)
    run.properties["deps_diff"] = result
    return run.log()


# ---- lockfiles ----------------------------------------------------------------

def _lockfile_format(path: str) -> Any:
    """(format, ecosystem) for a lockfile's name; ("not-read", None) for
    one recognised and not read; None for a file that is not a lockfile."""
    name = os.path.basename(path)
    if name in _LOCKFILES:
        return _LOCKFILES[name]
    if re.match(r"^requirements[\w.-]*\.txt$", name):
        return ("requirements", "pypi")
    if name in _LOCKFILES_NOT_READ:
        return ("not-read", None)
    return None


def _parse_lockfile(fmt: str, text: Any) -> tuple[Any, ...]:
    """({name: {version: ...}}, notes) - the pinned versions a lockfile
    names, from the registry deps-diff reads. An entry from git, a path, a
    link, or another registry or index is left out and said: reading the
    public registry's package of the same name would compare a different
    package."""
    import urllib.parse
    out: dict[Any, Any] = {}
    notes: list[Any] = []
    if text is None:
        return out, notes
    if fmt == "npm-lock":
        try:
            doc = json.loads(text)
        except ValueError:
            return out, ["it is not JSON"]
        npm_host = urllib.parse.urlsplit(os.environ.get(
            "VELARIS_NPM_REGISTRY", "https://registry.npmjs.org")).netloc.lower()

        def elsewhere(name: Any, e: Any) -> str | None:
            v = str(e.get("version") or "")
            resolved = str(e.get("resolved") or "")
            if e.get("link") or not re.match(r"^\d", v):
                return (f"{name} is not from a registry ({v or 'a link'}); "
                        f"not read")
            if resolved:
                host = urllib.parse.urlsplit(resolved).netloc.lower()
                if not resolved.startswith(("https://", "http://")) \
                        or host != npm_host:
                    return (f"{name} {v} was resolved from "
                            f"{host or resolved.split(':', 1)[0]}, not from "
                            f"the registry deps-diff reads; not read")
            return None

        pkgs = doc.get("packages")
        if isinstance(pkgs, dict):
            for key, e in pkgs.items():
                if not key or "node_modules/" not in key \
                        or not isinstance(e, dict):
                    continue
                name = key.rsplit("node_modules/", 1)[1]
                why = elsewhere(name, e)
                if why:
                    notes.append(why)
                    continue
                out.setdefault(e.get("name") or name, {})[
                    str(e["version"])] = key
        else:
            def walk(deps: Any, trail: Any) -> None:
                for name, e in (deps or {}).items():
                    if not isinstance(e, dict):
                        continue
                    why = elsewhere(name, e)
                    if why:
                        notes.append(why)
                    else:
                        out.setdefault(name, {})[str(e["version"])] = \
                            trail + name
                    walk(e.get("dependencies"), trail + name + "/")
            walk(doc.get("dependencies"), "")
    elif fmt == "pipfile-lock":
        try:
            doc = json.loads(text)
        except ValueError:
            return out, ["it is not JSON"]
        pypi = os.environ.get("VELARIS_PYPI_URL", "https://pypi.org").rstrip(
            "/")
        indexes = {s.get("name"): str(s.get("url") or "")
                   for s in (doc.get("_meta") or {}).get("sources") or []
                   if isinstance(s, dict)}
        for section in ("default", "develop"):
            for name, e in (doc.get(section) or {}).items():
                e = e if isinstance(e, dict) else {}
                url = indexes.get(e.get("index"), "")
                if url and not url.startswith(("https://pypi.org/", pypi)):
                    notes.append(f"{name} comes from the index {url}, not "
                                 f"PyPI; not read")
                    continue
                v = str(e.get("version") or "")
                if v.startswith("=="):
                    out.setdefault(_pep508_name(name) or name, {})[v[2:]] = \
                        section
                else:
                    notes.append(f"{name} is not pinned to a version from "
                                 f"an index; not read")
    elif fmt == "toml-packages":
        for block in re.split(r"(?m)^\[\[package\]\]\s*$", text)[1:]:
            head = re.split(r"(?m)^\[", block)[0]
            n = re.search(r'(?m)^name\s*=\s*"([^"]+)"', head)
            ver = re.search(r'(?m)^version\s*=\s*"([^"]+)"', head)
            if not n or not ver:
                continue
            src = re.search(r"(?m)^source\s*=\s*\{([^}]*)\}", head)
            sub = re.search(r'(?m)^\[package\.source\]\s*\n(?:.*\n)*?'
                            r'type\s*=\s*"([^"]+)"', block)
            name = _pep508_name(n.group(1)) or n.group(1)
            if (src and not re.search(r'registry\s*=\s*"https://pypi\.org/',
                                      src.group(1))) or sub:
                notes.append(f"{name} is not from PyPI; not read")
                continue
            out.setdefault(name, {})[ver.group(1)] = "package"
    elif fmt == "requirements":
        lines = [raw.split(" #", 1)[0].strip() for raw in text.splitlines()]
        index = next((ln for ln in lines if re.match(
            r"^(-i|--index-url|--extra-index-url)(\s|=|$)", ln)), None)
        if index:
            # pip takes a pin from whichever index has it, so no pin in
            # this file is known to be PyPI's package. (The option is
            # found outside the f-string: a backslash inside one is a
            # syntax error before Python 3.12, and 7.1.0 shipped that.)
            option = re.split(r"[\s=]", index)[0]
            return out, [f"it sets a package index ({option}), so a pin may "
                         f"not come from PyPI; its pins were not read"]
        for line in lines:
            m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*"
                         r"===?\s*([^\s;\\#]+)", line)
            if m:
                out.setdefault(_pep508_name(m.group(1)), {})[m.group(3)] = \
                    "pin"
    elif fmt == "velaris-lock":
        try:
            doc = json.loads(text)
        except ValueError:
            return out, ["it is not JSON"]
        for e in doc.get("libraries") or []:
            if isinstance(e, dict) and e.get("name") and e.get("sha256"):
                out.setdefault(e["name"], {})[e["sha256"]] = e
    return out, notes


def _lock_line(text: str, fmt: str, name: str, version: str) -> Any:
    """The line of a lockfile that pins name at version, when it can be
    found; None otherwise."""
    if not text:
        return None
    lines = text.splitlines()
    if fmt == "npm-lock":
        start = [i for i, ln in enumerate(lines)
                 if re.search(r'"(?:[^"]*node_modules/)?' + re.escape(name)
                              + r'"\s*:\s*\{', ln)]
        for i in start:
            for j in range(i, min(i + 12, len(lines))):
                if f'"version": "{version}"' in lines[j]:
                    return j + 1
    elif fmt == "pipfile-lock":
        inside = False                 # within this package's own object
        for i, ln in enumerate(lines):
            key = re.match(r'^\s*"([^"]+)"\s*:\s*\{', ln)
            if key:
                inside = (_pep508_name(key.group(1)) or key.group(1)) == name
            if inside and f'"version": "=={version}"' in ln:
                return i + 1
    elif fmt == "toml-packages":
        for i, ln in enumerate(lines):
            m = re.match(r'^name\s*=\s*"([^"]+)"', ln)
            if m and (_pep508_name(m.group(1)) or m.group(1)) == name \
                    and i + 1 < len(lines) and re.match(
                        r'^version\s*=\s*"' + re.escape(version) + '"',
                        lines[i + 1]):
                return i + 2
    elif fmt == "requirements":
        for i, ln in enumerate(lines):
            m = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]*\])?\s*"
                         r"===?\s*([^\s;\\#]+)", ln)
            if m and _pep508_name(m.group(1)) == name \
                    and m.group(3) == version:
                return i + 1
    elif fmt == "velaris-lock":
        for i, ln in enumerate(lines):
            if f'"{version}"' in ln:
                return i + 1
    return None


def _lock_changes(base: dict[Any, Any], head: dict[Any, Any]) -> tuple[Any, ...]:
    """(upgrades as (name, old, new), added as (name, version), removed as
    (name, version)). A name pinned at a version the base did not have is
    compared with the highest version the base had and the head does not,
    or failing that with the highest the base had."""
    upgrades: list[tuple[str, str, str]] = []
    added: list[tuple[str, str]] = []
    removed: list[tuple[str, str]] = []
    for name in sorted(set(base) | set(head)):
        old, new = set(base.get(name, {})), set(head.get(name, {}))
        came, gone = new - old, old - new
        pool = gone or old
        for v in sorted(came, key=_ver_key):
            if pool:
                upgrades.append((name, max(pool, key=_ver_key), v))
            else:
                added.append((name, v))
        if not new:
            removed.extend((name, v) for v in sorted(gone, key=_ver_key))
    return upgrades, added, removed


def _vendored_diff(name: str, old_entry: dict[Any, Any], new_entry: dict[Any, Any],
                   old_bytes: Any, new_bytes: Any) -> dict[Any, Any]:
    """deps-diff of a library velaris.lock vendors, between the file the
    base commit held and the file the working tree holds."""
    import shutil
    import tempfile
    file = new_entry.get("file") or f"lib/{name}.vel"
    a = {"version": old_entry["sha256"][:12], "read": [{
        "artifact": "vendored", "path": f"{file} at the base"}],
         "files": {} if old_bytes is None else {
             os.path.basename(file): old_bytes},
         "surface_from": "vendored", "hooks": [], "declared": None,
         "notes": [] if old_bytes is not None else [
             f"the base commit does not hold {file}"]}
    b = {"version": new_entry["sha256"][:12], "read": [{
        "artifact": "vendored", "path": f"{file} in the working tree"}],
         "files": {} if new_bytes is None else {
             os.path.basename(file): new_bytes},
         "surface_from": "vendored", "hooks": [], "declared": None,
         "notes": [] if new_bytes is not None else [
             f"the working tree does not hold {file}"]}
    scratch = tempfile.mkdtemp(prefix="velaris-deps-")
    try:
        result = _deps_result(f"velaris.lock:{name}", "vendored", file, a, b,
                              scratch)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    result["not_derived"] = [t for t in result["not_derived"]
                             if not t.startswith("Neither version has a")]
    return result


def deps_review(against: str, root: str = ".",
                limit: int = _DEPS_MAX_UPGRADES) -> dict[str, Any]:
    """Every dependency the lockfiles under root upgrade between the git
    ref `against` and the working tree, each compared with deps_diff, as a
    velaris.deps-diff-lockfiles/1 document. RuntimeError when git cannot
    answer."""
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{against}^{{commit}}"], root).strip()
    except RuntimeError:
        raise RuntimeError(f"no commit called '{against}' in this "
                           f"repository (a shallow clone may need: git "
                           f"fetch --depth=1 origin {against})")
    prefix = _git(["rev-parse", "--show-prefix"], root).strip()
    changed = [p for p in _git(["diff", "--name-only", "--relative", "-z",
                                commit, "--", "."], root).split("\0") if p]
    lockfiles, upgrades, added, removed, skipped = [], [], [], [], []
    budget = limit
    for rel in sorted(p for p in changed if _lockfile_format(p)):
        fmt, eco = _lockfile_format(rel)
        entry = {"file": rel, "format": fmt, "read": fmt != "not-read",
                 "notes": []}
        lockfiles.append(entry)
        if fmt == "not-read":
            entry["notes"].append("velaris deps-diff does not read this "
                                  "lockfile's format, so nothing about its "
                                  "upgrades is reported")
            continue
        try:
            base_text = _git(["show", f"{commit}:{prefix}{rel}"], root)
        except RuntimeError:
            base_text = None
        full = os.path.join(root, *rel.split("/"))
        head_text = None
        if os.path.exists(full):
            with open(full, encoding="utf-8", errors="replace") as fh:
                head_text = fh.read()
        base, _ = _parse_lockfile(fmt, base_text)
        head, notes_h = _parse_lockfile(fmt, head_text)
        said = sorted(set(notes_h))       # what the tree's lockfile left out
        entry["notes"] += said[:20] + ([f"and {len(said) - 20} more left out"]
                                       if len(said) > 20 else [])
        ups, adds, rems = _lock_changes(base, head)
        for name, v in adds:
            added.append({"lockfile": rel, "ecosystem": eco, "name": name,
                          "version": v,
                          "line": _lock_line(cast(str, head_text), fmt, name, v)})
        for name, v in rems:
            removed.append({"lockfile": rel, "ecosystem": eco, "name": name,
                            "version": v})
        for name, old, new in ups:
            item = {"lockfile": rel, "ecosystem": eco, "name": name,
                    "old": old, "new": new,
                    "line": _lock_line(cast(str, head_text), fmt, name, new),
                    "result": None, "error": None}
            if budget <= 0:
                skipped.append(item)
                continue
            budget -= 1
            try:
                if eco == "velaris":
                    ob, nb = base[name][old], head[name][new]
                    for e in (ob, nb):           # the lockfile is the pull
                        f = str(e.get("file") or "")   # request's to write
                        if not f.endswith(".vel") or f.startswith("/") \
                                or any(p in ("", ".", "..") or ":" in p
                                       or "\\" in p for p in f.split("/")):
                            raise DepsError(
                                f"velaris.lock names {f!r} for {name}, "
                                f"which is not a .vel file inside the "
                                f"repository; not read")
                    try:
                        old_bytes = _git(["show", f"{commit}:{prefix}"
                                          f"{ob.get('file') or ''}"], root,
                                         binary=True)
                    except RuntimeError:
                        old_bytes = None
                    path = os.path.join(root, *(nb.get("file") or "").split(
                        "/"))
                    new_bytes = None
                    if nb.get("file") and os.path.isfile(path):
                        with open(path, "rb") as fh:
                            new_bytes = fh.read()
                    item["result"] = _vendored_diff(name, ob, nb, old_bytes,
                                                    new_bytes)
                else:
                    item["result"] = deps_diff(f"{eco}:{name}", old, new)
            except DepsError as e:
                item["error"] = str(e)
            upgrades.append(item)
    gained = any(u["result"] and u["result"]["gained"] for u in upgrades)
    unseen = (sum(1 for u in upgrades if u["error"] or (
        u["result"] and u["result"]["capability"] != "derived"))
        + len(skipped) + sum(1 for x in lockfiles if not x["read"]))
    return {"schema": DEPS_LOCKFILES_SCHEMA, "velaris_version": VERSION,
            "against": against, "commit": commit, "root": root,
            "lockfiles": lockfiles, "upgrades": upgrades, "added": added,
            "removed": removed, "not_compared": skipped, "limit": limit,
            "gained": gained, "not_derived": unseen,
            "exit": 1 if gained else 3 if unseen else 0}


def deps_review_lines(review: dict[Any, Any]) -> list[Any]:
    L = [f"velaris deps-diff: lockfiles changed since {review['against']} "
         f"({review['commit'][:7]}): "
         + (", ".join(x["file"] for x in review["lockfiles"]) or "none")]
    for x in review["lockfiles"]:
        for n in x["notes"]:
            L.append(f"  {x['file']}: {n}")
    for u in review["upgrades"]:
        L.append("")
        L.append(f"{u['ecosystem']}:{u['name']} {u['old']} -> {u['new']} "
                 f"({u['lockfile']}"
                 + (f" line {u['line']})" if u["line"] else ")"))
        if u["error"]:
            L.append(f"  not compared: {u['error']}")
        else:
            L.extend("  " + ln for ln in deps_diff_lines(u["result"])[1:])
    for u in review["not_compared"]:
        L.append(f"not compared, over the limit of {review['limit']}: "
                 f"{u['ecosystem']}:{u['name']} {u['old']} -> {u['new']}")
    if review["added"]:
        L.append("")
        L.append("added, with no earlier version to compare: " + ", ".join(
            f"{a['name']} {a['version']}" for a in review["added"][:40])
            + (f" and {len(review['added']) - 40} more"
               if len(review["added"]) > 40 else ""))
    if review["removed"]:
        L.append("removed: " + ", ".join(
            f"{a['name']} {a['version']}" for a in review["removed"][:40]))
    L.append("")
    L.append("gained: yes - see above" if review["gained"] else
             "nothing gained that could be seen; "
             f"{review['not_derived']} dependenc(ies) or lockfile(s) could "
             f"not be derived, which is not a finding that they are safe"
             if review["not_derived"] else "nothing gained")
    return L


def deps_markdown(review: dict[Any, Any]) -> str:
    """The pull-request comment: what each upgraded dependency gained,
    with what could not be seen said as plainly as what could."""
    L = [DEPS_COMMENT_MARKER, "## What each upgraded dependency gained", ""]
    if not review["lockfiles"]:
        L.append(f"No lockfile in this pull request changes since the base "
                 f"`{review['commit'][:7]}` any more.")
        L.append("")
        L.append("<sub>Posted by the Velaris action (deps-diff); this "
                 "comment is edited in place on later runs.</sub>")
        return "\n".join(L)
    L.append("Lockfiles changed since the base `"
             + review["commit"][:7] + "`: "
             + ", ".join(f"`{_md(x['file'])}`" for x in review["lockfiles"])
             + ".")
    L.append("")
    L.append("For a Velaris library this compares the capability surface "
             "the two versions declare. For any other package it reads the "
             "install-time scripts and the declared dependencies, and "
             "nothing more: what Python or JavaScript code does cannot be "
             "derived from it, so those rows say **unknown**, and unknown is "
             "not safe. Either way it sees what is declared, not what the "
             "code does when it runs.")
    for u in review["upgrades"]:
        where = f"`{_md(u['lockfile'])}`" + (f" line {u['line']}"
                                              if u["line"] else "")
        L.append("")
        L.append(f"### `{_md(u['ecosystem'])}:{_md(u['name'])}` "
                 f"`{_md(u['old'])}` -> `{_md(u['new'])}` ({where})")
        L.append("")
        if u["error"]:
            L.append(f"**Not compared:** {_md_text(u['error'])}")
            continue
        r = u["result"]
        vel = r["velaris"]
        if vel is not None and vel["findings"]:
            L.append("**Gained:**")
            for f in vel["findings"]:
                if f["kind"] == "grant":
                    q = f["programs"][0]
                    s = (q["origins"] or [{}])[0]
                    L.append(f"- `{_md(f['grant'])}` - "
                             + (f"a new effect, `{f['effect']}`"
                                if f["new_effect"] else "within an effect "
                                "the old version already had")
                             + (f"; `{_md(s['file'])}:{s['line']}` in "
                                f"`{_md(s['function'])}`" if s else ""))
                elif f["kind"] == "count":
                    now = "no bound" if f["current"] is None \
                        else f"at most {f['current']}"
                    L.append(f"- {now} `{f['effect']}` operations in a run "
                             f"in `{_md(f['file'])}`")
                else:
                    L.append(f"- `{_md(f['function'])}` in "
                             f"`{_md(f['file'])}` now declares "
                             + ", ".join(f"`{e}`" for e in f["gained"]))
        elif vel is not None:
            L.append("Capability surface of the `.vel` files: "
                     + ("narrowed." if vel["narrowed"] else "unchanged."))
        if r["capability"] == "unknown":
            L.append(f"**Capability surface: unknown.** "
                     f"{_md_text(r['not_derived'][0])}")
        elif r["capability"] == "partial":
            L.append(f"**Capability surface: partly derived.** "
                     f"{_md_text(r['not_derived'][0])}")
        hooks = r["install_time"]
        bits = ([f"**added** `{_md(_hook_text(h, s))}`"
                 for h, s in _grouped(hooks["added"], lambda x: x)]
                + [f"**changed** `{_md(_hook_text(c['new'], s))}` - `"
                   + _md("; ".join(c["what"])) + "`"
                   for c, s in _grouped(hooks["changed"], lambda x: x["new"])]
                + [f"removed `{_md(_hook_text(h, s))}`"
                   for h, s in _grouped(hooks["removed"], lambda x: x)])
        L.append("")
        L.append("- install-time scripts: " + ("; ".join(bits) if bits else
                                                "unchanged" if
                                                hooks["unchanged"] else
                                                "none in either version"))
        d = r["dependencies"]
        if d is None:
            L.append("- declared dependencies: none read (no manifest "
                     "declares them)")
        else:
            bits = ([f"+ `{_md(x['name'])}` `{_md(x['spec'])}`"
                     for x in d["added"]]
                    + [f"~ `{_md(x['name'])}` `{_md(x['old'])}` -> "
                       f"`{_md(x['new'])}`" for x in d["changed"]]
                    + [f"- `{_md(x['name'])}`" for x in d["removed"]])
            L.append("- declared dependencies: " + ("; ".join(bits[:20])
                                                     if bits else "unchanged"))
    if review["not_compared"]:
        L.append("")
        L.append(f"Not compared, over the limit of {review['limit']}: "
                 + ", ".join(f"`{_md(u['name'])}` `{_md(u['new'])}`"
                             for u in review["not_compared"][:40]) + ".")
    if review["added"]:
        L.append("")
        L.append("Added, with no earlier version to compare: "
                 + ", ".join(f"`{_md(a['name'])}` `{_md(a['version'])}`"
                             for a in review["added"][:40])
                 + (f" and {len(review['added']) - 40} more"
                    if len(review["added"]) > 40 else "") + ".")
    unread = [x for x in review["lockfiles"] if not x["read"]]
    if unread:
        L.append("")
        L.append("Changed and not read, because deps-diff does not read "
                 "their format: " + ", ".join(f"`{_md(x['file'])}`"
                                              for x in unread) + ".")
    L.append("")
    L.append("<sub>Posted by the Velaris action (deps-diff); this comment is "
             "edited in place on later runs.</sub>")
    body = "\n".join(L)
    if len(body) > 60000:                     # GitHub stops at 65536
        body = body[:60000] + ("\n\n... cut here: the comment is too long. "
                               "The job log has all of it.")
    return body


def sarif_deps_review(review: dict[Any, Any]) -> dict[Any, Any]:
    """`velaris deps-diff --against REF --sarif`: each finding at the line
    of the lockfile that pins the upgraded version."""
    run = _SarifRun("deps-diff")
    root = review["root"]
    for u in review["upgrades"]:
        path = os.path.join(root, *u["lockfile"].split("/"))

        def at(file: Any, line: Any, path: Any = path, u: Any = u) -> tuple[Any, ...]:
            return path, u["line"]

        if u["error"]:
            run.add("dependency-surface-unknown",
                    f"{u['ecosystem']}:{u['name']} {u['old']} -> {u['new']}: "
                    f"not compared: {u['error']}", path, u["line"])
            continue
        _deps_sarif_add(run, u["result"], at)
    for x in review["lockfiles"]:
        if not x["read"]:
            run.add("dependency-surface-unknown",
                    f"{x['file']} changed, and deps-diff does not read its "
                    f"format", os.path.join(root, *x["file"].split("/")),
                    None)
    run.properties["deps_diff"] = review
    return run.log()


def _github(method: str, url: str, token: str, body: Any = None) -> tuple[Any, ...]:
    import urllib.error
    import urllib.request
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"velaris/{VERSION} (deps-diff)",
        **({"Content-Type": "application/json"} if data else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, None


def deps_comment(body: str, pr: str, has_lockfiles: bool = True) -> str:
    """Post the comment, or edit the one an earlier run posted - found by
    its marker - so a pull request holds one. Reads GITHUB_TOKEN,
    GITHUB_REPOSITORY and GITHUB_API_URL. With no lockfile changed and no
    earlier comment, posts nothing. Returns what it did; RuntimeError when
    the API refuses."""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    api = os.environ.get("GITHUB_API_URL", "https://api.github.com") \
        .rstrip("/")
    if not token or not repo or not str(pr).isdigit():
        raise RuntimeError("--comment needs GITHUB_TOKEN and "
                           "GITHUB_REPOSITORY in the environment and --pr N")
    found = None
    for page in range(1, 11):              # up to 1000 comments back
        status, got = _github(
            "GET", f"{api}/repos/{repo}/issues/{pr}/comments?per_page=100"
                   f"&page={page}", token)
        if status != 200 or not isinstance(got, list):
            raise RuntimeError(f"listing the comments: HTTP {status}")
        found = next((c["id"] for c in got
                      if DEPS_COMMENT_MARKER in (c.get("body") or "")), None)
        if found is not None or len(got) < 100:
            break
    if found is not None:
        status, _ = _github("PATCH",
                            f"{api}/repos/{repo}/issues/comments/{found}",
                            token, {"body": body})
        if status != 200:
            raise RuntimeError(f"editing comment {found}: HTTP {status}")
        return f"edited comment {found}"
    if not has_lockfiles:
        return "no lockfile changed and no earlier comment: nothing posted"
    status, got = _github("POST", f"{api}/repos/{repo}/issues/{pr}/comments",
                          token, {"body": body})
    if status != 201:
        raise RuntimeError(f"posting the comment: HTTP {status}")
    return f"posted comment {(got or {}).get('id')}"


def deps_diff_main(argv: list[Any]) -> int:
    """velaris deps-diff <package> <old> <new> [--json | --sarif]
    velaris deps-diff --against REF [path] [--json | --sarif | --markdown]
                      [--comment --pr N] [--max N]
    velaris deps-diff --from FILE [...the same outputs]"""
    usage = ("usage: velaris deps-diff <package> <old-version> <new-version> "
             "[--json | --sarif]\n"
             "       velaris deps-diff --against REF [path] "
             "[--json | --sarif | --markdown] [--comment --pr N] [--max N]\n"
             "       velaris deps-diff --from FILE "
             "[--json | --sarif | --markdown] [--comment --pr N]\n"
             "  <package> is pypi:NAME, npm:NAME, git:URL-or-PATH or "
             "dir:PATH")
    opts: dict[Any, Any] = {}
    words: list[Any] = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--against", "--pr", "--max", "--from"):
            if i + 1 >= len(argv):
                print(usage, file=sys.stderr)
                return 2
            opts[a] = argv[i + 1]
            i += 2
            continue
        if a in ("--json", "--sarif", "--markdown", "--comment"):
            opts[a] = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            words.append(a)
        i += 1
    formats = [f for f in ("--json", "--sarif", "--markdown") if f in opts]
    lockfile_mode = "--against" in opts or "--from" in opts
    if len(formats) > 1 or ("--comment" in opts) != ("--pr" in opts) or (
            lockfile_mode and len(words) > 1) or (
            not lockfile_mode and (len(words) != 3 or "--comment" in opts
                                   or "--markdown" in opts
                                   or "--max" in opts)) or (
            "--against" in opts and "--from" in opts):
        print(usage, file=sys.stderr)
        return 2

    if not lockfile_mode:
        try:
            result = deps_diff(*words)
        except DepsError as e:
            print(f"velaris deps-diff: {e}", file=sys.stderr)
            return 2
        if "--json" in opts:
            print(json.dumps(result, indent=2))
        elif "--sarif" in opts:
            log = sarif_deps_diff(result)
            print(json.dumps(log, indent=2))
            print_sarif_summary(log)
        else:
            print("\n".join(deps_diff_lines(result)))
        return cast(int, result["exit"])

    if "--from" in opts:
        try:
            with open(opts["--from"], encoding="utf-8") as fh:
                review_doc = json.load(fh)
        except (OSError, ValueError) as e:
            print(f"velaris deps-diff: cannot read {opts['--from']}: {e}",
                  file=sys.stderr)
            return 2
        if review_doc.get("schema") != DEPS_LOCKFILES_SCHEMA:
            print(f"velaris deps-diff: {opts['--from']} is not a "
                  f"{DEPS_LOCKFILES_SCHEMA} document", file=sys.stderr)
            return 2
    else:
        try:
            limit = int(opts.get("--max", _DEPS_MAX_UPGRADES))
        except ValueError:
            print(usage, file=sys.stderr)
            return 2
        root = words[0] if words else "."
        try:
            review_doc = deps_review(opts["--against"], root, limit)
        except (RuntimeError, OSError) as e:
            print(f"velaris deps-diff: {e}", file=sys.stderr)
            return 2
    if "--json" in opts:
        print(json.dumps(review_doc, indent=2))
    elif "--sarif" in opts:
        log = sarif_deps_review(review_doc)
        print(json.dumps(log, indent=2))
        print_sarif_summary(log)
    elif "--markdown" in opts:
        print(deps_markdown(review_doc))
    elif "--comment" not in opts:
        print("\n".join(deps_review_lines(review_doc)))
    if "--comment" in opts:
        try:
            said = deps_comment(deps_markdown(review_doc), opts["--pr"],
                                bool(review_doc["lockfiles"]))
        except RuntimeError as e:
            print(f"velaris deps-diff: {e}", file=sys.stderr)
            return 2
        print(f"velaris deps-diff: {said}", file=sys.stderr)
    return cast(int, review_doc["exit"])
