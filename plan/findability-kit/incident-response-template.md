# Same week: "Would Sabline have stopped [incident]?"

For the week a new incident is in the news, when people are searching for
it by name. The answer is almost always "not that one - it ran in npm (or
GitHub Actions, or an agent framework), which Sabline does not run - but
here is the same shape in Sabline, and what a budget does with it". This
template is how to say that fast without saying more.

**It becomes a catalogue entry, not a blog post.** Copy
`incidents/TEMPLATE.md` to `incidents/<slug>/incident.md`, fill it in from
the answers below, record the evidence with `incident_evidence.py`, and add
the incident's common name to `incidents/names.json`. `build_incidents.py`
then gives it a page titled with that name - but only once `verified: true`,
after a person has checked every sentence of "What happened" against the
sources. Same week is the goal; the check is not skipped for it.

## Fill in

**The name people use** (search Hacker News and the vendor posts; use the
one in titles, not the CVE unless that is what people say):
`[name]` - also called `[other names]`. One page showing the name in use:
`[url]`.

**What happened** (two to four sentences, each traceable to a source, no
sentence about Sabline):

> [facts]

**Sources** (a primary report is required: a vendor post-mortem, a CVE, or
the researcher's own write-up):

- [primary report](url) - which kind it is
- [second source](url) - optional

**The shape a budget can see** (one line): reads [what] and sends it to
[where] / writes [what] outside [where] / runs [what] / reaches [host].

**Is there a Sabline program of that shape?**

- [ ] Yes, and a budget refuses it: write the program, run it under the
      budget the task legitimately needs, record the refusal. Verdict
      `STOPPED` - and say what the budget must be for it to hold.
- [ ] Partly: record the part refused and the part that goes through.
      Verdict `PARTIAL`.
- [ ] No: nothing here addresses it. Verdict `NOT COVERED`, the reason
      added to `docs/known-open.md`.
- [ ] Prompt injection where no code ran: `OUT OF SCOPE`.

**The one line that does the work:** `--allow [grant]`, and why that line.

**What this does not cover** (one plain sentence, no hedging).

## Before publishing - the checks

- [ ] The first sentence under the title says the real incident did not
      involve Sabline and adopting it is not claimed to have prevented it
      (the page `build_incidents.py` writes says this for you).
- [ ] Every sentence of "What happened" checked against its source;
      `verified: true` set by the person who checked.
- [ ] `python incident_evidence.py` recorded the refusal; `python
      check_incidents.py` passes.
- [ ] The name is in `incidents/names.json` with a page showing it in use.
- [ ] Nothing in the entry names the project that was attacked as careless;
      the post-mortem's own words, not ours.

## Where to mention it

Only where the incident is already being discussed and the page adds
something - the shape, the refusal, the stated limit. Say you wrote it. Do
not reply to every thread; one link where it answers a question someone
asked is enough.
