#!/usr/bin/env python3
"""The audit and the SARIF are the same bytes on every system (8.2).

`--write DIR` writes, for a fixed set of example programs, the documents
`velaris audit --json` and `velaris audit --sarif` print, and one
`velaris proofs --sarif` log over them - built by the functions those
commands call and serialized as they serialize them, so what is compared is
the document and not the console's line ends. `--compare A B C` holds the
directories to be byte for byte the same and names each file that differs.

One value is not compared as written: a SARIF log's
`originalUriBaseIds.%SRCROOT%.uri`, which the SARIF standard makes an
absolute URI of the directory the command ran in and so names the machine.
It is replaced by `file:///SRCROOT/` in every file before the bytes are
compared, and nothing else is touched.

CI writes the documents on Linux, Windows and macOS (Python 3.12, with the
prover) and compares them in one job.

    python check_identical.py --write out
    python check_identical.py --compare linux windows macos
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# programs whose audits reach every field: effects and budgets, paths and
# hosts, Python modules, secrets and declassification, counts, promises
# proven and left to runtime, a loop not shown to end, one that does not
# compile
PROGRAMS = ("examples/effects.vel", "examples/discount.vel",
            "examples/ffi.vel", "examples/secret.vel", "examples/sandbox.vel",
            "examples/settlement.vel", "examples/termination_bad.vel",
            "examples/wordcount.vel", "examples/sneaky.vel",
            "examples/ledger.vel")

ROOT_PLACEHOLDER = "file:///SRCROOT/"


def documents() -> dict[str, bytes]:
    """{file name: bytes} of every document, built with this checkout as the
    working directory and the programs named relative to it, as CI runs."""
    import velaris
    os.chdir(HERE)
    out: dict[str, bytes] = {}
    for rel in PROGRAMS:
        stem = Path(rel).stem
        with open(rel, encoding="utf-8") as fh:
            source = fh.read()
        audit = velaris._audit_here(source, path=rel).as_dict()
        out[f"{stem}.audit.json"] = json.dumps(audit, indent=2).encode()
        sarif = velaris.sarif_audit([rel])
        out[f"{stem}.audit.sarif"] = json.dumps(sarif, indent=2).encode()
    reports = {rel: velaris.inspect_source(rel) for rel in PROGRAMS}
    totals = {"proven": 0, "runtime": 0, "plain": 0, "errors": 0}
    for rel, report in reports.items():
        for f in report["functions"]:
            if os.path.abspath(f["file"]) != os.path.abspath(rel):
                continue
            key = ("proven" if f["status"] == "proven" else "runtime"
                   if f["status"] == "checked at runtime" else "plain")
            totals[key] += 1
        totals["errors"] += len(report["errors"])
    promising = totals["proven"] + totals["runtime"]
    share = 100.0 * totals["proven"] / promising if promising else 0.0
    log = velaris.sarif_proofs(reports, totals, share, None)
    out["proofs.sarif"] = json.dumps(log, indent=2).encode()
    return out


def comparable(name: str, raw: bytes) -> bytes:
    """The bytes to compare: a SARIF log with its root URI replaced."""
    if not name.endswith(".sarif"):
        return raw
    doc = json.loads(raw)
    for run in doc.get("runs", []):
        root = run.get("originalUriBaseIds", {}).get("%SRCROOT%")
        if isinstance(root, dict) and "uri" in root:
            text = raw.decode()
            raw = text.replace(json.dumps(root["uri"]),
                               json.dumps(ROOT_PLACEHOLDER)).encode()
    return raw


def main(argv: list[str]) -> int:
    if argv[:1] == ["--write"] and len(argv) == 2:
        target = Path(argv[1]).resolve()
        target.mkdir(parents=True, exist_ok=True)
        docs = documents()
        for name, raw in docs.items():
            (target / name).write_bytes(raw)
        print(f"wrote {len(docs)} documents to {target}")
        return 0
    if argv[:1] == ["--compare"] and len(argv) >= 3:
        places = [Path(p) for p in argv[1:]]
        names = sorted({p.name for d in places if d.is_dir()
                        for p in d.iterdir()})
        missing = [str(d) for d in places if not d.is_dir()]
        if missing or not names:
            print(f"nothing to compare: {missing or 'no documents'}")
            return 1
        wrong = 0
        for name in names:
            digests = {}
            for d in places:
                f = d / name
                digests[str(d)] = (hashlib.sha256(
                    comparable(name, f.read_bytes())).hexdigest()[:16]
                    if f.exists() else "missing")
            same = len(set(digests.values())) == 1 \
                and "missing" not in digests.values()
            print(f"  {'ok' if same else 'DIFFERS':8} {name}"
                  + ("" if same else f"  {digests}"))
            wrong += not same
        print(f"{len(names) - wrong} of {len(names)} documents the same on "
              f"{len(places)} systems")
        return 1 if wrong else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
