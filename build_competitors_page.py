#!/usr/bin/env python3
"""docs/competitors.md, its page of every scenario and its evidence pages,
written from benchmark/competitors/results.json.

    python build_competitors_page.py            write them all
    python build_competitors_page.py --check    fail if any is not current
    python build_competitors_page.py --self-test   the claim checks, shown to fail

The first page publishes the table - the date, each runtime's version, the
scenarios, each category's count for all seven tools - and says, before
anything else, where a competitor is ahead. Four more (8.7) take one
competitor each - Deno, WASI, CaMeL and the Python sandbox - as
docs/compare-*.md: the same record, losses first, then every row that
differs, for a reader who arrived asking about that one tool. The second has every row with
its verdicts and notes, and the rest every cell's evidence line; none of it
fits on one page within the site's page budget, so it is split, never
trimmed. benchmark/compete.py records the
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
EVIDENCE_PART_BYTES = 45_000       # of Markdown: about 63,000 of HTML
TOOLS = ("sabline", "deno", "python", "wasi", "starlark", "sandbox", "camel")
RIVALS = ("deno", "wasi", "starlark", "sandbox", "camel")
SHORT = {"caught-before-run": "before", "caught-during-run": "during",
         "missed": "**missed**", "not-applicable": "clean",
         "false-positive": "**false positive**", "not-run": "NOT RUN",
         "tool-absent": "NOT RUN", "not-expressible": "not expressible",
         "outside": "outside"}
RANK = {"caught-before-run": 2, "caught-during-run": 1, "missed": 0}
REPO = "https://github.com/gowrishankar-infra/sabline-lang"


def v(row: dict[str, Any], tool: str) -> str:
    return str(row["cells"][tool]["verdict"])


UNSCORED = ("not-run", "tool-absent", "not-expressible", "outside")


def task_broken(row: dict[str, Any], tool: str) -> bool:
    return bool(row["cells"][tool].get("task") == "broken")


UNEARNED = ("Not a refusal", "Not like-for-like: the task's own request",
            "Stopped by the deadline")


def unearned(row: dict[str, Any], tool: str) -> bool:
    """A catch whose own row note says the danger was not what was refused:
    the runtime could not do the task's own work either, or a deadline
    stopped a slow interpreter."""
    cell = row["cells"][tool]
    return (str(cell["verdict"]).startswith("caught")
            and any(n.startswith(UNEARNED) for n in cell["notes"]))


def outcome(row: dict[str, Any], tool: str) -> int | None:
    """What a tool achieved on a row, before timing: on a dangerous row 2
    for the danger stopped with the task's work intact (or no work to
    check), 1 for stopped with the work broken too - or stopped by
    something that would have stopped the work as well, which the row's
    note says - and 0 for missed; on a control 1 for clean, 0 for a false
    positive. None when not scored."""
    vd = v(row, tool)
    if vd in UNSCORED:
        return None
    if row["dangerous"]:
        if vd == "missed":
            return 0
        return 1 if task_broken(row, tool) or unearned(row, tool) else 2
    return 1 if vd == "not-applicable" else 0


def compare_row(row: dict[str, Any], tool: str) -> str:
    """ahead / behind / tie / timing-ahead / timing-behind / n/a: the
    competitor against Sabline on one row - the outcome first, and only
    where the outcome is the same, the timing (before running or while)."""
    a, s = outcome(row, tool), outcome(row, "sabline")
    if a is None or s is None:
        return "n/a"
    if a != s:
        return "ahead" if a > s else "behind"
    if row["dangerous"] and a >= 1:
        ra, rs = RANK[v(row, tool)], RANK[v(row, "sabline")]
        if ra != rs:
            return "timing-ahead" if ra > rs else "timing-behind"
    return "tie"


def why_ahead(row: dict[str, Any], tool: str) -> str:
    a, s = outcome(row, tool), outcome(row, "sabline")
    if not row["dangerous"]:
        return "ran the correct program clean, where Sabline stopped or flagged it"
    if s == 0:
        if a == 2:
            return "caught what Sabline missed"
        if unearned(row, tool):
            return ("stopped what Sabline missed, by a failure that is not a "
                    "refusal and would have stopped the task too (†)")
        return "caught what Sabline missed, though with the task broken"
    return ("stopped the danger with the task's work intact, where Sabline's "
            "refusal ended the run and the task with it")


def cell_text(row: dict[str, Any], tool: str) -> str:
    text = SHORT[v(row, tool)]
    if row["dangerous"] and v(row, tool).startswith("caught") \
            and task_broken(row, tool):
        text += ", task broken"
    if unearned(row, tool):
        text += " †"
    if tool != "sabline":
        c = compare_row(row, tool)
        if c in ("ahead", "timing-ahead"):
            text += " ▲"
    return text


def got_class(x: dict[str, Any], t: str) -> str:
    """A cell's class for the expectations table, with a broken task said."""
    k = SHORT[v(x, t)].strip("*")
    return k + (" (task broken)" if x["dangerous"] and k in ("before", "during")
                and task_broken(x, t) else "")


