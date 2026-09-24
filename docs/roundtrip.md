# Model round trip

For each model, the same small tasks asked for twice - as a Sabline program, with the language card [LLM.md](../LLM.md) in the prompt, and as a Python program, with none - and each answer compiled, run, and checked by the same check in both languages. A failed answer goes back to the model with the toolchain's own message, for at most 6 rounds; a wrong answer is not sent back, so the feedback never carries the answer. This is [plan/8.7.md](../plan/8.7.md) section 2: the number that speaks to whether a model can write this language, beside the language models already write. The page is generated from `evals/roundtrip/results.json`, which `roundtrip_eval.py` re-derives from the recorded replies on every push, with no model and no key.

The tasks are in two sets, reported apart: the original 10, which the card was changed in answer to after the first recording, and 5 held out from that change - written and committed before it, by the person who then made it, so they are held out from the edit and not from its author. A row is one recording: a model, the card it was given and the task set it was asked, each named by the first eight hex digits of its SHA-256. The current card is `221344ba` and the current task set `297f3d34`; a recording is scored on the tasks it was asked, by today's checks.

> [!NOTE]
> **Scored** on Linux x86_64, Python 3.12, Sabline 8.6.0. Each row gives the model's exact version and the date its replies were recorded; a recording more than 183 days old is marked **stale** when this page is built, and its numbers are not carried to a newer version of the model.

## The numbers

### The original ten tasks

Tasks that work on the first answer / within 6 rounds, of 10, and how the rest ended.

| Model | Version | Card | Tasks | Recorded | Sabline: first / within | Python: first / within | Sabline wrong / gave up | Python wrong / gave up |
|---|---|---|---|---|---:|---:|---:|---:|
| `ollama:qwen2.5:7b` | `845dbda0ea48` | `221344ba` (current) | `5d8906d1` (earlier) | 2026-09-23 | 6 / 7 | 9 / 9 | 1 / 2 | 1 / 0 |

### The held-out tasks

No recording has been asked these tasks yet.

### Every failed attempt, by what went wrong

Did not compile (with the compiler's code, or Python's exception), refused by the budget (Sabline only: Python has no budget), crashed while running, timed out, or ran and printed the wrong thing. Only the first is about the language's syntax.

| Model | Card | Set | Language | Failed attempts |
|---|---|---|---|---|
| `ollama:qwen2.5:7b` | `221344ba` | original | sabline | did-not-compile E101 x12, did-not-compile E513 x2, wrong x1 |
| `ollama:qwen2.5:7b` | `221344ba` | original | python | wrong x1 |

### Every task

Each cell is the attempts in order, ending at the first that worked or printed the wrong thing. A task a recording was not asked is left out of its table.

**`ollama:qwen2.5:7b`, card `221344ba`, tasks `5d8906d1`**

| Task | Set | Sabline | Python |
|---|---|---|---|
| sum | original | wrong output | works |
| parse | original | did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) | works |
| larger | original | did not compile (E513) → did not compile (E513) → works | works |
| write | original | works | works |
| fetch | original | works | works |
| evens | original | works | works |
| split_bill | original | did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) | wrong output |
| points | original | works | works |
| home_set | original | works | works |
| positive | original | works | works |

## What the full set would cost

The models the harness is ready to ask, at the prices their vendors published (read 2026-09-23: [anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [openai](https://developers.openai.com/api/docs/pricing), [google](https://ai.google.dev/gemini-api/docs/pricing)). The **ceiling** holds whatever a model says: every task runs all 6 rounds in both languages, every reply is 4000 tokens (the harness's maximum), every message counted at 3 characters a token, with Anthropic's newer tokenizer counted 30% heavier. The **estimate** is what the recorded models actually sent and received (, about 0.0 calls a model), at 4 characters a token. No prompt cache and no batch discount, both of which would lower it.

| Model | Input $/MTok | Output $/MTok | Ceiling | Estimate |
|---|---:|---:|---:|---:|
| `anthropic:claude-fable-5-1` | 10.00 | 50.00 | $71.39 | $0.00 |
| `anthropic:claude-opus-5-5` | 4.00 | 20.00 | $28.56 | $0.00 |
| `anthropic:claude-sonnet-5` | 2.00 | 10.00 | $14.28 | $0.00 |
| `anthropic:claude-haiku-4-5-20251001` | 1.00 | 5.00 | $6.74 | $0.00 |
| `openai:gpt-6-astra` | 10.00 | 50.00 | $67.38 | $0.00 |
| `openai:gpt-6-sol` | 2.00 | 10.00 | $13.48 | $0.00 |
| `openai:gpt-6-luna` | 0.10 | 0.50 | $0.67 | $0.00 |
| `gemini:gemini-3.1-pro-preview` | 2.00 | 12.00 | $14.92 | $0.00 |
| `gemini:gemini-3.8-flash` | 0.75 | 3.75 | $5.05 | $0.00 |
| **All of them** | | | **$222.47** | **$0.00** |

What costs nothing: any model that runs locally (the rows above, through Ollama), and the free tiers some vendors list - Google lists one for several Gemini models - which need that vendor's key, and which this project does not hold. A local model is free in money and not in time: a model that reasons at length before it answers takes minutes a call on a small graphics card.

## What it does not show

- **The models on this page are the free ones.** Every row is a model that runs locally for nothing; none of the priced models has been asked. Small quantized models are weaker than the models an agent is usually built on, at both languages, so the gap between the two columns is the thing to read, not either column.
- **One sample, at temperature 0.** A model is asked once per task and language. A different seed, or a remote model's own nondeterminism, would give different replies; the recording is what was actually said. A changed card changes every prompt, so every answer can change with it: a difference of one task between two rows is noise, not a finding.
- **Small tasks written by this project**: the ten `agent_loop.py --metric` already had, and the held-out set. They are not a benchmark of programming ability, and a task that exercises what Sabline refuses (a budget, a Secret) is harder in Sabline by design. The held-out tasks are held out from a card change, not from the person who wrote both.
- **Sabline gets a card and Python does not.** A model has read Python; it has not read Sabline. The card is the documentation a model is meant to be given, and it is what the premise is about.

## Reproducing it

    python roundtrip_eval.py --check                   # re-derive every verdict, no model
    python roundtrip_eval.py --live ollama:qwen3:4b    # ask a local model, free
    python roundtrip_eval.py --live anthropic:claude-sonnet-5   # needs your key; costs money

The recordings, one file per model, card and task set, are in [evals/roundtrip/recordings](https://github.com/gowrishankar-infra/sabline-lang/tree/main/evals/roundtrip/recordings), with every reply, the feedback it got and the tokens it used.
