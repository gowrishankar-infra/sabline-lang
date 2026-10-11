"""The organisation ceiling (9.0, M3; decisions/0007, item 32c): a file
whoever administers a machine installs, which caps what any budget on it
may grant - at every entry point: the command line, the library, a pool,
the HTTP door, the MCP server, `sabline eval`, `sabline test` and
`sabline replay`, in either runtime.

**The file** is sabline.ceiling/1, a JSON object:

    {"schema": "sabline.ceiling/1",
     "allow": "io,fs:read:/srv/data,net:*.corp.com:443@100",
     "description": "what this machine's runs may be given"}

`allow` is a budget, as `--allow` writes it (SPEC.md 7.1): the most a run's
budget may grant, effect by effect, module by module, path, host, tool and
count. `all` caps nothing. Write its paths whole: a relative one is
resolved where the run is.

**Where it is**: one place for the system (`system_path`), and the file
SABLINE_CEILING names, when it names one - held as well as the system's,
never instead of it. A ceiling can only narrow, so a second one cannot
widen the first, and nothing a person running a program sets in the
environment can take the system's away.

**What it does**: before a run is given its budget, every ceiling must
cover the whole of it - each grant, at each level, inside a grant of the
ceiling (`Budget.gap`, the rule `--max-allow` holds the doors to). One
that does not is E325, before the program is read, naming the file, the
first grant of the budget outside it and what the ceiling allows. So what
a run may do is inside every ceiling and its budget at once, and since
each is asked the same question, no order of asking gives anything else.
A ceiling that cannot be read - no file where SABLINE_CEILING points, not
UTF-8, not JSON, not a ceiling, an `allow` that is not a budget - is held as
one that allows nothing: every run is refused, E325, saying what is wrong
with it, because a ceiling that cannot be read cannot be held.

**Where it is named**, so that a refusal is never for a reason found in
neither the command line nor the source: in the refusal; in the receipt's
`run_parameters.ceilings`, each with its path, the sha256 of its bytes and
what it allows; in `sabline audit`; and by `sabline ceiling`, which shows
what is installed without anyone having to find the file.
"""
import hashlib
import json
import os
import sys
from typing import Any

from .budget import Budget, BudgetError, expand_allow
from .errors import SablineError

CEILING_SCHEMA = "sabline.ceiling/1"
# Named `*_ENV`, as every variable sabline/*.py reads is, so that
# check_self_budget.py finds it and varies it: it can only add a ceiling.
CEILING_ENV = "SABLINE_CEILING"
# what the file may hold
FIELDS = ("schema", "allow", "description")
# the largest file read as one: a ceiling is a line of budget
MOST_BYTES = 1 << 20

_PROGRAM_DATA = "{62AB5D82-FDC1-4DC3-A9DD-070D1D495D97}"    # FOLDERID_ProgramData


def _program_data() -> str:
    """Windows' ProgramData folder, as the system knows it - not as the
    environment says, which the person running a program can change."""
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]
        guid = GUID()
        ole32 = ctypes.WinDLL("ole32")       # type: ignore[attr-defined]
        shell32 = ctypes.WinDLL("shell32")   # type: ignore[attr-defined]
        if ole32.CLSIDFromString(ctypes.c_wchar_p(_PROGRAM_DATA),
                                 ctypes.byref(guid)) != 0:
            raise OSError("no GUID")
        found = ctypes.c_wchar_p()
        if shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None,
                                        ctypes.byref(found)) != 0:
            raise OSError("no folder")
        try:
            return str(found.value)
        finally:
            ole32.CoTaskMemFree(found)
    except (OSError, AttributeError, ValueError):
        return "C:\\ProgramData"


def system_path() -> str:
    """Where this system's ceiling is installed, if it is."""
    if os.name == "nt":
        return os.path.join(_program_data(), "Sabline", "ceiling.json")
    if sys.platform == "darwin":
        return "/Library/Application Support/Sabline/ceiling.json"
    return "/etc/sabline/ceiling.json"


class Ceiling:
    """One ceiling, as read: where it came from, the sha256 of its bytes,
    and the budget it allows - or `broken`, why it is not one."""

    __slots__ = ("path", "text", "sha256", "budget", "broken")

    def __init__(self, path: str, text: str | None, sha256: str | None,
                 budget: Budget | None, broken: str | None) -> None:
        self.path, self.text, self.sha256 = path, text, sha256
        self.budget, self.broken = budget, broken

    def allows(self) -> str | None:
        """What it allows, as a budget writes it; None for one broken."""
        return None if self.budget is None else self.budget.spec()

    def receipt(self) -> dict[str, Any]:
        """What a receipt says of it."""
        return {"path": self.path, "sha256": self.sha256,
                "allow": self.allows()}


def read(path: str, text: str) -> Ceiling:
    """A ceiling from its text: the text the file at `path` holds. Both
    runtimes read a ceiling from this text, so a request to sabline-rt and
    a line of the gate's list carry the text, not the file."""
    digest = hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest()

    def broken(why: str) -> Ceiling:
        return Ceiling(path, text, digest, None, why)
    try:
        doc = json.loads(text)
    except ValueError as e:
        return broken(f"it is not JSON: {e}")
    if not isinstance(doc, dict):
        return broken("it is not a JSON object")
    if doc.get("schema") != CEILING_SCHEMA:
        return broken(f'it does not say "schema": "{CEILING_SCHEMA}"')
    unknown = sorted(str(k) for k in doc if k not in FIELDS)
    if unknown:
        return broken(f"'{unknown[0]}' is not a field of a ceiling (it "
                      f"holds {', '.join(FIELDS)})")
    allow = doc.get("allow")
    if not isinstance(allow, str):
        return broken('its "allow" is not a budget written as text, as '
                      '"io,fs:read:/srv/data"')
    try:
        budget = Budget.parse(expand_allow(allow))
    except BudgetError as e:
        return broken(f'its "allow" is not a budget: {e}')
    return Ceiling(path, text, digest, budget, None)


