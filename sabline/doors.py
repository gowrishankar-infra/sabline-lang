"""The HTTP door, sabline serve, and the ceilings both doors share.
"""
import json
import os
import re
import sys

from .version import VERSION
from . import naming
from .tables import (
    ALLOW_ALL,
    CHECK_MEMORY_MB_DEFAULT,
    CHECK_TIMEOUT_DEFAULT,
    DEFAULT_ALLOW,
    HAVE_Z3,
)
from .budget import (
    Budget,
    BudgetError,
    _ascii_digits,
    expand_allow,
    warn_allow_all,
)
from .findings import InvocationLog, run_outcome, run_refusals
from typing import Any, cast


def _token_problem(token: str, where: str) -> str | None:
    """Why this token will not do, without ever repeating it."""
    if len(token) < 16:
        return (f"the token in {where} is shorter than 16 characters; make "
                f"one with: python -c \"import secrets; "
                f"print(secrets.token_urlsafe(32))\"")
    if not all(0x21 <= ord(c) <= 0x7E for c in token):
        return (f"the token in {where} must be printable ASCII with no "
                f"spaces")
    return None


def _read_token_file(path: str) -> tuple[Any, ...]:
    """(token, None) or (None, why not). The file holds the token and
    nothing else; surrounding whitespace and a UTF-8 byte-order mark
    are ignored."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        return None, f"cannot read the token file {path}: {e.strerror or e}"
    raw = raw.removeprefix(b"\xef\xbb\xbf").strip()
    try:
        token = raw.decode("ascii")
    except UnicodeDecodeError:
        return None, (f"the token in {path} must be printable ASCII with "
                      f"no spaces")
    why = _token_problem(token, path)
    return (None, why) if why else (token, None)


# What a door - the HTTP door or the MCP server - lets one run take when
# its operator names nothing else: the defaults the doors have had since
# 2.59, and from 4.0 a ceiling as well. Before 4.0 a caller could send
# any timeout and any memory cap and have it, so the operator's limits
# were only the values used when a caller sent none.
DOOR_MAX_TIMEOUT = 30
DOOR_MAX_MEMORY_MB = 512
# requests a minute the HTTP door answers for one token - or, for requests
# without it, one address - unless --rate-limit says otherwise (8.1)
DOOR_RATE_LIMIT = 600


def check_ceilings(timeout_flag: Any, memory_flag: Any) -> tuple[Any, ...]:
    """(most seconds, most MB) one check or audit through a door may take,
    from --check-timeout and --check-memory-mb (None when not given): the
    ceiling `sabline check` has, 60 seconds and 2048 MB unless raised. A
    value that is not one is a ValueError holding the sentence to show."""
    most_time = CHECK_TIMEOUT_DEFAULT
    if timeout_flag is not None:
        if not (_ascii_digits(str(timeout_flag)) and int(timeout_flag) >= 1):
            raise ValueError("--check-timeout needs a whole number of "
                             "seconds, 1 or more, as --check-timeout 120")
        most_time = int(timeout_flag)
    most_memory = CHECK_MEMORY_MB_DEFAULT
    if memory_flag is not None:
        if not (_ascii_digits(str(memory_flag)) and int(memory_flag) >= 1):
            raise ValueError("--check-memory-mb needs a whole number of MB, "
                             "1 or more, as --check-memory-mb 4096")
        most_memory = int(memory_flag)
    return most_time, most_memory


def _token_matches(given: list[Any], want: Any) -> bool:
    """Does the one Authorization header a request carries hold the door's
    bearer token? `want` is the token's sha256 digest, or None when the door
    takes no token. The comparison is secrets.compare_digest over the two
    sha256 digests: its time depends on neither how long the guess is nor
    how much of it is right. A request with no header, two headers or
    another scheme is refused before any comparison; none of that is about
    the token."""
    import hashlib
    import secrets
    if want is None:
        return True
    if len(given) != 1:
        return False
    scheme, _, value = given[0].strip().partition(" ")
    if scheme.lower() != "bearer":
        return False
    got = hashlib.sha256(value.strip().encode("latin-1", "replace")).digest()
    return secrets.compare_digest(got, want)


class _RateLimit:
    """At most `per_minute` requests a minute for each key: a bucket of that
    many that refills evenly, so a burst up to the limit is answered and a
    steady stream past it is not. The door keys a request by its token when
    it carries the right one, and by its address otherwise, so a caller
    guessing tokens is limited too and cannot spend the holder's allowance.
    At most KEEP keys are remembered; the least recently seen goes first."""

    KEEP = 4096

    def __init__(self, per_minute: int) -> None:
        import threading as _threading
        self.per_minute = int(per_minute)
        self._rate = self.per_minute / 60.0
        self._lock = _threading.Lock()
        self._buckets: dict[Any, Any] = {}

    def take(self, key: str) -> float:
        """0 when this request may go ahead; otherwise the seconds until
        one could."""
        import time as _t
        now = _t.monotonic()
        with self._lock:
            level, last = self._buckets.pop(key, (float(self.per_minute),
                                                  now))
            level = min(float(self.per_minute),
                        level + (now - last) * self._rate)
            if level >= 1.0:
                level, wait = level - 1.0, 0.0
            else:
                wait = (1.0 - level) / self._rate
            self._buckets[key] = (level, now)
            while len(self._buckets) > self.KEEP:
                self._buckets.pop(next(iter(self._buckets)))
        return wait


def door_ceilings(timeout_flag: Any, memory_flag: Any) -> tuple[Any, ...]:
    """(most seconds, most MB) one run may have, from a door's
    --max-timeout and --max-memory-mb (None when not given). A value
    that is not a limit is a ValueError holding the sentence to show."""
    most_time: float = DOOR_MAX_TIMEOUT
    if timeout_flag is not None:
        try:
            most_time = float(timeout_flag)
        except ValueError:
            most_time = float("nan")
        if not (most_time > 0 and most_time != float("inf")):
            raise ValueError("--max-timeout needs a number of seconds "
                             "greater than 0, as --max-timeout 30")
        if most_time == int(most_time):
            most_time = int(most_time)
    most_memory = DOOR_MAX_MEMORY_MB
    if memory_flag is not None:
        if not (_ascii_digits(str(memory_flag)) and int(memory_flag) >= 1):
            raise ValueError("--max-memory-mb needs a whole number of MB, "
                             "1 or more, as --max-memory-mb 512")
        most_memory = int(memory_flag)
    return most_time, most_memory


def run_limits(asked: dict[Any, Any], most_time: Any, most_memory: Any) -> tuple[Any, ...]:
    """What a door gives one run: (timeout, max_memory_mb, None), or
    (None, None, (outcome, sentence)) when the request cannot have it -
    'bad_request' for a value that is not a limit, 'ceiling' for one
    past what the operator set. A limit the request leaves out is the
    operator's; a caller may ask for less, never for more."""
    def number(v: Any) -> bool:
        return isinstance(v, (int, float)) and not isinstance(v, bool)

    timeout = asked.get("timeout")
    if timeout is None:
        timeout = most_time
    elif not (number(timeout) and 0 < timeout < float("inf")):
        return None, None, ("bad_request", "timeout is a number of "
                            "seconds greater than 0")
    elif timeout > most_time:
        return None, None, ("ceiling", f"this server allows at most "
                            f"{most_time:g} second(s) per run; the request "
                            f"asked for {timeout:g}")
    memory = asked.get("max_memory_mb")
    if memory is None:
        memory = most_memory
    elif not (number(memory) and memory == int(memory) and memory >= 1):
        return None, None, ("bad_request", "max_memory_mb is a whole number "
                            "of MB, 1 or more")
    elif memory > most_memory:
        return None, None, ("ceiling", f"this server allows at most "
                            f"{most_memory} MB per run; the request asked "
                            f"for {int(memory)}")
    return timeout, int(memory), None


