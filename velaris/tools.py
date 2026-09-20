"""The runner's first cut (8.5): tools the host process offers a program.

`velaris run program.vel --tools manifest.json` starts a run whose program
may call `tool(name, arguments)` and `tool_secret(name, arguments)`. The
manifest - velaris.tools/1 - is the host's: which tools there are, a JSON
Schema for each one's arguments, which results are secret, what a call
costs, the most calls and the most cost one run may spend, and any grants
of its own. The budget is the operator's, as for every other effect:
`tool`, `tool:NAME`, `tool:NAME:ARGUMENT=PATTERN`, `tool:NAME@N`, `tool@N`.
A call has to pass both.

The door is this process's standard input and output, one JSON object to a
line (EMBEDDING.md, "Hosting a run that calls tools"). A call is written,
the run waits, and the host's answer is what the call evaluates to. While a
session is open the program's own output travels the same way, as `output`
events, so a line the program prints can never be read as a line of the
protocol.

What this does not do, and 9.0 will: a tool's result is a Text like any
other. A result that names a host, a path or another tool's argument steers
the program exactly as far as the budget lets the program go, and no
further - but nothing marks the result as the host's words rather than the
program's. That mark is `Untrusted`, and it is not here yet.
"""
import json
import queue
import sys
import threading

from . import state as _state
from .errors import VelarisError
from .values import FailSignal
from .budget import Budget, BudgetError, tool_pattern_matches
from typing import Any, cast

TOOLS_SCHEMA = "velaris.tools/1"
TOOLS_PROTOCOL = "velaris.tools-door/1"
TOOL_TIMEOUT_DEFAULT = 120          # seconds the host has to answer one call
MAX_REPLY_BYTES = 1 << 20           # one reply line, as one fetch's body
MAX_ARGUMENT_BYTES = 1 << 20

# the JSON Schema keywords an `arguments` schema may use. A keyword that is
# not here is refused when the manifest is read: a constraint nobody checks
# is worse than none, because somebody believes it
_SCHEMA_KEYWORDS = frozenset({
    "type", "properties", "required", "additionalProperties", "items",
    "enum", "const", "minLength", "maxLength", "minimum", "maximum",
    "minItems", "maxItems", "description", "title", "default"})
_SCHEMA_TYPES = ("object", "array", "string", "integer", "number", "boolean",
                 "null")


class ManifestError(ValueError):
    """A tool manifest that is not one. The message says what is wrong."""


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) \
        and v == v and v not in (float("inf"), float("-inf"))


def _check_schema(schema: Any, where: str) -> None:
    if not isinstance(schema, dict):
        raise ManifestError(f"{where}: a schema is a JSON object")
    unknown = sorted(set(schema) - _SCHEMA_KEYWORDS)
    if unknown:
        raise ManifestError(
            f"{where}: '{unknown[0]}' is not a keyword this reads; the ones "
            f"it holds a call to are {', '.join(sorted(_SCHEMA_KEYWORDS))}")
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t is not None else []
    for one in types:
        if one not in _SCHEMA_TYPES:
            raise ManifestError(f"{where}: type '{one}' is not one of "
                                f"{', '.join(_SCHEMA_TYPES)}")
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        raise ManifestError(f"{where}: properties is a JSON object")
    for name, sub in props.items():
        _check_schema(sub, f"{where}.{name}")
    if "items" in schema:
        _check_schema(schema["items"], f"{where}[]")
    extra = schema.get("additionalProperties", False)
    if not isinstance(extra, bool):
        _check_schema(extra, f"{where}.*")
    req = schema.get("required", [])
    if not isinstance(req, list) or not all(isinstance(r, str) for r in req):
        raise ManifestError(f"{where}: required is a list of names")
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema and not (isinstance(schema[key], int)
                                  and not isinstance(schema[key], bool)
                                  and schema[key] >= 0):
            raise ManifestError(f"{where}: {key} is a whole number, 0 or more")
    for key in ("minimum", "maximum"):
        if key in schema and not _is_number(schema[key]):
            raise ManifestError(f"{where}: {key} is a number")
    if "enum" in schema and not isinstance(schema["enum"], list):
        raise ManifestError(f"{where}: enum is a list")


def _type_is(value: Any, t: str) -> bool:
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return _is_number(value)


