SABLINE PAPER ON ARXIV - WHAT TO PASTE, AND WHAT IS IN THE PACKAGE

NOTE (2026-09-20, 8.6.0): the project was renamed Velaris -> Sabline,
because the name Velaris belongs to an unrelated company (velaris.io).
Nothing has been submitted, so the paper is renamed with everything else:
paper/sabline.md, and sabline.tex and sabline.bbl here. The REBUILT log at
the bottom of this file is a record of builds made before the rename - it
names releases (5.0.0, 7.1.1, 8.2.0) that were published as Velaris, and
the pandoc commands in it were run on files called velaris.md and
velaris.tex. The names in it were renamed with the rest of the tree; the
dates, versions, page counts and engine versions are untouched.

DONE 2026-09-22: the rename's outstanding rebuild. sabline.tex was
regenerated from sabline.md by pandoc (step 1 below) rather than edited,
sabline.bbl was rebuilt by BibTeX, and both were checked as steps 2 and 3.
The page count in the Comments field is now this text's own, measured, not
8.2.0's. See the last REBUILT entry.

This file is for you, not for arXiv. It is NOT inside
..\arxiv-submission.zip: arXiv asks that a submission hold nothing that
is not needed to build the paper, and anything uploaded becomes part of
the public source.

THE PACKAGE
  ..\arxiv-submission.zip holds two files, at the top level of the zip:
    sabline.tex   the paper, converted from sabline.md by pandoc 3.11
    sabline.bbl   the bibliography, made here by BibTeX with apalike.bst
  On the form, choose the processor "pdflatex" and TeX Live 2025 (the
  default). arXiv uses a .bbl when one is uploaded whose name matches
  the .tex, so it will not run BibTeX; no .bib is uploaded.

  The zip is not committed (.gitignore); in a fresh clone, zip these two
  files again, at the top level.

BEFORE YOU UPLOAD
  arXiv requires authors to report significant use of generative AI in
  the paper itself (info.arxiv.org/help/moderation/index.html). The
  paper's "Use of generative AI" section, between the Conclusion and
  Reproducibility, is that statement; sabline.md and sabline.tex carry
  the same text.

  Still to do: get one endorsement (a personal endorsement is required
  for a first submission since 2026-01-21; four requests are out under
  cs.CR against code 7KRYIG), and read the PDF arXiv builds before you
  confirm.

FORM FIELDS - paste as they are

Title:
Sabline: effects in signatures, budgets at run time, and a baseline for a repository's capability surface

