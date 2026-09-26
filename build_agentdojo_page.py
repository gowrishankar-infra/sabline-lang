#!/usr/bin/env python3
"""docs/agentdojo.md, written from evals/agentdojo/results.json.

    python build_agentdojo_page.py            write it
    python build_agentdojo_page.py --check    fail if it is not current

The page publishes the score with the date it was measured, the AgentDojo
version it was measured on, and the model used - none, here, and the page
says why. agentdojo_eval.py records the numbers; this only renders them, so
the page cannot drift from the record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "evals" / "agentdojo" / "results.json"
OUT = HERE / "docs" / "agentdojo.md"


def _values(arguments: dict[str, Any]) -> str:
    """One call's arguments, short enough for a table cell."""
    out = []
    for k, v in sorted(arguments.items()):
        text = str(v).replace("|", "\\|").replace("\n", " ")
        if len(text) > 60:
            text = text[:57] + "..."
        out.append(f"`{k}` = `{text}`")
    return "; ".join(out)


def _door_section(p: Any, r: dict[str, Any]) -> None:
    """Which door the attacker's value came through, for each attack that
    lands under the task budget."""
    split = r.get("door_split")
    if not split:
        return
    counts = split["counts"]
    total = sum(counts.values())
    written = counts.get("program", 0)
    read = counts.get("tool_output", 0) + counts.get("mixed", 0)
    p("## Which door the attacker's value came through")
    p("")
    p(f"An attacker's value can reach a tool call two ways: **written into "
      f"the program** as a literal, because the attacker changed the "
      f"program the model wrote; or **read at run time** out of what a tool "
      f"returned, because the attacker changed the data. The door decides "
      f"what a budget can do about it, so every attack that lands under the "
      f"task budget is classified. Of the {total}: **{written} written into "
      f"the program, {read} read at run time**.")
    p("")
    p("That split is not a property of AgentDojo; it is a property of this "
      "harness, and it is the first thing to say about it. There is no "
      "model here, so where a model would read the injected instruction and "
      "act on it, the harness transcribes the injection task's ground "
      "truth - which writes the attacker's value into the program as a "
      "literal. The attacker's value **originates** in the data in every "
      "one of these; what the harness fixes is that it **arrives** as a "
      "literal.")
    p("")
    p("| Attack | Tool | The attacker's value | Door | Still lands with "
      "arguments pinned |")
    p("|---|---|---|---|---|")
    for pair in sorted(split["attacks"],
                       key=lambda k: (k.split("__")[1],
                                      int(k.split("__")[0].rsplit("_", 1)[1]))):
        row = split["attacks"][pair]
        for call in row["calls"]:
            doors = set(call["arguments_from"].values())
            word = ("written into the program" if doors == {"program"}
                    else "read at run time" if doors == {"tool_output"}
                    else "both")
            p(f"| `{row['user_task']}` + `{row['injection_task']}` | "
              f"`{call['tool']}` | {_values(call['arguments'])} | {word} | "
              f"{'yes' if row['still_lands_under_pinned'] else 'no'} |")
    p("")
    injections = r.get("injections", {})
    laundering = sorted(i for i, v in injections.items()
                        if v.get("reads_then_sends"))
    if laundering:
        granting = ", ".join(
            f"`{i}`, {injections[i]['user_tasks_granting_every_tool']}"
            for i in laundering)
        p(f"{len(laundering)} of the {len(injections)} injection tasks do "
          f"have the laundering shape - a tool that reads, then a tool that "
          f"sends - and so carry a payload no attacker writes out in "
          f"advance. Neither lands under any task budget here, and not "
          f"because of an argument: of the 21 user tasks, none grants every "
          f"tool their action needs ({granting}), so the call is refused "
          f"before any argument is looked at. The one case where the "
          f"attacker's value would genuinely arrive through the data door "
          f"is a case this suite never puts in front of the door. That is a "
          f"limit of the corpus, not a result.")
        p("")