def category_cell(mine: list[dict[str, Any]], t: str) -> str:
    cells = [v(x, t) for x in mine]
    if all(c in ("not-run", "tool-absent") for c in cells):
        return "NOT RUN"
    dang = [x for x in mine if x["dangerous"] and v(x, t) not in UNSCORED]
    ctl = [x for x in mine if not x["dangerous"] and v(x, t) not in UNSCORED]
    parts = []
    if dang:
        b = sum(v(x, t) == "caught-before-run" for x in dang)
        d = sum(v(x, t) == "caught-during-run" for x in dang)
        m = sum(v(x, t) == "missed" for x in dang)
        broken = sum(1 for x in dang if v(x, t).startswith("caught")
                     and task_broken(x, t))
        parts.append(f"{b}/{d}/{m}" + (f" ({broken} task broken)"
                                       if broken else ""))
    if ctl:
        fp = sum(v(x, t) == "false-positive" for x in ctl)
        parts.append(f"{len(ctl) - fp} clean" + (f", **{fp} FP**" if fp else ""))
    ne = sum(c == "not-expressible" for c in cells)
    out = sum(c == "outside" for c in cells)
    if ne:
        parts.append(f"{ne} not expressible")
    if out:
        parts.append(f"{out} outside")
    return "; ".join(parts)


def total_caught(dangerous: list[dict[str, Any]], t: str) -> str:
    scored = [x for x in dangerous if v(x, t) not in UNSCORED]
    caught = [x for x in scored if v(x, t).startswith("caught")]
    before = sum(v(x, t) == "caught-before-run" for x in caught)
    broken = sum(task_broken(x, t) for x in caught)
    return (f"**{len(caught)}** of {len(scored)} ({before} before; "
            f"{broken} with the task broken)")


def total_fp(controls: list[dict[str, Any]], t: str) -> str:
    scored = [x for x in controls if v(x, t) not in UNSCORED]
    fp = sum(v(x, t) == "false-positive" for x in scored)
    return f"**{fp}** of {len(scored)}"


def ids(rows: list[dict[str, Any]]) -> str:
    return ", ".join(r["id"] for r in rows) if rows else "none"