Authors:
Gowri Shankar Palakurthi
  (arXiv wants given names first so that it indexes Palakurthi as the
  family name. The PDF's byline, from sabline.md, reads "Palakurthi
  Gowri Shankar"; arXiv does not require the two to match.)

Abstract (1832 characters, one line, plain ASCII; the limit is 1920;
no character needed replacing - the abstract has none outside ASCII.
CORRECTED 2026-09-22: this field had been left at 8.2.0's text, which
said 68 programs, 60 with one defect and 8 correct, Sabline 58 of 60
and 46 before running, Deno 36, Python 28. UPDATED 2026-09-23 for the
benchmark's categories 16 to 20 and the competitor comparison: 102/80/22,
70/54/51/32, 4 false positives, 18 programs where a competitor does
better. The text below is copied from sabline.md and the count is of
that text):
Code written by language models is increasingly run by people who have not read it. Sabline is a small programming language for that situation. A function's signature declares which of seven effects it may perform, and the compiler checks the declaration across the whole call graph. A runtime refuses any operation outside a budget the operator writes - before the operation happens, and in a way the program cannot catch. Contracts are checked by the Z3 prover where it can settle them, and at run time where it cannot. A repository can commit a baseline of the capability surface its programs need, and a check fails any change that needs more. The central claim is about that surface. Suppose a repository's Sabline programs are held to a committed baseline by a required check. If a change makes a program need an effect, path, host, module or operation count the baseline does not grant, the check fails. It goes on failing at every later commit at which the program still compiles and still needs it, until a person edits the baseline. The claim is not about which function an effect is attributed to: a function renamed in the change that gives it an effect its program already had escapes the function-level rule. On a benchmark of 102 programs, 80 with one defect and 22 correct, each written in Sabline, in JavaScript for Deno and in Python, Sabline caught 70 of the 80 defects, 54 of them before running; Deno caught 51 and Python 32. Sabline stopped 4 of the correct programs, the others none; eight of its ten misses are in five categories written for it to lose; and against five more tools, each in its own runtime, one or another does better than Sabline on 18 programs. The capability format is published separately, under CC0, with a conformance corpus of 456 cases that an implementation in any language can run.

Comments:
19 pages, 1 figure, 3 tables. Code: https://github.com/gowrishankar-infra/sabline-lang ; format and conformance corpus: https://github.com/gowrishankar-infra/sabline-spec

Primary category:
cs.CR (Cryptography and Security)

Cross-list:
cs.PL (Programming Languages)
  CHANGED 2026-09-22, the other way round from every build above. The
  submission and all four endorsement requests are under cs.CR
  (endorsement code 7KRYIG), so this is settled; paper/SUBMITTING.md
  section 1 carries the argument and keeps the earlier recommendation
  as the record.
  Why: the motivation and nearly all of the related work are security -
  CaMeL, ChainCaps, TypeGuard, Wassette, WASI, TACIT, in-toto and SLSA,
  the sandbox platforms, the gradual-attack paper and the paper on
  benchmarking agents - and a cs.CR reader is the one most likely to be
  misled if the paper is filed away from them. The contribution that is
  language design and its implementation carries the cs.PL cross-list.
  What this does NOT change: the paper still says the budget is not a
  security boundary, that from 8.4.0 the operating system holds the
  same budget beneath it (by default, fully only on Linux), and that
  there is no evaluation against an adversary - section 6 now states
  that last one as a limitation of its own, and plan/8.7.md is the plan
  for one. The category does not license a stronger sentence anywhere.

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
       pandoc sabline.md --standalone --natbib -V biblio-style=apalike
         --shift-heading-level-by=-1 -V geometry:margin=1in -M date=
         -o sabline.tex
     --shift-heading-level-by=-1 makes the paper's "##" headings
     sections; -M date= leaves out the "Draft ... not submitted" date
     line (arXiv also advises against \today in \date); pandoc turns the
     closing "References" heading into the bibliography's title.
  2. TeX Live 2025 (pdfTeX 1.40.28, BibTeX 0.99d), with the .bib beside
     it: pdflatex, bibtex, pdflatex, pdflatex. That run made sabline.bbl.
  3. As arXiv builds it: sabline.tex and sabline.bbl alone in an empty
     folder, pdflatex twice, no bibtex. Result: 11 pages; no undefined
     citation or reference; no overfull or underfull box; no error. One
     warning, harmless: "Package caption Warning: Unused
     \captionsetup[table]", from pandoc's template.
  4. All 15 cited keys have an entry in sabline.bbl, and every entry is
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

REBUILT 2026-09-22 (related work: six more systems, and cs.CR primary)
  sabline.md's section 5 was rewritten. It now says, for each piece of
  work, WHERE THAT WORK IS AHEAD OF SABLINE and not only how Sabline
  differs, and it adds six systems: language-based agent control and its
  TypeGuard prototype (arXiv:2605.12863), ChainCaps (arXiv:2605.26542,
  AIWILD at ICML 2026), Microsoft's Wassette together with the Wasmtime
  filesystem sandbox escape published on 2026-08-20 (RUSTSEC-2026-0269 /
  GHSA-vqjp-4c8c-hfgg), E2B and Modal as the isolation layer Sabline
  combines with, and Abdelnabi and colleagues on why benchmarking agents
  is hard (arXiv:2605.22568). CaMeL's paragraph was rewritten to the same
  shape. Section 6 gained one limitation - that there is NO evaluation
  against an adversary, and that plan/8.7.md is a plan for one and not a
  result - and the reproducibility section gained a paragraph naming the
  four files section 5 cites that are at the tip of main rather than at
  either pinned tag.

  Every citation was checked against its own source on 2026-09-22, not
  against a summary: the three arXiv entries against their abstract pages
  and arXiv's API metadata (title, every author in order, submission
  date, primary category, and ChainCaps' venue from its own arXiv
  comment); Wassette against its repository, its documentation and the
  notes of its 0.7.1 release; the advisory against both the RUSTSEC entry
  and the Bytecode Alliance's GHSA page; E2B's and Modal's quoted
  sentences against the pages the bibliography names. references.bib's
  header records this. Nothing was cited that could not be checked.

  references.bib went from 20 entries to 27: zhou2026lbac,
  jiang2026chaincaps, abdelnabi2026measuring, wassette,
  rustsec2026trailing, e2b, modal.

  CATEGORY CHANGED: primary cs.CR, cross-list cs.PL - the other way round
  from every build above. The submission and four endorsement requests
  are under cs.CR (code 7KRYIG). The form fields above are updated, and
  paper/SUBMITTING.md section 1 keeps the earlier cs.PL recommendation as
  the record of what changed and why. No claim in the paper was softened
  or strengthened for the category.

  sabline.tex is pandoc output and was REGENERATED, not edited, with
  pandoc 3.11 and the same command as step 1 above - which also clears
  the rename's outstanding rebuild, noted at the top of this file.
  Because the bibliography changed, sabline.bbl WAS rebuilt (step 2:
  pdflatex, bibtex, pdflatex, pdflatex with the .bib beside it). BibTeX
  gave the familiar "entry type ... isn't style-file defined" warning for
  the seven @software entries, one more than before because wassette is
  one, and no other warning.

  Checked as step 3: sabline.tex and sabline.bbl alone in an empty
  folder, pdflatex three times, no bibtex. Result: 16 pages - three more
  than 8.2.0's 13, from the longer related work, the added limitation,
  the reproducibility paragraph and seven more bibliography entries - so
  the Comments field above now reads 16. No undefined citation or
  reference; no overfull or underfull box; no error; the same one
  harmless caption warning ("Unused \captionsetup[table]"). All 27 cited
  keys have an entry in sabline.bbl, every entry is cited, and both files
  are pure ASCII (checked byte by byte).

  The abstract form field above was ALSO corrected in this pass: it had
  been left at 8.2.0's benchmark figures while sabline.md's abstract has
  carried 8.3.0's since the fourteenth and fifteenth categories were
  added. It is now copied from sabline.md; the character count is of that
  text. This was a defect in the package, not a change of claim.

  Engine: MiKTeX 25.12 (MiKTeX-pdfTeX 4.23, BibTeX 0.99e), not the TeX
  Live arXiv runs. Read the PDF arXiv builds before confirming.


