# Model round trip

For each model, the same ten small tasks asked for twice - as a Sabline program, with the language card [LLM.md](../LLM.md) in the prompt, and as a Python program, with none - and each answer compiled, run, and checked by the same check in both languages. A failed answer goes back to the model with the toolchain's own message, for at most 6 rounds; a wrong answer is not sent back, so the feedback never carries the answer. This is [plan/8.7.md](../plan/8.7.md) section 2: the number that speaks to whether a model can write this language, beside the language models already write. The page is generated from `evals/roundtrip/results.json`, which `roundtrip_eval.py` re-derives from the recorded replies on every push, with no model and no key.

> [!NOTE]
> **Scored** on Linux x86_64, Python 3.12, Sabline 8.6.0. Each model's row gives its exact version and the date its replies were recorded; a recording more than 183 days old is marked **stale** when this page is built, and its numbers are not carried to a newer version of the model.

## The numbers

Tasks that work on the first answer / within 6 rounds, of 10, and how the rest ended.

| Model | Version | Recorded | Sabline: first / within | Python: first / within | Sabline wrong / gave up | Python wrong / gave up |
|---|---|---|---:|---:|---:|---:|
| `ollama:qwen2.5:7b` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | 2026-09-23 | 6 / 7 | 9 / 9 | 1 / 2 | 1 / 0 |

### Every failed attempt, by what went wrong

Did not compile (with the compiler's code, or Python's exception), refused by the budget (Sabline only: Python has no budget), crashed while running, timed out, or ran and printed the wrong thing. Only the first is about the language's syntax.

| Model | Language | Failed attempts |
|---|---|---|
| `ollama:qwen2.5:7b` | sabline | did-not-compile E101 x12, did-not-compile E513 x2, wrong x1 |
| `ollama:qwen2.5:7b` | python | wrong x1 |

### Every task

Each cell is the attempts in order, ending at the first that worked or printed the wrong thing.

**`ollama:qwen2.5:7b`**

| Task | Sabline | Python |
|---|---|---|
| sum | wrong output | works |
| parse | did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) | works |
| larger | did not compile (E513) → did not compile (E513) → works | works |
| write | works | works |
| fetch | works | works |
| evens | works | works |
| split_bill | did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) → did not compile (E101) | wrong output |
| points | works | works |
| home_set | works | works |
| positive | works | works |

## What the full set would cost

The models the harness is ready to ask, at the prices their vendors published (read 2026-09-23: [anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [openai](https://developers.openai.com/api/docs/pricing), [google](https://ai.google.dev/gemini-api/docs/pricing)). The **ceiling** holds whatever a model says: every task runs all 6 rounds in both languages, every reply is 4000 tokens (the harness's maximum), every message counted at 3 characters a token, with Anthropic's newer tokenizer counted 30% heavier. The **estimate** is what the recorded models actually sent and received (`ollama:qwen2.5:7b`, about 32.0 calls a model), at 4 characters a token. No prompt cache and no batch discount, both of which would lower it.

| Model | Input $/MTok | Output $/MTok | Ceiling | Estimate |
|---|---:|---:|---:|---:|
| `anthropic:claude-fable-5-1` | 10.00 | 50.00 | $47.60 | $2.77 |
| `anthropic:claude-opus-5-5` | 4.00 | 20.00 | $19.04 | $1.11 |
| `anthropic:claude-sonnet-5` | 2.00 | 10.00 | $9.52 | $0.55 |
| `anthropic:claude-haiku-4-5-20251001` | 1.00 | 5.00 | $4.49 | $0.21 |
| `openai:gpt-6-astra` | 10.00 | 50.00 | $44.92 | $2.13 |
| `openai:gpt-6-sol` | 2.00 | 10.00 | $8.98 | $0.43 |
| `openai:gpt-6-luna` | 0.10 | 0.50 | $0.45 | $0.02 |
| `gemini:gemini-3.1-pro-preview` | 2.00 | 12.00 | $9.94 | $0.44 |
| `gemini:gemini-3.8-flash` | 0.75 | 3.75 | $3.37 | $0.16 |
| **All of them** | | | **$148.31** | **$7.82** |

What costs nothing: any model that runs locally (the rows above, through Ollama), and the free tiers some vendors list - Google lists one for several Gemini models - which need that vendor's key, and which this project does not hold. A local model is free in money and not in time: a model that reasons at length before it answers takes minutes a call on a small graphics card.

## What it does not show

- **The models on this page are the free ones.** Every row is a model that runs locally for nothing; none of the priced models has been asked. Small quantized models are weaker than the models an agent is usually built on, at both languages, so the gap between the two columns is the thing to read, not either column.
- **One sample, at temperature 0.** A model is asked once per task and language. A different seed, or a remote model's own nondeterminism, would give different replies; the recording is what was actually said.
- **Ten small tasks**, the ones `agent_loop.py --metric` already had, written by this project. They are not a benchmark of programming ability, and a task that exercises what Sabline refuses (a budget, a Secret) is harder in Sabline by design.
- **Sabline gets a card and Python does not.** A model has read Python; it has not read Sabline. The card is the documentation a model is meant to be given, and it is what the premise is about.

## Reproducing it

    python roundtrip_eval.py --check                   # re-derive every verdict, no model
    python roundtrip_eval.py --live ollama:qwen3:4b    # ask a local model, free
    python roundtrip_eval.py --live anthropic:claude-sonnet-5   # needs your key; costs money

The recordings, one file per model, are in [evals/roundtrip/recordings](https://github.com/gowrishankar-infra/sabline-lang/tree/main/evals/roundtrip/recordings), with every reply, the feedback it got and the tokens it used.