def write_pages(r: dict[str, Any],
                expect: dict[str, Any]) -> tuple[str, list[str]]:
    rows: list[dict[str, Any]] = r["programs"]
    labels: dict[str, str] = r["labels"]
    meta = r["meta"]
    rt = meta["runtimes"]
    dangerous = [x for x in rows if x["dangerous"]]
    controls = [x for x in rows if not x["dangerous"]]
    parts = len(evidence_pages(r))
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
    p("Each row is compared first on what a tool achieved, and only then on "
      "when: stopping the danger with the task's legitimate work intact beats "
      "stopping it with the work broken too, which beats missing it, and on "
      "a correct program running it clean beats flagging it. Only where two "
      "tools achieved the same does the timing count - before running or "
      "while. A row a tool cannot express, or one outside CaMeL's threat "
      "model, is not compared.")
    p("")
    ahead_any = False
    for t in RIVALS:
        rows_ahead = [x for x in rows if compare_row(x, t) == "ahead"]
        if not rows_ahead:
            continue
        ahead_any = True
        by_reason: dict[str, list[str]] = {}
        for x in rows_ahead:
            by_reason.setdefault(why_ahead(x, t), []).append(x["id"])
        p(f"- **{labels[t]}**, {len(rows_ahead)} row(s): " + "; ".join(
            f"{reason} ({', '.join(found)})"
            for reason, found in by_reason.items()) + ".")
    if not ahead_any:
        p(f"**On this benchmark's {len(rows)} rows, no competitor is ahead "
          "of Sabline on any row.** plan/8.7.md says what that means: a "
          "table where Sabline wins everything is evidence that the "
          "benchmark is wrong, not that Sabline is good.")
    p("")
    p("Against Sabline, row by row. *Tie* is the same outcome at the same "
      "time; *earlier* and *later* mean the same outcome, one before running "
      "and one while running. *Not compared* counts the rows a tool cannot "
      "express, and for CaMeL the rows outside its threat model.")
    p("")
    p("| Competitor | Ahead | Earlier | Tie | Later | Behind | Not compared |")
    p("|---|---:|---:|---:|---:|---:|---:|")
    for t in RIVALS:
        cs = [compare_row(x, t) for x in rows]
        p(f"| {labels[t]} | {cs.count('ahead')} | {cs.count('timing-ahead')}"
          f" | {cs.count('tie')} | {cs.count('timing-behind')} | "
          f"{cs.count('behind')} | {cs.count('n/a')} |")
    p("")
    nobody = [x for x in dangerous if all(
        outcome(x, t) in (0, None) for t in TOOLS)]
    p(f"Nothing caught {ids(nobody)}.")
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
      "with how many of the catches broke the task's legitimate work too; "
      "for the correct programs, clean / false positive; and the rows a tool "
      "cannot express, or that are outside CaMeL's threat model, which are "
      "not scored. The per-program rows follow, each with its notes.")
    p("")
    p("| Category | " + " | ".join(labels[t] for t in TOOLS) + " |")
    p("|---|" + "---|" * len(TOOLS))
    for cat in r["categories"]:
        mine = [x for x in rows if x["category"] == cat["number"]]
        p(f"| {cat['number']}. {cat['title']} | "
          + " | ".join(category_cell(mine, t) for t in TOOLS) + " |")
    p("| **Caught, of the dangerous rows scored** | " + " | ".join(
        total_caught(dangerous, t) for t in TOOLS) + " |")
    p("| **False positives, of the correct programs scored** | " + " | ".join(
        total_fp(controls, t) for t in TOOLS) + " |")
    p("| **Not expressible / outside the threat model** | " + " | ".join(
        f"{sum(v(x, t) == 'not-expressible' for x in rows)} / "
        f"{sum(v(x, t) == 'outside' for x in rows)}" for t in TOOLS) + " |")
    p("| **Catches the row itself says were not a refusal** | " + " | ".join(
        str(sum(1 for x in dangerous if unearned(x, t))) for t in TOOLS)
      + " |")
    p("")
    p("A catch with the task broken stopped the danger and the program's "
      "legitimate work with it - a refusal that ends the whole run, a "
      "program that did not compile or resolve, a runtime that cannot make "
      "the task's own request. The last row counts catches the benchmark's "
      "rule credits but whose row note says the program was stopped by "
      "something other than a refusal of its danger. Read each column's "
      "catches net of both.")
    p("")

    p("## Every scenario")
    p("")
    p("Every program's row, with the verdict for all seven tools and every "
      "place a row is not like-for-like, is on a page of its own: "
      "[every scenario](competitors-scenarios.md). Every cell's evidence "
      "line is on the evidence pages ("
      + ", ".join(f"[part {i}](competitors-evidence-{i}.md)"
                  for i in range(1, parts + 1))
      + ").")
    p("")

    # ---- countermeasures 1 and 2 ------------------------------------------------
    p("## Expected, and what happened")
    p("")
    p("`benchmark/competitors/expectations.json` was committed before the "
      "harness ran anything, and its categories 16 to 20 before any "
      "competitor ran on them (countermeasure 1 in plan/8.7.md). Here it is "
      "beside the record, for the four columns it predicted; *as expected* "
      "means every dangerous row of the category landed in the predicted "
      "class, and anything else is shown as it happened. The predictions "
      "for categories 1 to 15 were written under the first rules and are "
      "left as they were.")
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
        ctl = [x for x in controls if x["category"] == ex["number"]]
        cells = []
        for t in new:
            want = str(ex["expect"].get(t, ""))
            got = [got_class(x, t) for x in mine]
            summary = ", ".join(f"{got.count(k)} {k}" for k in sorted(set(got)))
            if ctl:
                cg = [got_class(x, t) for x in ctl]
                summary += "; controls: " + ", ".join(
                    f"{cg.count(k)} {k}" for k in sorted(set(cg)))
            if want in ("before", "during", "missed", "not-expressible",
                        "outside") and set(got) == {want}:
                cell = "as expected"
            elif set(got) == {"outside"}:
                cell = f"outside, not scored (predicted {want})"
            else:
                cell = f"expected {want}; got {summary}"
            for i in excepted:
                x = next(y for y in rows if y["id"] == i)
                cell += f"; {i} {got_class(x, t)}"
            cells.append(cell.replace("|", "\\|"))
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
        return (outcome(x, t) or 0) >= 1 and not unearned(x, t)

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
                    if (outcome(x, "sabline") or 0) >= 1
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

    return "\n".join(w), evidence_pages(r)


