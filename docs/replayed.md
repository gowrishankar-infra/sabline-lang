# We examined 15 real incidents and replayed 8 in Sabline

<!-- description: 15 publicly reported incidents examined; 8 replayed as Sabline programs of the same shape (2 refused, 6 in part); 7 with no replay, each saying why. -->

We examined 15 publicly reported incidents from 2023 onward in which code ran with more authority than it should have, and replayed 8 of them: for each, a Sabline program of the same shape, run under a budget, with a recorded result - 2 refused outright, 6 refused in part.

The other 7 have no replay, and each row below says why:

- 5 are not covered: nothing in Sabline addresses the shape, so there is no Sabline program to run.
- 2 are out of scope: prompt injection where no code ran, so there is no program of any kind to replay.

All 15 are on this page; none is left out.

> [!NOTE]
> **None of these involved a Sabline program, and this is not a claim that adopting Sabline would have prevented any of them.** Each replay is the *shape* of the attack, written in Sabline and run; the real events happened in languages, package managers and agent frameworks Sabline neither runs nor bounds. Every refusal below is re-run on every push, and fails the build if it stops.

## Not replayed: nothing here addresses the shape

Nothing in Sabline addresses this shape.

| Incident | Date | Why there is no replay |
|---|---|---|
| [The CircleCI breach](incident-circleci-oauth-token-theft.md) | 2022-12-22 | Not covered: nothing in Sabline addresses the shape, so there is no Sabline program to run |
| [The xz backdoor](incident-xz-utils-backdoor.md) | 2024-03-29 | Not covered: nothing in Sabline addresses the shape, so there is no Sabline program to run |
| [The Ultralytics attack](incident-ultralytics-pypi-cache-poisoning.md) | 2024-12-04 | Not covered: nothing in Sabline addresses the shape, so there is no Sabline program to run |
| [The GitHub MCP exploit](incident-github-mcp-toxic-agent-flow.md) | 2025-05-26 | Not covered: nothing in Sabline addresses the shape, so there is no Sabline program to run |
| [The Amazon Q wiper prompt](incident-amazon-q-extension-wiper.md) | 2025-07-17 | Not covered: nothing in Sabline addresses the shape, so there is no Sabline program to run |

## Replayed: refused in part

Part of the shape is refused and part is not; both halves are recorded.

| Incident | Date | The line that does the work |
|---|---|---|
| [Slopsquatting](incident-package-hallucination.md) | 2024-03-28 | `import "lib/..."` |
| [tj-actions/changed-files](incident-tj-actions-changed-files.md) | 2025-03-14 | `env` |
| [MCP tool poisoning](incident-mcp-tool-poisoning.md) | 2025-04-01 | `--max-allow io` |
| [The Nx (s1ngularity) attack](incident-nx-s1ngularity.md) | 2025-08-26 | `ffi:json` |
| [Shai-Hulud](incident-shai-hulud-npm-worm.md) | 2025-09-14 | `fs:read:.` |
| [postmark-mcp](incident-postmark-mcp-bcc-exfiltration.md) | 2025-09-25 | `tool:send_email:to=*@corp.com` |

## Replayed: refused

The shape, written in Sabline and run under a budget granting what the task needs, is refused - and the refusal is recorded and re-run on every push.

| Incident | Date | The line that does the work |
|---|---|---|
| [The Solana web3.js backdoor](incident-solana-web3js-backdoor.md) | 2024-12-03 | `sabline.lock` |
| [CVE-2025-6514 (mcp-remote)](incident-mcp-remote-command-injection.md) | 2025-07-09 | `ffi:json` |

## Not replayed: out of scope

Prompt injection where no code ran - listed so the boundary is visible, not counted as a gap.

| Incident | Date | Why there is no replay |
|---|---|---|
| [EchoLeak](incident-echoleak-m365-copilot.md) | 2025-06-11 | Out of scope: prompt injection where no code ran, so there is no program of any kind to replay |
| [CamoLeak](incident-camoleak-copilot-chat.md) | 2025-10-08 | Out of scope: prompt injection where no code ran, so there is no program of any kind to replay |

## Check it yourself

`python incident_evidence.py` re-runs every program and writes what it printed; `python check_incidents.py` is what CI runs. The entries, their sources and their programs are in [incidents/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/).
