"""velaris stats: counts over a directory of programs.
"""
import json
import os
import sys

from .version import VERSION
from .tables import CHECK_MEMORY_MB_DEFAULT, CHECK_TIMEOUT_DEFAULT
from .pool import Pool
from typing import Any

# ---------------------------------------------------------------------------
# 20b. STATS - a count over a directory of programs
#
#     `velaris stats --ffi <dir>` (8.2) counts the Python a directory of
#     programs reaches, from each program's audit: how many call Python at
#     all; how many name every module they call, and so run under a grant
#     that names them (`ffi:math,json`); how many name a module with a value
#     built while running, or name none, and so need a plain `ffi`; and
#     which modules are named, by how many programs, and whether each ships
#     native code (ffi_native). Nothing is run. The JSON it writes,
#     velaris.stats-ffi/1, is provisional (STABILITY.md).
# ---------------------------------------------------------------------------


STATS_FFI_SCHEMA = "velaris.stats-ffi/1"


def stats_ffi(root: str, *, timeout: Any = CHECK_TIMEOUT_DEFAULT,
              max_memory_mb: Any = CHECK_MEMORY_MB_DEFAULT) -> dict[str, Any]:
    """The ffi grants the .vel files under `root` need, counted. Each file
    is audited on one worker under the check ceiling, as `velaris audit`
    is; a file that does not compile, cannot be read or is stopped by the
    ceiling is named under not_counted and counted nowhere else."""
    files = sorted(os.path.join(dp, name)
                   for dp, _, names in os.walk(root) for name in names
                   if name.endswith(".vel"))
    programs: list[Any] = []
    modules: dict[Any, Any] = {}
    not_counted: list[Any] = []
    with Pool(size=1, timeout=timeout, max_memory_mb=max_memory_mb) as pool:
        for path in files:
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as fh:
                    source = fh.read()
            except (OSError, UnicodeDecodeError):
                not_counted.append(rel)
                continue
            got = pool.audit(source, path=os.path.abspath(path))
            if not got.ok:
                not_counted.append(rel)
                continue
            if "ffi" not in (got.effects or []):
                continue
            named = sorted(got.ffi_modules or [])
            plain = bool(got.ffi_any) or not named
            programs.append({"file": rel, "modules": named, "plain": plain,
                             "grant": ("ffi" if plain
                                       else "ffi:" + ",".join(named))})
            for m in named:
                entry = modules.setdefault(m, {
                    "programs": 0,
                    "native": (got.ffi_native or {}).get(m, "unknown")})
                entry["programs"] += 1
    return {"schema": STATS_FFI_SCHEMA, "velaris_version": VERSION,
            "root": root.replace(os.sep, "/"), "files": len(files),
            "not_counted": not_counted, "needing_ffi": len(programs),
            "scoped": sum(1 for p in programs if not p["plain"]),
            "plain": sum(1 for p in programs if p["plain"]),
            "modules": dict(sorted(modules.items())), "programs": programs}


def stats_ffi_lines(result: dict[Any, Any]) -> list[Any]:
    """What `velaris stats --ffi` prints."""
    counted = result["files"] - len(result["not_counted"])
    out = [f"velaris stats --ffi {result['root']}: {result['files']} "
           f"program(s), {counted} compiled",
           f"  {result['needing_ffi']} call Python",
           f"    {result['scoped']} name every module they call "
           f"(a grant like ffi:math)",
           f"    {result['plain']} name a module while running, or none "
           f"(a plain ffi grant)"]
    if result["modules"]:
        out.append("  modules named, by how many programs name them:")
        width = max(len(m) for m in result["modules"])
        for m, e in sorted(result["modules"].items(),
                           key=lambda kv: (-kv[1]["programs"], kv[0])):
            out.append(f"    {m.ljust(width)}  {e['programs']:>3}  "
                       f"{e['native']}")
    if result["programs"]:
        out.append("  the grant each needs:")
        width = max(len(p["grant"]) for p in result["programs"])
        for p in result["programs"]:
            out.append(f"    {p['grant'].ljust(width)}  {p['file']}")
    if result["not_counted"]:
        out.append(f"  not counted (does not compile, or could not be read): "
                   f"{len(result['not_counted'])}")
    return out


def stats_main(argv: list[Any]) -> int:
    """velaris stats --ffi [dir] [--json]"""
    words = [a for a in argv if a not in ("--ffi", "--json")]
    if "--ffi" not in argv or len(words) > 1 \
            or any(w.startswith("-") for w in words):
        print("usage: velaris stats --ffi [dir] [--json]", file=sys.stderr)
        return 2
    root = words[0] if words else "."
    if not os.path.isdir(root):
        print(f"velaris stats: {root} is not a directory", file=sys.stderr)
        return 2
    result = stats_ffi(root)
    if "--json" in argv:
        print(json.dumps(result, indent=2))
    else:
        print("\n".join(stats_ffi_lines(result)))
    return 0
