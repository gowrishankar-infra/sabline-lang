#!/usr/bin/env python3
"""The numbers README.md states about this repository, written from what they
count (8.2).

    python build_readme.py --write   # rewrite every generated value
    python build_readme.py --check   # exit 1 when one differs from its source

A value in running text is marked where it stands, and only the part between
the markers is rewritten:

    <!-- count:examples -->97<!-- /count -->
    <!-- count:benchmark-velaris-missed:word -->two<!-- /count -->

`:word` writes a number from zero to twenty as a word. A whole block is
written between `<!-- generated:NAME -->` and `<!-- /generated -->`: README's
benchmark table is one, from benchmark/results.json.

Inside a fenced code block a comment would be printed, so a count there is
found by the fixed text around it, from IN_TEXT below; so are SPEC.md's
`Version X.Y.Z.` line and its count of currencies, because the documentation
site prints SPEC.md's comments as text. A line in IN_TEXT that is no longer in
its document is a failure, not a count that has quietly stopped being checked,
and so is a count that no document uses. EMBEDDING.md takes the same markers.

Where each value comes from is COUNTS. The proven share, and the two counts of
examples/discount.vel beside it, are what `velaris proofs examples stdlib
--json` measures, and need z3-solver: without it, --check skips them with a
notice and --write leaves them as they are.

check_docs.py runs --check.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

DOCUMENTS = ("README.md", "EMBEDDING.md", "SPEC.md")

WORDS = ("zero one two three four five six seven eight nine ten eleven twelve "
         "thirteen fourteen fifteen sixteen seventeen eighteen nineteen "
         "twenty").split()


def have_prover() -> bool:
    try:
        import z3  # noqa: F401
        return True
    except ImportError:
        return False


class Facts:
    """Each source read once, when a count first asks for it."""

    def __init__(self) -> None:
        self._seen: dict[Any, Any] = {}

    def _once(self, key: Any, make: Any) -> Any:
        if key not in self._seen:
            self._seen[key] = make()
        return self._seen[key]

    @property
    def results(self) -> dict[Any, Any]:
        return cast("dict[Any, Any]", self._once("results", lambda: json.loads(
            (HERE / "benchmark" / "results.json").read_text(encoding="utf-8"))))

    def programs(self, dangerous: bool, category: int | None = None) -> int:
        return sum(1 for p in self.results["programs"]
                   if p["dangerous"] is dangerous
                   and (category is None or p["category"] == category))

    @property
    def proofs(self) -> dict[Any, Any]:
        def measure() -> dict[Any, Any]:
            done = subprocess.run(
                [sys.executable, str(HERE / "velaris.py"), "proofs",
                 "examples", "stdlib", "--json"],
                cwd=HERE, capture_output=True, text=True, timeout=900)
            try:
                return cast("dict[Any, Any]", json.loads(done.stdout))
            except ValueError:
                raise SystemExit("velaris proofs examples stdlib --json did "
                                 f"not answer with JSON (exit "
                                 f"{done.returncode}): {done.stderr[:400]}")
        return cast("dict[Any, Any]", self._once("proofs", measure))

    def proof_file(self, name: str) -> dict[Any, Any]:
        for f in self.proofs["files"]:
            if f["file"].replace("\\", "/").endswith(name):
                return cast("dict[Any, Any]", f)
        raise SystemExit(f"velaris proofs examples stdlib --json names no {name}")

    @property
    def velaris(self) -> Any:
        import velaris
        return velaris


def passes_counted(path: str) -> int:
    """The checks an example that counts its own passes holds: each place it
    adds one to `passed`."""
    text = (HERE / path).read_text(encoding="utf-8")
    return len(re.findall(r"\bpassed = passed \+ 1\b", text))


def expect() -> dict[Any, Any]:
    import run_tests
    return run_tests.EXPECT


def refusals() -> int:
    import check_refusals
    return len(check_refusals.CASES) + len(check_refusals.STRICT_CASES)


def escapes() -> int:
    import check_sandbox
    return len(check_sandbox.ESCAPES)


def corpus_cases() -> int:
    import build_conformance
    return len(build_conformance.corpus()) - 1     # less index.json


def card_words(f: Facts) -> str:
    n = len(f.velaris.card().split())
    return f"{round(n, -2):,}"


# name: (what it is, where it comes from, needs the prover)
COUNTS: dict[str, tuple[str, Callable[[Facts], Any], bool]] = {
    "examples": ("example programs with an expected verdict",
                 lambda f: len(expect()), False),
    "examples-rejected": ("of them built to be rejected",
                          lambda f: sum(1 for v in expect().values()
                                        if v == "REJECTED"), False),
    "benchmark-programs": ("benchmark programs",
                           lambda f: len(f.results["programs"]), False),
    "benchmark-dangerous": ("benchmark programs with a defect",
                            lambda f: f.programs(True), False),
    "benchmark-controls": ("benchmark controls",
                           lambda f: f.programs(False), False),
    "benchmark-velaris-missed": (
        "dangerous benchmark programs Velaris missed",
        lambda f: f.results["totals"]["velaris"]["missed"], False),
    "category-12-dangerous": ("category 12's dangerous programs",
                              lambda f: f.programs(True, 12), False),
    "category-12-controls": ("category 12's controls",
                             lambda f: f.programs(False, 12), False),
    "conformance-cases": ("cases in velaris-spec's corpus, as "
                          "build_conformance.py writes it",
                          lambda f: corpus_cases(), False),
    "card-words": ("words in `velaris card`, to the nearest hundred",
                   card_words, False),
    "stress-checks": ("checks examples/stress.vel counts",
                      lambda f: passes_counted("examples/stress.vel"), False),
    "edges-checks": ("checks examples/edges.vel counts",
                     lambda f: passes_counted("examples/edges.vel"), False),
    "refusals": ("wrong programs in check_refusals.py",
                 lambda f: refusals(), False),
    "sandbox-escapes": ("escape attempts in check_sandbox.py",
                        lambda f: escapes(), False),
    "deps-max-upgrades": ("upgrades one deps-diff --against compares",
                          lambda f: f.velaris.upgrades._DEPS_MAX_UPGRADES,
                          False),
    "currencies": ("currencies in velaris.CURRENCIES",
                   lambda f: len(f.velaris.CURRENCIES), False),
    "version": ("velaris.VERSION", lambda f: f.velaris.VERSION, False),
    "proven": ("functions proven, over examples and stdlib",
               lambda f: f.proofs["totals"]["proven"], True),
    "promised": ("functions that make a promise, over examples and stdlib",
                 lambda f: f.proofs["totals"]["proven"]
                 + f.proofs["totals"]["runtime"], True),
    "proven-share": ("velaris proofs examples stdlib --json's proven_share",
                     lambda f: f.proofs["proven_share"], True),
    "discount-proven": ("functions proven in examples/discount.vel",
                        lambda f: f.proof_file("examples/discount.vel")
                        ["proven"], True),
    "discount-promised": ("functions in examples/discount.vel that promise",
                          lambda f: (lambda d: d["proven"] + d["runtime"])(
                              f.proof_file("examples/discount.vel")), True),
}

# Counts found by the text around them: (document, the text, {name} where
# the value stands). Whitespace in the text matches any whitespace.
IN_TEXT = (
    ("README.md", "velaris card > card.md # ~{card-words} words: paste into "
                  "any model"),
    ("README.md", "# {stress-checks} checks across the whole language"),
    ("README.md", "# {edges-checks} boundary, property and round-trip checks"),
    ("README.md", "# {refusals} wrong programs, each refused correctly"),
    ("README.md", "# {sandbox-escapes} escape attempts, each refused with its "
                  "code"),
    ("README.md", "# velaris-spec's {conformance-cases}-case corpus, L1 to L3"),
    ("SPEC.md", "Version {version}. Where this document"),
    ("SPEC.md", "which today holds {currencies} of them"),
)

GENERATED = {"benchmark-table"}


def as_text(value: Any, style: str | None) -> str:
    if style == "word":
        if not isinstance(value, int) or not 0 <= value < len(WORDS):
            raise SystemExit(f"{value!r} has no word in build_readme.py")
        return WORDS[value]
    return str(value)


def benchmark_table(f: Facts) -> str:
    meta, totals = f.results["meta"], f.results["totals"]

    def minor(v: str) -> str:
        return ".".join(v.split()[0].split(".")[:2])

    lines = ["| | caught before running | caught while running | missed "
             f"| false positives on the {f.programs(False)} controls |",
             "|---|---|---|---|---|"]
    for label, tool in ((f"**Velaris {minor(meta['velaris'])}**", "velaris"),
                        (f"Deno {minor(meta['deno'])}", "deno"),
                        (f"Python {minor(meta['python'])}", "python")):
        t = totals[tool]
        lines.append(f"| {label} | {t['caught-before-run']} | "
                     f"{t['caught-during-run']} | {t['missed']} | "
                     f"{t['false-positive']} |")
    return "\n".join(lines)


MARK = re.compile(r"<!-- count:([a-z0-9-]+)(?::(word))? -->(.*?)<!-- /count -->")
BLOCK = re.compile(r"(<!-- generated:([a-z0-9-]+) -->\n)(.*?)(\n<!-- /generated -->)",
                   re.S)


def in_text_pattern(template: str) -> tuple[Any, ...]:
    """(compiled regex, [(name, style)]) for one IN_TEXT template."""
    parts, names = [], []
    for piece in re.split(r"(\{[a-z0-9-]+(?::word)?\})", template):
        m = re.fullmatch(r"\{([a-z0-9-]+)(?::(word))?\}", piece)
        if m:
            names.append((m.group(1), m.group(2)))
            parts.append(r"([A-Za-z]+|[0-9][0-9.,]*[0-9]|[0-9])")
        else:
            parts.append(r"\s+".join(re.escape(w) for w in piece.split(" ")))
    return re.compile("".join(parts)), names


def build(write: bool) -> int:
    facts = Facts()
    prover = have_prover()
    values: dict[Any, Any] = {}
    skipped: set[Any] = set()

    def value(name: str) -> Any:
        if name not in COUNTS:
            raise SystemExit(f"no count called {name!r} in build_readme.py")
        if COUNTS[name][2] and not prover:
            skipped.add(name)
            return None
        if name not in values:
            values[name] = COUNTS[name][1](facts)
        return values[name]

    used: set[Any] = set()
    wrong: list[Any] = []
    changed: dict[Any, Any] = {}
    texts = {doc: (HERE / doc).read_text(encoding="utf-8")
             for doc in DOCUMENTS}

    for doc in DOCUMENTS:
        text = texts[doc]

        def mark(m: Any, doc: Any = doc) -> Any:
            name, style, said = m.group(1), m.group(2), m.group(3)
            used.add(name)
            got = value(name)
            if got is None:
                return m.group(0)
            want = as_text(got, style)
            if said != want:
                wrong.append(f"{doc}: {name} says {said!r}; "
                             f"{COUNTS[name][0]}: {want!r}")
            return m.group(0).replace(f"-->{said}<!--", f"-->{want}<!--", 1)

        text = MARK.sub(mark, text)

        def block(m: Any, doc: Any = doc) -> Any:
            name = m.group(2)
            used.add(name)
            if name not in GENERATED:
                raise SystemExit(f"{doc}: no generated block called {name!r}")
            want = "\n" + benchmark_table(facts) + "\n"
            if m.group(3) != want:
                wrong.append(f"{doc}: the {name} differs from "
                             "benchmark/results.json")
            return m.group(1) + want + m.group(4)

        text = BLOCK.sub(block, text)
        changed[doc] = text

    for doc, template in IN_TEXT:
        pattern, names = in_text_pattern(template)
        text = changed[doc]
        found = list(pattern.finditer(text))
        if len(found) != 1:
            wrong.append(f"{doc}: {len(found)} places read {template!r}; "
                         "build_readme.py's IN_TEXT expects one")
            continue
        m = found[0]
        pieces, at = [], m.start()
        for i, (name, style) in enumerate(names, 1):
            used.add(name)
            got = value(name)
            said = m.group(i)
            want = said if got is None else as_text(got, style)
            if said != want:
                wrong.append(f"{doc}: {name} says {said!r} in "
                             f"{template!r}; {COUNTS[name][0]}: {want!r}")
            pieces.append(text[at:m.start(i)] + want)
            at = m.end(i)
        changed[doc] = text[:m.start()] + "".join(pieces) + text[at:m.end()] \
            + text[m.end():]

    for name in sorted(set(COUNTS) - used):
        wrong.append(f"the count {name!r} is generated and no document uses it")
    if "benchmark-table" not in used:
        wrong.append("README.md has no <!-- generated:benchmark-table --> block")

    if skipped:
        print("skip  " + ", ".join(sorted(skipped)) + ": z3-solver is not "
              "installed, and they are what the prover proves")
    if write:
        for doc in DOCUMENTS:
            if changed[doc] != texts[doc]:
                (HERE / doc).write_text(changed[doc], encoding="utf-8",
                                        newline="\n")
                print(f"wrote {doc}")
        left = [w for w in wrong if " says " not in w and "differs" not in w]
        for w in left:
            print(f"WRONG  {w}")
        return 1 if left else 0
    for w in wrong:
        print(f"WRONG  {w}")
    counted = len(used & set(COUNTS)) - len(skipped)
    if wrong:
        print(f"{len(wrong)} generated value(s) differ from what they count; "
              "python build_readme.py --write rewrites them")
        return 1
    print(f"every generated value matches what it counts ({counted} counts, "
          f"{len(used & GENERATED)} generated block)")
    return 0


def main(argv: list[Any]) -> int:
    if argv not in (["--write"], ["--check"]):
        print("usage: python build_readme.py --write | --check",
              file=sys.stderr)
        return 2
    return build(write=argv == ["--write"])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
