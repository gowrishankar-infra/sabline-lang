# Sabline compared with CaMeL

<!-- description: CaMeL 1.0.0 against Sabline 8.6.0 on 102 measured programs, 2026-09-23: where CaMeL is ahead (3 rows) comes first. -->

CaMeL and Sabline, run on the same 102 programs of Sabline's comparison benchmark, each in its own real runtime. This page takes the one tool from [the competitor table](competitors.md), and starts with where CaMeL does better.

> [!NOTE]
> **Last verified:** 2026-09-23, on Linux x86_64: **CaMeL** 1.0.0, commit f083b6b396399d3b3c7f2ddaf613a5945eaf32d8, **Sabline** 8.6.0. Every verdict below comes from a program that ran, recorded in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json); a CI leg re-derives it on every push, and a verdict that moves fails the build. A score on this corpus is not what either tool is for - the next section is.

## Where CaMeL is stronger by design

Information flow per value: every value carries where it came from and who may read it, and a policy decides at each tool call whether *this data* may go *there*. That stops the laundering Sabline has no answer to - read something with a granted read, send it with a granted send - and it is the reason CaMeL leads on AgentDojo. Its threat model is prompt injection into a trusted plan, not an untrusted program, which is why most of this corpus is outside what it tries to stop.

## Where CaMeL is ahead, row by row

3 of the 102 rows: a better outcome - the danger stopped with the task's work intact where Sabline's refusal ended the task, a catch Sabline missed, or a correct program run clean where Sabline stopped it. The row links to its evidence.

| Row | Category | Program | CaMeL | Sabline | Why |
|---|---|---|---|---|---|
| [16a](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `a_posts_the_ledger` | during ▲ | **missed** | caught what Sabline missed |
| [16b](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `b_summary_with_ledger` | during ▲ | **missed** | caught what Sabline missed |
| [16c](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `c_uppercased_note` | during ▲ | **missed** | caught what Sabline missed |

## Where Sabline is ahead

4 rows where Sabline's outcome is the better one, and 2 where both reached the same outcome and Sabline reached it earlier - before running, where CaMeL did while running.

| Row | Category | Program | CaMeL | Sabline |
|---|---|---|---|---|
| [12a](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `a_gains_net` | **missed** | before, task broken |
| [14a](competitors-evidence-2.md) | 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | `a_weather_telemetry` | during, task broken | before |
| [14b](competitors-evidence-2.md) | 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | `b_notes_update` | during, task broken | before |
| [16d](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `d_posts_the_count (control)` | **false positive** | clean |

## The rest

2 rows are a tie - the same outcome at the same time, in categories 14, 16. 91 are not compared: rows CaMeL cannot express, and rows outside its threat model ([the rule](competitors.md#how-each-column-was-run)). Every row, with every tool's verdict and its notes, is on [the scenario page](competitors-scenarios.md).

See also [the AgentDojo run](agentdojo.md).
