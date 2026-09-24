"""What the operating system is asked to enforce of a budget (8.4), so that a
fault in sabline itself is a crash inside a box and not an escape.
"""
import ctypes
import hashlib
import json
import os
import sys
import threading

from . import naming
from typing import Any

# ---------------------------------------------------------------------------
# 17b. CONFINEMENT - the budget, asked of the operating system as well
#
#     The budget is enforced by the interpreter, in the process that runs
#     the program. From 8.4 that process also asks the operating system to
#     hold the same budget, before the program's first statement runs:
#
#       Linux    Landlock holds the file system to the fs: grants and what
#                the interpreter itself reads; seccomp-bpf refuses sockets
#                when no net is granted, and refuses starting a process,
#                ptrace, mount and the rest of DENIED_ALWAYS
#       macOS    a sandbox profile (the language sandbox-exec reads, applied
#                with sandbox_init): writes, the network and fork/exec held;
#                reads held only under the home directory and /Volumes
#       Windows  a job object (no second process, no clipboard or desktop),
#                every privilege removed from the token, and a low integrity
#                level when the budget grants no write - files otherwise,
#                and the network always, are not held
#
#     os_policy() is the one derivation: budget -> OS policy. ENFORCES is
#     the table of what each system holds for each budget item, which
#     THREAT_MODEL.md prints and check_confine.py holds to this module.
#     FFI_WIDENS says what a granted Python module widens the policy to.
#     The level a run reports - full, partial, none - is what was applied
#     and held, never what was asked for, and comes with its reason.
# ---------------------------------------------------------------------------

POLICY_SCHEMA = "sabline.os-policy/1"
FULL, PARTIAL, NONE = "full", "partial", "none"

# layer names, as receipts and `sabline doctor` write them
LANDLOCK = "landlock"
SECCOMP = "seccomp"
MAC_SANDBOX = "sandbox-profile"
WINDOWS_JOB = "job-object"
WINDOWS_TOKEN = "token-privileges-removed"
WINDOWS_LOW = "low-integrity"

# Set for the honesty test (check_confine.py): once confinement has been
# applied - or not, under --no-confine - the runtime itself, in Python and
# not from Sabline, attempts one effect outside the budget. `read:PATH`,
# `write:PATH`, `connect:HOST:PORT`, `spawn`, `spawn-breakaway` (Windows: a
# process asked to leave the job), `signal:PID`, `mount:SOURCE:TARGET`
# (Linux: a bind mount) or `unix-socket` (a Unix-domain socket made). A program cannot set it: it is read from the
# environment the process was started with, and each of these is something
# the person who set it could do themselves.
FAULT_ENV = "SABLINE_FAULT_INJECT"

# What a granted Python module widens the OS policy to: "fs" is any path,
# "net" is any host, "all" is nothing enforced. A module that is not here
# widens to "all" - what it needs is not known, and a run that worked under
# 8.3.1 must not be refused - and the audit says so.
FFI_WIDENS: dict[str, tuple[str, ...]] = {
    **{m: () for m in (
        "abc", "array", "ast", "base64", "binascii", "bisect", "calendar",
        "cmath", "collections", "colorsys", "copy", "csv", "dataclasses",
        "datetime", "decimal", "difflib", "email", "enum", "fnmatch",
        "fractions", "functools", "gc", "hashlib", "heapq", "hmac", "html",
        "ipaddress", "itertools", "json", "keyword", "math", "numbers",
        "operator", "pprint", "random", "re", "reprlib", "secrets", "shlex",
        "statistics", "string", "struct", "textwrap", "threading", "time",
        "tomllib", "typing", "unicodedata", "uuid", "zlib", "zoneinfo")},
    **{m: ("fs",) for m in (
        "bz2", "codecs", "configparser", "dbm", "fileinput", "glob", "gzip",
        "io", "lzma", "pathlib", "shutil", "sqlite3", "tarfile", "tempfile",
        "xml", "zipfile")},
    **{m: ("net",) for m in (
        "ftplib", "http", "imaplib", "poplib", "select", "selectors",
        "smtplib", "socket", "ssl", "urllib", "xmlrpc")},
    **{m: ("fs", "net") for m in (
        "aiohttp", "httpx", "logging", "requests", "urllib3")},
    **{m: ("all",) for m in (
        "asyncio", "builtins", "code", "concurrent", "ctypes", "importlib",
        "multiprocessing", "nt", "os", "pdb", "pickle", "pkgutil",
        "platform", "posix", "pty", "runpy", "shelve", "signal", "site",
        "subprocess", "sys", "venv", "webbrowser", "winreg", "zipimport")},
}

# Every budget item, and what each system enforces for it. THREAT_MODEL.md
# prints these rows; check_confine.py fails when the two differ.
ENFORCES: tuple[tuple[str, str, str, str], ...] = (
    ("no `fs` granted",
     "Landlock: no file read, written, made or removed but what the "
     "interpreter itself needs (below)",
     "writes refused everywhere but the private temporary directory; reads "
     "refused under the home directory and /Volumes, but for the names in "
     "the working directory and in each directory above it, which getcwd "
     "reads",
     "low integrity level: no write to anything of the user's; reads not "
     "held"),
    ("`fs:read:DIR`",
     "Landlock: reads beneath DIR (resolved), and nothing else of the "
     "user's; when DIR does not exist yet - a file the program writes and "
     "reads back - beneath the nearest directory that does, and the level "
     "is partial",
     "reads beneath DIR allowed; outside it, refused only under the home "
     "directory and /Volumes",
     "not held: the low integrity level does not stop a read"),
    ("`fs:write:DIR`",
     "Landlock: files written, made and truncated beneath DIR; when DIR "
     "does not exist yet, beneath the nearest directory that does, and the "
     "level is partial",
     "writes beneath DIR, as Linux",
     "not held: a write grant keeps the process at medium integrity, "
     "because lowering it would need the granted directory relabelled"),
    ("`fs`, `fs:read`, `fs:write` with no path",
     "that direction is not restricted, as the budget says",
     "as Linux", "as Linux"),
    ("a credential location under a broad grant (E318)",
     "not held: Landlock cannot take a path out of a hierarchy it allows",
     "not held", "not held"),
    ("no `net` granted",
     "seccomp: socket, socketpair, connect, bind, listen and accept refused "
     "(EPERM); Landlock ABI 4 and later also refuses TCP",
     "`(deny network*)`",
     "not held: it needs an AppContainer, which this Python cannot start "
     "in (below)"),
    ("`net:HOST`, `net:HOST:PORT`",
     "IPv4, IPv6 and netlink sockets allowed, and no Unix socket; with "
     "Landlock ABI 4 and later, and a port on every grant, TCP connections "
     "to those ports and 53 only. The host is held by the language alone, "
     "so the level is partial",
     "the network allowed; the host is held by the language alone "
     "(partial)",
     "not held"),
    ("`net` with no host",
     "any host, as the budget says; still no Unix socket, unless a granted "
     "Python module widened the policy to any host",
     "not restricted, as the budget says", "as macOS"),
    ("`@N` counts", "the language", "the language", "the language"),
    ("`io`", "the descriptors the process was started with; not restricted",
     "as Linux", "as Linux"),
    ("`env`",
     "not held: the environment is in the process's own memory",
     "not held", "not held"),
    ("`clock`, `rand`, `declassify`",
     "not held: reading the clock or the kernel's randomness reaches "
     "nothing outside the process, and declassify is a rule of the type "
     "system", "not held", "not held"),
    ("`tool`",
     "not held: a tool call is a line written to the standard output the "
     "process was started with and an answer read from its standard input; "
     "what the tool then does happens in the host's process, which this "
     "policy does not reach", "not held", "not held"),
    ("starting a process (never a budget item)",
     "seccomp: execve, execveat, fork, vfork, clone without CLONE_THREAD "
     "refused, clone3 answered ENOSYS; Landlock refuses execute",
     "`(deny process-fork)` `(deny process-exec)`",
     "job object: one active process; and the clipboard, the desktop, "
     "global atoms and other processes' USER handles"),
    ("the rest of the deny-list (never a budget item)",
     "seccomp: ptrace, mount and its new calls, pivot_root, chroot, "
     "unshare, setns, kernel modules, kexec, bpf, perf_event_open, "
     "process_vm_readv and writev, keyrings, io_uring, userfaultfd, "
     "open_by_handle_at, setting the clock, reboot, swapon, acct, quotactl, "
     "personality; a signal, by kill, tgkill or sigqueue, to any process "
     "but this one; input pushed at the terminal (TIOCSTI, TIOCLINUX)",
     "what `(deny process-fork)` and the denial of writes imply; no list "
     "of system calls",
     "every privilege but SeChangeNotifyPrivilege removed from the token"),
    ("`ffi:MODULE`",
     "widened to what FFI_WIDENS names for MODULE: nothing, any path, any "
     "host, or nothing enforced; a module not in the table, `ffi:os`, "
     "`ffi:subprocess` and plain `ffi` widen to nothing enforced, and the "
     "level is none", "as Linux", "as Linux"),
    ("time and memory limits",
     "RLIMIT_AS, and the parent's clock (as before 8.4)",
     "the parent's clock; RLIMIT_AS is best-effort",
     "the job object's memory limit, and the parent's clock"),
)

