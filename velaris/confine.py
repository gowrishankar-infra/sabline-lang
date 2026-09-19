"""What the operating system adds to a budget, where it offers anything: the
confinement `velaris eval` asks for (8.3).
"""
import ctypes
import os
import subprocess
import sys
from typing import Any

# ---------------------------------------------------------------------------
# 17b. CONFINEMENT - a second boundary under the budget, where the OS has one
#
#     The budget is enforced by the interpreter, in the process that runs
#     the program. Under `velaris eval` the worker that runs it is also held
#     by what the operating system offers without privileges, and the run's
#     receipt names which of these it got:
#
#       landlock-net     Linux, Landlock ABI 4 or later: no file written,
#                        removed or made outside the granted write
#                        directories and the run's own temporary directory,
#                        no program started, no TCP connection made or
#                        listened for
#       landlock         Linux, Landlock ABI 1 to 3: the same, but TCP is not
#                        held
#       job-one-process  Windows: the worker's job object holds one process,
#                        so it cannot start another; files and the network are
#                        not held
#       sandbox-exec     macOS: no network, no process forked, no file written
#                        outside the granted write directories and the run's
#                        temporary directory - applied only when a trial run of
#                        the profile starts Python
#       none             nothing: the budget is the only boundary
#
#     Reads are held by none of them: the budget holds a program's reads,
#     and the worker itself reads Python's own files as it runs. The level is
#     what was applied, not what was asked for: a kernel without Landlock, a
#     job object that could not be made, or a profile that failed its trial
#     is `none`, and `velaris eval --confinement-probe` shows what the level
#     stops on this machine.
# ---------------------------------------------------------------------------

NONE = "none"
LANDLOCK = "landlock"
LANDLOCK_NET = "landlock-net"
WINDOWS_JOB = "job-one-process"
MAC_SANDBOX = "sandbox-exec"

# what each level claims to refuse, as the probe names the attempts
CLAIMS = ((NONE, ()),
          (LANDLOCK, ("write", "spawn")),
          (LANDLOCK_NET, ("write", "spawn", "connect")),
          (WINDOWS_JOB, ("spawn",)),
          (MAC_SANDBOX, ("write", "spawn", "connect")))

# Landlock (Linux 5.13 and later): the same system call numbers on every
# architecture, and the access rights of include/uapi/linux/landlock.h
_SYS_CREATE_RULESET, _SYS_ADD_RULE, _SYS_RESTRICT_SELF = 444, 445, 446
_CREATE_RULESET_VERSION = 1
_RULE_PATH_BENEATH = 1
_PR_SET_NO_NEW_PRIVS = 38
_FS_EXECUTE = 1 << 0
_FS_WRITE_FILE = 1 << 1
_FS_REMOVE_DIR = 1 << 4
_FS_REMOVE_FILE = 1 << 5
_FS_MAKE_ALL = sum(1 << b for b in range(6, 13))   # char, dir, reg, sock,
                                                   # fifo, block, sym
_FS_REFER = 1 << 13                                # ABI 2
_FS_TRUNCATE = 1 << 14                             # ABI 3
_NET_BIND_TCP = 1 << 0                             # ABI 4
_NET_CONNECT_TCP = 1 << 1


class _RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64),
                ("handled_access_net", ctypes.c_uint64)]


class _PathBeneath(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64),
                ("parent_fd", ctypes.c_int32)]


def claims(level: str) -> tuple[str, ...]:
    """The attempts a level says it refuses."""
    return next((c for name, c in CLAIMS if name == level), ())


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


