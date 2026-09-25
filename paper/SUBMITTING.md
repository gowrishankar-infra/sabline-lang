# Submitting sabline.md to arXiv: a checklist

A checklist for the author. The paper has not been submitted; a
submission has been **started** under cs.CR, and four endorsement
requests are out against endorsement code 7KRYIG (section 2). The rules
below were read from arXiv's own pages on 2026-09-11; each section names
the page. Where this file says "tested here", it means on the
maintainer's Windows machine, in a scratch directory, on that date.

## 1. Category: cs.CR, cross-listed to cs.PL

**Settled on 2026-09-22, the other way round from what this section
recommended until then.** The submission and all four endorsement
requests are under cs.CR (endorsement code 7KRYIG), so the choice is
made and is not open. The record of the earlier recommendation, and of
why it moved, is below: it is kept rather than deleted, because a file
that quietly agrees with whatever was decided last is not a record.

What changed, and what did not:

- **The related work moved.** Section 5 now places the paper against
  ChainCaps (cs.CR), Abdelnabi and colleagues on benchmarking agents
  (cs.CR), CaMeL (cs.CR), Microsoft's Wassette and a Wasmtime sandbox
  escape, E2B and Modal as the isolation layer, and language-based
  agent control (cs.PL). Six of the seven works added are read by
  cs.CR readers, and three of them make a claim against an adversary
  that this paper does not. A cs.CR reader is now the one most likely
  to be misled by the paper if it is filed away from them.
- **The paper's claims did not move, and must not.** Sections 3 and 6
  still say the budget is not a security boundary; that it is enforced
  by a Python interpreter in the same process as the program; that
  from 8.4.0 the operating system is asked to hold the same budget
  beneath it - on by default, `--no-confine` to turn it off - and
  holds it fully on Linux, partly on macOS and less on Windows, with
  each run's receipt saying which; and that **there is no evaluation
  against an adversary**, which section 6 now states as a limitation
  of its own and `plan/8.7.md` is the plan for. Filing under cs.CR
  does not license a single stronger sentence, and a moderator reading
  the paper should find it saying less than its category invites, not
  more.
