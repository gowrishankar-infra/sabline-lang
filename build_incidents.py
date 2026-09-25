#!/usr/bin/env python3
"""docs/incidents.md, generated from incidents/ - and, once their entries
are checked, a page for each incident and the flagship page (8.7).

    python build_incidents.py              write them and say what changed
    python build_incidents.py --check      fail if they are not what is here
    python build_incidents.py --drafts DIR every page, checked or not, into
                                           DIR, to read before verifying

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

ONE PAGE PER INCIDENT, AND THE FLAGSHIP (8.7). docs/incident-<slug>.md is
the whole entry - what happened, the program, the command, the refusal as
recorded, the line of budget, what it does not cover, the sources - titled
with the name people actually use for the incident (incidents/names.json,
from plan/findability-research/phrasings.md): "Shai-Hulud", "the xz
backdoor", "slopsquatting". docs/replayed.md, the flagship, is every
incident on one page with its verdict. The same rule holds them back as
holds back a summary above, and harder: an incident's page is written only
once its entry says `verified: true`, and the flagship only once every entry
does, since it summarises all of them. Until then neither exists in docs/,
so neither is published; --drafts writes them elsewhere to be read, and
--check fails if docs/ holds one it should not, or lacks one it should.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from incident_evidence import body, entries, front_matter  # noqa: E402

OUT = HERE / "docs" / "incidents.md"
NAMES = HERE / "incidents" / "names.json"
FLAGSHIP = "replayed.md"
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


def names() -> dict[str, dict[str, Any]]:
    import json
    known: dict[str, dict[str, Any]] = json.loads(
        NAMES.read_text(encoding="utf-8"))["names"]
    return known


def programs(slug: str) -> list[str]:
    """The entry's own .vel files, the programs its recorded run uses."""
    return sorted(q.name for q in (HERE / "incidents" / slug).glob("*.vel"))


def incident_page(entry: dict[str, Any], name: dict[str, Any]) -> str:
    """docs/incident-<slug>.md: one incident, whole, under its common name."""
    slug = entry["slug"]
    s = entry["sections"]
    out: list[str] = []
    w = out.append
    w(f"# {name['name']}, replayed in Sabline")
    w("")
    what = s["What happened"].split("\n\n")[0].replace("\n", " ")
    short = what if len(what) <= 150 else what[:147].rsplit(" ", 1)[0] + " ..."
    w(f"<!-- description: {entry['verdict']}: {short} -->")
    w("")
    also = (f" Also called {', '.join(name['also'])}." if name["also"]
            else "")
    w(f"**{entry['title']}**, {entry['date']}.{also} "
      f"([The name in use]({name['in_use']}).) Verdict: "
      f"**`{entry['verdict']}`** - {MEANING[entry['verdict']]}.")
    w("")
    w("> [!NOTE]")
    w("> **This is the shape of the attack, not a claim that Sabline would "
      "have prevented the real event.** The real one happened in a language, "
      "a package manager, a build system or an agent framework that Sabline "
      "neither runs nor bounds. What this page shows is narrower and "
      "checkable: the same shape written in Sabline, the command, what the "
      "runtime printed, and the one line of budget that did the work - or, "
      "where nothing here addresses the shape, that.")
    w("")
    for heading in ("What happened", "The shape, in Sabline",
                    "The one line that does the work",
                    "What this does not cover"):
        if heading in s:
            w(f"## {heading}")
            w("")
            w(s[heading])
            w("")
    for vel in programs(slug):
        source = (HERE / "incidents" / slug / vel).read_text(encoding="utf-8")
        w(f"### {vel}")
        w("")
        w("```vel")
        w(source.rstrip("\n"))
        w("```")
        w("")
    refusal = HERE / "incidents" / slug / "refusal.txt"
    if refusal.exists():
        w("## What the runtime printed")
        w("")
        w("Recorded by `incident_evidence.py`, and re-run by "
          "`check_incidents.py` on every push:")
        w("")
        w("```text")
        w(refusal.read_text(encoding="utf-8").rstrip("\n"))
        w("```")
        w("")
    w("## Sources")
    w("")
    w(s["Sources"])
    w("")
    w(f"The entry, its program and its recorded run are in "
      f"[incidents/{slug}/]({TREE}/{slug}/). Every incident, with its "
      f"verdict, is in [the catalogue](incidents.md).")
    w("")
    return "\n".join(out)


