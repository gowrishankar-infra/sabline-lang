"""The MCP server's tools, hashed and signed, and checked against a running
server.
"""
import json
import os
import sys

from .version import VERSION, _INSTALL_DIR
from .findings import REPOSITORY
from typing import IO, Any, cast


# ---- the MCP server's tools, hashed and signed ------------------------------

MCP_TOOLS_SCHEMA = "velaris.mcp-tools/1"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
RELEASE_IDENTITY = REPOSITORY + "/.github/workflows/release.yml@refs/tags/v{version}"
# From 7.2.0 no pushed tag starts a release: release.yml runs on main once
# the tests pass there (a workflow_run), tags the commit itself and signs in
# that same run - so a release is signed as main, not as its tag.
# RELEASING.md and SECURITY.md.
RELEASE_IDENTITY_MAIN = REPOSITORY + "/.github/workflows/release.yml@refs/heads/main"
RELEASED_FROM_MAIN = (7, 2, 0)


def release_identity(version: Any) -> str:
    """The sigstore identity the release workflow signed `version` with:
    its tag up to 7.1.2, main from 7.2.0."""
    try:
        parts = [int(p) for p in str(version).split(".")]
    except ValueError:
        return RELEASE_IDENTITY.format(version=version)
    if len(parts) in (2, 3) and tuple(parts + [0])[:3] >= RELEASED_FROM_MAIN:
        return RELEASE_IDENTITY_MAIN
    return RELEASE_IDENTITY.format(version=version)