REBUILT 2026-09-12 (sabline-lang 5.0.0)
  sabline-lang 5.0.0 made `io` the budget a run gets when nobody writes
  one, where every version this paper measured granted all seven
  effects. Nothing the paper measures changes - the benchmark always
  passed an explicit budget, and rerunning it at 5.0.0 moved no verdict
  and no number in Table 1 - but three passages in sabline.md said the
  old thing and now say what changed and when: the related-work
  paragraph on WASI, the one on Boruna, and the reproducibility
  section's list of releases that postdate the paper. The paper still
  describes v4.2.1 and sabline-spec v0.5.1, and the measured numbers
  are unchanged.

  sabline.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the same command as step 1 above. It differs from the
  previous one by those three passages alone. sabline.bbl is unchanged:
  no citation was added or removed.

  NOT YET RE-CHECKED as steps 2 and 3: the three passages are longer
  than what they replace by about twelve lines of body text, so the
  page count needs confirming before upload. Run pdflatex, bibtex,
  pdflatex, pdflatex with the .bib beside it, then sabline.tex and
  sabline.bbl alone in an empty folder, pdflatex twice, no bibtex; if
  the result is not 11 pages, change the Comments field above to match.

REBUILT 2026-09-12 (sabline-lang 4.3.4)
  sabline.md gained a paragraph at the top of the reproducibility
  section saying which two tags the paper describes (v4.2.1 and
  sabline-spec v0.5.1) and that later releases are not reflected in it.
  sabline.tex is pandoc output, so it was regenerated rather than
  edited, with pandoc 3.11 and the same command as step 1 above. The
  new .tex differs from the previous one by that paragraph alone: ten
  added lines, nothing else changed.

  Checked again as steps 2 and 3: pdflatex, bibtex, pdflatex, pdflatex
  with the .bib beside it, then sabline.tex and sabline.bbl alone in an
  empty folder, pdflatex twice, no bibtex. Result: 11 pages, as before,
  so "11 pages, 1 figure, 2 tables" in the Comments field still holds;
  no undefined citation or reference; no overfull or underfull box; no
  error; the same one harmless caption warning. BibTeX produced a .bbl
  whose text is identical to the committed one - the bibliography did
  not change - so sabline.bbl is unchanged and was not rewritten.

  One difference from the 2026-09-11 build, and the only one: that build
  used TeX Live 2025 (pdfTeX 1.40.28, BibTeX 0.99d), which is what arXiv
  runs. No TeX Live was installed on this machine any longer, so this
  rebuild used MiKTeX 25.12 (MiKTeX-pdfTeX 4.23, BibTeX 0.99d), which
  SUBMITTING.md names as one of the options. Both are pdflatex and both
  gave 11 clean pages from the same source, but the engine build is not
  the one arXiv uses. Read the PDF arXiv builds before confirming, which
  was always the last step anyway.


