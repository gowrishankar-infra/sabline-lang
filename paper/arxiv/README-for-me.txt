VELARIS PAPER ON ARXIV - WHAT TO PASTE, AND WHAT IS IN THE PACKAGE

This file is for you, not for arXiv. It is NOT inside
..\arxiv-submission.zip: arXiv asks that a submission hold nothing that
is not needed to build the paper, and anything uploaded becomes part of
the public source.

THE PACKAGE
  ..\arxiv-submission.zip holds two files, at the top level of the zip:
    velaris.tex   the paper, converted from velaris.md by pandoc 3.11
    velaris.bbl   the bibliography, made here by BibTeX with apalike.bst
  On the form, choose the processor "pdflatex" and TeX Live 2025 (the
  default). arXiv uses a .bbl when one is uploaded whose name matches
  the .tex, so it will not run BibTeX; no .bib is uploaded.

  The zip is not committed (.gitignore); in a fresh clone, zip these two
  files again, at the top level.

BEFORE YOU UPLOAD
  arXiv requires authors to report significant use of generative AI in
  the paper itself (info.arxiv.org/help/moderation/index.html). The
  paper's "Use of generative AI" section, between the Conclusion and
  Reproducibility, is that statement; velaris.md and velaris.tex carry
  the same text.

  Still to do: find one endorser who knows your work (a personal
  endorsement is required for a first submission since 2026-01-21), and
  read the PDF arXiv builds before you confirm.

FORM FIELDS - paste as they are

Title:
Velaris: effects in signatures, budgets at run time, and a baseline for a repository's capability surface

