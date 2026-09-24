# The model round trip, against Python

`plan/8.7.md` section 2: for each model, how often a program it writes in
Sabline actually works, beside how often the same model's program for the
same task in Python works. The published numbers are on
[/roundtrip.html](https://sabline.dev/roundtrip.html).

    python roundtrip_eval.py --check              # re-derive every verdict; what CI runs
    python roundtrip_eval.py --record             # re-derive, and rewrite results.json and the page
    python roundtrip_eval.py --self-test          # show --check failing when a verdict moves
    python roundtrip_eval.py --live ollama:qwen2.5:7b          # ask a local model: free
    python roundtrip_eval.py --live anthropic:claude-sonnet-5  # ask a hosted one: your key, your money

## What is here

    tasks.json        the tasks, in two sets: the original ten -
                      agent_loop.py --metric's, made checkable offline - and
                      five held out, written before the card was changed in
                      answer to the first recording; each with the budget a
                      Sabline run gets, its input, and one check applied to
                      both languages, and `more` for a task run again on a
                      further input
    recordings/       one file per model, card and task set, named
                      MODEL.card-XXXXXXXX.tasks-YYYYYYYY.json from the first
                      eight hex digits of LLM.md's and tasks.json's SHA-256
                      (line ends as LF): every reply the model gave, in
                      order, with the feedback it was given after each, the
                      tokens and seconds each call took, its exact version,
                      the options it was asked with, and the date. Asking
                      again after the card or the tasks changed adds a file,
                      and asking again with neither changed adds a second
                      run (.run-2.json): none is ever replaced, and a local
                      model at temperature 0 does not answer the card's long
                      prompt the same way twice
    results.json      every attempt re-derived from the recordings: its
                      class, its code, the command, the exit status, what it
                      printed; the per-model summaries; and the cost
    prices.json       the vendors' published prices, with where and when they
                      were read, for the cost figure

## The rules

- **The same task, the same check, both languages.** The Sabline prompt
  carries the language card, `LLM.md`, and says how the program will be run
  (`sabline program.vel --allow <budget>`); the Python prompt says `python
  program.py`, standard library only. Nothing else differs.
- **Compiled, run, checked.** Sabline: `sabline check`, then the run under the
  task's budget. A task with `more` is run again on each further input and
  works only if every run passes its check; a run after the first that
  fails tells the model the input it was given, never what it should have
  printed. Python: `python -I -S -m py_compile`, then `python -I -S`
  (isolated, no site-packages, so no machine's installed packages decide a
  verdict). Each run gets 20 s, its own directory, a local listener for the
  one task that fetches, and a HOME the check can look for.
- **Feedback is the toolchain's own words, and never the answer.** A program
  that does not compile, is refused, crashes or times out goes back with the
  compiler's errors, the refusal, the runtime error or the traceback (at
  most 2,000 characters), for at most six rounds. A program that runs and
  prints the wrong thing ends the conversation: telling the model why would
  be telling it the answer.
- **The program is the reply's first code block**, as `agent_loop.py`
  takes it; a reply that gives two (a program, then "the corrected
  code") is held to the first. In the recorded replies, taking the last
  instead would have compiled the same way every time.
- **Four ways to fail, kept apart**: did not compile, refused by the budget
  (Sabline only; Python has no budget), crashed while running, or wrong
  output - with a timeout as a crash that did not end.
- **Per model, never pooled**, each with its exact version: a local model's
  digest, or the model string a hosted API returns. A row is one recording,
  so one model asked with two cards is two rows, and each says which card
  and which task set it was asked.
- **Two sets, reported apart.** The held-out tasks were written and
  committed before the card was changed in answer to the first recording,
  by the person who then changed it: they are held out from the edit, not
  from its author. A recording is scored on the tasks it was asked, by
  today's checks; one made before a task existed is not scored on it.
- **One sample per task and language**, at temperature 0 where the
  provider takes one, with a fixed seed for a local model.
- **Stale after six months.** The page marks a recording older than 183
  days when it is built, and a result is never carried to a newer version
  of the model.

## What costs money, and what does not

`--live` is off by default and refuses to run under CI. A local model
through Ollama costs nothing; a hosted model costs what its vendor charges,
and nothing here holds a key. The committed numbers are re-derived from the
recordings by `--check` with no model, no key and no network, so a reader
can re-run the scoring without paying for anything; re-running a model is
`--live` with their own key, and a hosted model's replies will differ from
run to run, which is why the recording, not the number, is the evidence.

The page publishes what a full run of every model in `prices.json` would
cost: a ceiling that holds whatever the models say (every task, every
round, every reply at the 4,000-token maximum), and an estimate from what
the recorded models actually used.