# What is exempt from confinement, and why.
EXEMPT: tuple[tuple[str, str], ...] = (
    ("`sabline.run()` with no `timeout` and no `max_memory_mb`",
     "it runs in the caller's process, which Sabline must not confine: "
     "Landlock, seccomp, a sandbox profile and a lowered token cannot be "
     "taken off again. Pass a limit, or use a Pool."),
    ("the REPL, `sabline test`, `sabline bench`",
     "they run many programs in one process, each read after the last; a "
     "policy applied for the first would hold the rest"),
    ("a `Pool` made without `import_root`, on reads",
     "its workers compile each program they are sent, and an import may "
     "name any .vel file the process can read, so reads are not held and "
     "the level is partial; writes, the network and processes are held"),
    ("compiling, proving and native code generation",
     "done before the policy is applied in a single run, since imports "
     "are read from wherever they are and Z3 and LLVM load their "
     "libraries; the program's first statement runs after it"),
)


class ConfinementRefused(OSError):
    """The operating system's confinement refused what the runtime itself
    attempted (the fault-injection hook)."""


# ---- budget -> OS policy: the one derivation ---------------------------------

def os_policy(budget: Any, *, confine: bool = True) -> dict[str, Any]:
    """The OS policy of a budget: what the operating system is asked to hold
    for a run under it. Pure - it reads nothing of the machine - so the same
    budget gives the same policy, and policy_sha256() of it is what a
    receipt records.

      fs_read, fs_write   the resolved paths that direction may touch, or
                          None for any path; [] for none of the user's
      net                 "none", "any", or {"hosts": [[host, port], ...]}
      spawn               False: no process is started, whatever the budget
      widened_by          the granted ffi modules that widened it, and to what
      enforced            False when nothing is asked of the system:
                          --no-confine, or a module that widens to "all"
    """
    fs_read: list[str] | None = []
    fs_write: list[str] | None = []
    if "fs" in budget.effects:
        if budget.fs is None:
            fs_read = fs_write = None
        else:
            for kind, prefix in budget.fs:
                if kind == "read":
                    fs_read = None if prefix is None or fs_read is None \
                        else fs_read + [prefix]
                else:
                    fs_write = None if prefix is None or fs_write is None \
                        else fs_write + [prefix]
    net: Any = "none"
    if "net" in budget.effects:
        net = "any" if budget.net is None else {
            "hosts": sorted(([h, p] for h, p in budget.net),
                            key=lambda hp: (str(hp[0]), hp[1] or 0))}
    spawn = False
    enforced = bool(confine)
    widened = []
    if "ffi" in budget.effects:
        modules = ["*"] if budget.modules is None else sorted(budget.modules)
        for module in modules:
            widens = FFI_WIDENS.get(module, ("all",))
            if module not in FFI_WIDENS:
                widened.append({"module": module, "widens": ["all"],
                                "known": False})
            elif widens:
                widened.append({"module": module, "widens": list(widens),
                                "known": True})
            if "fs" in widens:
                fs_read = fs_write = None
            if "net" in widens:
                net = "any"
            if "all" in widens:
                fs_read = fs_write = None
                net, spawn, enforced = "any", True, False
    return {"schema": POLICY_SCHEMA, "enforced": enforced,
            "fs_read": None if fs_read is None else sorted(set(fs_read)),
            "fs_write": None if fs_write is None else sorted(set(fs_write)),
            "net": net, "spawn": spawn, "widened_by": widened,
            "system": ["interpreter", "standard-library", "program",
                       "private-temp"] + (
                           ["dns", "tls-roots"] if net != "none" else [])}


def policy_sha256(policy: dict[str, Any]) -> str:
    """The digest a receipt records: sha256 of the policy as canonical JSON."""
    text = json.dumps(policy, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def _restricted(policy: dict[str, Any]) -> list[str]:
    """The things this policy asks the system to hold."""
    if not policy["enforced"]:
        return []
    asks = []
    if policy["fs_read"] is not None:
        asks.append("fs_read")
    if policy["fs_write"] is not None:
        asks.append("fs_write")
    if policy["net"] != "any":
        asks.append("net")
    if not policy["spawn"]:
        asks.append("spawn")
    return asks


def not_in_table(budget: Any) -> list[str]:
    """The ffi modules a budget names that FFI_WIDENS does not: each widens
    the OS policy to nothing enforced. A name that is no module at all is
    among them - nothing here imports it to find out. Plain `ffi` names
    none, and is not here."""
    if "ffi" not in budget.effects or budget.modules is None:
        return []
    return sorted(m for m in budget.modules if m not in FFI_WIDENS)


def not_in_table_warning(modules: list[str]) -> str:
    """The one line the command line writes to stderr for them (8.7)."""
    names = ", ".join(f"ffi:{m}" for m in modules)
    return (f"sabline: {names} {'is' if len(modules) == 1 else 'are'} not in "
            f"the confinement table, so the operating system layer is off "
            f"for this run: the budget is the only boundary")


def _why_not_enforced(policy: dict[str, Any]) -> str:
    names = [("plain ffi" if w["module"] == "*" else "ffi:" + w["module"])
             + ("" if w.get("known", True) else " (not in the table of "
                "modules, so what it needs is not known)")
             for w in policy["widened_by"] if "all" in w["widens"]]
    if not names:
        return "--no-confine: the budget is the only boundary"
    return (", ".join(names) + " widens the OS policy to nothing enforced: "
            "a granted module that can start a process or load code is "
            "the operating system as this user")


def report(level: str, reason: str, layers: list[str],
           policy: dict[str, Any]) -> dict[str, Any]:
    return {"level": level, "reason": reason, "layers": layers,
            "policy_sha256": policy_sha256(policy),
            "platform": _platform()}


def _platform() -> str:
    if sys.platform.startswith("linux"):
        return "linux"
    return {"darwin": "macos", "win32": "windows"}.get(sys.platform,
                                                       sys.platform)


def _judge(policy: dict[str, Any], held: dict[str, str],
           layers: list[str], notes: list[str]) -> dict[str, Any]:
    """The level: `held` says, for each thing the policy restricts, 'yes',
    'partly: why' or 'no: why'."""
    asks = _restricted(policy)
    if not policy["enforced"]:
        return report(NONE, _why_not_enforced(policy), [], policy)
    said = {what: held.get(what, "no: not held") for what in asks}
    gaps = [f"{what}: {answer.partition(':')[2].strip()}"
            for what, answer in said.items() if answer != "yes"] + notes
    if not any(answer == "yes" or answer.startswith("partly")
               for answer in said.values()):
        return report(NONE, "; ".join(gaps) or "nothing was applied", layers,
                      policy)
    if gaps:
        return report(PARTIAL, "; ".join(gaps), layers, policy)
    return report(FULL, "the operating system holds every file, network "
                  "and process limit of this budget", layers, policy)


# ---- where the interpreter itself reads ---------------------------------------

def _existing(paths: Any) -> list[str]:
    seen, out = set(), []
    for p in paths:
        if not p:
            continue
        real = os.path.realpath(str(p))
        if real not in seen and os.path.exists(real):
            seen.add(real)
            out.append(real)
    return out


def interpreter_reads(net: bool) -> list[str]:
    """What this process must be able to read to keep running: Python's own
    install and every directory it imports from, this package and the
    standard library beside it, shared libraries, the devices and /proc
    entries Python asks for, the time zone data - and, under a net grant,
    the resolver's configuration and the TLS roots."""
    here = os.path.dirname(os.path.abspath(__file__))
    places = [sys.prefix, sys.base_prefix, sys.exec_prefix,
              getattr(sys, "base_exec_prefix", None),
              getattr(sys, "_MEIPASS", None), here,
              os.path.join(os.path.dirname(here), "stdlib"),
              os.path.dirname(os.path.realpath(sys.executable))]
    places += [p for p in sys.path if p]
    if sys.platform.startswith("linux"):
        places += ["/lib", "/lib64", "/usr/lib", "/usr/lib64", "/usr/local/lib",
                   "/etc/ld.so.cache", "/etc/ld.so.conf", "/etc/ld.so.conf.d",
                   "/etc/localtime", "/usr/share/zoneinfo", "/etc/timezone",
                   "/usr/share/locale", "/usr/lib/locale",
                   "/dev/null", "/dev/zero", "/dev/urandom", "/dev/random",
                   "/proc/self", "/proc/cpuinfo", "/proc/meminfo",
                   "/proc/sys/kernel", "/proc/sys/vm",
                   "/sys/devices/system/cpu", "/sys/fs/cgroup"]
        if net:
            places += ["/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf",
                       "/etc/gai.conf", "/etc/host.conf", "/etc/services",
                       "/etc/protocols", "/etc/ssl", "/etc/pki",
                       "/etc/ca-certificates", "/usr/share/ca-certificates",
                       "/usr/lib/ssl", "/run/systemd/resolve",
                       "/run/resolvconf", "/mnt/wsl/resolv.conf",
                       "/var/run/nscd"]
    return _existing(places)


def _nearest_directory(path: str) -> tuple[str | None, bool]:
    """(the path when it exists, else the nearest directory above it that
    does; whether that is wider than the path): a write grant may name a
    file or a directory not made yet."""
    p = os.path.realpath(path)
    if os.path.exists(p):
        return p, False
    while True:
        parent = os.path.dirname(p)
        if parent == p:
            return None, True
        p = parent
        if os.path.isdir(p):
            return p, True


# ---- Linux: Landlock ------------------------------------------------------------

_SYS_CREATE_RULESET, _SYS_ADD_RULE, _SYS_RESTRICT_SELF = 444, 445, 446
_CREATE_RULESET_VERSION = 1
_RULE_PATH_BENEATH, _RULE_NET_PORT = 1, 2
_PR_SET_NO_NEW_PRIVS = 38
_FS_EXECUTE = 1 << 0
_FS_WRITE_FILE = 1 << 1
_FS_READ_FILE = 1 << 2
_FS_READ_DIR = 1 << 3
_FS_REMOVE_DIR = 1 << 4
_FS_REMOVE_FILE = 1 << 5
_FS_MAKE_DIR = 1 << 7
_FS_MAKE_REG = 1 << 8
_FS_MAKE_ALL = sum(1 << b for b in range(6, 13))   # char, dir, reg, sock,
                                                   # fifo, block, sym
_FS_REFER = 1 << 13                                # ABI 2
_FS_TRUNCATE = 1 << 14                             # ABI 3
_NET_BIND_TCP = 1 << 0                             # ABI 4
_NET_CONNECT_TCP = 1 << 1
_SCOPE_ABSTRACT_UNIX = 1 << 0                      # ABI 6
_SCOPE_SIGNAL = 1 << 1


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64),
                ("scoped", ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64),
                ("parent_fd", ctypes.c_int32)]


