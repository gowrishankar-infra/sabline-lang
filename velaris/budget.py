"""The effect budget: its grammar, and its enforcement while a program runs
(paths, hosts, proxies, Python modules, counts, the tracer).
"""
import os
import sys

from . import state as _state
from .errors import VelarisError
from .tables import (
    ALLOW_ALL,
    ALL_EFFECTS,
    DEFAULT_ALLOW,
    INT_MAX,
    INT_MIN,
    REDACTED,
)
from .values import FailSignal, MoneyValue, to_text
from typing import Any, TypeVar, cast

_Num = TypeVar("_Num", bound="int | MoneyValue")

# ---------------------------------------------------------------------------
# 4. EFFECT CHECKER — the heart of Velaris
#    Rule: a function may only cause effects it declares with `uses`.
# ---------------------------------------------------------------------------


def set_run_params(seed: Any = None, freeze_time: Any = None) -> None:
    """Install --seed / --freeze-time (or the library's seed= / freeze_time=).
    `freeze_time` is an ISO 8601 instant or an int of epoch seconds."""
    import random as _random
    g = vars(_state)
    frozen = _frozen_epoch(freeze_time)       # a bad instant fails first
    g["SEED"] = None if seed is None else int(seed)
    g["_RNG"] = _random.Random(int(seed)) if seed is not None else None
    g["FROZEN_TIME"] = frozen


def _frozen_epoch(freeze_time: Any) -> int | None:
    """--freeze-time as epoch seconds: an int, or an ISO 8601 instant (UTC
    when it names no zone). ValueError for anything else."""
    import datetime
    if freeze_time is None:
        return None
    if isinstance(freeze_time, (int, float)) and \
            not isinstance(freeze_time, bool):
        return int(freeze_time)
    text = str(freeze_time).strip().replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(
            f"--freeze-time wants an ISO 8601 instant, as "
            f"2026-01-01T00:00:00Z, not {freeze_time!r}")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return int(dt.timestamp())


def run_params() -> dict[Any, Any] | None:
    """The run's determinism parameters, or None when neither is set -
    for the invocation log (velaris.invocation/1)."""
    if _state.SEED is None and _state.FROZEN_TIME is None:
        return None
    return {"seed": _state.SEED, "freeze_time": _state.FROZEN_TIME}


def expand_allow(spec: str) -> str:
    """`all`, written on its own, as every effect; anything else
    unchanged. From 6.0 that is eight, `declassify` among them: `all`
    means all, and an operator who writes it has waived every gate,
    which is why it writes a line to stderr.

    `all` is an operator's shorthand on a command line (`--allow all`,
    `--max-allow all`), not part of the budget grammar of SPEC.md 7.1 -
    so a caller sending a budget over the HTTP door or the MCP server
    cannot write it, and `Budget.parse` never sees it. It exists because
    5.0 made `io` the default: there has to be a way to ask for what a
    run used to get, and it has to be written down when it is used.
    """
    return ",".join(ALL_EFFECTS) if spec.strip() == ALLOW_ALL else spec


def warn_allow_all(where: str = "velaris") -> None:
    """One line to stderr when an operator asks for every effect.

    Not a refusal and not advice: a record, where whoever is watching
    the terminal or the log can see it.
    """
    print(f"{where}: --allow all grants every effect "
          f"({', '.join(ALL_EFFECTS)}); nothing this run does will be "
          f"refused by the budget", file=sys.stderr)


class BudgetError(ValueError):
    """A budget that does not parse. Raised before anything runs."""


# A path or host component can hold characters the grant grammar uses as
# structure: `,` splits items, `@` marks a count, `[` `]` bracket an IPv6
# address. Those five characters (with `%` itself) are percent-encoded
# inside a path or host component and decoded when the budget is parsed,
# so `safe_command` round-trips: a path with a comma, a host with an `@`,
# an IPv6 literal all survive being written to text and read back. This
# is the escaping rule of velaris-spec v0.2 (§5.1, §5.2). Only these five
# sequences are decoded; every other `%` is literal.
_PCT_ENCODE = (("%", "%25"), (",", "%2C"), ("@", "%40"),
               ("[", "%5B"), ("]", "%5D"))
_PCT_DECODE = {"%2C": ",", "%40": "@", "%5B": "[", "%5D": "]", "%25": "%"}


def _pct_encode(s: str) -> str:
    """Encode the five structural characters in a path or host component.
    `%` first, so an already-`%`-bearing string is not double-decoded."""
    for ch, enc in _PCT_ENCODE:
        s = s.replace(ch, enc)
    return s


def _pct_decode(s: str) -> str:
    """Decode exactly the five sequences, in one left-to-right pass so a
    literal `%2C` (written `%252C`) decodes to `%2C`, not to a comma."""
    out, i, n = [], 0, len(s)
    while i < n:
        chunk = s[i:i + 3].upper()
        if s[i] == "%" and chunk in _PCT_DECODE:
            out.append(_PCT_DECODE[chunk])
            i += 3
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def _net_grant_text(host: str, port: Any) -> str:
    """One `net:` grant as canonical text: an IPv6 host in brackets, any
    other host with its structural characters percent-encoded, then an
    optional `:port`."""
    h = f"[{host}]" if ":" in host else _pct_encode(host)
    return f"net:{h}" + (f":{port}" if port else "")


