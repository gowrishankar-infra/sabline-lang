# Sabline compared with Deno's permissions

<!-- description: Deno 2.9.7 against Sabline 8.6.0 on 102 measured programs, 2026-09-23: where Deno is ahead (15 rows) comes first. -->

Deno and Sabline, run on the same 102 programs of Sabline's comparison benchmark, each in its own real runtime. This page takes the one tool from [the competitor table](competitors.md), and starts with where Deno does better.

> [!NOTE]
> **Last verified:** 2026-09-23, on Linux x86_64: **Deno** 2.9.7, **Sabline** 8.6.0. Every verdict below comes from a program that ran, recorded in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json); a CI leg re-derives it on every push, and a verdict that moves fails the build. A score on this corpus is not what either tool is for - the next section is.

## Where Deno is stronger by design

A permission system for a language people already write, enforced by the runtime at the moment of the call, for JavaScript and TypeScript and everything npm ships. It can grant one program to run (`--allow-run=git`), which Sabline cannot express: Sabline's `ffi:` grants a whole host module, and it has no model of a subprocess. It needs no new language and no rewrite.

## Where Deno is ahead, row by row

15 of the 102 rows: a better outcome - the danger stopped with the task's work intact where Sabline's refusal ended the task, a catch Sabline missed, or a correct program run clean where Sabline stopped it. The row links to its evidence.

| Row | Category | Program | Deno | Sabline | Why |
|---|---|---|---|---|---|
| [12a](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `a_gains_net` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [12b](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `b_new_host` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [12c](competitors-evidence-2.md) | 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `c_gains_write` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [14c](competitors-evidence-2.md) | 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | `c_setup_env` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [17a](competitors-evidence-3.md) | 17. One legitimate subprocess: the task needs one program, and the program also runs another | `a_labels_with_hostname` | during ▲ | **missed** | caught what Sabline missed |
| [17b](competitors-evidence-3.md) | 17. One legitimate subprocess: the task needs one program, and the program also runs another | `b_preflight_first` | during ▲ | **missed** | caught what Sabline missed |
| [18a](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `a_count_until_end (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18b](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `b_euclid (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18c](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `c_factorial_exact (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [18d](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `d_modular_product (control)` | clean ▲ | **false positive** | ran the correct program clean, where Sabline stopped or flagged it |
| [19a](competitors-evidence-3.md) | 19. Danger below the language: a granted library, or its native code, doing I/O of its own | `a_cache_file` | during ▲ | **missed** | caught what Sabline missed |
| [19b](competitors-evidence-3.md) | 19. Danger below the language: a granted library, or its native code, doing I/O of its own | `b_library_telemetry` | during ▲ | **missed** | caught what Sabline missed |
| [20b](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `b_update_check_first` | during ▲ | before, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [20c](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `c_feed_after_ping` | during ▲ | during, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |
| [20d](competitors-evidence-3.md) | 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other | `d_report_after_stray_write` | during ▲ | during, task broken | stopped the danger with the task's work intact, where Sabline's refusal ended the run and the task with it |

## Where Sabline is ahead

23 rows where Sabline's outcome is the better one, and 29 where both reached the same outcome and Sabline reached it earlier - before running, where Deno did while running.

| Row | Category | Program | Deno | Sabline |
|---|---|---|---|---|
| [03a](competitors-evidence-1.md) | 3. Division by a value that comes from input and can be zero | `a_share_per_person` | **missed** | before |
| [03b](competitors-evidence-1.md) | 3. Division by a value that comes from input and can be zero | `b_bucket_remainder` | **missed** | before |
| [03c](competitors-evidence-1.md) | 3. Division by a value that comes from input and can be zero | `c_per_item_in_main` | **missed** | during |
| [03d](competitors-evidence-1.md) | 3. Division by a value that comes from input and can be zero | `d_guarded_one_path` | **missed** | during |
| [03e](competitors-evidence-1.md) | 3. Division by a value that comes from input and can be zero | `e_range_width` | **missed** | before |
| [03f](competitors-evidence-1.md) | 3. Division by a value that comes from input and can be zero | `f_remainder_in_loop` | **missed** | during |
| [04a](competitors-evidence-1.md) | 4. An off-by-one read past the end of a list | `a_sum_inclusive` | **missed** | before |
| [04b](competitors-evidence-1.md) | 4. An off-by-one read past the end of a list | `b_last_item` | **missed** | before |
| [04d](competitors-evidence-1.md) | 4. An off-by-one read past the end of a list | `d_empty_input` | **missed** | before |
| [04e](competitors-evidence-1.md) | 4. An off-by-one read past the end of a list | `e_pairs` | **missed** | during |
| [04f](competitors-evidence-1.md) | 4. An off-by-one read past the end of a list | `f_index_from_input` | **missed** | before |
| [05a](competitors-evidence-1.md) | 5. Integer overflow | `a_factorial_25` | **missed** | during |
| [05b](competitors-evidence-1.md) | 5. Integer overflow | `b_square_input` | **missed** | during |
| [05c](competitors-evidence-1.md) | 5. Integer overflow | `c_sum_of_cubes` | **missed** | during |
| [05d](competitors-evidence-1.md) | 5. Integer overflow | `d_record_field` | **missed** | during |
| [05e](competitors-evidence-1.md) | 5. Integer overflow | `e_map_accumulate` | **missed** | during |
| [05f](competitors-evidence-1.md) | 5. Integer overflow | `f_negate_minimum` | **missed** | during |
| [06a](competitors-evidence-1.md) | 6. An ignored failure (a parse that can fail, not handled) | `a_to_int_unhandled` | **missed** | before |
| [06b](competitors-evidence-1.md) | 6. An ignored failure (a parse that can fail, not handled) | `b_json_field` | **missed** | before |
| [06c](competitors-evidence-1.md) | 6. An ignored failure (a parse that can fail, not handled) | `c_map_lookup` | **missed** | before |
| [06d](competitors-evidence-1.md) | 6. An ignored failure (a parse that can fail, not handled) | `d_inside_lambda` | **missed** | before |
| [06e](competitors-evidence-1.md) | 6. An ignored failure (a parse that can fail, not handled) | `e_pop_empty` | **missed** | before |
| [18f](competitors-evidence-3.md) | 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins | `f_id_past_64_bits` | **missed** | during |

**Category 5 is a judgement call, not a clean win.** Reviewed, and kept, as a judgement call rather than a win. Sabline's whole numbers are 64-bit and arithmetic that leaves the range stops the program (E407); every competitor computes the arithmetically right, larger number, because Python's, JavaScript's (as a double) and Starlark's integers do not wrap. Nothing in the corpus says the result must fit 64 bits, so the category counts a correct answer as a miss. A reader who disagrees can discount its six rows. The other side is category 18: 18c and 18d need numbers past 64 bits, are correct, and Sabline stops both.

## The rest

35 rows are a tie - the same outcome at the same time, in categories 4, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 19, 20. 0 are not compared: rows Deno cannot express ([the rule](competitors.md#how-each-column-was-run)). Every row, with every tool's verdict and its notes, is on [the scenario page](competitors-scenarios.md).
