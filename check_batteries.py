#!/usr/bin/env python3
"""The batteries, each against a stand-in for the service it talks to.

    python check_batteries.py

stdlib/azure.vel, k8s.vel, github.vel and aws.vel are written in Velaris and
call no Python. Each is run here, by this implementation, against a server
in this process that answers as the real one does - paging, the error
shapes, a rate limit, a signature checked the way AWS checks one - and what
the server received is held to what the API expects.

The libraries name their hosts as text (`https://management.azure.com:443/`
and so on), which is the point of them, so the stand-in does not change the
URL: the run's budget is the real host's, the request is made to the real
host's name over TLS, and only where that name connects to is changed, in
this process, to the stand-in's port on 127.0.0.1. The certificate is
tests/standin/standin-cert.pem, self-signed, for those names, and trusted
by nothing but this script.

Each example under examples/ops is also audited: no Python module, and the
hosts the library's text fixes.
"""
import datetime
import hashlib
import hmac
import http.server
import json
import os
import socket
import ssl
import sys
import threading
import urllib.parse
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from suite_dirs import isolate  # noqa: E402

HERE = Path(__file__).parent
STANDIN = HERE / "tests" / "standin"
TOKEN = "standin-token-7f3a"                 # a value only this script knows


class Received:
    """Every request the stand-in got, for a test to hold to account."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def add(self, req: dict[str, Any]) -> None:
        with self.lock:
            self.requests.append(req)

    def clear(self) -> None:
        with self.lock:
            self.requests.clear()

    def all(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.requests)


RECEIVED = Received()
ROUTES: dict[str, Any] = {}         # host -> handler(method, path, headers, body)
STATE: dict[str, Any] = {}          # what a route remembers between requests


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_: Any) -> None:
        return None

    def _serve(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        req = {"host": host, "method": self.command, "path": self.path,
               "headers": {k.lower(): v for k, v in self.headers.items()},
               "body": body.decode("utf-8", "replace")}
        RECEIVED.add(req)
        route = ROUTES.get(host)
        if route is None:
            status, headers, out = 404, {}, json.dumps({"no": "such host"})
        else:
            status, headers, out = route(req)
        data = out.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", headers.pop("Content-Type",
                                                     "application/json"))
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    do_GET = do_PUT = do_PATCH = do_DELETE = do_POST = do_HEAD = _serve


def start_standin() -> int:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(STANDIN / "standin-cert.pem"),
                            str(STANDIN / "standin-key.pem"))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return int(server.server_address[1])


def reroute(port: int) -> None:
    """Every connection this process makes to one of the stand-in's names
    goes to the stand-in; anything else is refused, so a test cannot reach
    the real service by accident. The URL, the budget check and the TLS
    name are untouched."""
    real = socket.create_connection

    def create_connection(address: Any, *args: Any, **kw: Any) -> Any:
        host = str(address[0]).lower()
        if host in ROUTES:
            return real(("127.0.0.1", port), *args, **kw)
        raise OSError(f"check_batteries.py reaches no real host ({host})")

    trust = ssl.create_default_context(cafile=str(STANDIN / "standin-cert.pem"))

    def trusting() -> ssl.SSLContext:
        return trust

    vars(socket)["create_connection"] = create_connection
    vars(ssl)["_create_default_https_context"] = trusting


# ---- the checks --------------------------------------------------------------

FAILED: list[str] = []
PASSED = [0]


def expect(what: str, ok: bool, detail: Any = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != "" else ""))


def run_vel(source: str, allow: str, env: dict[str, str] | None = None,
            args: list[str] | None = None, path: str | None = None) -> Any:
    import velaris
    saved = dict(os.environ)
    os.environ.update(env or {})
    try:
        return velaris.run(source, allow=allow, args=args or [], path=path)
    finally:
        os.environ.clear()
        os.environ.update(saved)


def audit_example(name: str, hosts: list[str] | None) -> None:
    """No Python module, no ffi effect, and the hosts the text fixes (None
    for a library whose host is the caller's)."""
    import velaris
    path = HERE / "examples" / "ops" / name
    report = velaris.audit(path.read_text(encoding="utf-8"), path=str(path))
    expect(f"{name}: compiles", report.ok,
           [p.message for p in report.problems])
    expect(f"{name}: the audit shows no ffi",
           "ffi" not in report.effects and report.ffi_modules == []
           and not report.ffi_any, (report.effects, report.ffi_modules))
    if hosts is not None:
        expect(f"{name}: the audit names exactly {hosts}",
               report.net_hosts == {"hosts": hosts, "any": False},
               report.net_hosts)


# ---- Azure -------------------------------------------------------------------

def azure_route(req: dict[str, Any]) -> tuple[int, dict[str, str], str]:
    if req["headers"].get("authorization") != f"Bearer {TOKEN}":
        return 401, {}, json.dumps({"error": {
            "code": "AuthenticationFailed", "message": "no valid token"}})
    path = req["path"]
    if path.startswith("/subscriptions/sub-1/resourcegroups?"):
        if "$skiptoken=2" in path:
            return 200, {}, json.dumps({"value": [
                {"name": "rg-data", "tags": {"owner": "data"}}]})
        STATE["azure_first"] = STATE.get("azure_first", 0) + 1
        if STATE["azure_first"] == 1:        # told to slow down, once
            return 429, {"Retry-After": "0"}, json.dumps({"error": {
                "code": "TooManyRequests", "message": "slow down"}})
        return 200, {}, json.dumps({
            "value": [{"name": "rg-web", "tags": {"owner": "web",
                                                  "cost-center": "42"}},
                      {"name": "rg-old"}],
            "nextLink": "https://management.azure.com/subscriptions/sub-1/"
                        "resourcegroups?api-version=2021-04-01&$skiptoken=2"})
    if path.startswith("/subscriptions/sub-away/"):
        return 200, {}, json.dumps({
            "value": [{"name": "rg-one"}],
            "nextLink": "https://management.azure.com.attacker.example/next"})
    if path.startswith("/subscriptions/sub-denied/"):
        return 403, {}, json.dumps({"error": {
            "code": "AuthorizationFailed",
            "message": "the client does not have authorization"}})
    if path.startswith("/subscriptions/sub-1/resourcegroups/rg-new"):
        return (200 if req["method"] != "DELETE" else 202), {}, json.dumps(
            {"name": "rg-new", "method": req["method"],
             "sent": req["body"]})
    return 404, {}, json.dumps({"error": {"code": "NotFound",
                                          "message": path}})


AZURE_WRITES = '''
import "azure.vel" as azure

fn main() uses io, env, net, declassify {
    let token = env("AZURE_TOKEN", "")
    let path = "/subscriptions/sub-1/resourcegroups/rg-new?api-version=2021-04-01"
    check azure.put_resource(token, path, json_of({"location": "westeurope"})) {
        ok reply { print(format("put {}", reply.status)) }
        fail why { print("put failed: " + why) }
    }
    check azure.patch_resource(token, path, json_of({"tags": {"owner": "ops"}})) {
        ok reply { print(format("patch {}", reply.status)) }
        fail why { print("patch failed: " + why) }
    }
    check azure.delete_resource(token, path) {
        ok reply { print(format("delete {}", reply.status)) }
        fail why { print("delete failed: " + why) }
    }
}
'''


def check_azure() -> None:
    print("azure.vel")
    ROUTES["management.azure.com"] = azure_route
    example = HERE / "examples" / "ops" / "azure_groups.vel"
    source = example.read_text(encoding="utf-8")
    budget = "io,env,declassify,net:management.azure.com:443@20"
    RECEIVED.clear()
    got = run_vel(source, budget, {"AZURE_TOKEN": TOKEN},
                  ["sub-1", "owner,cost-center"], path=str(example))
    expect("azure: two pages are one list, and the drift is reported",
           got.exit_code == 1 and "ok      rg-web" in got.output
           and "drift   rg-old: missing owner, cost-center" in got.output
           and "drift   rg-data: missing cost-center" in got.output
           and "3 group(s), 2 drifted" in got.output,
           (got.exit_code, got.output, [p.message for p in got.problems]))
    seen = RECEIVED.all()
    expect("azure: a 429 is asked again, and the next page is followed",
           [r["path"].count("skiptoken") for r in seen] == [0, 0, 1], seen)
    expect("azure: every request carries the token as a bearer header",
           all(r["headers"].get("authorization") == f"Bearer {TOKEN}"
               for r in seen))
    expect("azure: the token is nowhere in what the program printed",
           TOKEN not in got.output and TOKEN not in got.logs)
    expect("azure: the receipt counts the one grant, and the declassification",
           any(g["grant"] == "net:management.azure.com:443"
               and g["times"] == 3
               for g in got.receipt["predicate"]["grants_used"])
           and any("Authorization header" in str(d["reason"])
                   for d in got.receipt["predicate"]["declassifications"]),
           got.receipt["predicate"])
    got = run_vel(source, budget, {"AZURE_TOKEN": TOKEN},
                  ["sub-denied", "owner"], path=str(example))
    expect("azure: ARM's error shape becomes the failure's words",
           got.exit_code == 2 and "answered 403: AuthorizationFailed: the "
           "client does not have authorization" in got.output, got.output)
    got = run_vel(source, budget, {"AZURE_TOKEN": "wrong"},
                  ["sub-1", "owner"], path=str(example))
    expect("azure: a refused token is a 401 the program is told about",
           got.exit_code == 2 and "AuthenticationFailed" in got.output,
           got.output)
    RECEIVED.clear()
    got = run_vel(source, budget, {"AZURE_TOKEN": TOKEN},
                  ["sub-away", "owner"], path=str(example))
    expect("azure: a nextLink on another host is not followed",
           "1 group(s)" in got.output and len(RECEIVED.all()) == 1,
           (got.output, RECEIVED.all()))
    RECEIVED.clear()
    got = run_vel(AZURE_WRITES, budget, {"AZURE_TOKEN": TOKEN})
    sent = [(r["method"], r["body"]) for r in RECEIVED.all()]
    expect("azure: PUT, PATCH and DELETE arrive with their JSON bodies",
           got.output.split() == ["put", "200", "patch", "200", "delete",
                                  "202"]
           and sent == [("PUT", '{"location": "westeurope"}'),
                        ("PATCH", '{"tags": {"owner": "ops"}}'),
                        ("DELETE", "")], (got.output, sent, got.problems))
    got = run_vel(source, "io,env,declassify,net:example.com",
                  {"AZURE_TOKEN": TOKEN}, ["sub-1", "owner"],
                  path=str(example))
    expect("azure: under another host's grant the request is refused (E314)",
           [p.code for p in got.problems] == ["E314"], got.problems)
    got = run_vel(source, "io,env,net:management.azure.com:443",
                  {"AZURE_TOKEN": TOKEN}, ["sub-1", "owner"],
                  path=str(example))
    expect("azure: without the declassify grant the token is not sent (E310)",
           [p.code for p in got.problems] == ["E310"]
           and got.refused_effect == "declassify", got.problems)
    audit_example("azure_groups.vel", ["management.azure.com:443"])


# ---- GitHub ------------------------------------------------------------------

def github_route(req: dict[str, Any]) -> tuple[int, dict[str, str], str]:
    limits = {"X-RateLimit-Remaining": "4990", "X-RateLimit-Reset": "1790000000"}
    if req["headers"].get("authorization") != f"Bearer {TOKEN}":
        return 401, {}, json.dumps({"message": "Bad credentials"})
    path = req["path"]
    if path.startswith("/repos/octo-org/limited/"):
        return 403, {"X-RateLimit-Remaining": "0",
                     "X-RateLimit-Reset": "1790000321"}, json.dumps(
            {"message": "API rate limit exceeded"})
    if path.startswith("/repos/octo-org/octo-repo/issues?"):
        if "page=2" in path:
            return 200, dict(limits), json.dumps([
                {"number": 9, "title": "Third", "pull_request": {}}])
        return 200, dict(limits, Link=(
            '<https://api.github.com/repos/octo-org/octo-repo/issues?'
            'state=open&per_page=100&page=2>; rel="next", '
            '<https://api.github.com/repos/octo-org/octo-repo/issues?'
            'state=open&per_page=100&page=2>; rel="last"')), json.dumps([
                {"number": 3, "title": "First"},
                {"number": 7, "title": "Second, with a \"quote\""}])
    if path == "/repos/octo-org/octo-repo/releases/latest":
        return 200, dict(limits), json.dumps({"tag_name": "v1.2.3"})
    if path == "/repos/octo-org/octo-repo/issues" and req["method"] == "POST":
        return 201, dict(limits), json.dumps(
            {"number": 10, "got": json.loads(req["body"])})
    if path == "/repos/octo-org/octo-repo/issues/10/comments":
        return 201, dict(limits), json.dumps(
            {"id": 1, "got": json.loads(req["body"])})
    if path.startswith("/repos/octo-org/octo-repo/contents/docs/a%20b.md?"):
        import base64
        text = base64.encodebytes("caf\u00e9 au lait\n".encode("utf-8") * 8)
        return 200, dict(limits), json.dumps({"content": text.decode("ascii"),
                                              "encoding": "base64"})
    if path.startswith("/repos/octo-org/octo-repo/commits/main/check-runs"):
        return 200, dict(limits), json.dumps({"total_count": 2, "check_runs": [
            {"name": "tests", "conclusion": "success"},
            {"name": "lint", "conclusion": "failure"}]})
    if path.startswith("/repos/octo-org/octo-repo/pulls?"):
        return 200, dict(limits), json.dumps([{"number": 9, "title": "Third"}])
    if path == "/repos/octo-org/octo-repo/pulls/9":
        return 200, dict(limits), json.dumps({"number": 9, "merged": False})
    if path == "/repos/octo-org/octo-repo":
        return 200, dict(limits), json.dumps({"full_name": "octo-org/octo-repo"})
    if path.startswith("/users/octo-org/repos?"):
        return 200, dict(limits), json.dumps([{"name": "octo-repo"}])
    if path.startswith("/repos/octo-org/octo-repo/releases?"):
        return 200, dict(limits), json.dumps([{"tag_name": "v1.2.3"},
                                              {"tag_name": "v1.2.2"}])
    return 404, dict(limits), json.dumps({"message": "Not Found"})


GITHUB_REST = """
import "github.vel" as github

fn show(what: Text, got: Text) uses io {
    print(what + ": " + got)
}

fn main() uses io, env, net, declassify {
    let token = env("GITHUB_TOKEN", "")
    check github.create_issue(token, "octo-org", "octo-repo", "A title", "The body") {
        ok made { show("issue", made) }
        fail why { show("issue failed", why) }
    }
    check github.create_comment(token, "octo-org", "octo-repo", 10, "Seen.") {
        ok made { show("comment", made) }
        fail why { show("comment failed", why) }
    }
    check github.file_text(token, "octo-org", "octo-repo", "docs/a b.md", "main") {
        ok text { show("file", text) }
        fail why { show("file failed", why) }
    }
    check github.check_runs(token, "octo-org", "octo-repo", "main") {
        ok runs { show("checks", format("{}", length(runs))) }
        fail why { show("checks failed", why) }
    }
    check github.pulls(token, "octo-org", "octo-repo", "open") {
        ok found { show("pulls", format("{}", length(found))) }
        fail why { show("pulls failed", why) }
    }
    check github.pull(token, "octo-org", "octo-repo", 9) {
        ok found { show("pull", found) }
        fail why { show("pull failed", why) }
    }
    check github.repo(token, "octo-org", "octo-repo") {
        ok found { show("repo", found) }
        fail why { show("repo failed", why) }
    }
    check github.repos_of(token, "octo-org") {
        ok found { show("repos", format("{}", length(found))) }
        fail why { show("repos failed", why) }
    }
    check github.releases(token, "octo-org", "octo-repo") {
        ok found { show("releases", format("{}", length(found))) }
        fail why { show("releases failed", why) }
    }
    check github.issues(token, "octo-org", "limited", "open") {
        ok found { show("limited", "listed") }
        fail why { show("limited failed", why) }
    }
}
"""


def check_github() -> None:
    print("github.vel")
    ROUTES["api.github.com"] = github_route
    example = HERE / "examples" / "ops" / "github_issues.vel"
    source = example.read_text(encoding="utf-8")
    budget = "io,env,declassify,net:api.github.com:443@30"
    RECEIVED.clear()
    got = run_vel(source, budget, {"GITHUB_TOKEN": TOKEN},
                  ["octo-org", "octo-repo"], path=str(example))
    expect("github: the Link header's next page is followed, and pull "
           "requests are told from issues",
           got.exit_code == 0 and "#3  First" in got.output
           and '#7  Second, with a "quote"' in got.output
           and "2 open issue(s), 1 open pull request(s)" in got.output
           and "latest release: v1.2.3" in got.output,
           (got.output, [p.message for p in got.problems]))
    seen = RECEIVED.all()
    expect("github: the API version, the media type and the token are sent",
           all(r["headers"].get("x-github-api-version") == "2022-11-28"
               and r["headers"].get("accept") == "application/vnd.github+json"
               and r["headers"].get("authorization") == f"Bearer {TOKEN}"
               for r in seen) and len(seen) == 3, seen)
    RECEIVED.clear()
    got = run_vel(GITHUB_REST, budget, {"GITHUB_TOKEN": TOKEN})
    out = got.output
    expect("github: an issue and a comment are created with their JSON bodies",
           '"got": {"title": "A title", "body": "The body"}' in out
           and '"got": {"body": "Seen."}' in out, out)
    expect("github: contents come back as text, from base64 in lines, with "
           "the path's space encoded",
           "file: " + "caf\u00e9 au lait\n" * 8 in out, out)
    expect("github: check runs, pulls, a pull, a repo, repos and releases",
           "checks: 2" in out and "pulls: 1" in out
           and 'pull: {"number": 9' in out
           and 'repo: {"full_name": "octo-org/octo-repo"}' in out
           and "repos: 1" in out and "releases: 2" in out, out)
    expect("github: the rate limit is a failure that says when it resets",
           "limited failed: api.github.com: the rate limit is reached; it "
           "resets at 1790000321" in out, out)
    expect("github: a rate-limited request is not asked again",
           len([r for r in RECEIVED.all() if "/limited/" in r["path"]]) == 1)
    got = run_vel(source, budget, {"GITHUB_TOKEN": "wrong"},
                  ["octo-org", "octo-repo"], path=str(example))
    expect("github: bad credentials are GitHub's own message",
           got.exit_code == 1 and "answered 401: Bad credentials"
           in got.output, got.output)
    audit_example("github_issues.vel", ["api.github.com:443"])


# ---- Kubernetes --------------------------------------------------------------

def k8s_route(req: dict[str, Any]) -> tuple[int, dict[str, str], str]:
    if req["headers"].get("authorization") != f"Bearer {TOKEN}":
        return 401, {}, json.dumps({"kind": "Status", "reason": "Unauthorized",
                                    "message": "Unauthorized", "code": 401})
    url = urllib.parse.urlsplit(req["path"])
    query = urllib.parse.parse_qs(url.query)
    if url.path == "/api/v1/namespaces/default/pods":
        if query.get("watch") == ["true"]:
            return 200, {}, "\n".join(json.dumps(e) for e in (
                {"type": "ADDED", "object": {"metadata": {
                    "name": "web-1", "resourceVersion": "12"}}},
                {"type": "MODIFIED", "object": {"metadata": {
                    "name": "web-1", "resourceVersion": "13"}}})) + "\n"
        if query.get("continue") == ["page two/="]:
            return 200, {}, json.dumps({"metadata": {}, "items": [
                {"metadata": {"name": "job-1"},
                 "status": {"phase": "Succeeded"}}]})
        return 200, {}, json.dumps({
            "metadata": {"continue": "page two/="},
            "items": [{"metadata": {"name": "web-1"},
                       "status": {"phase": "Running"}},
                      {"metadata": {"name": "web-2"},
                       "status": {"phase": "Pending",
                                  "reason": "Unschedulable"}}]})
    if url.path == "/api/v1/namespaces/locked/pods":
        return 403, {}, json.dumps({
            "kind": "Status", "reason": "Forbidden", "code": 403,
            "message": 'pods is forbidden: User "sa" cannot list resource '
                       '"pods" in the namespace "locked"'})
    if url.path == "/apis/apps/v1/namespaces/default/deployments/web/scale":
        return 200, {}, json.dumps({"got": json.loads(req["body"]),
                                    "type": req["headers"].get("content-type")})
    if url.path == "/api/v1/namespaces/default/configmaps" \
            and req["method"] == "POST":
        return 201, {}, json.dumps({"created": json.loads(req["body"])})
    if url.path == "/api/v1/namespaces/default/configmaps/settings" \
            and req["method"] == "DELETE":
        return 200, {}, json.dumps({"kind": "Status", "status": "Success"})
    return 404, {}, json.dumps({"kind": "Status", "reason": "NotFound",
                                "message": url.path, "code": 404})


K8S_REST = """
import "k8s.vel" as k8s

fn main() uses io, env, fs, net, declassify {
    let c = k8s.cluster("https://kubernetes.default.svc:443", k8s.first_line(env("K8S_TOKEN", "")))
    check k8s.watch_once(c, "/api/v1/namespaces/default/pods", "11", 5) {
        ok seen { print(format("watched {}: {}", length(seen), get(seen, 1))) }
        fail why { print("watch failed: " + why) }
    }
    check k8s.write_scale(c, "default", "web", 3) {
        ok done { print("scaled: " + done) }
        fail why { print("scale failed: " + why) }
    }
    check k8s.write_create(c, "/api/v1/namespaces/default/configmaps", json_of({"metadata": {"name": "settings"}})) {
        ok done { print("created: " + done) }
        fail why { print("create failed: " + why) }
    }
    check k8s.write_delete(c, "/api/v1/namespaces/default/configmaps/settings") {
        ok done { print("deleted: " + done) }
        fail why { print("delete failed: " + why) }
    }
    check k8s.in_cluster() {
        ok found { print("in a pod") }
        fail why { print("not in a pod: " + why) }
    }
}
"""


def check_k8s() -> None:
    print("k8s.vel")
    ROUTES["kubernetes.default.svc"] = k8s_route
    example = HERE / "examples" / "ops" / "k8s_pods.vel"
    source = example.read_text(encoding="utf-8")
    server = "https://kubernetes.default.svc:443"
    budget = "io,env,declassify,net:kubernetes.default.svc:443@10"
    RECEIVED.clear()
    got = run_vel(source, budget, {"K8S_TOKEN": TOKEN}, [server, "default"],
                  path=str(example))
    expect("k8s: a list is followed through metadata.continue, and the pod "
           "that is not running is named with its reason",
           got.exit_code == 1
           and "web-2  Pending  Unschedulable" in got.output
           and "3 pod(s), 1 not running" in got.output,
           (got.output, [p.message for p in got.problems]))
    paths = [r["path"] for r in RECEIVED.all()]
    expect("k8s: the continue token is sent back encoded",
           paths == ["/api/v1/namespaces/default/pods?limit=500",
                     "/api/v1/namespaces/default/pods?limit=500"
                     "&continue=page%20two%2F%3D"], paths)
    got = run_vel(source, budget, {"K8S_TOKEN": TOKEN}, [server, "locked"],
                  path=str(example))
    expect("k8s: a Status object becomes the failure's words",
           got.exit_code == 2 and "answered 403: Forbidden: pods is forbidden"
           in got.output, got.output)
    RECEIVED.clear()
    got = run_vel(K8S_REST, budget + ",fs:read:/var/run/secrets",
                  {"K8S_TOKEN": TOKEN + "\n"})
    out = got.output
    expect("k8s: a token file's trailing line end is not sent",
           all(r["headers"].get("authorization") == f"Bearer {TOKEN}"
               for r in RECEIVED.all()) and len(RECEIVED.all()) == 4,
           RECEIVED.all())
    expect("k8s: watch-once gives the events the server sent, in order",
           'watched 2: {"type": "MODIFIED"' in out, out)
    expect("k8s: write_scale is a merge patch of spec.replicas",
           '"got": {"spec": {"replicas": 3}}' in out
           and '"type": "application/merge-patch+json"' in out, out)
    expect("k8s: write_create and write_delete",
           'created: {"created": {"metadata": {"name": "settings"}}}' in out
           and '"status": "Success"' in out, out)
    expect("k8s: outside a pod, in_cluster is a failure and not a stop",
           "not in a pod: cannot read file" in out, out)
    import re
    text = (HERE / "stdlib" / "k8s.vel").read_text(encoding="utf-8")
    writers = set()
    for m in re.finditer(r"^fn (\w+)\((.*?)^}", text, re.M | re.S):
        if re.search(r'"(POST|PUT|PATCH|DELETE)"', m.group(2)) \
                or re.search(r"\bwrite_\w+\(", m.group(2)):
            writers.add(m.group(1))
    expect("k8s: every function that sends a changing method is named write_",
           bool(writers) and all(w.startswith("write_") for w in writers),
           writers)
    audit_example("k8s_pods.vel", None)


# ---- AWS ---------------------------------------------------------------------

AWS_KEY_ID = "AKIDSTANDIN"
AWS_SECRET = "standin/secret+key/7f3a"
AWS_SESSION = "standin-session-token"


def sigv4_problem(req: dict[str, Any], service: str) -> str | None:
    """Why this request's Signature Version 4 is not valid, or None: the
    check AWS makes, made here from the request as it arrived - its method,
    path, query, the headers it says it signed, and its body."""
    headers = req["headers"]
    auth = headers.get("authorization", "")
    if not auth.startswith("AWS4-HMAC-SHA256 "):
        return "no AWS4-HMAC-SHA256 Authorization header"
    fields = dict(part.strip().split("=", 1)
                  for part in auth[len("AWS4-HMAC-SHA256 "):].split(","))
    try:
        key_id, day, region, svc, last = fields["Credential"].split("/")
    except (KeyError, ValueError):
        return "the Credential is not key/date/region/service/aws4_request"
    if key_id != AWS_KEY_ID or svc != service or last != "aws4_request":
        return f"the credential scope is wrong: {fields['Credential']}"
    amz_date = headers.get("x-amz-date", "")
    if not amz_date.startswith(day):
        return "x-amz-date and the scope's date differ"
    sent_at = datetime.datetime.strptime(amz_date, "%Y%m%dT%H%M%SZ").replace(
        tzinfo=datetime.timezone.utc)
    if abs((datetime.datetime.now(datetime.timezone.utc)
            - sent_at).total_seconds()) > 300:
        return f"x-amz-date {amz_date} is not within five minutes of now"
    signed = fields.get("SignedHeaders", "").split(";")
    if "host" not in signed or "x-amz-date" not in signed:
        return "host and x-amz-date must be signed"
    body = req["body"].encode("utf-8")
    payload_hash = hashlib.sha256(body).hexdigest()
    if headers.get("x-amz-content-sha256") != payload_hash:
        return "x-amz-content-sha256 is not the body's sha256"
    url = urllib.parse.urlsplit(req["path"])
    query = "&".join(sorted(url.query.split("&"))) if url.query else ""
    canonical = "\n".join([
        req["method"], url.path, query,
        "".join(f"{h}:{headers.get(h, '').strip()}\n" for h in signed),
        ";".join(signed), payload_hash])
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date,
                         f"{day}/{region}/{svc}/aws4_request",
                         hashlib.sha256(canonical.encode()).hexdigest()])
    key = ("AWS4" + AWS_SECRET).encode()
    for part in (day, region, svc, "aws4_request"):
        key = hmac.new(key, part.encode(), hashlib.sha256).digest()
    want = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, fields.get("Signature", "")):
        return "SignatureDoesNotMatch"
    return None