def _ascii_digits(s: str) -> bool:
    """True for a non-empty run of ASCII 0-9 only - not other Unicode
    digits, which str.isdigit would accept."""
    return bool(s) and s.isascii() and s.isdigit()


class Budget:
    """What a run may touch, as written on the command line.

        io                      the console: print, read_line, args
        env                     environment variables (since 3.0)
        fs                      any file, read and write
        fs:read  fs:write       one direction, any path
        fs:read:./data          one direction, under that path only
        fs:write:./out@50       ...and at most 50 file operations
        net                     any host
        net:api.example.com     that host, any port
        net:api.example.com:443 that host and port
        net:*.example.com       one label in place of the star
        net:...@100             at most 100 network operations
        ffi                     any Python module
        ffi:math,json           those top-level modules only

    Grants are additive: two fs items grant both. A count is the
    smallest count given for that effect and applies to the whole run.
    A budget with no count is a budget on what, not on how much. Paths
    are resolved with realpath when the budget is parsed and again at
    every call, so `..` and symlinks cannot reach past a prefix; paths
    holding a comma cannot be written in this grammar.
    """

    def __init__(self) -> None:
        self.effects: set[Any] = set()
        self.modules: set[Any] | None = None
        self.fs: list[Any] | None = None        # [(kind, prefix or None)]
        self.net: list[Any] | None = None       # [(host pattern, port or None)]
        self.limits: dict[Any, Any] = {"fs": None, "net": None}
        self._fs_any = False               # a plain 'fs' was written
        self._net_any = False              # a plain 'net' was written
        self._ffi_any = False              # a plain 'ffi' was written

    # ---- parsing -------------------------------------------------------
    @classmethod
    def parse(cls, spec: str) -> "Budget":
        b = cls()
        items = [s.strip() for s in spec.split(",")]
        i = 0
        while i < len(items):
            item = items[i]
            i += 1
            if not item or item in ("''", '""'):
                # an empty budget. A shell strips the quotes; a child
                # process started with a list of arguments does not, and
                # until 3.1 `run(src, allow=set(), timeout=1)` reached the
                # child as the literal two characters '' and came back
                # E000 instead of refusing io.
                continue
            if item.startswith("ffi:"):
                b.effects.add("ffi")
                # ffi is additive like fs and net (SPEC.md §7.1, resolved
                # in spec v0.2 / Q2): a plain `ffi` anywhere grants every
                # module, and the wider grant wins, so `ffi,ffi:math` and
                # `ffi:math,ffi` both grant every module. Named modules
                # narrow only while no plain `ffi` has been written.
                raw = [item[4:].strip()]
                while i < len(items) and items[i] and ":" not in items[i] \
                        and "@" not in items[i] \
                        and items[i] not in ALL_EFFECTS:
                    raw.append(items[i])
                    i += 1
                mods = []
                for r in raw:
                    if "@" in r:      # ffi takes no count (spec Q6)
                        raise BudgetError(
                            f"'{r}': ffi takes no count; a module is a "
                            f"name, as ffi:math")
                    m = r.split(".")[0]
                    if not m:         # ffi: with no module (spec Q6)
                        raise BudgetError(
                            f"'{item}': ffi: needs a module name, as "
                            f"ffi:math")
                    mods.append(m)
                if not b._ffi_any:
                    b.modules = set() if b.modules is None else b.modules
                    b.modules.update(mods)
            elif item == "fs" or item.startswith("fs:") or \
                    item.startswith("fs@"):
                b._add_fs(item)
            elif item == "net" or item.startswith("net:") or \
                    item.startswith("net@"):
                b._add_net(item)
            elif item == "ffi":
                b.effects.add("ffi")
                b._ffi_any = True
                b.modules = None           # every module; the wider grant
            elif item in ALL_EFFECTS:
                b.effects.add(item)
            elif item == ALLOW_ALL:
                # `all` is the command line's shorthand and is expanded
                # before a budget is parsed (expand_allow), so reaching
                # here means it was written among other grants, or sent
                # by a caller over a door, where it is not a grant
                raise BudgetError(
                    f"'{ALLOW_ALL}' is not an effect. On a command line "
                    f"write it on its own - --allow {ALLOW_ALL} - which "
                    f"grants {', '.join(ALL_EFFECTS)}; in a budget "
                    f"alongside other grants, name the effects you want")
            else:
                raise BudgetError(
                    f"'{item}' is not an effect. They are: "
                    f"{', '.join(ALL_EFFECTS)} (or ffi:module, fs:read:path, "
                    f"net:host:port, with @count)")
        return b

    @staticmethod
    def _split_count(item: str) -> tuple[Any, ...]:
        """'fs:read:./x@50' -> ('fs:read:./x', 50); no count -> None.

        A count is ASCII digits only. Python's str.isdigit also accepts
        other Unicode digits, so before 3.3 `fs@٣` was read as 3 and
        `fs@²` stopped the parser with an uncaught ValueError instead of
        a budget error (spec Q6). Only 0-9 count now."""
        at = item.rfind("@")
        if at > 0 and _ascii_digits(item[at + 1:]):
            body = item[:at]
            if "@" in body:      # a second @ is a stray, not a count
                raise BudgetError(
                    f"'{item}': a grant takes at most one @count; write "
                    f"an @ inside a path as %40")
            return body, int(item[at + 1:])
        if at > 0:
            raise BudgetError(f"'{item}': what follows @ must be a whole "
                              f"number of operations, written 0-9")
        return item, None

    def _limit(self, kind: str, n: Any) -> None:
        if n is None:
            return
        cur = self.limits[kind]
        self.limits[kind] = n if cur is None else min(cur, n)

    def _add_fs(self, item: str) -> None:
        body, n = self._split_count(item)
        self.effects.add("fs")
        self._limit("fs", n)
        if body == "fs":
            self.fs = None                     # any path, either direction
            self._fs_any = True
            return
        rest = body[3:]                        # after 'fs:'
        kind, sep, path = rest.partition(":")
        if kind not in ("read", "write"):
            raise BudgetError(f"'{item}': after fs: write read or write, "
                              f"then optionally :path")
        prefix = None
        if sep:
            if not path:
                raise BudgetError(f"'{item}': the path after fs:{kind}: "
                                  f"is empty")
            # a `,` or `@` in the path arrives percent-encoded (spec v0.2
            # §5.1); decode before resolving, so the path names the file
            # it means
            prefix = os.path.normcase(os.path.realpath(_pct_decode(path)))
        if getattr(self, "_fs_any", False):
            return                             # plain fs already covers it
        if self.fs is None:
            self.fs = []
        self.fs.append((kind, prefix))

    def _add_net(self, item: str) -> None:
        body, n = self._split_count(item)
        self.effects.add("net")
        self._limit("net", n)
        if body == "net":
            self._net_any = True
            self.net = None
            return
        rest = body[4:]                        # after 'net:'
        host, port = parse_host_port(rest)
        if host.startswith("*."):
            tail = host[2:]
            if not tail or "*" in tail or "." not in tail:
                raise BudgetError(f"'{item}': the wildcard must be "
                                  f"'*.' followed by at least two labels")
            if all(lbl.isdigit() for lbl in tail.split(".")):
                raise BudgetError(f"'{item}': no wildcard over an IP "
                                  f"literal")
        elif "*" in host:
            raise BudgetError(f"'{item}': only one leading '*.' label "
                              f"is allowed")
        if getattr(self, "_net_any", False):
            return
        if self.net is None:
            self.net = []
        self.net.append((host, port))

    # ---- the other direction: back to text, and to the runtime --------
    def spec(self) -> str:
        """The budget as the command line would write it, absolute paths
        included, so a child process parses to the same budget."""
        out = []
        for e in sorted(self.effects):
            if e == "ffi":
                out.append("ffi" if self.modules is None else
                           ",".join("ffi:" + m for m in sorted(self.modules)))
            elif e == "fs":
                tail = f"@{self.limits['fs']}" if self.limits["fs"] is not None else ""
                if self.fs is None:
                    out.append("fs" + tail)
                else:
                    for kind, prefix in self.fs:
                        p = f":{_pct_encode(prefix)}" if prefix else ""
                        out.append(f"fs:{kind}" + p + tail)
            elif e == "net":
                tail = f"@{self.limits['net']}" if self.limits["net"] is not None else ""
                if self.net is None:
                    out.append("net" + tail)
                else:
                    for host, port in self.net:
                        out.append(_net_grant_text(host, port) + tail)
            else:
                out.append(e)
        return ",".join(out)

    def deny(self, names: Any) -> None:
        for name in names:
            self.effects.discard(name)
            if name == "fs":
                self.fs = None
                self.limits["fs"] = None
            elif name == "net":
                self.net = None
                self.limits["net"] = None
            elif name == "ffi":
                self.modules = None

    def install(self) -> None:
        _state.EFFECT_BUDGET.clear()
        _state.EFFECT_BUDGET.update(self.effects)
        g = vars(_state)
        g["FFI_MODULES"] = self.modules
        g["FS_GRANTS"] = None if self.fs is None else list(self.fs)
        g["NET_GRANTS"] = None if self.net is None else list(self.net)
        g["OP_LIMITS"] = dict(self.limits)
        g["OP_COUNTS"] = {"fs": 0, "net": 0}
        g["EFFECT_USES"] = {}

    @classmethod
    def current(cls) -> "Budget":
        """The budget this run is under, read back from what install()
        wrote. Nothing new is stored for it, so a pool worker has one
        less piece of state to put back between programs."""
        b = cls()
        b.effects = set(_state.EFFECT_BUDGET)
        b.modules = _state.FFI_MODULES
        b.fs = None if _state.FS_GRANTS is None else list(_state.FS_GRANTS)
        b.net = None if _state.NET_GRANTS is None else list(_state.NET_GRANTS)
        b.limits = dict(_state.OP_LIMITS)
        return b

    @staticmethod
    def snapshot() -> dict[str, Any]:
        return {"effects": set(_state.EFFECT_BUDGET), "modules": _state.FFI_MODULES,
                "fs": _state.FS_GRANTS, "net": _state.NET_GRANTS,
                "limits": dict(_state.OP_LIMITS), "counts": dict(_state.OP_COUNTS),
                "uses": dict(_state.EFFECT_USES)}

    @staticmethod
    def restore(saved: dict[Any, Any]) -> None:
        _state.EFFECT_BUDGET.clear()
        _state.EFFECT_BUDGET.update(saved["effects"])
        g = vars(_state)
        g["FFI_MODULES"] = saved["modules"]
        g["FS_GRANTS"] = saved["fs"]
        g["NET_GRANTS"] = saved["net"]
        g["OP_LIMITS"] = saved["limits"]
        g["OP_COUNTS"] = saved["counts"]
        g["EFFECT_USES"] = saved.get("uses", {})

    # ---- one budget inside another (the HTTP door's ceiling) ----------
    def covers(self, asked: "Budget") -> str | None:
        """None when everything `asked` wants sits inside this budget;
        else one sentence naming the first thing that does not."""
        for e in sorted(asked.effects):
            if e not in self.effects:
                return f"this server does not grant {e}"
        if "ffi" in asked.effects and self.modules is not None:
            if asked.modules is None:
                return "this server grants ffi for named modules only"
            extra = asked.modules - self.modules
            if extra:
                return f"this server does not grant ffi:{sorted(extra)[0]}"
        if "fs" in asked.effects:
            if self.limits["fs"] is not None and (
                    asked.limits["fs"] is None
                    or asked.limits["fs"] > self.limits["fs"]):
                return (f"this server allows at most {self.limits['fs']} "
                        f"file operations")
            if self.fs is not None:
                if asked.fs is None:
                    return "this server grants fs under named paths only"
                for kind, prefix in asked.fs:
                    if not any(_fs_grant_covers(sk, sp, kind, prefix)
                               for sk, sp in self.fs):
                        return (f"this server does not grant fs:{kind}"
                                + (f":{prefix}" if prefix else ""))
        if "net" in asked.effects:
            if self.limits["net"] is not None and (
                    asked.limits["net"] is None
                    or asked.limits["net"] > self.limits["net"]):
                return (f"this server allows at most {self.limits['net']} "
                        f"network operations")
            if self.net is not None:
                if asked.net is None:
                    return "this server grants net for named hosts only"
                for host, port in asked.net:
                    if not any(_net_grant_covers(sh, sp, host, port)
                               for sh, sp in self.net):
                        return (f"this server does not grant net:{host}"
                                + (f":{port}" if port else ""))
        return None


