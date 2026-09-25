# Sabline compared with a Python sandbox (smolagents)

<!-- description: Python sandbox (smolagents) 1.26.0 against Sabline 8.6.0 on 102 measured programs, 2026-09-23: where the Python sandbox is ahead (7 rows) comes first. -->

Python sandbox (smolagents) and Sabline, run on the same 102 programs of Sabline's comparison benchmark, each in its own real runtime. This page takes the one tool from [the competitor table](competitors.md), and starts with where the Python sandbox does better.

> [!NOTE]
> **Last verified:** 2026-09-23, on Linux x86_64: **Python sandbox (smolagents)** 1.26.0, **Sabline** 8.6.0. Every verdict below comes from a program that ran, recorded in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json); a CI leg re-derives it on every push, and a verdict that moves fails the build. A score on this corpus is not what either tool is for - the next section is.

## Where the Python sandbox is stronger by design

Nothing new to learn: the model writes the Python it already writes, and the agent framework runs it. Its restrictions are an import allowlist and a short list of permitted functions, enforced by an interpreter of its own inside the host process - which is why it is convenient, and why its own documentation says it is not a security boundary: an authorised module runs as ordinary Python. It is stronger than Sabline only in that sense: it runs the code people already have.

## Where the Python sandbox is ahead, row by row

7 of the 102 rows: a better outcome - the danger stopped with the task's work intact where Sabline's refusal ended the task, a catch Sabline missed, or a correct program run clean where Sabline stopped it. The row links to its evidence.

| Row | Category | Program | Python sandbox (smolagents) | Sabline | Why |
|---|---|---|---|---|---|
| [16a](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `a_posts_the_ledger` | during † ▲ | **missed** | stopped what Sabline missed, by a failure that is not a refusal and would have stopped the task too (†) |
| [16b](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `b_summary_with_ledger` | during † ▲ | **missed** | stopped what Sabline missed, by a failure that is not a refusal and would have stopped the task too (†) |
| [16c](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `c_uppercased_note` | during † ▲ | **missed** | stopped what Sabline missed, by a failure that is not a refusal and would have stopped the task too (†) |
| [18a](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `a_count_until_end (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18b](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `b_euclid (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18c](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `c_factorial_exact (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18d](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `d_modular_product (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |

## Where Sabline is ahead

20 rows where Sabline's outcome is the better one, and 47 where both reached the same outcome and Sabline reached it earlier - before running, where the Python sandbox did while running.

| Row | Category | Program | Python sandbox (smolagents) | Sabline |
|---|---|---|---|---|
| [01e](competitors-evidence-1.md) | 1. A file write hidden inside a helper function | `e_path_in_record` | during † | before |
| [05a](competitors-evidence-1.md) | 5. Integer overflow | `a_factorial_25` | **missed** | during |
| [05b](competitors-evidence-1.md) | 5. Integer overflow | `b_square_input` | **missed** | during |
| [05c](competitors-evidence-1.md) | 5. Integer overflow | `c_sum_of_cubes` | **missed** | during |
| [05d](competitors-evidence-1.md) | 5. Integer overflow | `d_record_field` | during † | during |
| [05e](competitors-evidence-1.md) | 5. Integer overflow | `e_map_accumulate` | **missed** | during |
| [05f](competitors-evidence-1.md) | 5. Integer overflow | `f_negate_minimum` | **missed** | during |
| [08b](competitors-evidence-2.md) | 8. Runaway memory growth | `b_log_kept_in_memory` | during † | before |
| [08f](competitors-evidence-2.md) | 8. Runaway memory growth | `f_two_layer_log` | during † | during |
| [11a](competitors-evidence-2.md) | 11. A grant narrower than the effect: one directory, one host, no secrets (3.0) | `a_read_outside` | **missed** | during |
| [11b](competitors-evidence-2.md) | 11. A grant narrower than the effect: one directory, one host, no secrets (3.0) | `b_other_host` | during † | during |
| [12b](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `b_new_host` | **missed** | before, task broken |
| [12c](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `c_gains_write` | **missed** | before, task broken |
| [14a](competitors-evidence-2.md) | 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | `a_weather_telemetry` | during, task broken | before |
| [14b](competitors-evidence-2.md) | 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | `b_notes_update` | during, task broken | before |
| [16d](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `d_posts_the_count (control)` | **false positive** | clean |
| [16e](competitors-evidence-2.md) | 16. Leaking data through a granted channel: the task needs the read and the send, and the program sends what it read | `e_posts_a_status (control)` | **false positive** | clean |
| [18f](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `f_id_past_64_bits` | **missed** | during |
| [20a](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `a_task_then_telemetry` | during, task broken | before |
| [20d](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `d_report_after_stray_write` | **missed** | during, task broken |

**Category 5 is a judgement call, not a clean win.** Reviewed, and kept, as a judgement call rather than a win. Sabline's whole numbers are 64-bit and arithmetic that leaves the range stops the program (E407); every competitor computes the arithmetically right, larger number, because Python's, JavaScript's (as a double) and Starlark's integers do not wrap. Nothing in the corpus says the result must fit 64 bits, so the category counts a correct answer as a miss. A reader who disagrees can discount its six rows. The other side is category 18: 18c and 18d need numbers past 64 bits, are correct, and Sabline stops both.

## The rest

28 rows are a tie - the same outcome at the same time, in categories 3, 4, 7, 9, 10, 12, 14, 15, 17, 19, 20. 0 are not compared: rows the Python sandbox cannot express ([the rule](competitors.md#how-each-column-was-run)). Every row, with every tool's verdict and its notes, is on [the scenario page](competitors-scenarios.md).
