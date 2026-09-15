#!/usr/bin/env python3
"""Build velaris.mcpb - the double-click install for MCP clients.

An .mcpb bundle is a zip holding a manifest and everything the server
needs. The point is that a person installs Velaris's tools without
editing JSON, finding a Python path, or knowing what stdio is: they
download one file and open it.

The compiler travels inside the bundle, so the user does not need
`pip install velaris-lang` first. The prover (z3) does not - proofs
degrade to runtime checks without it, which the tools report honestly
rather than hiding.

    python build_mcpb.py            -> velaris.mcpb
"""
import json
import shutil
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "velaris.mcpb"
STAGE = HERE / "_mcpb_build"


def main() -> int:
    manifest_path = HERE / "mcpb" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # the bundle's version follows the compiler's, always
    sys.path.insert(0, str(HERE))
    import velaris
    if manifest["version"] != velaris.VERSION:
        manifest["version"] = velaris.VERSION
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                                 encoding="utf-8")
        print(f"manifest version follows the compiler: {velaris.VERSION}")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    lib = STAGE / "server" / "lib"
    lib.mkdir(parents=True)

    shutil.copy2(HERE / "velaris_mcp.py", STAGE / "server" / "velaris_mcp.py")
    shutil.copytree(HERE / "velaris", lib / "velaris",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2(HERE / "LLM.md", lib / "LLM.md")
    shutil.copytree(HERE / "stdlib", lib / "stdlib")
    shutil.copy2(manifest_path, STAGE / "manifest.json")
    for extra in ("README.md", "LICENSE"):
        if (HERE / extra).exists():
            shutil.copy2(HERE / extra, STAGE / extra)

    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(STAGE))
    shutil.rmtree(STAGE)

    size = OUT.stat().st_size / 1024
    print(f"{OUT.name} written, {size:.0f} KB")
    print("install: double-click it, or drag it onto an MCP client that")
    print("accepts bundles (Claude Desktop: Settings -> Extensions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