def parse_host_port(text: str) -> tuple[Any, ...]:
    """'api.example.com:443' -> ('api.example.com', 443); '[::1]:80' ->
    ('::1', 80); a bare host -> (host, None). Lower-cased, no trailing
    dot."""
    text = text.strip()
    if not text:
        raise BudgetError("net: needs a host")
    port = None
    if text.startswith("["):
        end = text.find("]")
        if end < 0:
            raise BudgetError(f"'{text}': unclosed [ in an IPv6 literal")
        host = _pct_decode(text[1:end])
        if not host:
            raise BudgetError(f"'{text}': the brackets hold no address")
        rest = text[end + 1:]
        if rest:
            if not rest.startswith(":") or not _ascii_digits(rest[1:]):
                raise BudgetError(f"'{text}': expected :port after ]")
            port = int(rest[1:])
    else:
        # structure is read on the encoded text - `@` and `/` are still
        # errors as raw characters, since a host that means to hold them
        # writes them percent-encoded (spec v0.2 §5.2)
        host, sep, tail = text.rpartition(":")
        if sep and _ascii_digits(tail):
            port = int(tail)
        else:
            host = text
        if "/" in host or "@" in host or not host:
            raise BudgetError(f"'{text}': a host is a name or address, "
                              f"with an optional :port")
        if ":" in host:
            # a residual colon is an unbracketed IPv6 address; it must be
            # written net:[...] so host:port is not ambiguous (spec v0.2
            # §5.2, Q5). This is what made net:::1 mean the host ':' at
            # port 1 before 3.3.
            raise BudgetError(f"'{text}': an IPv6 address must be written "
                              f"in brackets, as net:[{host}] or "
                              f"net:[{host}]:port")
        host = _pct_decode(host)
    if port is not None and not 0 < port < 65536:
        raise BudgetError(f"'{text}': port out of range")
    return host.lower().rstrip("."), port