def scenario_page(r: dict[str, Any], parts: int) -> str:
    """Every program's row, for all seven tools, with its notes: a page of
    its own, since it does not fit beside the rest within the budget."""
    rows: list[dict[str, Any]] = r["programs"]
    labels: dict[str, str] = r["labels"]
    w: list[str] = []
    p = w.append
    p("# Competitors: every scenario")
    p("")
    p("Every row of [the competitor table](competitors.md), measured "
      f"{r['meta']['date']}. ▲ marks a competitor that did better than "
      "Sabline on the row (or the same, earlier); † marks a catch whose row "
      "note says it was not a refusal of the danger; *task broken* marks a "
      "catch that stopped the program's legitimate work too. The last column "
      "is where a row is not like-for-like - a different threat model, a "
      "construct a runtime lacks, a catch that came from a failure rather "
      "than a refusal - stated in the row, not in a footnote. CaMeL's column "
      "reads *outside* on every row its threat model does not claim: it "
      "trusts the plan, and is scored only where private or untrusted data "
      "reaches a tool ([the rule](competitors.md#how-each-column-was-run)). "
      "Every cell's evidence line is on the evidence pages ("
      + ", ".join(f"[part {i}](competitors-evidence-{i}.md)"
                  for i in range(1, parts + 1))
      + "); the commands and their output are in "
      f"[results.json]({REPO}/blob/main/benchmark/competitors/results.json).")
    p("")
    for cat in r["categories"]:
        mine = [x for x in rows if x["category"] == cat["number"]]
        p(f"## {cat['number']}. {cat['title']}")
        p("")
        p("| # | Program | " + " | ".join(labels[t] for t in TOOLS)
          + " | Not like-for-like |")
        p("|---|---|" + "---|" * len(TOOLS) + "---|")
        for x in mine:
            notes = []
            for t in TOOLS:
                cell = x["cells"][t]
                if cell["verdict"] == "not-expressible":
                    notes.append(f"*{labels[t]}:* cannot be expressed: "
                                 + cell["evidence"][len("NOT EXPRESSIBLE: "):]
                                 + ".")
                for n in cell["notes"] + PAGE_NOTES.get((x["id"], t), []):
                    notes.append(f"*{labels[t]}:* {n}")
            name = x["name"] + ("" if x["dangerous"] else " (control)")
            p(f"| {x['id']} | `{name}` | "
              + " | ".join(cell_text(x, t) for t in TOOLS) + " | "
              + ("<br>".join(n.replace("|", "\\|") for n in notes) or "-")
              + " |")
        p("")
    return "\n".join(w)


def evidence_pages(r: dict[str, Any]) -> list[str]:
    """Every cell's evidence line, in as many pages as the site's budget
    needs: categories are packed in order until a page's text would pass
    EVIDENCE_PART_BYTES, and a new page starts."""
    rows: list[dict[str, Any]] = r["programs"]
    labels: dict[str, str] = r["labels"]
    meta = r["meta"]

    def category(cat: dict[str, Any]) -> list[str]:
        mine = [x for x in rows if x["category"] == cat["number"]]
        e = [f"## {cat['number']}. {cat['title']}", ""]
        for x in mine:
            # a description may hold Python's power (2**61), which the site
            # would take for emphasis: the page writes it 2^61
            text = x["description"].replace("**", "^")
            e += [f"**{x['id']}** `{x['name']}` - {text}", ""]
            for t in TOOLS:
                c = x["cells"][t]
                task = c.get("task")
                e.append(f"- {labels[t]}: **{c['verdict']}**"
                         + (f" (task {task})" if task else "") + " - "
                         + c["evidence"].replace("|", "\\|"))
            e.append("")
        return e

    groups: list[list[dict[str, Any]]] = [[]]
    size = 0
    for cat in r["categories"]:
        n = len("\n".join(category(cat)))
        if groups[-1] and size + n > EVIDENCE_PART_BYTES:
            groups.append([])
            size = 0
        groups[-1].append(cat)
        size += n
    pages = []
    for part, group in enumerate(groups, 1):
        others = ", ".join(f"[part {i}](competitors-evidence-{i}.md)"
                           for i in range(1, len(groups) + 1) if i != part)
        e = [f"# Competitors: the evidence, part {part}", "",
             f"Categories {group[0]['number']} to {group[-1]['number']} of "
             f"[the competitor table](competitors.md) (the rest are in "
             f"{others}), measured {meta['date']}: every cell's verdict, "
             "whether the program's legitimate work still succeeded where the "
             "row checks it, and the evidence line the harness wrote from what "
             "ran. The commands each cell ran, the input it was given and "
             "what it printed are in "
             f"[results.json]({REPO}/blob/main/benchmark/competitors/"
             "results.json), with the scratch directory written as `<workdir>` "
             "and the two listener ports as `<port>` (granted) and "
             "`<other-port>` (not).", ""]
        for cat in group:
            e += category(cat)
        pages.append("\n".join(e))
    return pages


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
    ("08f", "sabline"): [
        "Sabline's audit, Deno's lint and Starlark's resolver each flag the "
        "loop that drives the growth, two helpers above the line that grows, "
        "and none of the three is credited: one line rule for all."],
}