def serve_main(argv: list[Any]) -> int:
    """`sabline serve`: an HTTP door, so a program in any language can
    check, audit and run Sabline under a budget - not only Python and
    not only MCP clients.

    Every endpoint but GET /health needs `Authorization: Bearer
    <token>`, compared in constant time; a missing or wrong token is a
    401 that says nothing about which. The token comes from
    --token-file, else SABLINE_TOKEN (which is then removed from the
    environment the workers inherit), else it is made here and printed
    once. It is never taken as an argument: every process on the machine
    can read another's command line. --no-auth drops the token, for
    local development only, is refused on any host but 127.0.0.1 or
    localhost, and warns on every start. Every call is one line in the
    invocation log (InvocationLog).

    The operator sets the limits (4.0): --max-allow is the most a
    request's budget may grant, io when the flag is absent;
    --max-timeout and --max-memory-mb are the most one run may have, 30
    seconds and 512 MB when absent. A request for more at any of the
    three is refused with 403, naming the ceilings.
    """
    import hashlib
    import http.server
    import secrets
    import urllib.parse

    valued = {"--port", "--host", "--bind", "--max-allow", "--token-file",
              "--log-file", "--log", "--max-timeout", "--max-memory-mb",
              "--root", "--rate-limit", "--check-timeout",
              "--check-memory-mb"}
    opts: dict[Any, Any] = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--token" or a.startswith("--token="):
            print("sabline serve does not take a token as an argument: "
                  "every process on this machine can read another's "
                  "command line. Put it in a file and pass --token-file "
                  "<path>, or set SABLINE_TOKEN.", file=sys.stderr)
            return 2
        if a in ("--no-auth", "--no-confine"):
            opts[a] = True
            i += 1
            continue
        if a in valued:
            if i + 1 >= len(argv):
                print(f"{a} needs a value", file=sys.stderr)
                return 2
            opts[a] = argv[i + 1]
            i += 2
            continue
        # an option's name is repeated back; anything else is not, in
        # case it is a token typed where it should not be
        shown = f" '{a}'" if re.fullmatch(r"--[a-z][a-z-]{0,30}", a) else ""
        print(f"sabline serve: unknown argument{shown}. It takes --port, "
              f"--bind (or --host), --max-allow, --max-timeout, "
              f"--max-memory-mb, --check-timeout, --check-memory-mb, "
              f"--root, --rate-limit, --token-file, --no-auth, --log-file "
              f"and --log.", file=sys.stderr)
        return 2

    # Read SABLINE_TOKEN and take it out of the environment whichever
    # source wins, so no pool worker - and so no program - inherits it.
    # The token is settled first, so every message after this point can
    # be kept from repeating it, even one about a flag it was typed into.
    env_token = naming.pop_env("SABLINE_TOKEN")
    no_auth = "--no-auth" in opts
    token_file = opts.get("--token-file")
    token: str | None = None
    told = None
    if no_auth:
        if token_file:
            print("--no-auth and --token-file ask for opposite things; "
                  "give one", file=sys.stderr)
            return 2
    elif token_file:
        token, why = _read_token_file(token_file)
        if why:
            print(why, file=sys.stderr)
            return 2
        told = f"read from {token_file}"
    elif env_token is not None:
        token = env_token.strip()
        why = _token_problem(token, "SABLINE_TOKEN")
        if why:
            print(why, file=sys.stderr)
            return 2
        told = "read from SABLINE_TOKEN, and removed from the environment"
    else:
        token = secrets.token_urlsafe(32)
        told = "made for this run, shown once: " + token
    want = hashlib.sha256(token.encode("ascii")).digest() if token else None

    def refuse(message: str) -> int:
        print(message.replace(token, "[redacted]") if token else message,
              file=sys.stderr)
        return 2

    if "--bind" in opts and "--host" in opts \
            and opts["--bind"] != opts["--host"]:
        return refuse("--bind and --host are two names for one setting; "
                      "give one")
    # loopback unless the operator widens it, and a widened door says so on
    # stderr before it listens (8.1 names the flag --bind; --host still is)
    host = opts.get("--bind", opts.get("--host", "127.0.0.1"))
    if no_auth and host not in ("127.0.0.1", "localhost"):
        return refuse(f"--no-auth is refused with --host {host}: without "
                      f"a token, anyone who can reach the port can run "
                      f"programs. It is allowed on 127.0.0.1 or localhost "
                      f"only.")
    try:
        port = int(opts.get("--port", "8787"))
        if not 0 <= port <= 65535:
            raise ValueError
    except ValueError:
        return refuse("--port needs a whole number from 0 to 65535")
    # the ceiling: a caller may ask for anything inside it, at any level -
    # effect, module, path prefix, host, count - and nothing outside;
    # Budget.covers is the one place that rule lives. Without the flag it
    # is io, as the MCP server's is (4.0); before 4.0 a door started
    # without --max-allow granted every effect, ffi included, to anyone
    # holding the token.
    try:
        _asked_ceiling = opts.get("--max-allow", DEFAULT_ALLOW)
        if _asked_ceiling.strip() == ALLOW_ALL:
            warn_allow_all("sabline serve")
        ceiling = Budget.parse(expand_allow(_asked_ceiling))
    except BudgetError as e:
        return refuse(f"--max-allow: {e}")
    max_allow = ceiling.effects
    ceiling_list = ceiling.spec().split(",") if ceiling.spec() else []
    try:
        most_time, most_memory = door_ceilings(opts.get("--max-timeout"),
                                               opts.get("--max-memory-mb"))
        check_time, check_memory = check_ceilings(
            opts.get("--check-timeout"), opts.get("--check-memory-mb"))
    except ValueError as e:
        return refuse(str(e))
    rate = opts.get("--rate-limit", str(DOOR_RATE_LIMIT))
    if not (_ascii_digits(rate) and int(rate) >= 1):
        return refuse("--rate-limit needs a whole number of requests a "
                      "minute, 1 or more, as --rate-limit 600")
    limiter = _RateLimit(int(rate))
    # the directory a request's imports may come from (8.1): a source is
    # compiled as a file in it, so its relative imports resolve there, and
    # an import that leaves it - or is not a .vel file - is E515. Until 8.1
    # a request could import any file the door's user could read, and an
    # error quoted what it found there.
    served = opts.get("--root", os.getcwd())
    if not os.path.isdir(served):
        return refuse(f"--root: {served} is not a directory")
    served = os.path.realpath(served)
    request_file = os.path.join(served, ".sabline-request.vel")

    def over_ceiling(what: str) -> dict[str, Any]:
        return {"error": what, "max_allow": ceiling_list,
                "max_timeout": most_time, "max_memory_mb": most_memory}

    try:
        log = InvocationLog(opts.get("--log-file"), opts.get("--log", "full"),
                            redact=[token] if token else [])
    except ValueError as e:
        return refuse(f"--log: {e}")
    except OSError as e:
        return refuse(f"cannot open the log file {opts.get('--log-file')}: "
                      f"{e.strerror or e}")

    import sabline as _self              # the library half, reused whole

    # One pool per distinct budget a caller asks for, made the first
    # time that budget is seen and closed when the door stops. The
    # ceiling is checked before a pool is asked for, so a pool never
    # exists for a budget this server would refuse.
    # From 8.4 each worker also asks the operating system to hold its
    # pool's budget. --no-confine is the operator's, on this command line:
    # no request can carry it.
    confined = "--no-confine" not in opts
    if not confined:
        print("sabline serve: --no-confine: the operating system is not "
              "asked to hold any run; the budget is the only boundary",
              file=sys.stderr)
    pools = _self.PoolRegistry(confine=confined)
    # checks and audits run on their own workers, under the check ceiling,
    # so a crafted program answers E613 or E614 instead of holding a
    # request thread (8.1); a worker that answers is kept
    checker = _self.Pool(size=2, timeout=check_time,
                         max_memory_mb=check_memory, import_root=served,
                         confine=confined)
    endpoints = {("GET", "/health"), ("GET", "/"), ("GET", "/card"),
                 ("POST", "/check"), ("POST", "/audit"), ("POST", "/run")}

    class Door(http.server.BaseHTTPRequestHandler):
        def version_string(self) -> str:        # no Python version in the header
            return "sabline"

        def log_message(self, *a: Any) -> None:       # the invocation log is the log
            pass

        def answer(self, code: Any, payload: Any, headers: Any = ()) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers:
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def authorized(self) -> bool:
            return _token_matches(self.headers.get_all("Authorization")
                                  or [], want)

        def bucket(self) -> str:
            """Whose allowance a request spends: the token's when it
            carries the right one, its address's otherwise."""
            if want is not None and self.authorized():
                return "token"
            return "client:" + str(self.client_address[0])

        def not_local(self) -> tuple[Any, ...] | None:
            """With --no-auth, what stands in for the token against a web
            page open in a browser on this machine: the request must be
            addressed to 127.0.0.1 or localhost (which a DNS-rebinding
            page cannot fake), carry no Origin but this server's, and a
            POST must say it is JSON (which a page cannot send across
            origins without a preflight, and this server approves none)."""
            bound = str(cast(tuple[str, int], self.server.server_address)[1])
            ok_names = ("127.0.0.1", "localhost")
            name, _, at = (self.headers.get("Host") or "").strip() \
                .lower().partition(":")
            if name not in ok_names or at not in ("", bound):
                return 403, ("this server answers requests addressed to "
                             "127.0.0.1 or localhost only")
            origin = (self.headers.get("Origin") or "").strip().lower()
            if origin and origin not in (f"http://{n}:{bound}"
                                         for n in ok_names):
                return 403, "this server does not answer web pages"
            kind = (self.headers.get("Content-Type") or "").split(";")[0]
            if self.command == "POST" and \
                    kind.strip().lower() != "application/json":
                return 415, "send Content-Type: application/json"
            return None

        def drain(self) -> None:
            # read what the caller sent before refusing it, so the socket
            # closes cleanly instead of resetting under the answer
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return
            if 0 < n <= 2_000_000:
                self.rfile.read(n)

        def do_GET(self) -> None:
            self.call()

        def do_POST(self) -> None:
            self.call()

        do_HEAD = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_GET

        def call(self) -> None:
            started = InvocationLog.started()
            method = self.command
            where = urllib.parse.urlsplit(self.path).path.rstrip("/") or "/"
            rec: dict[str, Any] = {"outcome": "error", "budget": None, "effects": None,
                   "refusals": [], "source": None}
            try:
                wait = limiter.take(self.bucket())
                if wait:
                    self.drain()
                    rec["outcome"] = "rate_limited"
                    code, payload, headers = 429, {
                        "error": "too many requests",
                        "rate_limit": limiter.per_minute}, (
                        ("Retry-After", str(max(1, int(wait + 0.999)))),)
                else:
                    code, payload, headers = self.route(method, where, rec)
                try:
                    self.answer(code, payload, headers)
                except OSError:
                    rec["outcome"] = "caller_gone"
            finally:
                # the endpoint by name - never the path as sent, which
                # could carry anything, a token in a query string included
                log.record(started, door="http",
                           endpoint=(f"{method} {where}"
                                     if (method, where) in endpoints
                                     else f"{method} (no such endpoint)"),
                           client=self.client_address[0],
                           outcome=rec["outcome"], budget=rec["budget"],
                           effects=rec["effects"], refusals=rec["refusals"],
                           source=rec["source"],
                           run_params=rec.get("run_params"))

        def status(self) -> dict[Any, Any]:
            doc = {"sabline": VERSION, "prover": bool(HAVE_Z3),
                   "auth": "bearer" if want is not None else "none"}
            if self.authorized():
                doc["max_allow"] = sorted(max_allow)
                doc["max_timeout"] = most_time
                doc["max_memory_mb"] = most_memory
                doc["check_timeout"] = check_time
                doc["check_memory_mb"] = check_memory
                doc["rate_limit"] = limiter.per_minute
                doc["endpoints"] = ["POST /check", "POST /audit",
                                    "POST /run", "GET /card"]
            return doc

        def route(self, method: Any, where: Any, rec: Any) -> tuple[Any, ...]:
            if (method, where) == ("GET", "/health"):
                rec["outcome"] = "ok"
                return 200, self.status(), ()
            if no_auth:
                why = self.not_local()
                if why:
                    self.drain()
                    rec["outcome"] = "not_local"
                    return why[0], {"error": why[1]}, ()
            if not self.authorized():
                self.drain()
                rec["outcome"] = "unauthorized"
                return 401, {"error": "unauthorized"}, (
                    ("WWW-Authenticate", 'Bearer realm="sabline"'),)
            if (method, where) not in endpoints:
                self.drain()
                rec["outcome"] = "not_found"
                return 404, {"error": "no such endpoint"}, ()
            if method == "GET":
                rec["outcome"] = "ok"
                if where == "/card":
                    return 200, {"card": _self.card()}, ()
                return 200, self.status(), ()
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length < 0:
                    raise ValueError
            except ValueError:
                rec["outcome"] = "bad_request"
                return 400, {"error": "Content-Length is not a length"}, ()
            if length > 2_000_000:
                rec["outcome"] = "too_large"
                return 413, {"error": "that is too large"}, ()
            try:
                body = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, UnicodeDecodeError) as e:
                rec["outcome"] = "bad_request"
                return 400, {"error": f"bad JSON: {e}"}, ()
            source = body.get("source", "") if isinstance(body, dict) \
                else None
            if not isinstance(source, str) or not source.strip():
                rec["outcome"] = "bad_request"
                return 400, {"error": "send {\"source\": ...}"}, ()
            rec["source"] = source
            try:
                if where in ("/check", "/audit"):
                    got = (checker.check(source, path=request_file)
                           if where == "/check"
                           else checker.audit(source, path=request_file))
                    stopped = {p.code for p in got.problems} \
                        & {"E613", "E614"}
                    rec["outcome"] = ("timeout" if "E613" in stopped else
                                      "out_of_memory" if "E614" in stopped
                                      else "ok" if got.ok else "problems")
                    return 200, got.as_dict(), ()
                asked = body.get("allow") or ["io"]
                if not isinstance(asked, list) or \
                        not all(isinstance(a, str) for a in asked):
                    rec["outcome"] = "bad_request"
                    return 400, {"error": "allow is a list of grants, "
                                          "as [\"io\"]"}, ()
                try:
                    wanted = _self.Budget.parse(",".join(asked))
                except _self.BudgetError as e:
                    rec["outcome"] = "bad_request"
                    return 400, {"error": str(e)}, ()
                refused = ceiling.covers(wanted)
                if refused:
                    rec["outcome"] = "ceiling"
                    rec["refusals"] = [{"by": "ceiling", "what": refused}]
                    return 403, over_ceiling(refused), ()
                # the time and memory a run may have are the operator's
                # too: a caller may ask for less, and asking for more is
                # refused the way an over-wide budget is (4.0)
                timeout, memory, why = run_limits(body, most_time,
                                                  most_memory)
                if why:
                    rec["outcome"] = why[0]
                    if why[0] == "ceiling":
                        rec["refusals"] = [{"by": "ceiling",
                                            "what": why[1]}]
                        return 403, over_ceiling(why[1]), ()
                    return 400, {"error": why[1]}, ()
                rec["budget"] = wanted.spec()
                seed, frozen = body.get("seed"), body.get("freeze_time")
                if seed is not None and not isinstance(seed, int):
                    rec["outcome"] = "bad_request"
                    return 400, {"error": "seed is a whole number"}, ()
                want_receipt = body.get("receipt", False)
                if not isinstance(want_receipt, bool):
                    rec["outcome"] = "bad_request"
                    return 400, {"error": "receipt is true or false"}, ()
                try:
                    out = pools.run(
                        source, allow=set(asked),
                        stdin=body.get("stdin", ""),
                        args=body.get("args") or [],
                        seed=seed, freeze_time=frozen,
                        timeout=timeout, max_memory_mb=memory,
                        path=request_file, import_root=served,
                        _name="<source>")
                except ValueError as e:      # a bad --freeze-time, say
                    rec["outcome"] = "bad_request"
                    return 400, {"error": str(e)}, ()
                if seed is not None or frozen is not None:
                    rec["run_params"] = {"seed": seed, "freeze_time": frozen}
                rec["effects"] = out.effects_used
                rec["outcome"] = run_outcome(out)
                rec["refusals"] = run_refusals(out)
                payload = out.as_dict()
                if not want_receipt:
                    payload.pop("receipt", None)    # on request (8.1)
                payload["allowed"] = sorted(asked)
                return 200, payload, ()
            except Exception as e:
                rec["outcome"] = "error"
                return 500, {"error": f"{type(e).__name__}: {e}"}, ()

    if host not in ("127.0.0.1", "localhost"):
        # said before listening, so the line is there even when the bind
        # fails - whoever widened the door sees that they did
        print("  WARNING: not bound to localhost. This endpoint RUNS "
              "programs, and it speaks plain HTTP: the token crosses the "
              "network readable by anyone on the path unless a TLS proxy "
              "sits in front. Do not expose it to a network you do not "
              "control.", file=sys.stderr)
        sys.stderr.flush()
    try:
        httpd = http.server.ThreadingHTTPServer((host, port), Door)
    except OSError as e:
        log.close()
        checker.close()
        pools.close()
        return refuse(f"cannot listen on {host}:{port}: {e.strerror or e}")
    port = httpd.server_address[1]

    print(f"sabline {VERSION} listening on http://{host}:{port}")
    print("  POST /check /audit /run   GET /card /health")
    print(f"  grants at most: {ceiling.spec() or 'nothing'}"
          + ("   (the default; --max-allow to change it)"
             if "--max-allow" not in opts else ""))
    print(f"  each run at most: {most_time:g} second(s), {most_memory} MB"
          + ("" if "--max-timeout" in opts and "--max-memory-mb" in opts
             else "   (--max-timeout, --max-memory-mb)"))
    print(f"  each check or audit at most: {check_time} second(s), "
          f"{check_memory} MB   (--check-timeout, --check-memory-mb)")
    print(f"  imports from: {served}   (--root)")
    print(f"  at most {limiter.per_minute} requests a minute per token, or "
          f"per address without it   (--rate-limit)")
    if token is not None:
        print("  every endpoint but GET /health needs "
              "'Authorization: Bearer <token>'")
        print(f"  token: {told}")
    where_log = opts.get("--log-file") or "stderr"
    print(f"  log: one JSON line per call ({log.detail}) to {where_log}")
    sys.stdout.flush()
    if no_auth:
        bar = "  " + "!" * 66
        print("\n".join([
            bar,
            "  WARNING: --no-auth. No token is asked for. Any process on",
            "  this machine, run by any user, can send this server a",
            f"  program and it runs, with up to: {ceiling.spec() or 'nothing'}",
            "  This is for local development only. A request must be",
            "  addressed to 127.0.0.1 or localhost, carry no other",
            "  Origin, and POST as Content-Type: application/json, so a",
            "  web page in a browser here cannot use it; nothing stops a",
            "  local program.",
            bar]), file=sys.stderr)
    if token_file and os.name != "nt":
        try:
            if os.stat(token_file).st_mode & 0o077:
                print(f"  WARNING: {token_file} can be read by other users "
                      f"on this machine; chmod 600 it", file=sys.stderr)
        except OSError:
            pass
    if "ffi" in max_allow:
        print("  note: ffi is grantable here, which means a caller "
              "can do anything Python can. --max-allow io,fs is "
              "safer for a shared machine.")
    sys.stdout.flush()
    sys.stderr.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
        pools.close()                     # no worker outlives the door
        checker.close()
        log.close()
    return 0
