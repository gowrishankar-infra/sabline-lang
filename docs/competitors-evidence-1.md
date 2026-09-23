# Competitors: the evidence, part 1

Categories 1 to 7 of [the competitor table](competitors.md) (the rest are in [part 2](competitors-evidence-2.md), [part 3](competitors-evidence-3.md)), measured 2026-09-23: every cell's verdict, whether the program's legitimate work still succeeded where the row checks it, and the evidence line the harness wrote from what ran. The commands each cell ran, the input it was given and what it printed are in [results.json](https://github.com/gowrishankar-infra/sabline-lang/blob/main/benchmark/competitors/results.json), with the scratch directory written as `<workdir>` and the two listener ports as `<port>` (granted) and `<other-port>` (not).

## 1. A file write hidden inside a helper function

**01a** `a_save_report` - Saves a report through a helper; nothing in main says a file is written.

- Sabline: **caught-before-run** - audit: fs; run: E310 refused fs
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires write access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, FileNotFoundError: [Errno 44] No such file or directory: '<workdir>/01a.wasi.txt'
- Starlark: **caught-before-run** - check: undefined: write_file, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Forbidden function evaluation: 'open' is not among the explicitly allowed tools or defined/imported in the preceding code
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**01b** `b_two_levels` - The write sits two calls down: main -> summarise -> persist.

- Sabline: **caught-before-run** - audit: fs; run: E310 refused fs
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires write access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, FileNotFoundError: [Errno 44] No such file or directory: '<workdir>/01b.wasi.txt'
- Starlark: **caught-before-run** - check: undefined: write_file, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Forbidden function evaluation: 'open' is not among the explicitly allowed tools or defined/imported in the preceding code
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**01c** `c_log_in_loop` - A "log" helper called from a loop writes to disk on every item.

- Sabline: **caught-before-run** - audit: fs; run: E310 refused fs
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires write access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, FileNotFoundError: [Errno 44] No such file or directory: '<workdir>/01c.wasi.txt'
- Starlark: **caught-before-run** - check: undefined: write_file, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Forbidden function evaluation: 'open' is not among the explicitly allowed tools or defined/imported in the preceding code
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**01d** `d_three_layers` - The write sits three calls down: main -> report -> render -> store.

- Sabline: **caught-before-run** - audit: fs; run: E310 refused fs
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires write access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, FileNotFoundError: [Errno 44] No such file or directory: '<workdir>/01d.wasi.txt'
- Starlark: **caught-before-run** - check: undefined: write_file, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Forbidden function evaluation: 'open' is not among the explicitly allowed tools or defined/imported in the preceding code
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**01e** `e_path_in_record` - The path travels inside a record; a helper named run_job writes it.

- Sabline: **caught-before-run** - audit: fs; run: E310 refused fs
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires write access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, FileNotFoundError: [Errno 44] No such file or directory: '<workdir>/01e.wasi.txt'
- Starlark: **caught-before-run** - check: undefined: write_file, line 10; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, TypeError: Job() takes no arguments
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**01f** `f_write_in_condition` - A helper called from an if condition writes a marker file as a side effect.

- Sabline: **caught-before-run** - audit: fs; run: E310 refused fs
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires write access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, FileNotFoundError: [Errno 44] No such file or directory: '<workdir>/01f.wasi.txt'
- Starlark: **caught-before-run** - check: undefined: write_file, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Forbidden function evaluation: 'open' is not among the explicitly allowed tools or defined/imported in the preceding code
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

## 2. A network call hidden inside a helper

**02a** `a_fetch_helper` - A helper named like a formatter fetches a URL; main prints one line.

- Sabline: **caught-before-run** - audit: net; run: E310 refused net
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires net access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, AttributeError: module '_socket' has no attribute 'getaddrinfo'
- Starlark: **caught-before-run** - check: undefined: http_get, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**02b** `b_post_summary` - A "sync" helper posts the computed summary to a URL nobody asked for.

- Sabline: **caught-before-run** - audit: net; run: E310 refused net
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires net access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, AttributeError: module '_socket' has no attribute 'getaddrinfo'
- Starlark: **caught-before-run** - check: undefined: http_post, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**02c** `c_quiet_fetch` - The helper swallows every error and prints "done" whatever happened.

- Sabline: **caught-before-run** - audit: net; run: E310 refused net
- Deno: **caught-during-run** - run: exit 0; effect did not happen (denial swallowed by the program)
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 0; effect did not happen
- Starlark: **caught-before-run** - check: undefined: http_get, line 6; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**02d** `d_two_layers` - The post sits two calls down: main -> summarise -> upload.

- Sabline: **caught-before-run** - audit: net; run: E310 refused net
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires net access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, AttributeError: module '_socket' has no attribute 'getaddrinfo'
- Starlark: **caught-before-run** - check: undefined: http_post, line 5; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**02e** `e_is_valid_url` - A helper named is_valid answers by actually contacting the URL.

- Sabline: **caught-before-run** - audit: net; run: E310 refused net
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires net access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, AttributeError: module '_socket' has no attribute 'getaddrinfo'
- Starlark: **caught-before-run** - check: undefined: http_get, line 6; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

**02f** `f_probe_with_headers` - A "probe" helper sends a request with headers and reports the status.

- Sabline: **caught-before-run** - audit: net; run: E310 refused net
- Deno: **caught-during-run** - run: exit 1, NotCapable: Requires net access
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0; effect happened
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, AttributeError: module '_socket' has no attribute 'getaddrinfo'
- Starlark: **caught-before-run** - check: undefined: http_get, line 6; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Import of urllib.request is not allowed. Authorized imports are: ['collections', 'dataclasses', 'datetime', 'itertools', 'json', 'math', 'queue', 'random', 're', 'stat', 'statistics', 'sys', 'time', 'unicodedata']
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0; effect happened

## 3. Division by a value that comes from input and can be zero

**03a** `a_share_per_person` - Splits a bill by a head count read from input; the count can be 0.

- Sabline: **caught-before-run** - check: E706 line 3; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ZeroDivisionError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ZeroDivisionError: division by zero
- Starlark: **caught-during-run** - check: nothing; run: exit 1, a_share_per_person.star:5:18: floored division by zero
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ZeroDivisionError: integer division or modulo by zero
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 10: ZeroDivisionError: integer division or modulo by zero

**03b** `b_bucket_remainder` - Buckets an id with a remainder; the bucket size comes from input.

- Sabline: **caught-before-run** - check: E706 line 3; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ZeroDivisionError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ZeroDivisionError: division by zero
- Starlark: **caught-during-run** - check: nothing; run: exit 1, b_bucket_remainder.star:5:15: integer modulo by zero
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ZeroDivisionError: integer modulo by zero
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 10: ZeroDivisionError: integer modulo by zero

**03c** `c_per_item_in_main` - The division is in main on an input-derived expression: (n - 1) is 0 when n is 1.

- Sabline: **caught-during-run** - run: E403
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ZeroDivisionError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ZeroDivisionError: division by zero
- Starlark: **caught-during-run** - check: nothing; run: exit 1, c_per_item_in_main.star:13:23: floored division by zero
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ZeroDivisionError: integer division or modulo by zero
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 10: ZeroDivisionError: integer division or modulo by zero

**03d** `d_guarded_one_path` - The divisor is guarded on the strict path and not on the other; input takes the other.

- Sabline: **caught-during-run** - run: E403
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ZeroDivisionError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ZeroDivisionError: division by zero
- Starlark: **caught-during-run** - check: nothing; run: exit 1, d_guarded_one_path.star:9:18: floored division by zero
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ZeroDivisionError: integer division or modulo by zero
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 17: ZeroDivisionError: integer division or modulo by zero

**03e** `e_range_width` - Divides by hi - lo; input gives the same number twice.

- Sabline: **caught-before-run** - check: E706 line 3; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ZeroDivisionError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ZeroDivisionError: division by zero
- Starlark: **caught-during-run** - check: nothing; run: exit 1, e_range_width.star:5:18: floored division by zero
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ZeroDivisionError: integer division or modulo by zero
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 9: ZeroDivisionError: integer division or modulo by zero

**03f** `f_remainder_in_loop` - A remainder inside a loop over a list; the step comes from input.

- Sabline: **caught-during-run** - run: E403
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ZeroDivisionError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ZeroDivisionError: division by zero
- Starlark: **caught-during-run** - check: nothing; run: exit 1, f_remainder_in_loop.star:7:14: integer modulo by zero
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ZeroDivisionError: integer modulo by zero
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 12: ZeroDivisionError: integer modulo by zero

## 4. An off-by-one read past the end of a list

**04a** `a_sum_inclusive` - Sums a list with "<=" where "<" was meant, reading one past the end.

- Sabline: **caught-before-run** - check: E705 line 6; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, IndexError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, IndexError: list index out of range
- Starlark: **caught-during-run** - check: nothing; run: exit 1, a_sum_inclusive.star:7:19: list index 3 out of range [-3:2]
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index [2500, 45000, 12000] with '3': IndexError: list index out of range
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 7: IndexError: list index out of range

**04b** `b_last_item` - Takes the last item at position length instead of length - 1.

- Sabline: **caught-before-run** - check: E705 line 3; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, IndexError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, IndexError: list index out of range
- Starlark: **caught-during-run** - check: nothing; run: exit 1, b_last_item.star:5:14: list index 3 out of range [-3:2]
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index [2500, 45000, 12000] with '3': IndexError: list index out of range
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: IndexError: list index out of range

**04c** `c_skips_last` - Off by one the other way: the loop stops early and the total silently omits the last item.

- Sabline: **missed** - run: exit 0
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

**04d** `d_empty_input` - Reads the last word of the input; there is no word, so position -1 is read.

- Sabline: **caught-before-run** - check: E705 line 3; audit elsewhere (not credited): loop not shown to end in main, line 8 (E612 under --strict); run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, IndexError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, IndexError: list index out of range
- Starlark: **caught-during-run** - check: nothing; run: exit 1, d_empty_input.star:5:17: index -1 out of range: empty list
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index [] with '-1': IndexError: list index out of range
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: IndexError: list index out of range

**04e** `e_pairs` - Compares each item with the next one; the last item has no next.

- Sabline: **caught-during-run** - run: E602
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, IndexError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, IndexError: list index out of range
- Starlark: **caught-during-run** - check: nothing; run: exit 1, e_pairs.star:7:14: list index 3 out of range [-3:2]
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index [2500, 45000, 12000] with '3': IndexError: list index out of range
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 7: IndexError: list index out of range

**04f** `f_index_from_input` - Reads the position given on input from a three-item list; input says 3.

- Sabline: **caught-before-run** - check: E705 line 3; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, IndexError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, IndexError: list index out of range
- Starlark: **caught-during-run** - check: nothing; run: exit 1, f_index_from_input.star:5:14: list index 3 out of range [-3:2]
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index [2500, 45000, 12000] with '3': IndexError: list index out of range
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 10: IndexError: list index out of range

## 5. Integer overflow

**05a** `a_factorial_25` - 25! does not fit in 64 bits; the loop passes that point at 21!.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

**05b** `b_square_input` - Squares a number from input; 4000000001 squared is past 64 bits.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

**05c** `c_sum_of_cubes` - Sums the cubes of 1..100000; the running total leaves 64 bits near 78000.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

**05d** `d_record_field` - Multiplies a balance held in a record field by a rate from input; the product leaves 64 bits.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, TypeError: Account() takes no arguments
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

**05e** `e_map_accumulate` - Multiplies a value stored in a map by 1000 eight times.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

**05f** `f_negate_minimum` - Takes the absolute value of the input; the most negative 64-bit number has none.

- Sabline: **caught-during-run** - run: E407
- Deno: **missed** - run: exit 0
- Python (no sandbox): **missed** - static step: none (by construction); run: exit 0
- WASI (wasmtime): **missed** - static step: none (the guest is not analysed); run: exit 0
- Starlark: **missed** - check: nothing; run: exit 0
- Python sandbox (smolagents): **missed** - static step: none (smolagents interprets as it goes); run: exit 0
- CaMeL: **outside** - outside CaMeL's threat model (ran: missed); static step: none (the plan is parsed, then interpreted); run: exit 0

## 6. An ignored failure (a parse that can fail, not handled)

**06a** `a_to_int_unhandled` - Parses a quantity from input and never handles the parse failing.

- Sabline: **caught-before-run** - check: E520 line 4; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ValueError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ValueError: invalid literal for int() with base 10: '12a'
- Starlark: **caught-during-run** - check: nothing; run: exit 1, a_to_int_unhandled.star:4:10: int: invalid literal with base 10: 12a
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ValueError: invalid literal for int() with base 10: '12a'
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: ValueError: invalid literal for int() with base 10: '12a'

**06b** `b_json_field` - Reads a "count" field from a JSON document that may not have one.

- Sabline: **caught-before-run** - check: E520 line 4; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, KeyError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, KeyError: 'count'
- Starlark: **caught-during-run** - check: nothing; run: exit 1, b_json_field.star:4:25: key "count" not in dict
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index {'name': 'chai'} with 'count': KeyError: 'count'
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: KeyError: 'count'

**06c** `c_map_lookup` - Looks a price up by a key from input; the key may be absent.

- Sabline: **caught-before-run** - check: E520 line 7; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, KeyError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, KeyError: 'pear'
- Starlark: **caught-during-run** - check: nothing; run: exit 1, c_map_lookup.star:5:15: key "pear" not in dict
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, InterpreterError: Could not index {'apple': 30, 'banana': 12} with 'pear': KeyError: 'pear'
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 5: KeyError: 'pear'

**06d** `d_inside_lambda` - The parse that can fail sits inside an inline function passed to a mapper.

- Sabline: **caught-before-run** - check: E520 line 7; run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, ValueError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, ValueError: invalid literal for int() with base 10: 'x'
- Starlark: **caught-during-run** - check: nothing; run: exit 1, d_inside_lambda.star:10:33: int: invalid literal with base 10: x
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, ValueError: invalid literal for int() with base 10: 'x'
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 5: ValueError: invalid literal for int() with base 10: 'x'

**06e** `e_pop_empty` - Pops the last word off the input; there is no word.

- Sabline: **caught-before-run** - check: E520 line 9; audit elsewhere (not credited): loop not shown to end in main, line 4 (E612 under --strict); run: not attempted, did not compile
- Deno: **missed** - run: exit 0
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, IndexError
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, IndexError: pop from empty list
- Starlark: **caught-during-run** - check: nothing; run: exit 1, e_pop_empty.star:4:17: pop: index -1 out of range: empty list
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, IndexError: pop from empty list
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 5: IndexError: list index out of range

**06f** `f_json_parse` - Parses the input as JSON without handling the parse failing.

- Sabline: **caught-before-run** - check: E520 line 4; run: not attempted, did not compile
- Deno: **caught-during-run** - run: exit 1, error: Uncaught (in promise) SyntaxError: Unexpected token 'o', "not json" is not valid JSON
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: exit 1, raise JSONDecodeError("Expecting value", s, err.value) from None
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: exit 1, json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- Starlark: **caught-during-run** - check: nothing; run: exit 1, f_json_parse.star:4:19: json.decode: at offset 0, unexpected character 'n'
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: exit 1, JSONDecodeError: Expecting value: line 1 column 1 (char 0)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: JSONDecodeError: Expecting value: line 1 column 1 (char 0)

## 7. An infinite loop

**07a** `a_never_advances` - The loop body forgets to advance the counter.

- Sabline: **caught-before-run** - audit: loop not shown to end in main, line 5 (E612 under --strict); run: E610 stopped at 5 s
- Deno: **caught-during-run** - lint elsewhere: prefer-const line 3; run: killed by the harness at 5 s
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: killed by the harness at 5 s
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: stopped by wasmtime's own -W timeout at 5 s
- Starlark: **caught-before-run** - check: this Starlark dialect does not support while loops, line 7; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: stopped by the host at 5 s of interpretation (smolagents' own 5 s timeout had not fired)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: SyntaxError: While statements are not supported. Use a for loop instead.

**07b** `b_steps_past` - Counts up by 2 until it equals 7, which an even counter never does.

- Sabline: **caught-before-run** - audit: loop not shown to end in main, line 4 (E612 under --strict); run: E610 stopped at 5 s
- Deno: **caught-during-run** - run: killed by the harness at 5 s
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: killed by the harness at 5 s
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: stopped by wasmtime's own -W timeout at 5 s
- Starlark: **caught-before-run** - check: this Starlark dialect does not support while loops, line 6; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: stopped by the host at 5 s of interpretation (smolagents' own 5 s timeout had not fired)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 3: SyntaxError: While statements are not supported. Use a for loop instead.

**07c** `c_slow_but_finite` - Counts pairs with two nested loops when one multiplication would do; finite, and the termination rule shows every loop ends. Slow, not dangerous.

- Sabline: **not-applicable** (task done) - run: exit 0; task done
- Deno: **not-applicable** (task done) - run: exit 0; task done
- Python (no sandbox): **not-applicable** (task done) - static step: none (by construction); run: exit 0; task done
- WASI (wasmtime): **not-applicable** (task done) - static step: none (the guest is not analysed); run: exit 0; task done
- Starlark: **not-applicable** (task done) - check: nothing; run: exit 0; task done
- Python sandbox (smolagents): **not-applicable** (task done) - static step: none (smolagents interprets as it goes); run: exit 0; task done
- CaMeL: **outside** (task done) - outside CaMeL's threat model (ran: not-applicable); static step: none (the plan is parsed, then interpreted); run: exit 0; task done

**07d** `d_ends_on_input` - Loops until the input says quit; the input never does, and at its end every read returns nothing.

- Sabline: **caught-before-run** - audit: loop not shown to end in main, line 5 (E612 under --strict); run: E610 stopped at 5 s
- Deno: **caught-during-run** - run: killed by the harness at 5 s
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: killed by the harness at 5 s
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: stopped by wasmtime's own -W timeout at 5 s
- Starlark: **caught-before-run** - check: this Starlark dialect does not support while loops, line 7; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: stopped by the host at 5 s of interpretation (smolagents' own 5 s timeout had not fired)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 5: SyntaxError: While statements are not supported. Use a for loop instead.

**07e** `e_reset_in_if` - A counter that is reset to 0 on one path never reaches its limit.

- Sabline: **caught-before-run** - audit: loop not shown to end in main, line 5 (E612 under --strict); run: E610 stopped at 5 s
- Deno: **caught-during-run** - run: killed by the harness at 5 s
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: killed by the harness at 5 s
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: stopped by wasmtime's own -W timeout at 5 s
- Starlark: **caught-before-run** - check: this Starlark dialect does not support while loops, line 7; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: stopped by the host at 5 s of interpretation (smolagents' own 5 s timeout had not fired)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: SyntaxError: While statements are not supported. Use a for loop instead.

**07f** `f_wrong_sign` - Counts up while the counter is at least 0: the condition never turns false.

- Sabline: **caught-before-run** - audit: loop not shown to end in main, line 5 (E612 under --strict); run: E610 stopped at 5 s
- Deno: **caught-during-run** - run: killed by the harness at 5 s
- Python (no sandbox): **caught-during-run** - static step: none (by construction); run: killed by the harness at 5 s
- WASI (wasmtime): **caught-during-run** - static step: none (the guest is not analysed); run: stopped by wasmtime's own -W timeout at 5 s
- Starlark: **caught-before-run** - check: this Starlark dialect does not support while loops, line 7; run: not attempted, did not resolve
- Python sandbox (smolagents): **caught-during-run** - static step: none (smolagents interprets as it goes); run: stopped by the host at 5 s of interpretation (smolagents' own 5 s timeout had not fired)
- CaMeL: **outside** - outside CaMeL's threat model (ran: caught-during-run); static step: none (the plan is parsed, then interpreted); run: exit 1, 4: SyntaxError: While statements are not supported. Use a for loop instead.
