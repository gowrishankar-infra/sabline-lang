#!/usr/bin/env python3
"""The runner's first cut: tools a host offers, held to a manifest and a budget.

    python check_runner.py

Each case starts `velaris run PROGRAM --tools MANIFEST` as a host would,
speaks the door's JSON lines to it, and holds what happened - what reached
the host, what the program was told, how the run ended, what its receipt
says - to what THREAT_MODEL.md and EMBEDDING.md say. The adversarial cases
of 8.5's pass are here so that they stay tried: an argument that escapes its
pattern, a ceiling passed, a host that lies, and a result that tries to
steer the program past its budget (it cannot; that the program may act on it
inside its budget is the 9.0 Untrusted case, and is said, not fixed).
"""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).parent))
from suite_dirs import isolate  # noqa: E402

HERE = Path(__file__).parent
WORK = isolate("check_runner")
VELARIS = [sys.executable, str(HERE / "velaris.py")]
FAILED: list[str] = []
PASSED = [0]


def expect(what: str, ok: bool, detail: Any = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != "" else ""))


MANIFEST: dict[str, Any] = {
    "schema": "velaris.tools/1",
    "tools": {
        "search": {"arguments": {"type": "object", "properties": {
            "query": {"type": "string", "maxLength": 50}},
            "required": ["query"]}, "cost": 1},
        "send_email": {"arguments": {"type": "object", "properties": {
            "to": {"type": ["string", "array"], "items": {"type": "string"}},
            "body": {"type": "string"}}, "required": ["to", "body"]},
            "cost": 5},
        "vault": {"arguments": {"type": "object"}, "result": "secret"},
    },
    "ceiling": {"calls": 6, "cost": 12, "unit": "credits"},
}


