#!/usr/bin/env python3
"""docs/competitors.md and its two evidence pages, written from
benchmark/competitors/results.json.

    python build_competitors_page.py            write all three
    python build_competitors_page.py --check    fail if any is not current
    python build_competitors_page.py --self-test   the claim checks, shown to fail

The first page publishes the table - the date, each runtime's version, the
scenarios, every row with its verdict for all seven tools - and says, before
anything else, where a competitor is ahead. Two more hold every cell's
evidence line, which does not fit on one page within the site's page
budget and is split, never trimmed. benchmark/compete.py records the
numbers; this only renders them, so no page can drift from the record. What is written here as prose is
about the design of the tools and the benchmark, and is checked against the
record where it names a row: a claim about a row that the record does not
bear out stops the build.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
COMP = HERE / "benchmark" / "competitors"
RESULTS = COMP / "results.json"
EXPECT = COMP / "expectations.json"
OUT = HERE / "docs" / "competitors.md"
EVIDENCE = (HERE / "docs" / "competitors-evidence-1.md",
            HERE / "docs" / "competitors-evidence-2.md")
TOOLS = ("sabline", "deno", "python", "wasi", "starlark", "sandbox", "camel")
RIVALS = ("deno", "wasi", "starlark", "sandbox", "camel")
SHORT = {"caught-before-run": "before", "caught-during-run": "during",
         "missed": "**missed**", "not-applicable": "clean",
         "false-positive": "**false positive**", "not-run": "NOT RUN",
         "tool-absent": "NOT RUN"}
RANK = {"caught-before-run": 2, "caught-during-run": 1, "missed": 0}
REPO = "https://github.com/gowrishankar-infra/sabline-lang"


def v(row: dict[str, Any], tool: str) -> str:
    return str(row["cells"][tool]["verdict"])


def compare_row(row: dict[str, Any], tool: str) -> str:
    """ahead / behind / tie / timing-ahead / timing-behind / n/a: the
    competitor against Sabline on one row."""
    a, s = v(row, tool), v(row, "sabline")
    if "not-run" in (a, s):
        return "n/a"
    if not row["dangerous"]:
        if a == s:
            return "tie"
        return "ahead" if s == "false-positive" else "behind"
    ra, rs = RANK[a], RANK[s]
    if ra == rs:
        return "tie"
    if min(ra, rs) >= 1:                   # both caught: only the timing differs
        return "timing-ahead" if ra > rs else "timing-behind"
    return "ahead" if ra > rs else "behind"


UNEARNED = ("Not a refusal", "Not like-for-like: the task's own request",
            "Stopped by the deadline")


def unearned(row: dict[str, Any], tool: str) -> bool:
    """A catch whose own row note says the danger was not what was refused."""
    cell = row["cells"][tool]
    return (str(cell["verdict"]).startswith("caught")
            and any(n.startswith(UNEARNED) for n in cell["notes"]))


def cell_text(row: dict[str, Any], tool: str) -> str:
    text = SHORT[v(row, tool)]
    if unearned(row, tool):
        text += " †"
    if tool != "sabline":
        c = compare_row(row, tool)
        if c in ("ahead", "timing-ahead"):
            text += " ▲"
    return text


def ids(rows: list[dict[str, Any]]) -> str:
    return ", ".join(r["id"] for r in rows) if rows else "none"


def write_pages(r: dict[str, Any],
                expect: dict[str, Any]) -> tuple[str, str, str]:
    rows: list[dict[str, Any]] = r["programs"]
    labels: dict[str, str] = r["labels"]
    meta = r["meta"]
    rt = meta["runtimes"]
    dangerous = [x for x in rows if x["dangerous"]]
    controls = [x for x in rows if not x["dangerous"]]
    w: list[str] = []
    p = w.append

    def version(tool: str) -> str:
        info = rt[tool]
        if "absent" in info:
            return f"NOT RUN ({info['absent']})"
        extra = f", {info['detail']}" if info.get("detail") else ""
        return f"{info['version']}{extra}"

    p("# Competitors")
    p("")
    p("Sabline's [comparison benchmark](https://sabline.dev/index.html) - "
      f"{len(rows)} programs, {len(dangerous)} with one defect and "
      f"{len(controls)} correct, in {len(r['categories'])} categories - run "
      "through five tools that claim part of what Sabline claims, each in "
      "its own real runtime, beside Sabline and unsandboxed Python. Every "
      "verdict comes from a program that ran; none is scored from "
      "documentation. This page is generated from "
      "`benchmark/competitors/results.json`, which `benchmark/compete.py` "
      "records and a CI leg re-derives on every push: a verdict or an "
      "evidence line that moves fails the build.")
    p("")
    p("> [!NOTE]")
    p(f"> **Measured** {meta['date']} on {meta['platform']}. "
      + " · ".join(f"**{labels[t]}** {version(t)}" for t in TOOLS)
      + f". A {meta['timeout_s']} s deadline for every tool but CaMeL, "
      f"which gets 30 s of interpretation, and a {meta['memory_mb']} MB cap "
      "where the runtime can take one "
      "([how each column is run](#how-each-column-was-run)).")
    p("")

    # ---- losses first ---------------------------------------------------------
    p("## Where a competitor is ahead")
    p("")
    ahead = [(x, t) for x in rows for t in RIVALS
             if compare_row(x, t) == "ahead"]
    timing = [(x, t) for x in rows for t in RIVALS
              if compare_row(x, t) == "timing-ahead"]
    if ahead:
        p("On these rows a competitor did better than Sabline - caught what "
          "Sabline missed, or left a correct program alone that Sabline "
          "stopped:")
        p("")
        for x, t in ahead:
            p(f"- **{x['id']}** ({x['name']}): {labels[t]} "
              f"{v(x, t)}, Sabline {v(x, 'sabline')}.")
        p("")
    else:
        p(f"**On this benchmark's {len(rows)} rows, no competitor is ahead "
          "of Sabline on any row** - none caught a program Sabline missed, "
          "and none left alone a correct program Sabline stopped. "
          "plan/8.7.md says what that means, and it is repeated here "
          "because it is the most important sentence on the page: a table "
          "where Sabline wins everything is evidence that the benchmark is "
          "wrong, not that Sabline is good. The benchmark was written by "
          "this project, around what this project does. "
          "[What it is missing](#what-the-benchmark-is-missing) lists the "
          "scenarios where each competitor should win and where Sabline "
          "should lose; none of them is in the corpus yet.")
        p("")
    if timing:
        p("Where both caught a program and the competitor did it *earlier* - "
          "before running, where Sabline stopped it while running:")
        p("")
        for x, t in timing:
            p(f"- **{x['id']}** ({x['name']}): {labels[t]} "
              f"{v(x, t)}, Sabline {v(x, 'sabline')}.")
        p("")
    p("Against Sabline, row by row. *Tie* is the same verdict; *earlier* "
      "and *later* mean both caught the program, one before running and one "
      "while running - a difference of timing, not of outcome.")
    p("")
    p("| Competitor | Ahead | Earlier | Tie | Later | Behind |")
    p("|---|---:|---:|---:|---:|---:|")
    for t in RIVALS:
        cs = [compare_row(x, t) for x in rows]
        p(f"| {labels[t]} | {cs.count('ahead')} | {cs.count('timing-ahead')}"
          f" | {cs.count('tie')} | {cs.count('timing-behind')} | "
          f"{cs.count('behind')} |")
    p("")
    both_missed = [x for x in dangerous if all(
        v(x, t) == "missed" for t in TOOLS)]
    p(f"Every tool missed {ids(both_missed)}: the benchmark put them there "
      "because nothing can catch them (a loop that stops one item early "
      "with no contract; a program that only prints a shell command).")
    p("")

    p("### Where each is stronger by design")
    p("")
    p("A score on this corpus is not what any of these tools is for. What "
      "each is actually built to do, and where that makes it stronger than "
      "Sabline whatever this table says:")
    p("")
    for t, text in BY_DESIGN.items():
        p(f"- **{labels[t]}.** {text}")
    p("")

    # ---- the table --------------------------------------------------------------
    p("## The table")
    p("")
    p("Per category: caught before running / caught while running / missed, "
      "and for the control rows, clean / false positive. The per-program "
      "rows, and every note on a row that is not like-for-like, follow.")
    p("")
    p("| Category | " + " | ".join(labels[t] for t in TOOLS) + " |")
    p("|---|" + "---|" * len(TOOLS))
    for cat in r["categories"]:
        mine = [x for x in rows if x["category"] == cat["number"]]
        cells = []
        for t in TOOLS:
            c = cat["tools"][t]
            if c["not-run"] or c.get("tool-absent"):
                cells.append("NOT RUN")
                continue
            parts = []
            if any(x["dangerous"] for x in mine):
                parts.append(f"{c['caught-before-run']}/"
                             f"{c['caught-during-run']}/{c['missed']}")
            if any(not x["dangerous"] for x in mine):
                parts.append(f"{c['not-applicable']} clean"
                             + (f", **{c['false-positive']} FP**"
                                if c["false-positive"] else ""))
            cells.append("; ".join(parts))
        p(f"| {cat['number']}. {cat['title']} | " + " | ".join(cells) + " |")
    tot = r["totals"]
    p("| **Caught, of " + str(len(dangerous)) + "** | " + " | ".join(
        f"**{tot[t]['caught-before-run'] + tot[t]['caught-during-run']}** "
        f"({tot[t]['caught-before-run']} before)" for t in TOOLS) + " |")
    p("| **False positives, of " + str(len(controls)) + "** | " + " | ".join(
        f"**{tot[t]['false-positive']}**" for t in TOOLS) + " |")
    p("| **Catches the row itself says were not a refusal** | " + " | ".join(
        str(sum(1 for x in dangerous if unearned(x, t))) for t in TOOLS)
      + " |")
    p("")
    p("The last row counts catches the benchmark's rule credits but whose "
      "row note says the program was stopped by something other than a "
      "refusal of its danger - a runtime with no network failing the task's "
      "own request, an interpreter defect, a deadline reached by a slow "
      "interpreter, a crash of a broken program. Read each column's catches "
      "net of it.")
    p("")

    p("## Every scenario")
    p("")
    p("▲ marks a competitor that did better than Sabline on the row (or "
      "caught it earlier); † marks a catch whose row note says it was not "
      "a refusal of the danger. The last column is where a row is not "
      "like-for-like - a different threat model, a construct a runtime "
      "lacks, a catch that came from a failure rather than a refusal - "
      "stated in the row, not in a footnote. Every cell's evidence line is "
      "on the evidence pages ([part 1](competitors-evidence-1.md), "
      "[part 2](competitors-evidence-2.md)); the commands and "
      "their output are in "
      f"[results.json]({REPO}/blob/main/benchmark/competitors/results.json).")
    p("")
    for cat in r["categories"]:
        mine = [x for x in rows if x["category"] == cat["number"]]
        p(f"### {cat['number']}. {cat['title']}")
        p("")
        p("| # | Program | " + " | ".join(labels[t] for t in TOOLS)
          + " | Not like-for-like |")
        p("|---|---|" + "---|" * len(TOOLS) + "---|")
        for x in mine:
            notes = []
            for t in TOOLS:
                for n in x["cells"][t]["notes"] + PAGE_NOTES.get(
                        (x["id"], t), []):
                    notes.append(f"*{labels[t]}:* {n}")
            name = x["name"] + ("" if x["dangerous"] else " (control)")
            p(f"| {x['id']} | `{name}` | "
              + " | ".join(cell_text(x, t) for t in TOOLS) + " | "
              + ("<br>".join(n.replace("|", "\\|") for n in notes) or "-")
              + " |")
        p("")

    # ---- countermeasures 1 and 2 ------------------------------------------------
    p("## Expected, and what happened")
    p("")
    p("`benchmark/competitors/expectations.json` was committed before the "
      "harness ran anything (countermeasure 1 in plan/8.7.md). Here it is "
      "beside the record, for the four columns it predicted; *as expected* "
      "means every dangerous row of the category landed in the predicted "
      "class, and anything else is shown as it happened.")
    p("")
    new = ("wasi", "starlark", "sandbox", "camel")
    p("| Category | " + " | ".join(labels[t] for t in new) + " |")
    p("|---|" + "---|" * len(new))
    for ex in expect["categories"]:
        # the rows the file named as exceptions in advance are held to their
        # own sentence, shown in full, not to the category's class
        excepted = sorted(ex.get("exceptions", {}))
        mine = [x for x in dangerous if x["category"] == ex["number"]
                and x["id"] not in excepted]
        if not mine:
            continue
        cells = []
        for t in new:
            want = str(ex["expect"].get(t, ""))
            got = [SHORT[v(x, t)].strip("*") for x in mine]
            summary = ", ".join(f"{got.count(k)} {k}" for k in sorted(set(got)))
            if want in ("before", "during", "missed") and set(got) == {want}:
                cell = "as expected"
            else:
                cell = f"expected {want}; got {summary}"
            for i in excepted:
                x = next(y for y in rows if y["id"] == i)
                cell += f"; {i} {SHORT[v(x, t)].strip('*')}"
            cells.append(cell)
        p(f"| {ex['number']}. {ex['title']} | " + " | ".join(cells) + " |")
    p("")
    p("The rows named as exceptions in advance, and what the file said of "
      "them: " + "; ".join(
          f"**{i}**: {text}" for ex in expect["categories"]
          for i, text in sorted(ex.get("exceptions", {}).items())) + ".")
    p("")
    p(MISMATCH_NOTE)
    p("")

    p("### Categories no competitor catches")
    p("")
    def earned(x: dict[str, Any], t: str) -> bool:
        return v(x, t).startswith("caught") and not unearned(x, t)

    lone = []
    for cat in r["categories"]:
        mine = [x for x in dangerous if x["category"] == cat["number"]]
        if mine and not any(earned(x, t) for x in mine for t in RIVALS):
            lone.append(cat)
    p("Countermeasure 2: a category that only Sabline catches is either a "
      "real property or a rigged question, and is reviewed before it is "
      "published. A catch whose own row says it was not a refusal is not "
      "counted here. " + (
          "Categories caught by no competitor: " + ", ".join(
              f"{c['number']} ({c['title']})" for c in lone) + "."
          if lone else "Every category is caught by at least one competitor."))
    p("")
    for c in lone:
        p(f"- **{c['number']}. {c['title']}.** "
          + LONE_REVIEW.get(c["number"], "Not yet reviewed."))
    p("")
    only_sabline = [x for x in dangerous
                    if v(x, "sabline").startswith("caught")
                    and not any(earned(x, t) for t in RIVALS)]
    p(f"Rows only Sabline catches: {ids(only_sabline)}.")
    p("")

    for heading, text in PROSE:
        p(f"## {heading}")
        p("")
        p(text.strip())
        p("")

    p("## How each column was run")
    p("")
    p("Each tool gets the narrowest grant that still lets the task's "
      "legitimate work run, derived from the program's `needs` by one rule "
      "per tool, never tuned per program. The full rules, and why this "
      "Python sandbox, are in "
      f"[benchmark/competitors/README.md]({REPO}/blob/main/benchmark/"
      "competitors/README.md).")
    p("")
    p("| Column | Runtime | Grant | Time limit | Memory cap |")
    p("|---|---|---|---|---|")
    for t in TOOLS:
        runtime, grant, limit, cap = COLUMNS[t]
        p(f"| {labels[t]} | {runtime} | {grant} | {limit} | {cap} |")
    p("")
    p("## Reproducing it")
    p("")
    p("    python benchmark/competitors/fetch_runtimes.py   # pinned by SHA-256; builds the Starlark host")
    p("    pip install -r requirements/competitors.txt      # smolagents and CaMeL, pinned all the way down")
    p("    python benchmark/compete.py --check              # every cell, re-derived")
    p("    python benchmark/compete.py --only 13a,14c       # a few cells, printed")
    p("")
    p("Nothing costs money: public downloads, pinned packages, no key, no "
      "model. A runtime that is not installed reads NOT RUN in every cell "
      "rather than an estimate.")
    p("")

    # ---- the evidence pages -----------------------------------------------------
    # every cell's evidence line does not fit one page within the site's
    # budget, so it is split at the category that halves the programs
    cats = r["categories"]
    count = 0
    split = len(cats)
    for i, cat in enumerate(cats):
        count += sum(1 for x in rows if x["category"] == cat["number"])
        if count * 2 >= len(rows):
            split = i + 1
            break
    parts = []
    for part, group in ((1, cats[:split]), (2, cats[split:])):
        e: list[str] = []
        q = e.append
        other = 2 if part == 1 else 1
        q(f"# Competitors: the evidence, part {part}")
        q("")
        q(f"Categories {group[0]['number']} to {group[-1]['number']} of "
          f"[the competitor table](competitors.md) (the rest are in "
          f"[part {other}](competitors-evidence-{other}.md)), measured "
          f"{meta['date']}: every cell's verdict and the evidence line the "
          "harness wrote from what ran. The commands each cell ran, the "
          "input it was given and what it printed are in "
          f"[results.json]({REPO}/blob/main/benchmark/competitors/"
          "results.json), with the scratch directory written as `<workdir>` "
          "and the two listener ports as `<port>` (granted) and "
          "`<other-port>` (not).")
        q("")
        for cat in group:
            mine = [x for x in rows if x["category"] == cat["number"]]
            q(f"## {cat['number']}. {cat['title']}")
            q("")
            for x in mine:
                q(f"**{x['id']}** `{x['name']}` - {x['description']}")
                q("")
                for t in TOOLS:
                    c = x["cells"][t]
                    q(f"- {labels[t]}: **{c['verdict']}** - "
                      + c["evidence"].replace("|", "\\|"))
                q("")
        parts.append("\n".join(e))
    return "\n".join(w), parts[0], parts[1]


# ---- prose: about the tools and the benchmark, not about a number -----------

BY_DESIGN = {
    "deno": "A permission system for a language people already write, "
            "enforced by the runtime at the moment of the call, for "
            "JavaScript and TypeScript and everything npm ships. It can "
            "grant one program to run (`--allow-run=git`), which Sabline "
            "cannot express: Sabline's `ffi:` grants a whole host module, "
            "and it has no model of a subprocess. It needs no new language "
            "and no rewrite.",
    "wasi": "A boundary made by the virtual machine, not by the language: "
            "whatever code runs inside - interpreted Python, compiled C, a "
            "native extension - reaches only the handles the host passed in, "
            "one by one. Sabline's first guard is its own interpreter, with "
            "OS confinement (8.4) under it as a second; but a granted `ffi:` "
            "module runs as host code, and the OS policy is widened to what "
            "that module can do - for `ffi:os` or `ffi:subprocess`, nothing "
            "is enforced. Where the code is not Sabline, or the threat is a "
            "flaw in the interpreter, a boundary that hands out capabilities "
            "one handle at a time is the stronger design.",
    "starlark": "Determinism and termination by construction: no `while`, "
                "no recursion, no I/O but what the host predeclares, and "
                "the same result on every run. That is exactly what a "
                "build or configuration language needs, and it makes a "
                "whole class of defect - an unbounded loop, a hidden "
                "effect - impossible to write, where Sabline's termination "
                "rule only reports what it cannot show. The cost is that "
                "programs that need an unbounded loop cannot be written.",
    "sandbox": "Nothing new to learn: the model writes the Python it "
               "already writes, and the agent framework runs it. Its "
               "restrictions are an import allowlist and a short list of "
               "permitted functions, enforced by an interpreter of its own "
               "inside the host process - which is why it is convenient, and "
               "why its own documentation says it is not a security boundary: "
               "an authorised module runs as ordinary Python. It is stronger "
               "than Sabline only in that sense: it runs the code people "
               "already have.",
    "camel": "Information flow per value: every value carries where it came "
             "from and who may read it, and a policy decides at each tool "
             "call whether *this data* may go *there*. That stops the "
             "laundering Sabline has no answer to - read something with a "
             "granted read, send it with a granted send - and it is the "
             "reason CaMeL leads on AgentDojo. Its threat model is prompt "
             "injection into a trusted plan, not an untrusted program, "
             "which is why most of this corpus is outside what it tries to "
             "stop.",
}

# Row notes the page adds to what the record holds, each a reading of the
# record's own evidence line that claims() holds to it.
PAGE_NOTES = {
    ("08f", "deno"): [
        "Deno's lint does flag this program's unbounded loop (no-unreachable "
        "after it) and is not credited, because the growth is two helpers "
        "away from the loop; Sabline's audit flags the same loop and is "
        "credited. The benchmark's rule, applied unevenly."],
}

MISMATCH_NOTE = (
    "Where an expectation was wrong it is left wrong in the file, and the "
    "difference is the finding. The predictions assumed each runtime would "
    "stop a program for the reason the category is about; where the record "
    "differs, the notes in the scenario rows say what did stop it - most "
    "often a failure unrelated to the danger (a runtime with no network "
    "failing the task's own request, a smolagents defect, a deadline "
    "reached by a slow interpreter), which the benchmark's rule credits as "
    "a catch.")

LONE_REVIEW = {
    5: "Reviewed, and kept, as a judgement call rather than a win. Sabline's "
       "whole numbers are 64-bit and arithmetic that leaves the range stops "
       "the program (E407); every competitor computes the arithmetically "
       "right, larger number, because Python's, JavaScript's (as a double) "
       "and Starlark's integers do not wrap. Nothing in the corpus says the "
       "result must fit 64 bits, so the category counts a correct answer as "
       "a miss. A reader who disagrees can discount its six rows, and the "
       "control that would show the other side - a program that needs a "
       "large integer, which Sabline would stop - is missing.",
}

PROSE = [
    ("Where the benchmark is unfair", """