def schema_problem(value: Any, schema: dict[str, Any], where: str = "arguments"
                   ) -> str | None:
    """Why `value` is not what `schema` says, or None. An object takes no
    property its schema does not name unless additionalProperties says so:
    the closed reading, because an argument nobody described is one nobody
    constrained."""
    t = schema.get("type")
    types = t if isinstance(t, list) else [t] if t is not None else []
    if types and not any(_type_is(value, one) for one in types):
        return f"{where} is not {' or '.join(types)}"
    if "const" in schema and value != schema["const"]:
        return f"{where} is not the one value allowed"
    if "enum" in schema and value not in schema["enum"]:
        return f"{where} is not one of the values allowed"
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            return f"{where} is shorter than {schema['minLength']}"
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            return f"{where} is longer than {schema['maxLength']}"
    if _is_number(value):
        if "minimum" in schema and value < schema["minimum"]:
            return f"{where} is below {schema['minimum']}"
        if "maximum" in schema and value > schema["maximum"]:
            return f"{where} is above {schema['maximum']}"
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            return f"{where} has fewer than {schema['minItems']} item(s)"
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            return f"{where} has more than {schema['maxItems']} item(s)"
        if "items" in schema:
            for i, item in enumerate(value):
                why = schema_problem(item, schema["items"], f"{where}[{i}]")
                if why:
                    return why
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                return f"{where} has no '{name}'"
        extra = schema.get("additionalProperties", False)
        for name, item in value.items():
            if name in props:
                why = schema_problem(item, props[name], f"{where}.{name}")
            elif extra is False:
                why = f"{where} has '{name}', which the tool does not take"
            elif extra is True:
                why = None
            else:
                why = schema_problem(item, extra, f"{where}.{name}")
            if why:
                return why
    return None


def read_manifest(text: str) -> dict[str, Any]:
    """A velaris.tools/1 manifest, checked and with every default written
    in. ManifestError says what is wrong with one that is not."""
    try:
        doc = json.loads(text)
    except ValueError as e:
        raise ManifestError(f"it is not JSON: {e}")
    if not isinstance(doc, dict) or doc.get("schema") != TOOLS_SCHEMA:
        raise ManifestError(f'it does not say "schema": "{TOOLS_SCHEMA}"')
    unknown = sorted(set(doc) - {"schema", "tools", "allow", "ceiling",
                                 "description"})
    if unknown:
        raise ManifestError(f"'{unknown[0]}' is not a field of a manifest")
    tools = doc.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise ManifestError("tools is an object with at least one tool")
    from .budget import _tool_word
    out_tools: dict[str, Any] = {}
    for name, t in tools.items():
        if not _tool_word(name):
            raise ManifestError(f"'{name}' is not a tool's name (letters, "
                                f"digits, _ . -, starting with a letter)")
        if not isinstance(t, dict):
            raise ManifestError(f"tools.{name} is a JSON object")
        unknown = sorted(set(t) - {"description", "arguments", "result",
                                   "cost"})
        if unknown:
            raise ManifestError(f"tools.{name}: '{unknown[0]}' is not a "
                                f"field of a tool")
        schema = t.get("arguments", {"type": "object"})
        _check_schema(schema, f"tools.{name}.arguments")
        if schema.get("type", "object") != "object":
            raise ManifestError(f"tools.{name}.arguments: a tool's arguments "
                                f"are a JSON object")
        result = t.get("result", "text")
        if result not in ("text", "secret"):
            raise ManifestError(f'tools.{name}.result is "text" or "secret"')
        cost = t.get("cost", 0)
        if not _is_number(cost) or cost < 0:
            raise ManifestError(f"tools.{name}.cost is a number, 0 or more")
        out_tools[name] = {"description": str(t.get("description", "")),
                           "arguments": dict(schema, type="object"),
                           "result": result, "cost": cost}
    allow = doc.get("allow", [])
    if not isinstance(allow, list) or not all(isinstance(a, str)
                                              for a in allow):
        raise ManifestError("allow is a list of tool grants, as the budget "
                            "writes them")
    for a in allow:
        if not (a == "tool" or a.startswith(("tool:", "tool@"))):
            raise ManifestError(f"allow: '{a}' is not a tool grant")
        if "," in a:
            raise ManifestError(f"allow: '{a}' holds a ','; write it %2C")
    try:
        held = Budget.parse(",".join(allow)) if allow else None
    except BudgetError as e:
        raise ManifestError(f"allow: {e}")
    ceiling = doc.get("ceiling", {})
    if not isinstance(ceiling, dict) or set(ceiling) - {"calls", "cost",
                                                        "unit"}:
        raise ManifestError("ceiling holds calls, cost and unit")
    calls, cost_most = ceiling.get("calls"), ceiling.get("cost")
    if calls is not None and not (isinstance(calls, int)
                                  and not isinstance(calls, bool)
                                  and calls >= 0):
        raise ManifestError("ceiling.calls is a whole number, 0 or more")
    if cost_most is not None and (not _is_number(cost_most) or cost_most < 0):
        raise ManifestError("ceiling.cost is a number, 0 or more")
    return {"schema": TOOLS_SCHEMA, "tools": out_tools, "allow": list(allow),
            "held": held,
            "ceiling": {"calls": calls, "cost": cost_most,
                        "unit": str(ceiling.get("unit", "units"))}}


