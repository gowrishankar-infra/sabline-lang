# Sabline compared with WASI (wasmtime)

<!-- description: WASI (wasmtime) 49.0.0 against Sabline 8.6.0 on 102 measured programs, 2026-09-23: where WASI is ahead (10 rows) comes first. -->

WASI (wasmtime) and Sabline, run on the same 102 programs of Sabline's comparison benchmark, each in its own real runtime. This page takes the one tool from [the competitor table](competitors.md), and starts with where WASI does better.

> [!NOTE]
> **Last verified:** 2026-09-23, on Linux x86_64: **WASI (wasmtime)** 49.0.0, CPython 3.14.7 WASI build, **Sabline** 8.6.0. Every verdict below comes from a program that ran, recorded in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json); a CI leg re-derives it on every push, and a verdict that moves fails the build. A score on this corpus is not what either tool is for - the next section is.

## Where WASI is stronger by design

A boundary made by the virtual machine, not by the language: whatever code runs inside - interpreted Python, compiled C, a native extension - reaches only the handles the host passed in, one by one. Sabline's first guard is its own interpreter, with OS confinement (8.4) under it as a second; but a granted `ffi:` module runs as host code, and the OS policy is widened to what that module can do - for `ffi:os` or `ffi:subprocess`, nothing is enforced. Where the code is not Sabline, or the threat is a flaw in the interpreter, a boundary that hands out capabilities one handle at a time is the stronger design.

## Where WASI is ahead, row by row

10 of the 102 rows: a better outcome - the danger stopped with the task's work intact where Sabline's refusal ended the task, a catch Sabline missed, or a correct program run clean where Sabline stopped it. The row links to its evidence.

| Row | Category | Program | WASI (wasmtime) | Sabline | Why |
|---|---|---|---|---|---|
| [12c](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `c_gains_write` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [14c](competitors-evidence-2.md) | 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | `c_setup_env` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [18a](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `a_count_until_end (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18b](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `b_euclid (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18c](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `c_factorial_exact (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18d](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `d_modular_product (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [19a](competitors-evidence-3.md) | 19. Danger below the language: a granted library, or its native code, doing I/O of its own | `a_cache_file` | during ▲ | **missed** | caught what Sabline missed |
| [19b](competitors-evidence-3.md) | 19. Danger below the language: a granted library, or its native code, doing I/O of its own | `b_library_telemetry` | during ▲ | **missed** | caught what Sabline missed |
| [20b](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `b_update_check_first` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [20d](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `d_report_after_stray_write` | during ▲ | during, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |

## Where Sabline is ahead

7 rows where Sabline's outcome is the better one, and 49 where both reached the same outcome and Sabline reached it earlier - before running, where WASI did while running.

| Row | Category | Program | WASI (wasmtime) | Sabline |
|---|---|---|---|---|
| [05a](competitors-evidence-1.md) | 5. Integer overflow | `a_factorial_25` | **missed** | during |
| [05b](competitors-evidence-1.md) | 5. Integer overflow | `b_square_input` | **missed** | during |
| [05c](competitors-evidence-1.md) | 5. Integer overflow | `c_sum_of_cubes` | **missed** | during |
| [05d](competitors-evidence-1.md) | 5. Integer overflow | `d_record_field` | **missed** | during |
| [05e](competitors-evidence-1.md) | 5. Integer overflow | `e_map_accumulate` | **missed** | during |
| [05f](competitors-evidence-1.md) | 5. Integer overflow | `f_negate_minimum` | **missed** | during |
| [18f](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `f_id_past_64_bits` | **missed** | during |

**Category 5 is a judgement call, not a clean win.** Reviewed, and kept, as a judgement call rather than a win. Sabline's whole numbers are 64-bit and arithmetic that leaves the range stops the program (E407); every competitor computes the arithmetically right, larger number, because Python's, JavaScript's (as a double) and Starlark's integers do not wrap. Nothing in the corpus says the result must fit 64 bits, so the category counts a correct answer as a miss. A reader who disagrees can discount its six rows. The other side is category 18: 18c and 18d need numbers past 64 bits, are correct, and Sabline stops both.

## The rest

21 rows are a tie - the same outcome at the same time, in categories 3, 4, 7, 8, 9, 10, 11, 12, 14, 15, 19, 20. 15 are not compared: rows WASI cannot express ([the rule](competitors.md#how-each-column-was-run)). Every row, with every tool's verdict and its notes, is on [the scenario page](competitors-scenarios.md).