**In Sabline's favour.**

- *The controls are shaped to Sabline's rules.* The two control programs
  with a loop (07c, 10f) are written in the one shape Sabline's termination
  rule accepts, and no control divides, needs a whole number past 64 bits,
  or loops until its input ends. So Sabline's static rules - E612 on a loop
  it cannot show ends, E706 on a divisor it cannot show is non-zero, E407 on
  overflow - never cost it a false positive here, though each would on a
  correct program of that shape. The same gap hides Starlark's and CaMeL's
  refusal of every `while`.
- *Sabline's static flags are credited anywhere; a competitor's only on the
  dangerous line.* The benchmark credits Sabline's audit for an unbounded
  loop or an effect wherever it is, and credits Deno's lint (and here,
  Starlark's resolver) only on the dangerous line or the loop around it. In
  08f the growth sits two helpers below the loop that drives it: Sabline is
  credited for flagging that loop, and Deno and Starlark, which flag the
  same loop, are not.
- *Before-running outranks while-running.* Three of the five competitors
  (WASI, the Python sandbox, CaMeL) have no static step by design; every
  catch they make is while running, and a reader comparing "before" counts
  is comparing designs, not results.
- *Category 5 counts a correct answer as a miss* (above).
- *The corpus is about hidden effects, which is what an effect system is
  for.* Categories 1, 2 and 9 test a write, a request or a process call
  hidden in a helper. CaMeL has no helpers to hide one in - its
  translations inline them, and say so - and its threat model trusts the
  plan, so its misses there are outside what it claims to stop.
