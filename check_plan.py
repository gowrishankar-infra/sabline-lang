#!/usr/bin/env python3
"""The milestone table and the CHANGELOG agree, and the ladder is whole.

`plan/9.0.md` names eight milestones, M1 to M8, which are bodies of work
and not version numbers, and carries a table of every pre-release
published so far against the milestone it was working on. From
`9.0.0-alpha.5` on, every pre-release's CHANGELOG heading names its
milestone:

    ## 9.0.0-alpha.5 - M2: types and effects, as far as they got

Two documents saying the same thing is two documents that will disagree,
so this suite holds them to each other. It fails when:

- a pre-release has a CHANGELOG entry and no row in the table, which is
  what happens when somebody ships one and forgets the plan;
- a row names a version no CHANGELOG entry has;
- a row names a milestone the ladder does not define;
- the ladder is not exactly M1 to M8, consecutive, with no gap and no
  repeat;
- a pre-release at or after the enforcement point has a heading that
  names no milestone, names more than one, or names a milestone other
  than the table's;
- a pre-release before the enforcement point is not one of the four
  named below, so the exemption cannot grow by accident;
- a row names a version this checkout has no tag for (where this is a
  git checkout; where it is not, that part says it skipped).

The four pre-releases published before the rule existed are exempt from
the heading rule and from nothing else. They are NOT retitled: they
shipped under the names they shipped under, and a changelog edited after
the fact to look tidier is a changelog nobody can use.

**It is proven to detect, not merely to run.** Every rule above is a
function of two texts and a tag set, so the last part of this suite
feeds it mutated copies of the real documents - a row deleted, a
milestone changed, a rung removed, a heading that names the wrong one,
a pre-release slipped in below the rule - and requires the named rule to
go red for each. A check that has never been shown to fail is a check
nobody has tested (`plan/9.0.md`, the agreement gate).

    python check_plan.py
    python check_plan.py --self   only the injections
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / "plan" / "9.0.md"
CHANGELOG = HERE / "CHANGELOG.md"
TABLE_HEADING = "### Versions, and the milestone each one was in"

# The heading rule begins here. A pre-release below it is exempt; one at
# or above it is held. Changing this line is a decision, not a fix.
RULE_FROM = "9.0.0-alpha.5"

# The four that shipped before the rule existed. A pre-release that is
# not one of these and is below RULE_FROM is an error, so this list
# cannot grow without somebody editing it.
BEFORE_THE_RULE = ("9.0.0-alpha.1", "9.0.0-alpha.2", "9.0.0-alpha.3",
                   "9.0.0-alpha.4")

MILESTONES = 8

PASSED = FAILED = SKIPPED = 0


def ok(label: str, good: object, detail: object = "") -> None:
    global PASSED, FAILED
    if good:
        PASSED += 1
        print(f"  ok       {label}")
    else:
        FAILED += 1
        print(f"  BROKEN   {label}")
        if detail:
            print(f"           {str(detail)[:1500]}")


def skip(label: str, why: str) -> None:
    global SKIPPED
    SKIPPED += 1
    print(f"  skip     {label} ({why})")


# ---- reading the two documents ---------------------------------------------

def version_key(version: str) -> tuple[int, ...]:
    """A pre-release sorted the way its numbers sort, so that "before
    RULE_FROM" is a comparison and not a string test. `9.0.0-alpha.10`
    is after `9.0.0-alpha.9`, which is the whole reason this is not
    `<` on the text."""
    m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)-([a-z]+)\.(\d+)", version)
    if not m:
        raise ValueError(f"not a pre-release version: {version!r}")
    kinds = {"alpha": 0, "beta": 1, "rc": 2}
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)),
            kinds.get(m.group(4), 9), int(m.group(5)))


def ladder(plan: str) -> list[str]:
    """Every milestone the plan defines, in the order it defines them."""
    return re.findall(r"^### (M\d+)\b", plan, re.MULTILINE)


def table(plan: str) -> list[tuple[str, str, str]]:
    """The version table: (version, milestone cell, what it published).

    Read from the section it lives in and from nowhere else, so that a
    table added elsewhere in the file is not silently picked up.
    """
    start = plan.index(TABLE_HEADING)
    end = plan.index("\n### ", start + 1)
    rows = []
    for line in plan[start:end].splitlines():
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*([^|]*?)\s*\|\s*(.*?)\s*\|\s*$",
                     line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3)))
    return rows


def milestone_of(cell: str) -> str | None:
    """The milestone a table cell names: `M1 (in progress)` and
    `**M1, complete**` are both M1."""
    m = re.search(r"\bM(\d+)\b", cell)
    return f"M{m.group(1)}" if m else None


def changelog_entries(changelog: str) -> list[tuple[str, str]]:
    """(version, the rest of the heading) for every entry."""
    out = []
    for line in changelog.splitlines():
        m = re.match(r"^## (\S+) - (.*)$", line)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def tags() -> set[str] | None:
    try:
        done = subprocess.run(["git", "tag", "--list"], cwd=HERE,
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if done.returncode != 0:
        return None
    return {t.strip() for t in done.stdout.splitlines() if t.strip()}


# ---- the rules, as a function of the two texts -----------------------------

def verdicts(plan: str, changelog: str,
             have_tags: set[str] | None) -> list[tuple[str, str, bool, str]]:
    """(rule, label, held, detail) for every rule, over these two texts.

    `rule` is the short name an injection names when it says which rule
    must catch it; several labels may share one.
    """
    out: list[tuple[str, str, bool, str]] = []

    def say(rule: str, label: str, held: object, detail: object = "") -> None:
        out.append((rule, label, bool(held), str(detail)))

    rungs = ladder(plan)
    say("ladder", f"plan/9.0.md defines exactly {MILESTONES} milestones",
        len(rungs) == MILESTONES, rungs)
    say("ladder", "...M1 to M8, consecutive, no gap and no repeat",
        rungs == [f"M{n}" for n in range(1, MILESTONES + 1)], rungs)

    try:
        rows = table(plan)
    except ValueError:
        say("table", f"plan/9.0.md has a section {TABLE_HEADING!r}", False,
            "the section is missing, so there is no table to check")
        return out
    say("table", "the table has at least one row", bool(rows), rows)
    if not rows:
        return out

    table_versions = [v for v, _, _ in rows]
    say("table", "...and no version twice",
        len(table_versions) == len(set(table_versions)), table_versions)

    entries = dict(changelog_entries(changelog))
    pre = {v: title for v, title in entries.items() if "-" in v}
    missing_row = sorted(set(pre) - set(table_versions), key=version_key)
    say("row-for-each-entry",
        "every pre-release in the CHANGELOG has a row in the table",
        not missing_row,
        f"no row for {', '.join(missing_row)}" if missing_row else "")
    missing_entry = sorted(set(table_versions) - set(pre))
    say("entry-for-each-row",
        "...and every row names a pre-release the CHANGELOG has",
        not missing_entry,
        f"no CHANGELOG entry for {', '.join(missing_entry)}"
        if missing_entry else "")

    named = {v: milestone_of(cell) for v, cell, _ in rows}
    unknown = sorted(f"{v} -> {named[v]}" for v in named
                     if named[v] not in rungs)
    say("known-milestone",
        "...and every row names a milestone the ladder defines",
        not unknown, unknown)

    said = {v: what for v, _, what in rows}
    empty = sorted(v for v in said if not said[v].strip())
    say("table", "...and every row says what that version published",
        not empty, empty)

    cut = version_key(RULE_FROM)
    for version in sorted(pre, key=version_key):
        title = pre[version]
        found = re.findall(r"\bM(\d+)\b", title)
        if version_key(version) < cut:
            say("exemption",
                f"{version}: before the rule, and named as exempt",
                version in BEFORE_THE_RULE,
                f"{version} is before {RULE_FROM} and is not one of the four "
                f"BEFORE_THE_RULE names; a pre-release cannot be given a "
                f"number below the rule to escape it")
            continue
        say("heading-names-one",
            f"{version}: the heading names exactly one milestone",
            len(found) == 1, f"heading: {title!r} names {found}")
        if len(found) == 1:
            want = named.get(version)
            say("heading-agrees", f"...and it is {want}, as the table says",
                f"M{found[0]}" == want,
                f"heading says M{found[0]}, table says {want}")
            say("heading-form",
                "...written as `M<n>: ` at the start of the title",
                re.match(r"^M\d+: \S", title) is not None,
                f"heading: {title!r}")

    stale = sorted(set(BEFORE_THE_RULE) - set(table_versions))
    say("exemption", "every exempt version is still one the table knows about",
        not stale,
        f"exempt but not in the table: {', '.join(stale)}" if stale else "")
    late = sorted(v for v in BEFORE_THE_RULE if version_key(v) >= cut)
    say("exemption", "...and no exempt version is at or after the rule",
        not late, late)

    if have_tags is not None:
        untagged = [v for v in table_versions if f"v{v}" not in have_tags]
        say("tags", "every version in the table has a tag in this checkout",
            not untagged,
            f"no tag for {', '.join(untagged)}" if untagged else "")
    return out


# ---- the injections --------------------------------------------------------

def a_row(plan: str, version: str) -> str:
    """The table row for `version`, exactly as the plan writes it."""
    for line in plan.splitlines():
        if line.startswith(f"| `{version}`"):
            return line
    raise AssertionError(f"no table row for {version}")


def injections(plan: str, changelog: str) -> list[tuple[str, str, str, str]]:
    """(what was changed, the rule that must catch it, plan, changelog)."""
    out = []

    # 1. A pre-release shipped and nobody added a row.
    out.append((
        "the table row for 9.0.0-alpha.4 is deleted",
        "row-for-each-entry",
        plan.replace(a_row(plan, "9.0.0-alpha.4") + "\n", ""),
        changelog))

    # 2. The same version in the table twice, saying two things. A merge
    #    that keeps both sides of a conflicted table looks exactly like
    #    this, and the later row would otherwise win silently.
    out.append((
        "9.0.0-alpha.4 appears in the table twice, under two milestones",
        "table",
        plan.replace(a_row(plan, "9.0.0-alpha.4"),
                     a_row(plan, "9.0.0-alpha.4") + "\n"
                     + a_row(plan, "9.0.0-alpha.4").replace("M1", "M2", 1)),
        changelog))

    # 3. A row names a milestone that does not exist.
    out.append((
        "the table names M9, which the ladder does not define",
        "known-milestone",
        plan.replace(a_row(plan, "9.0.0-alpha.1"),
                     a_row(plan, "9.0.0-alpha.1").replace("M1", "M9", 1)),
        changelog))

    # 4. A milestone is dropped from the ladder.
    out.append((
        "the M5 heading is removed from the ladder",
        "ladder",
        re.sub(r"^### M5 .*$", "### The runner's tool door", plan,
               count=1, flags=re.MULTILINE),
        changelog))

    # 5. A new pre-release, at the rule, whose heading names no milestone.
    out.append((
        "9.0.0-alpha.5 ships with a heading that names no milestone",
        "heading-names-one",
        plan.replace(a_row(plan, "9.0.0-alpha.4"),
                     a_row(plan, "9.0.0-alpha.4")
                     + "\n| `9.0.0-alpha.5` | M2 | the tag and the crate. |"),
        changelog.replace("## 9.0.0-alpha.4 -",
                          "## 9.0.0-alpha.5 - Types, and what they cost\n\n"
                          "A pre-release.\n\n## 9.0.0-alpha.4 -", 1)))

    # 6. The same, but the heading names the wrong milestone.
    out.append((
        "9.0.0-alpha.5's heading says M4 where the table says M2",
        "heading-agrees",
        plan.replace(a_row(plan, "9.0.0-alpha.4"),
                     a_row(plan, "9.0.0-alpha.4")
                     + "\n| `9.0.0-alpha.5` | M2 | the tag and the crate. |"),
        changelog.replace("## 9.0.0-alpha.4 -",
                          "## 9.0.0-alpha.5 - M4: types, and what they cost\n\n"
                          "A pre-release.\n\n## 9.0.0-alpha.4 -", 1)))

    # 7. The same, right milestone, but not written as the rule says.
    out.append((
        "9.0.0-alpha.5's heading mentions M2 in passing, not as its title",
        "heading-form",
        plan.replace(a_row(plan, "9.0.0-alpha.4"),
                     a_row(plan, "9.0.0-alpha.4")
                     + "\n| `9.0.0-alpha.5` | M2 | the tag and the crate. |"),
        changelog.replace("## 9.0.0-alpha.4 -",
                          "## 9.0.0-alpha.5 - Types, and what M2 cost\n\n"
                          "A pre-release.\n\n## 9.0.0-alpha.4 -", 1)))

    # 8. A pre-release numbered below the rule, to escape the rule.
    out.append((
        "a 9.0.0-alpha.0 appears, below the rule and not exempt",
        "exemption",
        plan.replace(a_row(plan, "9.0.0-alpha.1"),
                     "| `9.0.0-alpha.0` | M1 (in progress) | a tag. |\n"
                     + a_row(plan, "9.0.0-alpha.1")),
        changelog.replace("## 9.0.0-alpha.1 -",
                          "## 9.0.0-alpha.0 - The first one\n\nA pre-release."
                          "\n\n## 9.0.0-alpha.1 -", 1)))

    # 9. A row for a version the CHANGELOG has never heard of.
    out.append((
        "the table gains a row for 9.0.0-alpha.7, which was never released",
        "entry-for-each-row",
        plan.replace(a_row(plan, "9.0.0-alpha.4"),
                     a_row(plan, "9.0.0-alpha.4")
                     + "\n| `9.0.0-alpha.7` | M3 | the tag. |"),
        changelog))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    only_self = "--self" in argv
    plan = PLAN.read_text(encoding="utf-8")
    changelog = CHANGELOG.read_text(encoding="utf-8")
    have = tags()

    if not only_self:
        print("the documents as they are")
        print("-" * 62)
        for _, label, held, detail in verdicts(plan, changelog, have):
            ok(label, held, detail)
        if have is None:
            skip("every row's version is tagged", "not a git checkout")

    print()
    print("and the check is shown to fail: one injection per rule")
    print("-" * 62)
    # The tag rule is not exercised by an injection: every injection that
    # adds a version would trip it as well as the rule it is for, which
    # would prove nothing about the rule it is for. So the injections run
    # with no tag set, and the real documents above are what holds it.
    for changed, rule, bad_plan, bad_changelog in injections(plan, changelog):
        broke = [(r, label) for r, label, held, _
                 in verdicts(bad_plan, bad_changelog, None) if not held]
        ok(f"{changed}: caught by {rule}",
           any(r == rule for r, _ in broke),
           f"rules that went red: {sorted({r for r, _ in broke}) or 'none'}")

    print()
    print(f"{PASSED} correct, {FAILED} wrong"
          + (f", {SKIPPED} skipped" if SKIPPED else ""))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
