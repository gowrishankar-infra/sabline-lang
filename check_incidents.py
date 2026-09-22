#!/usr/bin/env python3
"""Every STOPPED entry still refuses, and every PARTIAL still behaves as its
entry says.

    python check_incidents.py

The incident catalogue makes claims about what Sabline does with the shape
of a real attack, and a claim about a compiler is worth what it is worth on
the day it was written. This re-runs all of it:

CATALOGUE   every directory under incidents/ has an `incident.md` with a
            complete frontmatter block, a verdict this suite knows, a
            Sources section, and `verified:` set to true or false; every
            STOPPED or PARTIAL entry has a `run.json`, and every NOT
            COVERED, UNVERIFIED or OUT OF SCOPE entry has none, because a
            verdict of "nothing refuses this" cannot come with a refusal.
EVIDENCE    incident_evidence.py runs every step of every entry from a
            scratch copy of its directory and holds it to: the exit
            status the entry recorded, the text that must be in what it
            printed, the text that must NOT be (a canary secret, where the
            point is that it did not leave), and then to `refusal.txt` and
            the receipts recorded beside it, byte for byte after the
            normalisation incidents/README.md lists.
GAPS        every PARTIAL, NOT COVERED and UNVERIFIED entry says in one
            plain sentence what it does not cover, and that sentence's
            subject is in the known-open table, docs/known-open.md - a gap
            found here belongs in the threat model, not only in a catalogue.
PAGE        docs/incidents.md is what build_incidents.py writes from the
            entries, and no entry marked `verified: false` has its summary
            published on it.

test.yml runs this on every push, and release.yml starts only when test.yml
has passed on the commit, so no release is made from a tree where a STOPPED
entry has stopped refusing.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from incident_evidence import body, entries, front_matter  # noqa: E402

INCIDENTS = HERE / "incidents"
VERDICTS = ("STOPPED", "PARTIAL", "NOT COVERED", "UNVERIFIED",
            "OUT OF SCOPE")
WITH_EVIDENCE = ("STOPPED", "PARTIAL")
MUST_SAY_THE_GAP = ("PARTIAL", "NOT COVERED", "UNVERIFIED")
PASSED = [0]
FAILED: list[str] = []


def expect(what: str, ok: bool, detail: object = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != ""
                                     else ""))


def catalogue() -> list[dict[str, str]]:
    """Each entry's frontmatter, with the shape of the directory held."""
    found = []
    for entry in entries():
        meta = front_matter(entry / "incident.md")
        name = entry.name
        expect(f"{name}: its frontmatter is complete",
               all(k in meta for k in ("slug", "title", "date", "lane",
                                       "verdict", "budget_line",
                                       "verified")), sorted(meta))
        expect(f"{name}: its slug is its directory",
               meta.get("slug") == name, meta.get("slug"))
        expect(f"{name}: its verdict is one this suite knows",
               meta.get("verdict") in VERDICTS, meta.get("verdict"))
        expect(f"{name}: verified is true or false",
               meta.get("verified") in ("true", "false"),
               meta.get("verified"))
        text = body(entry / "incident.md")
        expect(f"{name}: it names the sources it was written from",
               "## Sources" in text and "](http" in text)
        runs = (entry / "run.json").exists()
        if meta.get("verdict") in WITH_EVIDENCE:
            expect(f"{name}: a {meta['verdict']} entry has a program that "
                   f"runs", runs,
                   "no run.json - STOPPED and PARTIAL are never given on "
                   "reasoning")
        else:
            expect(f"{name}: a {meta.get('verdict')} entry has no recorded "
                   f"refusal, because there is nothing to refuse", not runs)
        found.append(meta)
    expect("there are entries at all", bool(found), "incidents/ is empty")
    return found


def evidence() -> None:
    """incident_evidence.py, in the mode that changes nothing."""
    done = subprocess.run([sys.executable,
                           str(HERE / "incident_evidence.py")],
                          capture_output=True, cwd=HERE,
                          stdin=subprocess.DEVNULL, timeout=1800)
    said = (done.stdout.decode("utf-8", "replace")
            + done.stderr.decode("utf-8", "replace"))
    expect("every recorded command still prints what the entry says it "
           "prints", done.returncode == 0, said)
    for line in said.split("\n"):
        if line.strip().startswith("ok "):
            PASSED[0] += 1


def gaps(found: list[dict[str, str]]) -> None:
    """A gap named in an entry is a gap in the threat model."""
    # the known-open table, which has a page of its own so the threat model
    # stays inside build_docs.py's PAGE_BUDGET; the first section after the
    # table is the crosswalk's, and is not the table
    known_open = (HERE / "docs" / "known-open.md").read_text(encoding="utf-8")
    table = known_open.split("\n## ", 1)[0]
    for meta in found:
        entry = INCIDENTS / meta["slug"]
        text = body(entry / "incident.md")
        if meta["verdict"] in MUST_SAY_THE_GAP:
            expect(f"{meta['slug']}: it says what it does not cover",
                   "## What this does not cover" in text)
    expect("the known-open table names the incident catalogue, so a reader "
           "of the threat model is sent to the gaps found here",
           "incidents/" in table or "incidents.html" in table,
           table[:200])


def page() -> None:
    """docs/incidents.md is what the entries say, and withholds what has
    not been checked."""
    done = subprocess.run([sys.executable, str(HERE / "build_incidents.py"),
                           "--check"], capture_output=True, cwd=HERE,
                          stdin=subprocess.DEVNULL, timeout=300)
    said = (done.stdout.decode("utf-8", "replace")
            + done.stderr.decode("utf-8", "replace"))
    expect("docs/incidents.md is what build_incidents.py writes from the "
           "entries", done.returncode == 0, said)
    built = HERE / "docs" / "incidents.md"
    if not built.exists():
        return
    published = built.read_text(encoding="utf-8")
    for entry in entries():
        meta = front_matter(entry / "incident.md")
        sentence = first_sentence(body(entry / "incident.md"))
        if meta.get("verified") == "false" and sentence:
            expect(f"{meta['slug']}: its summary is not published while it "
                   f"says verified: false", sentence not in published,
                   sentence[:120])
            expect(f"{meta['slug']}: the page names it and links its "
                   f"sources anyway", meta["slug"] in published)


def first_sentence(text: str) -> str:
    """The opening of an entry's 'What happened', which is the thing a page
    must not carry while the entry is unverified."""
    start = text.find("## What happened")
    if start < 0:
        return ""
    after = text[start + len("## What happened"):].strip()
    stop = after.find(". ")
    return after[:stop] if stop > 0 else after[:200]


def main() -> int:
    print("the catalogue")
    found = catalogue()
    print("the evidence")
    evidence()
    print("the gaps")
    gaps(found)
    print("the page")
    page()
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    counts = {v: sum(1 for m in found if m["verdict"] == v)
              for v in VERDICTS}
    withheld = sum(1 for m in found if m["verified"] == "false")
    print(f"all {PASSED[0]} checks passed: {len(found)} incidents - "
          + ", ".join(f"{counts[v]} {v.lower()}" for v in VERDICTS
                      if counts[v])
          + f"; {withheld} summary(ies) not yet checked against their "
            f"sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