MISMATCH_NOTE = (
    "Where an expectation was wrong it is left wrong in the file, and the "
    "difference is the finding. The predictions assumed each runtime would "
    "stop a program for the reason the category is about; where the record "
    "differs, the notes in the scenario rows say what did stop it - most "
    "often something other than a refusal of the danger (a smolagents "
    "defect, or a language with no try that stops at the first refusal and "
    "takes the task with it), which the benchmark's rule credits as a catch "
    "and this page ranks as a catch with the task broken.")

LONE_REVIEW = {
    5: "Reviewed, and kept, as a judgement call rather than a win. Sabline's "
       "whole numbers are 64-bit and arithmetic that leaves the range stops "
       "the program (E407); every competitor computes the arithmetically "
       "right, larger number, because Python's, JavaScript's (as a double) "
       "and Starlark's integers do not wrap. Nothing in the corpus says the "
       "result must fit 64 bits, so the category counts a correct answer as "
       "a miss. A reader who disagrees can discount its six rows. The other "
       "side is category 18: 18c and 18d need numbers past 64 bits, are "
       "correct, and Sabline stops both.",
}

PROSE = [
    ("What changed in the scoring, and why", """
The first version of this table (pull request #104, never published) had
Sabline ahead or level on every row. That was the benchmark, not the tools,
and these are the corrections, each applied to every column alike.

- *The outcome comes first; the timing only breaks a tie.* A row is scored
  on what a tool achieved: the danger stopped with the task's legitimate
  work intact, stopped with the work broken too, or missed - and on a
  correct program, run clean or not. Before, catching a danger *before
  running* outranked catching it while running, so a design with no static
  step (WASI, the Python sandbox, CaMeL) could never be ahead of one with
  a static step, whatever it did.
- *Whether the legitimate work still succeeded is checked,* on every row
  that has work to check: the output the task asked for, the request it
  was granted, the file it was to write. A runtime that stops everything
  now scores as a catch with the task broken, not as though it had stopped
  only the danger - and a Sabline refusal, which ends the run and cannot be
  caught, is scored the same way. Where a row's own note says a catch came
  from a failure that would have stopped the task as well (a runtime
  without sockets, a defect in smolagents, a deadline), it is scored the
  same way even where there is no task line to check.
- *"Caught before running" is credited only where the tool's own design has
  that step:* Sabline's check, audit and deps-diff, Deno's type check and
  lint, Starlark's resolver. The others are scored on what happened when
  the program ran.
- *A static flag counts only on the marked dangerous line, for every tool.*
  Before, Sabline's audit was credited for an effect or an unbounded loop
  anywhere in the program, while Deno's lint and Starlark's resolver were
  credited only on the dangerous line. Now Sabline's audit is credited only
  for an effect that a call on the dangerous line needs, or a loop its
  termination rule names on that line or on the loop around it; a flag
  anywhere else is recorded and not credited.
- *CaMeL is scored only where its threat model makes a claim:* where a
  value that came from a tool (a file read, a web page, the environment)
  reaches another tool on the dangerous line. Its plan is trusted by
  design, so a hidden write or a runaway loop in the plan is outside what
  it tries to stop. Those cells still ran and say what happened; they read
  *outside* and are not counted.
- *A scenario a runtime cannot express is recorded as such, with the reason,*
  rather than scored or skipped: WASI has no sockets and no processes,
  a Starlark module has no I/O of its own, a native library cannot be
  loaded into a WebAssembly guest.
- *Five categories were added where a competitor should win or Sabline
  should lose* (16 to 20), and their predictions were committed before any
  competitor ran them.
"""),
    ("Where the benchmark is still unfair", """
**In Sabline's favour.**

- *Most rows of categories 1 to 11 have no task check.* Their dangerous
  programs do nothing but the dangerous thing, so there is no legitimate
  work to measure, and a refusal that ends the run costs nothing there.
  That favours the designs that end the program at the first refusal -
  Sabline, Starlark and CaMeL - over the ones whose programs can catch a
  denial and go on, as Deno's do. Category 20 measures exactly this, and
  Sabline loses it.
- *The corpus is about hidden effects, which is what an effect system is
  for.* Categories 1, 2 and 9 test a write, a request or a process call
  hidden in a helper, and Sabline finds each one before it runs (09c,
  which only prints text, is no hidden effect).
- *Categories 5 and 18f count a correct, larger number as a miss*
  (reviewed above, under the categories no competitor catches).
- *Every program was written by Sabline's author, and every translation by
  agents working for them.* The rows are small, and each is built to
  show one property.

**Against Sabline, and for the competitors.**

- *A catch by an unrelated failure still ranks above a miss.* The Python
  sandbox "catches" rows whose task needs the network because smolagents
  1.26.0 cannot run `urllib.request.urlopen` at all; each such row says so,
  and scores as a catch with the task broken - still ahead of a Sabline
  miss.
- *A swallowed denial counts.* Where a Deno program catches the permission
  error and goes on, the harness credits the catch because it watched the
  socket or the file. A caller reading the exit status would have seen
  success.
- *Crashes on chosen input count.* Categories 3 and 6 are caught by every
  Python-shaped runtime because the harness feeds the input that makes the
  defect fire; with ordinary input they run clean. Sabline's E706 and E520
  do not depend on the input.
"""),
    ("What the benchmark is still missing", """
- **A model in the loop.** Every CaMeL plan here is a hand translation; CaMeL
  exists to constrain plans a model writes from untrusted input, and the
  [AgentDojo evaluation](agentdojo.md) is where that is measured (Sabline:
  19 of 105 attacks land under a task budget).
- **An operating-system sandbox column** - bubblewrap, nsjail, gVisor, a
  container - which would stop 19d, where native code in a granted library
  writes a file of its own and no column here stops it. Sabline's own OS
  confinement (8.4) is not in its column: a granted `ffi:` module runs as
  host code and the policy is widened to what the module can do.
- **More correct programs Sabline refuses:** a legitimate read of a
  credential file (E318), a safe division the prover cannot show is safe
  (E706), a loop over a structure that shrinks.
- **Task checks on categories 1 to 11,** so that ending the run at the
  first refusal costs something there too.
- **Other platforms.** Everything was recorded on one Linux machine; how
  Deno, wasmtime and the others behave on Windows or macOS is not measured.
"""),
]