def flagship_page(found: list[dict[str, Any]],
                  known: dict[str, dict[str, Any]]) -> str:
    """docs/replayed.md: every incident on one page, what nothing here
    addresses first."""
    ran = [e for e in found if e["runs"]]
    counts = {v: sum(1 for e in found if e["verdict"] == v) for v in VERDICTS}
    out: list[str] = []
    w = out.append
    w(f"# We replayed {len(ran)} real incidents in Sabline")
    w("")
    w(f"<!-- description: {len(found)} publicly reported incidents, each "
      f"written as a Sabline program of the same shape: {counts['STOPPED']} "
      f"refused, {counts['PARTIAL']} partly, {counts['NOT COVERED']} "
      "nothing here addresses. -->")
    w("")
    w(f"{len(found)} publicly reported incidents from 2023 onward in which code "
      f"ran with more authority than it should have. For {len(ran)} of them "
      f"there is a Sabline program of the same shape, run under a budget, "
      f"and a recorded result: {counts['STOPPED']} refused outright, "
      f"{counts['PARTIAL']} refused in part. For {counts['NOT COVERED']}, "
      f"nothing in Sabline addresses the shape, and {counts['OUT OF SCOPE']} "
      "are prompt injection where no code ran.")
    w("")
    w("> [!NOTE]")
    w("> **None of these involved a Sabline program, and this is not a claim "
      "that adopting Sabline would have prevented any of them.** Each replay "
      "is the *shape* of the "
      "attack, written in Sabline and run; the real events happened in "
      "languages, package managers and agent frameworks Sabline neither runs "
      "nor bounds. Every refusal below is re-run on every push, and fails "
      "the build if it stops.")
    w("")
    order = ("NOT COVERED", "PARTIAL", "STOPPED", "OUT OF SCOPE")
    heads = {"NOT COVERED": "What nothing here addresses",
             "PARTIAL": "Refused in part",
             "STOPPED": "Refused", "OUT OF SCOPE": "Out of scope"}
    for verdict in order:
        here = [e for e in found if e["verdict"] == verdict]
        if not here:
            continue
        w(f"## {heads[verdict]}")
        w("")
        w(MEANING[verdict][0].upper() + MEANING[verdict][1:] + ".")
        w("")
        w("| Incident | Date | The line that does the work |")
        w("|---|---|---|")
        for e in here:
            line = (f"`{e['budget_line']}`" if e["budget_line"] != "none"
                    else "none")
            w(f"| [{known[e['slug']]['name']}](incident-{e['slug']}.md) | "
              f"{e['date']} | {line} |")
        w("")
    w("## Check it yourself")
    w("")
    w("`python incident_evidence.py` re-runs every program and writes what it "
      "printed; `python check_incidents.py` is what CI runs. The entries, "
      f"their sources and their programs are in [incidents/]({TREE}/).")
    w("")
    return "\n".join(out)


def gated(found: list[dict[str, Any]]) -> dict[str, str]:
    """{docs/ file name: text} for every page the verified flags allow."""
    known = names()
    missing = [e["slug"] for e in found if e["slug"] not in known]
    if missing:
        raise SystemExit(f"incidents/names.json has no name for: "
                         f"{', '.join(missing)}")
    pages = {f"incident-{e['slug']}.md": incident_page(e, known[e["slug"]])
             for e in found if e["verified"] == "true"}
    if found and all(e["verified"] == "true" for e in found):
        pages[FLAGSHIP] = flagship_page(found, known)
    return pages


def every_page(found: list[dict[str, Any]]) -> dict[str, str]:
    """Every page as if every entry were checked: the drafts."""
    known = names()
    pages = {f"incident-{e['slug']}.md": incident_page(e, known[e["slug"]])
             for e in found}
    pages[FLAGSHIP] = flagship_page(found, known)
    return pages


def main(argv: list[str]) -> int:
    found = read()
    text = page(found)
    if "--drafts" in argv:
        where = Path(argv[argv.index("--drafts") + 1])
        where.mkdir(parents=True, exist_ok=True)
        for name, body_ in every_page(found).items():
            (where / name).write_text(body_, encoding="utf-8", newline="\n")
        print(f"wrote {len(found) + 1} draft pages to {where} - not "
              "published; docs/ holds only the ones checked entries allow")
        return 0
    allowed = gated(found)
    every_page(found)          # the drafts render, whatever is checked
    present = {q.name for q in (OUT.parent).glob("incident-*.md")}
    if (OUT.parent / FLAGSHIP).exists():
        present.add(FLAGSHIP)
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
        early = sorted(present - set(allowed))
        if early:
            print("docs/ holds a page for an incident no person has checked: "
                  + ", ".join(early) + " - it would be published "
                  "(python build_incidents.py removes it)")
            return 1
        stale = sorted(n for n, body_ in allowed.items()
                       if not (OUT.parent / n).exists()
                       or (OUT.parent / n).read_text(encoding="utf-8")
                       .replace("\r\n", "\n") != body_)
        if stale:
            print(", ".join(stale) + " not current (python build_incidents.py)")
            return 1
        print(f"docs/incidents.md is current: {len(found)} entries, "
              f"{len(withheld)} summaries withheld; {len(allowed)} incident "
              f"page(s) published, {len(found) + 1 - len(allowed)} held "
              "back until their entries are checked")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    for name in sorted(present - set(allowed)):
        (OUT.parent / name).unlink()
        print(f"  removed docs/{name}: its entry is not checked")
    for name, body_ in allowed.items():
        (OUT.parent / name).write_text(body_, encoding="utf-8", newline="\n")
        print(f"  wrote docs/{name}")
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
