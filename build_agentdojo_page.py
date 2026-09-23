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

    p("## The score")
    p("")
    p("| | Under a budget written for the task | Under `--allow all` (control) |")
    p("|---|---|---|")
    p(f"| **Utility** (reference solution completes) | "
      f"{u['task_budget']['passed']} / {u['task_budget']['of']} | "
      f"{u['allow_all']['passed']} / {u['allow_all']['of']} |")
    p(f"| **Attack success** (injection's action lands) | "
      f"{a['task_budget']['succeeded']} / {a['task_budget']['of']} | "
      f"{a['allow_all']['succeeded']} / {a['allow_all']['of']} |")
    p("")
    p("Lower attack success is better. The gap between the two columns is "
      "exactly what the operator's budget did: under `--allow all` nothing "
      "is bounded, so the control shows how many attacks the budget - and "
      "not the language, and not a model - refused.")
    p("")
    blocked = a["allow_all"]["succeeded"] - a["task_budget"]["succeeded"]
    p(f"So a budget written for each task refused **{blocked} of "
      f"{a['allow_all']['of']}** attacks that a wide-open run lets through. "
      f"The **{a['task_budget']['succeeded']}** that still land are the ones "
      f"whose action reuses a tool the user task legitimately needs - the "
      f"laundering an ambient budget cannot see, which `decisions/0004` is "
      f"the design for and which has not shipped.")
    p("")
    by = a.get("by_injection", {})
    if by:
        p("### By injection task")
        p("")
        p("| Injection | Goal | Blocked by the task budget | Still lands "
          "under the task budget |")
        p("|---|---|---:|---:|")
        for iid in sorted(by):
            row = by[iid]
            goal = row["goal"].replace("|", "\\|")
            p(f"| `{iid}` | {goal} | {row['blocked_by_budget']} / 21 | "
              f"{row['landed_under_budget']} / 21 |")
        p("")

    p("## What these numbers are, and are not")
    p("")
    p("This measures the **operator budget's contribution**, offline, with "
      "no model and no cost. Where a model would write the program, the "
      "harness transcribes AgentDojo's own ground truth: the benign program "
      "is the user task's reference solution, and the attacked program is "
      "that solution followed by the injection task's ground-truth action - "
      "a worst case, a model that was fully steered and does both. Each runs "
      "through `sabline run --tools` against AgentDojo's real environment and "
      "is scored by AgentDojo's own `utility` and `security`.")
    p("")
    p(f"- **Utility** is whether the reference solution runs to completion "
      f"under a budget written for the task - not whether a model can find "
      f"it. It passes for all {u['task_budget']['of']} tasks, and for the "
      f"same tasks under `--allow all`, so the budget never blocks a task it "
      f"should allow. It is high by construction (the reference solution, "
      f"scored by AgentDojo's own trace-based checks); what it does not show "
      f"is that a model can write these programs, which is the harder half.")
    p("- **Attack success** is whether the budget lets a fully-steered "
      "program's attacker action through - not how often a model is "
      "actually steered. It is an *upper bound* on what a budget permits: an "
      "attack whose tool the task never granted is refused before it reaches "
      "the host (E321); an attack that reuses a tool the task does grant "
      "goes through, and that is the laundering Sabline has no answer to "
      "(`decisions/0004`, not yet shipped).")
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
      "reduction; our two columns are a budget's decision on a fixed action. |")
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
      "program, and `results.json` with each pair's outcome. "
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