def held_by(grants: "dict[str, Any] | None", name: str,
            arguments: dict[str, Any]) -> tuple[str | None, list[str]]:
    """(why not, the grants that held it) for one call against one set of
    tool grants - the budget's, or the manifest's own. An argument a grant
    names has to be there, and be a text, a number or a Bool that matches
    one of the patterns written for it, or a list whose every item does."""
    if grants is None:
        return None, []
    if name not in grants:
        return f"tool '{name}' is not granted", []
    wanted = grants[name]
    if wanted is None:
        return None, []
    held: list[str] = []
    for arg in sorted({a for a, _ in wanted}):
        patterns = [p for a, p in wanted if a == arg]
        if arg not in arguments:
            return (f"argument '{arg}' is held to a pattern and was not "
                    f"given"), []
        value = arguments[arg]
        items = value if isinstance(value, list) else [value]
        if not items:
            return f"argument '{arg}' is an empty list", []
        for item in items:
            if isinstance(item, bool):
                text = "true" if item else "false"
            elif isinstance(item, str):
                text = item
            elif _is_number(item):
                text = json.dumps(item)
            else:
                return (f"argument '{arg}' is held to a pattern, and only a "
                        f"text, a number, a Bool or a list of those can "
                        f"match one"), []
            hit = next((p for p in patterns
                        if tool_pattern_matches(p, text)), None)
            if hit is None:
                return (f"argument '{arg}' does not match "
                        + " or ".join(f"'{p}'" for p in patterns)), []
            grant = f"tool:{name}:{arg}={hit}"
            if grant not in held:
                held.append(grant)
    return None, held


class _EventStream:
    """The program's standard output while a session is open: each write is
    an `output` event on the door."""

    def __init__(self, session: "ToolSession") -> None:
        self._session = session
        self._pending = ""

    def write(self, text: str) -> int:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            self._session.send({"event": "output", "text": line})
        return len(text)

    def flush(self) -> None:
        if self._pending:
            self._session.send({"event": "output", "text": self._pending,
                                "partial": True})
            self._pending = ""

    def isatty(self) -> bool:
        return False

    encoding = "utf-8"
    errors = "backslashreplace"

    def reconfigure(self, **_: Any) -> None:
        return None