class _NetPort(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64),
                ("port", ctypes.c_uint64)]


def _libc() -> Any:
    libc = ctypes.CDLL(None, use_errno=True)
    libc.syscall.restype = ctypes.c_long
    return libc


def landlock_abi() -> int:
    """The Landlock ABI this kernel offers, or 0 for none."""
    if not sys.platform.startswith("linux"):
        return 0
    try:
        abi = _libc().syscall(ctypes.c_long(_SYS_CREATE_RULESET), None,
                              ctypes.c_size_t(0),
                              ctypes.c_uint32(_CREATE_RULESET_VERSION))
    except (OSError, AttributeError):
        return 0
    return int(abi) if abi > 0 else 0


def _tcp_ports(policy: dict[str, Any]) -> list[int] | None:
    """The TCP ports a net policy allows, when every grant names one; else
    None, and TCP is not held by port."""
    net = policy["net"]
    if not isinstance(net, dict):
        return None
    ports = [p for _h, p in net["hosts"]]
    if any(p is None for p in ports):
        return None
    return sorted({int(p) for p in ports} | {53})


def _landlock_plan(policy: dict[str, Any], abi: int, reads: list[str],
                   writes: list[str], temp: str | None,
                   read_any: bool) -> dict[str, Any]:
    """What a Landlock ruleset for this policy handles and allows."""
    write_all = (_FS_WRITE_FILE | _FS_REMOVE_DIR | _FS_REMOVE_FILE
                 | _FS_MAKE_ALL | (_FS_REFER if abi >= 2 else 0)
                 | (_FS_TRUNCATE if abi >= 3 else 0))
    write_grant = (_FS_WRITE_FILE | _FS_MAKE_REG
                   | (_FS_TRUNCATE if abi >= 3 else 0))
    read_all = _FS_READ_FILE | _FS_READ_DIR
    handled = 0 if policy["spawn"] else _FS_EXECUTE
    rules: list[tuple[str, int]] = []
    wider: list[str] = []
    wider_reads: list[str] = []
    hold_reads = policy["fs_read"] is not None and not read_any
    if hold_reads:
        handled |= read_all
        for place in interpreter_reads(policy["net"] != "none") + _existing(
                reads):
            rules.append((place, read_all))
        for grant in policy["fs_read"]:
            # a program may read back what it has just written: a granted
            # path that is not there yet is held to the nearest directory
            # that is, as a write grant is, and the level says so
            nearest, widened = _nearest_directory(grant)
            if nearest is None:
                continue
            if widened:
                wider_reads.append(f"{grant} does not exist yet, so reads "
                                   f"are held to {nearest}")
            rules.append((nearest, read_all))
    if policy["fs_write"] is not None:
        handled |= write_all
        for grant in policy["fs_write"]:
            nearest, widened = _nearest_directory(grant)
            if nearest is None:
                continue
            if widened:
                wider.append(f"{grant} does not exist yet, so writes are "
                             f"held to {nearest}")
            rules.append((nearest, write_grant))
        for place in _existing(writes):
            rules.append((place, write_grant))
        if os.path.exists("/dev/null"):
            rules.append(("/dev/null", _FS_WRITE_FILE))
    if temp:
        rules.append((temp, write_all | read_all))
    ports = _tcp_ports(policy)
    net_handled, net_rules = 0, []
    if abi >= 4 and policy["net"] == "none":
        net_handled = _NET_BIND_TCP | _NET_CONNECT_TCP
    elif abi >= 4 and ports is not None:
        net_handled = _NET_BIND_TCP | _NET_CONNECT_TCP
        net_rules = ports
    return {"handled": handled, "rules": rules, "wider": wider,
            "wider_reads": wider_reads, "hold_reads": hold_reads, "net_handled": net_handled,
            "net_rules": net_rules,
            # Landlock ABI 6's scopes (abstract Unix sockets, signals) are
            # not asked for: the seccomp filter already refuses both, and
            # kernels before 6.15 refuse a signal between two threads of one
            # process that restricted themselves separately, as the main
            # thread and a run's thread do on Python 3.10
            "scoped": 0}


def _landlock_restrict(plan: dict[str, Any], abi: int) -> str | None:
    """Build the ruleset and hold THIS THREAD (and the threads it starts
    after) with it. None, or why it failed - and then nothing was applied."""
    libc = _libc()
    attr = _RulesetAttr(plan["handled"], plan["net_handled"], plan["scoped"])
    size = 8 if abi < 4 else 16
    fd = libc.syscall(ctypes.c_long(_SYS_CREATE_RULESET), ctypes.byref(attr),
                      ctypes.c_size_t(size), ctypes.c_uint32(0))
    if fd < 0:
        return f"landlock_create_ruleset: errno {ctypes.get_errno()}"
    try:
        for place, access in plan["rules"]:
            try:
                parent = os.open(place, getattr(os, "O_PATH", 0) | os.O_CLOEXEC)
            except OSError:
                continue                  # gone, or not ours to open
            try:
                if not os.path.isdir(place):   # a file takes file rights only
                    access &= (_FS_EXECUTE | _FS_WRITE_FILE | _FS_READ_FILE
                               | _FS_TRUNCATE)
                access &= plan["handled"]
                if not access:
                    continue
                rule = _PathBeneath(access, parent)
                if libc.syscall(ctypes.c_long(_SYS_ADD_RULE), ctypes.c_int(fd),
                                ctypes.c_int(_RULE_PATH_BENEATH),
                                ctypes.byref(rule), ctypes.c_uint32(0)) != 0:
                    return f"landlock_add_rule({place}): errno " \
                           f"{ctypes.get_errno()}"
            finally:
                os.close(parent)
        for port in plan["net_rules"]:
            net_rule = _NetPort(_NET_CONNECT_TCP, port)
            if libc.syscall(ctypes.c_long(_SYS_ADD_RULE), ctypes.c_int(fd),
                            ctypes.c_int(_RULE_NET_PORT),
                            ctypes.byref(net_rule), ctypes.c_uint32(0)) != 0:
                return f"landlock_add_rule(port {port}): errno " \
                       f"{ctypes.get_errno()}"
        if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            return f"PR_SET_NO_NEW_PRIVS: errno {ctypes.get_errno()}"
        if libc.syscall(ctypes.c_long(_SYS_RESTRICT_SELF), ctypes.c_int(fd),
                        ctypes.c_uint32(0)) != 0:
            return f"landlock_restrict_self: errno {ctypes.get_errno()}"
    finally:
        os.close(fd)
    return None