def _pinning_section(p: Any, r: dict[str, Any]) -> None:
    """What pinning could say, what it could not, and what that cost."""
    pin = r.get("pinning")
    if not pin:
        return
    counts = pin["counts"]
    loose = pin["tasks_with_an_argument_that_cannot_be_known_in_advance"]
    p("## Pinning the arguments a task names")
    p("")
    p(f"The third budget holds each tool's arguments to what the user "
      f"task's text names. The rule is one an operator could follow before "
      f"the run: {pin['rule']}. Across the "
      f"{counts['pinned_arguments'] + counts['arguments_that_cannot_be_known_in_advance']} "
      f"arguments the reference solutions pass, "
      f"**{counts['pinned_arguments']} could be pinned** and "
      f"**{counts['arguments_that_cannot_be_known_in_advance']} could not**. "
      f"{counts['fully_pinned_tasks']} of the "
      f"{counts['fully_pinned_tasks'] + counts['tasks_with_an_argument_that_cannot_be_known_in_advance']} "
      f"user tasks can be pinned all the way through; "
      f"{counts['tasks_with_an_argument_that_cannot_be_known_in_advance']} "
      f"cannot.")
    p("")
    p("### Every task whose legitimate argument cannot be known in advance")
    p("")
    p("Pinning cannot express these. An argument left free is one the "
      "attacker may choose, so an attack lands wherever it wants that tool "
      "and whatever else the task pinned happens to match. Each entry is "
      "the task's own text, and then the arguments that text does not say.")
    p("")
    for uid in loose:
        task = pin["tasks"][uid]
        prompt = " ".join(task["prompt"].split())
        if len(prompt) > 240:
            prompt = prompt[:237] + "..."
        p(f"- **`{uid}`** - \"{prompt}\"")
        for key, why in task["cannot_be_known_in_advance"].items():
            p(f"    - `{key}`: {why}")
    p("")
    p("### What the pattern grammar could not say")
    p("")
    p("These are reported, not fixed. The grammar is the tool door's "
      "(SPEC.md 7.2) and an evaluation does not get to extend the thing it "
      "is measuring; each line below is run against the door's own matcher "
      "when the evaluation runs, so it is a test and not a sentence.")
    p("")
    for limit in pin["what_the_pattern_grammar_cannot_say"]:
        p(f"- {limit['limit']} ({limit['shown_by']}).")
    p("")
    p("None of these is why an attack lands. They are why a body or a "
      "free-text argument has to be left wholly free rather than narrowed: "
      "the choice a pattern offers is *this exact string* or *anything*, "
      "and for a message a model writes, only the second is usable.")
    p("")