class ToolSession:
    """One run's tools: the manifest, the door, what has been spent."""

    def __init__(self, manifest: dict[str, Any], manifest_sha256: str,
                 out: Any = None, inp: Any = None,
                 timeout: float = TOOL_TIMEOUT_DEFAULT) -> None:
        self.manifest = manifest
        self.manifest_sha256 = manifest_sha256
        self.timeout = timeout
        self.calls_used = 0
        self.cost_used = 0.0
        self.next_id = 1
        self._out = out if out is not None else sys.stdout
        self._inp = inp if inp is not None else getattr(sys.stdin, "buffer",
                                                        sys.stdin)
        self._lock = threading.Lock()
        self._replies: "queue.Queue[Any]" = queue.Queue()
        # started now, before the program's first statement and so before
        # the operating system is asked to hold the run: a confined process
        # may not be let start a thread
        self._reader = threading.Thread(target=self._read_loop, daemon=True,
                                        name="velaris-tools-door")
        self._reader.start()

    # ---- the door ---------------------------------------------------------
    def send(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=True, separators=(",", ":"))
        with self._lock:
            try:
                self._out.write(line + "\n")
                self._out.flush()
            except (OSError, ValueError):
                pass                       # the host went away; a call says so

    def _read_loop(self) -> None:
        """Lines from the host, put on the queue; None when it goes away.
        Read from the descriptor itself where there is one: a thread left
        waiting inside Python's buffered reader holds that reader's lock,
        and the interpreter cannot shut down past it."""
        import os
        inp: Any = self._inp
        fd: int | None
        try:
            fd = int(inp.fileno())
        except (AttributeError, OSError, ValueError):
            fd = None
        held = b""
        while True:
            try:
                if fd is None:
                    chunk = inp.readline(MAX_REPLY_BYTES + 2)
                else:
                    chunk = os.read(fd, 65536)
            except (OSError, ValueError):
                chunk = b""
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8")
            if not chunk:
                self._replies.put(None)
                return
            held += chunk
            while b"\n" in held:
                line, held = held.split(b"\n", 1)
                self._replies.put(line + b"\n")
            if len(held) > MAX_REPLY_BYTES:
                self._replies.put(held)    # too long to be one: _reply says so
                held = b""

    def _reply(self, call_id: int, line: int) -> dict[str, Any]:
        try:
            raw = self._replies.get(timeout=self.timeout)
        except queue.Empty:
            raise _door_error(f"the host did not answer call {call_id} "
                              f"within {self.timeout:g} second(s)", line)
        if raw is None:
            raise _door_error(f"the host closed the door before answering "
                              f"call {call_id}", line)
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if len(raw) > MAX_REPLY_BYTES or not raw.endswith(b"\n"):
            raise _door_error(f"the host's answer to call {call_id} is over "
                              f"{MAX_REPLY_BYTES} bytes, or is not a whole "
                              f"line", line)
        try:
            reply = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _door_error(f"the host's answer to call {call_id} is not a "
                              f"line of JSON", line)
        if not isinstance(reply, dict) or reply.get("id") != call_id \
                or isinstance(reply.get("id"), bool):
            raise _door_error(f"the host answered something other than call "
                              f"{call_id}: one call is open at a time, and "
                              f"its answer carries its id", line)
        if ("result" in reply) == ("error" in reply):
            raise _door_error(f"the host's answer to call {call_id} holds "
                              f"neither a result nor an error, or both", line)
        return reply

    # ---- one call ---------------------------------------------------------
    def call(self, builtin: str, name: str, arguments_json: str,
             line: int) -> str:
        tools = self.manifest["tools"]
        if name not in tools:
            raise VelarisError("E320",
                f"'{builtin}' calls tool '{name}', which the host does not "
                f"offer (it offers: {', '.join(sorted(tools))})", line,
                fixes=["call a tool the manifest names",
                       "or have the host offer it: add it to the manifest "
                       "given to --tools"])
        tool = tools[name]
        if len(arguments_json.encode("utf-8", "surrogatepass")) \
                > MAX_ARGUMENT_BYTES:
            raise _arguments_error(builtin, name, "they are over "
                                   f"{MAX_ARGUMENT_BYTES} bytes", line)
        try:
            arguments = json.loads(arguments_json) if arguments_json.strip() \
                else {}
        except ValueError:
            raise _arguments_error(builtin, name, "they are not JSON", line)
        if not isinstance(arguments, dict):
            raise _arguments_error(builtin, name, "they are not a JSON "
                                   "object", line)
        why = schema_problem(arguments, tool["arguments"])
        if why:
            raise _arguments_error(builtin, name, why, line)
        if tool["result"] == "secret" and builtin != "tool_secret":
            raise VelarisError("E323",
                f"the manifest marks the result of tool '{name}' secret, and "
                f"'tool' would hand it back as an ordinary Text", line,
                fixes=[f"call it with tool_secret(\"{name}\", ...), which "
                       f"gives a Secret of Text"])
        # the operator's grants, then the host's own: a call passes both
        held: list[str] = []
        for whose, grants in (("this run's budget", _state.TOOL_GRANTS),
                              ("the manifest's own grants",
                               None if self.manifest["held"] is None
                               else self.manifest["held"].tools)):
            why_not, got = held_by(grants, name, arguments)
            if why_not:
                raise VelarisError("E321",
                    f"'{builtin}' calls tool '{name}' outside "
                    f"{whose}: {why_not}", line,
                    fixes=["call it with arguments the grant allows",
                           f"or allow it: --allow tool:{name} (any "
                           f"arguments), or tool:{name}:ARGUMENT=PATTERN"])
            held += [g for g in got if g not in held]
        self._spend_count(builtin, name, line)
        ceiling = self.manifest["ceiling"]
        if ceiling["calls"] is not None and self.calls_used >= ceiling["calls"]:
            raise VelarisError("E322",
                f"'{builtin}' would be tool call {self.calls_used + 1}, and "
                f"the manifest's ceiling is {ceiling['calls']} call(s) a run",
                line, fixes=["use a program that calls fewer tools",
                             "or have the host raise ceiling.calls"])
        if ceiling["cost"] is not None and \
                self.cost_used + tool["cost"] > ceiling["cost"]:
            raise VelarisError("E322",
                f"'{builtin}' calls tool '{name}' at {tool['cost']:g} "
                f"{ceiling['unit']}, and {self.cost_used:g} of the run's "
                f"{ceiling['cost']:g} are spent", line,
                fixes=["use a program that spends less",
                       "or have the host raise ceiling.cost"])
        call_id = self.next_id
        self.next_id += 1
        self.calls_used += 1
        rec = _state.RUN_RECORDER
        if rec is not None:
            rec.note("tool", tool=name, line=line, held="\\n".join(held),
                     secret=tool["result"] == "secret")
        for grant in held or [f"tool:{name}"]:
            _state.GRANT_USES[grant] = _state.GRANT_USES.get(grant, 0) + 1
        flush = getattr(sys.stdout, "flush", None)
        if flush is not None:
            flush()                        # what was printed comes first
        self.send({"event": "call", "id": call_id, "tool": name,
                   "arguments": arguments})
        reply = self._reply(call_id, line)
        cost = reply.get("cost", tool["cost"])
        if not _is_number(cost) or cost < 0:
            raise _door_error(f"the host's answer to call {call_id} gives a "
                              f"cost that is not a number, 0 or more", line)
        self.cost_used += float(cost)
        if reply.get("secret") is True and builtin != "tool_secret":
            raise VelarisError("E323",
                f"the host marked this result of tool '{name}' secret, and "
                f"'tool' would hand it back as an ordinary Text", line,
                fixes=[f"call it with tool_secret(\"{name}\", ...)",
                       'and mark it in the manifest: "result": "secret"'])
        if "error" in reply:
            # the host's words are not written into the failure: what a tool
            # says went wrong is a result like any other, and 9.0 marks it
            raise FailSignal(f"tool '{name}' failed: {_short(reply['error'])}")
        result = reply["result"]
        return result if isinstance(result, str) else json.dumps(
            result, ensure_ascii=False)

    def _spend_count(self, builtin: str, name: str, line: int) -> None:
        for key, what in ((name, f"tool '{name}'"), ("", "tools")):
            limit = _state.TOOL_LIMITS.get(key)
            used = _state.TOOL_COUNTS.get(key, 0) + 1
            if limit is not None and used > limit:
                grant = f"tool:{name}@{used}" if key else f"tool@{used}"
                raise VelarisError("E322",
                    f"'{builtin}' is call {used} of {what}, and this run "
                    f"allows {limit}", line,
                    fixes=[f"allow more: --allow {grant}",
                           "or use a program that calls less"])
        for key in (name, ""):
            _state.TOOL_COUNTS[key] = _state.TOOL_COUNTS.get(key, 0) + 1

    # ---- what a receipt says of it ------------------------------------------
    def ceiling_record(self) -> dict[str, Any]:
        c = self.manifest["ceiling"]
        return {"calls": c["calls"], "cost": c["cost"], "unit": c["unit"],
                "calls_used": self.calls_used,
                "cost_used": round(self.cost_used, 6),
                "manifest_sha256": self.manifest_sha256}


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value)
    return text if len(text) <= 300 else text[:300] + "..."


