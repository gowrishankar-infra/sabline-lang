#!/usr/bin/env python3
"""Metamorphic tests for the audit: transforms that must not change what
a program is allowed to do, and one that must change it in exactly one way.

`velaris.audit/1` describes a program's capability surface. Four
transforms leave that surface untouched - renaming its functions,
reordering them, adding dead (pure, uncalled) code, and splitting it
across files - because none of them changes what the program can do to
the outside world. A fifth, adding one effect, must change the surface
in exactly one dimension and no other. This suite asserts both, so a
future change to the audit that makes it sensitive to a program's shape,
or blind to an added effect, is caught.

"The surface" here is the security-relevant part of the audit: the
effect set, the safe command, the file paths and hosts and Python
modules named, and the secrets section - not the `functions` list, whose
names and order are meant to follow the source.

    python check_metamorphic.py
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

isolate("check_metamorphic")          # its own directory

PASS = FAIL = 0


def ok(label: Any, cond: Any, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok    {label}")
    else:
        FAIL += 1
        print(f"  CHANGED  {label}   {detail}")


def surface(src: Any, path: Any = None) -> dict[str, Any]:
    """The security-relevant surface of an audit, as a comparable dict."""
    a = velaris.audit(src, path=path)
    return {
        "effects": tuple(a.effects),
        "safe_command": a.safe_command,
        "fs_paths": {k: (sorted(v) if isinstance(v, list) else v)
                     for k, v in (a.fs_paths or {}).items()},
        "net_hosts": {"hosts": sorted((a.net_hosts or {}).get("hosts", [])),
                      "any": (a.net_hosts or {}).get("any")},
        "ffi_modules": tuple(sorted(a.ffi_modules or [])),
        "secrets": a.secrets,
    }


BASE = '''
fn store(path: Text, body: Text) uses fs { write_file(path, body) }
fn pull(url: Text) -> Text uses net or fail { return try fetch(url) }
fn main() uses io, fs, net {
    store("out/report.txt", "hi")
    check pull("https://api.example.com/data") {
        ok b { print(b) }
        fail w { print("f") }
    }
}
'''

RENAMED = '''
fn save(path: Text, body: Text) uses fs { write_file(path, body) }
fn grab(url: Text) -> Text uses net or fail { return try fetch(url) }
fn main() uses io, fs, net {
    save("out/report.txt", "hi")
    check grab("https://api.example.com/data") {
        ok b { print(b) }
        fail w { print("f") }
    }
}
'''

REORDERED = '''
fn pull(url: Text) -> Text uses net or fail { return try fetch(url) }
fn main() uses io, fs, net {
    store("out/report.txt", "hi")
    check pull("https://api.example.com/data") {
        ok b { print(b) }
        fail w { print("f") }
    }
}
fn store(path: Text, body: Text) uses fs { write_file(path, body) }
'''

DEAD_CODE = BASE + '''
fn unused(n: Int) -> Int { return n + 1 }
fn also_unused(a: Int, b: Int) -> Int { return a * b }
'''

# one added effect: main also reads the clock. Exactly `clock` is gained.
ADDED_EFFECT = '''
fn store(path: Text, body: Text) uses fs { write_file(path, body) }
fn pull(url: Text) -> Text uses net or fail { return try fetch(url) }
fn main() uses io, fs, net, clock {
    store("out/report.txt", "hi")
    let t = now()
    check pull("https://api.example.com/data") {
        ok b { print(b) }
        fail w { print("f") }
    }
}
'''


def split_across_files() -> Any:
    """BASE with store and pull moved into an imported library."""
    d = tempfile.mkdtemp(prefix="velaris-metamorphic-")
    lib = os.path.join(d, "lib.vel")
    with open(lib, "w", encoding="utf-8", newline="\n") as f:
        f.write('fn store(path: Text, body: Text) uses fs '
                '{ write_file(path, body) }\n'
                'fn pull(url: Text) -> Text uses net or fail '
                '{ return try fetch(url) }\n')
    entry = os.path.join(d, "main.vel")
    src = ('import "lib.vel"\n'
           'fn main() uses io, fs, net {\n'
           '    store("out/report.txt", "hi")\n'
           '    check pull("https://api.example.com/data") {\n'
           '        ok b { print(b) }\n        fail w { print("f") }\n'
           '    }\n}\n')
    with open(entry, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    return surface(src, path=entry)


def main() -> int:
    print("metamorphic audit tests")
    print("-" * 62)
    base = surface(BASE)
    ok("renaming every function leaves the surface unchanged",
       surface(RENAMED) == base, f"{surface(RENAMED)} != {base}")
    ok("reordering the functions leaves the surface unchanged",
       surface(REORDERED) == base, f"{surface(REORDERED)} != {base}")
    ok("adding dead (pure, uncalled) code leaves the surface unchanged",
       surface(DEAD_CODE) == base, f"{surface(DEAD_CODE)} != {base}")
    ok("splitting the program across files leaves the surface unchanged",
       split_across_files() == base)

    after = surface(ADDED_EFFECT)
    gained = set(after["effects"]) - set(base["effects"])
    lost = set(base["effects"]) - set(after["effects"])
    ok("adding one effect gains exactly that effect",
       gained == {"clock"} and not lost, f"gained {gained}, lost {lost}")
    # and nothing ELSE about the surface moved: only effects and the
    # safe_command that follows from them
    unchanged_dims = all(after[k] == base[k]
                         for k in ("fs_paths", "net_hosts", "ffi_modules",
                                   "secrets"))
    ok("adding one effect changes nothing else (paths, hosts, modules, "
       "secrets)", unchanged_dims,
       str({k: (base[k], after[k]) for k in
            ("fs_paths", "net_hosts", "ffi_modules", "secrets")
            if base[k] != after[k]}))
    ok("adding one effect adds it to the safe command",
       "clock" in after["safe_command"]
       and "clock" not in base["safe_command"], after["safe_command"])
    print("-" * 62)
    print(f"{PASS} correct, {FAIL} wrong")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