def _fs_grant_covers(kind: str, prefix: str | None, want_kind: str,
                     want_prefix: str | None) -> bool:
    """Does a server's grant (kind, prefix) cover a caller's grant
    (want_kind, want_prefix)? Same direction, and the caller's prefix
    (None = any path) must sit under the server's (None = any path)."""
    if kind != want_kind:
        return False
    if prefix is None:
        return True
    if want_prefix is None:
        return False
    return (want_prefix == prefix
            or want_prefix.startswith(prefix.rstrip(os.sep) + os.sep))


def _host_matches(pattern: str, host: str) -> bool:
    if pattern.startswith("*."):
        tail = pattern[2:]
        return host.endswith("." + tail) and \
            "." not in host[:-len(tail) - 1] and len(host) > len(tail) + 1
    return pattern == host


def _net_grant_covers(host: str, port: Any, want_host: str, want_port: Any) -> bool:
    """Does the grant permit want_host:want_port? Both sides may be
    patterns when one budget is checked against another; a wildcard
    covers the same wildcard and any single-label host under it."""
    if port is not None and want_port != port:
        return False
    if host.startswith("*.") and want_host.startswith("*."):
        return host == want_host
    if want_host.startswith("*."):
        return False
    return _host_matches(host, want_host)


def parse_budget(spec: str) -> tuple[Any, ...]:
    """(effects, modules) - the 2.60 shape, kept for callers that only
    want those two; the scoped grants live on Budget.parse(spec)."""
    b = Budget.parse(spec)
    return b.effects, b.modules