def write_page(r: dict[str, Any]) -> str:
    u = r["utility"]
    a = r["attack_success"]
    c = r["counts"]
    w: list[str] = []
    p = w.append

    p("# AgentDojo")
    p("")
    p("Sabline evaluated on [AgentDojo](https://github.com/ethz-spylab/"
      "agentdojo), the agent-security benchmark of Debenedetti et al., so "
      "that its numbers can be put beside CaMeL, LBAC and ChainCaps. This "
      "page is generated from `evals/agentdojo/results.json`, which "
      "`agentdojo_eval.py` records and a CI leg re-derives on every push.")
    p("")
    p("> [!NOTE]")
    p(f"> **Suite:** `{r['suite']}` &nbsp;·&nbsp; **AgentDojo:** "
      f"{r['agentdojo_version']} ({r['benchmark_version']}) &nbsp;·&nbsp; "
      f"**Model:** {r['model']} &nbsp;·&nbsp; **Measured:** {r['date']}. "
      f"{c['user_tasks']} user tasks, {c['injection_tasks']} injection "
      f"tasks, {c['attack_pairs']} attack pairs.")
    p("")

    p("## The score, under three budgets")
    p("")
    p("| | `--allow all` (control) | A budget written for the task | "
      "...with the task's arguments pinned |")
    p("|---|---|---|---|")
    p(f"| **Utility** (reference solution completes) | "
      f"{u['allow_all']['passed']} / {u['allow_all']['of']} | "
      f"{u['task_budget']['passed']} / {u['task_budget']['of']} | "
      f"{u['pinned_budget']['passed']} / {u['pinned_budget']['of']} |")
    p(f"| **Attack success** (injection's action lands) | "
      f"{a['allow_all']['succeeded']} / {a['allow_all']['of']} | "
      f"{a['task_budget']['succeeded']} / {a['task_budget']['of']} | "
      f"{a['pinned_budget']['succeeded']} / {a['pinned_budget']['of']} |")
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
    blocked = a["allow_all"]["succeeded"] - a["task_budget"]["succeeded"]
    pinning = a["task_budget"]["succeeded"] - a["pinned_budget"]["succeeded"]
    p(f"So a budget written for each task refused **{blocked} of "
      f"{a['allow_all']['of']}** attacks that a wide-open run lets through. "
      f"Pinning the arguments the task names refused **{pinning}** of the "
      f"**{a['task_budget']['succeeded']}** that were left, and neither cost "
      f"a single task its utility. The **{a['pinned_budget']['succeeded']}** "
      f"that still land are the ones where the task's own text cannot say "
      f"what the argument should be, so the attacker's value is inside "
      f"whatever the operator could write down.")
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
            goal = row["goal"].replace("|", "\\|")
            p(f"| `{iid}` | {goal} | {row['landed_under_all']} / 21 | "
              f"{row['landed_under_budget']} / 21 | "
              f"{row['landed_under_pinned']} / 21 |")
        p("")

    _door_section(p, r)
    _pinning_section(p, r)

    p("## What these numbers are, and are not")
    p("")
    p("This measures the **operator budget's contribution**, offline, with "
      "no model and no cost. Where a model would write the program, the "
      "harness transcribes AgentDojo's own ground truth: the benign program "
      "is the user task's reference solution, and the attack program is the "
      "injection task's own ground-truth action - a worst case, a model that "
      "was fully steered. The attack program is run on its own rather than "
      "after the benign solution, so whether it lands is the budget's "
      "decision and nothing else. Each runs through `sabline run --tools` "
      "against AgentDojo's real environment and is scored by AgentDojo's own "
      "`utility` and `security`.")
    p("")
    p(f"- **Utility** is whether the reference solution runs to completion "
      f"under a budget written for the task - not whether a model can find "
      f"it. It passes for all {u['task_budget']['of']} tasks under all three "
      f"budgets, so neither the budget nor the pins block a task they should "
      f"allow. It is high by construction (the reference solution, scored by "
      f"AgentDojo's own trace-based checks); what it does not show is that a "
      f"model can write these programs, which is the harder half.")
    p("- **Attack success** is whether the budget lets a fully-steered "
      "program's attacker action through - not how often a model is "
      "actually steered. It is an *upper bound* on what a budget permits: an "
      "attack whose tool the task never granted is refused before it reaches "
      "the host (E321), and so is one whose arguments the pins exclude; an "
      "attack that reuses a tool the task does grant, with an argument the "
      "task could not name, goes through. That is the laundering Sabline has "
      "no answer to (`decisions/0004`, not yet shipped).")
    p("- **Pinning is not a provenance defence.** A pattern is matched "
      "against the value at the door, whichever door it came through, so it "
      "stops an attacker's value whenever the operator can say in advance "
      "what the value should be - and can do nothing at all when they "
      "cannot. Every attack that still lands is of the second kind.")
    p("- **The runs are deterministic**, so the three repeats AgentDojo's "
      "runtime-uncertainty countermeasure asks for agree by construction. "
      "Repeats matter for a model, which varies; that is not this.")
    p("")
    p("What needs a model - and a key, and therefore money - is how often a "
      "model is *actually* steered, and how often it writes a working "
      "program at all. That is behind a flag, off by default, and is not run "
      "in CI. Until it is, these are not a measurement of Sabline-plus-a-"
      "model; they are a measurement of the budget.")
    p("")

    p("## Beside CaMeL, LBAC and ChainCaps")
    p("")
    p("The three systems Sabline's paper (§5) names as ahead of it report "
      "AgentDojo like this. The comparison is **not like-for-like**, and the "
      "ways it is unfair run in both directions:")
    p("")
    p("| System | What it reports | Why it is not a fair comparison |")
    p("|---|---|---|")
    p("| **CaMeL** | Utility and attack success across AgentDojo suites, "
      "with a real model and per-value provenance | It runs a model; these "
      "numbers do not. CaMeL tracks where each value may go, which is the "
      "laundering defence Sabline lacks - so on attack success it should, "
      "and structurally must, do better. |")
    p("| **LBAC / TypeGuard** | Slack suite: 105/105 attacks resisted with "
      "policies on; 15/21 benign tasks completed without them, 8/21 with | "
      "Its security is measured against a real model's behaviour; ours is a "
      "worst-case steered program against the budget. Its utility drop under "
      "policy is the price its policies charge; our utility is the reference "
      "solution, so it does not show that price. |")
    p("| **ChainCaps** | 82 tasks on five frontier models: attack success "
      "25-68% down to 0-4.8%, benign completion 96-100% | Real models, a "
      "different task set, and per-value capability propagation. Its "
      "before/after attack-success range is a model's susceptibility and its "
      "reduction; our three columns are three budgets' decisions on a fixed "
      "action. |")
    p("")
    p("Where the comparison is unfair **to** Sabline: these numbers use no "
      "model, so they cannot show that a model can write Sabline for these "
      "tasks, which is the harder half. Where it is unfair **for** Sabline: "
      "utility here is the reference solution, so it never pays the utility "
      "cost a real policy or a real model would; and attack success is a "
      "worst-case upper bound, which flatters nothing but is not a model's "
      "real steer rate.")
    p("")

    p("## The evidence")
    p("")
    p("Everything is in "
      "[evals/agentdojo/](https://github.com/gowrishankar-infra/sabline-lang/"
      "tree/main/evals/agentdojo): the tool manifest, every generated "
      "program, and `results.json` with each pair's outcome under each of "
      "the three budgets, the pins and the reason for every argument that "
      "has none, and the door each landing attack's value came through. "
      "`python agentdojo_eval.py --check` re-runs the whole matrix and fails "
      "if a number moved - a score here can be reproduced, not trusted.")
    p("")
    return "\n".join(w)


def main(argv: list[str]) -> int:
    if not RESULTS.exists():
        print("no evals/agentdojo/results.json (python agentdojo_eval.py "
              "--record)")
        return 1
    r = json.loads(RESULTS.read_text(encoding="utf-8"))
    text = write_page(r)
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text(
                encoding="utf-8").replace("\r\n", "\n") != text:
            print("docs/agentdojo.md is not current "
                  "(python build_agentdojo_page.py)")
            return 1
        print("docs/agentdojo.md is current")
        return 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote docs/agentdojo.md ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
