#!/usr/bin/env python3
"""Set up Velaris's MCP tools in whatever assistant this machine has.

Different clients keep their configuration in different files, and a
person should not have to know which. This finds the ones present,
adds a `velaris` server to each without disturbing anything else, and
says what it did.

    velaris mcp-install              set it up everywhere it finds
    velaris mcp-install --list       show what it found, change nothing
    velaris mcp-install --remove     take it back out

Claude Desktop builds that accept .mcpb bundles are better served by
`velaris.mcpb` - double-click, no files edited. This is for everything
else: Claude Code, Cline, Continue, Cursor, Windsurf, Zed, and any
client that reads a standard mcpServers block.
"""
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "velaris"


def homes() -> dict[str, Any]:
    """Where each client keeps its configuration, per platform."""
    home = Path.home()
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA",
                                    home / "AppData/Local"))
        return {
            "Claude Desktop": appdata / "Claude/claude_desktop_config.json",
            "Claude Code": home / ".claude.json",
            "Cline": (appdata / "Code/User/globalStorage/saoudrizwan."
                      "claude-dev/settings/cline_mcp_settings.json"),
            "Cursor": home / ".cursor/mcp.json",
            "Windsurf": home / ".codeium/windsurf/mcp_config.json",
            "Continue": home / ".continue/config.json",
            "Zed": local / "Zed/settings.json",
        }
    if sys.platform == "darwin":
        support = home / "Library/Application Support"
        return {
            "Claude Desktop": support / "Claude/claude_desktop_config.json",
            "Claude Code": home / ".claude.json",
            "Cline": (support / "Code/User/globalStorage/saoudrizwan."
                      "claude-dev/settings/cline_mcp_settings.json"),
            "Cursor": home / ".cursor/mcp.json",
            "Windsurf": home / ".codeium/windsurf/mcp_config.json",
            "Continue": home / ".continue/config.json",
            "Zed": home / ".config/zed/settings.json",
        }
    config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
    return {
        "Claude Desktop": config / "Claude/claude_desktop_config.json",
        "Claude Code": home / ".claude.json",
        "Cline": (config / "Code/User/globalStorage/saoudrizwan."
                  "claude-dev/settings/cline_mcp_settings.json"),
        "Cursor": home / ".cursor/mcp.json",
        "Windsurf": home / ".codeium/windsurf/mcp_config.json",
        "Continue": home / ".continue/config.json",
        "Zed": config / "zed/settings.json",
    }


def entry() -> dict[str, Any]:
    """How to start the server, using this very Python."""
    return {"command": sys.executable, "args": ["-m", "velaris_mcp"]}


def load(path: Path) -> dict[Any, Any]:
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else {}
    except (json.JSONDecodeError, OSError):
        return {}


def install_into(path: Path, remove: bool = False) -> str:
    """Add or remove our server, leaving every other key untouched."""
    config = load(path)
    servers = config.get("mcpServers")
    if servers is None:
        if remove:
            return "not set up here"
        servers = {}
        config["mcpServers"] = servers

    if remove:
        if SERVER_NAME not in servers:
            return "not set up here"
        del servers[SERVER_NAME]
        action = "removed"
    else:
        already = servers.get(SERVER_NAME)
        servers[SERVER_NAME] = entry()
        action = "updated" if already else "added"

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():                      # never lose a working config
        shutil.copy2(path, path.with_suffix(path.suffix + ".velaris-backup"))
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return action


def main(argv: list[Any]) -> int:
    listing = "--list" in argv
    remove = "--remove" in argv

    print("looking for assistants that speak MCP")
    print("-" * 62)
    found = 0
    for label, path in homes().items():
        exists = path.exists()
        parent = path.parent.exists()
        if not exists and not parent:
            continue                       # this client is not installed
        found += 1
        if listing:
            state = "configured" if SERVER_NAME in \
                load(path).get("mcpServers", {}) else "present"
            print(f"  {label:<16} {state:<12} {path}")
            continue
        try:
            what = install_into(path, remove)
        except OSError as e:
            what = f"could not write ({e.strerror or e})"
        print(f"  {label:<16} {what:<12} {path}")

    print("-" * 62)
    if not found:
        print("no MCP client found on this machine.")
        print("Velaris still works from the command line and as a library;")
        print("see EMBEDDING.md.")
        return 0
    if listing:
        print("nothing was changed (--list)")
    elif remove:
        print("removed. Restart the assistant for it to take effect.")
    else:
        print("done. RESTART the assistant completely - closing the")
        print("window is usually not enough - then ask it:")
        print()
        print('   "Use the velaris tools: read the card, write a small')
        print('    program, audit it, then run it with allow io."')
        print()
        print("Each config was backed up next to itself before writing.")
        print("The server grants a run at most io, 30 seconds and 512 MB.")
        print("To let it grant more, add --max-allow, --max-timeout or")
        print("--max-memory-mb to its args - EMBEDDING.md shows how.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
