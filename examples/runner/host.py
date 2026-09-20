#!/usr/bin/env python3
"""A host for a Sabline program that calls tools: the whole protocol.

    python examples/runner/host.py examples/runner/digest.vel
    python examples/runner/host.py examples/runner/digest_outside.vel

It offers two tools, `search` and `send_email` (tools.json beside this
file), starts the program with `sabline run --tools`, and answers each call
on the run's standard input. It sends no mail: `send_email` appends to the
list this prints at the end, which is how you can see that the second
program's mail was refused before this host ever heard of it.

The door is one JSON object to a line (docs/runner.md, "Hosting a run that
calls tools"). From the run: `ready`, `output` for what the program
printed, `call` for a tool call, `exit` last. To the run: one answer for
each call, carrying its id and a `result` or an `error`.

A tool's result is a Text to the program like any other. Nothing yet marks
it as the host's words rather than the program's own (that is `Untrusted`,
in 9.0), so a host should not put in a result anything it would not want
the program to act on inside its budget.
"""
import json
import os
import subprocess
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUDGET = "io,tool:search@20,tool:send_email:to=*@corp.com"

NOTES = {"release checklist": "bump the six version files; write the "
                              "CHANGELOG entry; ask the gate"}


def search(arguments: dict[str, Any]) -> str:
    return NOTES.get(arguments["query"], "nothing found")


def sabline_command() -> list[str]:
    """This checkout's sabline.py when the example is run from one, else the
    installed command."""
    launcher = os.path.join(ROOT, "sabline.py")
    if os.path.exists(launcher):
        return [sys.executable, launcher]
    return [sys.executable, "-m", "sabline"]


def host(program: str, receipt: str | None = None) -> int:
    outbox: list[dict[str, Any]] = []

    def send_email(arguments: dict[str, Any]) -> str:
        outbox.append(arguments)
        return f"queued as message {len(outbox)}"

    tools = {"search": search, "send_email": send_email}
    command = sabline_command() + [
        "run", program, "--tools", os.path.join(HERE, "tools.json"),
        "--allow", BUDGET]
    if receipt:
        command += ["--receipt", receipt]
    run = subprocess.Popen(command, stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, text=True,
                           encoding="utf-8")
    assert run.stdin is not None and run.stdout is not None
    status = 1
    for line in run.stdout:
        event = json.loads(line)
        kind = event.get("event")
        if kind == "output":
            print("program:", event["text"])
        elif kind == "call":
            print(f"call {event['id']}: {event['tool']} "
                  f"{json.dumps(event['arguments'], sort_keys=True)}")
            try:
                answer: dict[str, Any] = {
                    "id": event["id"],
                    "result": tools[event["tool"]](event["arguments"])}
            except Exception as e:             # the tool's failure, told
                answer = {"id": event["id"], "error": str(e)}
            run.stdin.write(json.dumps(answer) + "\n")
            run.stdin.flush()
        elif kind == "exit":
            status = event["status"]
            print(f"exit {status}: {event['calls_used']} call(s), "
                  f"{event['cost_used']:g} of {event['cost']:g} "
                  f"{event['unit']}")
    run.stdin.close()
    run.wait()
    print(f"mail sent: {len(outbox)}")
    for mail in outbox:
        print(f"  to {mail['to']}: {mail['subject']}")
    return status


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(host(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