COLUMNS = {
    "sabline": ("this checkout", "`allow=needs`", "its own, 5 s",
                "its own, 256 MB"),
    "deno": ("Deno, pinned", "`--allow-read=<dir>`, `--allow-write=<dir>`, "
             "`--allow-net=<host:port>`, `--allow-run=<program>`, "
             "`--allow-ffi`, or none", "the harness's, 5 s",
             "its own, `--max-old-space-size=256`"),
    "python": ("CPython, no sandbox", "none: no budget exists",
               "the harness's, 5 s", "the harness's `RLIMIT_AS`"),
    "wasi": ("the same `.py`, in CPython's WASI build under wasmtime",
             "`--dir <dir>` for a read or a write (no read-only form); "
             "**a network grant, a process or a native library cannot be "
             "expressed**; no environment", "its own, `-W timeout=5s`",
             "its own, `-W max-memory-size`"),
    "starlark": ("a translation, in starlark-go", "a predeclared function per "
                 "grant, refusing any other path, host or program; nothing "
                 "else",
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
              "program; scored only on the rows its threat model claims",
              "the host's, **30 s** of interpretation (not like-for-"
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

    def cat(n: int) -> list[dict[str, Any]]:
        return [x for x in r["programs"] if x["category"] == n]

    f = rows["08f"]
    need(v(f, "sabline") == "caught-during-run"
         and "not credited" in f["cells"]["sabline"]["evidence"],
         "08f: Sabline's audit of the loop in main recorded, not credited")
    need(v(f, "deno") == "caught-during-run"
         and "lint elsewhere: no-unreachable" in f["cells"]["deno"]["evidence"],
         "08f: Deno's lint of the same loop not credited")
    need(v(f, "starlark") == "caught-during-run"
         and "not credited" in f["cells"]["starlark"]["evidence"],
         "08f: Starlark's refusal of the same loop not credited")
    need(any(compare_row(x, "deno") == "ahead" for x in cat(20)),
         "category 20: Deno ahead of Sabline on a row")
    need(any("no attribute 'request'" in x["cells"]["sandbox"]["evidence"]
             and unearned(x, "sandbox") for x in r["programs"]),
         "a sandbox row failed on urllib.request, and says it was no refusal")
    need(any(v(x, "deno") == "caught-during-run"
             and "swallowed" in x["cells"]["deno"]["evidence"]
             for x in r["programs"]), "a Deno denial swallowed by a program")
    early = [x for n in range(1, 12) for x in cat(n) if x["dangerous"]]
    need(sum(x["cells"]["sabline"].get("task") is None for x in early) * 2
         > len(early), "categories 1 to 11: most dangerous rows no task check")
    need(all(v(x, "sabline") == "caught-before-run"
             for n in (1, 2, 9) for x in cat(n)
             if x["dangerous"] and x["id"] != "09c"),
         "categories 1, 2 and 9: every hidden effect found by Sabline before "
         "running (09c prints text, and is no hidden effect)")
    need(v(rows["18f"], "sabline").startswith("caught")
         and all(v(rows["18f"], t) in ("missed",) + UNSCORED for t in RIVALS),
         "18f: a larger number counted as every competitor's miss")
    need(all(v(rows[i], "sabline") == "false-positive" for i in ("18c", "18d")),
         "18c and 18d: Sabline stops both correct programs")
    need(all(outcome(rows["19d"], t) in (0, None) for t in TOOLS),
         "19d: no column stops the native write")
    need(all(v(rows[i], "wasi") == "not-expressible"
             for i in ("11b", "12a", "12b")),
         "11b, 12a, 12b: a network task WASI cannot express")
    need(v(rows["07c"], "sabline") == "not-applicable"
         and v(rows["10f"], "sabline") == "not-applicable",
         "07c and 10f: loops in the shape Sabline's rule accepts")
    need(not any(any(n.startswith("Stopped by the deadline")
                     for n in x["cells"]["camel"]["notes"])
                 and v(x, "camel") not in UNSCORED for x in r["programs"]),
         "no scored CaMeL cell decided by its 30 s deadline")
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
        ("08f: Sabline credited again", "08f", "sabline", "verdict",
         "caught-before-run"),
        ("18c: Sabline runs it clean", "18c", "sabline", "verdict",
         "not-applicable"),
        ("19d: Deno stops the native write", "19d", "deno", "verdict",
         "caught-during-run"),
        ("12a: WASI scored", "12a", "wasi", "verdict", "caught-during-run"),
        ("18f: Deno catches it", "18f", "deno", "verdict", "caught-during-run"),
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


# One page per competitor (8.7): (the page, its title, the tool's name in
# running text, a page that says more about the same tool)
COMPARE = {
    "deno": ("compare-deno.md", "Sabline compared with Deno's permissions",
             "Deno", None),
    "wasi": ("compare-wasi.md", "Sabline compared with WASI (wasmtime)",
             "WASI", None),
    "camel": ("compare-camel.md", "Sabline compared with CaMeL", "CaMeL",
              ("agentdojo.md", "the AgentDojo run")),
    "sandbox": ("compare-python-sandbox.md",
                "Sabline compared with a Python sandbox (smolagents)",
                "the Python sandbox", None),
}
COMPARED_AS = {"ahead": "ahead", "timing-ahead": "earlier", "tie": "tie",
               "timing-behind": "later", "behind": "behind", "n/a": "n/a"}


def evidence_part(r: dict[str, Any]) -> dict[int, int]:
    """{category number: the evidence page holding it}, as evidence_pages
    packs them."""
    found: dict[int, int] = {}
    for part, text in enumerate(evidence_pages(r), 1):
        for cat in r["categories"]:
            if f"\n## {cat['number']}. " in "\n" + text:
                found[cat["number"]] = part
    return found


def compare_page(r: dict[str, Any], tool: str) -> str:
    """docs/compare-<tool>.md: one competitor against Sabline, from the
    record. Where it is ahead comes first - by design, then row by row -
    then where it is earlier, where Sabline is, and what is not compared."""
    rows: list[dict[str, Any]] = r["programs"]
    labels: dict[str, str] = r["labels"]
    meta = r["meta"]
    rt = meta["runtimes"]
    _, title, name, also = COMPARE[tool]
    part = evidence_part(r)
    by = {k: [x for x in rows if COMPARED_AS[compare_row(x, tool)] == k]
          for k in ("ahead", "earlier", "tie", "later", "behind", "n/a")}
    label = labels[tool]
    version = rt[tool]["version"] + (f", {rt[tool]['detail']}"
                                     if rt[tool].get("detail") else "")
    w: list[str] = []
    p = w.append

    def row_table(chosen: list[dict[str, Any]], why: bool) -> None:
        p(f"| Row | Category | Program | {label} | Sabline |"
          + (" Why |" if why else ""))
        p("|---|---|---|---|---|" + ("---|" if why else ""))
        for x in chosen:
            ev = f"competitors-evidence-{part[x['category']]}.md"
            name_ = x["name"] + ("" if x["dangerous"] else " (control)")
            p(f"| [{x['id']}]({ev}) | {x['category']}. "
              f"{x['category_title'].replace('|', '/')} | `{name_}` | "
              f"{cell_text(x, tool)} | {cell_text(x, 'sabline')} |"
              + (f" {why_ahead(x, tool)} |" if why else ""))
        p("")

    p(f"# {title}")
    p("")
    p(f"<!-- description: {label} {rt[tool]['version']} against Sabline "
      f"{rt['sabline']['version']} on {len(rows)} measured programs, "
      f"{meta['date']}: where {name} is ahead ({len(by['ahead'])} rows) "
      "comes first. -->")
    p("")
    p(f"{label} and Sabline, run on the same {len(rows)} programs of "
      "Sabline's comparison benchmark, each in its own real runtime. This "
      "page takes the one tool from [the competitor table](competitors.md), "
      f"and starts with where {name} does better.")
    p("")
    p("> [!NOTE]")
    p(f"> **Last verified:** {meta['date']}, on {meta['platform']}: "
      f"**{label}** {version}, **Sabline** {rt['sabline']['version']}. "
      "Every verdict below comes from a program that ran, recorded in "
      f"[results.json]({REPO}/blob/main/benchmark/competitors/results.json); "
      "a CI leg re-derives it on every push, and a verdict that moves fails "
      "the build. A score on this corpus is not what either tool is for - "
      "the next section is.")
    p("")
    p(f"## Where {name} is stronger by design")
    p("")
    p(BY_DESIGN[tool])
    p("")
    p(f"## Where {name} is ahead, row by row")
    p("")
    if by["ahead"]:
        p(f"{len(by['ahead'])} of the {len(rows)} rows: a better outcome - the "
          "danger stopped with the task's work intact where Sabline's refusal "
          "ended the task, a catch Sabline missed, or a correct program run "
          "clean where Sabline stopped it. The row links to its evidence.")
        p("")
        row_table(by["ahead"], True)
    else:
        p(f"On none of the {len(rows)} rows.")
        p("")
    if by["earlier"]:
        p(f"## Where {name} is earlier")
        p("")
        p(f"The same outcome, but {name} reached it before running and Sabline "
          "while running:")
        p("")
        row_table(by["earlier"], False)
    p("## Where Sabline is ahead")
    p("")
    if by["behind"]:
        p(f"{len(by['behind'])} rows where Sabline's outcome is the better "
          f"one, and {len(by['later'])} where both reached the same outcome "
          f"and Sabline reached it earlier - before running, where {name} "
          "did while running.")
        p("")
        row_table(by["behind"], False)
        # a category the benchmark itself calls a judgement call says so
        # here too, beside the rows it would otherwise count as a win
        for number in sorted({x["category"] for x in by["behind"]}):
            if number in LONE_REVIEW:
                p(f"**Category {number} is a judgement call, not a clean "
                  f"win.** {LONE_REVIEW[number]}")
                p("")
    else:
        p(f"On no row is Sabline's outcome better; on {len(by['later'])} it "
          "reached the same one earlier.")
        p("")
    p("## The rest")
    p("")
    cats = sorted({x["category"] for x in by["tie"]})
    p(f"{len(by['tie'])} rows are a tie - the same outcome at the same time"
      + (f", in categories {', '.join(str(c) for c in cats)}" if cats else "")
      + f". {len(by['n/a'])} are not compared: rows {name} cannot express"
      + (", and rows outside its threat model" if tool == "camel" else "")
      + " ([the rule](competitors.md#how-each-column-was-run)). Every row, "
      "with every tool's verdict and its notes, is on "
      "[the scenario page](competitors-scenarios.md).")
    p("")
    if also:
        p(f"See also [{also[1]}]({also[0]}).")
        p("")
    return "\n".join(w)


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
    page, parts = write_pages(r, expect)
    pages = [(OUT, page),
             (OUT.parent / "competitors-scenarios.md",
              scenario_page(r, len(parts)))] + [
        (OUT.parent / f"competitors-evidence-{i}.md", text)
        for i, text in enumerate(parts, 1)] + [
        (OUT.parent / COMPARE[tool][0], compare_page(r, tool))
        for tool in COMPARE]
    names = {out.name for out, _ in pages}
    extra = sorted(q for q in OUT.parent.glob("competitors-evidence-*.md")
                   if q.name not in names)
    if "--check" in argv:
        stale = [out.name for out, text in pages
                 if not out.exists()
                 or out.read_text(encoding="utf-8").replace("\r\n", "\n")
                 != text] + [q.name + " (no longer written)" for q in extra]
        if stale:
            print(", ".join(stale) + " not current "
                  "(python build_competitors_page.py)")
            return 1
        print("docs/competitors.md and its evidence pages are current")
        return 0
    for out, text in pages:
        out.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote docs/{out.name} ({len(text)} bytes)")
    for q in extra:
        q.unlink()
        print(f"removed docs/{q.name}: the evidence fits fewer pages now, "
              "so take it out of build_docs.DOCS_ORDER")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