class Run:
    """One hosted run: every event it sent, what it printed, how it ended."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self.calls: list[dict[str, Any]] = []
        self.output: list[str] = []
        self.stderr = ""
        self.status: int | None = None
        self.receipt: dict[str, Any] = {}


def hosted(program: str, allow: str, answer: Callable[[dict[str, Any]], Any],
           manifest: dict[str, Any] | None = None,
           extra: list[str] | None = None) -> Run:
    """Run `program` under `allow`, answering each call with `answer(event)`:
    a dict is the reply's fields (the id is added unless it names one), a
    str is written as the raw line, None answers nothing and closes."""
    stem = f"case{PASSED[0] + len(FAILED)}"
    source = WORK / f"{stem}.vel"
    source.write_text(program, encoding="utf-8")
    tools = WORK / f"{stem}.tools.json"
    tools.write_text(json.dumps(manifest or MANIFEST), encoding="utf-8")
    receipt = WORK / f"{stem}.receipt.json"
    proc = subprocess.Popen(
        VELARIS + ["run", str(source), "--tools", str(tools), "--allow", allow,
                   "--receipt", str(receipt)] + (extra or []),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdin is not None and proc.stdout is not None
    run = Run()
    for raw in proc.stdout:
        event = json.loads(raw.decode("utf-8"))
        run.events.append(event)
        if event.get("event") == "output":
            run.output.append(event["text"])
        if event.get("event") == "call":
            run.calls.append(event)
            reply = answer(event)
            if reply is None:
                proc.stdin.close()
                continue
            line = reply if isinstance(reply, str) else json.dumps(
                {"id": event["id"], **reply})
            try:
                proc.stdin.write(line.encode("utf-8") + b"\n")
                proc.stdin.flush()
            except (OSError, ValueError):
                pass
    try:
        proc.stdin.close()
    except (OSError, ValueError):
        pass
    assert proc.stderr is not None
    run.stderr = proc.stderr.read().decode("utf-8", "replace")
    run.status = proc.wait(timeout=60)
    if receipt.exists():
        try:
            run.receipt = json.loads(receipt.read_text(encoding="utf-8"))[
                "predicate"]
        except (ValueError, KeyError):
            run.receipt = {}
    return run


def program(body: str, effects: str = "io, tool") -> str:
    return f"fn main() uses {effects} {{\n{body}\n}}\n"


def call(tool: str, args: str, builtin: str = "tool") -> str:
    return (f'    check {builtin}("{tool}", {args}) {{\n'
            f'        ok got {{ print("ok: " + got) }}\n'
            f'        fail why {{ print("failed: " + why) }}\n    }}')


def echo(event: dict[str, Any]) -> dict[str, Any]:
    return {"result": f"{event['tool']} done"}


def refused_with(run: Run, code: str) -> bool:
    return (run.status == 1 and f"error[{code}]" in run.stderr
            and any(r.get("code") == code and r.get("effect") == "tool"
                    and r.get("stopped") for r in run.receipt.get(
                        "refusals", [])))


def main() -> int:
    print("the door")
    q = 'json_of({"query": "x"})'
    run = hosted(program('    print("before")\n' + call("search", q)
                         + '\n    print("after")'), "io,tool:search", echo)
    kinds = [e["event"] for e in run.events]
    expect("ready, the program's output, the call, and exit last - and "
           "nothing on standard output that is not one JSON object a line",
           kinds == ["ready", "output", "call", "output", "output", "exit"]
           and run.output == ["before", "ok: search done", "after"]
           and run.events[0]["tools"] == ["search", "send_email", "vault"]
           and run.events[-1]["status"] == 0 and run.status == 0,
           (kinds, run.output, run.stderr))
    expect("the call carries the tool and its arguments as JSON",
           run.calls == [{"event": "call", "id": 1, "tool": "search",
                          "arguments": {"query": "x"}}], run.calls)
    expect("the receipt lists the call, the grant that let it through and "
           "the ceiling, with the manifest's digest",
           run.receipt.get("tool_calls") == [
               {"tool": "search", "line": 3, "times": 1, "secret": False,
                "held_to": []}]
           and {"grant": "tool:search", "times": 1}
           in run.receipt.get("grants_used", [])
           and run.receipt["tool_ceiling"]["calls_used"] == 1
           and run.receipt["tool_ceiling"]["cost_used"] == 1
           and len(run.receipt["tool_ceiling"]["manifest_sha256"]) == 64,
           run.receipt)
    run = hosted(program(call("search", q)), "io,tool:search",
                 lambda e: {"error": "index offline"})
    expect("a tool's error is a failure the program handles",
           run.output == ["failed: tool 'search' failed: index offline"]
           and run.status == 0, (run.output, run.stderr))
    run = hosted(program('    print("x")\n    print(read_line() + "|")'),
                 "io,tool", echo)
    expect("a hosted program reads nothing from the door",
           run.output == ["x", "|"], run.output)

    print("the budget")
    run = hosted(program(call("search", q)), "io", echo)
    expect("with no tool grant a call is E310, and the host hears nothing",
           run.status == 1 and "error[E310]" in run.stderr
           and not run.calls, run.stderr)
    run = hosted(program(call("send_email", 'json_of({"to": "a@corp.com", '
                                            '"body": "b"})')),
                 "io,tool:search", echo)
    expect("a tool that is not granted is E321, and the host hears nothing",
           refused_with(run, "E321") and not run.calls, run.stderr)
    run = hosted(program(call("missing", "\"{}\"")), "io,tool", echo)
    expect("a tool the manifest does not offer is E320",
           refused_with(run, "E320") and not run.calls, run.stderr)
    plain = subprocess.run(
        VELARIS + [str(WORK / "case0.vel"), "--allow", "io,tool"],
        capture_output=True, stdin=subprocess.DEVNULL, timeout=60)
    expect("with no manifest at all a call is E320: there is no tool",
           plain.returncode == 1 and b"error[E320]" in plain.stderr,
           plain.stderr)

    print("an argument that escapes its constraint")
    held = "io,tool:send_email:to=*@corp.com"
    escapes = {
        "another domain": '"eve@evil.example"',
        "the domain as a prefix": '"eve@corp.com.evil.example"',
        "two addresses in one text": '"eve@evil.example, ann@corp.com"',
        "a second @": '"eve@evil.example@corp.com"',
        "a line feed": '"eve@evil.example\\nann@corp.com"',
        "a semicolon": '"eve@evil.example;ann@corp.com"',
        "angle brackets": '"<eve@evil.example> ann@corp.com"',
        "a quoted local part": '"\\"eve@evil.example\\"@corp.com"',
        "upper case": '"ann@CORP.COM"',
        "a trailing space": '"ann@corp.com "',
        "a list with one outside": '["ann@corp.com", "eve@evil.example"]',
        "an empty list": '[]',
        "a map": '{"x": "ann@corp.com"}',
        "nothing at the star": '"@corp.com"',
    }
    for name, value in escapes.items():
        # the value is spliced into JSON text, as a program building its
        # arguments by hand would write it
        args = ('"{\\"to\\": ' + value.replace("\\", "\\\\").replace('"', '\\"')
                + ', \\"body\\": \\"b\\"}"')
        run = hosted(program(call("send_email", args)), held, echo)
        expect(f"to = {name}: refused, and the host hears nothing",
               (refused_with(run, "E321") or refused_with(run, "E323"))
               and not run.calls, (run.stderr, run.calls))
    run = hosted(program(call("send_email", 'json_of({"body": "b"})')),
                 held, echo, manifest={**MANIFEST, "tools": {
                     **MANIFEST["tools"], "send_email": {
                         "arguments": {"type": "object",
                                       "additionalProperties": True}}}})
    expect("a held argument that is left out is refused: the host's default "
           "is not the operator's pattern", refused_with(run, "E321")
           and not run.calls, run.stderr)
    run = hosted(program(call("send_email", 'json_of({"to": "ann@corp.com", '
                                            '"body": "b", "bcc": "eve@evil.example"})')),
                 held, echo)
    expect("an argument the schema does not name is refused (E323): what "
           "nobody described, nobody constrained",
           refused_with(run, "E323") and not run.calls, run.stderr)
    run = hosted(program(call("send_email", '"{\\"to\\": [\\"ann@corp.com\\", '
                                            '\\"bob@corp.com\\"], \\"body\\": \\"b\\"}"')),
                 held, echo)
    expect("a list whose every address matches goes through, and the "
           "receipt names the pattern, not the addresses",
           run.status == 0 and len(run.calls) == 1
           and run.receipt["tool_calls"][0]["held_to"]
           == ["tool:send_email:to=*@corp.com"]
           and "ann@corp.com" not in json.dumps(run.receipt), run.receipt)
    both = hosted(program(call("send_email", 'json_of({"to": "ann@corp.com", '
                                             '"body": "b"})')),
                  "io,tool", echo,
                  manifest={**MANIFEST,
                            "allow": ["tool:send_email:to=*@partner.example"]})
    expect("the manifest's own grants hold too: a call passes both",
           refused_with(both, "E321") and "manifest's own grants"
           in both.stderr and not both.calls, both.stderr)

    print("a ceiling exceeded")
    three = "\n".join(call("search", q) for _ in range(3))
    run = hosted(program(three), "io,tool:search@2", echo)
    expect("tool:search@2 lets two calls through and refuses the third",
           refused_with(run, "E322") and len(run.calls) == 2, run.stderr)
    run = hosted(program(three), "io,tool@2", echo)
    expect("tool@2 is the same for the run as a whole",
           refused_with(run, "E322") and len(run.calls) == 2, run.stderr)
    seven = "\n".join(call("search", q) for _ in range(7))
    run = hosted(program(seven), "io,tool", echo)
    expect("the manifest's ceiling of 6 calls refuses the seventh",
           refused_with(run, "E322") and len(run.calls) == 6
           and run.receipt["tool_ceiling"]["calls_used"] == 6, run.stderr)
    mail = call("send_email", 'json_of({"to": "a@corp.com", "body": "b"})')
    run = hosted(program("\n".join([mail] * 3)), "io,tool", echo)
    expect("the cost ceiling of 12 refuses the third call at 5 credits",
           refused_with(run, "E322") and len(run.calls) == 2, run.stderr)
    run = hosted(program(three), "io,tool",
                 lambda e: {"result": "r", "cost": 7})
    expect("a cost the host reports is the one counted: two calls at 7 "
           "pass 12, and the third is refused",
           refused_with(run, "E322") and len(run.calls) == 2
           and run.receipt["tool_ceiling"]["cost_used"] == 14, run.receipt)

    print("a host that lies")
    lies: dict[str, Callable[[dict[str, Any]], Any]] = {
        "answers with another call's id": lambda e: {"id": 99, "result": "r"},
        "answers with a Bool for an id": lambda e: {"id": True, "result": "r"},
        "sends a line that is not JSON": lambda e: "{not json",
        "sends a JSON list": lambda e: "[1]",
        "gives a result and an error": lambda e: {"result": "r", "error": "e"},
        "gives neither": lambda e: {},
        "gives a negative cost, to win budget back":
            lambda e: {"result": "r", "cost": -100},
        "gives a cost that is not a number":
            lambda e: {"result": "r", "cost": "free"},
        "gives NaN for a cost": lambda e: '{"id": %d, "result": "r", '
                                          '"cost": NaN}' % e["id"],
        "closes the door without answering": lambda e: None,
    }
    for name, answer in lies.items():
        run = hosted(program(call("search", q) + '\n    print("went on")'),
                     "io,tool", answer)
        expect(f"a host that {name}: E324, and the program does not go on",
               run.status == 1 and "error[E324]" in run.stderr
               and "went on" not in run.output, (run.stderr, run.output))
    run = hosted(program(call("search", q)), "io,tool", lambda e: None,
                 extra=["--tool-timeout", "1"])
    expect("a host that never answers is E324 when the wait is over",
           run.status == 1 and "error[E324]" in run.stderr, run.stderr)
    run = hosted(program(call("search", q)), "io,tool",
                 lambda e: {"result": "r", "budget": "all", "allow": "net",
                            "grants": ["net"], "tool": "send_email"})
    expect("fields a reply adds change nothing: the result is a Text",
           run.output == ["ok: r"] and run.status == 0, run.output)

    print("a secret result")
    run = hosted(program(call("vault", "\"{}\"")), "io,tool", echo)
    expect("a tool marked secret called through tool is E323, unheard",
           refused_with(run, "E323") and not run.calls, run.stderr)
    leak = hosted("fn main() uses io, tool {\n"
                  '    check tool_secret("vault", "{}") {\n'
                  "        ok got { print(got) }\n"
                  '        fail why { print("no") }\n    }\n}\n', "io,tool",
                  echo)
    expect("what tool_secret gives back is a Secret: printing it does not "
           "compile (E560)", leak.status == 1 and "E560" in leak.stderr
           and not leak.calls, leak.stderr)
    run = hosted(program(call("search", q)), "io,tool",
                 lambda e: {"result": "r", "secret": True})
    expect("a host that marks one result secret is not handed back as Text",
           refused_with(run, "E323"), run.stderr)

    print("a result that steers (the 9.0 Untrusted case)")
    steer = ("fn main() uses io, net, tool {\n"
             '    check tool("search", json_of({"query": "x"})) {\n'
             "        ok where {\n"
             "            check fetch(where) {\n"
             '                ok body { print("fetched") }\n'
             '                fail why { print("not fetched") }\n'
             "            }\n        }\n"
             '        fail why { print("no") }\n    }\n}\n')
    run = hosted(steer, "io,tool,net:api.example.com",
                 lambda e: {"result": "https://attacker.example/x"})
    expect("a result that names a host outside the budget: the fetch is "
           "refused (E314), as it is for any Text",
           run.status == 1 and "error[E314]" in run.stderr, run.stderr)

    print("the manifest")
    bad = {
        "no schema": {"tools": MANIFEST["tools"]},
        "a keyword nobody checks": {**MANIFEST, "tools": {"t": {
            "arguments": {"type": "object", "pattern": "^a"}}}},
        "a grant for another effect": {**MANIFEST, "allow": ["net"]},
        "a negative ceiling": {**MANIFEST, "ceiling": {"calls": -1}},
        "a tool name with a colon": {**MANIFEST, "tools": {"a:b": {}}},
    }
    for name, doc in bad.items():
        run = hosted(program('    print("ran")'), "io,tool", echo,
                     manifest=doc)
        expect(f"a manifest with {name} is exit 2, and nothing runs",
               run.status == 2 and not run.events
               and "cannot be used" in run.stderr, (run.status, run.stderr))

    print("the worked example, and skill verify")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "runner_host", HERE / "examples" / "runner" / "host.py")
    assert spec is not None and spec.loader is not None
    for name, status, sent in (("digest.vel", 0, "mail sent: 1"),
                               ("digest_outside.vel", 1, "mail sent: 0")):
        done = subprocess.run(
            [sys.executable, str(HERE / "examples" / "runner" / "host.py"),
             str(HERE / "examples" / "runner" / name)],
            capture_output=True, timeout=120)
        text = done.stdout.decode("utf-8", "replace")
        expect(f"examples/runner/host.py {name}: exit {status}, {sent}",
               done.returncode == status and sent in text
               and (status == 0 or b"error[E321]" in done.stderr),
               (text, done.stderr))
    done = subprocess.run(VELARIS + ["skill", "verify",
                                     str(HERE / "examples" / "runner"),
                                     "--json"], capture_output=True,
                          timeout=120)
    report = json.loads(done.stdout.decode("utf-8"))
    expect("skill verify: the tools, that each is offered, and the budget",
           done.returncode == 0 and report["ok"]
           and [t["tool"] for t in report["tools"]] == ["search", "send_email"]
           and all(t["offered"] for t in report["tools"])
           and report["budget"] == "io,tool:search,tool:send_email"
           and report["schema"] == "velaris.skill-verify/1", report)
    skill = WORK / "skill"
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: mailer\n---\n",
                                    encoding="utf-8")
    (skill / "tools.json").write_text(json.dumps(MANIFEST), encoding="utf-8")
    (skill / "a.vel").write_text(program(call("vault", "\"{}\"") + "\n"
                                         + call("wire_money", "\"{}\"")),
                                 encoding="utf-8")
    done = subprocess.run(VELARIS + ["skill", "verify", str(skill), "--json"],
                          capture_output=True, timeout=120)
    report = json.loads(done.stdout.decode("utf-8"))
    expect("skill verify fails a skill that calls a tool nobody offers, and "
           "one that would take a secret as Text",
           done.returncode == 1 and report["skill"] == "mailer"
           and any("wire_money" in p for p in report["problems"])
           and any("tool_secret" in p for p in report["problems"]), report)
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    print(f"all {PASSED[0]} checks passed: a tool call passes the manifest, "
          f"the budget and the ceiling, or the host never hears of it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