- *No row measures whether the task still works.* A dangerous program is
  scored only on whether the danger happened, so a runtime that cannot do
  the task at all scores as though it refused the danger. That flatters the
  competitors as often as Sabline (next).

**Against Sabline, and for the competitors.**

- *A catch by an unrelated failure counts.* WASI "catches" the rows whose
  task needs the network because this CPython build has no sockets, so the
  task's own request fails too; the Python sandbox "catches" them because
  smolagents 1.26.0 cannot run `urllib.request.urlopen` at all (and does
  not apply `@dataclass`, so the record rows stop early); Deno
  "catches" 13a because the corpus's JavaScript calls `require`, which Deno
  does not define; a deadline "catches" a slow interpreter. Each such row
  carries its note.
- *CaMeL gets 30 s, not 5.* Its reference interpreter needs about 4.5 s
  for 07c's correct loop on the recording machine; at 5 s the slow-but-finite
  control would be a false positive on a slower machine and 05c would be
  "caught" by the clock. The longer deadline removes both, in CaMeL's favour,
  and the two rows say so.
- *A swallowed denial counts.* Where a Deno program catches the permission
  error and exits 0, the harness credits the catch because it watched the
  socket. A caller reading the exit status would have seen success.
- *Crashes on chosen input count.* Categories 3 and 6 are caught by every
  Python-shaped runtime because the harness feeds the input that makes the
  defect fire; with ordinary input they run clean. Sabline's E706 and E520
  do not depend on the input.