REBUILT 2026-09-12 (related work: the AI-first language field)
  sabline.md's related work gained one paragraph, "AI-first languages",
  at the end of section 5: that a catalogue of languages designed for
  models exists, its three camps, that Sabline sits in two of them, and
  the four entries occupying close ground (Boruna, Thermite, Vera,
  AILANG) with what differs in each. references.bib gained five keys -
  agentlanguages, boruna, thermite, vera, ailang - so the bibliography
  went from 15 entries to 20.

  sabline.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the same command as step 1 above. Because the
  bibliography changed, sabline.bbl WAS rebuilt this time (step 2:
  pdflatex, bibtex, pdflatex, pdflatex with the .bib beside it), unlike
  the 2026-09-12 rebuild above.

  Checked as step 3: sabline.tex and sabline.bbl alone in an empty
  folder, pdflatex twice, no bibtex. Result: 12 pages - one more than
  before, from the added paragraph and five added bibliography entries,
  so the Comments field above now reads "12 pages, 1 figure, 2 tables";
  no undefined citation or reference; no overfull or underfull box; no
  error; the same one harmless caption warning. A third pdflatex run
  cleared the "Label(s) may have changed" notice and left the page count
  at 12. All 20 cited keys have an entry in sabline.bbl and every entry
  is cited; both files are still pure ASCII (checked byte by byte).

  BibTeX warns "entry type for ... isn't style-file defined" for the six
  @software entries, including the four new ones: apalike.bst has no
  @software type and falls back to @misc formatting. The warning is
  pre-existing - sabline_lang and sabline_spec already produced it - and
  the entries render correctly in the .bbl. The catalogue is cited as
  @misc with an author rather than an editor field, because apalike.bst
  ignores editor on @misc and the entry would otherwise print unlabelled.

  Engine: MiKTeX 25.12 again, not the TeX Live arXiv runs. The caveat in
  the entry above still applies - read the PDF arXiv builds before
  confirming.


REBUILT 2026-09-13 (sabline-lang 7.1.0: the benchmark's twelfth category)
  sabline-lang 7.1.0 added a twelfth benchmark category (indirect
  authority: an unchanged caller, and a dependency whose declared budget
  widened between two versions), so the benchmark is 67 programs, 59
  dangerous and 8 controls, and Table 1 reads Sabline 45/12/2, Deno
  5/30/24, Python 0/28/31. sabline.md changed where it reports benchmark
  figures and nowhere else that is measured: the abstract (the form
  field above is updated to match; still 1729 characters, still pure
  ASCII), section 4.1 (the paragraph, Table 1, and a paragraph on
  category 12), the conclusion's benchmark sentence, and the
  reproducibility section, which now says those figures come from
  v7.1.0 while every other number stays pinned to v4.2.1 and
  sabline-spec v0.5.1, and checks out v7.1.0 for Table 1.

  sabline.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the same command as step 1 above; it differs from the
  previous one by those passages, reflowed. sabline.bbl is unchanged:
  no citation was added or removed.

  Checked as step 3: sabline.tex and sabline.bbl alone in an empty
  folder, pdflatex three times, no bibtex. Result: 12 pages, so the
  Comments field above still holds; no undefined citation or reference;
  no overfull or underfull box (a first build had one, from a long line
  in the reproducibility commands, which was shortened in sabline.md);
  the same one harmless caption warning. This also settles the
  2026-09-12 (5.0.0) entry's "NOT YET RE-CHECKED": the page count of the
  current text is 12.

  Engine: MiKTeX 25.12 (MiKTeX-pdfTeX 4.23), not the TeX Live arXiv
  runs; read the PDF arXiv builds before confirming.

  Re-pinned the same day to sabline-lang 7.1.1. 7.1.0 did not import on
  Python 3.10 or 3.11 and is to be yanked; 7.1.1 fixes that and changes
  nothing the benchmark measures (a full run at 7.1.1 wrote every verdict
  and line of evidence 7.1.0's had). sabline.md now names 7.1.1 wherever
  it said where the benchmark figures come from - section 4.1, Table 1's
  caption and the reproducibility section, which checks out v7.1.1 - and
  lists 7.1.1 among the later releases. sabline.tex regenerated with
  pandoc 3.11; sabline.bbl unchanged; step 3 again gives 12 pages, no
  undefined reference, no overfull or underfull box. The abstract did not
  change, so the form field above stands.

  2026-09-14 (8.2.0). The figures are regenerated for 8.2.0: the
  benchmark's from benchmark/results.json (68 programs, 60 with one
  defect and 8 correct; Sabline 58 of 60, 46 before running; Deno 36,
  Python 28), the conformance corpus's from sabline-spec
  tests/index.json (456 cases: 307 at L1, 40 at L2, 109 at L3; 19
  scenarios left out). The reproducibility section checks out v8.2.0.
  sabline.tex regenerated with pandoc 3.11; sabline.bbl unchanged. The
  form's abstract above is updated to match (1729 characters, plain
  ASCII), and the Comments field reads 13 pages: sabline.tex and
  sabline.bbl alone in an empty folder, MiKTeX pdflatex three times, no
  bibtex, give 13 pages, no undefined reference, no overfull box. Read
  the PDF arXiv builds before confirming.


