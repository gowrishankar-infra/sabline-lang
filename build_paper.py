#!/usr/bin/env python3
"""The paper, built: arXiv's source and the PDF sabline.dev serves (8.7).

    python build_paper.py            both, then paper/built.json
    python build_paper.py --check    fail if paper/sabline.md, the
                                     bibliography or scholar.tex changed
                                     since the PDF and the .tex were built

paper/SUBMITTING.md and paper/arxiv/README-for-me.txt describe the arXiv
package by hand; this is the same pandoc command, run for both outputs:

- paper/arxiv/sabline.tex and sabline.bbl - pandoc 3.11 with the command in
  README-for-me.txt, plus --ascii, so a name with an umlaut in the text is
  written as a TeX accent and the .tex stays pure ASCII, as arXiv's
  package always has; then pdflatex, bibtex, pdflatex, pdflatex with the
  .bib beside it, which makes the .bbl.
- paper/sabline.pdf - the same, with paper/scholar.tex in the preamble:
  the title at 24 points and the authors at 16, which Google Scholar's
  inclusion guidelines ask a PDF's first page to have. build_docs.py copies
  it to papers/sabline.pdf, beside the landing page that carries the
  citation_* tags.

It needs pandoc and a TeX system with pdflatex and bibtex (MiKTeX or TeX
Live), so a person runs it and commits what it writes; CI has neither, and
runs --check, which reads paper/built.json: the SHA-256 of each source as
it was built from. A source changed and not rebuilt is a failure, so the PDF
on the site cannot silently fall behind the paper in the repository.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAPER = HERE / "paper"
SOURCES = ("sabline.md", "references.bib", "scholar.tex")
BUILT = PAPER / "built.json"
PANDOC = ["pandoc", "sabline.md", "--standalone", "--natbib",
          "-V", "biblio-style=apalike", "--shift-heading-level-by=-1",
          "-V", "geometry:margin=1in", "-M", "date=", "--ascii"]


def digest(name: str) -> str:
    data = (PAPER / name).read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def run(args: list[str], cwd: Path) -> str:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.stdout + done.stderr


def latex(where: Path) -> str:
    """pdflatex, bibtex, pdflatex, pdflatex: the last run's log."""
    run(["pdflatex", "-interaction=nonstopmode", "sabline.tex"], where)
    run(["bibtex", "sabline"], where)
    run(["pdflatex", "-interaction=nonstopmode", "sabline.tex"], where)
    return run(["pdflatex", "-interaction=nonstopmode", "sabline.tex"], where)


def pages(log: str) -> int:
    m = re.search(r"Output written on sabline\.pdf \((\d+) pages?", log)
    if not m:
        raise SystemExit("pdflatex wrote no PDF:\n" + log[-2000:])
    return int(m.group(1))


def build() -> int:
    for tool in ("pandoc", "pdflatex", "bibtex"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is not installed; see this file's "
                             "docstring")
    report: dict[str, object] = {}
    for kind, extra in (("arxiv", []), ("site", ["-H", "scholar.tex"])):
        with tempfile.TemporaryDirectory() as tmp:
            where = Path(tmp)
            out = run(PANDOC + extra + ["-o", str(where / "sabline.tex")],
                      PAPER)
            if not (where / "sabline.tex").is_file():
                raise SystemExit("pandoc wrote nothing:\n" + out)
            tex = (where / "sabline.tex").read_bytes()
            if any(b > 127 for b in tex):
                raise SystemExit(f"{kind}: the .tex is not pure ASCII")
            shutil.copy(PAPER / "references.bib", where)
            log = latex(where)
            n = pages(log)
            problems = [ln for ln in log.splitlines()
                        if re.search(r"undefined|Overfull|Underfull|^! ", ln)]
            if problems:
                raise SystemExit(f"{kind}: " + "\n".join(problems[:10]))
            if kind == "arxiv":
                (PAPER / "arxiv" / "sabline.tex").write_bytes(tex)
                shutil.copy(where / "sabline.bbl",
                            PAPER / "arxiv" / "sabline.bbl")
            else:
                shutil.copy(where / "sabline.pdf", PAPER / "sabline.pdf")
            report[kind] = {"pages": n}
            print(f"{kind}: {n} pages, no undefined reference, no overfull "
                  "or underfull box")
    engine = run(["pdflatex", "--version"], HERE).splitlines()[0]
    record = {"built": datetime.now(timezone.utc).date().isoformat(),
              "engine": engine,
              "sources": {name: digest(name) for name in SOURCES},
              **report}
    BUILT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8",
                     newline="\n")
    print(f"wrote paper/arxiv/sabline.tex, sabline.bbl, paper/sabline.pdf "
          f"and paper/built.json ({engine})")
    return 0


def check() -> int:
    if not BUILT.is_file() or not (PAPER / "sabline.pdf").is_file():
        print("paper/built.json or paper/sabline.pdf is missing "
              "(python build_paper.py)")
        return 1
    record = json.loads(BUILT.read_text(encoding="utf-8"))
    stale = [name for name in SOURCES
             if record.get("sources", {}).get(name) != digest(name)]
    if stale:
        print("the paper changed since its PDF and .tex were built: "
              + ", ".join(f"paper/{n}" for n in stale)
              + " (python build_paper.py, which needs pandoc and pdflatex)")
        return 1
    print(f"paper/sabline.pdf and paper/arxiv/sabline.tex are built from "
          f"the paper as it is ({record['built']}, "
          f"{record['site']['pages']} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv[1:] else build())