def _flag_value(argv: list[str], flag: str) -> str | None:
    """The word after `flag`, or None when the flag is absent; a flag
    written last, with nothing after it, is a budget error rather than
    an IndexError."""
    if flag not in argv:
        return None
    i = argv.index(flag)
    if i + 1 >= len(argv):
        raise BudgetError(f"{flag} needs a value after it")
    return argv[i + 1]


def cli_budget(argv: list[Any]) -> "Budget":
    """The budget a command line asks for: --allow, then --deny.

    Since 5.0, no --allow means `io` - the console and nothing else -
    where it used to mean all seven effects. --deny narrows whatever
    --allow gave, so `--deny net` no longer grants fs and ffi by the
    back door; `--allow all` is the one way to ask for everything, and
    says so on stderr when it is used.
    """
    asked = _flag_value(argv, "--allow")
    if asked is None:
        asked = DEFAULT_ALLOW
    elif asked.strip() == ALLOW_ALL:
        warn_allow_all()
    budget = Budget.parse(expand_allow(asked))
    denied = _flag_value(argv, "--deny")
    if denied is not None:
        names = [n.strip() for n in denied.split(",") if n.strip()]
        for name in names:
            if name not in ALL_EFFECTS:
                raise BudgetError(f"'{name}' is not an effect. They are: "
                                  f"{', '.join(ALL_EFFECTS)}")
        budget.deny(names)
    return budget


# A fixed, documented list of credential locations (8.0). A plain
# `read_file` of one of these returns ordinary Text a program can print or
# send, which is exactly the leak `Secret of T` exists to stop, so it is
# refused (E318) and pointed at `read_file_secret`, which returns a Secret.
# And a credential location is never covered by a broad `fs:read:` grant
# that merely happens to sit above it: an operator must name it - or a
# path within its credential root - explicitly. So `fs:read:.` or plain
# `fs` does not silently include `~/.aws/credentials`; `fs:read:~/.aws`
# (or the file itself) does. `read_file_secret` reading an explicitly
# granted credential path is the sanctioned way and works.
def _credential_root(real: str) -> Any:
    """The credential root `real` (an already-normcased realpath) sits at
    or below, or None. For a directory family (`~/.aws`) the root is the
    directory; for a single file or a glob (`~/.netrc`, `*.pem`) it is the
    file itself, so 'named explicitly' means naming that file."""
    import fnmatch
    sep = os.sep
    home = os.path.normcase(os.path.realpath(os.path.expanduser("~")))
    base = os.path.basename(real)

    def nc(*parts: Any) -> Any:
        return os.path.normcase(os.path.join(home, *parts))

    for parts in ((".aws",), (".ssh",), (".config", "gcloud")):
        root = nc(*parts)
        if real == root or real.startswith(root + sep):
            return root
    for parts in ((".docker", "config.json"), (".kube", "config"),
                  (".netrc",)):
        root = nc(*parts)
        if real == root:
            return root
    if base == os.path.normcase(".env"):
        return real
    if fnmatch.fnmatch(base, os.path.normcase("*.pem")) or \
            fnmatch.fnmatch(base, os.path.normcase("*.key")):
        return real
    return None


def allow_path(kind: str, path: str, what: str, line: int) -> str:
    """Refuse a file operation outside the paths this run granted.

    kind is 'read', 'write' or 'any' (file_exists). The path is resolved
    with realpath before the comparison, and so is every grant, so `..`
    and symlinks cannot reach past a prefix. Returns the resolved path
    the operation should use.
    """
    real = os.path.normcase(os.path.realpath(str(path)))
    # credential locations (8.0): checked before the ordinary grant rule,
    # so plain `fs` and a broad `fs:read:` are both held to it
    cred = _credential_root(real) if kind in ("read", "any") else None
    if cred is not None:
        if what == "read_file":
            raise VelarisError("E318",
                f"'read_file' reaches '{path}' (resolved: {real}), a "
                f"documented credential location; a plain read returns "
                f"ordinary text that can be printed or sent", line,
                fixes=["read it with read_file_secret, which returns a "
                       "Secret the compiler will not let escape",
                       f"and grant its exact path: --allow fs:read:{real}"])
        wants = ("read", "write") if kind == "any" else (kind,)
        sep = os.sep
        named = _state.FS_GRANTS is not None and any(
            gkind in wants and prefix is not None
            and (real == prefix or real.startswith(prefix.rstrip(sep) + sep))
            and (prefix == cred or prefix.startswith(cred.rstrip(sep) + sep))
            for gkind, prefix in _state.FS_GRANTS)
        if not named:
            raise VelarisError("E318",
                f"'{what}' reaches '{path}' (resolved: {real}), a "
                f"documented credential location the fs grants do not name "
                f"explicitly; a broad grant does not include it", line,
                fixes=[f"grant its exact path: --allow fs:read:{real}",
                       "or use a program that does not read credentials"])
        return real
    if _state.FS_GRANTS is None:
        return real
    wants = ("read", "write") if kind == "any" else (kind,)
    for gkind, prefix in _state.FS_GRANTS:
        if gkind in wants and (prefix is None or real == prefix
                               or real.startswith(prefix.rstrip(os.sep)
                                                  + os.sep)):
            return real
    need = kind if kind != "any" else "read"
    raise VelarisError("E313",
        f"'{what}' reaches '{path}' (resolved: {real}), which this run's "
        f"fs grants do not cover", line,
        fixes=[f"allow it: --allow fs:{need}:{os.path.dirname(real) or real}",
               "or use a program that stays inside the granted paths"])