- **Moderators may still reclassify**
  (<https://info.arxiv.org/help/moderation/index.html>). If cs.PL is
  put back as primary, nothing in the paper needs changing.

**What this section recommended until 2026-09-22, kept as the record.**
Primary cs.PL, one cross-list to cs.CR: what the paper contributes is
language design and its implementation - an effect discipline in
signatures checked across the call graph (2.1), the semantics of a
budget checked at each operation (2.2), contracts and what the prover
settles (2.3), and a format and check for a repository's declared
surface (2.4, 2.5), with a compiler and runtime (3) - which is cs.PL's
"language features ... programming approaches ... compilers", and
"cs.CR would be the wrong primary: the paper says plainly that the
budget is not a security boundary (sections 3 and 6), has no attack
evaluation, and does not claim to stop an adversary." That argument is
still true of the paper's claims; what it got wrong is who the paper's
reader is.

arXiv's descriptions (<https://arxiv.org/category_taxonomy>):

- cs.PL: "Covers programming language semantics, language features,
  programming approaches ... Also includes material on compilers
  oriented towards programming languages ... Roughly includes material
  in ACM Subject Classes D.1 and D.3."
- cs.CR: "Covers all areas of cryptography and security including
  authentication, public key cryptosytems, proof-carrying code, etc.
  Roughly includes material in ACM Subject Classes D.4.6 and E.3."
- cs.SE: "Covers design tools, software metrics, testing and
  debugging, programming environments, etc. Roughly includes material
  in all of ACM Subject Classes D.2 ..."

**Settled: primary cs.CR, one cross-list to cs.PL.** The motivation -
running code nobody has read, and gradual attacks - is security, and
so is nearly all of section 5: CaMeL, ChainCaps, TypeGuard, Wassette,
WASI, TACIT, in-toto and SLSA, the sandbox platforms, the gradual-attack
paper and the paper on benchmarking agents. That is cs.CR's "all areas
of cryptography and security", and it is where the readers who most
need to know what this paper does **not** claim are. The cs.PL
cross-list carries the contribution that is language design and its
implementation: an effect discipline in signatures checked across the
call graph (2.1), the semantics of a budget checked at each operation
(2.2), contracts and what the prover settles (2.3), and a format and
check for a repository's declared surface (2.4, 2.5), with a compiler
and runtime (3) - cs.PL's "language features ... programming approaches
... compilers". cs.SE fits the ratchet (a CI check) and could be a
second cross-list; arXiv says "It is rarely appropriate to add more
than one or two cross-lists" and that "Bad cross-lists will be removed"
(<https://info.arxiv.org/help/cross.html>). Moderators may reclassify
either way (<https://info.arxiv.org/help/moderation/index.html>), and
if they put cs.PL back as primary, nothing in the paper changes.

**The one thing filing under cs.CR must not do** is soften what the
paper says about its own limits. It says the budget is not a security
boundary, that from 8.4.0 the operating system holds the same budget
beneath it - by default, and only fully on Linux - and that there is no
evaluation against an adversary. Those sentences stay exactly as strong
as they are.

## 2. What a first-time submitter needs

1. **An account** (<https://arxiv.org/user/register>). arXiv asks for a
   real, accurate identity ("It is a violation of our policies to
   misrepresent your identity"), one account per person, and names in
   the order "Firstname Lastname ... (where Lastname is your family
   name)" (<https://info.arxiv.org/help/prep.html>). With no
   institution, "Independent" is accepted as the organisation
   (<https://info.arxiv.org/help/registerhelp.html>). Linking an ORCID
   iD is recommended. The address used to submit is visible to
   registered arXiv users.
2. **An endorsement.** "arXiv requires that users be endorsed before
   submitting their first paper to arXiv or a new category"
   (<https://info.arxiv.org/help/endorsement.html>). Since 2026-01-21
   an institutional address no longer qualifies on its own: automatic
   endorsement needs both an institutional address and earlier
   authorship in the same endorsement domain; everyone else needs "a
   personal endorsement directly from an established arXiv author in the
   same endorsement domain", and arXiv staff cannot waive or provide one
   (<https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/>).
   With a gmail address and no earlier arXiv paper, the personal route
   is the only one. How it works:
   - start a submission and choose cs.CR; arXiv emails an endorsement
     request with a link and a six-character code. This was done on
     2026-09-22 under cs.CR: the code is 7KRYIG, and four requests are
     out;
   - send that link to someone who has published in cs on arXiv
     recently and who knows you or will read the paper - the abstract
     page's "Which authors of this paper are endorsers?" link shows who
     can endorse; the endorser enters the code at
     <https://arxiv.org/auth/endorse>;
   - arXiv: "it is inappropriate to email large numbers of potential
     endorsers at once, or to repeatedly email the same endorser". Ask
     one or two people, with the paper attached.
3. **The right kind of paper.** Since October 2025 arXiv's cs category
   takes review articles and position papers only after peer review
   (<https://blog.arxiv.org/2025/10/31/attention-authors-updated-practice-for-review-articles-and-position-papers-in-arxiv-cs-category/>).
   This is a research article with an implementation and an
   evaluation, so that rule does not apply to it.
4. **A complete draft.** arXiv expects "complete final drafts"
   (<https://info.arxiv.org/help/policies/content-types.html>). Change
   the YAML `date:` line, which says "Draft of 2026-09-11 - not
   submitted", before building the upload (pandoc drops the HTML comment
   at the top; the date line reaches the PDF).
5. **A statement on AI use, in the paper.** arXiv requires authors "to
   report in their work any significant use of sophisticated tools ...
   in particular text-to-text generative AI", says each author takes
   "full responsibility for all its contents, irrespective of how the
   contents were generated", and that such tools "should not be listed
   as an author"
   (<https://info.arxiv.org/help/moderation/index.html#policy-for-authors-use-of-generative-ai-language-tools>).
   The paper's "Use of generative AI" section, between the conclusion
   and the reproducibility section, is that statement.
6. **Public links.** "Links to code or data sets must resolve to a
   publicly available repository"
   (<https://info.arxiv.org/help/policies/format_requirements.html>).
   Both repositories the paper names are public.

## 3. What to upload: the LaTeX source, not a PDF

**Superseded by the package.** `paper/arxiv/` holds the upload as built
on 2026-09-11 - `sabline.tex` with its bibliography as a BibTeX `.bbl`
(apalike), zipped as `paper/arxiv-submission.zip` - and
`paper/arxiv/README-for-me.txt` gives the form fields and how it was
built and checked with TeX Live 2025's pdflatex. The citeproc route
below still works, but the package is what to upload.

arXiv does "not accept ... PDF created from TeX/LaTeX source"
(<https://info.arxiv.org/help/submit/index.html>); a PDF from pandoc
goes through LaTeX, so upload the `.tex` and let arXiv compile it. arXiv
runs TeX Live 2025 by default, with pdflatex or xelatex; LuaLaTeX is not
supported (<https://info.arxiv.org/help/faq/texlive.html>).

Tools: pandoc (<https://pandoc.org/installing.html>; on Windows
`winget install --id JohnMacFarlane.Pandoc`), and, to check the build
before uploading, a LaTeX system - TeX Live 2025
(<https://tug.org/texlive/>), MiKTeX (`winget install --id
MiKTeX.MiKTeX`), or Tectonic (<https://tectonic-typesetting.github.io/>).

From `paper/`, after editing the date:

    pandoc sabline.md --citeproc --standalone -V geometry:margin=1in -o sabline.tex
    pdflatex sabline.tex
    pdflatex sabline.tex

- `--citeproc` writes the references into the `.tex` (pandoc's
  default style, Chicago author-date), so no `.bib` or `.bbl` is
  uploaded. `--standalone` makes a complete document with the title
  block.
- `-V geometry:margin=1in` gives arXiv's minimum margin ("Minimum 1"
  page margin") and room for the widest code line (83 characters, in
  the reproducibility section). The default body size is 10 pt, inside
  arXiv's 10 to 14.
- Figure 1 is text in a code block, so there are no image files.
- Upload `sabline.tex` alone, then read the PDF arXiv builds from it
  before you confirm.

Tested here: pandoc 3.11 wrote `sabline.tex` from the paper as of this
commit, and Tectonic 0.17.0 (XeTeX engine) compiled it to 11 pages at
1-inch margins with no overfull lines. pdflatex, which is arXiv's
default, has been run on the package since - with TeX Live 2025 on
2026-09-11 and with MiKTeX 25.12 on 2026-09-12, 11 clean pages both
times; `paper/arxiv/README-for-me.txt` records both. The pandoc
template supports both engines, and the only characters outside ASCII
that reach the `.tex` are two in reference names (ø in Bjørner, č in
Bračevac), which pdflatex's T1 encoding covers.

## 4. Metadata

arXiv's metadata fields take ASCII only
(<https://info.arxiv.org/help/prep.html>).

| Field | Enter |
|---|---|
| Title | Sabline: effects in signatures, budgets at run time, and a baseline for a repository's capability surface |
| Authors | Gowri Shankar Palakurthi |
| Abstract | the text in section 6 below |
| Comments | 16 pages, 1 figure, 2 tables. Code: https://github.com/gowrishankar-infra/sabline-lang ; format and conformance corpus: https://github.com/gowrishankar-infra/sabline-spec |
| Primary category | cs.CR |
| Cross-list | cs.PL |
| ACM-class | D.3.3; D.4.6; D.2.4 |
| MSC-class, Report-no, Journal-ref, DOI | leave empty |

- **Authors.** arXiv wants given names first so that it indexes
  Palakurthi as the family name. The paper's own byline, "Palakurthi
  Gowri Shankar", can stay as it is or change to match; that is your
  choice, and arXiv does not require the PDF to match.
- **Comments.** arXiv asks for the number of pages and figures, and
  "submitted to" information if any; no copyright statements. Recount
  the pages from arXiv's build. 16 is this text's count, from MiKTeX
  pdflatex on 2026-09-22 with sabline.tex and sabline.bbl alone in an
  empty folder, which is how arXiv builds it; 11 was the Tectonic
  build's count of a shorter paper, and 12 and 13 were earlier ones.
  paper/arxiv/README-for-me.txt's REBUILT log has each.
- **ACM-class.** arXiv's field takes codes of the 1998 ACM Computing
  Classification System, separated by "a semicolon and a space": D.3.3
  Language Constructs and Features, D.4.6 Security and Protection, D.2.4
  Software/Program Verification. All three were checked against ACM's
  1998 list as archived at web.archive.org (acm.org itself refuses
  automated fetches).

## 5. Licence

arXiv offers six (<https://info.arxiv.org/help/license/index.html>):
CC BY 4.0; CC BY-SA 4.0; CC BY-NC-SA 4.0; CC BY-NC-ND 4.0; the arXiv.org
perpetual, non-exclusive license 1.0; and CC Zero. "The license chosen
is irrevocable and cannot be changed", for that version; a later
version may carry a different one.

**Recommendation: CC BY 4.0.** The format the paper describes is CC0
and the implementation MIT-licensed; CC BY keeps the paper as open as
both while keeping attribution, which CC0 would give up, and arXiv
"encourages choosing a liberal license". The exception: if you mean to
submit the paper to a journal or conference that requires an exclusive
copyright transfer, read its preprint policy first; the arXiv
non-exclusive licence is the choice that commits you to least.

## 6. The abstract, ready to paste

1,729 characters, all ASCII; arXiv's limit is 1,920 ("abstracts longer
than 1920 characters will not be accepted"). Nothing was trimmed. It is
the paper's abstract as it stands, on one line; paste it as one
paragraph.

```text
Code written by language models is increasingly run by people who have not read it. Sabline is a small programming language for that situation. A function's signature declares which of seven effects it may perform, and the compiler checks the declaration across the whole call graph. A runtime refuses any operation outside a budget the operator writes - before the operation happens, and in a way the program cannot catch. Contracts are checked by the Z3 prover where it can settle them, and at run time where it cannot. A repository can commit a baseline of the capability surface its programs need, and a check fails any change that needs more. The central claim is about that surface. Suppose a repository's Sabline programs are held to a committed baseline by a required check. If a change makes a program need an effect, path, host, module or operation count the baseline does not grant, the check fails. It goes on failing at every later commit at which the program still compiles and still needs it, until a person edits the baseline. The claim is not about which function an effect is attributed to: a function renamed in the change that gives it an effect its program already had escapes the function-level rule. On a benchmark of 63 programs, 56 with one defect and 7 correct, each written in Sabline, in JavaScript for Deno and in Python, Sabline caught 54 of the 56 defects, 42 of them before running; Deno caught 32 and Python 28; none of the three flagged a correct program. One of Sabline's two misses is a logic error with no contract; the other no tool should catch. The capability format is published separately, under CC0, with a conformance corpus of 444 cases that an implementation in any language can run.
```

If the paper's abstract changes, count it again: this count is of the
text as pasted, with the Markdown backticks removed and the lines joined
by single spaces.

## 7. The order to do it in

1. Done: the AI-use statement is in the paper, and `paper/arxiv/` holds
   the package, checked with pdflatex; its build leaves out the draft
   date line (section 3).
2. Find one endorser who knows the work; register; start the
   submission in cs.CR and send them the endorsement link. Started:
   four endorsement requests are out under cs.CR, code 7KRYIG.
3. Once endorsed: upload `sabline.tex` and `sabline.bbl` from
   `paper/arxiv/` (zipped locally as `paper/arxiv-submission.zip`, which
   is not committed), enter the metadata (section 4), choose the
   licence (section 5), read arXiv's build, submit.

## 8. The PDF on sabline.dev, for Google Scholar

Separate from arXiv, and not a substitute for it: the paper is also served
at <https://sabline.dev/papers/sabline.pdf>, beside a landing page,
<https://sabline.dev/papers/sabline.html>, that carries the tags Google
Scholar reads - `citation_title`, `citation_author`,
`citation_publication_date`, `citation_pdf_url` and
`citation_technical_report_institution` and `citation_doi` - and shows
the abstract without a click. Scholar's inclusion
guidelines (<https://scholar.google.com/intl/en/scholar/inclusion.html>,
read 2026-09-25) ask for the PDF in the same directory as that page, one
paper to a URL, under 5 MB, the title in 24 points or more and the authors
in 16 to 23 points on the first page, a section headed "References", and no
bitmap (Type 3) fonts.

`python build_paper.py` makes it: the command of README-for-me.txt's step 1
with `--ascii` and `-H scholar.tex`, which sets the title and author sizes,
then pdflatex, bibtex, pdflatex, pdflatex. It rebuilds arXiv's
`sabline.tex` and `sabline.bbl` in the same run, and records in
`paper/built.json` the SHA-256 of `sabline.md`, `references.bib` and
`scholar.tex` as built. `python build_paper.py --check`, which CI runs,
fails when any of them has changed since; `build_docs.py` copies the PDF
to `papers/`, and `PAPER_DATE` there is the day it was built.

**The DOIs** (Zenodo, minted 2026-09-25 from the author's account; the
record names the author with ORCID iD 0009-0007-0004-2955):

- **10.5281/zenodo.22952528, the concept DOI** - all versions; it resolves
  to the newest. It is the one this repository uses: `PAPER_DOI` in
  `build_docs.py`, so the landing page's `citation_doi`, its DOI link and
  its BibTeX; and `doi` in `CITATION.cff`. Cite this one.
- **10.5281/zenodo.22952529, version 1** - one file, `sabline.pdf`, as
  built on 2026-09-25 before the ORCID iD was added to the paper's front
  matter (MD5 `b226d51a24860b1080fd41872bdc2e56`). Nothing here uses it;
  it is for citing those exact bytes. The PDF built since carries the
  ORCID iD in a footnote on the title and is not on Zenodo; uploading it
  as a new version there gives it a DOI of its own under the same concept
  DOI.

