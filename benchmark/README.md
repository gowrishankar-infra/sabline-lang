# The comparison benchmark

A hundred and two small programs, each written three times with the same
behaviour - in Sabline, in JavaScript for Deno, and in Python - and one
harness that runs every program through every tool and records what was
caught before running, what was caught while running, what was missed,
and, where the program has legitimate work to do, whether that work still
got done. The result
is `RESULTS.md` and `results.json`, regenerated with one command:

    python benchmark/run.py

Nothing in the harness is tuned per program. The same budget, the same
timeout, the same memory cap and the same observation checks apply to
every row. If you think a row is wrong, the program, the rule and the
command that produced it are all here; change one and rerun.

## What is being compared

| Tool | Before running | While running |
|---|---|---|
| Sabline | `sabline check` (types, effects, unhandled failures, and the prover's E705/E706) and `sabline audit` (which effects, Python modules, paths and hosts the program names, and which loops the termination rule cannot show to end - `loops_unshown`, E612 under `--strict`); in category 12, also `sabline deps-diff` on the dependency's two versions; in category 15, `sabline check` reports an import of a file that is not vendored (E512) on the import line | `sabline.run(source, allow=needs, timeout=5, max_memory_mb=256)` - the budget refuses anything the task does not need: an effect (E310), a module (E311), a path outside the granted directory (E313), a host or port outside the grant (E314), a documented credential location (E318); the limits stop a runaway (E610/E611) |
| Deno 2.x | `deno check` (given the run's `--allow-import` in category 15, so it can fetch the remote module graph) and `deno lint --json` | `deno run --no-prompt --v8-flags=--max-old-space-size=256 file.js` with no `--allow-*` flag, except where the task needs one - the program's `deno_flags` in `corpus.json`: `--allow-read=<dir>` in 11a, 12c, 12d, 13a and categories 14, 16 and 20, `--allow-net=<host:port>` in 11b, 12a, 12b and categories 16 and 20, `--allow-write=<dir>` in 20d and 20f, `--allow-run=git` in category 17, `--allow-ffi` in 19d and 19e, and `--allow-import=127.0.0.1:<port>` for the package host in category 15 |
| Plain Python | nothing, by construction | `python file.py` in a subprocess with the same 5 second timeout and, where the platform allows, the same 256 MB cap |

"Needs" is the effect set the task legitimately requires, stated per
program in `corpus.json`: `io` for most, `io, ffi:math` for the two
control programs that call the host's `sqrt`,
`io, fs:read:<the granted directory>` for 11a, 12c, 12d, 13a and the
four skills of category 14, `io, net:127.0.0.1:<the listener's port>`
for 11b, 12a and 12b, both for category 16, `io, ffi:subprocess` for
category 17, `io, ffi:<the vendored library>` for category 19, and in
category 20 what each task needs - a read, the granted host, or a write
into `out/<id>/<tool>/`; the harness fills the placeholders. `env` is never a need, so a program that reads the
environment is outside its budget. That is the
Sabline budget for the run; it is also the standard the audit is held to
(see the rules below).

The timeout for Deno and Python is the harness's own `subprocess`
timeout. Sabline's is the `timeout=` argument of `sabline.run`, which
runs the program in a child process it can kill. The difference is who
owns the limit, not whether it fires; the results say which.

Memory caps: Sabline `max_memory_mb` uses the OS address-space limit
(`RLIMIT_AS`) on POSIX and a job object with
`JOB_OBJECT_LIMIT_PROCESS_MEMORY` on Windows: enforced on Linux and on
Windows, best-effort on macOS. Deno gets `--max-old-space-size` on
every platform. Python's child gets `RLIMIT_AS` on Linux and macOS
(best-effort there) and a job object on Windows. The header of
`RESULTS.md` records which applied on the machine that produced it.

## The corpus

Twenty categories: ten of six programs each, category 11 of three
(added with the scoped budgets of 3.0), category 12 of four (added
with `sabline deps-diff` in 7.1), category 13 of one (the TrapDoor,
8.2), categories 14 and 15 of four each (the skill supply chain
and the hallucinated dependency, 8.3), and five added in 8.7, when the
[competitor scoring](competitors/README.md) showed a corpus Sabline
could not lose: 16 (five), 17 (four), 18 (six), 19 (five) and 20
(six). In the first ten, programs `a`
to `c` were written first; `d` to `f` were written afterwards, against
the tools, to hide the same defects better. Every dangerous program has one dangerous
line, marked `DANGER` in a trailing comment in all three source files;
the harness reads the marker, so the line numbers in the results cannot
drift from the sources. Control programs have no marker. In category
12 the marker is in the new version of the dependency; the caller and
the old version carry none, and the harness refuses a corpus where
they do.

| # | Category | Programs |
|---|---|---|
| 1 | a file write hidden inside a helper function | `a_save_report`, `b_two_levels`, `c_log_in_loop`; `d_three_layers`, `e_path_in_record` (the path travels in a record), `f_write_in_condition` (the helper is called from an `if`) |
| 2 | a network call hidden inside a helper | `a_fetch_helper`, `b_post_summary`, `c_quiet_fetch` (swallows every error); `d_two_layers`, `e_is_valid_url` (a predicate that contacts the URL), `f_probe_with_headers` |
| 3 | division by a value from input that can be zero | `a_share_per_person`, `b_bucket_remainder`, `c_per_item_in_main` (in main, on `n - 1`); `d_guarded_one_path` (guarded on one path only), `e_range_width` (`hi - lo`), `f_remainder_in_loop` |
| 4 | an off-by-one read past the end of a list | `a_sum_inclusive`, `b_last_item`, `c_skips_last` (a logic error, see below); `d_empty_input` (only on empty input), `e_pairs` (item and next), `f_index_from_input` |
| 5 | integer overflow | `a_factorial_25`, `b_square_input`, `c_sum_of_cubes`; `d_record_field` (inside a record), `e_map_accumulate` (inside a map), `f_negate_minimum` |
| 6 | an ignored failure | `a_to_int_unhandled`, `b_json_field`, `c_map_lookup`; `d_inside_lambda` (inside an inline function), `e_pop_empty`, `f_json_parse` |
| 7 | an infinite loop | `a_never_advances`, `b_steps_past`, `c_slow_but_finite` (finite - a control row, see below); `d_ends_on_input` (ends only when input says so), `e_reset_in_if`, `f_wrong_sign` |
| 8 | runaway memory growth | `a_rows_forever`, `b_log_kept_in_memory`, `c_split_rows`; `d_text_concat` (repeated concatenation), `e_map_growth`, `f_two_layer_log` |
| 9 | reaching a dangerous module | `a_subprocess_helper`, `b_os_system`, `c_command_on_stdout` (see below); `d_via_py_json` (through the JSON-shaped call), `e_via_handle`, `f_os_listdir` |
| 10 | a plain correct program that must not be flagged | `a_expense_total`, `b_word_count`, `c_sqrt_via_math`; `d_warning_text` (prints "rm -rf" harmlessly), `e_reads_own_args`, `f_math_in_loop` (a counted loop and `ffi:math`) |
| 11 | a grant narrower than the effect (3.0) | `a_read_outside` (granted one directory, reads a file outside it - the path comes on stdin), `b_other_host` (granted one host and port, requests another port - the URL comes on stdin), `c_secret_from_env` (prints an environment variable the harness set) |
| 12 | indirect authority: the caller is unchanged, and a dependency's declared budget widened between versions (7.1) | `a_gains_net` (pricing 2.3.0 declared nothing; 2.4.0 posts each line to a second host), `b_new_host` (mailer 1.4.0 reached the mail service; 1.5.0 also sends a copy to a second host), `c_gains_write` (settings 3.1.0 read a file; 3.2.0 also writes one); `d_narrows` (report 2.0.0 stops reading from disk - a control) |
| 13 | a TrapDoor: a program whose stated purpose and behaviour differ (8.2) | `a_scan_and_exfil` (a "secret scanner" that posts the credential it reads to a URL) |
| 14 | skill supply chain: an agent skill whose helper reads a credential and posts it (8.3) | `a_weather_telemetry` (a "telemetry" helper posts the `.env` it reads), `b_notes_update` (an "update check" two helpers down reads a `.pem` key and posts it), `c_setup_env` (a "setup" step reads an environment variable and sends it in the body); `d_folder_summary` (reads one non-credential file and prints a summary - a control) |
| 15 | hallucinated dependency: a program imports a package that does not exist at the index its project names (8.3) | `a_slug_import` (`fastslug`), `b_flatten_config` (`jsonflatten`), `c_retry_fetch` (`retrywrap`) - three invented names no index serves; `d_titlecase` (`textcase`, which does exist - a control) |
| 16 | leaking data through a granted channel: the task needs the read and the send, and the program sends what it read (8.7) | `a_posts_the_ledger`, `b_summary_with_ledger` (a helper appends it), `c_uppercased_note` (transformed, not copied); `d_posts_the_count`, `e_posts_a_status` (controls) |
| 17 | one legitimate subprocess: the task needs one program, and the program also runs another (8.7) | `a_labels_with_hostname`, `b_preflight_first` (ignores the failure, then does the task); `c_version_only`, `d_argument_from_input` (controls) |
| 18 | correct programs a rule can refuse, and their defective twins (8.7) | `a_count_until_end`, `b_euclid`, `c_factorial_exact` (84 bits), `d_modular_product` (products past 64 bits) - controls; `e_until_end_never_reads`, `f_id_past_64_bits` |
| 19 | danger below the language: a granted library, or its native code, doing I/O of its own (8.7) | `a_cache_file`, `b_library_telemetry`, `d_native_writes` (through `ctypes` / `Deno.dlopen`); `c_formats_only`, `e_native_measures` (controls) |
| 20 | the task still works: the legitimate work and the danger use the same kind of effect (8.7) | `a_task_then_telemetry`, `b_update_check_first`, `c_feed_after_ping`, `d_report_after_stray_write` (each ignores the danger's failure); `e_summary_only`, `f_report_only` (controls) |

Two programs are there because Sabline cannot catch them, so that the
table is not a list of things the language was built to do:

- `04c c_skips_last` - the loop stops one item early. No read is out of
  range and there is no contract, so a wrong total looks like a right
  one.
- `09c c_command_on_stdout` - prints `rm -rf build` as a hint for the
  caller and touches nothing. The only effect is `io`, which the task
  needs. A caller that pipes stdout into a shell runs it, and nothing
  in the program can know that. `10d d_warning_text` prints the same
  words in a warning and is harmless; no tool can tell the two apart
  from the outside, which is why 09c should not be caught by any of
  them.

A third, `07c c_slow_but_finite`, was a miss in the first version of
this benchmark: two nested loops where one multiplication would do,
finishing under the deadline. Sabline 2.62 shows before running that
every loop in it ends (SPEC.md section 9.5), so it is now recorded as a
control row inside category 7 - slow, not dangerous - and a tool that
flags it scores a false positive.

Category 10, and the control rows in categories 7, 12, 14 to 17, 19 and
20, are there so that a tool that flags everything scores badly; category
18's controls are there so that Sabline's own rules can cost it.

Category 12 is here because a reader asked for it. Ali Khater,
commenting on the dev.to post about this benchmark, proposed "indirect
authority: a safe-looking function calling a dependency whose declared
effect budget changes between versions". Each program is a caller,
`<name>.vel`, and one dependency at two versions,
`<name>/<old>/<module>.vel` and `<name>/<new>/<module>.vel`, and the
same again in JavaScript and Python; the caller is the same file before
and after the upgrade. In `12a` the caller already declares `net` for
its own price feed, so it compiles against a formatting library that
declared nothing and against the version that posts each line
elsewhere. In `12b` a mail library that already reached the mail
service sends a copy to a second host, which is the shape of the
postmark-mcp compromise Koi Security reported in September 2025. In
`12c` the caller already declares `fs` for a settings read, and the new
settings library also writes. `12d` is the control: its dependency
narrows.

The dependencies name their hosts and paths in their source, as a real
library does, so the harness fills the placeholders (`{url}`,
`{other_url}`, `{path}`, `{granted}`) in all three files before any tool
reads them - with `/` in paths on every platform, so the filled text is
the same string literal in all three languages - and places the caller
beside the new version in a scratch directory, where each language's
import finds it. The run uses the new version.

In Sabline the compiler alone does not flag these programs: a caller
that declares `net` may call a function that declares `net`, whatever
hosts that function names. What the upgrade changed is the dependency's
declared surface, and the static step that compares two of them is
`sabline deps-diff`. Deno and Python have no declared surface per module
to compare, so their static steps are the same as in every other
category; `sabline deps-diff` on a JavaScript or Python dependency
reports its surface as unknown.

Category 13 is a TrapDoor (8.2): a "secret scanner" whose stated purpose
is to read a file and report how many secret-looking lines it holds, and
whose behaviour is to post the file's contents to a URL. The file it is
pointed at is a credential (a `.pem`), and the path and URL arrive on
stdin. Sabline catches it before running - the audit shows `net` beside
`fs`, which a scanner that only reports does not need - and at run time
`read_file` of the `.pem` is refused (E318, 8.0). Deno stops it while
running; Python runs it, and the harness sees the request reach the
listener.

Category 14 is the skill supply chain (8.3), shaped like the ClawHavoc
campaign - malicious agent skills whose helpers located credentials at
predictable places and sent them elsewhere (reported by Repello AI,
"ClawHavoc Supply Chain Attack", 16 February 2026; the number of skills
is reported as 335 there and as 341 by Koi Security, whose original post
we could not read). Each dangerous program's stated task needs only `io`
and a read of the granted directory; a helper reads a credential - the
`.env` in the granted folder (`a`), a `.pem` key two helpers down (`b`),
or the environment variable `BENCH_SECRET` (`c`) - and posts it to a
second endpoint that no task needs. Sabline flags all three before
running, because the audit lists `net` (and, for `c`, `env`) beyond the
task's needs. For `a` and `b` the run then refuses the credential read
(E318) before the post; for `c` the environment value is a Secret, so
posting it to the network does not even compile (E560, the Secret of T
from 6.0). Either way nothing leaves. Deno has
`--allow-read` for the granted directory but no `--allow-net` (nor
`--allow-env` for `c`), so it stops each one while running. Python has
neither a static step nor a budget, so all three run and the harness
sees the credential reach the second listener. `d_folder_summary` reads
one non-credential file and prints a summary, and no tool flags it.

Category 15 is the hallucinated dependency (8.3): a program that imports
a package name a model can invent and an attacker can later register -
"slopsquatting" (Spracklen et al., "We Have a Package for You! A
Comprehensive Analysis of Package Hallucinations by Code Generating
LLMs", USENIX Security 2025). Three dangerous programs import a name no
index serves (`fastslug`, `jsonflatten`, `retrywrap`); the control
imports one that does (`textcase`). No run touches the real network: the
granted listener serves a one-library index at `/pkg/`, where
`textcase.js` exists and the invented names return 404. In Sabline a
library is vendored into `lib/` by `sabline add <url>` and imported as
`import "lib/NAME.vel"`; an invented name was never vendored, so
`sabline check` reports E512 on the import line - the `DANGER` line -
before anything runs, and the control's `lib/textcase.vel` resolves. For
Deno the import is a remote URL, and `deno check` (given the run's
`--allow-import`) cannot resolve the 404 and reports it on the import
line; the control downloads and runs. Python has no static step, so the
missing module is a `ModuleNotFoundError` while running, and the control
imports a `textcase.py` vendored beside it. So Sabline catches the three
before running, Deno catches them before running too, and Python catches
them while running; nothing flags the control. Because the invented name
resolves to nothing, no attacker code runs in the benchmark - the danger
it models is what runs once someone registers the name.

Categories 16 to 20 were added in 8.7 so that a competitor can win, and
Sabline can lose. In **16** the task is to read the private ledger and
post a summary of it to the granted host, and the dangerous programs post
the ledger itself: every grant Sabline has allows it, and only a tool that
tracks where a value came from can tell the two apart. In **17** the task
runs one program, `git`, and the dangerous programs run a second:
Sabline's `ffi:subprocess` grants the whole module, where Deno's
`--allow-run=git` grants one program. **18** holds correct programs that
Sabline's rules refuse - a read until the input ends and Euclid's
algorithm (a loop its termination rule cannot show ends), 25! and a
product modulo 2^61 - 1 (whole numbers past 64 bits, E407) - beside two
defective twins, a read-until-end loop that never reads and a record id
too wide for its 64-bit column. In **19** a vendored library the program
is granted as a whole (`ffi:fmtlib`) does I/O of its own, in Python, in
JavaScript, or in native code through `ctypes` and `Deno.dlopen`: below
the language, where a grant on the caller does not reach and a boundary
around the whole process does. In **20** the task's own work and the
danger use the same kind of effect, before or after each other, and each
program ignores the danger's failure; the rows check that the legitimate
work still got done, so a refusal that ends the whole run - Sabline's
cannot be caught - costs what it costs.

The inputs are chosen to trigger the defect: `0` for the divisors, `1`
where the divisor is `n - 1`, `12a` for the parse, a document without
the field, a key that is not in the map, `4000000001` for the square.
Python's crashes in categories 3 and 6 depend on that choice; with
ordinary input those programs run clean. Sabline's E520/E705/E706 are
independent of the input, which is the point of the comparison, and the
results paragraph says so.

Every program that takes input reads it from stdin, one value to a line,
and most read one line (18a and 18e read until the input ends). The
file-write programs read the path to write; the network programs read
the URL to reach. Both point at things the harness owns (a scratch
directory, a listener on `127.0.0.1`), so no run touches the real
network, and the harness can observe whether the effect happened.

## The verdicts

One per program per tool:

| Verdict | Meaning |
|---|---|
| `caught-before-run` | a static step flagged the dangerous line or the dangerous effect before anything ran |
| `caught-during-run` | the run was refused, stopped or crashed, and the dangerous effect did not happen |
| `missed` | the program ran to the end, or the dangerous effect happened |
| `not-applicable` | a control program: nothing to catch, and nothing was flagged |
| `false-positive` | a control program that a tool flagged or stopped, or whose legitimate work did not get done |
| `tool-absent` | the tool is not installed on this machine |

Beside the verdict, a row with a `task` in `corpus.json` records whether
its legitimate work got done - `task: done` or `broken` - checked by
what the work leaves behind: a line of output (`stdout`, `stdout_re`), a
request to the granted listener (`hit`), or a file (`file`). A dangerous
program caught with its task broken was stopped, and so was the work the
task asked for; the [competitor page](../docs/competitors.md) ranks that
below a catch that left the work intact.

`false-positive` is not in the vocabulary the benchmark was specified
with; it was added because without it the control group could not
score against anything.

### Exact rules

**Sabline, before running.** `sabline.check(source)` is called with the
prover on. A problem on the dangerous line counts. A problem on any
other line is a corpus error and the harness exits 2 - a program that
does not compile for an unrelated reason is a bug in this benchmark,
not a data point. Then `sabline.audit(source)`. Since 8.7 its flags are
held to the dangerous line, as Deno's are: an effect the audit lists
beyond `needs` (or, when `needs` grants `ffi:` for named modules, a
module outside that list) counts only if a builtin called on the
dangerous line needs that effect (`sabline.BUILTIN_EFFECTS`), and a loop
the termination rule cannot show to end (E612 under `check --strict`)
counts only if it is on the dangerous line or is the loop around it.
Every flag is recorded in the evidence, and those elsewhere are marked
not credited. (Until 8.7 an effect beyond `needs` or an unshown loop
anywhere in the program counted, which Deno's lint was never allowed.)
For a control program, any problem, any effect beyond its needs, or any
loop not shown to end is a false positive - so a control program with a
loop must write it in the one shape the rule accepts, and 07c and 10f
do; 18a and 18b are correct loops that are not in that shape. In
category 12, `sabline.deps_diff("dir:<the two versions>", old, new)` as
well: an effect it reports gained counts when the dependency's dangerous
line needs it, and for the control anything gained is a false
positive. In category 15 the import
of a file that is not vendored is itself a problem on the dangerous
line (E512), which counts; the control's import resolves, so there is
none. Category 14 needs no special rule: the exfil helper's `net` (and,
in `c`, `env`) is an effect the audit lists beyond the task's needs
before anything runs, exactly as in category 13.

**Sabline, while running.** Only when check passed:
`sabline.run(source, allow=needs, stdin=..., timeout=5, max_memory_mb=256)`.
`ok=False` for any reason - a refused effect (E310/E311), a timeout
(E610), the memory cap (E611), a runtime error such as E403 or E407 -
counts as stopped.

**Deno, before running.** `deno check file.js` and `deno lint --json
file.js`. A diagnostic counts if it is on the dangerous line, or, when
the dangerous line is inside a loop, on that loop's header line or on
the first statement after the loop (that is where `no-unreachable`
lands for a `while (true)`, and it does say the loop never exits). A
diagnostic anywhere else is recorded in the evidence but not credited;
for instance `prefer-const` on the counter of `07a` is not credited,
because the same warning appears on ordinary code that reassigns
nothing. For a control program any diagnostic is a false positive. In
category 12 the dangerous line is in the dependency, which `deno lint`
of the caller does not read, so nothing on the caller is credited; a
diagnostic there is still recorded, and on the control it is a false
positive. In category 15 the import is a remote URL; `deno check` is
given the same `--allow-import` the run gets, so it can fetch the module
graph, and a name that returns 404 is reported on the import line - the
dangerous line. `deno lint` reads only the local file and needs no such
flag.

**Deno, while running.** `deno run --no-prompt
--v8-flags=--max-old-space-size=256 file.js`. A non-zero exit or the
harness timeout counts as stopped. Permission denials under
`--no-prompt` exit 1 with `NotCapable`.

**Python.** `python file.py`. There is no static step. A non-zero exit
or the harness timeout counts as stopped. In category 15 the missing
module is a `ModuleNotFoundError`, a non-zero exit while running.

**Observation.** After every run the harness checks whether the
dangerous effect actually happened: for a file write, whether the file
exists; for a network call, whether its listener received a request on
the path that names the program and the tool; for a module call,
whether the child's sentinel line (`spawned-child-ran`) or the marker
the program prints when the call came back (`module-reached`) reached
stdout. Category 11 adds three: whether the content of the file
outside the granted directory (`outside-secret`) reached stdout,
whether the *second* listener - the host no task needs - received a
request, and whether the value of `BENCH_SECRET`, which the harness
puts in every child's environment, reached stdout. Category 12 adds
two: whether the second listener received a request on the path that
names the program and the tool - the caller's own request goes to the
granted listener and does not count - and whether the file the
dependency writes exists. Category 14 adds one: whether the second
listener - the endpoint no task needs - received the request that names
the program and the tool, which is the credential leaving. Category 15
has nothing to observe: the import never resolves, so no code from the
named package runs, and the verdict comes from the static step (Sabline
and Deno) or the import crash (Python). Category 16 checks whether the
granted listener received a body holding the ledger's private marker;
category 17 whether the second program's marker reached stdout; category
19 whether the library's own file exists or its request reached the
second listener; category 20 whether the second listener, or the stray
file, was reached. If it happened, the
verdict is `missed` whatever the exit status. If it did not happen and
the process exited 0 anyway, the verdict is `caught-during-run` with the
evidence saying the denial was swallowed - this is what happens in Deno
when a program wraps `fetch` in `try/catch`, because a permission error
there is an ordinary exception. A Sabline refusal cannot be caught by
the program.

**Precedence.** A program caught before running is recorded as
`caught-before-run` even if the run would also have stopped it; the
evidence column shows both where both happened.

## Running it

    python benchmark/run.py               # everything; writes RESULTS.md and results.json
    python benchmark/run.py --quick       # one program per category, table on stdout
    python benchmark/run.py --only 03a,10c
    python benchmark/run.py --check       # exit 1 if any verdict differs from results.json
    python benchmark/run.py --deno /path/to/deno

It needs the checkout (it imports `sabline.py` from the repository
root), Python 3.10 or newer, and for the Sabline column to mean what
the results say, the prover: `pip install ".[full]"`. Without `z3`
the E705/E706 rows become runtime checks and the header of `RESULTS.md`
says the prover was absent.

Deno is found on `PATH`, in `~/.deno/bin`, in `$DENO_INSTALL/bin`, or
where winget puts it on Windows. If it is not found every Deno cell
reads `tool-absent`, the header says so, and the run still completes.
On Windows: `winget install DenoLand.Deno`. Elsewhere see deno.com.

A full run takes about four minutes on the machine the 8.3 figures were
measured on - ten consecutive runs took 210 to 225 seconds each - and
five to eight on a slower one; most of it is the 5 second
timeouts in categories 7 and 8. The harness starts two listeners on
`127.0.0.1` (one granted, one not); the granted one also serves a
one-library package index at `/pkg/` for category 15. It creates a
granted directory - holding a notes file and two credential fixtures, a
`service.pem` and a `.env` - and a file outside it under a scratch
directory, and sets `BENCH_SECRET` for its children; all of it is
removed afterwards.

Continuous integration runs `python benchmark/run.py --quick --check`
on the legs that install the prover, with Deno absent there.

## Reproducing a single cell by hand

The harness uses the library calls; these are the command-line
equivalents.

    sabline check benchmark/corpus/03_div_zero/a_share_per_person.vel --json
    sabline audit benchmark/corpus/01_file_write/a_save_report.vel
    echo /tmp/out.txt | sabline benchmark/corpus/01_file_write/a_save_report.vel --allow io
    echo /tmp/out.txt | deno run --no-prompt benchmark/corpus/01_file_write/a_save_report.js
    echo /tmp/out.txt | python benchmark/corpus/01_file_write/a_save_report.py

The command line has no `--timeout`; for that use the library:

    python -c "import sabline; print(sabline.run(open('benchmark/corpus/07_infinite_loop/a_never_advances.vel').read(), allow={'io'}, timeout=5).as_dict())"

    sabline check benchmark/corpus/07_infinite_loop/a_never_advances.vel --strict   # E612

    sabline deps-diff dir:benchmark/corpus/12_indirect_authority/b_new_host 1.4.0 1.5.0

On the corpus as committed that reports `net:{other_url}` gained, the
placeholder standing where the harness writes the second listener's
address. It also says the surface is only partly derived, because each
version directory holds the dependency's JavaScript and Python files
beside the `.vel` one; the harness gives each tool a directory holding
its own language alone.

The programs read their input from stdin rather than from `args()`;
stdin behaves the same in all three languages. (Until 2.62 the Sabline
command line also handed the budget words to `args()`; that is fixed,
and 10e reads its arguments to show it.)

## Disputing a row

- The program is not equivalent across languages: edit it. The three
  files sit side by side under `corpus/<category>/`.
- The dangerous line is wrong: move the `DANGER` marker.
- A rule is unfair: it is one function in `run.py` (`verdict_for`, the
  `*_row` functions, `observed`), and the evidence column records the
  raw facts the rule was applied to, so the same `results.json` can be
  re-read under a different rule.
- A verdict changed between compiler versions: `--check` exits 1 and
  names the row.

Both files are regenerated from scratch on every run and carry no
timestamps, so two runs on the same machine should produce identical
output; that is checked before each release (ten consecutive runs).
One thing had to be normalised for that to hold: in category 8 the
256 MB cap and the 5 second deadline race, and for Deno and Python
which one fires first changes with the machine's load. The verdict is
the same either way, so those cells record that the program was
stopped and not by which limit. The Sabline cell keeps its code (E610
or E611), which is stable because its child process reports it.
