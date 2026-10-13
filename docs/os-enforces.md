# What the operating system enforces

This is the *what the operating system enforces* section of the
[threat model](../THREAT_MODEL.md), on a page of its own so that neither
page outgrows the size a page of the site may be, as
[known-open.md](known-open.md) is. The threat model says what Sabline
defends against; this page says, item by item, how much of that the
kernel holds too, on each of the three systems and in each of the two
runtimes.

From 8.4 the process that runs a program asks the operating system to
hold the budget it was given, before the program's first statement runs,
so that a fault in Sabline itself is a crash inside a box and not an
escape. The derivation is one function, `os_policy` in
`sabline/confine.py`: budget in, OS policy out, reading nothing of the
machine. This table is that module's `ENFORCES`, and `check_confine.py`
fails when the two differ.

| Budget item | Linux (Landlock, seccomp-bpf) | macOS (a sandbox profile) | Windows (job object, token, integrity level) |
|---|---|---|---|
| no `fs` granted | Landlock: no file read, written, made or removed but what the interpreter itself needs (below) | writes refused everywhere but the private temporary directory; reads refused under the home directory and /Volumes, but for the names in the working directory and in each directory above it, which getcwd reads | low integrity level: no write to anything of the user's; reads not held |
| `fs:read:DIR` | Landlock: reads beneath DIR (resolved), and nothing else of the user's; when DIR does not exist yet - a file the program writes and reads back - beneath the nearest directory that does, and the level is partial | reads beneath DIR allowed; outside it, refused only under the home directory and /Volumes | not held: the low integrity level does not stop a read |
| `fs:write:DIR` | Landlock: files written, made and truncated beneath DIR; when DIR does not exist yet, beneath the nearest directory that does, and the level is partial | writes beneath DIR, as Linux | not held: a write grant keeps the process at medium integrity, because lowering it would need the granted directory relabelled |
| `fs`, `fs:read`, `fs:write` with no path | that direction is not restricted, as the budget says | as Linux | as Linux |
| a credential location under a broad grant (E318) | not held: Landlock cannot take a path out of a hierarchy it allows | not held | not held |
| no `net` granted | seccomp: socket, socketpair, connect, bind, listen and accept refused (EPERM); Landlock ABI 4 and later also refuses TCP | `(deny network*)` | not held: it needs an AppContainer, which this Python cannot start in (below) |
| `net:HOST`, `net:HOST:PORT` | IPv4, IPv6 and netlink sockets allowed, and no Unix socket; with Landlock ABI 4 and later, and a port on every grant, TCP connections to those ports and 53 only. The host is held by the language alone, so the level is partial | the network allowed; the host is held by the language alone (partial) | not held |
| `net` with no host | any host, as the budget says; still no Unix socket, unless a granted Python module widened the policy to any host | not restricted, as the budget says | as macOS |
| `@N` counts | the language | the language | the language |
| `io` | the descriptors the process was started with; not restricted | as Linux | as Linux |
| `env` | not held: the environment is in the process's own memory | not held | not held |
| `clock`, `rand`, `declassify` | not held: reading the clock or the kernel's randomness reaches nothing outside the process, and declassify is a rule of the type system | not held | not held |
| `tool` | not held: a tool call is a line written to the standard output the process was started with and an answer read from its standard input; what the tool then does happens in the host's process, which this policy does not reach | not held | not held |
| starting a process (never a budget item) | seccomp: execve, execveat, fork, vfork, clone without CLONE_THREAD refused, clone3 answered ENOSYS; Landlock refuses execute | `(deny process-fork)` `(deny process-exec)` | job object: one active process; and the clipboard, the desktop, global atoms and other processes' USER handles |
| the rest of the deny-list (never a budget item) | seccomp: ptrace, mount and its new calls, pivot_root, chroot, unshare, setns, kernel modules, kexec, bpf, perf_event_open, process_vm_readv and writev, keyrings, io_uring, userfaultfd, open_by_handle_at, setting the clock, reboot, swapon, acct, quotactl, personality; a signal, by kill, tgkill or sigqueue, to any process but this one; input pushed at the terminal (TIOCSTI, TIOCLINUX) | what `(deny process-fork)` and the denial of writes imply; no list of system calls | every privilege but SeChangeNotifyPrivilege removed from the token |
| `ffi:MODULE` | widened to what FFI_WIDENS names for MODULE: nothing, any path, any host, or nothing enforced; a module not in the table, `ffi:os`, `ffi:subprocess` and plain `ffi` widen to nothing enforced, and the level is none | as Linux | as Linux |
| `ffi:MODULE` under `--confine strict` | widened to nothing: the policy is the budget's `fs:` and `net:` grants and what the interpreter itself reads, whatever modules are granted, and the rows above hold a module's own calls - native code, `ctypes`, `os.system` - as they hold the runtime's; a module that needs a path or a host needs it in the budget | as Linux, with the profile's limits: writes, the network and processes held, reads only under the home directory and /Volumes | as Linux, with this table's limits: no second process, and no write to anything of the user's when the budget grants no write |
| `--require-confinement full` or `partial` (never a budget item) | a run whose level, once applied, is below the one asked for is refused before its first statement (E326), and its receipt records the level it got | as Linux; every run is partial here at best - the level says that Apple has deprecated sandbox profiles - so `full` refuses every run | as Linux; a budget that restricts reads or the network - `io` itself does - gives partial here, so `full` refuses it |
| time and memory limits | RLIMIT_AS, and the parent's clock (as before 8.4) | the parent's clock; RLIMIT_AS is best-effort | the job object's memory limit, and the parent's clock |

## Through sabline-rt, which enters a container Windows' Python cannot