"""),
    ("What the benchmark is missing", """
Scenarios where a competitor should win, or where Sabline should lose, none
of which is in the corpus. Each is a category waiting to be written
(CONTRIBUTING.md says how), and until they are, this table cannot show a
competitor ahead.

- **Laundering through a granted sink** - where CaMeL should win. The task
  needs a read and a send to one host; the program sends what it read to
  that host. Every grant Sabline has would allow it (`decisions/0004`, the
  design that would not, has not shipped); CaMeL's provenance refuses it.
  The AgentDojo evaluation already shows the shape (19 of 105 attacks land
  under a task budget), but this corpus has no row for it.
- **One legitimate subprocess** - where Deno should win.
  `--allow-run=git` grants one program; Sabline can only grant a whole host
  module, or nothing.
- **A correct unbounded loop** - a read until end of input, Euclid's
  algorithm - where Sabline's termination rule should cost it a false
  positive (and Starlark's and CaMeL's refusal of `while` should cost them
  one too), and Deno, WASI and the sandbox should run it clean.
- **A correct large integer** - 25!, a 128-bit hash - where Sabline's E407
  should stop a correct program and every Python-shaped runtime should not.
- **A safe division the prover cannot show is safe**, where E706 would
  refuse a correct program before it runs.
- **Code below the language** - a granted host module that does its own
  I/O, or a native extension - where WASI's boundary holds and a
  language-level grant does not.
