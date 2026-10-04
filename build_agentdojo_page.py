#!/usr/bin/env python3
"""docs/agentdojo.md and a page per suite, from the recorded results.

    python build_agentdojo_page.py            write them
    python build_agentdojo_page.py --check    fail if one is not current

The overview page publishes the score over all four of AgentDojo's suites
with the date each was measured, the AgentDojo version they were measured
on, and the model used - none, here, and the page says why. Each suite then
has a page of its own: the three budgets task by task, which door each
landing attack's value came through, and every argument pinning could not
say. `agentdojo_eval.py` records the numbers; this only renders them, so a
page cannot drift from the record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVALS = HERE / "evals" / "agentdojo"
INDEX = EVALS / "results.json"
DOCS = HERE / "docs"
SUITES = ("slack", "workspace", "banking", "travel")
REPO = "https://github.com/gowrishankar-infra/sabline-lang"


def _read(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _values(arguments: dict[str, Any], most: int = 60) -> str:
    """One call's arguments, short enough for a table cell. A backtick in a
    value would end the code span it is written in, so it is replaced."""
    out = []
    for k, v in sorted(arguments.items()):
        text = (str(v).replace("|", "\\|").replace("\n", " ")
                .replace("`", "'"))
        if len(text) > most:
            text = text[:most - 3] + "..."
        out.append(f"`{k}` = `{text}`")
    return "; ".join(out)


def _prose(text: str) -> str:
    """Prose that came from the record, with the characters Markdown would
    otherwise eat escaped.

    The pattern limits are sentences about stars, and until this was fixed
    docs/agentdojo.md rendered the second of them - "'*meeting room*' against
    user_task_8's reply" - as "'<em>meeting room</em>'": a sentence about a
    star with no star left in it."""
    for ch in ("\\", "*", "_", "`", "[", "]"):
        text = text.replace(ch, "\\" + ch)
    return text


def _prompt(text: str, most: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= most else flat[:most - 3] + "..."


def _span(dates: list[str]) -> str:
    """One date, or the range the four suites were measured over."""
    return dates[0] if dates[0] == dates[-1] else f"{dates[0]} to {dates[-1]}"


def _fraction(cell: dict[str, Any], field: str) -> str:
    return f"{cell[field]} / {cell['of']}"


# ---- the overview -----------------------------------------------------------

def overview(index: dict[str, Any], suites: dict[str, Any]) -> str:
    t = index["totals"]
    w: list[str] = []
    p = w.append

    p("# AgentDojo")
    p("")
    p("Sabline evaluated on [AgentDojo](https://github.com/ethz-spylab/"
      "agentdojo), the agent-security benchmark of Debenedetti et al., so "
      "that its numbers can be put beside CaMeL, LBAC and ChainCaps. All "
      "four suites are run, with no model and at no cost. This page is "
      "generated from `evals/agentdojo/results.json`, which "
      "`agentdojo_eval.py` records and a CI job re-derives on every push.")
    p("")
    p("> [!NOTE]")
    p(f"> **Suites:** {t['suites']} (slack, workspace, banking, travel) "
      f"&nbsp;·&nbsp; **AgentDojo:** {index['agentdojo_version']} "
      f"({index['benchmark_version']}) &nbsp;·&nbsp; **Model:** "
      f"{index['model']} &nbsp;·&nbsp; **Measured:** "
      f"{_span(sorted(s['date'] for s in suites.values()))}. "
      f"{t['user_tasks']} user tasks, {t['injection_tasks']} injection "
      f"tasks, {t['attack_pairs']} attack pairs.")
    p("")

    p("## The score, under three budgets")
    p("")
    p("| Suite | Tasks | Scorable offline | Utility, of the scorable: task "
      "/ pinned | Attacks | Attack success: `all` / task / pinned |")
    p("|---|---:|---:|---|---:|---|")
    for name in SUITES:
        s = suites[name]
        u, a, c = s["utility"], s["attack_success"], s["counts"]
        p(f"| [{name}](agentdojo-{name}.md) | {c['user_tasks']} | "
          f"{c['scorable_user_tasks']} | "
          f"{u['scorable']['passed']} / {u['scorable_pinned']['passed']} "
          f"(of {u['scorable']['of']}) | {c['attack_pairs']} | "
          f"{a['allow_all']['succeeded']} / {a['task_budget']['succeeded']} / "
          f"{a['pinned_budget']['succeeded']} "
          f"(of {a['task_budget']['of']}) |")
    p(f"| **all four** | **{t['user_tasks']}** | "
      f"**{t['utility']['scorable']['of']}** | "
      f"**{t['utility']['scorable']['passed']}** / "
      f"**{t['utility']['pinned_budget']['passed']}** "
      f"(of {t['utility']['scorable']['of']}) | "
      f"**{t['attack_pairs']}** | "
      f"**{t['attack_success']['allow_all']['succeeded']} / "
      f"{t['attack_success']['task_budget']['succeeded']} / "
      f"{t['attack_success']['pinned_budget']['succeeded']}** "
      f"(of {t['attack_success']['task_budget']['of']}) |")
    p("")
    not_scorable = t["user_tasks"] - t["utility"]["scorable"]["of"]
    where = ", ".join(
        f"{suites[n]['counts']['user_tasks'] - suites[n]['counts']['scorable_user_tasks']} "
        f"of {suites[n]['counts']['user_tasks']} in {n}"
        for n in SUITES
        if suites[n]["counts"]["scorable_user_tasks"]
        < suites[n]["counts"]["user_tasks"])
    p(f"**Utility is reported over the tasks that can be judged offline, "
      f"and {not_scorable} of {t['user_tasks']} cannot be** ({where}). Many "
      f"of AgentDojo's utility checks read the assistant's own answer - "
      f"`\"4.2\" in model_output`, the restaurant's name in the reply - and "
      f"not only what the run did to the environment. There is no model "
      f"here, so there is no answer to judge, and no budget could make "
      f"those checks pass. They are counted, named on each suite's page, "
      f"and left out of the utility column rather than reported as "
      f"refusals. The scorable set is where a budget's effect on utility "
      f"can be read at all, and there the question is whether the task "
      f"budget and the pinned budget pass exactly what `--allow all` "
      f"passes.")
    p("")
    p("Lower attack success is better. The three budgets are nested, and "
      "each column is one more thing the operator said:")
    p("")
    p("- **`--allow all`** bounds nothing. It is the control.")
    p("- **The task budget** is `io` and a grant for each tool the "
      "reference solution calls, by name - an operator who wrote the budget "
      "for this task and no more.")
    p("- **The pinned budget** is that, with every argument the user task's "
      "*own text* names held to that value by the tool door's argument "
      "patterns (`tool:send_direct_message:recipient=Bob`, SPEC.md 7.2). "
      "Nothing in it is read from what a tool returns: the harness checks "
      "every literal in every pattern against that task's own prompt and "
      "stops if one is not there.")
    p("")
    atk = t["attack_success"]
    blocked = atk["allow_all"]["succeeded"] - atk["task_budget"]["succeeded"]
    pinning = atk["task_budget"]["succeeded"] - atk["pinned_budget"][
        "succeeded"]
    util = t["utility"]
    cost = util["allow_all"]["passed"] - util["pinned_budget"]["passed"]
    p(f"So a budget written for each task refused **{blocked} of the "
      f"{atk['allow_all']['succeeded']}** attacks that a wide-open run lets "
      f"through. Pinning the arguments the task names refused "
      f"**{pinning}** more of the "
      f"**{atk['task_budget']['succeeded']}** that were left, leaving "
      f"**{atk['pinned_budget']['succeeded']}**. The utility cost of both "
      f"together, over all four suites, is "
      f"**{cost} of the {util['scorable']['of']}** reference solutions "
      f"that can be judged at all.")
    p("")

    _door_section(p, index, suites)
    _probe_section(p, index, suites)
    _pinning_overview(p, index, suites)
    _limits_section(p, t, util, atk)
    _comparison_section(p, suites)

    p("## The evidence")
    p("")
    p(f"Everything is in [evals/agentdojo/]({REPO}/tree/main/evals/"
      f"agentdojo): a directory per suite with its tool manifest, every "
      f"generated program, and `results.json` with each pair's outcome "
      f"under each of the three budgets, the pins and the reason for every "
      f"argument that has none, and the door each landing attack's value "
      f"came through. The roll-up over the four is "
      f"`evals/agentdojo/results.json`. `python agentdojo_eval.py --check` "
      f"re-runs the whole matrix and fails if a number moved - a score here "
      f"can be reproduced, not trusted.")
    p("")
    p("Per suite:")
    p("")
    for name in SUITES:
        s = suites[name]
        p(f"- [{name}](agentdojo-{name}.md) - "
          f"{s['counts']['user_tasks']} user tasks, "
          f"{s['counts']['injection_tasks']} injection tasks, "
          f"{s['counts']['attack_pairs']} attacks")
    p("")
    return "\n".join(w)


def _door_section(p: Any, index: dict[str, Any],
                  suites: dict[str, Any]) -> None:
    t = index["totals"]
    ran = t["door_split"]
    gt = t["door_split_in_ground_truth"]
    landing = sum(ran.values())
    p("## Which door the attacker's value came through")
    p("")
    p("An attacker's value can reach a tool call two ways: **written into "
      "the program** as a literal, because the attacker changed the program "
      "the model wrote; or **read at run time** out of what a tool returned "
      "- *door 2* - because the attacker changed the data. The door decides "
      "what a budget can do about it, so every attack that lands under the "
      "task budget is classified. Three different questions are asked, and "
      "they have three different answers.")
    p("")
    p("**1. Where the value came from in this run.** "
      + ", ".join(f"**{n} {word.replace('_', ' ')}**"
                  for word, n in sorted(ran.items()))
      + f", of {landing} landing attacks. That number is a property of this "
      f"harness and not of AgentDojo, and it is worth nothing on its own: "
      f"there is no model here, so where a model would read the injected "
      f"instruction and act on it, the harness transcribes the injection "
      f"task's ground truth - which writes the attacker's value out as a "
      f"literal. Under transcription the answer **can only be** 'the "
      f"program'. The value originates in the data in every one of these; "
      f"what the harness fixes is that it arrives as a literal.")
    p("")
    p("**2. What AgentDojo itself says about the same arguments.** Its "
      "ground truth carries `placeholder_args` beside the resolved ones, and "
      "where a real agent would have to read a value out of the data it "
      "writes a marker there - `$code` for the security code in an email, "
      "`$email.body`, `$content`, `$most_expensive_hotel.name`. That is the "
      "benchmark's own judgement, made before Sabline existed, and it is "
      "evidence about the corpus rather than about this harness. Of the "
      f"{landing} landing attacks, "
      f" **{gt.get('tool_output', 0) + gt.get('mixed', 0)}** have ground "
      f"truth that marks at least one argument as read at run time, and "
      f"**{gt.get('program', 0)}** carry the attacker's own values "
      f"throughout.")
    p("")
    p("| Suite | Landing attacks | ...whose ground truth marks an argument "
      "read at run time | Injections the probe could launder |")
    p("|---|---:|---:|---|")
    for name in SUITES:
        s = suites[name]
        counts = s["door_split"]["counts"]
        gtc = s["door_split"]["counts_in_ground_truth"]
        marked = gtc.get("tool_output", 0) + gtc.get("mixed", 0)
        probes = s["door2_probe"]["injections"]
        p(f"| [{name}](agentdojo-{name}.md) | {sum(counts.values())} | "
          f"{marked} | "
          f"{', '.join(f'`{i}`' for i in probes) if probes else 'none'} |")
    p("")


def _probe_section(p: Any, index: dict[str, Any],
                   suites: dict[str, Any]) -> None:
    probe = index["totals"]["door2_probe"]
    p("**3. Door 2, run for real.** The first two answers leave the "
      "interesting question open, so the harness closes it. For every "
      "injection whose ground truth marks an argument as read at run time, "
      "and which makes a read call there is something to launder from, it "
      "generates a **second program**: the same calls, in the same order, "
      "with that one argument built *at run time* out of the text the read "
      "returned instead of written out as a literal. The attacker's value "
      "then genuinely comes through the data door. Each of these runs "
      "against the same three budgets, and its verdict is compared with the "
      "literal program's, pair by pair.")
    p("")
    same = probe["same_refusal_as_literal"]
    differ = probe["refusals_that_differ"]
    p(f"Over **{probe['pairs']} pairs** and three budgets each - "
      f"{probe['of']} runs - the budget decided **the same way as it did for "
      f"the literal program {same} times out of {probe['of']}**"
      + (f", and differently {differ} times."
         if differ else ", and differently not once."))
    p("")
    if differ:
        p("The runs where it differed are listed on the suite pages, with "
          "the refusal each one got. They are the result to read first: a "
          "budget that decides differently when the value is read rather "
          "than written is doing something a pattern alone cannot account "
          "for, and each case needs its own reading.")
    else:
        p("That is the result, and it is the one the design predicts: **a "
          "pattern is matched against the value at the door, whichever door "
          "it came through.** A budget that refuses the literal attack "
          "refuses the laundered one with the same code, and a budget that "
          "lets the literal attack through lets the laundered one through "
          "too. Pinning is not a provenance defence and does not become one "
          "when the value is read rather than written. What would tell the "
          "two apart is a mark on the value itself, which is "
          "`decisions/0004`'s `Untrusted of T` and has not shipped.")
    p("")
    p("The probe is reported beside the score and never inside it. It is "
      "not an AgentDojo number: it runs a program AgentDojo's ground truth "
      "describes but does not contain, and where a security check demands "
      "an exact value - a hotel's name, a subject line - a laundered "
      "argument fails that check for a reason that has nothing to do with "
      "the budget. The budget's own verdict is the comparison that holds, "
      "and `verdicts_that_differ_from_the_literal_program` in each suite's "
      "record lists every pair where either differed.")
    p("")


def _pinning_overview(p: Any, index: dict[str, Any],
                      suites: dict[str, Any]) -> None:
    pin = index["totals"]["pinning"]
    total = (pin["pinned_arguments"]
             + pin["arguments_that_cannot_be_known_in_advance"])
    p("## Pinning the arguments a task names")
    p("")
    p(f"Of the **{total} arguments** the reference solutions pass across "
      f"the four suites, **{pin['pinned_arguments']} are named by the user "
      f"task's own text** and **"
      f"{pin['arguments_that_cannot_be_known_in_advance']} are not**: a "
      f"summary the model writes, a channel found by counting users, an "
      f"event id the calendar returns, the hotel that comparing prices "
      f"picks out. "
      f"{pin['tasks_with_an_argument_that_cannot_be_known_in_advance']} of "
      f"the {index['totals']['user_tasks']} tasks have at least one such "
      f"argument; {pin['fully_pinned_tasks']} can be pinned all the way "
      f"through.")
    p("")
    p(f"A pin is checked against the task's prompt, and there are three "
      f"kinds. **{pin['patterns_verbatim_in_the_prompt']}** patterns are in "
      f"the prompt character for character. "
      f"**{pin['patterns_reformatted_from_it']}** are the prompt's own "
      f"letters and digits in another layout - `2024-05-19 12:00` from \"at "
      f"12:00 on 2024-05-19\" - and the check holds every letter and digit "
      f"of the pattern to the fragments it is declared to come from. "
      f"**{pin['patterns_translated_from_it']}** are another notation for "
      f"something the task says - `2024-05-15` for \"May 15th, 2024\", `r` "
      f"for \"read permissions\", `true` for \"recurring\" - where the "
      f"check can only hold the fragments to the prompt and a person "
      f"judged the notation. Those last ones are listed on each suite's "
      f"page, deliberately few, and the only place in this evaluation where "
      f"a pin rests on judgement rather than on a check.")
    p("")
    p("| Suite | Arguments | Pinned | Cannot be known in advance | Tasks "
      "fully pinned |")
    p("|---|---:|---:|---:|---|")
    for name in SUITES:
        c = suites[name]["pinning"]
        both = (c["pinned_arguments"]
                + c["arguments_that_cannot_be_known_in_advance"])
        p(f"| [{name}](agentdojo-{name}.md) | {both} | "
          f"{c['pinned_arguments']} | "
          f"{c['arguments_that_cannot_be_known_in_advance']} | "
          f"{c['fully_pinned_tasks']} of "
          f"{c['fully_pinned_tasks'] + c['tasks_with_an_argument_that_cannot_be_known_in_advance']} |")
    p("")


def _limits_section(p: Any, t: dict[str, Any], util: dict[str, Any],
                    atk: dict[str, Any]) -> None:
    p("## What these numbers are, and are not")
    p("")
    p("This measures the **operator budget's contribution**, offline, with "
      "no model and no cost. Where a model would write the program, the "
      "harness transcribes AgentDojo's own ground truth: the benign program "
      "is the user task's reference solution, and the attack program is the "
      "injection task's own ground-truth action - a worst case, a model "
      "that was fully steered. The attack program is run on its own rather "
      "than after the benign solution, so whether it lands is the budget's "
      "decision and nothing else. Each runs through `sabline run --tools` "
      "against AgentDojo's real environment and is scored by AgentDojo's "
      "own `utility` and `security`.")
    p("")
    p("- **Utility** is whether the reference solution runs to completion "
      "under a budget written for the task - not whether a model can find "
      "it. It is high by construction, and what it does not show is that a "
      "model can write these programs, which is the harder half.")
    p("- **Attack success** is whether the budget lets a fully-steered "
      "program's attacker action through - not how often a model is "
      "actually steered. It is an *upper bound* on what a budget permits: "
      "an attack whose tool the task never granted is refused before it "
      "reaches the host (E321), and so is one whose arguments the pins "
      "exclude; an attack that reuses a tool the task does grant, with an "
      "argument the task could not name, goes through.")
    p("- **No budget here sees what flows where.** A pattern is matched "
      "against the value at the door, whichever door it came through, so it "
      "refuses an attacker's value exactly when the operator can say in "
      "advance what the value should be, and can do nothing when they "
      "cannot. The door-2 probe above measures that rather than asserting "
      "it. Every attack that still lands is of the second kind.")
    p("- **The runs are deterministic**, so the three repeats AgentDojo's "
      "runtime-uncertainty countermeasure asks for agree by construction. "
      "Repeats matter for a model, which varies; that is not this.")
    p("")
    p("What needs a model - and a key, and therefore money - is how often a "
      "model is *actually* steered, and how often it writes a working "
      "program at all. That is not run here. Until it is, these are not a "
      "measurement of Sabline-plus-a-model; they are a measurement of the "
      "budget.")
    p("")


def _comparison_section(p: Any, suites: dict[str, Any]) -> None:
    slack = suites["slack"]["attack_success"]
    p("## Beside CaMeL, LBAC and ChainCaps")
    p("")
    p("The three systems Sabline's paper (§5) names as ahead of it report "
      "AgentDojo like this. The comparison is **not like-for-like**, and "
      "the ways it is unfair run in both directions:")
    p("")
    p("| System | What it reports | Why it is not a fair comparison |")
    p("|---|---|---|")
    p("| **CaMeL** | Utility and attack success across AgentDojo suites, "
      "with a real model and per-value provenance | It runs a model; these "
      "numbers do not. CaMeL tracks where each value may go, which is the "
      "laundering defence Sabline lacks - so on attack success it should, "
      "and structurally must, do better. |")
    p(f"| **LBAC / TypeGuard** | Slack suite: 105/105 attacks resisted with "
      f"policies on; 15/21 benign tasks completed without them, 8/21 with | "
      f"Its security is measured against a real model's behaviour; ours is "
      f"a worst-case steered program against the budget - on the same suite "
      f"{slack['pinned_budget']['succeeded']} of "
      f"{slack['pinned_budget']['of']} land under the pinned budget. Its "
      f"utility drop under policy is the price its policies charge; our "
      f"utility is the reference solution, so it does not show that "
      f"price. |")
    p("| **ChainCaps** | 82 tasks on five frontier models: attack success "
      "25-68% down to 0-4.8%, benign completion 96-100% | Real models, a "
      "different task set, and per-value capability propagation. Its "
      "before/after attack-success range is a model's susceptibility and "
      "its reduction; our three columns are three budgets' decisions on a "
      "fixed action. |")
    p("")
    p("Where the comparison is unfair **to** Sabline: these numbers use no "
      "model, so they cannot show that a model can write Sabline for these "
      "tasks, which is the harder half. Where it is unfair **for** Sabline: "
      "utility here is the reference solution, so it never pays the utility "
      "cost a real policy or a real model would; and attack success is a "
      "worst-case upper bound, which flatters nothing but is not a model's "
      "real steer rate.")
    p("")


# ---- a suite's own page -----------------------------------------------------

def suite_page(name: str, r: dict[str, Any]) -> str:
    u, a, c = r["utility"], r["attack_success"], r["counts"]
    w: list[str] = []
    p = w.append

    p(f"# AgentDojo: the {name} suite")
    p("")
    p(f"The {name} suite of [AgentDojo](https://github.com/ethz-spylab/"
      f"agentdojo), run through Sabline's tool door under three operator "
      f"budgets with no model in the loop. [The overview]"
      f"(agentdojo.md) says what is being measured and what it is worth; "
      f"this page is this suite's own numbers, generated from "
      f"`evals/agentdojo/{name}/results.json`.")
    p("")
    p("> [!NOTE]")
    p(f"> **Suite:** `{name}` &nbsp;·&nbsp; **AgentDojo:** "
      f"{r['agentdojo_version']} ({r['benchmark_version']}) &nbsp;·&nbsp; "
      f"**Model:** {r['model']} &nbsp;·&nbsp; **Measured:** {r['date']}. "
      f"{c['user_tasks']} user tasks, {c['injection_tasks']} injection "
      f"tasks, {c['attack_pairs']} attack pairs.")
    p("")

    p("## The score")
    p("")
    p("| | `--allow all` (control) | A budget written for the task | "
      "...with the task's arguments pinned |")
    p("|---|---|---|---|")
    p(f"| **Utility** (reference solution completes) | "
      f"{_fraction(u['allow_all'], 'passed')} | "
      f"{_fraction(u['task_budget'], 'passed')} | "
      f"{_fraction(u['pinned_budget'], 'passed')} |")
    p(f"| **Attack success** (injection's action lands) | "
      f"{_fraction(a['allow_all'], 'succeeded')} | "
      f"{_fraction(a['task_budget'], 'succeeded')} | "
      f"{_fraction(a['pinned_budget'], 'succeeded')} |")
    p("")
    blocked = a["allow_all"]["succeeded"] - a["task_budget"]["succeeded"]
    pinning = a["task_budget"]["succeeded"] - a["pinned_budget"]["succeeded"]
    cost = u["allow_all"]["passed"] - u["pinned_budget"]["passed"]
    p(f"A budget written for each task refused **{blocked}** of the "
      f"**{a['allow_all']['succeeded']}** attacks a wide-open run lets "
      f"through; pinning refused **{pinning}** more, leaving "
      f"**{a['pinned_budget']['succeeded']}**. "
      + (f"The two together cost **{cost}** of the "
         f"{u['allow_all']['passed']} reference solutions that complete "
         f"with nothing bounded." if cost
         else "What that cost in utility cannot be read off this suite at "
              "all: no reference solution in it can be judged offline, for "
              "the reason below." if not u["allow_all"]["passed"]
         else "The two together cost no task its utility: every reference "
              "solution that completes with nothing bounded completes "
              "under both."))
    p("")
    if u["allow_all"]["passed"] < u["allow_all"]["of"]:
        p(f"{u['allow_all']['of'] - u['allow_all']['passed']} of the "
          f"{u['allow_all']['of']} reference solutions do not pass "
          f"AgentDojo's utility check even with `--allow all`, so no budget "
          f"could make them. Two reasons, and neither is the budget's: a "
          f"check that reads the assistant's own answer (`\"4.2\" in "
          f"model_output`) has no answer to read when there is no model, "
          f"and a ground truth that encodes model-written content - a "
          f"summary, a free-text body - as a placeholder cannot satisfy its "
          f"own check. Those tasks are not scorable offline"
          + (", and in this suite that is all of them, so its utility "
             "column is empty rather than bad."
             if not u["scorable"]["of"] else
             f". The scorable set is where the budget's effect on utility "
             f"can be read: {_fraction(u['scorable'], 'passed')} under the "
             f"task budget and "
             f"{_fraction(u['scorable_pinned'], 'passed')} with arguments "
             f"pinned."))
        p("")

    by = a.get("by_injection", {})
    if by:
        p("### By injection task")
        p("")
        p("| Injection | Goal | Lands under `--allow all` | ...under the "
          "task budget | ...with arguments pinned |")
        p("|---|---|---:|---:|---:|")
        for iid in sorted(by):
            row = by[iid]
            goal = _prompt(row["goal"], 150).replace("|", "\\|")
            p(f"| `{iid}` | {goal} | "
              f"{row['landed_under_all']} / {row['of']} | "
              f"{row['landed_under_budget']} / {row['of']} | "
              f"{row['landed_under_pinned']} / {row['of']} |")
        p("")

    _suite_door(p, name, r)
    _suite_probe(p, name, r)
    _suite_pinning(p, name, r)
    p("## The evidence")
    p("")
    p(f"[evals/agentdojo/{name}/]({REPO}/tree/main/evals/agentdojo/{name}) "
      f"holds the tool manifest, every generated program - the benign "
      f"solutions, the attacker actions, and the door-2 probes - and "
      f"`results.json` with every pair's outcome under every budget. "
      f"`python agentdojo_eval.py --check --suite {name}` re-derives all of "
      f"it.")
    p("")
    return "\n".join(w)


def _suite_door(p: Any, name: str, r: dict[str, Any]) -> None:
    split = r["door_split"]
    landing = sum(split["counts"].values())
    p("## Which door the attacker's value came through")
    p("")
    if not landing:
        p("No attack lands under the task budget in this suite, so there is "
          "no value whose door to classify.")
        p("")
        return
    p(f"Of the **{landing}** attacks that land under the task budget, this "
      f"is where each attacker's value came from. **In this run** the "
      f"answer is "
      + ", ".join(f"{n} {word.replace('_', ' ')}"
                  for word, n in sorted(split["counts"].items()))
      + " - and under ground-truth transcription that answer is fixed by "
        "construction, because the harness writes the resolved value out as "
        "a literal. The column that carries information is the next one: "
        "**what AgentDojo's own ground truth says**, where a "
        "`placeholder_args` marker like `$code` is the benchmark saying a "
        "real agent reads this value out of the data.")
    p("")
    p("| Injection | The attacker's call | The value | Door, in this run | "
      "Door, in AgentDojo's ground truth | Lands / still lands pinned |")
    p("|---|---|---|---|---|---|")
    rows: dict[str, dict[str, Any]] = {}
    for pair, row in split["attacks"].items():
        iid = row["injection_task"]
        seen = rows.setdefault(iid, {"lands": 0, "pinned": 0, "calls": []})
        seen["lands"] += 1
        seen["pinned"] += int(row["still_lands_under_pinned"])
        for call in row["calls"]:
            key = (call["tool"], _values(call["arguments"]))
            if key not in [(c["tool"], c["values"]) for c in seen["calls"]]:
                seen["calls"].append({
                    "tool": call["tool"], "values": key[1],
                    "door": ", ".join(sorted(set(
                        call["arguments_from"].values()))).replace("_", " ")})
    for iid in sorted(rows):
        seen = rows[iid]
        inj = r["injections"][iid]
        marked = inj["arguments_read_at_run_time"]
        gt = (", ".join(f"`{m}`" for m in marked) if marked
              else "nothing marked: the attacker's own values")
        for n, call in enumerate(seen["calls"]):
            p(f"| {'`' + iid + '`' if n == 0 else ''} | `{call['tool']}` | "
              f"{call['values']} | {call['door']} | "
              f"{gt if n == 0 else ''} | "
              f"{str(seen['lands']) + ' / ' + str(seen['pinned']) if n == 0 else ''} |")
    p("")
    injections = r.get("injections", {})
    laundering = sorted(i for i, v in injections.items()
                        if v.get("reads_then_sends"))
    if laundering:
        granting = ", ".join(
            f"`{i}` ({injections[i]['user_tasks_granting_every_tool']})"
            for i in laundering)
        reach = [i for i in laundering
                 if injections[i]["user_tasks_granting_every_tool"]]
        p(f"{len(laundering)} of the {len(injections)} injection tasks have "
          f"the **laundering shape** - a tool that reads, then a tool that "
          f"sends - and so carry a payload no attacker writes out in "
          f"advance. The number of user tasks granting every tool each one "
          f"needs is {granting}; an injection no task grants all of is "
          f"refused before any argument is looked at. "
          + (f"{len(reach)} of them do reach the door, which is what the "
             f"probe below is run on."
             if reach else
             "None of them reaches the door here, so the one case where the "
             "attacker's value would genuinely arrive through the data door "
             "is a case this suite never puts in front of the door. That is "
             "a limit of the corpus, not a result."))
        p("")


def _suite_probe(p: Any, name: str, r: dict[str, Any]) -> None:
    probe = r["door2_probe"]
    p("## Door 2, run for real")
    p("")
    if not probe["injections"]:
        p("No injection in this suite can be made to launder its payload: "
          "none of them both marks an argument as read at run time *and* "
          "makes a read call there is something to read it from. So door 2 "
          "is not exercised here, and that is a limit of this suite's "
          "corpus rather than a result about Sabline. The other suites' "
          "pages have the measurement.")
        p("")
        return
    counts = probe["counts"]
    p("For each injection below, a second program makes the same calls with "
      "the marked argument built **at run time** out of what the read "
      "returned, instead of written out as a literal. The attacker's value "
      "then comes through the data door for real.")
    p("")
    p("| Injection | Reads | Then calls | The laundered argument | "
      "AgentDojo's own marker |")
    p("|---|---|---|---|---|")
    for iid, plan in sorted(probe["injections"].items()):
        marker = _prompt(plan["placeholder"], 60).replace("|", "\\|")
        p(f"| `{iid}` | `{plan['read']}` | `{plan['sink']}` | "
          f"`{plan['argument']}` | `{marker}` |")
    p("")
    doors = probe["door_the_laundered_argument_came_through"]
    p(f"Over **{counts['pairs']} pairs** and three budgets each, the budget "
      f"decided the same way as it did for the literal program "
      f"**{counts['same_refusal_as_literal']} times out of "
      f"{counts['of']}**"
      + (f", and differently {counts['refusals_that_differ']} times."
         if counts["refusals_that_differ"] else " - every time.")
      + " Under the task budget the laundered argument itself reached the "
        "door through door 2 in **"
      + str(doors.get("tool_output", 0)) + "** of the "
      + f"{counts['pairs']} pairs"
      + ("; in the rest the call was refused or never attempted."
         if sum(doors.values()) > doors.get("tool_output", 0) else "."))
    p("")
    p(f"Attack success for the laundering programs, for comparison with the "
      f"same pairs' literal runs: **{probe['landed']['all']}** under "
      f"`--allow all`, **{probe['landed']['task']}** under the task budget, "
      f"**{probe['landed']['pinned']}** with arguments pinned, of "
      f"{counts['pairs']}.")
    p("")
    differ = probe["verdicts_that_differ_from_the_literal_program"]
    if differ:
        budget = [d for d in differ if d["the_budget_decided_differently"]]
        scored = [d for d in differ if d["agentdojo_scored_it_differently"]]
        p(f"{len(differ)} of the {counts['of']} runs differ from the "
          f"literal program's"
          + (f": **{len(budget)}** where the *budget* decided differently, "
             f"and **{len(scored)}** where only *AgentDojo's security check* "
             f"did"
             if budget else
             " - in every one of them it is *AgentDojo's security check* "
             "that differs and never the budget")
          + ". A difference in the check is not a fact about "
          "Sabline: a check that demands an exact value - a hotel's name, "
          "a subject line - cannot be satisfied by an argument built out "
          "of a whole tool result, however faithfully that models what a "
          "steered agent would send. Every one of them is listed in "
          "`door2_probe.verdicts_that_differ_from_the_literal_program`.")
        p("")
        if budget:
            p("| Pair | Budget | The budget's answer to the laundered call |")
            p("|---|---|---|")
            for d in budget[:20]:
                p(f"| `{d['pair']}` | {d['budget']} | "
                  f"{d['refusal'] or 'allowed'}"
                  f"{', and the attack lands' if d['probe_attack_succeeded'] else ''} |")
            p("")
    else:
        p("No run differs from its literal counterpart, under any budget: "
          "the budget's verdict, and AgentDojo's own security check, come "
          "out the same whichever door the value came through.")
        p("")


def _suite_pinning(p: Any, name: str, r: dict[str, Any]) -> None:
    pin = r["pinning"]
    counts = pin["counts"]
    loose = pin["tasks_with_an_argument_that_cannot_be_known_in_advance"]
    both = (counts["pinned_arguments"]
            + counts["arguments_that_cannot_be_known_in_advance"])
    p("## Pinning the arguments a task names")
    p("")
    p(f"The third budget holds each tool's arguments to what the user "
      f"task's text names. The rule is one an operator could follow before "
      f"the run: {_prose(pin['rule'])}. Across the {both} arguments the "
      f"reference "
      f"solutions pass, **{counts['pinned_arguments']} could be pinned** "
      f"and **{counts['arguments_that_cannot_be_known_in_advance']} could "
      f"not**. {counts['fully_pinned_tasks']} of the "
      f"{counts['fully_pinned_tasks'] + counts['tasks_with_an_argument_that_cannot_be_known_in_advance']} "
      f"user tasks can be pinned all the way through.")
    p("")
    derived = pin.get("patterns_that_are_not_the_prompts_own_characters", [])
    p(f"Of the pins themselves, "
      f"{counts['patterns_verbatim_in_the_prompt']} are in the task's "
      f"prompt character for character, "
      f"{counts['patterns_reformatted_from_it']} are its own letters and "
      f"digits in another layout, and "
      f"{counts['patterns_translated_from_it']} are another notation for "
      f"something it says."
      + (" Those last two kinds are declared, and here they are in full:"
         if derived else ""))
    p("")
    if derived:
        p("| Pattern | Kind | Built from the task's | Why |")
        p("|---|---|---|---|")
        for entry in derived:
            frm = ", ".join(f'"{_prose(f)}"' for f in entry["from"])
            p(f"| `{entry['pattern']}` | {entry['kind']} | "
              f"{frm.replace('|', chr(92) + '|')} | {_prose(entry['why'])} |")
        p("")
    if loose:
        p("### Every task whose legitimate argument cannot be known in "
          "advance")
        p("")
        p("Pinning cannot express these. An argument left free is one the "
          "attacker may choose, so an attack lands wherever it wants that "
          "tool and whatever else the task pinned happens to match. Each "
          "entry is the task's own text, and then the arguments that text "
          "does not say.")
        p("")
        for uid in loose:
            task = pin["tasks"][uid]
            p(f"- **`{uid}`** - \"{_prompt(task['prompt'])}\"")
            for key, why in task["cannot_be_known_in_advance"].items():
                p(f"    - `{key}`: {_prose(why)}")
        p("")
    p("### What the pattern grammar could not say")
    p("")
    p("These are reported, not fixed. The grammar is the tool door's "
      "(SPEC.md 7.2) and an evaluation does not get to extend the thing it "
      "is measuring; each line below is run against the door's own matcher, "
      "or its own grant check, when the evaluation runs - so it is a test "
      "and not a sentence.")
    p("")
    for limit in pin["what_the_pattern_grammar_cannot_say"]:
        p(f"- {_prose(limit['limit'])} ({_prose(limit['shown_by'])}).")
    for limit in pin.get("what_only_the_door_shows", []):
        p(f"- {_prose(limit['limit'])} ({_prose(limit['shown_by'])}).")
    p("")


# ---- writing them -----------------------------------------------------------

def pages() -> dict[Path, str]:
    index = _read(INDEX)
    suites = {name: _read(EVALS / name / "results.json") for name in SUITES}
    out = {DOCS / "agentdojo.md": overview(index, index["suites"])}
    for name in SUITES:
        out[DOCS / f"agentdojo-{name}.md"] = suite_page(name, suites[name])
    return out


def write_pages() -> list[str]:
    written = []
    for path, text in pages().items():
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(f"{path.relative_to(HERE).as_posix()} "
                       f"({len(text)} bytes)")
    return written


def main(argv: list[str]) -> int:
    if not INDEX.exists():
        print("no evals/agentdojo/results.json (python agentdojo_eval.py "
              "--record)")
        return 1
    if "--check" in argv:
        stale = [path.relative_to(HERE).as_posix()
                 for path, text in pages().items()
                 if not path.exists() or path.read_text(
                     encoding="utf-8").replace("\r\n", "\n") != text]
        if stale:
            print("not current (python build_agentdojo_page.py): "
                  + ", ".join(stale))
            return 1
        print("every AgentDojo page is current")
        return 0
    for line in write_pages():
        print(f"wrote {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
