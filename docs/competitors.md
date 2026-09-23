# Competitors

Sabline's [comparison benchmark](https://sabline.dev/index.html) - 76 programs, 66 with one defect and 10 correct, in 15 categories - run through five tools that claim part of what Sabline claims, each in its own real runtime, beside Sabline and unsandboxed Python. Every verdict comes from a program that ran; none is scored from documentation. This page is generated from `benchmark/competitors/results.json`, which `benchmark/compete.py` records and a CI leg re-derives on every push: a verdict or an evidence line that moves fails the build.

> [!NOTE]
> **Measured** 2026-09-23 on Linux x86_64. **Sabline** 8.6.0, prover present · **Deno** 2.9.7 · **Python (no sandbox)** 3.12.3 · **WASI (wasmtime)** 49.0.0, CPython 3.14.7 WASI build · **Starlark** v0.0.0-20260908191801-89a6a09411d5 · **Python sandbox (smolagents)** 1.26.0 · **CaMeL** 1.0.0, commit f083b6b396399d3b3c7f2ddaf613a5945eaf32d8. A 5 s deadline for every tool but CaMeL, which gets 30 s of interpretation, and a 256 MB cap where the runtime can take one ([how each column is run](#how-each-column-was-run)).

## Where a competitor is ahead

**On this benchmark's 76 rows, no competitor is ahead of Sabline on any row** - none caught a program Sabline missed, and none left alone a correct program Sabline stopped. plan/8.7.md says what that means, and it is repeated here because it is the most important sentence on the page: a table where Sabline wins everything is evidence that the benchmark is wrong, not that Sabline is good. The benchmark was written by this project, around what this project does. [What it is missing](#what-the-benchmark-is-missing) lists the scenarios where each competitor should win and where Sabline should lose; none of them is in the corpus yet.

Against Sabline, row by row. *Tie* is the same verdict; *earlier* and *later* mean both caught the program, one before running and one while running - a difference of timing, not of outcome.

| Competitor | Ahead | Earlier | Tie | Later | Behind |
|---|---:|---:|---:|---:|---:|
| Deno | 0 | 0 | 22 | 32 | 22 |
| WASI (wasmtime) | 0 | 0 | 18 | 52 | 6 |
| Starlark | 0 | 0 | 50 | 20 | 6 |
| Python sandbox (smolagents) | 0 | 0 | 18 | 50 | 8 |
| CaMeL | 0 | 0 | 16 | 35 | 25 |

Every tool missed 04c, 09c: the benchmark put them there because nothing can catch them (a loop that stops one item early with no contract; a program that only prints a shell command).

### Where each is stronger by design

A score on this corpus is not what any of these tools is for. What each is actually built to do, and where that makes it stronger than Sabline whatever this table says:

- **Deno.** A permission system for a language people already write, enforced by the runtime at the moment of the call, for JavaScript and TypeScript and everything npm ships. It can grant one program to run (`--allow-run=git`), which Sabline cannot express: Sabline's `ffi:` grants a whole host module, and it has no model of a subprocess. It needs no new language and no rewrite.
- **WASI (wasmtime).** A boundary made by the virtual machine, not by the language: whatever code runs inside - interpreted Python, compiled C, a native extension - reaches only the handles the host passed in, one by one. Sabline's first guard is its own interpreter, with OS confinement (8.4) under it as a second; but a granted `ffi:` module runs as host code, and the OS policy is widened to what that module can do - for `ffi:os` or `ffi:subprocess`, nothing is enforced. Where the code is not Sabline, or the threat is a flaw in the interpreter, a boundary that hands out capabilities one handle at a time is the stronger design.
- **Starlark.** Determinism and termination by construction: no `while`, no recursion, no I/O but what the host predeclares, and the same result on every run. That is exactly what a build or configuration language needs, and it makes a whole class of defect - an unbounded loop, a hidden effect - impossible to write, where Sabline's termination rule only reports what it cannot show. The cost is that programs that need an unbounded loop cannot be written.
- **Python sandbox (smolagents).** Nothing new to learn: the model writes the Python it already writes, and the agent framework runs it. Its restrictions are an import allowlist and a short list of permitted functions, enforced by an interpreter of its own inside the host process - which is why it is convenient, and why its own documentation says it is not a security boundary: an authorised module runs as ordinary Python. It is stronger than Sabline only in that sense: it runs the code people already have.
- **CaMeL.** Information flow per value: every value carries where it came from and who may read it, and a policy decides at each tool call whether *this data* may go *there*. That stops the laundering Sabline has no answer to - read something with a granted read, send it with a granted send - and it is the reason CaMeL leads on AgentDojo. Its threat model is prompt injection into a trusted plan, not an untrusted program, which is why most of this corpus is outside what it tries to stop.

## The table

Per category: caught before running / caught while running / missed, and for the control rows, clean / false positive. The per-program rows, and every note on a row that is not like-for-like, follow.

| Category | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL |
|---|---|---|---|---|---|---|---|
| 1. A file write hidden inside a helper function | 6/0/0 | 0/6/0 | 0/0/6 | 0/6/0 | 6/0/0 | 0/6/0 | 0/0/6 |
| 2. A network call hidden inside a helper | 6/0/0 | 0/6/0 | 0/0/6 | 0/6/0 | 6/0/0 | 0/6/0 | 0/0/6 |
| 3. Division by a value that comes from input and can be zero | 3/3/0 | 0/0/6 | 0/6/0 | 0/6/0 | 0/6/0 | 0/6/0 | 0/6/0 |
| 4. An off-by-one read past the end of a list | 4/1/1 | 0/0/6 | 0/5/1 | 0/5/1 | 0/5/1 | 0/5/1 | 0/5/1 |
| 5. Integer overflow | 0/6/0 | 0/0/6 | 0/0/6 | 0/0/6 | 0/0/6 | 0/1/5 | 0/0/6 |
| 6. An ignored failure (a parse that can fail, not handled) | 6/0/0 | 0/1/5 | 0/6/0 | 0/6/0 | 0/6/0 | 0/6/0 | 0/6/0 |
| 7. An infinite loop | 5/0/0; 1 clean | 0/5/0; 1 clean | 0/5/0; 1 clean | 0/5/0; 1 clean | 5/0/0; 1 clean | 0/5/0; 1 clean | 0/5/0; 1 clean |
| 8. Runaway memory growth | 6/0/0 | 5/1/0 | 0/6/0 | 0/6/0 | 5/1/0 | 0/6/0 | 0/6/0 |
| 9. Reaching a dangerous module (subprocess / child_process / os.system) | 5/0/1 | 0/5/1 | 0/0/6 | 0/5/1 | 5/0/1 | 0/5/1 | 0/4/2 |
| 10. A plain correct program that must NOT be flagged | 6 clean | 6 clean | 6 clean | 6 clean | 6 clean | 6 clean | 6 clean |
| 11. A grant narrower than the effect: one directory, one host, no secrets (3.0) | 1/2/0 | 0/3/0 | 0/0/3 | 0/3/0 | 1/2/0 | 0/2/1 | 0/0/3 |
| 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | 3/0/0; 1 clean | 0/3/0; 1 clean | 0/0/3; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 0/1/2; 1 clean | 0/0/3; 1 clean |
| 13. A TrapDoor: a program whose stated purpose and behaviour differ | 1/0/0 | 0/1/0 | 0/0/1 | 0/1/0 | 1/0/0 | 0/1/0 | 0/1/0 |
| 14. Skill supply chain: an agent skill whose helper reads a credential and posts it | 3/0/0; 1 clean | 0/3/0; 1 clean | 0/0/3; 1 clean | 0/3/0; 1 clean | 3/0/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean |
| 15. Hallucinated dependency: a program that imports a package that does not exist | 3/0/0; 1 clean | 3/0/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean | 0/3/0; 1 clean |
| **Caught, of 66** | **64** (52 before) | **42** (8 before) | **31** (0 before) | **58** (0 before) | **58** (32 before) | **56** (0 before) | **39** (0 before) |
| **False positives, of 10** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| **Catches the row itself says were not a refusal** | 0 | 1 | 0 | 3 | 0 | 6 | 0 |

The last row counts catches the benchmark's rule credits but whose row note says the program was stopped by something other than a refusal of its danger - a runtime with no network failing the task's own request, an interpreter defect, a deadline reached by a slow interpreter, a crash of a broken program. Read each column's catches net of it.

## Every scenario

▲ marks a competitor that did better than Sabline on the row (or caught it earlier); † marks a catch whose row note says it was not a refusal of the danger. The last column is where a row is not like-for-like - a different threat model, a construct a runtime lacks, a catch that came from a failure rather than a refusal - stated in the row, not in a footnote. Every cell's evidence line is on the evidence pages ([part 1](competitors-evidence-1.md), [part 2](competitors-evidence-2.md)); the commands and their output are in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json).

### 1. A file write hidden inside a helper function

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 01a | `a_save_report` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the helper's write is inlined into the plan, so nothing is hidden inside a helper. |
| 01b | `b_two_levels` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the write two calls down is inlined into the plan, so nothing is hidden inside a helper. |
| 01c | `c_log_in_loop` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions and no append mode: the helper's write is inlined into the loop, so nothing is hidden inside a helper, and each write replaces the file where Python's appends to it. |
| 01d | `d_three_layers` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the write three calls down is inlined into the plan, so nothing is hidden inside a helper. |
| 01e | `e_path_in_record` | before | during | **missed** | during | before | during † | **missed** | *Starlark:* Starlark has no classes: the record is a dict.<br>*Python sandbox (smolagents):* Not a refusal: smolagents 1.26.0 does not apply @dataclass, so building the program's record fails before it reaches its dangerous line.<br>*CaMeL:* CaMeL has no functions: run_job's write is inlined into the plan, so nothing is hidden inside a helper, though the path still travels inside a record. |
| 01f | `f_write_in_condition` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the helper's write is inlined into the plan just before the if, so it is no longer hidden inside the if's condition. |

### 2. A network call hidden inside a helper

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 02a | `a_fetch_helper` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the helper's fetch is inlined into the plan, so nothing is hidden inside a helper. |
| 02b | `b_post_summary` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the helper's post is inlined into the plan, so nothing is hidden inside a helper. |
| 02c | `c_quiet_fetch` | before | during | **missed** | during | before | during | **missed** | *Starlark:* Starlark has no try: the helper cannot swallow a failed request, so a failure stops the program instead of printing "done".<br>*CaMeL:* CaMeL has no functions and no try: the helper's fetch is inlined into the plan, so nothing is hidden inside a helper, and an error the Python version swallows stops the plan. |
| 02d | `d_two_layers` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the post two calls down is inlined into the plan, so nothing is hidden inside a helper. |
| 02e | `e_is_valid_url` | before | during | **missed** | during | before | during | **missed** | *Starlark:* the host's http_get returns only the body, so is_valid cannot read the status code and answers "valid" for any response.<br>*CaMeL:* CaMeL has no functions and get_webpage returns the page, not the status: the helper's request is inlined into the plan, and a request that comes back counts as valid, as it does in Python, where urlopen raises on any status outside 2xx. |
| 02f | `f_probe_with_headers` | before | during | **missed** | during | before | during | **missed** | *Starlark:* the host's http_get takes no headers, so the request goes out without the X-Probe header.<br>*CaMeL:* CaMeL has no functions and get_webpage takes no headers: the helper's request is inlined into the plan, so nothing is hidden inside a helper, and it is sent without the X-Probe header. |

### 3. Division by a value that comes from input and can be zero

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 03a | `a_share_per_person` | before | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |
| 03b | `b_bucket_remainder` | before | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |
| 03c | `c_per_item_in_main` | during | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |
| 03d | `d_guarded_one_path` | during | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |
| 03e | `e_range_width` | before | **missed** | during | during | during | during | during | - |
| 03f | `f_remainder_in_loop` | during | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |

### 4. An off-by-one read past the end of a list

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 04a | `a_sum_inclusive` | before | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no while: the counted loop is a for over range(0, len(xs) + 1), which reads one past the end exactly as the while's "<=" did. |
| 04b | `b_last_item` | before | **missed** | during | during | during | during | during | - |
| 04c | `c_skips_last` | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | - |
| 04d | `d_empty_input` | before | **missed** | during | during | during | during | during | - |
| 04e | `e_pairs` | during | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no while: the counted loop is a for over range(0, len(xs)), which takes the same steps and reads xs[i + 1] one past the end exactly as the while did. |
| 04f | `f_index_from_input` | before | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |

### 5. Integer overflow

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 05a | `a_factorial_25` | during | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | - |
| 05b | `b_square_input` | during | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |
| 05c | `c_sum_of_cubes` | during | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | *CaMeL:* Not like-for-like: CaMeL is given 30 s, not 5. It needs about 7.4 s for this program here; under 5 s the deadline would stop it, and the benchmark's rule would credit that as a catch. |
| 05d | `d_record_field` | during | **missed** | **missed** | **missed** | **missed** | during † | **missed** | *Starlark:* Starlark has no classes: the record is a dict.<br>*Python sandbox (smolagents):* Not a refusal: smolagents 1.26.0 does not apply @dataclass, so building the program's record fails before it reaches its dangerous line.<br>*CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |
| 05e | `e_map_accumulate` | during | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | - |
| 05f | `f_negate_minimum` | during | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | *CaMeL:* CaMeL has no try: instead of catching int()'s ValueError the plan tests the input with isdigit() first, which takes the same branch on the benchmark's input. |

### 6. An ignored failure (a parse that can fail, not handled)

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 06a | `a_to_int_unhandled` | before | **missed** | during | during | during | during | during | - |
| 06b | `b_json_field` | before | **missed** | during | during | during | during | during | - |
| 06c | `c_map_lookup` | before | **missed** | during | during | during | during | during | - |
| 06d | `d_inside_lambda` | before | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no lambda: the inline function passed to map becomes a list comprehension, so the parse is no longer inside an inline function. |
| 06e | `e_pop_empty` | before | **missed** | during | during | during | during | during | *CaMeL:* CaMeL has no list.pop: the plan reads the last word with words[-1] and rebuilds the list without it, and on empty input words[-1] raises IndexError where pop() does. |
| 06f | `f_json_parse` | before | during | during | during | during | during | during | - |

### 7. An infinite loop

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 07a | `a_never_advances` | before | during | during | during | before | during | during | - |
| 07b | `b_steps_past` | before | during | during | during | before | during | during | - |
| 07c | `c_slow_but_finite (control)` | clean | clean | clean | clean | clean | clean | clean | *CaMeL:* Not like-for-like: CaMeL is given 30 s of interpretation, not the 5 s every other tool gets. Its interpreter needs about 4.5 s for this correct program's 90,000 steps on the recording machine (plain Python: under 0.1 s), so under 5 s it would be a false positive on any slower machine, and the cell would measure the machine. |
| 07d | `d_ends_on_input` | before | during | during | during | before | during | during | - |
| 07e | `e_reset_in_if` | before | during | during | during | before | during | during | - |
| 07f | `f_wrong_sign` | before | during | during | during | before | during | during | - |

### 8. Runaway memory growth

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 08a | `a_rows_forever` | before | before | during | during | before | during | during | *CaMeL:* CaMeL has no list.append: each row is added by building a new list, rows = rows + [row]. |
| 08b | `b_log_kept_in_memory` | before | before | during | during | before | during † | during | *Python sandbox (smolagents):* Not a refusal: `log` is one of smolagents' own tools (math.log), so the program's `log = ...` is refused before its loop runs.<br>*CaMeL:* CaMeL has no list.append: each event is added by building a new list, log = log + [event]. |
| 08c | `c_split_rows` | before | before | during | during | before | during | during | *CaMeL:* CaMeL has no list.append: each copy is added by building a new list, rows = rows + [copy]. |
| 08d | `d_text_concat` | before | before | during | during | before | during | during | - |
| 08e | `e_map_growth` | before | before | during | during | before | during | during | - |
| 08f | `f_two_layer_log` | before | during | during | during | during | during † | during | *Deno:* Deno's lint does flag this program's unbounded loop (no-unreachable after it) and is not credited, because the growth is two helpers away from the loop; Sabline's audit flags the same loop and is credited. The benchmark's rule, applied unevenly.<br>*Starlark:* Refused before running, but on a line the benchmark does not credit: the loop or call it rejects is not on the DANGER line. That is the rule Deno is held to; Sabline's audit flags an unbounded loop wherever it is, and is credited for it.<br>*Python sandbox (smolagents):* Not a refusal: `log` is one of smolagents' own tools (math.log), so the program's `log = ...` is refused before its loop runs.<br>*CaMeL:* CaMeL has no functions and no list.append: the two helpers are inlined into the loop, so the growth is no longer two helpers down, and each entry is added by building a new list, log = log + [entry]. |

### 9. Reaching a dangerous module (subprocess / child_process / os.system)

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 09a | `a_subprocess_helper` | before | during | **missed** | during | before | during | during | *CaMeL:* CaMeL has no functions: the helper's command is inlined into the plan, so nothing is hidden inside a helper. |
| 09b | `b_os_system` | before | during | **missed** | during | before | during | during | *CaMeL:* CaMeL has no functions and run_command returns the command's output, not its exit status: the helper's command is inlined into the plan, which prints the output itself (os.system lets the child write it) and reports exit 0. |
| 09c | `c_command_on_stdout` | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | **missed** | *CaMeL:* CaMeL has no functions: the helper that builds the command text is inlined into the plan. |
| 09d | `d_via_py_json` | before | during | **missed** | during | before | during | during | *CaMeL:* CaMeL has no functions: the helper's command is inlined into the plan, so nothing is hidden inside a helper. |
| 09e | `e_via_handle` | before | during | **missed** | during | before | during | during | *CaMeL:* CaMeL has no functions and no pipe handles: the helper's popen, read and close are one run_command call inlined into the plan, so nothing is hidden inside a helper. |
| 09f | `f_os_listdir` | before | during | **missed** | during | before | during | **missed** | *CaMeL:* CaMeL has no functions: the helper's listing is inlined into the plan, so nothing is hidden inside a helper. |

### 10. A plain correct program that must NOT be flagged

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 10a | `a_expense_total (control)` | clean | clean | clean | clean | clean | clean | clean | - |
| 10b | `b_word_count (control)` | clean | clean | clean | clean | clean | clean | clean | - |
| 10c | `c_sqrt_via_math (control)` | clean | clean | clean | clean | clean | clean | clean | *CaMeL:* CaMeL has no round(): the plan rounds with int(x + 0.5), which gives the same whole number for this positive value. |
| 10d | `d_warning_text (control)` | clean | clean | clean | clean | clean | clean | clean | - |
| 10e | `e_reads_own_args (control)` | clean | clean | clean | clean | clean | clean | clean | *Starlark:* the host gives a Starlark program no way to read its command-line arguments, so the list is always empty (the harness passes none, so the output is the same).<br>*CaMeL:* CaMeL gives a plan no command-line arguments, so the plan's argument list is empty, as it is when the benchmark runs the Python version with none. |
| 10f | `f_math_in_loop (control)` | clean | clean | clean | clean | clean | clean | clean | *CaMeL:* CaMeL has no while and no round(): the counted loop is a for over range(1, n + 1), and the rounding is int(x + 0.5), which gives the same whole number for this positive total. |

### 11. A grant narrower than the effect: one directory, one host, no secrets (3.0)

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 11a | `a_read_outside` | during | during | **missed** | during | during | **missed** | **missed** | - |
| 11b | `b_other_host` | during | during | **missed** | during † | during | during † | **missed** | *WASI (wasmtime):* Not like-for-like: the task's own request to the granted host could not be made either - this build has no network - so the catch cost the task.<br>*Python sandbox (smolagents):* Not a refusal: smolagents 1.26.0 binds `import urllib.request` wrongly, so `urllib.request.urlopen` fails for every URL, granted or not. The task's own request fails too. |
| 11c | `c_secret_from_env` | before | during | **missed** | during | before | during | **missed** | - |

### 12. Indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1)

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 12a | `a_gains_net` | before | during | **missed** | during † | during | during † | **missed** | *WASI (wasmtime):* Not like-for-like: the task's own request to the granted host could not be made either - this build has no network - so the catch cost the task.<br>*Starlark:* Starlark has no try: an error from the feed request or from the library stops the program instead of printing "no price feed: ...".<br>*Starlark:* Starlark has no try: the library cannot swallow the refused request, so the refusal stops the program.<br>*Python sandbox (smolagents):* Not a refusal: smolagents 1.26.0 binds `import urllib.request` wrongly, so `urllib.request.urlopen` fails for every URL, granted or not. The task's own request fails too.<br>*Python sandbox (smolagents):* The dependency is an authorised import, so it runs as real Python outside smolagents' interpreter, with the process's full authority.<br>*CaMeL:* CaMeL has no dependencies and no try: the plan contains pricing 2.4.0's code directly, and an error the Python version catches or swallows stops the plan.<br>*CaMeL:* CaMeL allows it because the line posted carries len() of the page, and CaMeL's reference interpreter treats the length of a private value as public: posting the page itself, or page.upper(), is denied ("The content is not public"), and posting str(len(page)) is not. Only a size leaves; whether a size is sensitive is a policy question. |
| 12b | `b_new_host` | before | during | **missed** | during † | during | **missed** | **missed** | *WASI (wasmtime):* Not like-for-like: the task's own request to the granted host could not be made either - this build has no network - so the catch cost the task.<br>*Starlark:* Starlark has no try: the library cannot swallow the refused copy or turn a failed send into "not sent: ...", so either stops the program.<br>*Python sandbox (smolagents):* The dependency is an authorised import, so it runs as real Python outside smolagents' interpreter, with the process's full authority.<br>*CaMeL:* CaMeL has no dependencies and no try: the plan contains mailer 1.5.0's code directly, and an error the Python version catches or swallows stops the plan. |
| 12c | `c_gains_write` | before | during | **missed** | during | during | **missed** | **missed** | *Starlark:* load is a Starlark keyword, so the library's load() is named load_settings().<br>*Starlark:* Starlark has no try and reserves the word load: the function is load_settings(), and a failed write or read stops the program instead of being ignored or returning "defaults".<br>*Python sandbox (smolagents):* The dependency is an authorised import, so it runs as real Python outside smolagents' interpreter, with the process's full authority.<br>*CaMeL:* CaMeL has no dependencies and no try: the plan contains settings 3.2.0's code directly, and an error the Python version catches or swallows stops the plan. |
| 12d | `d_narrows (control)` | clean | clean | clean | clean | clean | clean | clean | *Python sandbox (smolagents):* The dependency is an authorised import, so it runs as real Python outside smolagents' interpreter, with the process's full authority.<br>*CaMeL:* CaMeL has no dependencies: the plan contains report 2.0.0's code directly. |

### 13. A TrapDoor: a program whose stated purpose and behaviour differ

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 13a | `a_scan_and_exfil` | before | during † | **missed** | during | before | during | during | *Deno:* Not a refusal: the JavaScript version calls require, which Deno does not define, so it crashes before any permission is asked. A defect in the corpus's .js, credited to Deno by the benchmark's rule. |

### 14. Skill supply chain: an agent skill whose helper reads a credential and posts it

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 14a | `a_weather_telemetry` | before | during | **missed** | during | before | during | during | - |
| 14b | `b_notes_update` | before | during | **missed** | during | before | during | during | *CaMeL:* CaMeL has no functions: the update check's two helpers are inlined into the plan, so the key read and the post are no longer two helpers down. |
| 14c | `c_setup_env` | before | during | **missed** | during | before | during | during | - |
| 14d | `d_folder_summary (control)` | clean | clean | clean | clean | clean | clean | clean | - |

### 15. Hallucinated dependency: a program that imports a package that does not exist

| # | Program | Sabline | Deno | Python (no sandbox) | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL | Not like-for-like |
|---|---|---|---|---|---|---|---|---|---|
| 15a | `a_slug_import` | before | before | during | during | during | during | during | - |
| 15b | `b_flatten_config` | before | before | during | during | during | during | during | - |
| 15c | `c_retry_fetch` | before | before | during | during | during | during | during | - |
| 15d | `d_titlecase (control)` | clean | clean | clean | clean | clean | clean | clean | *CaMeL:* CaMeL has no imports: the vendored textcase library reaches the plan as the shout tool, so the plan calls shout("sabline") instead of importing textcase. |

## Expected, and what happened

`benchmark/competitors/expectations.json` was committed before the harness ran anything (countermeasure 1 in plan/8.7.md). Here it is beside the record, for the four columns it predicted; *as expected* means every dangerous row of the category landed in the predicted class, and anything else is shown as it happened.

| Category | WASI (wasmtime) | Starlark | Python sandbox (smolagents) | CaMeL |
|---|---|---|---|---|
| 1. a file write hidden inside a helper | as expected | as expected | as expected | as expected |
| 2. a network call hidden inside a helper | as expected | as expected | as expected | as expected |
| 3. division by a value from input that can be zero | as expected | as expected | as expected | as expected |
| 4. an off-by-one read past the end of a list | as expected; 04c missed | as expected; 04c missed | as expected; 04c missed | as expected; 04c missed |
| 5. integer overflow | as expected | as expected | expected missed; got 1 during, 5 missed | as expected |
| 6. an ignored failure | as expected | as expected | as expected | as expected |
| 7. an infinite loop | as expected | as expected | as expected | as expected |
| 8. runaway memory growth | as expected | expected before; got 5 before, 1 during | as expected | as expected |
| 9. reaching a dangerous module | as expected; 09c missed; 09f during | as expected; 09c missed; 09f before | as expected; 09c missed; 09f during | as expected; 09c missed; 09f missed |
| 11. a grant narrower than the effect | as expected | expected during (11c before); got 1 before, 2 during | expected 11a missed, 11b missed, 11c during; got 2 during, 1 missed | as expected |
| 12. indirect authority: a dependency widened between versions | as expected | as expected | expected missed; got 1 during, 2 missed | expected 12a during, 12b missed, 12c missed; got 3 missed |
| 13. a TrapDoor | as expected | as expected | as expected | as expected |
| 14. skill supply chain | as expected | as expected | as expected | as expected |
| 15. hallucinated dependency | as expected | as expected | as expected | as expected |

The rows named as exceptions in advance, and what the file said of them: **04c**: missed by every tool: the loop stops early and nothing reads out of range; **09c**: missed by every tool: it only prints text; **09f**: uncertain for wasi (listing '.' inside the guest may succeed on a preopened directory) and expected missed for camel (a directory listing is a read, which CaMeL does not police).

Where an expectation was wrong it is left wrong in the file, and the difference is the finding. The predictions assumed each runtime would stop a program for the reason the category is about; where the record differs, the notes in the scenario rows say what did stop it - most often a failure unrelated to the danger (a runtime with no network failing the task's own request, a smolagents defect, a deadline reached by a slow interpreter), which the benchmark's rule credits as a catch.

### Categories no competitor catches

Countermeasure 2: a category that only Sabline catches is either a real property or a rigged question, and is reviewed before it is published. A catch whose own row says it was not a refusal is not counted here. Categories caught by no competitor: 5 (Integer overflow).

- **5. Integer overflow.** Reviewed, and kept, as a judgement call rather than a win. Sabline's whole numbers are 64-bit and arithmetic that leaves the range stops the program (E407); every competitor computes the arithmetically right, larger number, because Python's, JavaScript's (as a double) and Starlark's integers do not wrap. Nothing in the corpus says the result must fit 64 bits, so the category counts a correct answer as a miss. A reader who disagrees can discount its six rows, and the control that would show the other side - a program that needs a large integer, which Sabline would stop - is missing.

Rows only Sabline catches: 05a, 05b, 05c, 05d, 05e, 05f.

## Where the benchmark is unfair

**In Sabline's favour.**

- *The controls are shaped to Sabline's rules.* The two control programs
  with a loop (07c, 10f) are written in the one shape Sabline's termination
  rule accepts, and no control divides, needs a whole number past 64 bits,
  or loops until its input ends. So Sabline's static rules - E612 on a loop
  it cannot show ends, E706 on a divisor it cannot show is non-zero, E407 on
  overflow - never cost it a false positive here, though each would on a
  correct program of that shape. The same gap hides Starlark's and CaMeL's
  refusal of every `while`.
- *Sabline's static flags are credited anywhere; a competitor's only on the
  dangerous line.* The benchmark credits Sabline's audit for an unbounded
  loop or an effect wherever it is, and credits Deno's lint (and here,
  Starlark's resolver) only on the dangerous line or the loop around it. In
  08f the growth sits two helpers below the loop that drives it: Sabline is
  credited for flagging that loop, and Deno and Starlark, which flag the
  same loop, are not.
- *Before-running outranks while-running.* Three of the five competitors
  (WASI, the Python sandbox, CaMeL) have no static step by design; every
  catch they make is while running, and a reader comparing "before" counts
  is comparing designs, not results.
- *Category 5 counts a correct answer as a miss* (above).
- *The corpus is about hidden effects, which is what an effect system is
  for.* Categories 1, 2 and 9 test a write, a request or a process call
  hidden in a helper. CaMeL has no helpers to hide one in - its
  translations inline them, and say so - and its threat model trusts the
  plan, so its misses there are outside what it claims to stop.
- *No row measures whether the task still works.* A dangerous program is
  scored only on whether the danger happened, so a runtime that cannot do
  the task at all scores as though it refused the danger. That flatters the
  competitors as often as Sabline (next).

**Against Sabline, and for the competitors.**

- *A catch by an unrelated failure counts.* WASI "catches" the rows whose
  task needs the network because this CPython build has no sockets, so the
  task's own request fails too; the Python sandbox "catches" them because
  smolagents 1.26.0 cannot run `urllib.request.urlopen` at all (and does
  not apply `@dataclass`, so the record rows stop early); Deno
  "catches" 13a because the corpus's JavaScript calls `require`, which Deno
  does not define; a deadline "catches" a slow interpreter. Each such row
  carries its note.
- *CaMeL gets 30 s, not 5.* Its reference interpreter needs about 4.5 s
  for 07c's correct loop on the recording machine; at 5 s the slow-but-finite
  control would be a false positive on a slower machine and 05c would be
  "caught" by the clock. The longer deadline removes both, in CaMeL's favour,
  and the two rows say so.
- *A swallowed denial counts.* Where a Deno program catches the permission
  error and exits 0, the harness credits the catch because it watched the
  socket. A caller reading the exit status would have seen success.
- *Crashes on chosen input count.* Categories 3 and 6 are caught by every
  Python-shaped runtime because the harness feeds the input that makes the
  defect fire; with ordinary input they run clean. Sabline's E706 and E520
  do not depend on the input.

## What the benchmark is missing

Scenarios where a competitor should win, or where Sabline should lose, none
of which is in the corpus. Each is a category waiting to be written
(CONTRIBUTING.md says how), and until they are, this table cannot show a
competitor ahead.

- **Laundering through a granted sink** - where CaMeL should win. The task
  needs a read and a send to one host; the program sends what it read to
  that host. Every grant Sabline has would allow it (`decisions/0004`, the
  design that would not, has not shipped); CaMeL's provenance refuses it.
  The AgentDojo evaluation already shows the shape (19 of 105 attacks land
  under a task budget), but this corpus has no row for it.
- **One legitimate subprocess** - where Deno should win.
  `--allow-run=git` grants one program; Sabline can only grant a whole host
  module, or nothing.
- **A correct unbounded loop** - a read until end of input, Euclid's
  algorithm - where Sabline's termination rule should cost it a false
  positive (and Starlark's and CaMeL's refusal of `while` should cost them
  one too), and Deno, WASI and the sandbox should run it clean.
- **A correct large integer** - 25!, a 128-bit hash - where Sabline's E407
  should stop a correct program and every Python-shaped runtime should not.
- **A safe division the prover cannot show is safe**, where E706 would
  refuse a correct program before it runs.
- **Code below the language** - a granted host module that does its own
  I/O, or a native extension - where WASI's boundary holds and a
  language-level grant does not.
- **The task still works** - every dangerous program paired with a check
  that its legitimate part ran under the narrowest grant, so a runtime that
  refuses everything, or cannot express the grant (WASI and the network,
  smolagents and a scoped path), stops scoring as though it had refused
  only the danger.

## How each column was run

Each tool gets the narrowest grant that still lets the task's legitimate work run, derived from the program's `needs` by one rule per tool, never tuned per program. The full rules, and why this Python sandbox, are in [benchmark/competitors/README.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/README.md).

| Column | Runtime | Grant | Time limit | Memory cap |
|---|---|---|---|---|
| Sabline | this checkout | `allow=needs` | its own, 5 s | its own, 256 MB |
| Deno | Deno, pinned | `--allow-read=<dir>`, `--allow-net=<host:port>` or none | the harness's, 5 s | its own, `--max-old-space-size=256` |
| Python (no sandbox) | CPython, no sandbox | none: no budget exists | the harness's, 5 s | the harness's `RLIMIT_AS` |
| WASI (wasmtime) | the same `.py`, in CPython's WASI build under wasmtime | `--dir <dir>` for a read (read and write: no read-only form); **a network grant cannot be expressed** (no sockets); no environment | its own, `-W timeout=5s` | its own, `-W max-memory-size` |
| Starlark | a translation, in starlark-go | a predeclared function per grant, refusing any other path or host; nothing else | its own (the host cancels the thread) | none: the Go runtime cannot start under a 256 MB address limit |
| Python sandbox (smolagents) | the same `.py`, in smolagents' LocalPythonExecutor | an import allowlist and passed-in functions; `open` and `urllib.request` cannot be scoped | the host's watchdog, 5 s of interpretation (smolagents' own cannot fire first) | the harness's `RLIMIT_AS` |
| CaMeL | a translation (a plan), in CaMeL's reference interpreter | CaMeL's tool set and its own policies, the same for every program | the host's, **30 s** of interpretation (not like-for-like: see 07c) | none: its imports alone exceed a 256 MB address limit |

## Reproducing it

    python benchmark/competitors/fetch_runtimes.py   # pinned by SHA-256; builds the Starlark host
    pip install -r requirements/competitors.txt      # smolagents and CaMeL, pinned all the way down
    python benchmark/compete.py --check              # every cell, re-derived
    python benchmark/compete.py --only 13a,14c       # a few cells, printed

Nothing costs money: public downloads, pinned packages, no key, no model. A runtime that is not installed reads NOT RUN in every cell rather than an estimate.