# ---- Linux: seccomp-bpf ---------------------------------------------------------

_AUDIT_ARCH = {"x86_64": 0xC000003E, "aarch64": 0xC00000B7}
_SYS_SECCOMP = {"x86_64": 317, "aarch64": 277}
_SECCOMP_SET_MODE_FILTER, _SECCOMP_FILTER_FLAG_TSYNC = 1, 1
_RET_KILL_PROCESS, _RET_ALLOW = 0x80000000, 0x7FFF0000
_RET_ERRNO = 0x00050000
_EPERM, _ENOSYS = 1, 38
_CLONE_THREAD = 0x00010000
_X32_BIT = 0x40000000
_AF_INET, _AF_INET6, _AF_NETLINK = 2, 10, 16
_TIOCSTI, _TIOCLINUX = 0x5412, 0x541C

_SYSCALLS: dict[str, dict[str, int]] = {
    "x86_64": {
        "socket": 41, "connect": 42, "accept": 43, "bind": 49, "listen": 50,
        "socketpair": 53, "accept4": 288,
        "clone": 56, "fork": 57, "vfork": 58, "execve": 59, "execveat": 322,
        "clone3": 435,
        "kill": 62, "tkill": 200, "tgkill": 234, "pidfd_send_signal": 424,
        "rt_sigqueueinfo": 129, "rt_tgsigqueueinfo": 297, "ioctl": 16,
        "ptrace": 101, "personality": 135, "pivot_root": 155, "adjtimex": 159,
        "chroot": 161, "acct": 163, "settimeofday": 164, "mount": 165,
        "umount2": 166, "swapon": 167, "swapoff": 168, "reboot": 169,
        "init_module": 175, "delete_module": 176, "quotactl": 179,
        "clock_settime": 227, "kexec_load": 246, "add_key": 248,
        "request_key": 249, "keyctl": 250, "unshare": 272,
        "perf_event_open": 298, "name_to_handle_at": 303,
        "open_by_handle_at": 304, "clock_adjtime": 305, "setns": 308,
        "process_vm_readv": 310, "process_vm_writev": 311,
        "finit_module": 313, "kexec_file_load": 320, "bpf": 321,
        "userfaultfd": 323, "io_uring_setup": 425, "io_uring_enter": 426,
        "io_uring_register": 427, "open_tree": 428, "move_mount": 429,
        "fsopen": 430, "fsconfig": 431, "fsmount": 432, "fspick": 433,
        "pidfd_getfd": 438, "process_madvise": 440, "mount_setattr": 442},
    "aarch64": {
        "socket": 198, "socketpair": 199, "bind": 200, "listen": 201,
        "accept": 202, "connect": 203, "accept4": 242,
        "clone": 220, "execve": 221, "execveat": 281, "clone3": 435,
        "kill": 129, "tkill": 130, "tgkill": 131, "pidfd_send_signal": 424,
        "rt_sigqueueinfo": 138, "rt_tgsigqueueinfo": 240, "ioctl": 29,
        "umount2": 39, "mount": 40, "pivot_root": 41, "chroot": 51,
        "quotactl": 60, "acct": 89, "personality": 92, "unshare": 97,
        "kexec_load": 104, "init_module": 105, "delete_module": 106,
        "clock_settime": 112, "ptrace": 117, "reboot": 142,
        "settimeofday": 170, "adjtimex": 171, "add_key": 217,
        "request_key": 218, "keyctl": 219, "swapon": 224, "swapoff": 225,
        "perf_event_open": 241, "name_to_handle_at": 264,
        "open_by_handle_at": 265, "clock_adjtime": 266, "setns": 268,
        "process_vm_readv": 270, "process_vm_writev": 271,
        "finit_module": 273, "bpf": 280, "userfaultfd": 282,
        "kexec_file_load": 294, "io_uring_setup": 425, "io_uring_enter": 426,
        "io_uring_register": 427, "open_tree": 428, "move_mount": 429,
        "fsopen": 430, "fsconfig": 431, "fsmount": 432, "fspick": 433,
        "pidfd_getfd": 438, "process_madvise": 440, "mount_setattr": 442},
}

DENIED_WITHOUT_NET = ("socket", "socketpair", "connect", "bind", "listen",
                      "accept", "accept4")
DENIED_WITHOUT_SPAWN = ("execve", "execveat", "fork", "vfork")
DENIED_ALWAYS = (
    "ptrace", "personality", "pivot_root", "adjtimex", "chroot", "acct",
    "settimeofday", "mount", "umount2", "swapon", "swapoff", "reboot",
    "init_module", "delete_module", "quotactl", "clock_settime", "kexec_load",
    "add_key", "request_key", "keyctl", "unshare", "perf_event_open",
    "name_to_handle_at", "open_by_handle_at", "clock_adjtime", "setns",
    "process_vm_readv", "process_vm_writev", "finit_module",
    "kexec_file_load", "bpf", "userfaultfd", "io_uring_setup",
    "io_uring_enter", "io_uring_register", "open_tree", "move_mount",
    "fsopen", "fsconfig", "fsmount", "fspick", "pidfd_getfd",
    "process_madvise", "mount_setattr", "tkill", "pidfd_send_signal")


class _SockFilter(ctypes.Structure):
    _fields_ = [("code", ctypes.c_uint16), ("jt", ctypes.c_uint8),
                ("jf", ctypes.c_uint8), ("k", ctypes.c_uint32)]


class _SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_uint16),
                ("filter", ctypes.POINTER(_SockFilter))]


def seccomp_arch() -> str | None:
    """The machine name seccomp's tables know this process as, or None."""
    import platform
    if not sys.platform.startswith("linux") or sys.byteorder != "little" \
            or ctypes.sizeof(ctypes.c_void_p) != 8:
        return None
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    return machine if machine in _SYSCALLS else None


def seccomp_program(policy: dict[str, Any], arch: str,
                    pid: int) -> list[tuple[int, int, int, int]]:
    """The BPF program for a policy: each instruction (code, jt, jf, k).
    Anything it does not name is allowed; what it names answers EPERM, so
    Python raises PermissionError and the run can say which layer refused."""
    LD, JEQ, JGE, JSET, RET = 0x20, 0x15, 0x35, 0x45, 0x06
    NR, ARCH, ARG0_LO, ARG0_HI, ARG1_LO = 0, 4, 16, 20, 24
    numbers = _SYSCALLS[arch]
    eperm, enosys = _RET_ERRNO | _EPERM, _RET_ERRNO | _ENOSYS
    prog: list[tuple[int, int, int, int]] = [
        (LD, 0, 0, ARCH), (JEQ, 1, 0, _AUDIT_ARCH[arch]),
        (RET, 0, 0, _RET_KILL_PROCESS), (LD, 0, 0, NR)]
    if arch == "x86_64":                    # the x32 numbers name other calls
        prog += [(JGE, 0, 1, _X32_BIT), (RET, 0, 0, enosys)]
    denied = list(DENIED_ALWAYS)
    if policy["net"] == "none":
        denied += DENIED_WITHOUT_NET
    if not policy["spawn"]:
        denied += DENIED_WITHOUT_SPAWN
    for name in denied:
        if name in numbers:
            prog += [(JEQ, 0, 1, numbers[name]), (RET, 0, 0, eperm)]
    if not policy["spawn"]:
        # a thread is a clone with CLONE_THREAD; a process is one without.
        # clone3 hides its flags behind a pointer a filter cannot read, so
        # it is answered "no such call" and libc falls back to clone.
        prog += [(JEQ, 0, 1, numbers["clone3"]), (RET, 0, 0, enosys),
                 (JEQ, 0, 4, numbers["clone"]), (LD, 0, 0, ARG0_LO),
                 (JSET, 1, 0, _CLONE_THREAD), (RET, 0, 0, eperm),
                 (RET, 0, 0, _RET_ALLOW)]
    if policy["net"] != "none" and not any(
            "net" in w["widens"] for w in policy["widened_by"]):
        # a net grant is for the internet: IPv4, IPv6, and the netlink
        # socket the resolver asks about addresses. Not a Unix socket, which
        # is how a process reaches the container runtime or the session bus
        # and which Landlock does not hold. A granted Python module that
        # widens the policy to any host keeps every family: it may need one.
        prog += [(JEQ, 0, 6, numbers["socket"]), (LD, 0, 0, ARG0_LO),
                 (JEQ, 2, 0, _AF_INET), (JEQ, 1, 0, _AF_INET6),
                 (JEQ, 0, 1, _AF_NETLINK), (RET, 0, 0, _RET_ALLOW),
                 (RET, 0, 0, eperm),
                 (JEQ, 0, 1, numbers["socketpair"]), (RET, 0, 0, eperm)]
    # input pushed into the controlling terminal is typed at the shell that
    # started this process once it ends: TIOCSTI, and TIOCLINUX's paste
    prog += [(JEQ, 0, 5, numbers["ioctl"]), (LD, 0, 0, ARG1_LO),
             (JEQ, 1, 0, _TIOCSTI), (JEQ, 0, 1, _TIOCLINUX),
             (RET, 0, 0, eperm), (LD, 0, 0, NR)]
    # a signal to this process only: abort() and raise() are tgkill(own pid)
    for name in ("kill", "tgkill", "rt_sigqueueinfo", "rt_tgsigqueueinfo"):
        prog += [(JEQ, 0, 6, numbers[name]), (LD, 0, 0, ARG0_HI),
                 (JEQ, 0, 3, 0), (LD, 0, 0, ARG0_LO), (JEQ, 0, 1, pid),
                 (RET, 0, 0, _RET_ALLOW), (RET, 0, 0, eperm),
                 (LD, 0, 0, NR)]
    prog.append((RET, 0, 0, _RET_ALLOW))
    return prog