def aws_error(code: str, message: str, status: int = 403
              ) -> tuple[int, dict[str, str], str]:
    return status, {"Content-Type": "application/xml"}, (
        f'<?xml version="1.0"?><Error><Code>{code}</Code>'
        f"<Message>{message}</Message></Error>")


def s3_route(req: dict[str, Any]) -> tuple[int, dict[str, str], str]:
    why = sigv4_problem(req, "s3")
    if why:
        return aws_error("SignatureDoesNotMatch", why)
    xml = {"Content-Type": "application/xml"}
    url = urllib.parse.urlsplit(req["path"])
    query = urllib.parse.parse_qs(url.query, keep_blank_values=True)
    if url.path == "/":
        return 200, xml, ("<ListAllMyBucketsResult><Buckets>"
                          "<Bucket><Name>logs-prod</Name></Bucket>"
                          "<Bucket><Name>a&amp;b</Name></Bucket>"
                          "</Buckets></ListAllMyBucketsResult>")
    if url.path == "/logs-prod" and query.get("list-type") == ["2"]:
        if query.get("continuation-token") == ["next/page=2"]:
            return 200, xml, ("<ListBucketResult><IsTruncated>false"
                              "</IsTruncated><Contents><Key>2026/09/c d.log"
                              "</Key></Contents></ListBucketResult>")
        return 200, xml, ("<ListBucketResult><IsTruncated>true</IsTruncated>"
                          "<NextContinuationToken>next/page=2"
                          "</NextContinuationToken>"
                          "<Contents><Key>2026/09/a.log</Key></Contents>"
                          "<Contents><Key>2026/09/b.log</Key></Contents>"
                          "</ListBucketResult>")
    if url.path == "/logs-prod/notes/caf%C3%A9%20au%20lait.txt":
        if req["method"] == "PUT":
            STATE["s3_object"] = req["body"]
            return 200, xml, ""
        if req["method"] == "DELETE":
            STATE.pop("s3_object", None)
            return 204, xml, ""
        if "s3_object" in STATE:
            return 200, {"Content-Type": "text/plain"}, STATE["s3_object"]
    return aws_error("NoSuchKey", "The specified key does not exist.", 404)


