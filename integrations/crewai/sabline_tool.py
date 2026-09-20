"""Sabline tools for CrewAI: run agent-written code in a box.

An agent that writes code needs somewhere safe to run it. These tools
compile a Sabline program, report what it can touch, and run it under
an effect budget the crew's author chooses - not the agent. A program
granted only "io" cannot read files, reach the network or call Python,
whatever its source claims, and a refusal cannot be caught by the
program.

    from sabline_tool import SablineAuditTool, SablineRunTool

    agent = Agent(
        role="Data analyst",
        tools=[SablineAuditTool(), SablineRunTool(allow=["io"])],
        ...
    )

Install the compiler once: pip install sabline-lang z3-solver
The z3-solver is optional; without it promises are checked while
running rather than proven beforehand, and the audit says so.
"""
from typing import List, Optional, Type, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

import sabline


class _SourceInput(BaseModel):
    source: str = Field(..., description="the Sabline program to inspect")


class _RunInput(BaseModel):
    source: str = Field(..., description="the Sabline program to run")
    stdin: str = Field("", description="text to feed the program")
    args: List[str] = Field(default_factory=list,
                            description="command-line arguments")


class SablineCardTool(BaseTool):  # type: ignore[misc]  # crewai is not installed by the lint job
    """The Sabline language, small enough to read before writing it."""
    name: str = "sabline_card"
    description: str = (
        "Read the Sabline language card (about 4,600 words) before "
        "writing Sabline. It covers syntax, the rules models get wrong, "
        "every builtin with its effects, and the error table.")

    def _run(self) -> str:
        return sabline.card()


class SablineAuditTool(BaseTool):  # type: ignore[misc]  # crewai is not installed by the lint job
    """What a program can touch, promise and fail at - before running."""
    name: str = "sabline_audit"
    description: str = (
        "Audit a Sabline program before running it: which effects it "
        "can perform (io, env, fs, net, clock, rand, ffi, declassify), "
        "whether it holds a secret and whether it ever lets one out, "
        "what each function "
        "promises and whether that was proven before running, what can "
        "fail, and the command to run it safely. Returns JSON in the "
        "sabline.audit/1 format.")
    args_schema: Type[BaseModel] = _SourceInput

    def _run(self, source: str) -> str:
        import json
        return json.dumps(sabline.audit(source).as_dict(), indent=2)


class SablineRunTool(BaseTool):  # type: ignore[misc]  # crewai is not installed by the lint job
    """Run a program under an effect budget the crew's author chose."""
    name: str = "sabline_run"
    description: str = (
        "Run a Sabline program in a sandbox. Effects outside the budget "
        "this tool was created with are refused while the program runs, "
        "whatever the source claims, and a refusal cannot be caught. "
        "Returns the program's output, or the problem that stopped it.")
    args_schema: Type[BaseModel] = _RunInput
    allow: List[str] = Field(default_factory=lambda: ["io"])
    timeout: float = Field(30.0, description="seconds before it is stopped")
    max_memory_mb: int = Field(512, description="memory cap in MB")

    def __init__(self, allow: Optional[List[str]] = None,
                 timeout: float = 30.0, max_memory_mb: int = 512, **kw: Any) -> None:
        super().__init__(**kw)
        if allow is not None:
            self.allow = list(allow)
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb

    def _run(self, source: str, stdin: str = "",
             args: Optional[List[str]] = None) -> str:
        # a separate, killable process: a program that never ends or
        # eats memory is stopped, and the crew's worker survives it
        result = sabline.run(source, allow=set(self.allow),
                             stdin=stdin, args=args or [],
                             timeout=self.timeout,
                             max_memory_mb=self.max_memory_mb)
        if result.ok:
            return result.output or "(the program printed nothing)"
        lines = []
        if result.timed_out:
            lines.append(f"STOPPED: the program ran longer than "
                         f"{self.timeout} seconds.")
        elif result.out_of_memory:
            lines.append(f"STOPPED: the program used more than "
                         f"{self.max_memory_mb} MB.")
        if result.refused_effect:
            lines.append(
                f"REFUSED: the program tried to use "
                f"'{result.refused_effect}', which this tool does not "
                f"allow (it allows: {', '.join(sorted(self.allow))}).")
        for p in result.problems:
            lines.append(f"line {p.line}: [{p.code}] {p.message}")
            for fix in (p.fixes or [])[:2]:
                lines.append(f"    fix: {fix}")
        if result.output:
            lines.append("output before it stopped:")
            lines.append(result.output)
        return "\n".join(lines) or "the program failed without a message"