def _seccomp_apply(policy: dict[str, Any]) -> str | None:
    """Install the filter on every thread of this process (TSYNC). None, or
    why it failed."""
    arch = seccomp_arch()
    if arch is None:
        return "seccomp: no system call table for this machine"
    prog = seccomp_program(policy, arch, os.getpid())
    array = (_SockFilter * len(prog))(*[_SockFilter(*i) for i in prog])
    fprog = _SockFprog(len(prog), array)
    libc = _libc()
    if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        return f"PR_SET_NO_NEW_PRIVS: errno {ctypes.get_errno()}"
    if libc.syscall(ctypes.c_long(_SYS_SECCOMP[arch]),
                    ctypes.c_uint(_SECCOMP_SET_MODE_FILTER),
                    ctypes.c_uint(_SECCOMP_FILTER_FLAG_TSYNC),
                    ctypes.byref(fprog)) != 0:
        return f"seccomp(SET_MODE_FILTER): errno {ctypes.get_errno()}"
    return None


def _thread_count() -> int:
    try:
        return len(os.listdir("/proc/self/task"))
    except OSError:
        return len(threading.enumerate())


def _apply_linux(policy: dict[str, Any], reads: list[str], writes: list[str],
                 temp: str | None, read_any: bool) -> dict[str, Any]:
    held: dict[str, str] = {}
    layers: list[str] = []
    notes: list[str] = []
    abi = landlock_abi()
    # everything this needs is imported and opened before anything is held
    plan = _landlock_plan(policy, abi, reads, writes, temp, read_any) \
        if abi else None
    failed = None
    if plan is not None:
        failed = _landlock_restrict(plan, abi)
        covered = 1
        if failed is None and threading.current_thread() \
                is not threading.main_thread():
            # Landlock holds the calling thread and the threads it starts;
            # on Python 3.10 a run is on a thread of its own, so the main
            # thread, waiting for it, is held by a call of its own
            from .runtime import call_on_main_thread
            answered, other = call_on_main_thread(
                lambda: _landlock_restrict(plan, abi))
            if answered and other is None:
                covered += 1
        if failed is None:
            layers.append(f"{LANDLOCK}-abi{abi}")
            # a thread that has ended stays listed until the kernel has
            # reaped it, so one on its way out is given a moment to go
            # before it is counted as a thread Landlock does not hold
            import time
            waited = 0
            while _thread_count() > covered and waited < 40:
                time.sleep(0.005)
                waited += 1
            unheld = _thread_count() - covered
            if unheld > 0:
                notes.append(f"{unheld} thread(s) started before confinement "
                             f"are not held by Landlock")
    if abi and failed is None and plan is not None:
        if policy["fs_read"] is not None:
            held["fs_read"] = "yes" if plan["hold_reads"] else \
                ("no: this pool has no import_root, and an import may name "
                 "any .vel file, so reads are not held")
            if plan["wider_reads"]:
                held["fs_read"] = "partly: " + "; ".join(plan["wider_reads"])
        if policy["fs_write"] is not None:
            held["fs_write"] = "yes"
            if abi < 3:
                held["fs_write"] = ("partly: Landlock ABI %d cannot hold "
                                    "truncation" % abi)
            if plan["wider"]:
                held["fs_write"] = "partly: " + "; ".join(plan["wider"])
    else:
        why = failed or "this kernel has no Landlock"
        for what in ("fs_read", "fs_write"):
            held[what] = f"no: {why}"
    failed = _seccomp_apply(policy)
    if failed is None:
        layers.append(SECCOMP)
        if not policy["spawn"]:
            held["spawn"] = "yes"
        if policy["net"] == "none":
            held["net"] = "yes"
    else:
        if not policy["spawn"]:
            held["spawn"] = ("partly: Landlock refuses execute, and " + failed
                             if abi and plan is not None else f"no: {failed}")
        if policy["net"] == "none":
            held["net"] = ("partly: Landlock refuses TCP only, and " + failed
                           if plan is not None and plan["net_handled"]
                           else f"no: {failed}")
    if isinstance(policy["net"], dict):
        ports = _tcp_ports(policy)
        held["net"] = (
            "partly: the kernel holds TCP to the granted ports "
            f"({', '.join(str(p) for p in ports or [])}); the host is held "
            "by the language alone"
            if plan is not None and plan["net_rules"] else
            "no: the kernel cannot hold a host; it is held by the language "
            "alone")
    return _judge(policy, held, layers, notes)


# ---- macOS: a sandbox profile ----------------------------------------------------

SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def _sbpl_text(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def mac_profile(policy: dict[str, Any], reads: list[str], writes: list[str],
                temp: str | None, read_any: bool = False) -> str:
    """The sandbox profile of a policy, in the language sandbox-exec reads.
    The later of two rules that match wins, so each denial follows `allow
    default` and what is allowed again follows its denial."""
    lines = ["(version 1)", "(allow default)"]
    if policy["net"] == "none":
        lines.append("(deny network*)")
    if not policy["spawn"]:
        lines += ["(deny process-fork)", "(deny process-exec)"]
    if policy["fs_write"] is not None:
        places = ['(literal "/dev/null")', '(literal "/dev/dtracehelper")']
        for grant in list(policy["fs_write"]) + writes + ([temp] if temp
                                                          else []):
            place, _wider = _nearest_directory(grant)
            if place:
                places.append(f"(subpath {_sbpl_text(place)})")
        lines += ["(deny file-write*)",
                  "(allow file-write* " + " ".join(places) + ")"]
    if policy["fs_read"] is not None and not read_any:
        home = os.path.realpath(os.path.expanduser("~"))
        # a read grant is named whether or not it is there yet: a program
        # may read back what it has just written
        allowed = interpreter_reads(policy["net"] != "none") + _existing(
            reads + ([temp] if temp else [])) + [
                os.path.realpath(g) for g in policy["fs_read"]]
        # a directory is allowed with what is beneath it, a file as itself
        # getcwd() opens the working directory, and failing that reads each
        # directory above it, so those directories themselves - the names in
        # them, not the files - stay readable: a relative path cannot be
        # resolved otherwise
        above, step = [], os.path.realpath(os.getcwd())
        while step not in above:
            above.append(step)
            step = os.path.dirname(step)
        # The denial names what it leaves out itself. A later `allow
        # file-read*` does not take back a `deny file-read-data`: the rule
        # for the one operation beats the rule for the family, whichever
        # comes last - which a Python installed under the home directory,
        # as a runner's 3.10 is, was the first to meet.
        kept = [f"(require-not ({'literal' if os.path.isfile(p) else 'subpath'}"
                f" {_sbpl_text(p)}))" for p in allowed] + [
                    f"(require-not (literal {_sbpl_text(p)}))" for p in above]
        lines += ["(deny file-read-data (require-all (require-any "
                  f'(subpath {_sbpl_text(home)}) (subpath "/Volumes")) '
                  + " ".join(kept) + "))"]
    return "\n".join(lines)


def _apply_macos(policy: dict[str, Any], reads: list[str], writes: list[str],
                 temp: str | None, read_any: bool) -> dict[str, Any]:
    held: dict[str, str] = {}
    profile = mac_profile(policy, reads, writes, temp, read_any)
    why = None
    try:
        lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        lib.sandbox_init.argtypes = [ctypes.c_char_p, ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_char_p)]
        lib.sandbox_init.restype = ctypes.c_int
        error = ctypes.c_char_p()
        if lib.sandbox_init(profile.encode("utf-8"), 0,
                            ctypes.byref(error)) != 0:
            why = "sandbox_init: " + (error.value or b"failed").decode(
                "utf-8", "replace")
    except (OSError, AttributeError) as e:
        why = f"sandbox_init is not available: {e}"
    if why is not None:
        for what in _restricted(policy):
            held[what] = f"no: {why}"
        return _judge(policy, held, [], [])
    if policy["fs_read"] is not None:
        held["fs_read"] = (
            "partly: reads are refused under the home directory and "
            "/Volumes only, not held to exactly the grants"
            if not read_any else
            "no: this pool has no import_root, so reads are not held")
    if policy["fs_write"] is not None:
        wider = [g for g in policy["fs_write"] if _nearest_directory(g)[1]]
        held["fs_write"] = "yes" if not wider else (
            f"partly: {wider[0]} does not exist yet, so writes are held to "
            f"the nearest directory that does")
    if policy["net"] == "none":
        held["net"] = "yes"
    elif isinstance(policy["net"], dict):
        held["net"] = ("no: the profile allows the network; the host is "
                       "held by the language alone")
    if not policy["spawn"]:
        held["spawn"] = "yes"
    return _judge(policy, held, [MAC_SANDBOX],
                  ["sandbox profiles are deprecated by Apple (sandbox-exec "
                   "and sandbox_init both), and may stop working in a later "
                   "macOS"])