def read_file(path: str) -> Ceiling:
    """The ceiling at `path`: read, or broken when it cannot be."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(MOST_BYTES + 1)
    except FileNotFoundError:
        return Ceiling(path, None, None, None, "there is no file there")
    except OSError as e:
        return Ceiling(path, None, None, None,
                       f"it cannot be read: {e.strerror or e}")
    if len(raw) > MOST_BYTES:
        return Ceiling(path, None, hashlib.sha256(raw).hexdigest(), None,
                       f"it is over {MOST_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return Ceiling(path, None, hashlib.sha256(raw).hexdigest(), None,
                       "it is not UTF-8 text")
    return read(path, text)


def installed() -> list[Ceiling]:
    """Every ceiling this machine holds a run to, in the order they are
    asked: the system's, where one is installed, and the one
    SABLINE_CEILING names, where it names one."""
    out = []
    system = system_path()
    if os.path.exists(system):
        out.append(read_file(system))
    named = os.environ.get(CEILING_ENV)
    if named:
        out.append(read_file(named))
    return out


def refusal(ceilings: list[Ceiling], budget: Budget) -> SablineError | None:
    """E325 for the first ceiling that is broken or does not cover all of
    `budget`, or None when every one does."""
    for c in ceilings:
        if c.budget is None:
            return SablineError("E325",
                f"the organisation ceiling {c.path} is not one, so no run on "
                f"this machine can be held to it: {c.broken}", 0,
                fixes=[f"mend it: a ceiling is a JSON object, "
                       f'{{"schema": "{CEILING_SCHEMA}", "allow": '
                       f'"io,fs:read:/srv/data"}}',
                       "until it is mended every run here is refused: a "
                       "ceiling that cannot be read cannot be held",
                       "sabline ceiling shows every ceiling installed here"])
        gap = c.budget.gap(budget)
        if gap is not None:
            effect, why = gap
            allows = c.budget.spec()
            return SablineError("E325",
                f"the budget's '{effect}' grant goes past the organisation "
                f"ceiling {c.path}: {why} (it allows: {allows or 'nothing'})",
                0, fixes=[(f"narrow the budget to fit inside it, as --allow "
                           f"{allows}") if allows else
                          "the ceiling allows nothing, so no budget fits "
                          "inside it",
                          f"or ask whoever administers this machine to widen "
                          f"{c.path}: nothing on the command line or in the "
                          f"program can",
                          "sabline ceiling shows every ceiling installed here"])
    return None


def hold(budget: Budget, ceilings: list[Ceiling] | None = None) -> list[Ceiling]:
    """Hold a run about to be given `budget` to the ceilings - this
    machine's, unless others are given (the gate's list) - before it is
    given anything: the ceilings, named in the receipt of the run being
    recorded; E325 raised for one that does not cover it."""
    from . import state as _state
    found = installed() if ceilings is None else ceilings
    recorder = _state.RUN_RECORDER
    if recorder is not None and hasattr(recorder, "ceilings"):
        recorder.ceilings = for_receipt(found)
    refused = refusal(found, budget)
    if refused is not None:
        raise refused
    return found


def for_receipt(ceilings: list[Ceiling]) -> list[dict[str, Any]]:
    """What a receipt's run_parameters say of the ceilings a run was held
    to."""
    return [c.receipt() for c in ceilings]


def for_request(ceilings: list[Ceiling]) -> list[dict[str, Any]]:
    """The ceilings as a request to sabline-rt and a line of the gate's list
    carry them: the path each was read from, and its text."""
    return [{"path": c.path, "text": c.text} for c in ceilings]


def given(lines: Any) -> list[Ceiling]:
    """The ceilings a line of the gate's list or a request names, read from
    the text each carries: [{"path": ..., "text": ...}]."""
    return [read(str(c.get("path")), str(c.get("text")))
            for c in lines or [] if isinstance(c, dict)]


def ceiling_main(argv: list[str]) -> int:
    """`sabline ceiling [--json]`: every ceiling this machine holds a run
    to, and what each allows - or that there is none."""
    found = installed()
    if "--json" in argv:
        print(json.dumps({"system_path": system_path(),
                          "ceilings": [dict(c.receipt(), broken=c.broken)
                                       for c in found]}, indent=2))
        return 0 if all(c.broken is None for c in found) else 1
    if not found:
        print(f"no organisation ceiling: none is installed at "
              f"{system_path()}, and {CEILING_ENV} names none")
        return 0
    for c in found:
        print(f"ceiling  {c.path}")
        if c.broken is not None:
            print(f"  BROKEN: {c.broken}")
            print("  every run on this machine is refused until it is mended")
        else:
            print(f"  allows: {c.allows() or 'nothing'}")
        if c.sha256:
            print(f"  sha256: {c.sha256}")
    return 0 if all(c.broken is None for c in found) else 1
