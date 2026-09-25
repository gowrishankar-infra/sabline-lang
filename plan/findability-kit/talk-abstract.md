# Talk abstract

## Where not to send it as written

Several CFPs forbid text a model wrote, and this abstract is such text (read
2026-09-25, `plan/findability-research/venues.md`):

- **Black Hat** (Asia Briefings, Arsenal, Summits): "LLM-generated text is
  prohibited".
- **RSAC 2027** and the **CNCF events** (KubeCon EU, Open Source SecurityCon,
  Agentics Day) warn against it.

For those, use this as notes and write your own. For the others, read the
CFP's rules on the day before using any of it, and rewrite it in your voice
either way. Deadlines found open on 2026-09-25 included BSides London
(30 Sep), 40C3 (9 Oct), CactusCon (10 Oct), DefCamp (15 Oct), NDC Security
(18 Oct), DistrictCon (30 Oct), SCaLE (1 Nov), BSides Seattle (1 Nov; blind
review, 150 and 400 word limits), CypherCon (9 Jan) and BSides Groningen
(31 Jan); the venues file has each CFP's page and limits.

## Title

Run code an AI wrote without handing it everything you can reach

## Abstract (about 150 words)

An agent writes a script, and the script runs with everything its user can
reach: the `.env` file, the SSH keys, any host on the internet. Recent
incidents - Shai-Hulud, the Nx attack, tj-actions/changed-files - had the
same shape: code with more authority than its job needed. This talk shows
one answer at the level of the language. In Sabline, every function
declares what it may touch; the person running a program grants one folder,
one host or a number of operations; and the runtime refuses anything else
at the moment it is attempted, in a way the program cannot catch, with the
operating system holding the same budget underneath. We replay the shapes of
real incidents and show what a budget stops, what it does not, and where
other tools - Deno, WebAssembly, CaMeL - are ahead, measured on 102
programs.

## Outline (for a longer form)

1. The shape: code with more authority than its task (5 min).
2. Effects in signatures, budgets at run time: live refusals (10 min).
3. Replaying incidents: stopped, partly, not covered - and why (10 min).
4. Where it loses, measured, and what it does not claim (5 min).
5. Questions.

## Speaker notes, not for the form

The claims above are the ones the site makes and CI checks: the 102-program
comparison is `benchmark/competitors/results.json`; the incident replays
are `incidents/`, and only the verified ones may be named as replayed in a
talk given before every entry is checked.
