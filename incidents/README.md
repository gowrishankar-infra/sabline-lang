# Incidents

Real, publicly reported incidents from 2023 onward in the lane Sabline is
written for: AI agent failures and software supply-chain attacks where code
ran with more authority than it should have. For each one, whether a program
of the same *shape*, written in Sabline and run under a budget, is refused.

**This is not a claim that adopting Sabline would have prevented any of these
events.** None of them involved a Sabline program. Every one of them happened
in a language, a package manager, a build system or an agent framework that
Sabline neither runs nor bounds. What a catalogue entry shows is narrower and
checkable: given the same shape - read a credential and send it out, take a
string from a server and hand it to the shell, call a tool with an argument
outside the grant - here is the program, here is the command, here is what
the runtime actually printed, and here is the one line of budget that did
the work. Where nothing in Sabline addresses the shape, the entry says so
and the reason goes into the threat model's known-open table,
[docs/known-open.md](../docs/known-open.md).

## How these were chosen

This is a selection, not a survey. An incident is here only if it is:

- **from 2023 onward.** The lane this project is written for is recent, and
  a catalogue that reached back further would be measuring a different one.
- **in the lane**: code that ran with more authority than it should have -
  an AI agent, a package, a build system or an action doing something
  outside what its task needed. That is the shape a budget is about.
- **backed by a primary source**: a vendor post-mortem, a CVE record, or the
  researcher's own write-up. An incident without one does not go in, however
  widely it was reported.

**These are not all the incidents in this lane, and the counts are not a
measurement of the field.** They are the ones that fit the three rules above
and that someone has written up here. A different selection would give
different counts, and a verdict count is a count of what is in this
directory, not a claim about how common each shape is.

What is deliberately left out, and why:

- **Anything before 2023.** The xz-utils backdoor (2024) is the oldest shape
  here; earlier supply-chain attacks are out of the window on purpose.
- **Prompt injection where no code ran.** An injection that ends in the model
  saying or rendering something, with no effect performed, is `OUT OF SCOPE`
  rather than a gap - there is nothing for a budget to bound. This is why
  `echoleak-m365-copilot` and `camoleak-copilot-chat` are listed as out of
  scope rather than counted.
- **Anything that cannot be sourced to a primary report.** One incident, an
  agent that deleted a production database (Replit, July 2025), was dropped
  for this reason: its record is participants' posts and the news that quoted
  them, with no vendor post-mortem, CVE or researcher write-up to check the
  account against. `incidents/FACTCHECK.md` keeps the evidence that decided
  it.

## Verdicts

| Verdict | What it means |
|---|---|
| `STOPPED` | The shape, written in Sabline and run under a budget granting what the task legitimately needs, is refused. The refusal is recorded in the entry, and `check_incidents.py` re-runs it on every push. |
| `PARTIAL` | Part of the shape is refused and part is not: another step of the same attack is outside what a budget can see, or the refusal holds only under a narrowing an operator might not make. Both halves are recorded - the refusal *and* the step that goes through. |
| `NOT COVERED` | Nothing in Sabline addresses this shape. There is no program, because there is no refusal to show. |
| `UNVERIFIED` | The shape may be covered, but no repro was built, so nothing is claimed. |
| `OUT OF SCOPE` | Prompt injection where no code ran: the model was steered and data moved, but nothing executed with authority. Listed so the boundary is visible, not counted as a gap. |

A verdict is never `STOPPED` on reasoning. It is `STOPPED` only when a real
program, run by `incident_evidence.py`, actually refuses.

## Every entry carries `verified: false`

The summaries here were written from the sources each entry links. They have
not yet been checked line by line against those sources by a person.
`build_incidents.py` refuses to publish the body of any entry whose
frontmatter still says `verified: false`: the page counts it, names it and
links its sources, and withholds the summary until someone sets the flag.
So the published page is honest about what has been checked, and this
directory is honest about what has not.

## Layout

    incidents/
      README.md          this
      TEMPLATE.md        the template for a new entry
      <slug>/
        incident.md      frontmatter, summary, sources, the shape, the gap
        attack.vel       the program, where there is one
        run.json         the steps the harness runs
        refusal.txt      what each step printed, recorded
        receipt.json     the run's receipt, recorded

    ../incident_evidence.py   records each entry's evidence, and re-runs it
    ../build_incidents.py     writes docs/incidents.md from these entries
    ../check_incidents.py     what CI runs on every push

The three scripts are at the top of the repository beside the other
`build_*.py` and `check_*.py`, where the suites live.

## The recorded evidence, and what is normalised in it

`refusal.txt` and `receipt.json` are what the commands actually printed and
wrote, with five substitutions, so that the same bytes appear on every
machine and survive the next release:

- the absolute path of the entry's own directory, and of this checkout,
  becomes `.`, and a backslash becomes a forward slash, so a path recorded
  on Windows reads as one recorded on Linux;
- the Sabline version, and the specification version a receipt names,
  become `<version>`;
- the receipt's `startedAt` and `wall_time_ms` become `<varies>`;
- the receipt's `confinement`, `confinement_reason`, `confinement_layers`
  and `os_policy_sha256` become `<varies by operating system>`, because what
  the kernel holds is not the same on Linux, macOS and Windows
  (THREAT_MODEL.md, "What the operating system enforces");
- the note Sabline prints when z3-solver is not installed (`note:
  z3-solver is not installed, so promises are checked while running ...`)
  is dropped, because whether an optional dependency is present says
  something about the machine, not about the program, and half of CI runs
  without it.

Nothing else is edited. `python incident_evidence.py --write` regenerates
them from real runs; `python check_incidents.py` re-runs every step and
fails if what it gets back is not what is recorded here.

A step may name `platforms` (for example `["linux"]`) when the point of the
step is a refusal one operating system makes and another does not - a Linux
kernel confinement refusal reads differently on macOS and Windows. Such a
step runs, and is checked, only on an operating system it names, and is held
to its `expect`, `expect_exit` and `expect_absent` alone: it is recorded in
no `refusal.txt` and carries no receipt, so the recorded bytes stay the same
on every machine. `tj-actions-changed-files` has one, showing the operating
system refuse the runtime a read of another process's memory.

## Adding one

1. Copy `TEMPLATE.md` to `incidents/<slug>/incident.md` and fill it in. A
   source that is not a vendor post-mortem, a CVE record or a researcher's
   own write-up is not a source; an incident without one does not go in.
2. If the verdict is `STOPPED` or `PARTIAL`, write `attack.vel` and
   `run.json`, then `python incident_evidence.py --write <slug>`.
3. `python build_incidents.py` to rebuild `docs/incidents.md`, then
   `python build_docs.py`.
4. `python check_incidents.py` must pass.
