# Awesome-list entries, each in its own list's format

Read 2026-09-25 from each list's own README, CONTRIBUTING and recent merged
pull requests (`plan/findability-research/venues.md` has every rule
verbatim, with the existing entries each draft copies the shape of). One
pull request per list; say in it that you are the author. Re-check counts,
positions and rules on the day - they move.

## 1. agentlanguages.dev (aallan/agentlanguages) - a catalogue of AI-first languages

A pull request adding one file, `src/content/languages/sabline.md`
(frontmatter schema, a body of 200 words or more, entries CC BY 4.0). The
scaffold already exists locally at `D:\agentlanguages`, branch `add-sabline`,
not pushed, with every prose field a TODO. Nothing excludes Sabline. Its
`one_liner` is capped at 280 characters.

## 2. ChessMax/awesome-programming-languages

Self-promotion is explicitly welcome ("promote your own programming
language"). Add as the first entry under `# S`, bump that header's count and
the total on line 2 (56 to 57 and 965 to 966 on 2026-09-25 - re-check).
PR title: `Add Sabline`.

```
- [Sabline](https://github.com/gowrishankar-infra/sabline-lang) - Sabline is a language for scripts an AI writes. Each function's signature declares the effects it may use (files, network hosts, environment variables, clock, randomness, Python modules); the person running it grants a narrower budget (a folder, a host, a number of calls), and the interpreter refuses any operation outside that budget at the moment it is attempted. Contracts are proven with Z3 where possible and checked at run time otherwise. Formerly Velaris. [AI]
```

## 3. ottosulin/awesome-ai-security

The only rule: "create a PR". Append at the end of `### Agent Runtime
Security & Sandboxing` (entries are not alphabetical), in its italic format.
PR title: `Add Sabline to Agent Runtime Security & Sandboxing`.

```
* [Sabline](https://github.com/gowrishankar-infra/sabline-lang) - _Programming language for running AI-written scripts under an operator-granted budget: each function declares the effects it may use (files, hosts, environment, clock, randomness, Python modules), and the runtime refuses any operation outside the budget. OS confinement underneath (full on Linux, partial on macOS and Windows). MIT._
```

## 4. scadastrangelove/awesome-ai-security-tools - WATCHLIST.md, not the README

Its rules send "very new repositories, zero-star projects" to `WATCHLIST.md`
first, and ask for descriptions that are "factual, one sentence long". A
repository created in August 2026 with three stars goes there. PR title:
`Add Sabline to WATCHLIST.md`.

```
- [Sabline](https://github.com/gowrishankar-infra/sabline-lang) — MIT programming language, Python CLI, and MCP server for running AI-written scripts under an operator-written effect budget: functions declare the files, hosts, environment variables, clock, randomness, and Python modules they may use, and the interpreter refuses any operation outside the granted budget when it is attempted, with Z3-checked contracts and SARIF and in-toto audit output. Watch because the repository was created in August 2026 with three stars and a single maintainer; the project's own threat model says enforcement is an interpreter in the program's own process rather than a security boundary, with operating-system confinement beneath it complete on Linux and partial on macOS and Windows.
```

## 5. punkpeye/awesome-mcp-servers - blocked until Sabline is on Glama

A bot checks every pull request: the server must be listed on Glama and pass
its checks (a Dockerfile added in Glama that starts the MCP server,
`python -m sabline_mcp`, and answers introspection - the repository's own
Dockerfile runs the CLI instead), and the line must carry Glama's score
badge. Sabline is not on Glama (404, 2026-09-25). After it is, under
`👨‍💻 Code Execution`, alphabetically between
`fstandhartinger/sandbox-as-a-service-mcp` and `gwbischof/outsource-mcp`,
with the badge path Glama assigns. PR title:
`Add gowrishankar-infra/sabline-lang server`.

```
- [gowrishankar-infra/sabline-lang](https://github.com/gowrishankar-infra/sabline-lang) 🐍 🏠 🍎 🪟 🐧 - Write, check, audit and run Sabline programs under an effect budget: each function declares the files, hosts, environment, clock, randomness and Python modules it may use, the operator grants a narrow budget (`--allow io,fs:read:./data`), and the runtime refuses anything else when it is tried. `pip install sabline-lang` [![gowrishankar-infra/sabline-lang MCP server](https://glama.ai/mcp/servers/gowrishankar-infra/sabline-lang/badges/score.svg)](https://glama.ai/mcp/servers/gowrishankar-infra/sabline-lang)
```

## 6. mcpservers.org (wong2/awesome-mcp-servers)

"We do not accept PRs": a web form on mcpservers.org. Free review takes up
to two weeks; the paid option is not needed. Name: Sabline. URL:
https://github.com/gowrishankar-infra/sabline-lang. Description: the
headline and the sentence after it, as every listing now opens.

## Considered and left out

- **restyler/awesome-sandbox** - outside pull requests sit unmerged and the
  maintainer adds entries from issues; if you open one, say it is a
  language-level budget, not a VM or container sandbox.
- **dckc/awesome-ocap** - about object capabilities; a Sabline effect is a
  name in a signature and a budget is ambient to a run (the paper's related
  work says so). Submitting there would invite the correction.
- **analysis-tools-dev/static-analysis** - requires six months' age, 20
  stars and more than one contributor; not before 2027.
- **appcypher/awesome-mcp-servers** (archived), **e2b-dev/awesome-ai-agents**
  (assistants and agents only), **corca-ai/awesome-llm-security** (no merge
  since 2025-08), **TalEliyahu/Awesome-AI-Security** (220+ stars).