def _canonical_json(value: Any) -> bytes:
    """Keys sorted, no whitespace between tokens, text as UTF-8 rather
    than escaped: the RFC 8785 form of the objects, arrays, strings,
    integers, booleans and nulls a tool's input schema holds."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode(
                          "utf-8", "surrogatepass")


def mcp_tool_hashes(tool: dict[Any, Any]) -> dict[str, Any]:
    """A tool's name, the sha256 of its description (the UTF-8 bytes of
    the text exactly as the server sends it) and of its input schema
    (_canonical_json)."""
    import hashlib
    description = tool.get("description")
    if not isinstance(description, str):
        description = ""
    try:
        schema = hashlib.sha256(_canonical_json(
            tool.get("inputSchema"))).hexdigest()
    except (TypeError, ValueError):         # NaN, or something not JSON
        schema = "cannot be hashed"
    return {"name": tool.get("name"),
            "description_sha256": hashlib.sha256(description.encode(
                "utf-8", "surrogatepass")).hexdigest(),
            "input_schema_sha256": schema}


def mcp_tool_manifest(server_info: dict[Any, Any], tools: list[Any]) -> dict[str, Any]:
    """velaris.mcp-tools/1: every tool a server offers, hashed."""
    return {"schema": MCP_TOOLS_SCHEMA,
            "server": {"name": server_info.get("name"),
                       "version": server_info.get("version")},
            "hash": "sha256",
            "tools": sorted((mcp_tool_hashes(t) for t in tools),
                            key=lambda t: str(t["name"]))}


def mcp_list_tools(command: list[Any], timeout: float = 120) -> tuple[Any, ...]:
    """Start an MCP server over stdio, as a client would, and ask it for
    its tools: (serverInfo, tools). RuntimeError says what went wrong."""
    import queue as _q
    import subprocess
    import threading as _threading
    import time as _t
    try:
        proc = subprocess.Popen(command, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
    except OSError as e:
        raise RuntimeError(f"cannot start the server: {e.strerror or e}")
    lines: "_q.Queue[bytes | None]" = _q.Queue()
    noise: list[Any] = []

    def pump() -> None:
        for raw in cast(IO[bytes], proc.stdout):
            lines.put(raw)
        lines.put(None)

    def drain() -> None:
        for raw in cast(IO[bytes], proc.stderr):
            noise.append(raw.decode("utf-8", "replace").strip())
            del noise[:-20]

    _threading.Thread(target=pump, daemon=True).start()
    _threading.Thread(target=drain, daemon=True).start()
    deadline = _t.monotonic() + timeout

    def send(message: dict[Any, Any]) -> None:
        cast(IO[bytes], proc.stdin).write((json.dumps(message) + "\n").encode("utf-8"))
        cast(IO[bytes], proc.stdin).flush()

    def answer_to(msg_id: int) -> dict[Any, Any]:
        while True:
            left = deadline - _t.monotonic()
            try:
                raw = lines.get(timeout=max(left, 0.01))
            except _q.Empty:
                raise RuntimeError(f"the server did not answer within "
                                   f"{timeout:g} s")
            if raw is None:
                said = noise[-1] if noise else "it said nothing"
                raise RuntimeError(f"the server stopped: {said}")
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == msg_id:
                if "error" in message:
                    raise RuntimeError(f"the server answered with an "
                                       f"error: {message['error']}")
                got = message.get("result")
                return got if isinstance(got, dict) else {}

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "velaris mcp-verify",
                                        "version": VERSION}}})
        info = answer_to(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        tools: list[Any] = []
        cursor, msg_id = None, 2
        while msg_id < 100:                 # a server paging forever
            send({"jsonrpc": "2.0", "id": msg_id, "method": "tools/list",
                  "params": {"cursor": cursor} if cursor else {}})
            page = answer_to(msg_id)
            tools += [t for t in page.get("tools") or []
                      if isinstance(t, dict)]
            cursor = page.get("nextCursor")
            msg_id += 1
            if not cursor:
                break
        server = info.get("serverInfo")
        return (server if isinstance(server, dict) else {}), tools
    except OSError as e:
        raise RuntimeError(f"the server's pipe closed: {e}")
    finally:
        try:
            cast(IO[bytes], proc.stdin).close()
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
            proc.wait()


def _default_mcp_command() -> list[Any] | None:
    """The MCP server beside this compiler, as a client would start it."""
    if getattr(sys, "frozen", False):
        return None                         # a standalone executable
    beside = os.path.join(_INSTALL_DIR,
                          "velaris_mcp.py")
    if os.path.exists(beside):
        return [sys.executable, beside]
    return [sys.executable, "-m", "velaris_mcp"]


def _split_server_command(argv: list[Any]) -> tuple[Any, ...]:
    """(own arguments, the server command after `--`, or the default)."""
    if "--" in argv:
        at = argv.index("--")
        return argv[:at], argv[at + 1:]
    return argv, _default_mcp_command()


def _sigstore_verify(artifact: bytes, bundle_path: str,
                     identity: str) -> str | None:
    """None when the sigstore bundle proves `identity` signed these
    exact bytes; otherwise why not."""
    try:
        from sigstore.models import Bundle
        from sigstore.verify import Verifier
        from sigstore.verify.policy import Identity
    except ImportError:
        return ("the sigstore package is not installed, so the signature "
                "cannot be checked: pip install sigstore - or check it with "
                "the sigstore command as SECURITY.md shows and then pass "
                "--skip-signature")
    try:
        with open(bundle_path, "rb") as fh:
            bundle = Bundle.from_json(fh.read())
        Verifier.production().verify_artifact(
            artifact, bundle, Identity(identity=identity, issuer=OIDC_ISSUER))
    except Exception as e:
        return f"the signature does not verify: {type(e).__name__}: {e}"
    return None


def mcp_manifest_main(argv: list[Any]) -> int:
    """velaris mcp-manifest [-o FILE] [-- server command...]"""
    own, command = _split_server_command(argv)
    if not command:
        print("mcp-manifest: name the server to ask after --, as: velaris "
              "mcp-manifest -o tools.json -- python -m velaris_mcp",
              file=sys.stderr)
        return 2
    out = None
    if "-o" in own:
        at = own.index("-o")
        if at + 1 >= len(own):
            print("mcp-manifest: -o needs a file", file=sys.stderr)
            return 2
        out = own[at + 1]
    try:
        info, tools = mcp_list_tools(command)
    except RuntimeError as e:
        print(f"mcp-manifest: {e}", file=sys.stderr)
        return 2
    text = json.dumps(mcp_tool_manifest(info, tools), indent=2) + "\n"
    if out is None:
        sys.stdout.write(text)
    else:
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"{out}: {len(tools)} tool(s) from {info.get('name')} "
              f"{info.get('version')}", file=sys.stderr)
    return 0


def mcp_verify_main(argv: list[Any]) -> int:
    """velaris mcp-verify MANIFEST [--bundle FILE] [--identity URL]
    [--skip-signature] [-- server command...]

    Checks the manifest's signature, starts the server the way a client
    would, and reports every tool whose description or input schema
    differs from the manifest, and every tool added or missing. Exit 0
    when everything matches, 1 when anything differs, 2 when the check
    could not be made."""
    own, command = _split_server_command(argv)
    manifest_path = bundle_path = identity = None
    skip = False
    i = 0
    while i < len(own):
        a = own[i]
        if a in ("--bundle", "--identity"):
            if i + 1 >= len(own):
                print(f"mcp-verify: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--bundle":
                bundle_path = own[i + 1]
            else:
                identity = own[i + 1]
            i += 2
            continue
        if a == "--skip-signature":
            skip = True
        elif a.startswith("-") or manifest_path is not None:
            print("usage: velaris mcp-verify MANIFEST [--bundle FILE] "
                  "[--identity URL] [--skip-signature] [-- server command]",
                  file=sys.stderr)
            return 2
        else:
            manifest_path = a
        i += 1
    if manifest_path is None:
        print("usage: velaris mcp-verify MANIFEST [--bundle FILE] "
              "[--identity URL] [--skip-signature] [-- server command]",
              file=sys.stderr)
        return 2
    if not command:
        print("mcp-verify: name the server to check after --, as: velaris "
              "mcp-verify tools.json -- python -m velaris_mcp",
              file=sys.stderr)
        return 2
    try:
        with open(manifest_path, "rb") as fh:
            raw = fh.read()
        manifest = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        manifest = None
    promised = manifest.get("tools") if isinstance(manifest, dict) else None
    if not (isinstance(manifest, dict)
            and manifest.get("schema") == MCP_TOOLS_SCHEMA
            and manifest.get("hash") == "sha256"
            and isinstance(promised, list)
            and all(isinstance(t, dict) and isinstance(t.get("name"), str)
                    for t in promised)):
        print(f"mcp-verify: {manifest_path} is not a readable "
              f"{MCP_TOOLS_SCHEMA} manifest", file=sys.stderr)
        return 2
    version = (manifest.get("server") or {}).get("version")
    print(f"manifest:  {manifest_path} ({len(promised)} tool(s), "
          f"{(manifest.get('server') or {}).get('name')} {version})")

    if skip:
        print("signature: NOT CHECKED (--skip-signature)")
    else:
        bundle_path = bundle_path or manifest_path + ".sigstore.json"
        identity = identity or release_identity(version)
        if not os.path.exists(bundle_path):
            print(f"mcp-verify: no signature bundle at {bundle_path}; "
                  f"download it from the release beside the manifest, or "
                  f"pass --bundle - or --skip-signature to compare without "
                  f"one", file=sys.stderr)
            return 2
        why = _sigstore_verify(raw, bundle_path, identity)
        if why:
            print(f"mcp-verify: {why}", file=sys.stderr)
            return 2
        print(f"signature: verified, signed by {identity}")

    try:
        info, tools = mcp_list_tools(command)
    except RuntimeError as e:
        print(f"mcp-verify: {e}", file=sys.stderr)
        return 2
    print(f"server:    {' '.join(command)} ({info.get('name')} "
          f"{info.get('version')})")
    if info.get("version") != version:
        print(f"           the manifest is for {version}; the server says "
              f"{info.get('version')}")

    offered: dict[Any, Any] = {}
    doubled = set()
    for t in tools:
        h = mcp_tool_hashes(t)
        name = str(h["name"])
        if name in offered:
            doubled.add(name)
        offered[name] = h
    wanted = {t["name"]: t for t in promised}
    same = changed = 0
    for name in sorted(set(wanted) | set(offered)):
        if name not in offered:
            changed += 1
            print(f"  MISSING  {name}: in the manifest, not offered by the "
                  f"server")
            continue
        if name not in wanted:
            changed += 1
            print(f"  NEW      {name}: offered by the server, not in the "
                  f"manifest")
            continue
        parts = [label for key, label in (
            ("description_sha256", "description"),
            ("input_schema_sha256", "input schema"))
            if offered[name][key] != wanted[name].get(key)]
        if name in doubled:
            parts.append("offered more than once")
        if parts:
            changed += 1
            print(f"  CHANGED  {name}: {' and '.join(parts)}")
        else:
            same += 1
            print(f"  ok       {name}")
    print(f"{same} of {len(set(wanted) | set(offered))} tool(s) match the "
          f"manifest" + (f"; {changed} differ" if changed else ""))
    return 1 if changed else 0