Authors:
Gowri Shankar Palakurthi
  (arXiv wants given names first so that it indexes Palakurthi as the
  family name. The PDF's byline, from velaris.md, reads "Palakurthi
  Gowri Shankar"; arXiv does not require the two to match.)

Abstract (1729 characters, one line, plain ASCII; the limit is 1920;
no character needed replacing - the abstract has none outside ASCII):
Code written by language models is increasingly run by people who have not read it. Velaris is a small programming language for that situation. A function's signature declares which of seven effects it may perform, and the compiler checks the declaration across the whole call graph. A runtime refuses any operation outside a budget the operator writes - before the operation happens, and in a way the program cannot catch. Contracts are checked by the Z3 prover where it can settle them, and at run time where it cannot. A repository can commit a baseline of the capability surface its programs need, and a check fails any change that needs more. The central claim is about that surface. Suppose a repository's Velaris programs are held to a committed baseline by a required check. If a change makes a program need an effect, path, host, module or operation count the baseline does not grant, the check fails. It goes on failing at every later commit at which the program still compiles and still needs it, until a person edits the baseline. The claim is not about which function an effect is attributed to: a function renamed in the change that gives it an effect its program already had escapes the function-level rule. On a benchmark of 68 programs, 60 with one defect and 8 correct, each written in Velaris, in JavaScript for Deno and in Python, Velaris caught 58 of the 60 defects, 46 of them before running; Deno caught 36 and Python 28; none of the three flagged a correct program. One of Velaris's two misses is a logic error with no contract; the other no tool should catch. The capability format is published separately, under CC0, with a conformance corpus of 456 cases that an implementation in any language can run.

Comments:
13 pages, 1 figure, 2 tables. Code: https://github.com/gowrishankar-infra/velaris-lang ; format and conformance corpus: https://github.com/gowrishankar-infra/velaris-spec

Primary category:
cs.PL (Programming Languages)

Cross-list:
cs.CR (Cryptography and Security)
  Why: the contribution is a language design and its implementation -
  effects in signatures, the semantics of a budget, contracts, a
  compiler - which is cs.PL's "language features ... compilers". The
  motivation and related work are security, hence the cs.CR
  cross-list; but the paper says the budget is not a security boundary
  and has no attack evaluation, so cs.CR would be the wrong primary.

ACM-class:
D.3.3; D.4.6; D.2.4
  From the 1998 ACM Computing Classification System, which arXiv's
  field uses: D.3.3 Language Constructs and Features; D.4.6 Security
  and Protection; D.2.4 Software/Program Verification (it lists
  correctness proofs and programming by contract). Checked against
  ACM's 1998 list as archived at web.archive.org.

MSC-class, Report-no, Journal-ref, DOI:
leave empty

Licence:
CC BY 4.0 (Creative Commons Attribution)
  Why: the format is CC0 and the implementation MIT; CC BY keeps the
  paper as open as both while keeping attribution, which CC0 would
  give up, and arXiv encourages a liberal licence. The choice cannot be
  changed for this version. Exception: if you mean to send the paper to
  a journal or conference that requires an exclusive copyright
  transfer, read its preprint policy first; the arXiv non-exclusive
  licence commits you to least.

HOW THE PACKAGE WAS MADE AND CHECKED (2026-09-11)
  1. pandoc 3.11:
       pandoc velaris.md --standalone --natbib -V biblio-style=apalike
         --shift-heading-level-by=-1 -V geometry:margin=1in -M date=
         -o velaris.tex
     --shift-heading-level-by=-1 makes the paper's "##" headings
     sections; -M date= leaves out the "Draft ... not submitted" date
     line (arXiv also advises against \today in \date); pandoc turns the
     closing "References" heading into the bibliography's title.
  2. TeX Live 2025 (pdfTeX 1.40.28, BibTeX 0.99d), with the .bib beside
     it: pdflatex, bibtex, pdflatex, pdflatex. That run made velaris.bbl.
  3. As arXiv builds it: velaris.tex and velaris.bbl alone in an empty
     folder, pdflatex twice, no bibtex. Result: 11 pages; no undefined
     citation or reference; no overfull or underfull box; no error. One
     warning, harmless: "Package caption Warning: Unused
     \captionsetup[table]", from pandoc's template.
  4. All 15 cited keys have an entry in velaris.bbl, and every entry is
     cited. Both files are pure ASCII: the names with o-slash and c-caron
     are written as TeX accents ({\o}, {\v{c}}).
  5. Figure 1 is text in a verbatim block: it prints whole on page 2,
     columns aligned, 61 characters at its widest against about 89 that
     fit at 1-inch margins.

  Rebuilt the same way after the "Use of generative AI" section was
  added: the .tex differed from the earlier one by that section alone,
  the .bbl came out byte for byte the same, and step 3 still gave 11
  pages with nothing new in the log. The section prints on page 9.

  Not the same as arXiv's system: arXiv's TeX Live 2025 is the state of
  2025-08-03; this build used the final TeX Live 2025 (March 2026). The
  packages the paper loads are standard ones. If arXiv's form suggests
  a processor other than pdflatex, change it to pdflatex.

REBUILT 2026-09-12 (velaris-lang 5.0.0)
  velaris-lang 5.0.0 made `io` the budget a run gets when nobody writes
  one, where every version this paper measured granted all seven
  effects. Nothing the paper measures changes - the benchmark always
  passed an explicit budget, and rerunning it at 5.0.0 moved no verdict
  and no number in Table 1 - but three passages in velaris.md said the
  old thing and now say what changed and when: the related-work
  paragraph on WASI, the one on Boruna, and the reproducibility
  section's list of releases that postdate the paper. The paper still
  describes v4.2.1 and velaris-spec v0.5.1, and the measured numbers
  are unchanged.

  velaris.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the same command as step 1 above. It differs from the
  previous one by those three passages alone. velaris.bbl is unchanged:
  no citation was added or removed.

  NOT YET RE-CHECKED as steps 2 and 3: the three passages are longer
  than what they replace by about twelve lines of body text, so the
  page count needs confirming before upload. Run pdflatex, bibtex,
  pdflatex, pdflatex with the .bib beside it, then velaris.tex and
  velaris.bbl alone in an empty folder, pdflatex twice, no bibtex; if
  the result is not 11 pages, change the Comments field above to match.

REBUILT 2026-09-12 (velaris-lang 4.3.4)
  velaris.md gained a paragraph at the top of the reproducibility
  section saying which two tags the paper describes (v4.2.1 and
  velaris-spec v0.5.1) and that later releases are not reflected in it.
  velaris.tex is pandoc output, so it was regenerated rather than
  edited, with pandoc 3.11 and the same command as step 1 above. The
  new .tex differs from the previous one by that paragraph alone: ten
  added lines, nothing else changed.

  Checked again as steps 2 and 3: pdflatex, bibtex, pdflatex, pdflatex
  with the .bib beside it, then velaris.tex and velaris.bbl alone in an
  empty folder, pdflatex twice, no bibtex. Result: 11 pages, as before,
  so "11 pages, 1 figure, 2 tables" in the Comments field still holds;
  no undefined citation or reference; no overfull or underfull box; no
  error; the same one harmless caption warning. BibTeX produced a .bbl
  whose text is identical to the committed one - the bibliography did
  not change - so velaris.bbl is unchanged and was not rewritten.

  One difference from the 2026-09-11 build, and the only one: that build
  used TeX Live 2025 (pdfTeX 1.40.28, BibTeX 0.99d), which is what arXiv
  runs. No TeX Live was installed on this machine any longer, so this
  rebuild used MiKTeX 25.12 (MiKTeX-pdfTeX 4.23, BibTeX 0.99d), which
  SUBMITTING.md names as one of the options. Both are pdflatex and both
  gave 11 clean pages from the same source, but the engine build is not
  the one arXiv uses. Read the PDF arXiv builds before confirming, which
  was always the last step anyway.


REBUILT 2026-09-12 (related work: the AI-first language field)
  velaris.md's related work gained one paragraph, "AI-first languages",
  at the end of section 5: that a catalogue of languages designed for
  models exists, its three camps, that Velaris sits in two of them, and
  the four entries occupying close ground (Boruna, Thermite, Vera,
  AILANG) with what differs in each. references.bib gained five keys -
  agentlanguages, boruna, thermite, vera, ailang - so the bibliography
  went from 15 entries to 20.

  velaris.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the same command as step 1 above. Because the
  bibliography changed, velaris.bbl WAS rebuilt this time (step 2:
  pdflatex, bibtex, pdflatex, pdflatex with the .bib beside it), unlike
  the 2026-09-12 rebuild above.

  Checked as step 3: velaris.tex and velaris.bbl alone in an empty
  folder, pdflatex twice, no bibtex. Result: 12 pages - one more than
  before, from the added paragraph and five added bibliography entries,
  so the Comments field above now reads "12 pages, 1 figure, 2 tables";
  no undefined citation or reference; no overfull or underfull box; no
  error; the same one harmless caption warning. A third pdflatex run
  cleared the "Label(s) may have changed" notice and left the page count
  at 12. All 20 cited keys have an entry in velaris.bbl and every entry
  is cited; both files are still pure ASCII (checked byte by byte).

  BibTeX warns "entry type for ... isn't style-file defined" for the six
  @software entries, including the four new ones: apalike.bst has no
  @software type and falls back to @misc formatting. The warning is
  pre-existing - velaris_lang and velaris_spec already produced it - and
  the entries render correctly in the .bbl. The catalogue is cited as
  @misc with an author rather than an editor field, because apalike.bst
  ignores editor on @misc and the entry would otherwise print unlabelled.

  Engine: MiKTeX 25.12 again, not the TeX Live arXiv runs. The caveat in
  the entry above still applies - read the PDF arXiv builds before
  confirming.


REBUILT 2026-09-13 (velaris-lang 7.1.0: the benchmark's twelfth category)
  velaris-lang 7.1.0 added a twelfth benchmark category (indirect
  authority: an unchanged caller, and a dependency whose declared budget
  widened between two versions), so the benchmark is 67 programs, 59
  dangerous and 8 controls, and Table 1 reads Velaris 45/12/2, Deno
  5/30/24, Python 0/28/31. velaris.md changed where it reports benchmark
  figures and nowhere else that is measured: the abstract (the form
  field above is updated to match; still 1729 characters, still pure
  ASCII), section 4.1 (the paragraph, Table 1, and a paragraph on
  category 12), the conclusion's benchmark sentence, and the
  reproducibility section, which now says those figures come from
  v7.1.0 while every other number stays pinned to v4.2.1 and
  velaris-spec v0.5.1, and checks out v7.1.0 for Table 1.

  velaris.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the same command as step 1 above; it differs from the
  previous one by those passages, reflowed. velaris.bbl is unchanged:
  no citation was added or removed.

  Checked as step 3: velaris.tex and velaris.bbl alone in an empty
  folder, pdflatex three times, no bibtex. Result: 12 pages, so the
  Comments field above still holds; no undefined citation or reference;
  no overfull or underfull box (a first build had one, from a long line
  in the reproducibility commands, which was shortened in velaris.md);
  the same one harmless caption warning. This also settles the
  2026-09-12 (5.0.0) entry's "NOT YET RE-CHECKED": the page count of the
  current text is 12.

  Engine: MiKTeX 25.12 (MiKTeX-pdfTeX 4.23), not the TeX Live arXiv
  runs; read the PDF arXiv builds before confirming.

  Re-pinned the same day to velaris-lang 7.1.1. 7.1.0 did not import on
  Python 3.10 or 3.11 and is to be yanked; 7.1.1 fixes that and changes
  nothing the benchmark measures (a full run at 7.1.1 wrote every verdict
  and line of evidence 7.1.0's had). velaris.md now names 7.1.1 wherever
  it said where the benchmark figures come from - section 4.1, Table 1's
  caption and the reproducibility section, which checks out v7.1.1 - and
  lists 7.1.1 among the later releases. velaris.tex regenerated with
  pandoc 3.11; velaris.bbl unchanged; step 3 again gives 12 pages, no
  undefined reference, no overfull or underfull box. The abstract did not
  change, so the form field above stands.

  2026-09-14 (8.2.0). The figures are regenerated for 8.2.0: the
  benchmark's from benchmark/results.json (68 programs, 60 with one
  defect and 8 correct; Velaris 58 of 60, 46 before running; Deno 36,
  Python 28), the conformance corpus's from velaris-spec
  tests/index.json (456 cases: 307 at L1, 40 at L2, 109 at L3; 19
  scenarios left out). The reproducibility section checks out v8.2.0.
  velaris.tex regenerated with pandoc 3.11; velaris.bbl unchanged. The
  form's abstract above is updated to match (1729 characters, plain
  ASCII), and the Comments field reads 13 pages: velaris.tex and
  velaris.bbl alone in an empty folder, MiKTeX pdflatex three times, no
  bibtex, give 13 pages, no undefined reference, no overfull box. Read
  the PDF arXiv builds before confirming.