REBUILT 2026-09-23 (the benchmark's categories 16 to 20, and the
competitor comparison; 8.7, not released)
  The benchmark grew to 102 programs, and a first comparison against five
  other tools had shown a corpus Sabline could not lose, so five
  categories were added for it to lose and the scoring was corrected for
  every tool alike. sabline.md changes in the abstract, section 4.1 and
  Table 1 (the re-recorded benchmark), a new section 4.2 and Table 2 (the
  competitors), the renumbered sections 4.3 and 4.4, one limitation, the
  conclusion, and the reproducibility section, which pins the new numbers
  to the commit that added the categories. The abstract field above is
  copied again and counted again (1832 characters).

  sabline.tex is pandoc output and was regenerated, not edited, with
  pandoc 3.11 and the command of step 1. sabline.bbl is unchanged: the
  one new citation is to an entry already cited. Checked as step 3
  (the two files alone, pdflatex three times, no bibtex, MiKTeX 25.12):
  18 pages - two more, from section 4.2 - so the Comments field now reads
  18 pages and 3 tables. No undefined citation or reference, no overfull
  or underfull box, no error; the same one harmless caption warning. Both
  files are pure ASCII.


REBUILT 2026-09-23 again (AgentDojo, and the stale adversary claim)
  Related work and section 6 still said Sabline had no evaluation against
  an adversary, which the AgentDojo run (pull request #103) had made
  untrue. A new section 4.3 reports it - 21 of 21 tasks, 19 of 105
  attacks landing under a task budget, every one reusing a tool the task
  was granted - with its limits: no model in the loop, so utility is
  AgentDojo's reference solution and attack success an upper bound
  rather than a measured steer rate; no per-value provenance, so CaMeL
  and ChainCaps should do better on those 19. The related-work
  paragraphs on CaMeL, TypeGuard, ChainCaps and benchmarking, and the
  limitation, now say that; sections 4.4 and 4.5 are renumbered. The
  abstract is unchanged (the field above still matches, 1832 characters).

  sabline.tex was regenerated by pandoc 3.11 with the command of step 1.
  sabline.bbl WAS rebuilt, because AgentDojo is cited now
  (debenedetti2024agentdojo, arXiv:2406.13352, authors checked against
  DataCite): pdflatex, bibtex, pdflatex, pdflatex with the .bib beside it,
  MiKTeX 25.12; BibTeX gave the familiar seven @software warnings and no
  other. Checked as step 3 (the two files alone, pdflatex three times, no
  bibtex): 19 pages - one more, from section 4.3 - so the Comments field
  reads 19. No undefined citation or reference, no overfull or underfull
  box, no error; the one harmless caption warning. All 28 cited keys have
  an entry and every entry is cited; both files are pure ASCII.
