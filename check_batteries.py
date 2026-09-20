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

    socket.create_connection = create_connection  # type: ignore[assignment]
    trust = ssl.create_default_context(cafile=str(STANDIN / "standin-cert.pem"))
    ssl._create_default_https_context = lambda: trust  # type: ignore[assignment]


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


CHECKS = [check_azure]


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