def sts_route(req: dict[str, Any]) -> tuple[int, dict[str, str], str]:
    why = sigv4_problem(req, "sts")
    if why:
        return aws_error("SignatureDoesNotMatch", why)
    if req["headers"].get("x-amz-security-token") not in (None, AWS_SESSION):
        return aws_error("InvalidClientTokenId", "the session token is wrong")
    if "Action=GetCallerIdentity" not in req["body"]:
        return aws_error("InvalidAction", "only GetCallerIdentity is here", 400)
    return 200, {"Content-Type": "text/xml"}, (
        "<GetCallerIdentityResponse><GetCallerIdentityResult>"
        "<Arn>arn:aws:iam::123456789012:user/standin</Arn>"
        "<UserId>AIDASTANDIN</UserId><Account>123456789012</Account>"
        "</GetCallerIdentityResult></GetCallerIdentityResponse>")


AWS_OBJECTS = """
import "aws.vel" as aws

fn main() uses io, env, clock, net, declassify {
    let creds = aws.credentials_from_env("us-east-1")
    let key = "notes/café au lait.txt"
    check aws.s3_put_object(creds, "logs-prod", key, "first line\\nsecond, with é") {
        ok status { print(format("put {}", status)) }
        fail why { print("put failed: " + why) }
    }
    check aws.s3_get_object(creds, "logs-prod", key) {
        ok text { print("got: " + text) }
        fail why { print("get failed: " + why) }
    }
    check aws.s3_delete_object(creds, "logs-prod", key) {
        ok status { print(format("delete {}", status)) }
        fail why { print("delete failed: " + why) }
    }
    check aws.s3_get_object(creds, "logs-prod", key) {
        ok text { print("still there: " + text) }
        fail why { print("gone: " + why) }
    }
}
"""

