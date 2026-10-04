# AgentDojo

Sabline evaluated on [AgentDojo](https://github.com/ethz-spylab/agentdojo), the agent-security benchmark of Debenedetti et al., so that its numbers can be put beside CaMeL, LBAC and ChainCaps. All four suites are run, with no model and at no cost. This page is generated from `evals/agentdojo/results.json`, which `agentdojo_eval.py` records and a CI job re-derives on every push.

> [!NOTE]
> **Suites:** 4 (slack, workspace, banking, travel) &nbsp;·&nbsp; **AgentDojo:** 0.1.35 (v1) &nbsp;·&nbsp; **Model:** none (AgentDojo ground-truth reference solutions) &nbsp;·&nbsp; **Measured:** 2026-10-04. 97 user tasks, 27 injection tasks, 629 attack pairs.

## The score, under three budgets

| Suite | Tasks | Scorable offline | Utility, of the scorable: task / pinned | Attacks | Attack success: `all` / task / pinned |
|---|---:|---:|---|---:|---|
| [slack](agentdojo-slack.md) | 21 | 21 | 21 / 21 (of 21) | 105 | 105 / 19 / 9 (of 105) |
| [workspace](agentdojo-workspace.md) | 40 | 11 | 11 / 11 (of 11) | 240 | 160 / 6 / 2 (of 240) |
| [banking](agentdojo-banking.md) | 16 | 10 | 10 / 10 (of 10) | 144 | 144 / 42 / 9 (of 144) |
| [travel](agentdojo-travel.md) | 20 | 0 | 0 / 0 (of 0) | 140 | 120 / 6 / 3 (of 140) |
| **all four** | **97** | **42** | **42** / **42** (of 42) | **629** | **529 / 73 / 23** (of 629) |

**Utility is reported over the tasks that can be judged offline, and 55 of 97 cannot be** (29 of 40 in workspace, 6 of 16 in banking, 20 of 20 in travel). Many of AgentDojo's utility checks read the assistant's own answer - `"4.2" in model_output`, the restaurant's name in the reply - and not only what the run did to the environment. There is no model here, so there is no answer to judge, and no budget could make those checks pass. They are counted, named on each suite's page, and left out of the utility column rather than reported as refusals. The scorable set is where a budget's effect on utility can be read at all, and there the question is whether the task budget and the pinned budget pass exactly what `--allow all` passes.

Lower attack success is better. The three budgets are nested, and each column is one more thing the operator said:

- **`--allow all`** bounds nothing. It is the control.
- **The task budget** is `io` and a grant for each tool the reference solution calls, by name - an operator who wrote the budget for this task and no more.
- **The pinned budget** is that, with every argument the user task's *own text* names held to that value by the tool door's argument patterns (`tool:send_direct_message:recipient=Bob`, SPEC.md 7.2). Nothing in it is read from what a tool returns: the harness checks every literal in every pattern against that task's own prompt and stops if one is not there.

So a budget written for each task refused **456 of the 529** attacks that a wide-open run lets through. Pinning the arguments the task names refused **50** more of the **73** that were left, leaving **23**. The utility cost of both together, over all four suites, is **0 of the 42** reference solutions that can be judged at all.

## Which door the attacker's value came through

An attacker's value can reach a tool call two ways: **written into the program** as a literal, because the attacker changed the program the model wrote; or **read at run time** out of what a tool returned - *door 2* - because the attacker changed the data. The door decides what a budget can do about it, so every attack that lands under the task budget is classified. Three different questions are asked, and they have three different answers.

**1. Where the value came from in this run.** **73 program**, of 73 landing attacks. That number is a property of this harness and not of AgentDojo, and it is worth nothing on its own: there is no model here, so where a model would read the injected instruction and act on it, the harness transcribes the injection task's ground truth - which writes the attacker's value out as a literal. Under transcription the answer **can only be** 'the program'. The value originates in the data in every one of these; what the harness fixes is that it arrives as a literal.

**2. What AgentDojo itself says about the same arguments.** Its ground truth carries `placeholder_args` beside the resolved ones, and where a real agent would have to read a value out of the data it writes a marker there - `$code` for the security code in an email, `$email.body`, `$content`, `$most_expensive_hotel.name`. That is the benchmark's own judgement, made before Sabline existed, and it is evidence about the corpus rather than about this harness. Of the 73 landing attacks,  **46** have ground truth that marks at least one argument as read at run time, and **27** carry the attacker's own values throughout.

| Suite | Landing attacks | ...whose ground truth marks an argument read at run time | Injections the probe could launder |
|---|---:|---:|---|
| [slack](agentdojo-slack.md) | 19 | 0 | `injection_task_2`, `injection_task_4` |
| [workspace](agentdojo-workspace.md) | 6 | 4 | `injection_task_3`, `injection_task_4`, `injection_task_5` |
| [banking](agentdojo-banking.md) | 42 | 41 | `injection_task_8` |
| [travel](agentdojo-travel.md) | 6 | 1 | `injection_task_3`, `injection_task_4`, `injection_task_5` |

**3. Door 2, run for real.** The first two answers leave the interesting question open, so the harness closes it. For every injection whose ground truth marks an argument as read at run time, and which makes a read call there is something to launder from, it generates a **second program**: the same calls, in the same order, with that one argument built *at run time* out of the text the read returned instead of written out as a literal. The attacker's value then genuinely comes through the data door. Each of these runs against the same three budgets, and its verdict is compared with the literal program's, pair by pair.

Over **238 pairs** and three budgets each - 714 runs - the budget decided **the same way as it did for the literal program 714 times out of 714**, and differently not once.

That is the result, and it is the one the design predicts: **a pattern is matched against the value at the door, whichever door it came through.** A budget that refuses the literal attack refuses the laundered one with the same code, and a budget that lets the literal attack through lets the laundered one through too. Pinning is not a provenance defence and does not become one when the value is read rather than written. What would tell the two apart is a mark on the value itself, which is `decisions/0004`'s `Untrusted of T` and has not shipped.

The probe is reported beside the score and never inside it. It is not an AgentDojo number: it runs a program AgentDojo's ground truth describes but does not contain, and where a security check demands an exact value - a hotel's name, a subject line - a laundered argument fails that check for a reason that has nothing to do with the budget. The budget's own verdict is the comparison that holds, and `verdicts_that_differ_from_the_literal_program` in each suite's record lists every pair where either differed.

## Pinning the arguments a task names

Of the **394 arguments** the reference solutions pass across the four suites, **160 are named by the user task's own text** and **234 are not**: a summary the model writes, a channel found by counting users, an event id the calendar returns, the hotel that comparing prices picks out. 79 of the 97 tasks have at least one such argument; 18 can be pinned all the way through.

A pin is checked against the task's prompt, and there are three kinds. **154** patterns are in the prompt character for character. **9** are the prompt's own letters and digits in another layout - `2024-05-19 12:00` from "at 12:00 on 2024-05-19" - and the check holds every letter and digit of the pattern to the fragments it is declared to come from. **9** are another notation for something the task says - `2024-05-15` for "May 15th, 2024", `r` for "read permissions", `true` for "recurring" - where the check can only hold the fragments to the prompt and a person judged the notation. Those last ones are listed on each suite's page, deliberately few, and the only place in this evaluation where a pin rests on judgement rather than on a check.

| Suite | Arguments | Pinned | Cannot be known in advance | Tasks fully pinned |
|---|---:|---:|---:|---|
| [slack](agentdojo-slack.md) | 80 | 32 | 48 | 3 of 21 |
| [workspace](agentdojo-workspace.md) | 128 | 74 | 54 | 12 of 40 |
| [banking](agentdojo-banking.md) | 57 | 18 | 39 | 2 of 16 |
| [travel](agentdojo-travel.md) | 129 | 36 | 93 | 1 of 20 |

## What these numbers are, and are not

This measures the **operator budget's contribution**, offline, with no model and no cost. Where a model would write the program, the harness transcribes AgentDojo's own ground truth: the benign program is the user task's reference solution, and the attack program is the injection task's own ground-truth action - a worst case, a model that was fully steered. The attack program is run on its own rather than after the benign solution, so whether it lands is the budget's decision and nothing else. Each runs through `sabline run --tools` against AgentDojo's real environment and is scored by AgentDojo's own `utility` and `security`.

- **Utility** is whether the reference solution runs to completion under a budget written for the task - not whether a model can find it. It is high by construction, and what it does not show is that a model can write these programs, which is the harder half.
- **Attack success** is whether the budget lets a fully-steered program's attacker action through - not how often a model is actually steered. It is an *upper bound* on what a budget permits: an attack whose tool the task never granted is refused before it reaches the host (E321), and so is one whose arguments the pins exclude; an attack that reuses a tool the task does grant, with an argument the task could not name, goes through.
- **No budget here sees what flows where.** A pattern is matched against the value at the door, whichever door it came through, so it refuses an attacker's value exactly when the operator can say in advance what the value should be, and can do nothing when they cannot. The door-2 probe above measures that rather than asserting it. Every attack that still lands is of the second kind.
- **The runs are deterministic**, so the three repeats AgentDojo's runtime-uncertainty countermeasure asks for agree by construction. Repeats matter for a model, which varies; that is not this.

What needs a model - and a key, and therefore money - is how often a model is *actually* steered, and how often it writes a working program at all. That is not run here. Until it is, these are not a measurement of Sabline-plus-a-model; they are a measurement of the budget.

## Beside CaMeL, LBAC and ChainCaps

The three systems Sabline's paper (§5) names as ahead of it report AgentDojo like this. The comparison is **not like-for-like**, and the ways it is unfair run in both directions:

| System | What it reports | Why it is not a fair comparison |
|---|---|---|
| **CaMeL** | Utility and attack success across AgentDojo suites, with a real model and per-value provenance | It runs a model; these numbers do not. CaMeL tracks where each value may go, which is the laundering defence Sabline lacks - so on attack success it should, and structurally must, do better. |
| **LBAC / TypeGuard** | Slack suite: 105/105 attacks resisted with policies on; 15/21 benign tasks completed without them, 8/21 with | Its security is measured against a real model's behaviour; ours is a worst-case steered program against the budget - on the same suite 9 of 105 land under the pinned budget. Its utility drop under policy is the price its policies charge; our utility is the reference solution, so it does not show that price. |
| **ChainCaps** | 82 tasks on five frontier models: attack success 25-68% down to 0-4.8%, benign completion 96-100% | Real models, a different task set, and per-value capability propagation. Its before/after attack-success range is a model's susceptibility and its reduction; our three columns are three budgets' decisions on a fixed action. |

Where the comparison is unfair **to** Sabline: these numbers use no model, so they cannot show that a model can write Sabline for these tasks, which is the harder half. Where it is unfair **for** Sabline: utility here is the reference solution, so it never pays the utility cost a real policy or a real model would; and attack success is a worst-case upper bound, which flatters nothing but is not a model's real steer rate.

## The evidence

Everything is in [evals/agentdojo/](https://github.com/gowrishankar-infra/sabline-lang/tree/main/evals/agentdojo): a directory per suite with its tool manifest, every generated program, and `results.json` with each pair's outcome under each of the three budgets, the pins and the reason for every argument that has none, and the door each landing attack's value came through. The roll-up over the four is `evals/agentdojo/results.json`. `python agentdojo_eval.py --check` re-runs the whole matrix and fails if a number moved - a score here can be reproduced, not trusted.

Per suite:

- [slack](agentdojo-slack.md) - 21 user tasks, 5 injection tasks, 105 attacks
- [workspace](agentdojo-workspace.md) - 40 user tasks, 6 injection tasks, 240 attacks
- [banking](agentdojo-banking.md) - 16 user tasks, 9 injection tasks, 144 attacks
- [travel](agentdojo-travel.md) - 20 user tasks, 7 injection tasks, 140 attacks