# ---- Windows: a job object, the token, the integrity level ---------------------

def _windows_job() -> str | None:
    """Put this process in a job of its own that holds one process and the
    USER-object restrictions. None, or why it failed."""
    import ctypes.wintypes as w
    k = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux

    class BASIC(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                    ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", w.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", w.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", w.DWORD),
                    ("SchedulingClass", w.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in (
            "ReadOperationCount", "WriteOperationCount",
            "OtherOperationCount", "ReadTransferCount",
            "WriteTransferCount", "OtherTransferCount")]

    class EXTENDED(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", BASIC), ("IoInfo", IO),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k.CreateJobObjectW.restype = w.HANDLE
    k.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
    k.SetInformationJobObject.restype = w.BOOL
    k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int,
                                          ctypes.c_void_p, w.DWORD]
    k.AssignProcessToJobObject.restype = w.BOOL
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    k.GetCurrentProcess.restype = w.HANDLE
    job = k.CreateJobObjectW(None, None)
    if not job:
        return f"CreateJobObject: error {ctypes.get_last_error()}"  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    info = EXTENDED()
    info.BasicLimitInformation.LimitFlags = 0x00000008   # ACTIVE_PROCESS
    info.BasicLimitInformation.ActiveProcessLimit = 1
    if not k.SetInformationJobObject(job, 9, ctypes.byref(info),
                                     ctypes.sizeof(info)):
        return f"SetInformationJobObject: error {ctypes.get_last_error()}"  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    ui = w.DWORD(0xFF)     # handles, clipboard, system parameters, display,
    #                        global atoms, desktop, exit windows
    k.SetInformationJobObject(job, 4, ctypes.byref(ui), ctypes.sizeof(ui))
    if not k.AssignProcessToJobObject(job, k.GetCurrentProcess()):
        return f"AssignProcessToJobObject: error {ctypes.get_last_error()}"  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    # the handle is kept for the life of the process: the job is the box
    from . import state as _state
    vars(_state)["_CONFINEMENT_JOB"] = job
    return None


def _windows_token(lower: bool, temp: str | None) -> tuple[str | None,
                                                           str | None]:
    """Remove every privilege but SeChangeNotifyPrivilege from this
    process's token, and, when `lower`, give it the low integrity level
    (labelling `temp` low first, so the run can still use it). (why the
    privileges were not removed or None, why it was not lowered or None)."""
    import ctypes.wintypes as w
    a = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    k = ctypes.WinDLL("kernel32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux

    class LUID(ctypes.Structure):
        _fields_ = [("LowPart", w.DWORD), ("HighPart", w.LONG)]

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", LUID), ("Attributes", w.DWORD)]

    k.GetCurrentProcess.restype = w.HANDLE
    a.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    a.OpenProcessToken.restype = w.BOOL
    a.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                      w.DWORD, ctypes.POINTER(w.DWORD)]
    a.GetTokenInformation.restype = w.BOOL
    a.AdjustTokenPrivileges.argtypes = [w.HANDLE, w.BOOL, ctypes.c_void_p,
                                        w.DWORD, ctypes.c_void_p,
                                        ctypes.c_void_p]
    a.AdjustTokenPrivileges.restype = w.BOOL
    a.LookupPrivilegeValueW.argtypes = [w.LPCWSTR, w.LPCWSTR,
                                        ctypes.POINTER(LUID)]
    a.LookupPrivilegeValueW.restype = w.BOOL
    a.SetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                      w.DWORD]
    a.SetTokenInformation.restype = w.BOOL
    a.ConvertStringSidToSidW.argtypes = [w.LPCWSTR,
                                         ctypes.POINTER(ctypes.c_void_p)]
    a.ConvertStringSidToSidW.restype = w.BOOL
    a.GetLengthSid.argtypes = [ctypes.c_void_p]
    a.GetLengthSid.restype = w.DWORD
    token = w.HANDLE()
    # TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY | TOKEN_ADJUST_DEFAULT
    if not a.OpenProcessToken(k.GetCurrentProcess(), 0x0020 | 0x0008 | 0x0080,
                              ctypes.byref(token)):
        why = f"OpenProcessToken: error {ctypes.get_last_error()}"  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        return why, why
    no_privileges: str | None = None
    try:
        needed = w.DWORD(0)
        a.GetTokenInformation(token, 3, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(max(needed.value, 4))
        if not a.GetTokenInformation(token, 3, buffer, needed.value,
                                     ctypes.byref(needed)):
            no_privileges = (f"GetTokenInformation: error "
                             f"{ctypes.get_last_error()}")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        else:
            count = w.DWORD.from_buffer(buffer).value
            entries = (LUID_AND_ATTRIBUTES * count).from_buffer(
                buffer, ctypes.sizeof(w.DWORD))
            keep = LUID()
            a.LookupPrivilegeValueW(None, "SeChangeNotifyPrivilege",
                                    ctypes.byref(keep))
            for entry in entries:
                if (entry.Luid.LowPart, entry.Luid.HighPart) != (
                        keep.LowPart, keep.HighPart):
                    entry.Attributes = 0x00000004      # SE_PRIVILEGE_REMOVED
            if not a.AdjustTokenPrivileges(token, False, buffer, 0, None,
                                           None):
                no_privileges = (f"AdjustTokenPrivileges: error "
                                 f"{ctypes.get_last_error()}")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        not_lowered: str | None = None
        if lower:
            if temp:
                not_lowered = _windows_label_low(temp)
            sid = ctypes.c_void_p()
            if not_lowered is None and not a.ConvertStringSidToSidW(
                    "S-1-16-4096", ctypes.byref(sid)):
                not_lowered = (f"ConvertStringSidToSid: error "
                               f"{ctypes.get_last_error()}")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
            if not_lowered is None:
                class LABEL(ctypes.Structure):
                    _fields_ = [("Sid", ctypes.c_void_p),
                                ("Attributes", w.DWORD)]
                label = LABEL(sid, 0x00000020)         # SE_GROUP_INTEGRITY
                if not a.SetTokenInformation(
                        token, 25, ctypes.byref(label),
                        ctypes.sizeof(label) + a.GetLengthSid(sid)):
                    not_lowered = (f"SetTokenInformation: error "
                                   f"{ctypes.get_last_error()}")  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
        else:
            not_lowered = "not asked for"
        return no_privileges, not_lowered
    finally:
        k.CloseHandle(token)


def _windows_label_low(path: str) -> str | None:
    """Give a directory the low mandatory label, inherited by what is made
    in it, so a process at the low integrity level can write there."""
    import ctypes.wintypes as w
    a = ctypes.WinDLL("advapi32", use_last_error=True)  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    sd = ctypes.c_void_p()
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = w.BOOL
    if not a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            "S:(ML;OICI;NW;;;LW)", 1, ctypes.byref(sd), None):
        return f"the label could not be built: error {ctypes.get_last_error()}"  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    present, defaulted = w.BOOL(), w.BOOL()
    sacl = ctypes.c_void_p()
    a.GetSecurityDescriptorSacl.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(w.BOOL),
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(w.BOOL)]
    a.GetSecurityDescriptorSacl.restype = w.BOOL
    if not a.GetSecurityDescriptorSacl(sd, ctypes.byref(present),
                                       ctypes.byref(sacl),
                                       ctypes.byref(defaulted)):
        return f"the label could not be read: error {ctypes.get_last_error()}"  # type: ignore[attr-defined]  # Windows only; mypy checks as Linux
    a.SetNamedSecurityInfoW.argtypes = [
        w.LPCWSTR, ctypes.c_int, w.DWORD, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p]
    a.SetNamedSecurityInfoW.restype = w.DWORD
    failed = a.SetNamedSecurityInfoW(path, 1, 0x00000010, None, None, None,
                                     sacl)
    return None if failed == 0 else (f"the temporary directory could not be "
                                     f"labelled low: error {failed}")


