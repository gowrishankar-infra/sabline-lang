"""The run state: everything a running program can change, in one place.

Every other module imports this as _state and reads and writes these
as _state.NAME. A name imported from here would be a copy, and a
rebinding - Budget.install() replaces FS_GRANTS - would not reach it.
MUTABLE_GLOBALS (velaris/pool.py) lists the names a pool worker puts back
between programs.
"""
import typing as _typing

from .tables import DEFAULT_ALLOW

if _typing.TYPE_CHECKING:
    import random as _random


# Where imports may come from, when a program is served rather than run by
# the person who owns the disk (8.1). None - the default everywhere but the
# doors - resolves an import wherever its path points, as it always has.
# Set, an import must be a .vel file at or under this directory (realpath,
# so `..` and a symbolic link cannot leave it) or a file of the shipped
# standard library; anything else is E515 before the file is opened, so
# whether it exists is not told either. The HTTP door and the MCP server set
# it to the directory they serve (--root, the directory they were started
# in by default); the library takes import_root=.
IMPORT_ROOT: str | None = None


PROGRAM_ARGS: list[str] = []    # filled by the CLI: velaris prog.vel a b c

# read_file / read_file_secret refuse a file larger than this, so a single
# read cannot exhaust memory (a whole file is read at once). The default is
# generous for source, config and data files; a program that legitimately
# reads more raises it with `--allow ... ` no - with `--max-read <MB>` on the
# command line. It is a resource ceiling like a memory cap, not a grant, so
# breaching it is E316 and cannot be caught. 64 MiB unless raised (7.1.2).
MAX_READ_BYTES = 64 * 1024 * 1024


EFFECT_BUDGET: set[str] = {DEFAULT_ALLOW}    # io, unless you say otherwise
FFI_MODULES: set[str] | None = None     # None = any module; a set = only
                                        # these top-level packages


FS_GRANTS: list[tuple[str, str | None]] | None = None   # None = any path;
                                                        # else [(kind, prefix)]
NET_GRANTS: list[tuple[str, int | None]] | None = None  # None = any host;
                                                        # else [(host, port)]
OP_LIMITS: dict[str, int | None] = {"fs": None, "net": None}   # None = unlimited
OP_COUNTS: dict[str, int] = {"fs": 0, "net": 0}
EFFECT_USES: dict[str, int] = {}     # effect -> how many builtin calls the
                           # budget let through this run; what the doors log (3.4)

# Tools (8.5). TOOL_GRANTS is None for any tool (a plain `tool` grant), else
# {name: None for any arguments, or [(argument, pattern), ...]}; an empty
# dict is what a budget without `tool` leaves. TOOL_LIMITS holds the @N
# caps, by tool name and under "" for the whole run; TOOL_COUNTS what has
# been spent of them. GRANT_USES counts what each grant let through, by the
# grant's own text - the operator's words, never the program's - which is
# what a receipt's `grants_used` is made from. TOOLS is the session `velaris
# run --tools` opened (velaris/tools.py), or None: then there is no tool to
# reach and a call is E320.
TOOL_GRANTS: "dict[str, list[tuple[str, str]] | None] | None" = {}
TOOL_LIMITS: dict[str, int] = {}
TOOL_COUNTS: dict[str, int] = {}
GRANT_USES: dict[str, int] = {}
TOOLS: _typing.Any = None

# Determinism knobs (8.0). --seed makes random() reproducible; --freeze-time
# makes now() a fixed instant. Neither is a grant: a program still needs
# `rand` for random() and `clock` for now(), and the budget still refuses
# them - these fix a value, they do not widen what a run may touch. They
# are recorded as the run's parameters (velaris.invocation/1 run_params on
# the doors; the CLI prints them under --time).
SEED: int | None = None                # int, or None
FROZEN_TIME: int | None = None         # epoch seconds (int), or None
_RNG: "_random.Random | None" = None   # a seeded random.Random when SEED is set


# What a receipt is recording about the run in progress (8.1), or None when
# nobody asked for one. Section 19 has the recorder. (A _RunRecorder; the
# recorder module comes after this one, so it is not named here.)
RUN_RECORDER: _typing.Any = None


TRACE = {"on": False, "depth": 0, "calls": 0, "limit": 4000}


# A file whose appearance asks the running program to stop (8.3). Set only in
# the worker of `velaris eval`, which makes it in a directory of its own,
# outside the run's budget: the interpreter looks for it every few hundred
# calls and loop turns and stops there with E615, a stop the run's receipt
# records as asked for and honoured. None - everywhere else - looks for
# nothing.
STOP_FILE: str | None = None


# The tool responses of code mode (8.3): what py, py_int, py_float and
# py_json gave back, recorded by `velaris program.vel --record-responses FILE`
# or handed back in order by `velaris replay --responses FILE`, in place of
# calling Python. The budget and the module grants are checked as they are
# for any call, first. None - everywhere else - calls Python.
RESPONSES: _typing.Any = None


_proof_timeout: float | None = None      # set by --proof-timeout


_NATIVE_KEEPALIVE: list[object] = []   # prevents the JIT engine being garbage-collected


PY_OBJECTS: dict[int, _typing.Any] = {}
PY_NEXT = [1]


# Whether a run asks the operating system to hold its budget too (8.4,
# velaris/confine.py). True unless --no-confine, Pool(confine=False) or
# run(confine=False) said otherwise - never anything a program can reach.
CONFINE = True

# What was applied to THIS process - {level, reason, layers, policy_sha256,
# platform} - or None while nothing has been. It cannot be taken off again,
# so it is not among the names a pool worker puts back between programs.
CONFINEMENT: "dict[str, _typing.Any] | None" = None

# What a run in this process does just before its program's first
# statement, once everything has been read, proven and compiled: apply the
# confinement. A callable taking the list of files the program was read
# from, set by the command line and by a worker whose pool serves one run;
# None elsewhere.
BEFORE_FIRST_STATEMENT: _typing.Any = None


# On Windows, the handle of the job object this process put itself in, kept
# open for the life of the process.
_CONFINEMENT_JOB: _typing.Any = None

# The files the program now running was read from, for the confinement to
# let the process keep reading them (an error names its line).
PROGRAM_FILES: list[str] = []

# In a pool worker: what the worker's hello said of its confinement, which
# is "pending" in a pool of one run until the first statement.
WORKER_CONFINEMENT: "dict[str, _typing.Any] | None" = None


# True in a process that is itself the bounded child of a check, an audit
# or a pool, so that a library call there does its work in place rather
# than start another child under the one already bounded.
_IN_CHILD = False