- **The task still works** - every dangerous program paired with a check
  that its legitimate part ran under the narrowest grant, so a runtime that
  refuses everything, or cannot express the grant (WASI and the network,
  smolagents and a scoped path), stops scoring as though it had refused
  only the danger.
"""),
]

COLUMNS = {
    "sabline": ("this checkout", "`allow=needs`", "its own, 5 s",
                "its own, 256 MB"),
    "deno": ("Deno, pinned", "`--allow-read=<dir>`, `--allow-net=<host:port>`"
             " or none", "the harness's, 5 s",
             "its own, `--max-old-space-size=256`"),
    "python": ("CPython, no sandbox", "none: no budget exists",
               "the harness's, 5 s", "the harness's `RLIMIT_AS`"),
    "wasi": ("the same `.py`, in CPython's WASI build under wasmtime",
             "`--dir <dir>` for a read (read and write: no read-only form); "
             "**a network grant cannot be expressed** (no sockets); no "
             "environment", "its own, `-W timeout=5s`",
             "its own, `-W max-memory-size`"),
    "starlark": ("a translation, in starlark-go", "a predeclared function per "
                 "grant, refusing any other path or host; nothing else",
                 "its own (the host cancels the thread)",
                 "none: the Go runtime cannot start under a 256 MB address "
                 "limit"),
    "sandbox": ("the same `.py`, in smolagents' LocalPythonExecutor",
                "an import allowlist and passed-in functions; `open` and "
                "`urllib.request` cannot be scoped", "the host's watchdog, 5 s "
                "of interpretation (smolagents' own cannot fire first)",
                "the harness's `RLIMIT_AS`"),
    "camel": ("a translation (a plan), in CaMeL's reference interpreter",
              "CaMeL's tool set and its own policies, the same for every "
              "program", "the host's, **30 s** of interpretation (not like-for-"
              "like: see 07c)",
              "none: its imports alone exceed a 256 MB address limit"),
}


def claims(r: dict[str, Any]) -> list[str]:
    """Every sentence of the prose above that names a row, or a number from
    another record, held to the record. A page that says something the
    record does not bear out is not written."""
    rows = {x["id"]: x for x in r["programs"]}
    wrong = []

    def need(ok: bool, what: str) -> None:
        if not ok:
            wrong.append(what)

    f = rows["08f"]
    need(v(f, "sabline") == "caught-before-run"
         and "loop not shown to end in main" in f["cells"]["sabline"]["evidence"],
         "08f: Sabline credited for the loop in main")
    need(v(f, "deno") == "caught-during-run"
         and "lint elsewhere: no-unreachable" in f["cells"]["deno"]["evidence"],
         "08f: Deno's lint of the same loop not credited")
    need(v(f, "starlark") == "caught-during-run"
         and "not credited" in f["cells"]["starlark"]["evidence"],
         "08f: Starlark's refusal of the same loop not credited")
    need("require is not defined" in rows["13a"]["cells"]["deno"]["evidence"]
         and v(rows["13a"], "deno").startswith("caught"),
         "13a: Deno caught by a crash on require")
    need(any("no attribute 'request'" in x["cells"]["sandbox"]["evidence"]
             for x in r["programs"]), "a sandbox row failed on urllib.request")
    need(any(v(x, "deno") == "caught-during-run"
             and "swallowed" in x["cells"]["deno"]["evidence"]
             for x in r["programs"]), "a Deno denial swallowed by a program")
    for i in ("07c", "10f"):
        need(v(rows[i], "sabline") == "not-applicable",
             f"{i}: a control Sabline runs clean")
    need(v(rows["07c"], "camel") == "not-applicable"
         and v(rows["05c"], "camel") == "missed"
         and all(any("30 s" in n for n in rows[i]["cells"]["camel"]["notes"])
                 for i in ("07c", "05c")),
         "07c and 05c: CaMeL's 30 s, said in both rows")
    need(all(v(rows[i], "wasi").startswith("caught")
             and any(n.startswith("Not like-for-like: the task's own request")
                     for n in rows[i]["cells"]["wasi"]["notes"])
             for i in ("11b", "12a", "12b")),
         "11b, 12a, 12b: WASI caught with no network, and says so")
    agentdojo = json.loads((HERE / "evals" / "agentdojo" / "results.json")
                           .read_text(encoding="utf-8"))
    a = agentdojo["attack_success"]["task_budget"]
    need((a["succeeded"], a["of"]) == (19, 105),
         "AgentDojo: 19 of 105 attacks land under a task budget")
    return wrong


def self_test(r: dict[str, Any]) -> int:
    """claims() is only worth anything if it goes red: each fault below
    changes one row the prose relies on, and must be caught."""
    import copy
    faults = 0
    injections = [
        ("08f: Sabline no longer credited", "08f", "sabline", "verdict",
         "caught-during-run"),
        ("13a: Deno's crash gone", "13a", "deno", "evidence",
         "run: exit 1, NotCapable: Requires net access"),
        ("07c: CaMeL a false positive", "07c", "camel", "verdict",
         "false-positive"),
        ("12a: WASI missed", "12a", "wasi", "verdict", "missed"),
    ]
    ok = not claims(r)
    faults += not ok
    print(f"  {'ok   ' if ok else 'WRONG'} the record as it is: no claim fails")
    for label, pid, tool, key, value in injections:
        bad = copy.deepcopy(r)
        row = next(x for x in bad["programs"] if x["id"] == pid)
        row["cells"][tool][key] = value
        caught = bool(claims(bad))
        faults += not caught
        print(f"  {'ok   ' if caught else 'WRONG'} {label}: "
              f"{'refused' if caught else 'NOT refused'}")
    print("build_competitors_page.py --self-test: "
          + ("0 wrong" if not faults else f"{faults} WRONG"))
    return 1 if faults else 0


def main(argv: list[str]) -> int:
    if not RESULTS.exists():
        print("no benchmark/competitors/results.json "
              "(python benchmark/compete.py --record)")
        return 1
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    expect = json.loads(EXPECT.read_text(encoding="utf-8"))
    if "--self-test" in argv:
        return self_test(r)
    wrong = claims(r)
    if wrong:
        print("the page's prose says what the record does not:")
        for w in wrong:
            print("  " + w)
        return 1
    page, one, two = write_pages(r, expect)
    pages = ((OUT, page), (EVIDENCE[0], one), (EVIDENCE[1], two))
    if "--check" in argv:
        stale = [out.name for out, text in pages
                 if not out.exists()
                 or out.read_text(encoding="utf-8").replace("\r\n", "\n")
                 != text]
        if stale:
            print(", ".join(stale) + " not current "
                  "(python build_competitors_page.py)")
            return 1
        print("docs/competitors.md and its evidence pages are current")
        return 0
    for out, text in pages:
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote docs/{out.name} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