class _RedirectRefused(Exception):
    def __init__(self, target: str, why: str) -> None:
        self.target, self.why = target, why
        super().__init__(why)


def host_refusal(url: str) -> str | None:
    """Why this URL's host is outside the run's net grants, or None."""
    import urllib.parse
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return f"'{parts.scheme or '?'}' is not http or https"
    try:
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port or (443 if parts.scheme == "https" else 80)
    except ValueError as e:
        return f"the address does not parse: {e}"
    if not host:
        return "the address has no host"
    if _state.NET_GRANTS is None:
        return None
    for ghost, gport in _state.NET_GRANTS:
        if _host_matches(ghost, host) and (gport is None or gport == port):
            return None
    return (f"host {host}:{port} is not in this run's net grants "
            f"(allow it: --allow net:{host}:{port})")


def allow_host(url: str, what: str, line: int) -> None:
    """Refuse a request to a host this run did not grant (E314)."""
    why = host_refusal(url)
    if why is None:
        return
    import urllib.parse
    host = (urllib.parse.urlsplit(url).hostname or "?")
    raise VelarisError("E314",
        f"'{what}' reaches host '{host}', which this run does not allow: "
        f"{why}", line,
        fixes=["or use a program that stays with the granted hosts"])


def count_op(kind: str, what: str, line: int) -> None:
    """Spend one of the run's fs or net operations (E315 past the count)."""
    limit = _state.OP_LIMITS.get(kind)
    _state.OP_COUNTS[kind] = _state.OP_COUNTS.get(kind, 0) + 1
    if limit is not None and _state.OP_COUNTS[kind] > limit:
        raise VelarisError("E315",
            f"'{what}' is the {_state.OP_COUNTS[kind]}{_ordinal(_state.OP_COUNTS[kind])} "
            f"{kind} operation, and this run allows {limit}", line,
            fixes=[f"allow more: --allow {kind}@{_state.OP_COUNTS[kind]}",
                   "or use a program that does less"])


def _ordinal(n: int) -> str:
    return "th" if 10 <= n % 100 <= 20 else \
        {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def _proxy_for(url: str) -> Any:
    """The ambient proxy that would carry a request to `url`, as a URL
    with a scheme, or None. Reads HTTP_PROXY / HTTPS_PROXY / http_proxy
    (getproxies) and honours NO_PROXY (proxy_bypass), so a host the
    environment exempts uses no proxy."""
    import urllib.parse
    import urllib.request
    parts = urllib.parse.urlsplit(url)
    scheme = parts.scheme
    proxies = urllib.request.getproxies()
    proxy = proxies.get(scheme)
    if not proxy:
        return None
    host = parts.hostname or ""
    try:
        if host and urllib.request.proxy_bypass(host):
            return None
    except Exception:
        pass
    if "://" not in proxy:
        proxy = "http://" + proxy
    return proxy


def guarded_opener(url: str) -> Any:
    """An opener whose redirects are held to the same net grants, which
    refuses to leave http(s), and which - from 8.0 - bounds the socket
    peer, not only the URL string.

    Through 7.x the opener kept urllib's default ProxyHandler, so an
    ambient HTTP_PROXY / HTTPS_PROXY routed the request (its payload
    included) to a proxy that need not be a granted host: `net:` bounded
    the URL, not the peer (THREAT_MODEL.md, fixed here). Now ambient
    proxies are disabled unless the proxy's own host:port is inside the
    net budget - `host_refusal` of the proxy URL is None - in which case
    that one proxy is honoured. A proxy the budget does not cover is
    refused with E317, naming the proxy and the grant that would allow
    it; the refusal cannot be caught, like the other budget refusals."""
    import urllib.request

    class Guarded(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: Any) -> Any:
            why = host_refusal(newurl)
            if why is not None:
                raise _RedirectRefused(newurl, why)
            return super().redirect_request(req, fp, code, msg, headers,
                                            newurl)

    proxy = _proxy_for(url)
    if proxy is None:
        # no ambient proxy applies: disable proxies outright, so nothing
        # the environment sets can reroute the socket
        return urllib.request.build_opener(
            urllib.request.ProxyHandler({}), Guarded)
    why = host_refusal(proxy)
    if why is not None:
        import urllib.parse
        p = urllib.parse.urlsplit(proxy)
        peer = p.hostname or proxy
        port = p.port or (443 if p.scheme == "https" else 80)
        raise VelarisError("E317",
            f"an ambient proxy ({proxy}) would carry this request, and its "
            f"host {peer}:{port} is outside this run's net grants: a net "
            f"grant bounds the URL's host, and from 8.0 also the socket's "
            f"peer", 0,
            fixes=[f"grant the proxy too: --allow net:{peer}:{port}",
                   "or run with no HTTP_PROXY / HTTPS_PROXY set"])
    # the proxy peer is granted: honour exactly this one proxy
    import urllib.parse
    scheme = urllib.parse.urlsplit(url).scheme
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({scheme: proxy}), Guarded)