The table above is the Python package's own runtime. From 9.0 a run may
go through **sabline-rt** (`SABLINE_REFERENCE_RUNTIME=rust`), whose own
process is the run's - so it can be started inside a Windows
**AppContainer**, where a running `python.exe` cannot enter one and a
fresh one started in one cannot read its own installation. Everything
else is the same table: `sabline-rt os-policy --enforces` writes how much
of each row above that runtime's kernel holds, and `check_confine.py`
holds it to be at least the package's everywhere, with a reason on every
cell that differs. These are all of them.


| Budget item | System | The package | Through sabline-rt | Why it differs |
|---|---|---|---|---|
| no `fs` granted | windows | partly | yes | windows: the run's own process is started inside an AppContainer with an ACE for nothing but the files it reads, so a read or a write of anything of the user's is refused by the kernel and not only a write |
| `fs:read:DIR` | windows | no | yes | windows: the container is given one ACE for DIR, resolved, and one for each file the run itself reads; a read of anything else of the user's is refused |
| `fs:write:DIR` | windows | no | yes | windows: the container is given an ACE for DIR that carries write and delete, and the integrity level is not lowered, because the ACE is what holds the write |
| no `net` granted | windows | no | yes | windows: the container is made with no capability, so a socket to anything outside the machine is refused with WSAEACCES |
| `net:HOST`, `net:HOST:PORT` | windows | no | partly | windows: the container is made with internetClient, which admits every host, so the host is held by the language alone, as on Linux and macOS |
| `ffi:MODULE` under `--confine strict` | windows | partly | yes | windows: under strict the policy is the budget's own grants, and the container holds a module's own calls - native code, ctypes - as it holds the runtime's |

A container is **left off** for a run whose budget it would refuse
something the budget allows, and the receipt's `confinement_reason` says
which: a budget granting a **loopback host**, since Windows isolates a
container from the loopback address unless an administrator exempts it;
and a budget that restricts **neither reads nor writes**, since a
container reaches only what it is given an ACE for. Such a run gets the
table above, as it did before 9.0. A budget that grants *any* host keeps
its container: it does not say it needs the loopback address, which is
then the one address the run itself cannot reach - its own network calls
are made by the process that started it, which can.

What the interpreter itself must read is allowed beside the grants, on
Linux by name: Python's own installation and every directory it imports
from, the `sabline` package and the standard library beside it, the
system's shared libraries, `/dev/null`, `/dev/urandom` and the `/proc` and
`/sys` entries Python asks for, the time zone data, the files the program
was read from, a private temporary directory - and, under a `net` grant
only, the resolver's configuration and the TLS roots. `@N` counts stay in
the language.

A granted `ffi` module widens the OS policy to what that module needs,
named per module (`FFI_WIDENS`). A module that is not in this table widens
to nothing enforced - what it needs is not known, and a run that worked
before 8.4 is not refused - and the audit's `confinement.widened_by` names
every module that widened the policy and to what.

| A granted module | widens the OS policy to |
|---|---|
| `abc`, `array`, `ast`, `base64`, `binascii`, `bisect`, `calendar`, `cmath`, `collections`, `colorsys`, `copy`, `csv`, `dataclasses`, `datetime`, `decimal`, `difflib`, `email`, `enum`, `fnmatch`, `fractions`, `functools`, `gc`, `hashlib`, `heapq`, `hmac`, `html`, `ipaddress`, `itertools`, `json`, `keyword`, `math`, `numbers`, `operator`, `pprint`, `random`, `re`, `reprlib`, `secrets`, `shlex`, `statistics`, `string`, `struct`, `textwrap`, `threading`, `time`, `tomllib`, `typing`, `unicodedata`, `uuid`, `zlib`, `zoneinfo` | nothing |
| `bz2`, `codecs`, `configparser`, `dbm`, `fileinput`, `glob`, `gzip`, `io`, `lzma`, `pathlib`, `shutil`, `sqlite3`, `tarfile`, `tempfile`, `xml`, `zipfile` | any path |
| `ftplib`, `http`, `imaplib`, `poplib`, `select`, `selectors`, `smtplib`, `socket`, `ssl`, `urllib`, `xmlrpc` | any host |
| `aiohttp`, `httpx`, `logging`, `requests`, `urllib3` | any path and any host |
| `asyncio`, `builtins`, `code`, `concurrent`, `ctypes`, `importlib`, `multiprocessing`, `nt`, `os`, `pdb`, `pickle`, `pkgutil`, `platform`, `posix`, `pty`, `runpy`, `shelve`, `signal`, `site`, `subprocess`, `sys`, `venv`, `webbrowser`, `winreg`, `zipimport` | nothing enforced |

The level is what was applied and held, not what was asked for. **full**:
every file, network and process limit of this run's budget is held by the
kernel. **partial**: some are, and `confinement_reason` names each that is
not. **none**: nothing is - `--no-confine`, a module that widens to nothing
enforced, a system that offers nothing, or a run that is exempt:

| Not confined | Why |
|---|---|
| `sabline.run()` with no `timeout` and no `max_memory_mb` | it runs in the caller's process, which Sabline must not confine: Landlock, seccomp, a sandbox profile and a lowered token cannot be taken off again. Pass a limit, or use a Pool. |
| the REPL, `sabline test`, `sabline bench` | they run many programs in one process, each read after the last; a policy applied for the first would hold the rest |
| a `Pool` made without `import_root`, on reads | its workers compile each program they are sent, and an import may name any .vel file the process can read, so reads are not held and the level is partial; writes, the network and processes are held |
| compiling, proving and native code generation | done before the policy is applied in a single run, since imports are read from wherever they are and Z3 and LLVM load their libraries; the program's first statement runs after it |

