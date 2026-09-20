"""What a receipt records while a program runs: refusals, declassifications,
where it stopped.
"""
import os
import re

from . import state as _state
from .predicates import RECEIPT_PREDICATE_TYPE as RECEIPT_PREDICATE_TYPE
from .tables import ALL_EFFECTS
from typing import Any

# ---------------------------------------------------------------------------
# 19b. RECEIPTS - what one run did, bound to the bytes attest names
#
#     An attestation says what a program may do, before it runs. A receipt
#     says what one run of it did: the budget it was given, every refusal,
#     every declassification with the reason written for it, the parameters
#     it ran under, how it ended and how long it took. Its subjects are the
#     files `velaris attest` names, by the same digests, so an audit and a
#     receipt of one program are the before and the after of the same
#     bytes. It is an in-toto Statement of the receipt/v1 predicate
#     (velaris-spec 8.7), and it is signed the way an attestation is.
#
#     It holds no value the program handled. A refusal is its code, its
#     effect and its line - not the path, host or module the program named,
#     which could have been built from a declassified secret; a
#     declassification is the reason written in the source (a literal,
#     E561); the output, the input, the arguments and every message are
#     left out. What the program chose that is not a value still shows - its
#     exit status, which lines it reached, how long it ran - and
#     THREAT_MODEL.md says so.
# ---------------------------------------------------------------------------


RECEIPT_SCHEMA = "velaris.receipt/1"
# the type is velaris/predicates.py's, at velaris-lang.dev from 8.3
RECEIPT_SPEC = "velaris-spec 0.12.0"
# the refusals a receipt lists and the doors log: the budget's, and the
# read ceiling's
REFUSAL_CODES = ("E310", "E311", "E313", "E314", "E315", "E316", "E317",
                 "E318", "E320", "E321", "E322", "E323")


def _utc_now_ms() -> str:
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    return (now.strftime("%Y-%m-%dT%H:%M:%S.")
            + f"{now.microsecond // 1000:03d}Z")


def _entry_name(path: str | None, name: str | None = None) -> str:
    """How a receipt names the program it ran: the path it was given,
    '/'-separated, or <source> for text that came with no file."""
    import posixpath
    if name:
        return name
    if path is None:
        return "<source>"
    return posixpath.normpath(str(path).replace(os.sep, "/"))


def _refusal_effect(code: str, message: str) -> str | None:
    """The effect a refusal is about, as one of the effect names - never
    the path, host or module the program gave."""
    if code == "E310":
        m = re.search(r"needs the '(\w+)' effect", message or "")
        return m.group(1) if m and m.group(1) in ALL_EFFECTS else None
    if code == "E315":
        m = re.search(r" (fs|net) operation", message or "")
        return m.group(1) if m else None
    if code == "E311":
        return "ffi"
    if code in ("E313", "E316", "E318"):
        return "fs"
    if code in ("E314", "E317"):
        return "net"
    if code in ("E320", "E321", "E322", "E323"):
        return "tool"
    return None


class _RunRecorder:
    """What a receipt records about one run, while it happens.

    Each refusal and each declassification is kept once per place - its
    kind, its code or its reason, its line - with a count, so a loop that
    declassifies a million times is one entry. `emit` streams an entry the
    first time it is seen and every thousandth time after; that is what a
    pool keeps when it has to kill the worker before the run ends, and the
    counts it has then are counts of at least that many."""

    STREAM_EVERY = 1000

    def __init__(self, emit: Any = None) -> None:
        self.emit = emit
        self.subjects: list[Any] | None = None
        self.sites: dict[Any, Any] = {}
        self.stop: dict[str, Any] | None = None
        self.compiled = False
        # line -> the key fingerprints an hmac call there has named (8.5)
        self.keys_at: dict[int, set[str]] = {}
        # what each grant let through, and a tool session's ceiling record,
        # put here when the run ends (8.5)
        self.grant_uses: dict[str, int] | None = None
        self.tools: dict[str, Any] | None = None

    def close(self) -> None:
        """The run has ended: keep what the budget counted, before the
        budget that was there before is put back."""
        self.grant_uses = dict(_state.GRANT_USES)
        if _state.TOOLS is not None:
            self.tools = _state.TOOLS.ceiling_record()

    def _send(self, event: dict[Any, Any]) -> None:
        if self.emit is None:
            return
        try:
            self.emit(event)
        except Exception:                 # nobody is listening any more
            self.emit = None

    def set_subjects(self, subjects: list[Any]) -> None:
        self.subjects = subjects
        self._send({"kind": "subjects", "subjects": subjects})

    def note(self, kind: str, **fields: Any) -> None:
        key = (kind,) + tuple(sorted(fields.items()))
        entry = self.sites.get(key)
        if entry is None:
            entry = self.sites[key] = dict(fields, kind=kind, times=0)
        entry["times"] += 1
        if entry["times"] == 1 or entry["times"] % self.STREAM_EVERY == 0:
            self._send(dict(entry))

    def take(self, event: dict[Any, Any]) -> None:
        """An entry a worker streamed, kept by its parent."""
        kind = event.get("kind")
        if kind == "subjects":
            if isinstance(event.get("subjects"), list):
                self.subjects = event["subjects"]
            return
        if kind not in ("refusal", "declassify", "tool"):
            return
        fields = {k: v for k, v in event.items()
                  if k not in ("kind", "times")}
        try:
            key = (kind,) + tuple(sorted(fields.items()))
            entry = self.sites.setdefault(
                key, dict(fields, kind=kind, times=0))
        except TypeError:                 # not a shape this file sends
            return
        try:
            entry["times"] = max(entry["times"],
                                 int(event.get("times") or 1))
        except (TypeError, ValueError):
            entry["times"] = max(entry["times"], 1)


def _note_error(e: Any) -> None:
    """A VelarisError stopped the run: what its receipt records of that."""
    rec = _state.RUN_RECORDER
    if rec is None:
        return
    code, line = getattr(e, "code", None), getattr(e, "line", 0) or 0
    rec.stop = {"code": code, "line": line}
    if code in REFUSAL_CODES:
        rec.note("refusal", code=code, line=line, stopped=True,
                 effect=_refusal_effect(code, getattr(e, "message", "")))


def _note_stop(code: str, line: int) -> None:
    if _state.RUN_RECORDER is not None:
        _state.RUN_RECORDER.stop = {"code": code, "line": line}


def _note_redirect(line: int) -> None:
    """A redirect the net grants refused: the one refusal a program is
    told about as a failure, and may carry on from."""
    if _state.RUN_RECORDER is not None:
        _state.RUN_RECORDER.note("refusal", code=None, effect="net", line=line,
                          stopped=False)