def _add_opener(origin: str) -> Any:
    """The opener `velaris add` fetches through (8.0). It refuses a
    redirect from https to http, and a redirect to a host outside the
    URL's origin - the two ways a vendoring fetch could be steered to
    bytes other than the ones the URL named - and, like every other
    request from 8.0, it does not defer to an ambient proxy (there is no
    net budget here to authorise a proxy peer)."""
    import urllib.parse
    import urllib.request

    def host_of(u: str) -> str:
        return (urllib.parse.urlsplit(u).hostname or "").lower().rstrip(".")

    start = urllib.parse.urlsplit(origin)

    class AddGuard(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req: Any, fp: Any, code: Any, msg: Any, headers: Any, newurl: Any) -> Any:
            new = urllib.parse.urlsplit(newurl)
            if start.scheme == "https" and new.scheme != "https":
                raise _RedirectRefused(
                    newurl, "a redirect from https to http, which would "
                    "drop the encrypted connection")
            if host_of(newurl) != host_of(origin):
                raise _RedirectRefused(
                    newurl, f"a redirect to '{host_of(newurl)}', a host "
                    f"outside the origin '{host_of(origin)}'")
            return super().redirect_request(req, fp, code, msg, headers,
                                            newurl)

    return urllib.request.build_opener(
        urllib.request.ProxyHandler({}), AddGuard)


def allow_module(module: str, what: str, line: int) -> None:
    """Refuse a Python module this run did not grant."""
    if _state.FFI_MODULES is None:
        return
    top = module.split(".")[0]
    if top in _state.FFI_MODULES:
        return
    raise VelarisError("E311",
        f"'{what}' reaches into Python module '{module}', which this run "
        f"does not allow", line,
        fixes=[f"allow it: --allow ffi:{top}"
               + ("," + ",".join(sorted(_state.FFI_MODULES)) if _state.FFI_MODULES
                  else ""),
               "or use a program that does not need it"])


# A call into Python names a module (checked by allow_module) and then a
# dotted path of attributes reached from it. Until 3.3 only the module
# name was checked, so `py("json", "codecs.encode", ...)` ran codecs code
# under `ffi:json` - the module json imports codecs into its namespace,
# and the attribute chain walked straight into it. From 3.3 every step of
# the chain is checked: an ffi:M grant is bounded to the module actually
# reached, not merely the one named. See SPEC.md §12 and THREAT_MODEL.md.

# Inert values are data, not code from any module, and are not checked:
# returning math.pi or a JSON field reaches no module's behaviour.
_FFI_INERT = (int, float, bool, str, bytes, bytearray, type(None),
              list, tuple, dict, set, frozenset)
_FFI_UNKNOWN = object()   # owning module cannot be determined -> refuse


def _ffi_owner(obj: Any) -> Any:
    """The top-level Python package that owns `obj` as code, `None` when
    `obj` is inert data, or `_FFI_UNKNOWN` when it cannot be told.

    Determining this soundly matters: the check refuses more rather than
    less, so anything whose owner cannot be placed - a bare code object,
    a frame, a reflective handle - is _FFI_UNKNOWN and is refused, not
    allowed. A builtin method carries `__module__` `None` but is bound to
    a class or module through `__self__`/`__objclass__`, which is where
    its code lives; that is consulted before the object's own type, so
    `datetime.date.today` is placed in `datetime`, not in `builtins`.
    """
    import types
    if isinstance(obj, types.ModuleType):
        name = getattr(obj, "__name__", None)
        return name.split(".")[0] if name else _FFI_UNKNOWN
    if isinstance(obj, _FFI_INERT):
        return None
    m = getattr(obj, "__module__", None)
    if isinstance(m, str) and m:
        return m.split(".")[0]
    # a builtin or bound method: the class or module it belongs to holds
    # the code, even when the method object itself reports no __module__
    for attr in ("__self__", "__objclass__"):
        holder = getattr(obj, attr, None)
        if holder is None:
            continue
        if isinstance(holder, types.ModuleType):
            n = getattr(holder, "__name__", None)
            if n:
                return n.split(".")[0]
        hm = getattr(holder, "__module__", None)
        if not (isinstance(hm, str) and hm):
            hm = getattr(type(holder), "__module__", None)
        if isinstance(hm, str) and hm:
            return hm.split(".")[0]
    # a foreign instance names its home in its type; a builtins-typed
    # object with no __module__ of its own (a code object, a frame, a
    # range) is not inert data we recognise, so it cannot be placed
    tm = getattr(type(obj), "__module__", None)
    if isinstance(tm, str) and tm and tm != "builtins":
        return tm.split(".")[0]
    return _FFI_UNKNOWN


