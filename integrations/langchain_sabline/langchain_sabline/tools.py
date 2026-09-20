import json
from typing import List, Optional, Type, Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

import sabline


class _SourceInput(BaseModel):
    source: str = Field(..., description="the Sabline program")


class _RunInput(BaseModel):
    source: str = Field(..., description="the Sabline program to run")
    stdin: str = Field("", description="text to feed the program")
    args: List[str] = Field(default_factory=list,
                            description="command-line arguments")


class SablineCardTool(BaseTool):  # type: ignore[misc]  # langchain_core is not installed by the lint job
    name: str = "sabline_card"
    description: str = (
        "The Sabline language in about 4,600 words. Read it before "
        "writing Sabline.")

    def _run(self, *_: Any, **__: Any) -> str:
        return sabline.card()


class SablineAuditTool(BaseTool):  # type: ignore[misc]  # langchain_core is not installed by the lint job
    name: str = "sabline_audit"
    description: str = (
        "Audit a Sabline program before running it: which effects it can "
        "perform, what each function promises and whether that was "
        "proven, what can fail, and the command to run it safely. "
        "Returns sabline.audit/1 JSON.")
    args_schema: Type[BaseModel] = _SourceInput

    def _run(self, source: str) -> str:
        return json.dumps(sabline.audit(source).as_dict(), indent=2)


class SablineRunTool(BaseTool):  # type: ignore[misc]  # langchain_core is not installed by the lint job
    name: str = "sabline_run"
    description: str = (
        "Run a Sabline program in a sandbox. Effects outside the budget "
        "this tool was built with are refused while it runs, whatever "
        "the source claims. Returns output, or the problem that stopped "
        "it.")
    args_schema: Type[BaseModel] = _RunInput
    allow: List[str] = Field(default_factory=lambda: ["io"])

    def _run(self, source: str, stdin: str = "",
             args: Optional[List[str]] = None) -> str:
        result = sabline.run(source, allow=set(self.allow),
                             stdin=stdin, args=args or [])
        if result.ok:
            return result.output or "(the program printed nothing)"
        lines = []
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
