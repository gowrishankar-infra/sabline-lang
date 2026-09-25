# Sabline: where to submit, and each venue's own rules

Research date: 2026-09-25. Everything below comes from each venue's own pages, loaded on that date with `gh api`, curl, or WebFetch. Where a page was blocked, rate-limited, or rendered only by JavaScript, the entry says so and nothing is guessed. Nothing was submitted, posted, or opened.

**Sabline facts used below** (checked 2026-09-25):
- **Repository:** `gowrishankar-infra/sabline-lang`, created 2026-08-16 (so about 40 days old), with 3 stars and 0 forks.
- **Contributors:** 1 human plus `github-actions[bot]`.
- **Licence and releases:** MIT. The latest release is v8.6.0 (2026-09-21); v9.0.0-alpha.4 is a pre-release.
- **MCP registry:** listed as `io.github.gowrishankar-infra/sabline` v8.6.0, status active.
- **Glama:** not listed (https://glama.ai/mcp/servers/gowrishankar-infra/sabline-lang returns 404).
- **README caveat:** the README says Sabline is "Not a security boundary by itself". Operating-system confinement is "fully on Linux, partly on macOS and on Windows". Every draft below respects that.

These age, star and contributor numbers decide several venues. See the "Excluded" table in section A.

---

## A. Awesome lists and catalogues

### Summary: the 8 best fits

| # | Venue | Stars | Last commit | How to submit | Blocker for Sabline today |
|---|---|---|---|---|---|
| A1 | agentlanguages.dev (aallan/agentlanguages) | 18 | 2026-09-21 | PR adding one `.md` file | None. A local scaffold already exists (see A1) |
| A2 | punkpeye/awesome-mcp-servers | 95,495 | 2026-09-23 | PR to README.md | **Must be listed on Glama first, with the score badge** |
| A3 | mcpservers.org (wong2/awesome-mcp-servers) | 4,323 | 2026-07-13 | Web form only ("We do not accept PRs") | None |
| A4 | ChessMax/awesome-programming-languages | 836 | 2026-09-21 | PR to README.md | None |
| A5 | ottosulin/awesome-ai-security | 1,497 | 2026-09-24 | PR (or contact on Mastodon) | None stated; 100+ open PRs |
| A6 | scadastrangelove/awesome-ai-security-tools | 1,537 | 2026-09-21 | PR to `data/sections.json` or `WATCHLIST.md` | Young, low-star repos go to **WATCHLIST.md first** |
| A7 | dckc/awesome-ocap | 414 | 2026-08-12 | PR to README.md | Fit risk: the list is about object capabilities (see A7) |
| A8 | restyler/awesome-sandbox | 585 | 2026-08-12 | Issue or PR | PRs sit unmerged; the maintainer adds entries from issues |

---

### A1. agentlanguages.dev: a catalogue of AI-first languages

- **Read:**
  - https://github.com/aallan/agentlanguages: `CONTRIBUTING.md`, `.github/PULL_REQUEST_TEMPLATE/new_language.md`, `src/content.config.ts` (the Zod schema) and the entries `boruna.md`, `thermite.md`, `vera.md`, `ailang.md` and `semaprax.md`. All via `gh api`, 2026-09-25.
- **Activity:**
  - 18 stars, created 2026-05-20, last commit 2026-09-21 ("chore: refresh GitHub star counts").
  - Recent outside submissions were merged: #54 SEMAPRAX (2026-09-05), #48 Modula-9, #45 reqlan and #44 Faber Romanus.
- **Licence of entries:** "Content in this repository, which includes language entries, is licensed CC BY 4.0; code is MIT. By opening a pull request you agree to your contribution being published under those terms. You keep the copyright in what you write."
- **Inclusion criterion** (verbatim): "A project qualifies if it is **designed for LLMs/agents to author code**." The signals listed include:
  - "Mechanically checkable contracts — refinement types, requires/ensures clauses, SMT verification"
  - "Agent-coordination primitives — capability-gated effects, deterministic replay, approval gates"
  - "Agent-facing tooling shipped with the compiler — SKILL.md, AGENTS.md, CLAUDE.md, structured-JSON diagnostics, MCP servers"
  
  Out of scope: "A tool that *uses* an LLM at runtime". **Sabline qualifies, and nothing excludes it.** No minimum stars or age. The file says under "What we never ask for": "Star counts, fork counts, commit counts" are fetched weekly and must not be hardcoded.
- **How to submit:**
  1. "Fork the repository."
  2. "Add one Markdown file under `src/content/languages/<slug>.md`… lowercase, hyphen-separated, no spaces."
  3. Write a body.
  4. "Open a pull request using the new-language template."
  
  The template is `.github/PULL_REQUEST_TEMPLATE/new_language.md`. On GitHub it is selected by adding `?template=new_language.md` to the compare URL.
- **Schema, as enforced by `content.config.ts`:**
  - `camp` is one of `syntactic | verification | orchestration | adjacent | unclassified`, and `spans_camps` is optional.
  - **`one_liner`: 10–280 characters.**
  - `url` must be a URL. `repo` is `owner/name` or null. `paper` is a URL or null.
  - `author`, `implementation_language`, `compilation_target` and `license` are strings.
  - `maturity` is one of `thought_experiment | research_paper | early_implementation | working_compiler | production_ready`.
  - `date_appeared` must match `YYYY-MM`.
  - `agent_tooling` is a list of strings. `key_idea` is a string.
  - Optional: `benchmark {label, url}`, `crossrefs [{slug, name, camp, relation}]` and `history [{when, what}]`.
  - A crossref `slug` that names no entry fails the build (PR #50).
- **PR template checklist** (verbatim):
  - "The project is designed for **LLMs or agents to author code**…"
  - "One Markdown file added at `src/content/languages/<slug>.md`…"
  - "Frontmatter validates against the Zod schema in `src/content.config.ts` (the build will fail if it doesn't)"
  - "One-liner is descriptive and neutral, not promotional"
  - "No star counts, fork counts, version numbers, or commit counts hardcoded"
  - "Self-classified camp with justification in the PR body below"
  
  The PR body also asks for: Name, URL, Repo, Camp, and a "Justification" of "Two or three sentences".
- **Body:**
  - "200 or more words with first-hand familiarity, covering the design DNA, how the language compares to its neighbours here, and where it strains under real use."
  - House headings: `## The thesis.` (or `## What it is.`), `## What it looks like.`, `## Distinctive moves.`, `## Maturity.`, `## Agent tooling.`
  - Code samples and pullquotes go inline as raw HTML, never in frontmatter. Do not leave a blank line inside `<pre>`.
- **Tone:** "Descriptive, not promotional… The word 'elegant' is almost always wrong; 'explicit', 'verified', 'deterministic' are usually right."
- **Review:** the maintainer reviews for fit, accuracy and tone. "Expect an editorial pass… British-English and house-style corrections, and scoping a claim to what the code supports."
- **Example one-liners** (verbatim):
  - Boruna (orchestration): `"Deterministic, capability-safe workflow execution. Every effect declared, policy-gated. Hash-chained tamper-evident evidence bundles."`
  - Vera (verification): `"Mandatory contracts on every function. Z3 SMT verification with a runtime-check fallback. Typed slot references replace variable names. LLM inference is a first-class typed effect."`
  - AILANG (verification): `"Row-polymorphic Hindley-Milner with capability-based effects (IO, FS, Net, Clock, AI). No loops, lambda calculus only. Written autonomously by AI agents."`
- **Where the Sabline entry stands:** the local fork at `D:\agentlanguages`, branch `add-sabline`, has commit `9d7ca05`, "Scaffold: Sabline (verification camp) - every prose field a TODO". Nothing is pushed and there is no PR.
  - Factual fields are filled: `camp: verification`, `spans_camps: [orchestration]`, `maturity: working_compiler` and `date_appeared: 2026-08`.
  - Crossrefs are scaffolded for vera, thermite, ailang and boruna.
  - The scaffold says the prose is the owner's to write.
- **Draft `one_liner`, only if wanted.** It is 262 characters, under the 280 cap, and written in the house fragment style:
  > `"Effects declared in every signature and checked across the call graph. An operator-written run budget (paths, hosts, modules, call counts) refused at the operation. Z3 proofs of contracts with a runtime-check fallback. A committed capability baseline held in CI."`

---

### A2. punkpeye/awesome-mcp-servers

- **Read:** `CONTRIBUTING.md`, `README.md` and `.github/workflows/check-glama.yml`, via `gh api`, 2026-09-25.
- **Activity:** 95,495 stars. Last commit 2026-09-23 ("Merge pull request #14910"). Actively merging.
- **Scope** (verbatim): "This list is for servers with a public GitHub repository — something you install and run yourself." Sabline's stdio server installed from PyPI fits.
- **Rules from CONTRIBUTING.md** (verbatim):
  - "Edit the `README.md` file… When adding a new server, make sure to include: The server name, linked to its repository. A brief description of the server's functionality. Categorize the server appropriately under the relevant section."
  - "**Alphabetical order:** Maintain alphabetical order within each category of servers."
  - "**One server per line**"
  - "**Clear descriptions:** Write concise and informative descriptions for each server."
  - The commit-message example is `git commit -m "Add new XYZ server"`.
  - "Provide a clear title and description of your changes in the pull request."
  - A note: "If you are an automated agent… add `🤖🤖🤖` to the end of the PR title to opt-in." This is only for PRs opened by agents.
- **Rules the bot enforces (`check-glama.yml`)** on every PR:
  1. **Glama listing and badge.** The bot's comment, verbatim:
     > "1. Ensure your server is listed on Glama. If it isn't already, submit it at https://glama.ai/mcp/servers and verify that it passes all checks (note: you must add Dockerfile directly to Glama. For checks to pass, we only need the server to start and respond to introspection requests). 2. Update your PR by adding a Glama score badge after the server description, using this format: `[![OWNER/REPO MCP server](https://glama.ai/mcp/servers/OWNER/REPO/badges/score.svg)](https://glama.ai/mcp/servers/OWNER/REPO)`"
  2. **Emoji.** The line needs at least one permitted emoji, and only permitted ones:
     - 🎖️ official implementation
     - 🐍 Python, 📇 TypeScript/JS, 🏎️ Go, 🦀 Rust, #️⃣ C#, ☕ Java, 🌊 C/C++, 💎 Ruby
     - ☁️ Cloud, 🏠 Local, 📟 Embedded
     - 🍎 macOS, 🪟 Windows, 🐧 Linux
  3. **Link text** must be the full `owner/repo`, not just the repo name.
  4. **The first link must be `https://github.com/...`.** Remote-only servers belong in `awesome-remote-mcp-servers`.
  5. **No duplicates.**
- **Blocker today:** Sabline is **not on Glama** (the page above returned 404 on 2026-09-25).
  - Glama's "Add Server" is a JavaScript button on https://glama.ai/mcp/servers. I did not load the flow, and it may need an account.
  - The repo's `Dockerfile` runs the `sabline` CLI. Glama needs a Dockerfile, added in Glama, that starts the **MCP server** (`python -m sabline_mcp`) and answers introspection.
- **Section:** "👨‍💻 Code Execution". Its heading text is "Code execution servers. Allow LLMs to execute code in a secure environment, e.g. for coding agents." 🔒 Security is the alternative.
  - Alphabetical position: between `fstandhartinger/sandbox-as-a-service-mcp` and `gwbischof/outsource-mcp`.
- **Existing entries** (verbatim, from Code Execution):
  ```
  - [fstandhartinger/sandbox-as-a-service-mcp](https://github.com/fstandhartinger/sandbox-as-a-service-mcp) 🎖️ 📇 ☁️ – Give an agent a real Linux VM: run commands, move files, expose a preview URL, destroy it. Own kernel and dedicated VM per sandbox, never shared with another tenant, so untrusted model-generated code stays contained. [![fstandhartinger/sandbox-as-a-service-mcp MCP server](https://glama.ai/mcp/servers/fstandhartinger/sandbox-as-a-service-mcp/badges/score.svg)](https://glama.ai/mcp/servers/fstandhartinger/sandbox-as-a-service-mcp)
  - [mavdol/capsule/mcp-server](https://github.com/mavdol/capsule/tree/main/integrations/mcp-server) [![capsule-mcp-server MCP server](https://glama.ai/mcp/servers/mavdol/capsule-mcp-server/badges/score.svg)](https://glama.ai/mcp/servers/mavdol/capsule-mcp-server) 🦀 🏠 🍎 🪟 🐧 - Run untrusted Python/JavaScript code in WebAssembly sandboxes.
  - [hileamlakB/PRIMS](https://github.com/hileamlakB/PRIMS) 🐍 🏠 – A Python Runtime Interpreter MCP Server that executes user-submitted code in an isolated environment.
  ```
- **Draft line.** Replace the Glama path with the one Glama assigns. The badge goes after the description, as the bot asks.
  ```
  - [gowrishankar-infra/sabline-lang](https://github.com/gowrishankar-infra/sabline-lang) 🐍 🏠 🍎 🪟 🐧 - Write, check, audit and run Sabline programs under an effect budget: each function declares the files, hosts, environment, clock, randomness and Python modules it may use, the operator grants a narrow budget (`--allow io,fs:read:./data`), and the runtime refuses anything else when it is tried. `pip install sabline-lang` [![gowrishankar-infra/sabline-lang MCP server](https://glama.ai/mcp/servers/gowrishankar-infra/sabline-lang/badges/score.svg)](https://glama.ai/mcp/servers/gowrishankar-infra/sabline-lang)
  ```
  - PR title / commit: `Add gowrishankar-infra/sabline-lang server`

---

### A3. mcpservers.org (the site for wong2/awesome-mcp-servers)

- **Read:**
  - https://github.com/wong2/awesome-mcp-servers: README and `.github/pull_request_template.md`, via `gh api`.
  - https://mcpservers.org/submit: curl, HTTP 200, the form is in the static HTML. Both 2026-09-25.
- **Activity:** 4,323 stars; last commit 2026-07-13.
- **Rule** (verbatim, README top): "**We do not accept PRs. Please submit your MCP on the website: https://mcpservers.org/submit**". The old PR template had a single item: "Place the newly added server in the right position alphabetically."
- **Form fields as read:**
  - **Server Name** (required; placeholder "e.g., Figma MCP")
  - **Category** (required select): Development, Productivity, Database, Search, Web Scraping, File System, Version Control, Communication, Cloud Service, Cloud Storage, Marketing, Finance, Design, Memory, Other. There is no Security category.
  - **Short Description** (required; placeholder "What does your server help people do?"; no maxlength in the HTML)
  - **Repository, Website or Documentation** (required URL, `maxLength=512`)
  - **Official MCP Registry Name** (optional, placeholder `io.github.example/my-server`, `maxLength=200`)
  - "This server supports remote connections" (checkbox)
  - **Contact Email** (required)
  - **Submission plan:** "Free $0 Review within 2 weeks." or "Premium Submit $39 one-time review fee Review within 24 hours. Official badge & priority in search results. Dofollow link (DR 71)." The page states "Listings on mcpservers.org are free."
- **Draft values:**
  - **Server Name:** `Sabline`
  - **Category:** `Development`
  - **Short Description** (30 words): `Lets an AI client write, check, audit and run Sabline programs, where each function declares what it may touch and the runtime refuses anything outside the budget the operator granted.`
  - **Repository:** `https://github.com/gowrishankar-infra/sabline-lang`
  - **Official MCP Registry Name:** `io.github.gowrishankar-infra/sabline`
  - **Remote:** leave unchecked (stdio only)
  - **Plan:** Free

---

### A4. ChessMax/awesome-programming-languages

- **Read:** README.md, PR #529 and PR #533 (body and diff), and the commit log, via `gh api` / `gh pr`, 2026-09-25. There is no CONTRIBUTING and no `.github` folder (404).
- **Activity:** 836 stars. Last commit 2026-09-21. Five outside PRs were merged that day, including #529 "NOVA — capability + effect-typed research-preview language".
- **Rules:** none written beyond the README intro. The intro says, verbatim: "Here you can find interesting programming languages that are not well known or promote your own programming language… Feel free to make a contribution." Self-submission is therefore explicitly welcome. There is no star or age gate.
- **Conventions the merged PRs follow:**
  - Entries are alphabetical within a letter section.
  - Each letter header carries a count, e.g. `# S (56):`, and line 2 carries the total, currently `The list of **965** programming languages`. PR #529 bumped both its letter count and the total. The maintainer also fixes counts after merges.
  - An optional trailing tag such as `[AI]` is used by 6 AI-oriented entries.
- **Section:** `# S`, as the first entry, since "Sabline" sorts before "SaC".
- **Example entries** (verbatim):
  ```
  - [NOVA](https://github.com/ieeecsopen/NOVA) - NOVA is a constraint-native research-preview language unifying object-capability security and row-typed effect systems: authority to touch the outside world is an unforgeable token passed explicitly, and a function's effects are part of its checked type signature, so a closure cannot silently launder captured capability into a context that expects a pure function.
  - [Sema](https://sema-lang.com) - Sema is a Lisp with first-class LLM and agent primitives, implemented in Rust on a bytecode VM. It pairs a Scheme-style core (define, lambda, cond) with Clojure-flavored data literals (maps, vectors, keywords, short lambdas), pattern matching, async, and built-in HTTP/JSON, plus LSP/DAP tooling and a WASM browser playground. [AI]
  - [Semaprax](https://wavect.io/semaprax/) - An experimental agent-native systems programming language built around a stable semantic program graph. Its v0.2 prototype supports typed semantic queries, revision-bound semantic patches, and verified native and browser/Wasm subsets. [Source](https://github.com/wavect/semaprax). [AI]
  ```
- **Draft line:** add it directly under `# S (56):`, change that header to `# S (57):`, and change `**965**` to `**966**`. Re-check both numbers at PR time.
  ```
  - [Sabline](https://github.com/gowrishankar-infra/sabline-lang) - Sabline is a language for scripts an AI writes. Each function's signature declares the effects it may use (files, network hosts, environment variables, clock, randomness, Python modules); the person running it grants a narrower budget (a folder, a host, a number of calls), and the interpreter refuses any operation outside that budget at the moment it is attempted. Contracts are proven with Z3 where possible and checked at run time otherwise. Formerly Velaris. [AI]
  ```
  - PR title, in the style of the merged ones: `Add Sabline`.
  - PR body, in the style of #529: one line naming the section and alphabetical position and saying the counts were bumped. Then 2–3 sentences, including an honest status line: not a security boundary by itself, and OS confinement is full on Linux only.

---

### A5. ottosulin/awesome-ai-security

- **Read:** README.md, the PR list, and the closed PRs #469/#470, via `gh`, 2026-09-25. There is no CONTRIBUTING and no `.github`.
- **Activity:** 1,497 stars. Last commit 2026-09-24.
  - More than 100 PRs are open.
  - Outside PRs merged in September: #443, #440, #438, #426 and #423 (Doberman, into Agent Runtime Security & Sandboxing).
  - Some PRs were closed with no comment (#469, #470, closed 2026-09-24).
- **The only written rule** (verbatim, README line 5): "If you want to contribute, create a PR or contact me [@ottosulin](https://mastodon.social/@ottosulin)." The list carries the sindresorhus Awesome badge. No stars or age gate is stated.
- **Format:** `* [Name](url) - _Description._` with the description in italics. The section is not alphabetical: new entries are appended at the end.
- **Section:** `### Agent Runtime Security & Sandboxing`, under "Defense & Security Controls". Append it after the last entry, currently Numbat.
- **Example entries** (verbatim):
  ```
  * [Agent Safehouse](https://github.com/eugene1g/agent-safehouse) - _macOS sandbox for LLM coding agents using sandbox-exec with composable policy profiles and a deny-first model._
  * [leash](https://github.com/strongdm/leash) - _Leash wraps AI coding agents in containers and monitors their activity._
  * [Doberman](https://github.com/DobermanCore/Doberman-Core) - _Runtime authorization layer between a coding agent and its tools. A local policy engine gives every tool call an allow/authenticate/block verdict before it executes; blocks carry reason codes, logs redact secrets to HMAC fingerprints, and errors fail closed. Ships an MCP proxy plus Claude Code and Codex adapters. Apache-2.0._
  ```
- **Draft line:**
  ```
  * [Sabline](https://github.com/gowrishankar-infra/sabline-lang) - _Programming language for running AI-written scripts under an operator-granted budget: each function declares the effects it may use (files, hosts, environment, clock, randomness, Python modules), and the runtime refuses any operation outside the budget. OS confinement underneath (full on Linux, partial on macOS and Windows). MIT._
  ```
  - Suggested PR title, in the form most merged PRs use: `Add Sabline to Agent Runtime Security & Sandboxing`

---

### A6. scadastrangelove/awesome-ai-security-tools

- **Read:** `CONTRIBUTING.md`, `WATCHLIST.md` and `data/sections.json`, plus the PR list, via `gh api`, 2026-09-25.
- **Activity:** 1,537 stars. Last commit 2026-09-21 ("Expand candidate metadata and curate new tools"). The maintainer curates in batches: PRs #117–#121 were closed and their tools appear in WATCHLIST.md in the maintainer's own wording.
- **Rules** (verbatim):
  - "Please edit `data/sections.json`, not the generated `README.md`."
  - "Prefer real, installable, public projects over blog-only announcements."
  - "Keep descriptions factual, one sentence long, and specific about what the tool does."
  - "Use `status: ["open_source"]` for public-source / open-source projects."
  - "Add a caveat flag and/or `note` when the project has a restrictive, non-commercial, unclear, missing, or copyleft license."
  - "**Very new repositories, zero-star projects, and projects without a clear root license may be tracked in `WATCHLIST.md` first instead of the main README**; they can graduate once license, adoption, and maintenance signals are clearer."
  - "do not add live per-entry badge URLs"
  - "do not paste badge Markdown by hand"
- **What this means for Sabline:** created August 2026, with 3 stars and 1 maintainer, it will almost certainly go to **WATCHLIST.md**. Submit there directly.
- **Section, if it later graduates:** "AI Agent & Coding-Agent Security" → "Runtime Protection & Enforcement".
- **Example WATCHLIST entries** (verbatim, abridged only where marked):
  ```
  - [Ratchet](https://github.com/suhui-organization/ratchet) — Apache-2.0 Go CLI and MCP server that inventories configured MCP servers, optionally enumerates their tools, and compiles reasoned allow, approve, or deny policy artifacts with a verifiable delivery manifest. Watch because the repository was created in September 2026 with no stars or independent adoption; capability classification is heuristic, the tool does not enforce or sandbox calls, and its optional introspection mode starts the configured MCP servers rather than performing a purely static scan.
  - [prompt-protection](https://github.com/mughalhere/prompt-protection) — MIT zero-dependency TypeScript library that labels untrusted tool data and applies caller-supplied source, destination, and sink policy before selected agent tool calls. Watch because the project has three stars and limited independent adoption; protection is a cooperative in-process wrapper rather than a sandbox, […]
  ```
- **Draft WATCHLIST.md line.** Its "Watch because" clause states the project's own caveats, in the style the maintainer uses:
  ```
  - [Sabline](https://github.com/gowrishankar-infra/sabline-lang) — MIT programming language, Python CLI, and MCP server for running AI-written scripts under an operator-written effect budget: functions declare the files, hosts, environment variables, clock, randomness, and Python modules they may use, and the interpreter refuses any operation outside the granted budget when it is attempted, with Z3-checked contracts and SARIF and in-toto audit output. Watch because the repository was created in August 2026 with three stars and a single maintainer; the project's own threat model says enforcement is an interpreter in the program's own process rather than a security boundary, with operating-system confinement beneath it complete on Linux and partial on macOS and Windows.
  ```
  - PR title, as others use: `Add Sabline to WATCHLIST.md`

---

### A7. dckc/awesome-ocap: "Awesome Object Capabilities and Capability-based Security"

- **Read:** `CONTRIBUTING.md` and README.md, plus merged PRs #36 (Cadence) and #67 (Tenuo), via `gh`, 2026-09-25.
- **Activity:** 414 stars. Last commit 2026-08-12 (#76 merged). The maintainer opened #78 on 2026-09-20. The latest outside additions were #68 (2026-02) and #67 Tenuo (2026-01), described as "Capability-based authorization for AI agents".
- **Rules** (verbatim, CONTRIBUTING.md):
  - "Sections are ordered in increasing effort / investment…"
  - "Emphasis is on active projects, preferably with dated items that show recent progress."
  - "The format of a typical entry is: `- YYYY-MM: [Title of linked doc](url-of-linked-doc) "exerpt..."` and/or `- YYYY-MM: [Title of linked doc](url-of-linked-doc) summarized news...`"
  - "All I/O, randomness, clock, etc. should be injected explicitly to each module level function. Each function / method should get the least authority that it needs." This is under "Coding style", for code in the repo.
- **Section:** `## Programming Languages`, which currently holds Pony, Austral, Newspeak, Monte and Cadence.
- **Fit risk:** the list's centre is *object* capabilities, meaning authority carried by unforgeable references.
  - Sabline instead *declares* effects in signatures and *grants* a per-run budget. That is least authority, but not ocap references. A strict ocap maintainer may judge it off-topic.
  - The list's title does include "Capability-based Security", and Tenuo (a least-privilege tool for AI agents) was accepted.
  - Say plainly in the PR which model Sabline uses.
- **Example entries** (verbatim):
  ```
    - [Austral](https://austral-lang.org/) - a systems language with linear types and capability security
      - 2022-09: [Release 0\.1\.0: Core language complete](https://github.com/austral/austral/releases/tag/v0.1.0)

    - [Cadence](https://developers.flow.com/cadence) is a smart contract language with resources (linear types) and capability security.
      Its static type system has direct support for object-capability security. For example, the facade pattern is natively supported, and the type system has special down-casting rules to express access control patterns.
  ```
- **Draft entry** (the release tags and dates are checked):
  ```
    - [Sabline](https://sabline.dev/) is a language for scripts written by AI models. A function's signature names the effects it may use (files, network, environment, clock, randomness, Python modules), and whoever runs the program grants a narrower budget - a folder, a host, a module, a number of calls - which the runtime enforces at each operation. Authority is declared and granted per run rather than passed as object references.
      - 2026-09: [v8.4.0](https://github.com/gowrishankar-infra/sabline-lang/releases/tag/v8.4.0) asks the OS to hold the same budget (Landlock and seccomp on Linux; partial on macOS and Windows)
      - 2026-09: [v8.6.0](https://github.com/gowrishankar-infra/sabline-lang/releases/tag/v8.6.0) renamed from Velaris
  ```

---

### A8. restyler/awesome-sandbox: "Awesome Code Sandboxing for AI"

- **Read:** README.md, the commit log and the PR list, via `gh`, 2026-09-25.
- **Activity:** 585 stars. Last commit 2026-08-12.
  - Six outside PRs are open (#25, #28–#30, #32–#34, from 2026-08-22 onward) and none has been merged since.
  - The maintainer's commit on 2026-08-12 was "Add Koyeb Sandboxes and Amazing Sandbox **from issue tracker**".
- **Rule** (verbatim, "8. Contributing"): "This is a living document… If you see inaccuracies, have experience with these or other platforms, or want to suggest additions, please open an issue or submit a pull request."
- **Route:** open an **issue**, which is how recent additions actually landed.
- **Format:** a long-form profile, `### 4.N. Name: subtitle`, with these bullets:
  - **Overview**
  - **GitHub**
  - **Website**
  - **Launch Date**
  - **GitHub Stars**
  - **License**
  - **Hosting** (SaaS / Self-Hosted)
  - **Capabilities** (Filesystem Access / Network Access / Workload Suitability)
  - optionally **Unique Value Proposition**
  - plus a feature-matrix row
- **Fit:** the guide covers isolation technologies (microVMs, gVisor, WASM, containers) and local wrappers such as Amazing Sandbox and nono. Sabline's language-level budget plus OS confinement is adjacent to those. The nearest section is "2.3 Language Runtimes".
- **Example** (verbatim, abridged to the first three bullets):
  ```
  ### **4.17. Amazing Sandbox: A Local CLI Wrapper Over OS-Native Sandboxing**

  * **Overview:** Amazing Sandbox (`asb`) is a small CLI that runs a given command, package manager, or coding agent inside whatever sandboxing primitive is native to your OS: Docker by default, Seatbelt on macOS, or Bubblewrap on Linux. […]
  * **GitHub:** [ashishb/amazing-sandbox](https://github.com/ashishb/amazing-sandbox)
  * **Website:** [ashishb.net/programming/amazing-sandbox](https://ashishb.net/programming/amazing-sandbox/)
  ```
- **Draft issue body:**
  > **Suggest: Sabline — a language whose runtime refuses effects outside an operator-granted budget**
  > * **Overview:** Sabline is a small language for scripts an AI writes. Each function declares what it may touch (files, hosts, environment, clock, randomness, Python modules); the operator grants a narrow budget (`--allow io,fs:read:./data,net:api.example.com:443@100`) and the interpreter refuses anything outside it at the moment it is attempted. From 8.4 the OS is asked to hold the same budget underneath.
  > * **GitHub:** gowrishankar-infra/sabline-lang · **Website:** sabline.dev · **Launch Date:** first commit August 2026 · **License:** MIT
  > * **Hosting:** Self-hosted only (`pip install sabline-lang`, npm wrapper, Docker image, MCP server)
  > * **Filesystem Access:** only the `fs:read:`/`fs:write:` paths granted; on Linux held by Landlock, on macOS writes held by a sandbox profile, on Windows only a no-write budget is held.
  > * **Network Access:** none without `net`; host names are checked by the interpreter, and TCP ports by Landlock ABI 4+ on Linux.
  > * **Workload Suitability:** short, one-off runs of generated scripts. It is not a VM or container boundary: the project's own threat model says the in-process interpreter is not a security boundary by itself.

---

### Also considered: msyvr/awesome-agent-sandboxes (5 stars, last commit 2026-09-04)

- **Read:** README.md, `docs/strategy-update-2026-04-25.md`, and `data/sandboxes.yaml`/`excluded.yaml` headers, via `gh api`.
- **Route:** "Edit `data/sandboxes.yaml` — follow the existing schema… Run `python scripts/generate_readme.py`… Open a PR."
- **Bar** (verbatim): policy-layer tools "enforced via hooks, rules, or application-level controls rather than kernel enforcement… don't meet our sandbox bar (no OS-level isolation)".
  - Sabline's 8.4 confinement (Landlock+seccomp, `sandbox_init`, and a Windows job object) may clear this bar. The maintainer decides after reading the code, as happened with "vetto" ("the isolation code was read before inclusion").
  - The vocabulary includes `landlock`, `seccomp`, `seatbelt` and `process`.
- **Verdict:** a small audience; optional.

### Excluded, with each venue's own reason

| Venue | Why Sabline does not go there now |
|---|---|
| appcypher/awesome-mcp-servers | **Archived** (last commit 2026-05-06). |
| e2b-dev/awesome-ai-agents (30k stars) | "This list is only for AI assistants and agents." It points SDKs and tools to e2b-dev/awesome-ai-sdks, which has had no content change since 2025-02 apart from UTM edits. |
| corca-ai/awesome-llm-security | Last merge 2025-08-20 (#54), with 100+ PRs open. **Effectively unmaintained.** |
| analysis-tools-dev/static-analysis | CONTRIBUTING: "each tool must have existed for at least six months; have at least 20 stars on GitHub; have more than one human contributor". Bots don't count. "The CI bot will politely close pull requests" that fail. **Sabline fails all three.** The earliest possible date is about 2027-02-16, and only with 20+ stars and a second human contributor. The format then would be `data/tools/<name>.yml`, a description of at most 500 characters, and `ai-generated-code` / `security` tags. |
| TalEliyahu/Awesome-AI-Security | README Tools section: "must have **220+ GitHub stars**, **active maintenance in the last 12 months**, and **≥3 contributors**." **Excluded.** Every outside PR since 2026-09-02 (#141–#153) was closed. |
| Puliczek/awesome-mcp-security (737 stars) | Its only real merge since 2025-12 was #36 (2026-02-08), which was then reverted (#47, 2026-03-03). 100+ PRs are open. **Stalled.** The format would be `- (DD.MM.YYYY) [NAME by Author] (link)`, with "Keep NEW on TOP of section". |
| sindresorhus/awesome | Lists only awesome *lists* ("Adding an awesome list"). A project does not qualify. |
| modelcontextprotocol/servers | README: "If you are looking for a list of MCP servers, you can browse published servers on the MCP Registry… this README is dedicated to housing just the small number of reference servers." Sabline is already in the registry. |
| bureado/awesome-software-supply-chain-security | No written rules. Its theme is attestations, SBOM and SCA. `sabline attest` and SARIF are side features, not the product, so this is a weak fit. |

---

## B. OWASP GenAI Security Project: AI Security Solutions Landscape

- **Pages read** (curl, 2026-09-25, all HTTP 200):
  - https://genai.owasp.org/ai-security-solutions-landscape/ (the directory)
  - https://genai.owasp.org/solution-submission/ (landing page)
  - https://genai.owasp.org/solution-submission-agentic/
  - https://genai.owasp.org/solution-submission-genaillm/
  - https://genai.owasp.org/solution-submission-redteaming/
  - https://genai.owasp.org/initiatives/ai-security-solutions/
  - The Agentic Q2 2026 landscape PDF (https://genai.owasp.org/download/53440/) and the LLM & GenAI Q2 2026 PDF (https://genai.owasp.org/download/53437/)
- **How to submit:** a form on genai.owasp.org's WordPress site. It is not a Google Form, a PR or an email. There is no login; it is protected by reCAPTCHA.
  - **Use the production page:** https://genai.owasp.org/solution-submission-agentic/, reached from https://genai.owasp.org/solution-submission/.
  - The directory's "Submit an Entry" button points at a **staging copy** (`staging-b66e-genaiowasp.wpcomstaging.com/solution-submission/`, marked noindex). I confirmed that link in the directory HTML.
- **Landing page rule** (verbatim, confirmed): "Please provide the requested details in the form. Once submitted the form will be reviewed for accuracy. Be functionally factual in your descriptions. **Please do NOT include competitive positioning, or mention of competitive solutions in your short description. Your submission will be rejected.** We want to ensure the GenAi Security Project's commitment to providing an open and unbiased set of resources for the industry."
- **Three lenses:** "GenAI & LLM Security", "Agentic Security" and "AI Red Teaming". Each is a separate form.
- **Agentic form fields** (* = required):
  - **Submitter Details** (help text: "used for any entry clarification required"):
    - Submitter eMail
    - Submitter Affiliation (End User / Company)
  - **Solution type:** a checkbox group that the page labels "Title \*", with options Open Source / Commercial / Proprietary.
  - **Solution Name \***
  - **Company / Project Name**
  - **Solution Description \*:** a rich-text field. **No maxlength and no word-limit script** (I confirmed there is no `maxlength` in the form HTML).
  - **Solution Link**
  - **Featured Image** (optional)
  - **Github Details:** Stars, Forks (optional)
  - **Lifecycle Stage(s) \*:** Scope & Plan, Augm & Fine Tune Data, Develop & Experiment, Test & Evaluate, Release, Deploy, Operate, Monitor, Govern
  - **Agentic Top 10 Coverage \*:** ASI01:26 to ASI10:26
  - **Capabilities Coverage \*:** checkboxes grouped by stage
  - reCAPTCHA
- **Taxonomy (edition Q2 2026, published 2026-03-17; no Q3 PDF yet):** there are **no product categories** such as "LLM firewall". Solutions are mapped to lifecycle stages, SecOps capability items and Top-10 codes.
- **Recommended mapping for Sabline:**
  - **Lens:** Agentic.
  - **Stages:** **Deploy** and **Operate**, plus **Develop & Experiment**.
    - Deploy PDF text: "…enforce zero-trust comms, rotate ephemeral credentials, set LLM firewalls and allowlists, and apply fine-grained authorization so each agent runs with least privilege…"
    - Develop & Experiment PDF text: "…validate I/O contracts, embed policy hooks…"
  - **Capabilities:**
    - Deploy: "Apply & manage runtime Guardrails", and "Enforce zero-trust policies between agents, tools, & external APIs".
    - Operate: "Runtime guardrails & moderation; anomalous tool use".
    - Test & Evaluation: "Sandboxed testing of all tool calls, code execution, cloud API triggers".
  - **Top 10:** **ASI05 Unexpected Code Execution**, **ASI02 Tool Misuse** and **ASI03 Identity & Privilege Abuse**. Tick only what can be defended as "functionally factual".
- **Length limit:** none stated or enforced.
  - The research agent observed that the directory **card shows only the first 30 words** of a description (all 9 entries it checked were cut at exactly 30 words). I could not re-confirm this from static HTML, so treat it as an observation, not a rule.
  - A 35-word text is accepted, but the card may cut it.
- **Inclusion and cadence:**
  - Open source is allowed. The directory says "a community resource of open source and proprietary solutions", and 38 open-source entries are already listed. Nothing I found requires sponsorship.
  - Cadence (verbatim): "The online database is updated at the end of the month, on a monthly basis. Allowing the project working group to review and accept or reject proposed entries. The solution landscape documents are published on a Quarterly Basis."
- **Draft description, 35 words** (factual, with no competitor mention):
  > Sabline is an open-source (MIT) programming language for AI-written scripts. Each function declares which files, hosts, environment variables, clock, randomness and Python modules it may use; the runtime refuses any operation outside the operator's budget.
- **Draft for the card, 29 words** (if the 30-word cut is real):
  > Open-source (MIT) language for AI-written scripts. Functions declare the files, hosts, environment variables, clock, randomness and Python modules they use; the runtime refuses anything outside the operator's granted budget.
- **Other fields:**
  - Solution type: Open Source
  - Solution Name: Sabline
  - Project: Sabline
  - Link: https://sabline.dev
  - GitHub stars/forks: optional; I would leave them blank while they are 3/0

---

## C. Show HN

- **Pages read** (2026-09-25):
  - https://news.ycombinator.com/showhn.html (200)
  - https://news.ycombinator.com/newsguidelines.html (200)
  - https://news.ycombinator.com/newsfaq.html (200)
  - dang's "tips" comment, item 22336638, which showhn.html links as "these tips". Read via the HN Firebase API (200); it was edited 2026-03-28.
  - https://news.ycombinator.com/showlim returned **HTTP 429 (rate-limited)** on two tries, so I read its Wayback snapshot of 2026-05-12 instead.
  - An HN Algolia search for "sabline", "velaris", "sabline-lang" and "sabline.dev" found **no previous Sabline or Velaris threads**.

**What qualifies** (verbatim, showhn.html):
- "Show HN is for something you've made that other people can play with."
- "The project should be non-trivial. Don't post quickly-generated one-offs; anybody can do that now. Share something that is deeply personal and interesting to you. Explain how and why."
- "The project must be something you've worked on personally and which you're around to discuss."
- "Please make it easy for users to try your thing out, ideally without barriers such as signups or emails." https://sabline.dev/playground.html answered HTTP 200 and needs no sign-up, and `pip install sabline-lang` works too.
- "New features and upgrades ('Foo 1.3.1 is out') generally aren't substantive enough to be Show HNs." This is the first Sabline Show HN, so it is fine. dang adds that a repost of a new version is ok "only if the new version is significantly different… once or twice a year".

**Title** (verbatim):
- "To post, submit a story whose title begins with 'Show HN'."
- The guidelines add: "Please don't do things to make titles stand out, like using uppercase or exclamation points, or saying how great an article is."
- "If the title includes the name of the site, please take it out."
- "don't editorialize."
- I could not load the submit form (it needs a login), so I have not checked the title's character limit myself.
- The usual shape is `Show HN: Sabline – <plain statement of what it is>`.

**Restriction in force:**
- The showlim snapshot (2026-05-12) says, verbatim: "We're temporarily restricting Show HNs because of a massive influx, mostly by users who aren't yet familiar with the site or its culture. You're welcome on HN! Take some time to get to know the community, become a good contributor, and then it will be fine to post an occasional Show HN."
- dang wrote on 2026-03-12 (item 47346735): "we're restricting Show HNs for now."
- The exact thresholds are not published. An account with little history may be refused.

**No LLM-written text.** This matters for any draft:
- The guidelines say: "Don't post generated text or AI-edited text. HN is for conversation between humans."
- dang's tips, edited 2026-03-28, say: "**Write your text by hand. Don't use an LLM to generate any of it (not even a tiny bit, including to edit or spruce it up).**"
- **So I have not drafted the title, the post text or the first comment.** Posting AI-drafted text there would break the venue's own rule. The owner has to write it by hand.

**What dang's tips say the text should cover.** This is a checklist, not prose:
1. The backstory: how you came to work on it and "what's different about it". It goes in the submission text, or as the first comment if it doesn't show at the top.
2. "a clear statement of what your project is or does".
3. "links to any previous HN threads that are relevant". There are none.
4. "Drop any language that sounds like marketing or sales… Use factual, direct language. Personal stories and technical details are great."
5. The honest limits HN will ask about anyway, all from the README: not a security boundary by itself; an in-process interpreter; OS confinement full only on Linux; one maintainer.

**Don'ts** (verbatim):
- "Please don't ask friends to upvote or comment. That's not ok on HN."
- "Can I ask people to upvote my submission? No… We penalize or ban submissions, accounts, and sites that break this rule."
- "Make sure your friends and users do not add booster comments in the thread."
- "Please don't delete and repost."
- "Don't have your username be that of your company or project."
- "Please don't use HN primarily for promotion."
- dang also suggests: "put your email address in your profile so we can contact you… and also so we can send you a repost invite."

---

## D. Newsletters

### tl;dr sec (Clint Gibler)
- **Pages read** (curl, 2026-09-25):
  - https://tldrsec.com/ (200)
  - https://tldrsec.com/about, /submit and /contact: **404**, each redirecting home
  - https://tldrsec.com/c/sponsor (200)
  - Issues https://tldrsec.com/p/tldr-sec-347 (2026-09-24), 346, 344 and 340 (200)
- **There is no submit page, form, or tips address.** The only route stated is the footer of every issue (verbatim): "Have questions, comments, or feedback? **Just reply directly**, I'd love to hear from you." That means replying to an issue email as a subscriber. It continues: "P.S. Feel free to connect with me on LinkedIn". The home page also links twitter.com/clintgibler.
- **Sponsorship is a separate route** ("Reach out to sponsorships AT tldrsec.com") and does not buy editorial coverage (verbatim): "Sponsorship blurbs will be contained in a clearly demarcated section, and sponsoring an issue does not give any influence over the rest of the newsletter." Also: "tl;dr sec will not officially endorse a company, product, or job description."
- **Pitch shape:** no stated rules. The reply goes to one person, so a short factual note with the repo link, what it does, and its limits.

### Console (console.dev): weekly developer-tools newsletter
- **Pages read:** https://console.dev/ (200), https://console.dev/selection-criteria (200); /submit/ and /contact returned 404. The route was re-confirmed by curl.
- **Route** (verbatim): "Submit a tool: Email **hello@console.dev** with the details and we'll happily take a look."
- **Criteria** (verbatim): "The more of these questions we can answer positively, the more likely a tool is to be featured". The questions:
  - Is this interesting and useful to developers?
  - Is the primary user a developer?
  - Is there a self-service signup?
  - Would it form part of a regular-use set of developer tools?
  - Does it make me a better developer?
  - Would advanced power-users use it (API/CLI)?
  - Is it high quality ("multiple platforms… easy to install/deploy? Does it do the job it claims?")?
  - Is it actively maintained?
  - Does it have good documentation?
  - Is it fast?
  - Any negative impact on security or privacy?
  - How would I feel recommending it to friends?
- **Betas slot:** "the release must be pre 1.0… Any GA or stable releases are not eligible". Sabline is at 8.x, so only the "Interesting tools" slot applies.
- **No paid route:** "We do not do sponsored reviews."
- The 2026-09-24 issue featured "Drop — Linux sandboxing" under Security, which suggests the topic fits.

### PyCoder's Weekly (Python audience, which fits the PyPI package)
- **Pages read:**
  - https://pycoders.com/submissions (200)
  - Its "Submit Your Link »" button leads to the public Google Form https://docs.google.com/forms/d/e/1FAIpQLScukOJr68Vb_xoSuxK2iX2t2gv7IlBTniuSHCx9ezW9xK9iyA/viewform (200). A sign-in is offered only "to save your progress".
  - I confirmed the field limits in the form's `FB_PUBLIC_LOAD_DATA_`.
- **Form text** (verbatim): "…while we cannot guarantee to feature every submitted link in the newsletter, we take everything you send us into consideration. [For advertising inquiries, please use the form at https://pycoders.com/advertise]"
- **Fields:**
  - **URL \*** ("No paywalled links, please.")
  - Author
  - **Title / Headline \*: max 220 characters.** Help text: "If you are submitting a coding project (rather than an article) the description field does not get used, so make sure your title encapsulates what your project does."
  - **Description / Summary \*: max 450 characters.** Help text: "Please write a 2-3 sentences…"
  - **Your Name \***; Email and Twitter are optional
- **Drafts:**
  - **URL:** `https://github.com/gowrishankar-infra/sabline-lang`
  - **Title** (149 characters, under the 220 limit): `Sabline: a language for AI-written scripts where each function declares what it may touch and the runtime refuses anything the operator did not grant`
  - **Description** (357 characters, under the 450 limit): `Sabline (MIT, pip install sabline-lang) runs code a model wrote under a budget the operator writes: one folder, one host, a set of Python modules, a number of calls. Functions declare their effects in their signatures, contracts go to Z3, and any operation outside the budget is refused when it is attempted. It also ships an MCP server and a GitHub Action.`

### Help Net Security: "Open source" monthly newsletter (security audience)
- **Pages read:**
  - https://www.helpnetsecurity.com/contact/ (200)
  - https://www.helpnetsecurity.com/newsletter/ (200)
  - https://www.helpnetsecurity.com/2026/03/09/open-source-tool-sage-security-layer-ai-agents/ (200)
- **Route** (verbatim): "Send all news pitches to **press@helpnetsecurity.com**, this is the main point of contact for all types of content and news. We welcome news under embargo… Because of the volume of submissions, we are not able to reply to each one individually, but we do consider everything we receive for publication."
- **What the newsletter covers:** it is described as "Monthly newsletter focusing on open source cybersecurity tools". In March 2026 it covered Sage, an open-source security layer between AI agents and the OS.

**Checked, but no submission route found in static HTML:**
- tldr.tech and tldr.tech/infosec link only to advertising.
- pythonweekly.com, detectionengineering.net, Unsupervised Learning, lastweekin.ai, hackernewsletter.com and news.risky.biz render mostly by JavaScript. I am not claiming whether they accept tips.
- cloudseclist.com offers only a sponsor page.
- **Changelog News** (https://changelog.com/news/submit) needs an account ("Please sign in / up to submit news"). Its last issue listed was #185 on 2026-04-29, so it is probably dormant.

---

## E. Conferences and meetups with open CFPs

- **Method:** every CFP page below was loaded on 2026-09-25 with WebFetch or curl (browser User-Agent). Only events whose CFP page loaded are listed.
- **Spot-checked by me with curl:**
  - Black Hat Asia deadline and LLM rule
  - KubeCon EU (Sessionize: "Call closes at 11:59 PM 11 Oct 2026… (UTC+02:00)")
  - 40C3 ("9 October 2026 (23:59 UTC): Deadline for submissions")
  - BSides Seattle word limits
  - BSides London ("2026-09-30 23:59 (UTC)")
- **The rest** come from a research agent's page reads, with the URLs given.

**Several venues ban or penalise AI-written proposals:**
- Black Hat (verbatim): "LLM‑generated text is prohibited. LLMs may be used solely to edit or refine author‑written material or to assist with reviewing prior art."
- CNCF co-located events: "Please avoid submitting low-effort, AI-generated proposals… 'slop'."
- RSAC: "If you use a large language model for anything other than grammar and spell checking, it will likely make your submission seem more generic."

For that reason no abstracts are drafted here.

### Open now, in deadline order

| Event (dates, place) | CFP URL | Deadline | Fit / track | Length limits and key rules (verbatim where quoted) |
|---|---|---|---|---|
| **BSides London 2026** (12 Dec 2026, London) | https://pretalx.com/bsides-london-2026/cfp | **30 Sep 2026, 23:59 UTC** (5 days) | General; a 15-min "Rookie" track is "for first-time public speakers only… A mentor can be provided" | 45-min main track; 2–4-hour workshops. No abstract limit or vendor rule stated. No travel. |
| **40C3**, Chaos Communication Congress (27–30 Dec 2026, Hamburg) | https://content.events.ccc.de/cfp/40c3/index.en.html; submit at https://cfp.cccv.de/40c3/cfp | **9 Oct 2026, 23:59 UTC** on the content page. The pretalx pages say UTC+1 or Europe/Berlin, so the safe cutoff is 21:59 UTC. | "Security & Hacking" (lists "programming languages") | 60-min slot by default; no character limits stated. "presentations which aim to market or promote commercial products or entities will be rejected without consideration." Free admission; "limited support for travel costs". |
| **RSAC 2027** (5–8 Apr 2027, San Francisco) | https://www.rsaconference.com/usa/call-for-submissions (WebFetch 403; curl with browser headers worked) | **9 Oct 2026, 11:59 PM PT** | Track session (50 min incl. Q&A) or Learning Lab (2 h) | Session detail "Limit 2,500 characters, including spaces"; abstract "Limit 400 characters"; submitter comments 400 characters; bio "Limit 800 characters". "Sales pitches are extremely easy to spot, and our Program Committee quickly eliminates them". "Every year, more than half the speakers are new to RSA Conference." |
| **CactusCon 15** (5–6 Feb 2027, Mesa AZ) | https://www.cactuscon.com/cfp → https://sessionize.com/cactuscon-15 | Page text says **10 Oct 2026**; the Sessionize widget says 16 Oct, 23:59 MST. **Aim for 10 Oct.** | General security | Talks of 20 or 50 min plus 10 min Q&A. "Talk acceptance is not related to sponsorship. Vendor pitches will not be accepted." No travel. |
| **KubeCon + CloudNativeCon EU 2027** (15–18 Mar 2027, Barcelona) | https://events.linuxfoundation.org/kubecon-cloudnativecon-europe/program/cfp/; https://sessionize.com/kubecon-cloudnativecon-europe-2027/ | **11 Oct 2026, 23:59 CEST (UTC+2)** | "Agentic AI" ("agent architectures, MCP… tool integration… identity and security, governance") or "Security" | 30-min session, 5-min lightning talk, 80-min tutorial, poster; at most 3 proposals per speaker; no character limit shown. "no product and/or vendor sales pitches"; "Avoid… discussing unlicensed or potentially closed-source technologies". "we strongly encourage first-time speakers to submit talks." |
| **Black Hat Asia 2027 Summits** (1 Mar 2027, Singapore) | https://www.blackhat.com/html/call-for-sessions.html | **12 Oct 2026, 23:59 SGT** | AI security summit track (seen only in search snippets; the portal is behind Cloudflare, **not verified**) | "Black Hat does not accept product or vendor-related pitches." |
| **DefCamp 2026** (19–20 Nov 2026, Bucharest) | https://sessionize.com/defcamp-2026 | **15 Oct 2026, 23:59 UTC+3** (final wave) | Topics list "agentic AI security", supply chain, SSDLC | No length limits stated; aims at level 300–400. "Ensure there is minimal marketing talk in your content". Travel and hotel covered for speakers from outside Bucharest. |
| **CNCF co-located events EU 2027**: Agentics Day (MCP + Agents) and Open Source SecurityCon (15 Mar 2027, Barcelona) | https://events.linuxfoundation.org/kubecon-cloudnativecon-europe/co-located-events/cfp-colocated-events/; https://sessionize.com/cncf-hosted-co-located-events-europe-2027/ | **18 Oct 2026, 11:59 pm** (the page says "CET", which it gives as UTC+2) | Agentics Day; Open Source SecurityCon ("secure software development, supply chain security, identity and access") | 25-min talk, 35-min panel, 10-min lightning. Same no-pitch rule as the main event, plus the AI-"slop" warning quoted above. |
| **NDC Security 2027** (15–18 Feb 2027, Oslo) | https://ndcsecurity.com/call-for-papers; https://sessionize.com/ndc-security-2027/ | **18 Oct 2026, 23:59 GMT+2** | Topics: "Securing AI", "Agentic AI", "Programming", "Supply Chain", "Secure AI-assisted development", "Security Tooling" | 60-min talks, 10-min lightning, 60–120-min workshops; "Try to limit your submissions to 3-4". Sessionize lists travel and hotel covered. No abstract limit or vendor rule stated. |
| **Black Hat Asia 2027 Briefings** (2–3 Mar 2027, Singapore) | https://www.blackhat.com/call-for-papers.html; prep doc https://i.blackhat.com/asia-27/BHAS27-Call%20for%20Briefings-Preparation-Doc.pdf (the portal returned 403) | **20 Oct 2026, 23:59 SGT (UTC+8)** | "Defense & Resilience" (covers "sandboxing frameworks") or "AI & ML: Attack and Defense" | Abstract "75-300 words"; outline "Max: 4,000 characters"; title 6–10 words with no double quotes or ampersands; slots of 20, 30 or 40 min. "Black Hat does not accept product or vendor-related pitches". "LLM‑generated text is prohibited". "Tool-focused talks should be submitted to Arsenal instead." Coaching required for first-time speakers. $1,000 honorarium plus travel. |
| **DistrictCon Year 2** (6–7 Feb 2027, Washington DC) | https://www.districtcon.org/cfp; https://sessionize.com/districtcon | **30 Oct 2026, 23:59 EDT** | Wants "Tool-release talks" with working code that is "open-source and released to the public" | Talks of 20 or 50 min incl. Q&A. Declines "primers on well-known technologies, vendor pitches, or refactors of old talks". "We especially encourage new presenters to submit talks!" |
| **SCaLE 24x** (1–4 Apr 2027, Pasadena) | https://www.socallinuxexpo.org/scale/24x/cfp | **1 Nov 2026** (no time zone given) | "Security" or "Open Source AI" | About 45-min talks; short and long abstracts with no numeric limit; bio "not more than 1000 characters". "No sales pitches." "We especially welcome new speakers". In person only; no financial help. |
| **BSides Seattle 2027** (5–6 Mar 2027, Redmond) | https://sessionize.com/bsides-seattle-2027 | **1 Nov 2026, 23:59 UTC-8** | "Just Over the Horizon" (AI agents and tooling) | Talks of 25 or 55 min. "Descriptions can be no longer than 150 words. Session details can be no longer than 400 words. Submissions longer than this will be automatically rejected." **Blind review:** "Submission cannot include PII (your name, your company name, your blog post, etc.)", so leave out the project's own links and names. No sales pitches; max 2 submissions. |
| **Black Hat Asia 2027 Arsenal**: open-source tool demos (2–3 Mar 2027, Singapore) | https://blackhat.com/html/arsenal-call-for-tools.html | **2 Nov 2026** (no time zone given) | **The best fit for a tool:** "a space for developers to showcase the latest open source tools" | The submission portal needs JavaScript and a Cloudflare check, so **the field limits were not verified**. Presenters must attend both days; one Briefings pass; travel at your own cost. |
| **CypherCon 10** (24–25 Mar 2027, Milwaukee) | https://sessionize.com/CypherCon2027/ | **9 Jan 2027, 23:59 CST** | Themes "AI failures", "open-source tools", "Live demos" | Lengths, limits and any vendor rule are not stated. No travel or lodging. |
| **BSides Groningen 2027** (9 Apr 2027) | https://sessionize.com/bsides-groningen-2027 | **31 Jan 2027, 23:59 UTC+1** | General | "Submissions deemed to be sales pitches for products/services or marketing campaigns will not be accepted." Length not stated. |

**Lower fit, also open:**
- BSides St. Pete 2027 (https://sessionize.com/bsides-st-pete-2027/): training sessions only; closes 30 Sep.
- BSidesDayton 2027 (https://bsidesdayton.com/submissions/): opens 1 Oct 2026 and closes 20 Mar 2027 at 11:59 PM EST; 45 min plus 15 Q&A; rolling acceptance.

### Opening soon (page loaded)
- **FOSDEM 2027** (30–31 Jan 2027, Brussels), https://fosdem.org/2027/news/call-for-devrooms/
  - Devroom proposals close 4 Oct 2026; accepted devrooms are announced 20 Oct.
  - Devroom and main-track calls open "around October 27". No 2027 devroom list exists yet.
- **RustWeek 2027** (24–29 May 2027, Utrecht), https://2027.rustweek.org/cfp: the CFP **opens 1 Oct and closes 15 Dec 2026**. The angle would be the Rust runtime in 9.0.
- **PyCon DE & PyData 2027** (20–22 Apr 2027, Heidelberg), https://pycon.de/: "November 2026: Call for Proposals".
- **TROOPERS27** (21–25 Jun 2027), https://troopers.de/: "CfT and CfP opens soon"; the deadline is 31 Mar 2027.
- **USENIX SAIS 2027**, the Conference on Secure Agentic-AI Systems (7–8 Jun 2027, Santa Clara), https://www.usenix.org/conference/sais27: "Call for Papers will be available soon"; paper deadline 4 Feb 2027. A paper venue, and topically the closest.

### Checked: closed, not yet announced, or blocked
- **Closed:**
  - Insomni'hack 2027: closed 30 Aug. Its rules would have ignored AI-generated submissions.
  - Disobey 2027: closed 20 Sep.
  - ConFoo 2027: closed 20 Sep.
  - Everything Open 2027: closed 6 Sep.
  - [un]prompted II: closed 8 Sep.
  - PyData Global 2026: closed 24 Aug.
  - Black Hat Europe 2026 and SecTor 2026: closed.
  - BSidesSF and BSides Las Vegas: the 2026 calls are closed and no 2027 CFP is posted.
  - NorthSec 2027: not open ("we do not accept sponsored talks").
- **Not yet announced:**
  - PyCon US 2027 (us.pycon.org/2027 returns 404)
  - EuroPython 2027
  - AI Engineer World's Fair 2027 ("CFP… to come")
  - Open Source Summit NA 2027
  - LangSec 2027 (/spw27 returns 404)
  - SEC-T (the CFP page still shows 2026)
- **Blocked or not verified:**
  - Wild West Hackin' Fest Mile High 2027: the CFP is a JavaScript-only monday.com form. The 30 Oct deadline comes only from the InfoSeCFP aggregator.
  - OWASP BASC 2027: the site is JavaScript-only; a search snippet says the CFP opens 1 Nov.
  - **No CFP page was found for** OWASP Global AppSec EU 2027, CanSecWest 2027, OpenSSF Community Day 2027 or DEF CON 35 Demo Labs.

Aggregators used for discovery only: https://www.infosecfp.com/ and https://cfp.watch/.

---

## Suggested order of work

1. **Before 30 Sep:** decide on BSides London (its Rookie track has mentoring).
2. **Before 9 Oct:**
   - 40C3 and RSAC.
   - KubeCon EU and CNCF Agentics Day / Open Source SecurityCon (11 and 18 Oct).
   - Black Hat Asia Briefings (20 Oct) and Arsenal (2 Nov). Arsenal is the most natural "show the tool" slot, and Black Hat forbids LLM-generated text.
3. **This week, no deadline:**
   - agentlanguages PR: the scaffold exists, so finish the prose.
   - mcpservers.org form.
   - ChessMax PR.
   - ottosulin PR.
   - scadastrangelove WATCHLIST PR.
   - OWASP Agentic form (reviewed at month end).
   - PyCoder's form.
   - Console and Help Net Security emails.
4. **Needs a step first:**
   - punkpeye requires a Glama listing, with a Dockerfile that starts `sabline_mcp`.
   - Show HN: the account needs HN history because of the showlim restriction, and the text must be written by hand.
5. **Not now:**
   - analysis-tools-dev: after about 2027-02-16, and only with 20+ stars and a second human contributor.
   - TalEliyahu: needs 220+ stars and 3 or more contributors.
