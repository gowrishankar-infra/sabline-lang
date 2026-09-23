#!/usr/bin/env python3
"""Ask Sabline's MCP server to run a program with more than its ceiling.

    python ask_for_more.py

Starts `sabline mcp --max-allow io` - the ceiling it has when nobody sets
one - and calls `sabline_run` with a program that reads a private key,
asking for `fs:read:.` as well as `io`. Prints the answer the server gives
and the outcome its invocation log records, and nothing that varies between
runs: no timestamps, no durations.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROGRAM = (HERE / "attack.vel").read_text(encoding="utf-8")


def sabline_command() -> list[str]:
    """How to start Sabline. incidents/run.py puts it in the environment,
    because this runs from a scratch copy with no checkout above it."""
    given = os.environ.get("SABLINE_COMMAND")
    if given:
        return [str(part) for part in json.loads(given)]
    for up in HERE.parents:
        if (up / "sabline.py").exists():
            return [sys.executable, str(up / "sabline.py")]
    return [sys.executable, "-m", "sabline"]


def main() -> int:
    server = subprocess.Popen(
        sabline_command() + ["mcp", "--max-allow", "io"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8")
    asked = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "a-poisoned-client",
                                   "version": "1"}}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
         "params": {"name": "sabline_run",
                    "arguments": {"source": PROGRAM,
                                  "allow": ["io", "fs:read:."]}}},
    ]
    out, err = server.communicate(
        "\n".join(json.dumps(one) for one in asked) + "\n", timeout=300)

    print("the client asked for: io, fs:read:.")
    for line in out.splitlines():
        try:
            answer = json.loads(line)
        except ValueError:
            continue
        if answer.get("id") == 2:
            said = json.loads(answer["result"]["content"][0]["text"])
            print("the server answered:")
            print(json.dumps(said, indent=2, sort_keys=True))
    for line in err.splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("schema") == "sabline.invocation/1":
            print(f"the invocation log recorded: "
                  f"outcome={record['outcome']}, "
                  f"refusals={json.dumps(record['refusals'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