AWS_VECTOR = """
import "aws.vel" as aws

fn main() uses io, env, declassify {
    let creds = AwsCredentials(key_id: "AKIDEXAMPLE", secret: env("VECTOR_SECRET", ""), session: env("VECTOR_NONE", ""), region: "us-east-1")
    let none: List of Text = []
    let headers = ["host:example.amazonaws.com", "x-amz-date:20150830T123600Z"]
    print(aws.signature(creds, "service", "20150830T123600Z", "GET", "/", none, headers, sha256("")))
    print(aws.amz_date_of(1440938160))
    print(aws.amz_date_of(951782400))
    print(aws.amz_date_of(1709251199))
    print(aws.amz_date_of(0))
}
"""


def check_aws() -> None:
    print("aws.vel")
    ROUTES["s3.us-east-1.amazonaws.com"] = s3_route
    ROUTES["sts.us-east-1.amazonaws.com"] = sts_route
    got = run_vel(AWS_VECTOR, "io,env,declassify", {
        "VECTOR_SECRET": "wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY"})
    expect("aws: the signature of AWS's own test request (get-vanilla) is "
           "the one AWS publishes, and dates are the calendar's",
           got.output.split() == [
               "5fa00fa31553b73ebf1942676e86291e8372ff2a2260956d9b8aae1d763fbf31",
               "20150830T123600Z", "20000229T000000Z", "20240229T235959Z",
               "19700101T000000Z"], (got.output, got.problems))
    example = HERE / "examples" / "ops" / "aws_buckets.vel"
    source = example.read_text(encoding="utf-8")
    budget = ("io,env,clock,declassify,net:sts.us-east-1.amazonaws.com:443,"
              "net:s3.us-east-1.amazonaws.com:443")
    keys = {"AWS_ACCESS_KEY_ID": AWS_KEY_ID, "AWS_SECRET_ACCESS_KEY": AWS_SECRET,
            "AWS_SESSION_TOKEN": ""}
    RECEIVED.clear()
    got = run_vel(source, budget, keys, ["us-east-1", "logs-prod", "2026/"],
                  path=str(example))
    expect("aws: STS and S3 accept the signatures; buckets, entities and a "
           "two-page listing come back",
           got.exit_code == 0
           and "signed in as arn:aws:iam::123456789012:user/standin"
           in got.output and "bucket  logs-prod" in got.output
           and "bucket  a&b" in got.output
           and "key     2026/09/c d.log" in got.output
           and "3 key(s)" in got.output,
           (got.output, [p.message for p in got.problems]))
    expect("aws: the secret key is in nothing that was sent or printed",
           all(AWS_SECRET not in json.dumps(r) for r in RECEIVED.all())
           and AWS_SECRET not in got.output + got.logs)
    reasons = [d["reason"] for d in
               got.receipt["predicate"]["declassifications"]]
    prints = {d.get("key_fingerprint") for d in
              got.receipt["predicate"]["declassifications"]
              if d["reason"] == "hmac signature"}
    expect("aws: the receipt records each signature as a declassification "
           "'hmac signature' with one key's fingerprint, and not the key",
           "hmac signature" in reasons and len(prints) == 1
           and all(isinstance(p, str) and len(p) == 12 for p in prints)
           and AWS_SECRET not in json.dumps(got.receipt), (reasons, prints))
    got = run_vel(source, budget, dict(keys, AWS_SESSION_TOKEN=AWS_SESSION),
                  ["us-east-1"], path=str(example))
    expect("aws: a session token is sent, and signed",
           got.exit_code == 0 and "bucket  logs-prod" in got.output,
           got.output)
    got = run_vel(source, budget, dict(keys, AWS_SECRET_ACCESS_KEY="wrong"),
                  ["us-east-1"], path=str(example))
    expect("aws: a wrong secret key is AWS's error shape, as a failure",
           got.exit_code == 1 and "AWS answered 403: SignatureDoesNotMatch"
           in got.output, got.output)
    got = run_vel(AWS_OBJECTS, budget, keys)
    expect("aws: an object with a space and a non-ASCII letter in its key is "
           "put, read back, deleted and gone",
           got.output == "put 200\ngot: first line\nsecond, with \u00e9\n"
           "delete 204\ngone: AWS answered 404: NoSuchKey The specified key "
           "does not exist.\n", (got.output, got.problems))
    got = run_vel(source, budget.replace(",declassify", ""), keys,
                  ["us-east-1"], path=str(example))
    expect("aws: without the declassify grant nothing is signed (E310)",
           [p.code for p in got.problems] == ["E310"], got.problems)
    audit_example("aws_buckets.vel", None)
    import velaris
    report = velaris.audit(source, path=str(example))
    hmacs = [d for d in (report.secrets or {})["declassifications"]
             if d.get("builtin") == "hmac_sha256_chain"]
    expect("aws: the audit lists the signature under secrets, reason 'hmac "
           "signature'",
           len(hmacs) == 1 and hmacs[0]["reason"] == "hmac signature"
           and hmacs[0]["function"] == "aws.signature", report.secrets)


CHECKS = [check_azure, check_github, check_k8s, check_aws]


def main() -> int:
    isolate("check_batteries")
    port = start_standin()
    reroute(port)
    for check in CHECKS:
        STATE.clear()
        check()
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    print(f"all {PASSED[0]} checks passed: the batteries call no Python and "
          f"speak to their services as the services expect")
    return 0


if __name__ == "__main__":
    sys.exit(main())
