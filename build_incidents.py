#!/usr/bin/env python3
"""docs/incidents.md, generated from incidents/.

    python build_incidents.py              write it and say what changed
    python build_incidents.py --check      fail if it is not what is here

Each directory under incidents/ holds one entry: `incident.md` with a
frontmatter block, the sources it was written from, and - for a verdict of
STOPPED or PARTIAL - the program, the command and the recorded refusal that
`incident_evidence.py` produced. This reads those entries and writes one page:
the counts by verdict, then every entry with its verdict, the one line of
budget that does the work, and its sources.

WHAT IT REFUSES TO PUBLISH. An entry whose frontmatter says
`verified: false` has been written from its sources but not checked against
them by a person, and its summary is not published. The page counts it,
names it, links its sources and says the summary is withheld; the prose
stays in the repository until someone reads the sources and sets the flag.
The count of withheld entries is printed by this script and shown at the
top of the page, so that "nothing is withheld" and "everything is withheld"
cannot look the same.

The page is deliberately an index. It carries no program text and no
receipt: those are files under incidents/, where they can be run. A page of
the documentation site may hold 100,000 bytes (build_docs.py's PAGE_BUDGET)
and an index of a hundred incidents still fits inside it.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from incident_evidence import body, entries, front_matter  # noqa: E402

OUT = HERE / "docs" / "incidents.md"
REPO = "https://github.com/gowrishankar-infra/sabline-lang"
TREE = f"{REPO}/blob/main/incidents"
VERDICTS = ("STOPPED", "PARTIAL", "NOT COVERED", "UNVERIFIED",
            "OUT OF SCOPE")
COUNTED = ("STOPPED", "PARTIAL", "NOT COVERED", "UNVERIFIED")
MEANING = {
    "STOPPED": "the shape, written in Sabline and run under a budget "
               "granting what the task needs, is refused - and the refusal "
               "is recorded and re-run on every push",
    "PARTIAL": "part of the shape is refused and part is not; both halves "
               "are recorded",
    "NOT COVERED": "nothing in Sabline addresses this shape",
    "UNVERIFIED": "it may be covered; no repro was built, so nothing is "
                  "claimed",
    "OUT OF SCOPE": "prompt injection where no code ran - listed so the "
                    "boundary is visible, not counted as a gap",
}


def read() -> list[dict[str, Any]]:
    """Every entry, by slug, with its frontmatter, its sections and whether
    it has evidence that runs."""
    found = []
    for entry in entries():
        meta = front_matter(entry / "incident.md")
        for key in ("slug", "title", "date", "lane", "verdict",
                    "budget_line", "verified"):
            if key not in meta:
                raise SystemExit(f"{entry.name}: no {key} in its frontmatter")
        if meta["slug"] != entry.name:
            raise SystemExit(f"{entry.name}: its slug says {meta['slug']!r}")
        if meta["verdict"] not in VERDICTS:
            raise SystemExit(f"{entry.name}: {meta['verdict']!r} is not a "
                             f"verdict ({', '.join(VERDICTS)})")
        if meta["verified"] not in ("true", "false"):
            raise SystemExit(f"{entry.name}: verified is "
                             f"{meta['verified']!r}, not true or false")
        sections = split(body(entry / "incident.md"))
        if "What happened" not in sections:
            raise SystemExit(f"{entry.name}: no 'What happened' section")
        if "Sources" not in sections:
            raise SystemExit(f"{entry.name}: no 'Sources' section - an "
                             f"incident without one does not go in")
        one: dict[str, Any] = dict(meta)
        one["sections"] = sections
        one["runs"] = (entry / "run.json").exists()
        found.append(one)
    return sorted(found, key=lambda e: (VERDICTS.index(e["verdict"]),
                                        e["date"], e["slug"]))


def split(text: str) -> dict[str, str]:
    """{heading: what is under it}, for the `## ` headings of an entry."""
    sections: dict[str, str] = {}
    heading = ""
    for line in text.split("\n"):
        if line.startswith("## "):
            heading = line[3:].strip()
            sections[heading] = ""
        elif heading:
            sections[heading] += line + "\n"
    return {k: v.strip() for k, v in sections.items()}


def page(found: list[dict[str, Any]]) -> str:
    """docs/incidents.md."""
    withheld = [e for e in found if e["verified"] == "false"]
    counts = {v: sum(1 for e in found if e["verdict"] == v)
              for v in VERDICTS}
    total = sum(counts[v] for v in COUNTED)
    out: list[str] = []
    w = out.append

    w("# Incidents")
    w("")
    w("Real, publicly reported incidents from 2023 onward in the lane "
      "Sabline is written for: AI agent failures and software supply-chain "
      "attacks where code ran with more authority than it should have. For "
      "each one, whether a program of the same **shape**, written in "
      "Sabline and run under a budget, is refused.")
    w("")
    w("> [!NOTE]")
    w("> **These are the shapes of the attacks. This is not a claim that "
      "adopting Sabline would have prevented the real events.** None of "
      "them involved a Sabline program. Every one happened in a language, "
      "a package manager, a build system or an agent framework that Sabline "
      "neither runs nor bounds. What an entry shows is narrower and "
      "checkable: given the same shape, here is the program, the command, "
      "what the runtime actually printed, and the one line of budget that "
      "did the work. Where nothing here addresses the shape, the entry says "
      "so, and the reason is in the "
      "[known-open table](known-open.html).")
    w("")

    w("## The counts")
    w("")
    w(f"{total} incidents in scope, and {counts['OUT OF SCOPE']} listed as "
      f"out of scope. Every entry links the report it was written from.")
    w("")
    w("| Verdict | Count | What it means |")
    w("|---|---|---|")
    for verdict in VERDICTS:
        w(f"| `{verdict}` | {counts[verdict]} | {MEANING[verdict]} |")
    w("")
    if withheld:
        w("> [!KNOWN-OPEN]")
        w(f"> **{len(withheld)} of {len(found)} summaries have not been "
          f"checked against their sources by a person**, so they are not "
          f"published. Each is named below with its verdict and its "
          f"sources, and its summary is withheld until someone reads those "
          f"sources and sets `verified: true` in the entry. The counts "
          f"above are of entries, not of checked entries. What is published "
          f"for a withheld entry is the part a machine checks - the verdict, "
          f"which `check_incidents.py` re-runs, and the links - and what is "
          f"withheld is the part only a person can check: the account of "
          f"what happened.")
        w("")
    else:
        w("> [!NOTE]")
        w("> Every summary below has been checked against its sources by a "
          "person. An entry is not published until that is done.")
        w("")
    w("A verdict is never `STOPPED` on reasoning: `check_incidents.py` "
      "re-runs every recorded command on every push, and an entry whose "
      "program stops refusing fails the build before a release is made "
      "from it.")
    w("")

    w("## How these were chosen")
    w("")
    w("This is a selection, not a survey. An incident is here only if it is "
      "**from 2023 onward**, **in the lane** - code that ran with more "
      "authority than it should have - and **backed by a primary source**: a "
      "vendor post-mortem, a CVE record, or the researcher's own write-up. "
      "Nothing goes in without one.")
    w("")
    w("**These are not all the incidents in this lane, and the counts are not "
      "a measurement of the field.** A verdict count is a count of what is in "
      "this catalogue, not a claim about how common each shape is. What is "
      "left out on purpose: anything before 2023; prompt injection where no "
      "code ran, which is `OUT OF SCOPE` rather than a gap and is why "
      "EchoLeak and CamoLeak are listed that way; and anything that cannot be "
      "sourced to a primary report - one incident, an agent that deleted a "
      "production database (Replit, July 2025), was dropped for exactly that "
      "reason.")
    w("")

    for verdict in VERDICTS:
        here = [e for e in found if e["verdict"] == verdict]
        if not here:
            continue
        w(f"## {verdict}")
        w("")
        w(MEANING[verdict][0].upper() + MEANING[verdict][1:] + ".")
        w("")
        for entry in here:
            w(f"### {entry['title']}")
            w("")
            line = (f"`{entry['budget_line']}`"
                    if entry["budget_line"] != "none"
                    else "no budget line: nothing here refuses it")
            w(f"{entry['date']} - "
              f"[incidents/{entry['slug']}/]({TREE}/{entry['slug']}/) - "
              f"the line that does the work: {line}")
            w("")
            if entry["verified"] == "false":
                w("*The summary of this incident is written and not yet "
                  "checked against the sources below, so it is not "
                  "published. It is in "
                  f"[incidents/{entry['slug']}/incident.md]"
                  f"({TREE}/{entry['slug']}/incident.md).*")
            else:
                w(entry["sections"].get("What happened", "").strip())
            w("")
            w(entry["sections"]["Sources"].strip())
            w("")

    w("## Adding one, and checking one")
    w("")
    w(f"The entries live in [incidents/]({TREE}/) in this repository, one "
      f"directory each, with `incidents/TEMPLATE.md` for a new one. "
      f"`incidents/README.md` gives the rules: what counts as a source, "
      f"what each verdict means, and exactly what is normalised in a "
      f"recorded refusal so the same bytes appear on every machine. "
      f"`python incident_evidence.py` re-runs the evidence, "
      f"`python check_incidents.py` is what CI runs, and "
      f"`python build_incidents.py` writes this page.")
    w("")
    return "\n".join(out)


def main(argv: list[str]) -> int:
    found = read()
    text = page(found)
    withheld = [e for e in found if e["verified"] == "false"]
    if "--check" in argv:
        if not OUT.exists():
            print("docs/incidents.md has not been written "
                  "(python build_incidents.py)")
            return 1
        if OUT.read_text(encoding="utf-8").replace("\r\n", "\n") != text:
            print("docs/incidents.md is not what incidents/ says it should "
                  "be (python build_incidents.py)")
            return 1
        print(f"docs/incidents.md is current: {len(found)} entries, "
              f"{len(withheld)} summaries withheld")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote docs/incidents.md: {len(found)} entries, "
          f"{len(text)} bytes of Markdown")
    for entry in withheld:
        print(f"  withheld  {entry['slug']}  (verified: false)")
    if withheld:
        print(f"{len(withheld)} summary(ies) not published: they have not "
              f"been checked against their sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
