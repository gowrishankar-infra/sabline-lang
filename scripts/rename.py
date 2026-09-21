#!/usr/bin/env python3
"""Velaris is renamed Sabline: the rename itself, and the test that it holds.

    python scripts/rename.py --stat     what it would change, file by file
    python scripts/rename.py --write    rewrite the tree
    python scripts/rename.py            the drift test: no old name left where
                                        the new one belongs (exit 1 if there is)

WHY A SCRIPT. The name Velaris belongs to an unrelated company in this
market (velaris.io), so the project is renamed Sabline (8.6.0). That was
27,202 occurrences in 471 files. Nobody can read a diff that size for
correctness, and a hand pass over it would miss things and invent things.
A reviewer can read the twenty lines of rules below instead, and then read
the diff for the places the rules did NOT touch - which is where the
judgement is. Everything else is mechanical and reproducible: run it again
on the previous commit and you get this one.

WHAT IT DOES. One case-preserving substitution, velaris -> sabline, after
two things are taken out of its way:

  1. KEEP - strings in which the old name is the fact, not the project's
     name for itself. A predicate type signed into Statements in 2026 is
     one of these: renaming it in the source would refuse every
     attestation and receipt already signed.
  2. HISTORICAL - whole files that record what happened rather than
     describe what is. The CHANGELOG's old entries, the eight published
     advisories, the documentation pages of releases that really were
     called Velaris.

WHAT IT DOES NOT DO. It does not move files (git mv did that, so git
follows the history), it does not touch the generated site under docs/
(build_docs.py rewrites it), and it cannot tell prose that is right from
prose that is merely renamed. The README's first paragraph, STABILITY.md's
new entry, predicates.py's list of earlier names and the compatibility
shims were written by hand after this ran; the drift test below is what
keeps them honest.

THE DRIFT TEST runs in run_tests.py. It fails on any occurrence of the old
name that is not inside a KEEP string, in a HISTORICAL file, or in ALLOWED
- the short list of places where `velaris` is still the right word: the
alias command kept for one major, the VELARIS_* environment variables
still accepted, the document formats still read, the shim package.
Anything else is drift, and it names the file and line.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

OLD, NEW = "velaris", "sabline"

# ---------------------------------------------------------------------------
# KEEP: the old name is the fact being recorded, in any file
# ---------------------------------------------------------------------------

KEEP: tuple[str, ...] = (
    # The predicate type every capability Statement signed from 4.2 to 8.2.1
    # carries, and the receipt type from 8.1. A name on a domain means what
    # the domain's holder says it means; these two names were published, and
    # `sabline verify` reads them as the types it defines. Renaming them here
    # would refuse every Statement already signed. predicates.py lists them
    # as earlier spellings, and the two pages are still served.
    "https://gowrishankar-infra.github.io/velaris-lang/capability/v1",
    "https://gowrishankar-infra.github.io/velaris-lang/receipt/v1",
    "https://velaris-lang.dev/capability/v1",
    "https://velaris-lang.dev/receipt/v1",
    # Where the Pages site was before 8.3. It redirects, and PROVENANCE.md
    # and the two predicate pages say so.
    "https://gowrishankar-infra.github.io/velaris-lang",
    # A domain registered to someone else. It is the worked example of a
    # predicate type this project does not define and refuses, in SPEC.md,
    # EMBEDDING.md, SECURITY.md and the suites - and it still is one.
    "velaris.dev",
    # The company the name belongs to, named once in the README and once in
    # the CHANGELOG entry so a reader knows why the project moved.
    "velaris.io",
)

# Allowed by the drift test, but not masked from the rewrite: the site's
# former address, which every document that mentions the rename names as
# the address that now redirects. Masking it would have kept 589 links on
# the old domain; the rewrite moves them and prose puts this one back.
REDIRECTS: tuple[str, ...] = (
    "velaris-lang.dev",
)

# ---------------------------------------------------------------------------
# HISTORICAL: whole files that record, rather than describe
# ---------------------------------------------------------------------------

HISTORICAL: tuple[str, ...] = (
    # Every entry before 8.6.0 describes a release that was published under
    # the old name. Rewriting them would make the record say something that
    # did not happen.
    "CHANGELOG.md",
    # The eight published advisories and their request bodies. Their text is
    # what GitHub shows under eight GHSA ids and what the CVE records quote;
    # the affected package really is velaris-lang on PyPI.
    "advisory-*.md",
    "advisory-*.json",
    # The documentation of releases 8.3, 8.4 and 8.5, frozen at the address
    # each was published under. build_docs.py never rewrites another
    # major.minor; these pages are what those releases shipped.
    "docs/8.3/**",
    "docs/8.4/**",
    "docs/8.5/**",
    # The decision record of a change made in 8.2, dated and signed.
    "decisions/0001-split-the-file.md",
    # NOT here: benchmark/results.json. Its only occurrences of the old
    # name are the key of the column the implementation's verdicts are
    # under - the implementation this project ships, which is now called
    # Sabline. No number and no recorded output is touched by renaming it,
    # and build_readme.py reads that key to generate the README's figures.
    # The proof cache of this checkout, not source.
    ".velaris/**",
    ".sabline/**",
)

# ---------------------------------------------------------------------------
# ALLOWED: where `velaris` is still the right word, file by file, and why
#
# Each entry is a file and the strings that may carry the old name in it.
# An occurrence outside a KEEP string, in a file that is not HISTORICAL, is
# drift unless it falls inside one of these.
# ---------------------------------------------------------------------------

ALLOWED: dict[str, tuple[str, ...]] = {
    # ---- the rename itself, and the test that it holds -------------------
    # These two files are ABOUT the old name: the rules above, and the
    # suite that proves every alias below still works. They are the only
    # two where the whole word may appear freely.
    "scripts/rename.py": ("velaris", "Velaris", "VELARIS"),
    "check_rename.py": ("velaris", "Velaris", "VELARIS"),

    # ---- the aliases kept for one major (STABILITY.md rule 2) ------------
    # The `velaris` command. The command line is part of what STABILITY.md
    # covers, so dropping the name would be a break and a major version.
    "pyproject.toml": ("velaris",),
    "npm/package.json": ("velaris",),
    "npm/bin/velaris.js": ("velaris", "Velaris"),
    "sabline/cli.py": ("velaris", "Velaris"),
    # the note about a bad proof budget names the variable the operator
    # wrote, which may be the VELARIS_ spelling (naming.env_name)
    "sabline/prover.py": ("VELARIS_",),
    # The conformance corpus is the one document written under the old
    # name: every published implementation reads that field strictly, and
    # none of them can be changed (sabline-spec 0.14.0).
    "sabline/conform.py": ("velaris.conformance-corpus/1", "velaris"),
    # and the suite that validates against the same schemas
    "check_library.py": ("velaris.", "velaris"),
    # The Action reads the committed baseline and a permissions-ratchet
    # document under either name, so a repository that has not renamed its
    # file does not quietly lose its ratchet the day its pin moves here.
    "action.yml": ("velaris.capabilities", "velaris.permissions-ratchet/1",
                   "velaris"),
    # The `velaris` import, and the three modules an MCP config or a
    # notebook may name. Each is an alias, not a copy.
    "velaris/__init__.py": ("velaris", "Velaris", "VELARIS"),
    "velaris_mcp.py": ("velaris", "Velaris"),
    "velaris_mcp_install.py": ("velaris", "Velaris"),
    "velaris_magic.py": ("velaris", "Velaris"),
    # VelarisError, which is SablineError under the name it had. A program
    # that catches it must go on catching it.
    "sabline/errors.py": ("VelarisError",),
    # velaris_version: the one field whose name carried the project's. It
    # is kept and the new name added beside it, because a required field
    # of a version-1 document may not disappear (sabline/naming.py).
    "sabline/results.py": ("velaris_version",),
    # GET /health names the version under both keys, and deps-diff finds a
    # dependency's lockfile under either name
    "sabline/doors.py": ("velaris",),
    "sabline/upgrades.py": ("velaris.lock", "velaris"),
    "sabline/ratchet.py": ("velaris_version", "velaris.capabilities",
                           "velaris"),
    "sabline/__init__.py": ("velaris.VelarisError", "VelarisError"),
    "tests/api/golden.json": ("VelarisError", "velaris_version",
                              '"velaris": "str"'),
    # Where every old name that is still read is decided: the VELARIS_*
    # environment variables, the velaris.* document formats, the velaris.*
    # file names.
    "sabline/naming.py": ("velaris", "Velaris", "VELARIS"),
    # The playground holds the sabline package's source, VelarisError and
    # naming.py among it (build_playground.py).
    "playground/index.html": ("velaris", "Velaris", "VELARIS"),

    # ---- the documents that say what is still accepted -------------------
    "STABILITY.md": ("velaris", "Velaris", "VELARIS_"),
    "README.md": ("velaris", "Velaris", "VELARIS_"),
    "docs/renamed.md": ("velaris", "Velaris", "VELARIS_"),
    # A policy admits an audit written before the rename.
    "policies/kyverno/require-capability-attestation.yaml":
        ("velaris.audit/1",),
    # The paper's submission log records builds made under the old name.
    "paper/arxiv/README-for-me.txt": ("Velaris", "velaris"),
    "check_policies.py": ("velaris.audit/1",),
    # why naming._said is written once per process and never reset
    "check_pool.py": ("velaris",),
    # why the pre-8.3 card address could not be kept: a repository of that
    # name would end GitHub's redirect from every old repository URL
    "check_urls.py": ("velaris-lang", r"velaris\.dev"),
    # The gate reads the compiler at a tag from before the rename, where the
    # package is velaris/; the differential runs such a tree.
    "release_checks.py": ("velaris",),
    "check_differential.py": ("velaris", "VELARIS_"),
    # the suite that scans for the variables the package reads, and the one
    # place that names velaris.toml outside project.py
    "check_self_budget.py": ("VELARIS_", "velaris.toml"),
    # the sidebar entry for the page that says what the project was called
    "build_docs.py": ("Velaris",),
    # The final release under the old name, and the packages that hold the
    # old names on PyPI and npm so that nobody else can take them.
    "packaging/farewell/**": ("velaris", "Velaris", "VELARIS_"),
    ".github/workflows/farewell.yml": ("velaris", "Velaris"),
    "packaging/placeholders/**": ("velaris", "Velaris"),
}

# Files the script never reads: build outputs, images, caches.
NEVER = (
    "docs/**",          # build_docs.py writes it; docs/*.md are the sources
    "*.png", "*.exe", "*.mcpb", "*.zip", "*.bbl.bak",
    "__pycache__/**", "*.pyc",
)
DOCS_SOURCES = ("docs/*.md", "docs/CNAME")


# ---------------------------------------------------------------------------

def case_of(word: str) -> str:
    """`sabline` in the case `word` is written in. VELARIS -> SABLINE,
    Velaris -> Sabline, anything else -> sabline. --stat names every
    occurrence that is none of the three, so none is renamed blind."""
    if word.isupper():
        return NEW.upper()
    if word[0].isupper() and word[1:].islower():
        return NEW.capitalize()
    return NEW


WORD = re.compile(OLD, re.IGNORECASE)
# velaris-lang.dev was the site; sabline.dev is, and it is shorter, so the
# domain is not renamed by the word rule but replaced whole.
SITE = re.compile(r"velaris-lang\.dev", re.IGNORECASE)


def mask(text: str) -> tuple[str, list[str]]:
    """Take every KEEP string out of the way, longest first so that a
    string inside another is not half-masked."""
    kept: list[str] = []
    for literal in sorted(KEEP, key=len, reverse=True):
        while literal in text:
            text = text.replace(literal, f"\x00{len(kept)}\x00", 1)
            kept.append(literal)
    return text, kept


def unmask(text: str, kept: list[str]) -> str:
    for i, literal in enumerate(kept):
        text = text.replace(f"\x00{i}\x00", literal, 1)
    return text


def rename(text: str) -> str:
    """The whole rule: mask what stays, replace the site, replace the word."""
    text, kept = mask(text)
    text = SITE.sub("sabline.dev", text)
    text = WORD.sub(lambda m: case_of(m.group()), text)
    return unmask(text, kept)


# ---------------------------------------------------------------------------

def matches(path: str, patterns: tuple[str, ...]) -> bool:
    from fnmatch import fnmatch
    for pattern in patterns:
        if fnmatch(path, pattern):
            return True
        if pattern.endswith("/**") and path.startswith(pattern[:-2]):
            return True
    return False


def tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=HERE, check=True,
                         capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def readable(path: str) -> bool:
    if matches(path, DOCS_SOURCES):
        return True
    if matches(path, NEVER):
        return False
    full = HERE / path
    if not full.is_file():
        return False
    try:
        chunk = full.read_bytes()[:8192]
    except OSError:
        return False
    return b"\x00" not in chunk


def read(path: str) -> str | None:
    try:
        return (HERE / path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def unusual_case(text: str) -> set[str]:
    """Occurrences whose case is none of the three the rule knows."""
    odd = set()
    for m in WORD.finditer(text):
        word = m.group()
        if word not in (OLD, OLD.upper(), OLD.capitalize()):
            odd.add(word)
    return odd


def do_write(paths: list[str]) -> int:
    changed = 0
    for path in paths:
        if matches(path, HISTORICAL) or not readable(path):
            continue
        text = read(path)
        if text is None or not WORD.search(text):
            continue
        new = rename(text)
        if new != text:
            (HERE / path).write_text(new, encoding="utf-8", newline="")
            changed += 1
    return changed


def do_stat(paths: list[str]) -> int:
    skipped, odd = [], {}
    rows = []
    for path in paths:
        if not readable(path):
            continue
        text = read(path)
        if text is None or not WORD.search(text):
            continue
        if matches(path, HISTORICAL):
            skipped.append((path, len(WORD.findall(text))))
            continue
        before = len(WORD.findall(text))
        after = len(WORD.findall(rename(text)))
        rows.append((path, before, after))
        strange = unusual_case(text)
        if strange:
            odd[path] = strange
    rows.sort(key=lambda r: -r[1])
    print(f"{len(rows)} files to rewrite, "
          f"{sum(r[1] for r in rows)} occurrences, "
          f"{sum(r[2] for r in rows)} kept by a KEEP string")
    for path, before, after in rows[:40]:
        print(f"  {before:6}  {'(' + str(after) + ' kept)' if after else '':12} {path}")
    print(f"\n{len(skipped)} historical files left alone, "
          f"{sum(n for _, n in skipped)} occurrences")
    for path, n in sorted(skipped, key=lambda r: -r[1])[:20]:
        print(f"  {n:6}  {path}")
    if odd:
        print("\noccurrences whose case is none of velaris/Velaris/VELARIS:")
        for path, words in odd.items():
            print(f"  {path}: {', '.join(sorted(words))}")
    return 0


def drift(paths: list[str]) -> list[tuple[str, int, str]]:
    """Every occurrence of the old name that no rule accounts for."""
    found: list[tuple[str, int, str]] = []
    for path in paths:
        if matches(path, HISTORICAL) or not readable(path):
            continue
        text = read(path)
        if text is None or not WORD.search(text):
            continue
        allowed = list(KEEP) + list(REDIRECTS)
        for pattern, extra in ALLOWED.items():
            if path == pattern or matches(path, (pattern,)):
                allowed.extend(extra)
        masked, _ = mask(text)
        for literal in sorted(set(allowed), key=len, reverse=True):
            masked = masked.replace(literal, "")
        if not WORD.search(masked):
            continue
        # name the lines, not the masked text
        for n, line in enumerate(text.splitlines(), 1):
            rest = line
            for literal in sorted(set(allowed), key=len, reverse=True):
                rest = rest.replace(literal, "")
            if WORD.search(rest):
                found.append((path, n, line.strip()[:120]))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write", action="store_true",
                    help="rewrite the tree (the rename itself)")
    ap.add_argument("--stat", action="store_true",
                    help="what it would change, file by file")
    args = ap.parse_args()
    paths = tracked()
    if args.stat:
        return do_stat(paths)
    if args.write:
        n = do_write(paths)
        print(f"rewrote {n} files")
        return 0
    found = drift(paths)
    if not found:
        print(f"no drift: the old name appears nowhere in {len(paths)} files "
              f"that HISTORICAL, KEEP and ALLOWED do not account for")
        return 0
    print(f"{len(found)} occurrences of the old name are unaccounted for.")
    print("Rename them, or say in ALLOWED or HISTORICAL why they stay.\n")
    for path, n, line in found[:60]:
        print(f"  {path}:{n}: {line}")
    if len(found) > 60:
        print(f"  ... and {len(found) - 60} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
