#!/usr/bin/env python3
"""The CaMeL column's host: CaMeL's own interpreter and its own policies.

    python camel_host.py PROGRAM

CaMeL (Debenedetti et al., "Defeating Prompt Injections by Design", 2025) runs
a plan written by a privileged model in a restricted Python interpreter that
tags every value with its sources and permitted readers, and checks a
security policy before each tool call. This host runs a benchmark program as
that plan, with the reference implementation
(google-research/camel-prompt-injection, pinned in
requirements/competitors.txt): its parser, its interpreter, its STRICT
dependency mode, its capability tags and its policy engine. No model is
involved. The program is the plan.

THE TOOLS. CaMeL has no I/O of its own; a plan reaches the world only
through tools. One tool set serves the whole benchmark, as one AgentDojo
suite serves all its tasks, and a task's `needs` is not an input: CaMeL does
not narrow tools per task, it polices how data flows into them. Where CaMeL
ships an annotation or a policy for a tool of the same shape, it is used as
shipped; where it ships none, that is said, and CaMeL's own default applies.

    read_line()             the user's input (stdin). This host tags it as
                            the user's, and public: it is the request.
    read_file(path)         CaMeL's own annotation for read_file: private,
                            untrusted. A read has no side effect, so no
                            policy applies (as CaMeL treats reads).
    get_webpage(url)        CaMeL's own annotation (private, untrusted) and
                            its Slack suite's get_webpage policy: the URL
                            must be public.
    post_webpage(url, content)
                            its Slack suite's post_webpage policy: the URL
                            and the content must be public.
    write_file(path, content)
                            its workspace suite's create_file policy, which
                            is Allowed(): the content stays with the user.
    list_dir(path)          a read, like workspace's list_files: no policy.
    get_env(name)           no CaMeL analogue. A read; this host tags the
                            value private and untrusted, as read_file is.
    run_command(command)    no CaMeL analogue and no policy, so CaMeL's
                            engine denies it: "No security policy matched".
    sqrt(x), parse_json(text), shout(text)
                            pure: the host's math and JSON parser (CaMeL's
                            planner hands parsing to a quarantined model;
                            with no model, a pure tool stands in), and the
                            vendored textcase library of category 15's
                            control.

Each tool does the real thing - reads the file, sends the request, runs the
process - so the harness observes the same effects it observes for every
other tool. print() is CaMeL's: its output is recovered from the recorded
print calls, as CaMeL's own pipeline does, one line per call.

TIME. CaMeL has no time limit of its own. With --timeout S the host stops
the plan S seconds after interpretation starts - not after the process
starts: importing CaMeL and the AgentDojo suites it needs takes seconds
before the first statement runs, and that is not the plan's time.

OUTPUT. The program's printed lines on stdout. An error - an interpreter
refusal, a policy denial, an exception - on stderr as
`camel-error: LINE: TYPE: MESSAGE`, exit 1; past --timeout, exit 3.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import threading
import urllib.request
from collections.abc import Iterable, Mapping
from typing import Any

import agentdojo.task_suite  # noqa: F401  (first, as CaMeL's own entry points
#                             do: importing a suite module first is a cycle)
from agentdojo.functions_runtime import FunctionsRuntime
from camel.capabilities import Capabilities, readers, sources
from camel.interpreter import interpreter, namespace as ns, result
from camel.interpreter.value import CaMeLValue
from camel.pipeline_elements.agentdojo_function import (
    AgentDojoFunction,
    make_agentdojo_namespace,
)
from camel.pipeline_elements.security_policies.slack import (
    SlackSecurityPolicyEngine,
)
from camel.pipeline_elements.security_policies.workspace import (
    WorkspaceSecurityPolicyEngine,
)
from camel.security_policy import (
    NO_SIDE_EFFECT_TOOLS,
    SecurityPolicyEngine,
    SecurityPolicyResult,
)


# ---- the tools --------------------------------------------------------------

def read_line() -> str:
    """Reads one line of the user's input.

    :return: the line, without its newline.
    """
    return sys.stdin.readline().rstrip("\r\n")


def read_file(path: str) -> str:
    """Reads a file.

    :param path: the file to read.
    """
    with open(path, encoding="utf-8") as f:
        return f.read()


def get_webpage(url: str) -> str:
    """Fetches a URL.

    :param url: the URL to fetch.
    """
    with urllib.request.urlopen(url, timeout=10) as r:
        return str(r.read().decode("utf-8", "replace"))


def post_webpage(url: str, content: str) -> str:
    """Posts content to a URL.

    :param url: the URL to post to.
    :param content: the body to send.
    """
    with urllib.request.urlopen(url, data=content.encode(), timeout=10) as r:
        return str(r.read().decode("utf-8", "replace"))


def write_file(path: str, content: str) -> None:
    """Writes a file.

    :param path: the file to write.
    :param content: the text to write.
    """
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def list_dir(path: str) -> list[str]:
    """Lists a directory.

    :param path: the directory to list.
    """
    return sorted(os.listdir(path))


def get_env(name: str) -> str:
    """Reads an environment variable.

    :param name: the variable's name.
    """
    return os.environ.get(name, "")


def run_command(command: str) -> str:
    """Runs a shell command.

    :param command: the command line.
    """
    return subprocess.getoutput(command)


def sqrt(x: float) -> float:
    """The square root of a number.

    :param x: the number.
    """
    return math.sqrt(x)


def parse_json(text: str) -> Any:
    """Parses a JSON document.

    :param text: the document.
    """
    return json.loads(text)


def shout(text: str) -> str:
    """textcase.shout, from the textcase library the project vendors.

    :param text: the text.
    """
    return text.upper()


TOOLS = [read_line, read_file, get_webpage, post_webpage, write_file,
         list_dir, get_env, run_command, sqrt, parse_json, shout]

# tools with no side effect: CaMeL runs them without consulting a policy
READS = {"read_line", "read_file", "list_dir", "get_env", "sqrt", "parse_json",
         "shout"}


# ---- the capability tags this host adds -------------------------------------
#
# Every other tool's result is tagged by CaMeL's own _get_metadata_for_ad,
# unchanged (read_file and get_webpage: private and untrusted; the rest: the
# tool as source, public).

def _private_untrusted(tool: str) -> Capabilities:
    return Capabilities(frozenset({sources.Tool(tool, frozenset())}),
                        frozenset())


HOST_TAGS = {
    "read_line": Capabilities(frozenset({sources.SourceEnum.User}),
                              readers.Public()),
    "get_env": _private_untrusted("get_env"),
}


class BenchmarkTool(AgentDojoFunction):  # type: ignore[misc]  # CaMeL ships no types
    def wrap_output(self, value: Any, args: Any, kwargs: Any,
                    namespace: ns.Namespace) -> Any:
        wrapped = super().wrap_output(value, args, kwargs, namespace)
        tag = HOST_TAGS.get(self.name().raw)
        return wrapped.new_with_metadata(tag) if tag is not None else wrapped


# ---- the policies: CaMeL's, as shipped --------------------------------------

def _get_webpage(tool: str, kwargs: Mapping[str, CaMeLValue]) -> SecurityPolicyResult:
    return SlackSecurityPolicyEngine.get_webpage_policy(
        None, tool, kwargs)  # the policy reads no state: no engine is needed


def _post_webpage(tool: str, kwargs: Mapping[str, CaMeLValue]) -> SecurityPolicyResult:
    return SlackSecurityPolicyEngine.post_webpage_policy(
        None, tool, kwargs)


def _write_file(tool: str, kwargs: Mapping[str, CaMeLValue]) -> SecurityPolicyResult:
    return WorkspaceSecurityPolicyEngine.create_file_policy(
        None, tool, kwargs)


class BenchmarkPolicies(SecurityPolicyEngine):  # type: ignore[misc]
    """CaMeL's engine (check_policy is inherited unchanged): a tool with no
    side effect runs; a side-effecting call that depends on a private value
    is denied; otherwise the first matching policy decides; no match is a
    denial."""

    def __init__(self) -> None:
        self.policies = [("get_webpage", _get_webpage),
                         ("post_webpage", _post_webpage),
                         ("write_file", _write_file)]
        self.no_side_effect_tools = set(NO_SIDE_EFFECT_TOOLS) | READS


# ---- run --------------------------------------------------------------------

def _message(exc: BaseException) -> str:
    """An exception's message on one line. A KeyError's argument is a CaMeL
    value whose repr holds its whole capability tag (sets, in an order that
    moves with the hash seed); the key itself is what the reader needs."""
    if isinstance(exc, KeyError) and exc.args:
        return repr(getattr(exc.args[0], "raw", exc.args[0]))
    return " ".join(str(exc).split())


def _line(error: Any) -> int:
    nodes: Iterable[Any] = getattr(error, "nodes", ()) or ()
    for node in nodes:
        line = getattr(node, "lineno", None)
        if isinstance(line, int) and line > 0:
            return line
    return 0


def main(argv: list[str]) -> int:
    timeout: float | None = None
    if len(argv) == 3 and argv[1] == "--timeout":
        timeout = float(argv[2])
    elif len(argv) != 1:
        print("usage: camel_host.py PROGRAM [--timeout SECONDS]",
              file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as f:
        code = f.read()
    runtime = FunctionsRuntime([])
    for tool in TOOLS:
        runtime.register_function(tool)
    namespace = ns.Namespace.with_builtins()
    tools = make_agentdojo_namespace(namespace, runtime, None)
    for name in [t.__name__ for t in TOOLS]:
        tools[name] = BenchmarkTool(name, Capabilities.camel(), runtime, None)
    namespace = namespace.add_variables(tools)
    eval_args = interpreter.EvalArgs(BenchmarkPolicies(),
                                     interpreter.MetadataEvalMode.STRICT)
    # fenced, as the privileged model's reply is, so CaMeL's own extractor
    # takes the program; the fence adds no line, the numbers are the file's
    box: dict[str, Any] = {}

    def interpret() -> None:
        try:
            box["done"] = interpreter.parse_and_interpret_code(
                f"```python\n{code}```", namespace, [], [], eval_args)
        except Exception as raised:
            box["raised"] = raised

    worker = threading.Thread(target=interpret, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        print(f"camel-error: 0: Timeout: the plan was still running "
              f"{timeout:g} s after interpretation began", file=sys.stderr)
        sys.stderr.flush()
        os._exit(3)
    if "raised" in box:
        # a policy denial is raised through the interpreter rather than
        # returned, and so is an exception a builtin raises (10 // 0); either
        # discards the calls recorded so far - CaMeL stops the plan there.
        # The line is the innermost node the interpreter was evaluating.
        raised = box["raised"]
        print(f"camel-error: {_raised_line(raised)}: "
              f"{type(raised).__name__}: {_message(raised)}",
              file=sys.stderr)
        return 1
    outcome, _, calls, _ = box["done"]
    for call in calls:
        if call.function == "print":
            sys.stdout.write(" ".join(str(v) for v in call.args.values())
                             + "\n")
    sys.stdout.flush()
    match outcome:
        case result.Error(error):
            exc = error.exception
            message = _message(exc)
            print(f"camel-error: {_line(error)}: {type(exc).__name__}: "
                  f"{message}", file=sys.stderr)
            return 1
    return 0


def _raised_line(exc: BaseException) -> int:
    line = 0
    tb = exc.__traceback__
    while tb is not None:
        if tb.tb_frame.f_code.co_filename.endswith("interpreter.py"):
            node = tb.tb_frame.f_locals.get("node")
            found = getattr(node, "lineno", None)
            if isinstance(found, int) and found > 0:
                line = found
        tb = tb.tb_next
    return line


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