def ffi_reach(obj: Any, what: str, line: int, described: str) -> None:
    """Refuse (E311) when `obj` - a step in the attribute chain a call
    names, an attribute read through a handle, or a non-JSON result kept
    as a handle - is code owned by a module outside this run's ffi
    grants, naming the module actually reached. Inert data is allowed;
    an owner that cannot be determined is refused."""
    if _state.FFI_MODULES is None:
        return
    owner = _ffi_owner(obj)
    if owner is None:
        return
    granted = ",".join(sorted(_state.FFI_MODULES))
    if owner is _FFI_UNKNOWN:
        raise VelarisError("E311",
            f"'{what}' reaches {described}, whose owning Python module "
            f"cannot be determined; this run allows ffi:{granted} and "
            f"refuses what it cannot place", line,
            fixes=["name the module the object comes from directly",
                   "or use a program that does not reach it this way"])
    if owner not in _state.FFI_MODULES:
        raise VelarisError("E311",
            f"'{what}' reaches into Python module '{owner}' (via "
            f"{described}), which this run does not allow", line,
            fixes=[f"allow it: --allow ffi:{owner}"
                   + ("," + granted if _state.FFI_MODULES else ""),
                   "or use a program that does not need it"])


def _ffi_resolve(module: str, func: Any, name: str, line: int) -> Any:
    """Import the module a call names (allow_module checks the name) and
    walk the attribute chain to the target it calls, checking the owning
    module of every step (ffi_reach). One place for all three py* import
    sites, so the chain is checked the same way for each."""
    import importlib
    mod, rest = None, ""
    parts = str(module).split(".")
    for cut in range(len(parts), 0, -1):      # datetime.date works:
        try:                                  # import what imports,
            allow_module(".".join(parts[:cut]), name, line)
            mod = importlib.import_module(".".join(parts[:cut]))
            rest = ".".join(parts[cut:])      # reach the rest by name
            break
        except ImportError:
            continue
    if mod is None:
        raise FailSignal(f"cannot import '{module}'")
    target = mod
    for part in ([p for p in rest.split(".") if p]
                 + [p for p in str(func).split(".") if p]):
        nxt = getattr(target, part, None)
        if nxt is None:
            raise FailSignal(f"'{module}' has no '{func}'")
        ffi_reach(nxt, name, line, f"attribute '{part}'")
        target = nxt
    return target


def spend(effect: str, what: str, line: int) -> None:
    """Refuse an effect the person running this did not allow.

    The compiler checks that a function declares what it does. This is
    the other half: the runtime refuses anything outside the budget
    given on the command line, whatever the source says about itself -
    so you can run a program you have not read.
    """
    if effect in _state.EFFECT_BUDGET:
        _state.EFFECT_USES[effect] = _state.EFFECT_USES.get(effect, 0) + 1
        return
    # Since 5.0 a run with no --allow gets io, so this is the first
    # thing many people meet after upgrading. It has to name the effect,
    # say what the run does allow, and give the flag that grants it -
    # the whole flag, with what was already granted kept.
    have = Budget.current().spec()
    wider = f"{have},{effect}" if have else effect
    raise VelarisError("E310",
        f"'{what}' needs the '{effect}' effect, which this run does not "
        f"allow (it allows: {have or 'nothing'})", line,
        fixes=[f"allow it: velaris <file> --allow {wider}",
               f"a run with no --allow gets {DEFAULT_ALLOW} (5.0); "
               f"--allow all grants every effect",
               "or use a program that does not need it"])


                           # place of a value the type system calls secret


def trace_enter(name: str, params: Any, args: Any, secret: Any = ()) -> None:
    if not _state.TRACE["on"] or _state.TRACE["calls"] >= _state.TRACE["limit"]:
        return
    _state.TRACE["calls"] += 1
    shown = ", ".join(
        f"{p}=" + (REDACTED if p in secret else to_text(a))
        for (p, _), a in zip(params, args))
    print("  " * _state.TRACE["depth"] + f"-> {name}({shown})", file=sys.stderr)
    _state.TRACE["depth"] += 1


def trace_leave(name: str, value: Any, failed: str | None = None,
                secret: bool = False) -> None:
    if not _state.TRACE["on"] or _state.TRACE["calls"] > _state.TRACE["limit"]:
        return
    _state.TRACE["depth"] = max(0, _state.TRACE["depth"] - 1)
    if failed is not None:
        print("  " * _state.TRACE["depth"] + f"<- {name} FAILED: {failed}",
              file=sys.stderr)
    elif value is None:
        print("  " * _state.TRACE["depth"] + f"<- {name}", file=sys.stderr)
    else:
        print("  " * _state.TRACE["depth"] + f"<- {name} = "
              + (REDACTED if secret else to_text(value)), file=sys.stderr)


def checked_int(value: _Num, op: str, line: int) -> _Num:
    """Whole numbers are 64-bit. Outgrowing that is an error, because
    the alternative is native code wrapping while the interpreter keeps
    counting - two engines, two answers, and no way to know which."""
    if isinstance(value, int) and not INT_MIN <= value <= INT_MAX:
        raise VelarisError("E407",
            f"this '{op}' made a number too big to hold "
            f"(whole numbers go from {INT_MIN} to {INT_MAX})", line,
            fixes=["keep the numbers smaller",
                   "or work in smaller units, like cents instead of "
                   "rupees"])
    if value.__class__ is MoneyValue and \
            not INT_MIN <= cast(MoneyValue, value).units <= INT_MAX:
        raise VelarisError("E407",
            f"this '{op}' made an amount too big to hold (an amount is "
            f"{INT_MIN} to {INT_MAX} minor units)", line,
            fixes=["an amount is held exactly, in 64 bits of minor "
                   "units; one this large is almost certainly a bug"])
    return value