def _door_error(what: str, line: int) -> VelarisError:
    return VelarisError("E324", what, line,
                        fixes=["this is the host's to fix: one line of JSON "
                               "for each call, carrying the call's id and a "
                               "result or an error (EMBEDDING.md)"])


def _arguments_error(builtin: str, name: str, why: str,
                     line: int) -> VelarisError:
    return VelarisError("E323",
        f"'{builtin}' calls tool '{name}' with arguments its manifest does "
        f"not take: {why}", line,
        fixes=["build the arguments the tool's schema describes, as "
               'json_of({"query": text})'])


def run_tool(builtin: str, args: list[Any], line: int) -> Any:
    """`tool` and `tool_secret` while running. The `tool` effect was spent
    before this ran."""
    session = _state.TOOL_SESSION
    if session is None:
        raise VelarisError("E320",
            f"'{builtin}' calls tool '{args[0]}', and this run has no tools: "
            f"none was offered to it", line,
            fixes=["run it under a host that offers tools: velaris run "
                   "<file> --tools manifest.json"])
    return session.call(builtin, str(args[0]), str(args[1]), line)


def open_session(path: str, timeout: float = TOOL_TIMEOUT_DEFAULT
                 ) -> ToolSession:
    """The session of `--tools PATH`. ManifestError or OSError when the
    manifest cannot be used. From here the program's standard output is the
    door's `output` events, and it reads nothing from standard input."""
    import hashlib
    import io
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ManifestError("it is not UTF-8")
    manifest = read_manifest(text)
    session = ToolSession(manifest, hashlib.sha256(raw).hexdigest(),
                          timeout=timeout)
    sys.stdout = cast(Any, _EventStream(session))
    sys.stdin = io.StringIO("")
    return session
