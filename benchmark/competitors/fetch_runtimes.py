#!/usr/bin/env python3
"""Fetch, verify and unpack the runtimes benchmark/compete.py scores.

    python benchmark/competitors/fetch_runtimes.py

Reads runtimes.json beside this file: wasmtime, CPython's WASI build and
Deno, each by URL and SHA-256, into competitors/.runtimes (or
$SABLINE_COMPETITORS_RT). A download whose hash differs stops it before
anything is unpacked. It then precompiles python.wasm for wasmtime (with
epoch interruption on, which -W timeout needs), so the 5 second deadline
measures the program and not Cranelift, and builds the Starlark host with
the Go toolchain on PATH (go.starlark.net pinned by go.mod and go.sum).

Linux x86_64 only: that is where the table is recorded and re-derived. Every
runtime is free and needs no key. Nothing here is fetched at run time.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RT_DIR = os.environ.get("SABLINE_COMPETITORS_RT",
                        os.path.join(HERE, ".runtimes"))


def download(name: str, pin: dict[str, str]) -> bytes:
    print(f"  {name} {pin['version']}: {pin['url']}")
    with urllib.request.urlopen(pin["url"], timeout=300) as r:
        data = bytes(r.read())
    digest = hashlib.sha256(data).hexdigest()
    if digest != pin["sha256"]:
        raise SystemExit(f"{name}: SHA-256 {digest}, runtimes.json pins "
                         f"{pin['sha256']} - not unpacked")
    return data


def executable(path: str) -> None:
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP
             | stat.S_IXOTH)


def main() -> int:
    if not (sys.platform.startswith("linux") and os.uname().machine
            in ("x86_64", "AMD64")):
        print("the competitor runtimes are pinned for Linux x86_64 only")
        return 2
    with open(os.path.join(HERE, "runtimes.json"), encoding="utf-8") as f:
        pins = json.load(f)
    os.makedirs(RT_DIR, exist_ok=True)

    data = download("wasmtime", pins["wasmtime"])
    dest = os.path.join(RT_DIR, "wasmtime")
    shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:xz") as tar:
        member = next(m for m in tar.getmembers()
                      if m.name.endswith("/wasmtime") and m.isfile())
        src = tar.extractfile(member)
        if src is None:
            raise SystemExit("wasmtime: the archive holds no wasmtime binary")
        with src, open(os.path.join(dest, "wasmtime"), "wb") as out:
            shutil.copyfileobj(src, out)
    wasmtime = os.path.join(dest, "wasmtime")
    executable(wasmtime)

    data = download("python-wasi", pins["python-wasi"])
    dest = os.path.join(RT_DIR, "python-wasi")
    shutil.rmtree(dest, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
    subprocess.run([wasmtime, "compile", "-W", "epoch-interruption=y",
                    os.path.join(dest, "python.wasm"), "-o",
                    os.path.join(dest, "python.cwasm")], check=True)

    data = download("deno", pins["deno"])
    dest = os.path.join(RT_DIR, "deno")
    shutil.rmtree(dest, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(dest)
    executable(os.path.join(dest, "deno"))

    host = os.path.join(RT_DIR, "starlark-host")
    print("  starlark-host: go build (go.starlark.net as go.mod pins it)")
    subprocess.run(["go", "build", "-trimpath", "-o", host, "."],
                   cwd=os.path.join(HERE, "hosts", "starlark"), check=True)
    print(f"runtimes ready in {RT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