WINDOWS_NOT_HELD = (
    "reads and the network need an AppContainer, which is not used: a "
    "process cannot enter one after it has started, and a python.exe "
    "started in one cannot read its own installation unless that was "
    "installed readable by ALL APPLICATION PACKAGES, which python.org's, "
    "the Store's and a virtual environment's are not")


def _apply_windows(policy: dict[str, Any], reads: list[str],
                   writes: list[str], temp: str | None,
                   read_any: bool) -> dict[str, Any]:
    held: dict[str, str] = {}
    layers: list[str] = []
    notes: list[str] = []
    lower = policy["fs_write"] == [] and not writes
    no_privileges, not_lowered = _windows_token(lower, temp)
    if no_privileges is None:
        layers.append(WINDOWS_TOKEN)
    else:
        notes.append(f"privileges were not removed ({no_privileges})")
    if not_lowered is None:
        layers.append(WINDOWS_LOW)
    no_job = None if policy["spawn"] else _windows_job()
    if not policy["spawn"]:
        held["spawn"] = "yes" if no_job is None else f"no: {no_job}"
        if no_job is None:
            layers.append(WINDOWS_JOB)
    if policy["fs_write"] is not None:
        if not_lowered is None:
            held["fs_write"] = "yes"
        elif not lower:
            held["fs_write"] = (
                "no: a budget with a write grant runs at medium integrity, "
                "because lowering it would need the granted directory "
                "relabelled")
        else:
            held["fs_write"] = f"no: {not_lowered}"
    if policy["fs_read"] is not None:
        held["fs_read"] = "no: reads are not held on Windows"
    if policy["net"] != "any":
        held["net"] = "no: the network is not held on Windows"
    if policy["fs_read"] is not None or policy["net"] != "any":
        notes.append(WINDOWS_NOT_HELD)
    return _judge(policy, held, layers, notes)


# ---- applying it ---------------------------------------------------------------------

def supported() -> tuple[bool, str]:
    """Whether this system offers anything, and what, for `sabline doctor`."""
    if sys.platform.startswith("linux"):
        abi, arch = landlock_abi(), seccomp_arch()
        if abi or arch:
            return True, (f"Landlock ABI {abi}" if abi else "no Landlock") \
                + (f", seccomp-bpf ({arch})" if arch else ", no seccomp "
                   "table for this machine")
        return False, "this kernel offers no Landlock and no seccomp table"
    if sys.platform == "darwin":
        return True, "a sandbox profile (sandbox_init; deprecated by Apple)"
    if os.name == "nt":
        return True, ("a job object, the token's privileges removed, a low "
                      "integrity level for a budget with no write grant; "
                      "no AppContainer")
    return False, f"nothing is known for {sys.platform}"


def apply(policy: dict[str, Any], *, reads: Any = (), writes: Any = (),
          temp: str | None = None, read_any: bool = False) -> dict[str, Any]:
    """Ask the operating system to hold this process to `policy`, and say
    what it did: {level, reason, layers, policy_sha256, platform}.

    `reads` and `writes` are what the run itself needs beyond the budget -
    the program's files, a receipt's directory - `temp` its private
    temporary directory, and `read_any` leaves reads unheld (a pool with no
    import root). It cannot be undone, and it is applied once: a second
    call reports the first."""
    from . import state as _state
    if _state.CONFINEMENT is not None:
        return dict(_state.CONFINEMENT)
    if not policy["enforced"]:
        done = _judge(policy, {}, [], [])
    else:
        reads = [str(p) for p in reads if p]
        writes = [str(p) for p in writes if p]
        try:
            if sys.platform.startswith("linux"):
                done = _apply_linux(policy, reads, writes, temp, read_any)
            elif sys.platform == "darwin":
                done = _apply_macos(policy, reads, writes, temp, read_any)
            elif os.name == "nt":
                done = _apply_windows(policy, reads, writes, temp, read_any)
            else:
                done = report(NONE, f"nothing is known for {sys.platform}",
                              [], policy)
        except Exception as e:             # never a reason not to run: say so
            done = report(NONE, f"confinement could not be applied: "
                          f"{type(e).__name__}: {e}", [], policy)
    vars(_state)["CONFINEMENT"] = dict(done)
    return done


def predict(policy: dict[str, Any], *, read_any: bool = False,
            system: str | None = None) -> dict[str, Any]:
    """What apply() would report, without applying it. For this machine -
    `sabline doctor`, the command line's audit - it asks the kernel what it
    offers and looks at the granted paths. With `system` ('linux', 'macos'
    or 'windows') it is what that system gives where every layer it has is
    there - Landlock ABI 4 or later and seccomp, on Linux - and reads
    nothing of the machine, which is what the audit document records, so
    that document stays the same bytes wherever it is made."""
    held: dict[str, str] = {}
    nominal = system is not None
    system = system or _platform()
    if not policy["enforced"]:
        return dict(_judge(policy, {}, [], []), platform=system)

    def not_yet(grants: list[str]) -> list[str]:
        return [] if nominal else [g for g in grants
                                   if _nearest_directory(g)[1]]

    if system == "linux":
        abi = 4 if nominal else landlock_abi()
        arch = "x86_64" if nominal else seccomp_arch()
        layers = ([LANDLOCK if nominal else f"{LANDLOCK}-abi{abi}"]
                  if abi else []) + ([SECCOMP] if arch else [])
        no_landlock = "no: this kernel has no Landlock"
        no_seccomp = "no: seccomp has no system call table for this machine"
        if policy["fs_read"] is not None:
            later = not_yet(policy["fs_read"])
            held["fs_read"] = no_landlock if not abi else (
                "no: this pool has no import_root, so reads are not held"
                if read_any else f"partly: {later[0]} does not exist yet, so "
                f"reads are held to the nearest directory that does"
                if later else "yes")
        if policy["fs_write"] is not None:
            wider = not_yet(policy["fs_write"])
            held["fs_write"] = no_landlock if not abi else (
                f"partly: Landlock ABI {abi} cannot hold truncation"
                if abi < 3 else f"partly: {wider[0]} does not exist yet, so "
                f"writes are held to the nearest directory that does"
                if wider else "yes")
        if policy["net"] == "none":
            held["net"] = "yes" if arch else no_seccomp
        elif isinstance(policy["net"], dict):
            held["net"] = ("partly: the kernel holds TCP to the granted "
                           "ports; the host is held by the language alone"
                           if abi >= 4 and _tcp_ports(policy) else
                           "no: the kernel cannot hold a host; it is held by "
                           "the language alone")
        if not policy["spawn"]:
            held["spawn"] = "yes" if arch else (
                "partly: Landlock refuses execute only" if abi
                else no_seccomp)
        done = _judge(policy, held, layers, [])
    elif system == "macos":
        if policy["fs_read"] is not None:
            held["fs_read"] = ("partly: reads are refused under the home "
                               "directory and /Volumes only, not held to "
                               "exactly the grants")
        if policy["fs_write"] is not None:
            held["fs_write"] = "yes"
        if policy["net"] == "none":
            held["net"] = "yes"
        elif isinstance(policy["net"], dict):
            held["net"] = ("no: the profile allows the network; the host is "
                           "held by the language alone")
        if not policy["spawn"]:
            held["spawn"] = "yes"
        done = _judge(policy, held, [MAC_SANDBOX],
                      ["sandbox profiles are deprecated by Apple"])
    elif system == "windows":
        lower = policy["fs_write"] == []
        if not policy["spawn"]:
            held["spawn"] = "yes"
        if policy["fs_write"] is not None:
            held["fs_write"] = "yes" if lower else (
                "no: a budget with a write grant runs at medium integrity")
        if policy["fs_read"] is not None:
            held["fs_read"] = "no: reads are not held on Windows"
        if policy["net"] != "any":
            held["net"] = "no: the network is not held on Windows"
        done = _judge(policy, held, [WINDOWS_TOKEN] + (
            [WINDOWS_LOW] if lower else []) + [WINDOWS_JOB],
            [WINDOWS_NOT_HELD] if policy["fs_read"] is not None
            or policy["net"] != "any" else [])
    else:
        done = report(NONE, f"nothing is known for {system}", [], policy)
    return dict(done, platform=system)


