"""What the library returns: Problem, CheckResult, AuditResult, RunResult.
"""
from typing import Any



AUDIT_SCHEMA = "velaris.audit/1"     # the shape of audit().as_dict()


class Problem:
    """One thing wrong, in a form a tool can act on."""

    __slots__ = ("code", "message", "line", "file", "fixes")

    def __init__(self, code: str, message: str, line: int | None,
                 file: str | None,
                 fixes: list[str] | None) -> None:
        self.code, self.message = code, message
        self.line, self.file, self.fixes = line, file, list(fixes or [])

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message,
                "line": self.line, "file": self.file, "fixes": self.fixes}

    def __repr__(self) -> str:
        return f"[{self.code}] line {self.line}: {self.message}"


class CheckResult:
    __slots__ = ("ok", "problems", "proven", "runtime_checked")

    def __init__(self, ok: bool, problems: list[Problem], proven: list[str],
                 runtime_checked: list[str]) -> None:
        self.ok = ok
        self.problems = problems
        self.proven = proven                  # names proven before running
        self.runtime_checked = runtime_checked

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok,
                "problems": [p.as_dict() for p in self.problems],
                "proven": list(self.proven),
                "runtime_checked": list(self.runtime_checked)}


class AuditResult:
    """What a program can touch, promise and fail at - before running."""

    __slots__ = ("schema", "velaris_version", "ok", "problems", "effects",
                 "functions", "proven_share", "safe_command", "warnings",
                 "ffi_modules", "loops_unshown", "contract_coverage",
                 "fs_paths", "net_hosts", "ffi_any", "counts", "prover",
                 "secrets", "ffi_native", "confinement", "tools")
    # each is what its maker passed (None for one it did not pass)
    schema: str
    velaris_version: str
    ok: bool
    problems: list[Problem]
    effects: list[str]
    functions: list[dict[str, Any]]
    proven_share: float | None
    safe_command: str
    warnings: list[str]
    ffi_modules: list[str]
    loops_unshown: int
    contract_coverage: list[str]
    fs_paths: dict[str, Any]
    net_hosts: dict[str, Any]
    ffi_any: bool
    counts: dict[str, int | None] | None
    prover: bool
    secrets: dict[str, Any] | None
    ffi_native: dict[str, str]
    confinement: dict[str, Any] | None
    tools: dict[str, Any] | None       # 8.5: the tools its calls name

    def __init__(self, **kw: Any) -> None:
        for k in self.__slots__:
            setattr(self, k, kw.get(k))

    def as_dict(self) -> dict[str, Any]:
        out = {k: getattr(self, k) for k in self.__slots__}
        out["problems"] = [p.as_dict() if hasattr(p, "as_dict") else p
                           for p in (out.get("problems") or [])]
        return out


class RunResult:
    """What a run did. `effects_used` (3.4) maps each effect to how many
    builtin calls the budget let through - what the program actually
    performed, as the runtime saw it. It is {} when nothing ran and None
    when the worker that ran it was killed before it could say (the
    timeout, the memory cap). What a granted ffi module does inside
    Python is not seen: it counts as ffi calls, nothing more.

    `receipt` (8.1) is the run's velaris.receipt/1 record, an in-toto
    Statement bound to the same subjects `attest` names: the budget, every
    refusal and declassification, the run's parameters, how it ended and
    how long it took - and no value the program handled."""

    __slots__ = ("ok", "output", "logs", "problems", "refused_effect",
                 "exit_code", "timed_out", "out_of_memory", "effects_used",
                 "receipt")

    def __init__(self, ok: bool, output: str, logs: str,
                 problems: list[Problem], refused_effect: str | None,
                 exit_code: int, timed_out: bool = False,
                 out_of_memory: bool = False,
                 effects_used: dict[str, int] | None = None,
                 receipt: dict[str, Any] | None = None) -> None:
        self.ok, self.output, self.logs = ok, output, logs
        self.problems, self.refused_effect = problems, refused_effect
        self.exit_code = exit_code
        self.timed_out = timed_out
        self.out_of_memory = out_of_memory
        self.effects_used = effects_used
        self.receipt = receipt

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "output": self.output, "logs": self.logs,
                "problems": [p.as_dict() for p in self.problems],
                "refused_effect": self.refused_effect,
                "exit_code": self.exit_code,
                "timed_out": self.timed_out,
                "out_of_memory": self.out_of_memory,
                "effects_used": self.effects_used,
                "receipt": self.receipt}


def _problem_of(d: Any) -> Problem:
    """A Problem back from its as_dict() form, as a worker sends it."""
    d = d if isinstance(d, dict) else {}
    return Problem(d.get("code"), d.get("message"), d.get("line"),
                   d.get("file"), d.get("fixes") or [])


def _as_problem(e: object, where: str | None) -> Problem:
    return Problem(getattr(e, "code", "E000"), getattr(e, "message", str(e)),
                   getattr(e, "line", 0), getattr(e, "file", None) or where,
                   getattr(e, "fixes", []))