def _nearest_directory(path: str) -> str | None:
    """The path itself when it is a directory, else the nearest directory
    above it that exists: a write grant may name a file not made yet."""
    p = os.path.realpath(path)
    while True:
        if os.path.isdir(p):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def confine_linux(writable: list[str]) -> str:
    """Hold this process with Landlock: writes only beneath `writable`, no
    program started, and from ABI 4 no TCP. Applied to this thread and every
    thread it starts after. The level applied; `none` when the kernel has no
    Landlock or a step failed, and then nothing was applied."""
    abi = landlock_abi()
    if abi < 1:
        return NONE
    libc = _libc()
    write = _FS_WRITE_FILE | _FS_REMOVE_DIR | _FS_REMOVE_FILE | _FS_MAKE_ALL
    if abi >= 2:
        write |= _FS_REFER
    if abi >= 3:
        write |= _FS_TRUNCATE
    net = (_NET_BIND_TCP | _NET_CONNECT_TCP) if abi >= 4 else 0
    attr = _RulesetAttr(write | _FS_EXECUTE, net)
    fd = libc.syscall(ctypes.c_long(_SYS_CREATE_RULESET), ctypes.byref(attr),
                      ctypes.c_size_t(ctypes.sizeof(attr)), ctypes.c_uint32(0))
    if fd < 0:
        return NONE
    try:
        for place in writable:
            directory = _nearest_directory(place)
            if directory is None:
                continue
            parent = os.open(directory, getattr(os, "O_PATH", 0)
                             | os.O_CLOEXEC)
            try:
                rule = _PathBeneath(write, parent)
                if libc.syscall(ctypes.c_long(_SYS_ADD_RULE), ctypes.c_int(fd),
                                ctypes.c_int(_RULE_PATH_BENEATH),
                                ctypes.byref(rule), ctypes.c_uint32(0)) != 0:
                    return NONE
            finally:
                os.close(parent)
        if libc.prctl(_PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
            return NONE
        if libc.syscall(ctypes.c_long(_SYS_RESTRICT_SELF), ctypes.c_int(fd),
                        ctypes.c_uint32(0)) != 0:
            return NONE
    except OSError:
        return NONE
    finally:
        os.close(fd)
    return LANDLOCK_NET if net else LANDLOCK


def confine_worker(writable: list[str]) -> str:
    """What a worker applies to itself before it serves anything: Landlock on
    Linux. Elsewhere the parent holds it, and the worker applies nothing."""
    if sys.platform.startswith("linux"):
        return confine_linux(writable)
    return NONE


SANDBOX_EXEC = "/usr/bin/sandbox-exec"


def _sbpl_text(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def mac_profile(writable: list[str]) -> str:
    """The sandbox-exec profile a macOS worker starts under. The later of two
    rules that match wins, so the denials follow `allow default` and the
    writable directories follow the denial of writes."""
    places = ['(literal "/dev/null")'] + [
        f"(subpath {_sbpl_text(os.path.realpath(p))})"
        for p in (_nearest_directory(w) for w in writable) if p]
    return "\n".join(["(version 1)", "(allow default)", "(deny network*)",
                      "(deny process-fork)", "(deny file-write*)",
                      "(allow file-write* " + " ".join(places) + ")"])


def mac_wrapper(writable: list[str]) -> list[str] | None:
    """The words to put before a worker's command on macOS, or None when
    sandbox-exec is not there or its profile does not let Python start."""
    if sys.platform != "darwin" or not os.path.exists(SANDBOX_EXEC):
        return None
    profile = mac_profile(writable)
    try:
        trial = subprocess.run(
            [SANDBOX_EXEC, "-p", profile, sys.executable, "-c",
             "import os; os.close(os.open(os.devnull, os.O_RDWR))"],
            capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return [SANDBOX_EXEC, "-p", profile] if trial.returncode == 0 else None


def probe(port: Any, outside: Any) -> dict[str, str]:
    """From inside a confined worker, try what the levels claim to stop: a
    TCP connection to 127.0.0.1:port, a file written at `outside`, and a
    process started. Each is 'allowed' or 'refused: why'."""
    import socket
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
    try:
        done = subprocess.run([sys.executable, "-c", "pass"],
                              capture_output=True, timeout=30)
        out["spawn"] = ("allowed" if done.returncode == 0 else
                        f"refused: it started and exited {done.returncode}")
    except (OSError, subprocess.SubprocessError) as e:
        out["spawn"] = f"refused: {type(e).__name__}: {e}"
    return out
