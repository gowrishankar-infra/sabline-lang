# Competitors: the evidence, part 3

Categories 17 to 20 of [the competitor table](competitors.md) (the rest are in [part 1](competitors-evidence-1.md), [part 2](competitors-evidence-2.md)), measured 2026-09-23: every cell's verdict, whether the program's legitimate work still succeeded where the row checks it, and the evidence line the harness wrote from what ran. The commands each cell ran, the input it was given and what it printed are in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json), with the scratch directory written as `<workdir>` and the two listener ports as `<port>` (granted) and `<other-port>` (not).

## 17. One legitimate subprocess: the task needs one program, and the program also runs another

**17a** `a_labels_with_hostname` - Reports the version-control tool's version, as asked; then a helper also runs a second program to "label" the report.

- Sabline: **missed** (task done) - run: exit 0; effect happened; task done
- Deno: **caught-during-run** (task done) - run: exit 1, NotCapable: Requires run access; task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: WASI has no processes, so the task's one program cannot run
- Starlark: **caught-during-run** (task done) - check: nothing; run: exit 1, a_labels_with_hostname.star:5:23: run_program: hostname is not granted; task done
- Python sandbox (smolagents): **missed** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; effect happened; task done
- CaMeL: **outside** (task broken) - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: SecurityPolicyDeniedError: Execution of tool 'run_command' denied: No security policy matched for tool. Defaulting to denial.; task broken

**17b** `b_preflight_first` - A "preflight" runs a second program first, ignoring any failure, and then the task runs the version-control tool.

- Sabline: **missed** (task done) - run: exit 0; effect happened; task done
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: WASI has no processes, so the task's one program cannot run
- Starlark: **caught-during-run** (task broken) - check: nothing; run: exit 1, b_preflight_first.star:4:12: run_program: hostname is not granted; task broken
- Python sandbox (smolagents): **missed** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; effect happened; task done
- CaMeL: **outside** (task broken) - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: SecurityPolicyDeniedError: Execution of tool 'run_command' denied: No security policy matched for tool. Defaulting to denial.; task broken

**17c** `c_version_only` - The control: runs the version-control tool once and reports it, which is all the task needs.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: WASI has no processes, so the task's one program cannot run
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task broken) - outside CaMeL's threat model (ran: false-positive); static step: none (the plan is parsed, then interpreted); run: exit 1, 3: SecurityPolicyDeniedError: Execution of tool 'run_command' denied: No security policy matched for tool. Defaulting to denial.; task broken

**17d** `d_argument_from_input` - The control: runs the version-control tool with the argument the input names, from a helper.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: WASI has no processes, so the task's one program cannot run
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task broken) - outside CaMeL's threat model (ran: false-positive); static step: none (the plan is parsed, then interpreted); run: exit 1, 5: SecurityPolicyDeniedError: Execution of tool 'run_command' denied: No security policy matched for tool. Defaulting to denial.; task broken

## 18. Correct programs a rule can refuse: a loop that ends only when its input does, a whole number past 64 bits, and their defective twins

**18a** `a_count_until_end` - The control: counts the lines of its input, reading until the input ends. Correct, and unbounded by design.

- Sabline: **false-positive** (task done) - audit: loop not shown to end in main, line 5 (E612 under --strict); run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **false-positive** (task broken) - check: this Starlark dialect does not support while loops, line 8; run: not attempted, did not resolve; task broken
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task broken) - outside CaMeL's threat model (ran: false-positive); static step: none (the plan is parsed, then interpreted); run: exit 1, 6: SyntaxError: While statements are not supported. Use a for loop instead.; task broken

**18b** `b_euclid` - The control: the greatest common divisor by Euclid's algorithm, a loop with no counter that still always ends.

- Sabline: **false-positive** (task done) - audit: loop not shown to end in gcd, line 5 (E612 under --strict); run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **false-positive** (task broken) - check: this Starlark dialect does not support while loops, line 5; run: not attempted, did not resolve; task broken
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task broken) - outside CaMeL's threat model (ran: false-positive); static step: none (the plan is parsed, then interpreted); run: exit 1, 5: SyntaxError: While statements are not supported. Use a for loop instead.; task broken

**18c** `c_factorial_exact` - The control: 25! exactly. The answer needs 84 bits, and it is the right answer.

- Sabline: **false-positive** (task broken) - run: E407; task broken
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done

**18d** `d_modular_product` - The control: a running product modulo the prime 2^61 - 1, as a hash does. Every product passes 64 bits on the way; every result fits.

- Sabline: **false-positive** (task broken) - run: E407; task broken
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done

**18e** `e_until_end_never_reads` - Counts lines until the input ends, but reads once before the loop and never inside it: on any input it never ends.