SYSTEMS = ("linux", "macos", "windows")


def private_temp() -> tuple[str | None, str | None]:
    """A temporary directory of this run's own, made before confinement and
    removed when the process ends: (the directory, the directory the
    confinement must let it write). On Linux the second is its parent, a
    directory of this user's that other confined runs of theirs share,
    because Landlock lets a directory be removed only by a right on the
    directory above it. tempfile and TMPDIR, TEMP and TMP name the first."""
    import atexit
    import shutil
    import tempfile
    try:
        if sys.platform.startswith("linux"):
            parent = os.path.join(tempfile.gettempdir(),
                                  f"sabline-{os.getuid()}")
            os.makedirs(parent, mode=0o700, exist_ok=True)
            held = os.lstat(parent)
            if held.st_uid != os.getuid() or not os.path.isdir(parent) \
                    or os.path.islink(parent):
                return None, None        # somebody else's: not ours to use
            os.chmod(parent, 0o700)
            made = tempfile.mkdtemp(prefix="run-", dir=parent)
            rule = parent
        else:
            made = rule = tempfile.mkdtemp(prefix="sabline-run-")
    except OSError:
        return None, None
    atexit.register(shutil.rmtree, made, True)
    tempfile.tempdir = made
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = made
    return made, rule


def confine_this_run(budget: Any, *, files: Any = (),
                     temp_rule: str | None = None) -> dict[str, Any]:
    """What the command line does at a program's first statement: derive
    the policy from the budget the run was given, apply it, and then let
    the fault-injection hook try it. A budget that grants ffi gets a
    private temporary directory, since a module may want one; a run with
    none has no use for one after it has been compiled."""
    from . import state as _state
    if budget is None:                     # the one installed for this run
        from .budget import Budget
        budget = Budget.current()
    if _state.CONFINEMENT is not None:
        done = dict(_state.CONFINEMENT)
    elif not _state.CONFINE:
        policy = os_policy(budget, confine=False)
        done = unconfined(policy, _why_not_enforced(policy))
        vars(_state)["CONFINEMENT"] = dict(done)
    else:
        policy = os_policy(budget)
        rule = temp_rule
        if rule is None and policy["enforced"] and "ffi" in budget.effects:
            _made, rule = private_temp()
        done = apply(policy, reads=list(files), temp=rule)
    inject_fault(done)
    return done


def unconfined(policy: dict[str, Any], reason: str) -> dict[str, Any]:
    """The report of a run the operating system was not asked to hold."""
    return report(NONE, reason, [], policy)


def current() -> dict[str, Any] | None:
    """What was applied to this process, or None when nothing was asked."""
    from . import state as _state
    return None if _state.CONFINEMENT is None else dict(_state.CONFINEMENT)


# ---- the honesty test's hook, and the probe -----------------------------------

def inject_fault(confinement: dict[str, Any] | None) -> None:
    """When SABLINE_FAULT_INJECT is set: the runtime itself, from Python,
    attempts one effect no budget was consulted about. Refused by the
    operating system under confinement, it ends the run with E319 naming the
    layers; otherwise what happened is said on stderr and the run goes on."""
    asked = naming.env(FAULT_ENV)
    if not asked:
        return
    from .errors import SablineError
    kind, _, rest = asked.partition(":")
    what = {"read": f"a read of {rest}", "write": f"a write to {rest}",
            "connect": f"a connection to {rest}",
            "spawn": "starting a process",
            "spawn-breakaway": "starting a process outside the job",
            "signal": f"a signal to process {rest}",
            "mount": f"a bind mount {rest}",
            "unix-socket": "a Unix-domain socket"}.get(kind)
    if what is None:
        print(f"sabline: {FAULT_ENV}={asked!r} names no fault; it is read:"
              f"PATH, write:PATH, connect:HOST:PORT, spawn, spawn-breakaway, "
              f"signal:PID, mount:SOURCE:TARGET or unix-socket",
              file=sys.stderr)
        return
    try:
        if kind == "read":
            with open(rest, "rb") as fh:
                fh.read(1)
        elif kind == "write":
            with open(rest, "w", encoding="utf-8") as fh:
                fh.write("written by the fault-injection hook")
        elif kind == "connect":
            import socket
            host, _, port = rest.rpartition(":")
            with socket.create_connection((host, int(port)), timeout=5):
                pass
        elif kind == "signal":
            if os.name == "nt":
                # Windows has no signal to send: os.kill's 0 there is
                # CTRL_C_EVENT, which interrupts the console's every process
                print(f"sabline: fault injection: {what} is not attempted "
                      f"on Windows, which has no such signal",
                      file=sys.stderr)
                return
            os.kill(int(rest), 0)
        elif kind == "unix-socket":
            import socket
            socket.socket(getattr(socket, "AF_UNIX", 1),
                          socket.SOCK_STREAM).close()
        elif kind == "mount":
            source, _, target = rest.partition(":")
            libc = _libc()
            if libc.mount(source.encode(), target.encode(), None,
                          ctypes.c_ulong(4096), None) != 0:    # MS_BIND
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
        else:
            import subprocess
            # CREATE_BREAKAWAY_FROM_JOB, which a job that allows no
            # breakaway refuses
            extra: dict[str, Any] = {"creationflags": 0x01000000} \
                if kind == "spawn-breakaway" else {}
            done = subprocess.run(
                [sys.executable, "-c", "pass"], capture_output=True,
                timeout=60, **extra)
            if done.returncode != 0:
                raise OSError(f"it started and exited {done.returncode}")
    except (OSError, ValueError) as e:
        level = (confinement or {}).get("level", NONE)
        if level != NONE:
            layers = ", ".join((confinement or {}).get("layers") or [])
            raise SablineError(
                "E319", f"the runtime itself attempted {what}, outside "
                f"this run's budget, and the operating system refused it "
                f"({type(e).__name__}: {e}); confinement: {level}, by "
                f"{layers}", 0,
                fixes=["this is the fault-injection hook "
                       f"({FAULT_ENV}); unset it to run the program"])
        print(f"sabline: fault injection: {what} failed, and not by "
              f"confinement, which is none: {type(e).__name__}: {e}",
              file=sys.stderr)
        return
    print(f"sabline: fault injection: {what} succeeded; confinement: "
          f"{(confinement or {}).get('level', NONE)}", file=sys.stderr)


def probe(port: Any, outside: Any, inside: Any = None) -> dict[str, str]:
    """From inside a confined worker, try what confinement may stop: a TCP
    connection to 127.0.0.1:port, a file written at `outside`, a file read
    at `inside`, and a process started. Each is 'allowed' or 'refused:
    why'."""
    import socket
    import subprocess
    out: dict[str, str] = {}
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=5):
            pass
        out["connect"] = "allowed"
    except (OSError, ValueError, TypeError) as e:
        out["connect"] = f"refused: {type(e).__name__}: {e}"
    try:
        with open(str(outside), "w", encoding="utf-8") as fh:
            fh.write("written from inside the confinement")
        out["write"] = "allowed"
    except OSError as e:
        out["write"] = f"refused: {type(e).__name__}: {e}"
    if inside is not None:
        try:
            with open(str(inside), "rb") as fh:
                fh.read(1)
            out["read"] = "allowed"
        except OSError as e:
            out["read"] = f"refused: {type(e).__name__}: {e}"
    try:
        done = subprocess.run([sys.executable, "-c", "pass"],
                              capture_output=True, timeout=30)
        out["spawn"] = ("allowed" if done.returncode == 0 else
                        f"refused: it started and exited {done.returncode}")
    except (OSError, subprocess.SubprocessError) as e:
        out["spawn"] = f"refused: {type(e).__name__}: {e}"
    return out


def claims(confinement: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    """The probe's attempts this confinement says it refuses."""
    if confinement.get("level") == NONE:
        return []
    layers = " ".join(confinement.get("layers") or [])
    reason = str(confinement.get("reason") or "")
    out = []
    if not policy["spawn"] and "spawn:" not in reason:
        out.append("spawn")
    if policy["net"] == "none" and "net:" not in reason:
        out.append("connect")
    if policy["fs_write"] is not None and "fs_write: a budget" not in reason \
            and "fs_write: no" not in reason and (
                LANDLOCK in layers or MAC_SANDBOX in layers
                or WINDOWS_LOW in layers):
        out.append("write")
    if policy["fs_read"] is not None and LANDLOCK in layers \
            and "fs_read:" not in reason:
        out.append("read")
    return out
