"""velaris.receipt/1: what one run did, as an in-toto Statement.
"""
import os

from . import state as _state
from .version import VERSION
from .recorder import RECEIPT_PREDICATE_TYPE, RECEIPT_SCHEMA, RECEIPT_SPEC
from .budget import _frozen_epoch
from .findings import REPOSITORY
from .attestation import INTOTO_STATEMENT_TYPE, _sha256_of, _subject_name
from typing import Any


def _receipt_subjects(entry: str, name: str, entry_bytes: bytes,
                      loaded: list[Any]) -> list[Any]:
    """A receipt's subjects, as attest_statement makes them: the program, by
    the sha256 of the text that ran, then each file it read, by the sha256
    of its bytes, named in the program's terms or as <stdlib>/NAME."""
    import hashlib
    subjects = [{"name": name, "digest": {
        "sha256": hashlib.sha256(entry_bytes).hexdigest()}}]
    seen = {os.path.abspath(entry)}
    for p in loaded:
        if os.path.abspath(p) in seen:
            continue
        seen.add(os.path.abspath(p))
        try:
            digest = _sha256_of(p)
        except OSError:
            continue
        subjects.append({"name": _subject_name(p, entry, name),
                         "digest": {"sha256": digest}})
    return subjects


def _run_parameters(seed: Any, freeze_time: Any, timeout: Any, max_memory_mb: Any) -> dict[str, Any]:
    """What a run was given besides its budget, as its receipt says it.
    ValueError for a freeze_time that is not an instant."""
    import datetime
    frozen = _frozen_epoch(freeze_time)
    return {"seed": None if seed is None else int(seed),
            "freeze_time": None if frozen is None else
            datetime.datetime.fromtimestamp(frozen, datetime.timezone.utc)
            .strftime("%Y-%m-%dT%H:%M:%SZ"),
            "timeout": timeout,
            "max_memory_mb": (None if max_memory_mb is None
                              else int(max_memory_mb)),
            "max_read_bytes": _state.MAX_READ_BYTES,
            "confinement": "none"}


def receipt_statement(recorder: Any, *, name: Any, entry_bytes: Any, budget: Any, parameters: Any,
                      result: Any, started_at: Any, wall_time_ms: Any,
                      complete: bool = True) -> dict[str, Any]:
    """The in-toto Statement of one run's receipt (velaris-spec 8.7)."""
    import hashlib
    subjects = recorder.subjects or [{"name": name, "digest": {
        "sha256": hashlib.sha256(entry_bytes).hexdigest()}}]
    sites = list(recorder.sites.values())
    refusals = sorted(
        ({"code": s.get("code"), "effect": s.get("effect"),
          "line": s.get("line"), "stopped": bool(s.get("stopped")),
          "times": s.get("times", 1)}
         for s in sites if s.get("kind") == "refusal"),
        key=lambda r: (r["line"] or 0, str(r["code"]), str(r["effect"]),
                       r["stopped"]))
    declassifications = sorted(
        ({"reason": s.get("reason"), "line": s.get("line"),
          "times": s.get("times", 1)}
         for s in sites if s.get("kind") == "declassify"),
        key=lambda d: (d["line"] or 0, str(d["reason"])))
    code: str | None
    if result.timed_out:
        outcome, code = "timeout", "E610"
    elif result.out_of_memory:
        outcome, code = "out_of_memory", "E611"
    else:
        code = (recorder.stop or {}).get("code") or (
            result.problems[0].code if result.problems and not result.ok
            else None)
        if any(r["stopped"] for r in refusals):
            outcome = "refused"
        elif result.ok:
            outcome = "ok"
        elif complete and not recorder.compiled and result.problems:
            outcome = "did_not_compile"
        else:
            outcome = "failed"
    return {"_type": INTOTO_STATEMENT_TYPE,
            "subject": subjects,
            "predicateType": RECEIPT_PREDICATE_TYPE,
            "predicate": {
                "schema": RECEIPT_SCHEMA,
                "producer": {"name": "velaris-lang", "uri": REPOSITORY,
                             "version": VERSION},
                "specification": RECEIPT_SPEC,
                "startedAt": started_at,
                "wall_time_ms": round(float(wall_time_ms), 1),
                "budget": budget,
                "run_parameters": parameters,
                "effects_used": result.effects_used,
                "refusals": refusals,
                "declassifications": declassifications,
                "exit": {"status": result.exit_code, "outcome": outcome,
                         "code": code},
                "complete": bool(complete)}}