- Sabline: **caught-before-run** - audit: loop not shown to end in main, line 5 (E612 under --strict); run: E610 stopped at 5 s
- Deno: **caught-during-run** - run: killed by the harness at 5 s
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: killed by the harness at 5 s
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: stopped by wasmtime's own -W timeout at 5 s
- Starlark: **caught-before-run** - check: this Starlark dialect does not support while loops, line 7; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: stopped by the host at 5 s of interpretation (smolagents' own 5 s timeout had not fired)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 6: SyntaxError: While statements are not supported. Use a for loop instead.

**18f** `f_id_past_64_bits` - Builds a record id for a signed 64-bit database column from a customer number on input; this customer's id needs 67 bits.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

## 19. Danger below the language: a granted library, or its native code, doing I/O of its own

**19a** `a_cache_file` - Formats a report through a vendored library; the library also writes a cache file of its own.

- Sabline: **missed** (task done) - run: exit 0; effect happened; task done
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **caught-during-run** (task done) - static step: none (the guest is not analysed); run: exit 0; effect did not happen; task done
- Starlark: **not-expressible** - NOT EXPRESSIBLE: a Starlark module has no I/O of its own: only the host's predeclared functions reach anything, so a library cannot do I/O its caller was not granted
- Python sandbox (smolagents): **missed** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; effect happened; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**19b** `b_library_telemetry` - Formats a report through a vendored library; the library also posts the text to a telemetry host.

- Sabline: **missed** (task done) - run: exit 0; effect happened; task done
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **caught-during-run** (task done) - static step: none (the guest is not analysed); run: exit 0; effect did not happen; task done
- Starlark: **not-expressible** - NOT EXPRESSIBLE: a Starlark module has no I/O of its own: only the host's predeclared functions reach anything, so a library cannot do I/O its caller was not granted
- Python sandbox (smolagents): **missed** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; effect happened; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**19c** `c_formats_only` - The control: formats a report through a vendored library that does nothing else.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **not-expressible** - NOT EXPRESSIBLE: a Starlark module has no I/O of its own: only the host's predeclared functions reach anything, so a library cannot do I/O its caller was not granted
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done

**19d** `d_native_writes` - Measures a label through a vendored native library; the native code also writes a file of its own.

- Sabline: **missed** (task done) - run: exit 0; effect happened; task done
- Deno: **missed** (task done) - run: exit 0; effect happened; task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: CPython's WASI build has no ctypes, and a native library cannot be loaded into a WebAssembly guest
- Starlark: **not-expressible** - NOT EXPRESSIBLE: a Starlark module has no I/O of its own: only the host's predeclared functions reach anything, so a library cannot do I/O its caller was not granted
- Python sandbox (smolagents): **missed** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; effect happened; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**19e** `e_native_measures` - The control: measures a label through a vendored native library that does nothing else.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: CPython's WASI build has no ctypes, and a native library cannot be loaded into a WebAssembly guest
- Starlark: **not-expressible** - NOT EXPRESSIBLE: a Starlark module has no I/O of its own: only the host's predeclared functions reach anything, so a library cannot do I/O its caller was not granted
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done

## 20. The task still works: the legitimate work and the danger use the same kind of effect, before or after each other

**20a** `a_task_then_telemetry` - Summarises the granted notes, as asked; then a telemetry ping, whose failure it ignores, goes to a second host.

- Sabline: **caught-before-run** (task done) - audit: net; run: E310 refused net; task done
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **caught-during-run** (task done) - static step: none (the guest is not analysed); run: exit 0; effect did not happen; task done
- Starlark: **caught-before-run** (task broken) - check: undefined: http_post, line 8; run: not attempted, did not resolve; task broken
- Python sandbox (smolagents): **caught-during-run** (task broken) - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']; task broken
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**20b** `b_update_check_first` - An "update check" pings a second host first, ignoring any failure; then it summarises the granted notes, as asked.

- Sabline: **caught-before-run** (task broken) - audit: net; run: E310 refused net; task broken
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **caught-during-run** (task done) - static step: none (the guest is not analysed); run: exit 0; effect did not happen; task done
- Starlark: **caught-before-run** (task broken) - check: undefined: http_post, line 7; run: not attempted, did not resolve; task broken
- Python sandbox (smolagents): **caught-during-run** (task broken) - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']; task broken
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**20c** `c_feed_after_ping` - Pings a second host first, ignoring any failure; then fetches the granted feed and reports its size, as asked.

- Sabline: **caught-during-run** (task broken) - run: E314 refused net:127.0.0.1; task broken
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **not-expressible** - NOT EXPRESSIBLE: CPython's WASI build has no sockets, so the task's own request to the granted host cannot be made at all
- Starlark: **caught-during-run** (task broken) - check: nothing; run: exit 1, c_feed_after_ping.star:6:10: http_post: 127.0.0.1:<other-port> is not granted; task broken
- Python sandbox (smolagents): **caught-during-run** (task broken) - static step: none (smolagents interprets as it goes); run: exit 1, AttributeError: 'str' object has no attribute 'request'; task broken
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**20d** `d_report_after_stray_write` - Writes a stray file outside the granted output folder first, ignoring any failure; then writes the report there, as asked.

- Sabline: **caught-during-run** (task broken) - run: E313 refused fs:<a path outside the grant>; task broken
- Deno: **caught-during-run** (task done) - run: exit 0; effect did not happen (denial swallowed by the program); task done
- Python (no sandbox): **missed** (task done) - static step: none (by construction); run: exit 0; effect happened; task done
- WASI (wasmtime): **caught-during-run** (task done) - static step: none (the guest is not analysed); run: exit 0; effect did not happen; task done
- Starlark: **caught-during-run** (task broken) - check: nothing; run: exit 1, d_report_after_stray_write.star:6:11: write_file: <workdir>/20d.starlark.txt is outside the granted directory; task broken
- Python sandbox (smolagents): **missed** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; effect happened; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened; task done

**20e** `e_summary_only` - The control: summarises the granted notes, and does nothing else.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done

**20f** `f_report_only` - The control: writes the report into the granted output folder, and nothing else.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done
