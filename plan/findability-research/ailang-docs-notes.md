# AILANG, read in full: sourced notes for "Sabline vs AILANG"

Read on **2026-09-25**. Every AILANG claim below carries a URL, a short verbatim quote (under 30 words; `…` marks an elision inside a quote), and the version/date it applies to.

**How to read the dates.** The docs site (Docusaurus, built from `docs/docs/` on branch `dev`) has no per-page "last updated" stamp. So each docs page is dated by **the last git commit to its source file on `dev`**. I got that date from `gh api repos/sunholo-data/ailang/commits?sha=dev&path=…` on 2026-09-25. The whole site is currently built for **v0.42.0**: the landing page says "Version v0.42.0 Released", and `docs/src/constants/version.js` has `STABLE_RELEASE = 'v0.42.0'` and `ACTIVE_PROMPT = 'v0.16.6'`. Pages often name the AILANG version a feature shipped in, and I quote that where it matters. **"Page date" means the date the page last changed, not the date the feature shipped.**

**What "read in full" covered:**
- All 205 URLs in `https://ailang.sunholo.com/sitemap.xml`. All returned HTTP 200 and were saved as HTML and text.
- The 144 Markdown sources behind those pages. Quotes come from these, so they are exact.
- README, CHANGELOG index, `changelogs/v0.32-current.md` (read v0.39.0–v0.42.0 and the security entries in full; grepped the rest), SECURITY.md, GOVERNANCE.md, `docs/LIMITATIONS.md`, `docs/talk-building-a-language.md`, `docs/docs-sync-findings.md`, `docs/README.md`.
- Nine design docs (listed in §10).
- The GitHub API (repo, releases, tags, contributors).
- The Sunholo blog post named in the task, plus the blog index.
- The benchmark dashboard's own data files. The dashboard pages render client-side, so their numbers come from `/benchmarks/latest.json` and `/benchmarks/os/latest.json`, labelled as such.

Five parallel sub-readers read the long operational and reference pages in full. They returned verbatim quotes, and I spot-checked those against the sources. Pages that render their content client-side ("JS-only") are listed in §10.

---

## Key findings (details and quotes in the sections below)

1. **Current release and project shape.**
   - AILANG is **v0.42.0** (2026-09-23): Apache-2.0, Go, pre-1.0. The 1.x stability promise is drafted but not ratified.
   - One maintainer plus an AI coordinator writes it; 173 releases since 2025-09-26; 34 stars.
2. **The earlier note is too coarse.**
   - `--caps` does grant whole effect categories.
   - But the operator can narrow outside the type system:
     - domain allowlist (`--net-allow-domains`), https-only, private/metadata IPs blocked;
     - one FS root (`AILANG_FS_SANDBOX`);
     - process binary and subcommand allowlists;
     - env-var allowlist (source flag).
   - Since v0.39.0/v0.41.0 (Sept 2026) there is a **supervised policy mode** (`ailang run --policy agent-policy.toml`). It adds per-effect operator `[budgets]` counts, a whole-run timeout, output and source byte caps, write-deny globs and a module-graph digest.
   - `@limit`/`@min` in the signature are **per invocation**, not per program.
3. **Confinement is recent and self-audited.**
   - AILANG's own audit (design doc, 2026-09-21) reproduced FS sandbox escapes (`../`, symlinks) and a domain-allowlist escape via redirect. All were fixed in **v0.41.0** with Go `os.Root` and per-hop authorisation.
   - **No OS-level sandbox (seccomp/Landlock) is described.** CPU and memory are explicitly "the container's job".
4. **Verification.**
   - `requires`/`ensures` proved by Z3 (`ailang verify`), with a broad fragment: strings, lists, records, ADTs, cross-function inlining, bounded recursion, known-lambda HOFs, bounded `forall`, counterexamples.
   - **Pure functions only.** Runtime checking is an **opt-in** `--verify-contracts` flag, not an automatic fallback.
   - The package registry gates publishes on refuted contracts.
5. **Information flow.**
   - Open-vocabulary IFC labels (`T<label>`, `T{not LABEL}`, `! {Declassify}`), compile-time, intraprocedural.
   - A `Secret` effect resolving 1Password refs with push-to-phone approval ("code-complete — deploy-gated").
   - Their own docs admit labelled secrets still reach `deep` traces.
6. **AI and agent features are much broader than Sabline's.**
   - A typed AI effect across providers, with tool loops and routing provenance.
   - Any module can be served as MCP, A2A or REST.
   - A hosted docs MCP, Claude Code and Codex plugins, an LSP.
   - A coordinator, messaging bus, mission loops and a 41-agent production fleet.
   - A large eval harness: 18 cloud models, 6 harnesses, Python baseline.
7. **Published numbers, in the dashboard data file** (v0.32.0, 2026-08-27):

   | | AILANG | Python |
   |---|---|---|
   | overall 0-shot | 68.3% | 82.8% |
   | core tier | **92.1%** | 89.4% |
   | frontier tier | 27.5% | 57.4% |
   | agent mode (AILANG only) | 94.9% | — |

8. **Honest gaps to cite for Sabline.**
   - The docs never state whether refusals can be caught. Allowlist refusals are ordinary `Err` values.
   - No port-level grant.
   - No multi-path or read-only path grants on a normal run.
   - No pre-run "what can this touch" report.
   - No FFI effect.
   - No signed program-run receipts or attestations.
   - Several docs pages are stale or contradict each other (§9), and there is **no `main` branch**, so every `blob/main` link in the docs is 404.

---

## 1. Identity

| Claim | Source (URL) | Verbatim quote | Version / date |
|---|---|---|---|
| Latest release is **v0.42.0**, published 2026-09-23T16:14:18Z. The release body's "What's Changed" is empty; it carries only download instructions. | `gh api repos/sunholo-data/ailang/releases/latest` | `"tag_name":"v0.42.0" … "published_at":"2026-09-23T16:14:18Z"` | read 2026-09-25 |
| Previous tags, newest first: v0.41.0 (2026-09-21), v0.40.2, v0.40.1 (2026-09-18), v0.40.0 (2026-09-17), v0.39.x (2026-09-16/17). 173 GitHub releases in total. | `gh api …/releases` | (API listing) | read 2026-09-25 |
| Licence: Apache-2.0 | https://github.com/sunholo-data/ailang (README) | "Apache 2.0 - See [LICENSE](LICENSE)" | README at dev, 2026-09-25 |
| Implementation language: Go (GitHub `language: Go`; the CLI ships as a single `ailang` binary). | https://ailang.sunholo.com/docs/reference/implementation-status | "**Go Codegen** \| Complete \| Full compilation to Go"; the README calls `internal/` "Compiler (lexer, parser, types, eval, effects)" | page date 2026-08-17 |
| Maintainer and org: one lead maintainer plus an AI coordinator bot; the org is Sunholo Ltd (UK) | https://github.com/sunholo-data/ailang/blob/dev/GOVERNANCE.md | "AILANG operates a **single-maintainer + AI-coordinator** model." / "The project's bus factor is **1**." | GOVERNANCE.md at dev |
| Lead maintainer is Mark Edmondson | same | "Lead maintainer \| Mark Edmondson, [email omitted] (GitHub: MarkEdmondson1234)" | same |
| Written mostly by AI agents | https://github.com/sunholo-data/ailang (README) | "AILANG is written autonomously by AI agents via its own [coordinator]" | README at dev |
| Contributors by commit count (GitHub API): sunholo-voight-kampff (bot) 5,227; MarkEdmondson1234 1,401; dependabot 139; claude 37 | `gh api …/contributors` | (API listing) | read 2026-09-25 |
| Install: curl installer script; also tarballs and `make install` from source | README | "curl -fsSL https://ailang.sunholo.com/install.sh \| bash" | README at dev |
| Release assets: darwin arm64/x64, linux x64/arm64, win32 x64, `ailang-wasm.tar.gz`, examples.zip. Each has `.sig`/`.pem`/`.sha256`, plus a signed SHA256SUMS. | `gh api …/releases/latest` | (asset list) | v0.42.0 |
| Release signing: keyless cosign | https://github.com/sunholo-data/ailang/blob/dev/SECURITY.md | "Release archives are signed keyless with [Sigstore cosign] … starting with v0.14.1." | SECURITY.md at dev |
| SLSA claim in SECURITY.md. **Observation:** no release I checked has `multiple.intoto.jsonl` as an asset (v0.42.0, v0.41.0, v0.40.2, v0.30.0, v0.20.0, v0.15.1). `release.yml` does contain an SLSA job. I did not query GitHub's attestation API. | SECURITY.md | "Starting with v0.15.x, every release also carries [SLSA Build Level 3 provenance] attached as `multiple.intoto.jsonl`." | checked 2026-09-25 |
| Maturity: pre-1.0 | https://ailang.sunholo.com/docs (intro) | "AILANG is pre-1.0. The core language, effects, modules, and codegen are stable; minor-version releases may still adjust public APIs." | page date 2026-09-04 (renders v0.42.0) |
| Maturity: 1.x stability promise is drafted but **not ratified** | https://ailang.sunholo.com/docs/reference/stability | "**RATIFICATION: pending (Mark, at release).**" | page date 2026-07-12 |
| Stability tiers: `std/ai`, `std/net`, `std/process`, `std/secret`, `std/stream` are **Experimental**; `std/fs`, `std/env`, `std/io`, `std/clock`, `std/rand` are **Stable** | same | "`std/net` \| Network operations \| ⚠ proposed — widely used (13 examples) but security/format-sensitive; held Experimental" | page date 2026-07-12 |
| Effect-refinement (parameterised effects) syntax is Experimental | same | "the effect-refinement surface (parameterised effects / capability refinement) is Experimental-pending its own decomposition" | same |
| Security support covers the latest release only | SECURITY.md | "AILANG is pre-1.0 and evolves rapidly. Security fixes are applied to the latest minor release" | SECURITY.md at dev |
| Stars 34, forks 5, open issues 132. Repo created 2025-09-26; last push 2026-09-24T21:12Z. Default branch `dev`. Topics: ai, ai-agents, anthropic, gemini, genai, openai. | `gh api repos/sunholo-data/ailang` | (API) | read 2026-09-25 |
| Companion repo `sunholo-data/ailang_bootstrap` (Claude Code / Codex plugin): MIT, 3 stars | `gh api repos/sunholo-data/ailang_bootstrap` | "AILANG quick start for AI coding agents (Claude Code, Gemini CLI)" | read 2026-09-25 |
| Self-description | https://ailang.sunholo.com/ | "AILANG makes AI-generated code cheaper to debug, replay, and fix. Explicit effects constrain what code can do." | landing, v0.42.0 |
| Positioning | README | "AILANG is a purely functional, effect-typed language designed as a **deterministic execution substrate** for AI-generated code." | README at dev |
| Size and pace, from a talk doc in the repo (not on the site): "6.5 months, 2,435 commits, 111 releases, one developer + AI"; "346,000" lines of Go at v0.10.15 | https://github.com/sunholo-data/ailang/blob/dev/docs/talk-building-a-language.md | "A data-driven story from AILANG: 6.5 months, 2,435 commits, 111 releases, one developer + AI." | dated v0.10.15 (9 Apr 2026) |

---

## 2. Effects and capabilities

### 2.1 The effects that exist

- **Core effects on the reference page** (https://ailang.sunholo.com/docs/reference/effects, page date 2026-09-11): `IO`, `FS`, `Clock`, `Net`, `Env`, `Process`, `Stream`. The same page's stdlib table adds `Rand` and `AI`.
- **Other pages add** `Secret` (`std/secret`), `Declassify` (the IFC label-lowering effect), `SharedMem`, `SharedIndex`, `Debug`, `Trace`, `DOM`, `Msg`/`Cog` (Cognitive-OS modules), and `DB` (used in examples).
  - Stdlib table (https://ailang.sunholo.com/docs/reference/stdlib, page date 2026-07-14): "`std/secret` \| Gated secret resolution (`op://…`); resolved value is tainted `<secret>` until an explicit `Declassify` step \| `Secret`".
- **Principle** (effects page, 2026-09-11): "AILANG uses an **algebraic effect system** with capability-based security. All side effects must be declared in function signatures and granted at runtime."
- **Pure stdlib modules need no capability** (same page): "`std/list`, `std/string`, `std/option`, `std/result`, `std/map`, `std/bytes`, … \| _(none)_ \| pure — usable from `pure func`, no `--caps`".
- **Crypto and hashing are pure, not effects.** `std/crypto` (hash/HMAC) and `std/jwt` list capability "—" in the stdlib table (2026-07-14).

### 2.2 How effects appear in types

- **Row syntax after `!`.** Effects page (2026-09-11): "Effects are declared after the return type with `!`". Example: `func process() -> Data ! {IO, FS, Net} { ... }`; `pure func` marks a pure function.
- **Row polymorphism.** Same page: "`func twice[e](f: () -> () ! e) -> () ! e`". The README calls the type system "Hindley-Milner with row polymorphism".
- **Parameterised effects (v0.15.0, Experimental).** https://ailang.sunholo.com/docs/guides/parameterised-effects (page date 2026-07-28): "AILANG effect rows can now carry `[key=value]` parameters that ride alongside the effect name: `!{Rand[mode=os]}`".
  - Only `Rand` and `AI` accept parameters: "Only `Rand` (`mode ∈ {os, seeded, crypto}`) and `AI` (`mode ∈ {fixed, routeable, replay-only}`, `scope ∈ {byok}`) carry a parameter schema today".
  - The mode set is closed to user code: "authors cannot introduce new modes from user code".

### 2.3 How capabilities are granted at run time

- **`--caps` on the command line** (effects page, 2026-09-11): "`ailang run --caps IO,FS,Net --entry main program.ail`".
  - Missing grant: "Error: Function 'main' requires capability IO but it was not granted."
  - Escape hatch: "`ailang run --caps ALL --entry main program.ail`" with the comment "Grant all capabilities (development only!)".
- **`--caps auto`** infers caps from the entrypoint.
  - Docs mention it only in passing, in a package `[bin]` example (https://ailang.sunholo.com/docs/guides/packages): "entry main, caps auto".
  - The flag's help text is in source only (`cmd/ailang/main_run.go` on `dev`, read 2026-09-25): "or 'auto' to infer from the entrypoint". **This is source, not a docs page.**
- **Grants are whole effect categories.** Planned design doc `m-effect-scope-params.md` (Status: Planned, target v1.1.0, created 2026-07-11): "Capabilities today are effect-granular: `--caps Rand` grants ALL Rand operations."
- **`serve-api` / MCP server grants are server-wide.** https://ailang.sunholo.com/docs/guides/serve-api (page date 2026-09-11): "Capabilities are granted server-wide. All API endpoints share the same capabilities."
  - The same page: "`--caps` gates effect execution, not tool discovery."
- **Operator policy file (v0.39.0+, hardened v0.41.0).** https://ailang.sunholo.com/docs/guides/agent-tool-policy (page date 2026-09-23): "`allowed_caps  = ["IO", "FS"]              # the WHOLE authority a submitted program can have`".
  - `ailang run --policy <agent-policy.toml> prog.ail` is "a **supervised** run".
  - Widening flags are refused: "every widening flag (`--caps`, `--entry`, `--env*`, `--net-*`, `--stream-*`, …) is refused **by name**".

### 2.4 Narrowing below the effect category (operator side, outside the type)

| Dimension | Supported? | How and where | Source quote | Page / version |
|---|---|---|---|---|
| **Directory (FS)** | Yes, one root | `AILANG_FS_SANDBOX` env var, or policy `fs_sandbox` | "Restrict all FS operations to a directory by setting the `AILANG_FS_SANDBOX` environment variable" | effects page, 2026-09-11 |
| FS enforcement mechanism | Yes, since v0.41.0 | Go `os.Root`: a kernel-resolved open directory handle | "every FS operation … goes through one `os.Root` handle — `..`, absolute paths outside, symlinks whose target leaves the root … fail inside the syscall" | agent-tool-policy, 2026-09-23 |
| Write-deny paths inside the sandbox | Yes (policy only) | `fs_deny_write` globs; `.git/**` is implied | "Paths inside the sandbox the program and the lane's tools may read but not write" | agent-tool-policy, 2026-09-23 (v0.41.0) |
| Per-file read/write size | Yes | `--fs-max-bytes` / `AILANG_FS_MAX_BYTES`; policy `max_fs_transfer_bytes` | "Cap on every FS read (a byte count or K/M/G/T-suffixed size)" | env-vars ref, 2026-09-19 |
| **Domain / host (Net)** | Yes | `--net-allow-domains`; policy `net_allow` | "`--net-allow-domains <list>` \| Domain allowlist (comma-separated)." | effects page, 2026-09-11 |
| Wildcard subdomains | Yes | label-boundary wildcard | "`*.example.com` matches neither `evil-example.com` nor the apex" | CHANGELOG v0.41.0 (2026-09-21) |
| Redirect hops | Yes, since v0.41.0 | re-authorised on every hop | "a redirect to a host outside `net_allow` is refused before any dial" | agent-tool-policy, 2026-09-23 |
| Scheme | Yes | https-only by default; `--net-allow-http` | "`--net-allow-http` \| Permit `http://` URLs (default: https only)." | effects page |
| Private IP, localhost, metadata | Blocked by default; opt-in flags | `--net-allow-localhost`, `--net-allow-metadata` | "Private IP blocking (10.x.x.x, 192.168.x.x, etc.)" | effects page |
| **Port** | No port-level grant described | — | (searched "port" in effects, agent-tool-policy, LIMITATIONS: none describes a port grant) | — |
| **URL path** | Not described | — | — | — |
| **Env var** | Yes, by name, but documented only as a phrase | `--allow-env`, `--allow-env-file` (source); docs say "with an allowlist" | "`std/env` \| `Env` \| environment variables (with an allowlist)" | effects page. Flag help text is in `main_run.go` only |
| **Process binary** | Yes | `--process-allowlist`, path-pinned at startup | "Each entry is resolved via `PATH` **once, at startup**, and pinned to that absolute path" | effects page |
| Process subcommand | Yes (v0.38.0) | `git:status,gh:pr:list` | "**Subcommand narrowing.** `git:status,git:commit,gh:pr:list` allows `git status …`, `git commit …` and `gh pr list …`" | effects page |
| Process time and output | Yes | `--process-timeout` (default 30s), `--process-max-output` (default 10MB) | "Per-exec wall-clock limit (default 30s) → `Timeout`." | effects page |
| **Count per function (source)** | Yes | `@limit=N` / `@min=N` in the effect row | "`func i() -> () ! {IO @limit=5, Net @min=1 @limit=3} { ... }`" | capability-budgets, 2026-07-24 |
| **Count per run (operator)** | Yes, policy only (v0.41.0) | `[budgets]` table | "operator ceilings for the whole run: 0 = zero operations, absent = unlimited; a source @limit can only tighten" | agent-tool-policy, 2026-09-23 |
| Whole-run wall time | Yes, policy only | `timeout_ms`, supervisor kills the process group | "`timeout_ms`    = 5000   # the WHOLE invocation, enforced by the supervisor" | agent-tool-policy |
| Output bytes, source bytes | Yes, policy only | `max_output_bytes`, `max_source_bytes`, `max_module_graph_bytes` | "restricted defaults: 1 MiB / 16 MiB / 8 MiB / 8 MiB" | agent-tool-policy |
| AI provider and spend | Pinned provider plus a count ceiling | `ai_provider` + `[budgets] AI` | "restricted mode admits `AI` when `ai_provider` is set **and** `[budgets] AI = N` states the ceiling" | agent-tool-policy |
| Per-task USD cost cap (coordinator jobs, not programs) | Yes | `AILANG_MAX_COST_USD` | "Per-task cost budget in USD; unset or malformed means no cap" | env-vars ref, 2026-09-19 |
| CPU / memory | **No hard bound** | `--max-memory` is Go's soft limit | "does not bound CPU or memory (host isolation is the container's job)" | agent-tool-policy |

**The allowlist flags belong to the command line, not the program.** Effects page (2026-09-11): "The allowlist is a property of the **invocation**, not of the program's signature — run the `.ail` without the flag and it may exec anything."

**Signature-level scoping is planned, not shipped.**
- Same page: "Signature-level narrowing (`! {Process[scope=...]}`) is tracked under M-EFFECT-REFINEMENT".
- Parameterised-effects guide (2026-07-28), future work: "`!{FS[scope=fixture]}` constrains a function to a sandboxed filesystem".
- Design doc `m-effect-scope-params.md` future work: "Scopes on FS/Net (fixture-tree scoping, host allowlists as scopes)".

### 2.5 Where limits are written

- **In the program** (per function, in the effect row). https://ailang.sunholo.com/docs/reference/capability-budgets (page date 2026-07-24): "Add `@limit=N` to set a maximum budget, or `@min=N` to require a minimum usage".
  - Also a **minimum**: "Minimum requirement: must use at least 1 IO operation".
  - Semantics are **per invocation** and **hierarchical** (effects page, 2026-09-11): "Each call to an annotated function pushes its own frame" … "Every matching effect op charges the current (innermost) frame **and** all active ancestor frames".
  - The operator can switch source budgets off: "Bypass for debugging: Use `--no-budgets` flag" (effects page). `--no-budgets` is refused under `--policy` (CHANGELOG v0.39.0 and v0.41.0).
- **By the operator** (whole run, policy file only, v0.41.0). See the `[budgets]` row in §2.4.
  - CHANGELOG v0.41.0 (2026-09-21): "charged once per logical op at the canonical charge scope, before the side effect; shared across `WithBudget`/`Clone`; untouched by `--no-budgets`".
- **No `--budget`-style flag on plain `ailang run`.** Operator counts live only in the policy TOML. (Searched effects, cli, capability-budgets, env-vars and agent-tool-policy; the `run` flag list in source has `--no-budgets` and `--budget-report` only.)

### 2.6 Is a refusal catchable?

Refusals come in two kinds. **The docs never state catchability as a property**, so this is inferred from documented return types and error messages.

- **Allowlist refusals come back as values the program handles.**
  - Net: `Err(DisallowedHost(...))`. https://ailang.sunholo.com/docs/examples/ai-api-integration (page date 2026-07-10): "`| DisallowedHost(string) -- Domain not in allowlist`". agent-tool-policy (2026-09-23): "with `Net` but without the host it gets `DisallowedHost(ollama.com)`."
  - Process: effects page, "**`Err`** = infrastructure failure (command not found, timeout, blocked by allowlist)", with example arm `Err(NotAllowed(cmd)) => println("blocked: ${cmd}")`.
  - AI budget: https://ailang.sunholo.com/docs/guides/ai-effect (page date 2026-05-05), where `callResult` returns `AIError` code "`BudgetExhausted` \| no \| AI cap budget overflow".
  - **So an AILANG program can observe these refusals and carry on.**
- **Missing capability and source-budget exhaustion stop the run.**
  - Capability-budgets page: "When a function exceeds its budget, it fails with a `BudgetExhaustedError`".
  - Effects page: "Error: Capability FS required but not granted".
  - AILANG has no exceptions (errors are `Result`/`Option`). The docs show no construct that intercepts these errors.
- **Denials in policy mode happen before execution.** agent-tool-policy: "denial prints the decision JSON and exits 2 without running".
- **Secret approval fails closed.** https://ailang.sunholo.com/docs/guides/secret-approvals (page date 2026-06-23): "any denial, timeout, or transport error returns `E_SECRET_DENIED`; there is no silent fallback".

### 2.7 Static, dynamic, or both?

**Both.**
- **Static.** Effects page: "The type checker verifies effect declarations" (example: reading a file in a function declared `! {IO}` is a "Compile error!").
- **Dynamic.** Effects page: "Even if you declare an effect, you must grant it".
- **Static admission in policy mode.** agent-tool-policy: "the program's declared effect row must be a subset of `allowed_caps`".
- **Transitive effects are caught by the typechecker.** CHANGELOG v0.39.0: "a clean-row `main` calling an imported `! {Net}` function is `typecheck_failed` before the policy is consulted".
- **Landing page** (v0.42.0): "Types, effects, capabilities, and inline contracts are verified before anything runs."

### 2.8 Sandboxing and OS-level enforcement

- **No OS sandbox mechanism is described.** Searched the Markdown sources, rendered site text, repo root docs and `llms.txt` for: seccomp, landlock, sandbox_init, sandbox-exec, gvisor, firecracker, nsjail, bubblewrap. **No matches.**
- **The kernel is used in two places:**
  - `os.Root` for FS containment (§2.4).
  - Process-group kill for the policy timeout. agent-tool-policy: "starts this binary as a worker in its own process group".
- **Unsupported platforms are refused.** agent-tool-policy: "Windows and `GOOS=js` refuse restricted mode."
- **Environment allowlist in restricted mode.** agent-tool-policy: "an allowlisted environment (restricted mode)"; "The restricted worker receives only the pinned provider's credential variables".
- **Proxy refused.** "It also refuses a configured HTTP proxy (`E_NET_PROXY_REFUSED`: the destination address cannot be pinned behind one)".
- **Confined git adapter.** agent-tool-policy: "`exec("git", …)` runs through a confined adapter … the argv is **built** from a per-subcommand schema".
- **Residuals that AILANG lists itself.** https://github.com/sunholo-data/ailang/blob/dev/docs/LIMITATIONS.md#execution-policy-residuals (post-v0.41.0):
  - "**CPU and memory** \| No portable effect-level bound; Go's soft memory target is not a hard limit"
  - "**The AI effect's HTTP client is not the Net authorizer**"
  - "`trusted_host` mode \| An explicit host-integration grant with no confinement claim".
- **Recent history: the FS sandbox and domain allowlist were bypassable until v0.41.0.**
  - Design doc `implemented/v0_41_0/m-executor-policy-hardening.md` (created 2026-09-21): "With FS sandbox set, `readFile("../marker.txt")` reads a disposable marker outside it"; "With only `allowed.example` listed, HTTP follows a redirect to `denied.example`".
  - CHANGELOG v0.41.0: "on the audited baseline 118 rows failed".
  - **Any AILANG FS or Net confinement claim should be dated v0.41.0 (2026-09-21) or later.**

### 2.9 Budget concepts, all of them

1. **Source capability budgets.**
   - `@limit` / `@min`, per invocation, hierarchical (§2.5).
   - Shipped v0.6.2 per the design-docs index (M-CAPABILITY-BUDGETS).
2. **Operator `[budgets]`** in the policy file (v0.41.0).
3. **Coordinator task cost caps.** `AILANG_MAX_COST_USD` (env-vars ref) and the `AILANG_BUDGET_UNLIMITED` acknowledgement: "1 acknowledges that a task may run with NO spend cap when no budget resolves".
4. **Eval cost and speed budgets** (evaluation guides; see §6).
5. **Planned budget work:**
   - "M-ENTROPY: Semantic Entropy Budgets" (roadmap v1.1.0).
   - "M-MEM-BUDGET-RUNTIME: Memory as a Budgeted Resource" (roadmap, v0.31.0 heading; status Planned).
   - Roadmap page date 2026-09-09.
6. **Budget report.** `--budget-report` flag (source); design-docs index "M-DX25: Scoped Budgets with Dual Counters & Budget Reporting" (v0.7.1).
   - Traces carry a `budget_delta` event. https://ailang.sunholo.com/docs/guides/traces (page date 2026-04-10): "`budget_delta` \| Resource consumed \| used, limit, remaining".

### 2.10 Secrets and information flow

- **IFC labels (v0.16.0).** https://ailang.sunholo.com/docs/guides/ifc-labels (page date 2026-08-17): "`T<label>` \| "T tainted with label" \| Mark a value as carrying source-level taint."
  - Sink refinement: "`T{not LABEL}` \| … \| Mark a parameter position as a sink that refuses LABEL."
- **Labels are open.** "**Labels are not a fixed vocabulary.**" / "they all erase at compile time".
- **Declassification is an effect.** "A function that changes a value's label must declare `! {Declassify}` in its effect row."
- **Static enforcement (v0.26.0).** "sink and declassification violations are caught as **compile-time type errors** by `CheckModuleIFC`, before Z3 runs".
- **Limits:**
  - "**Sink enforcement is intraprocedural.**"
  - "**cross-module** sinks still rely on Z3 contracts and are deferred to M-TAINT-TYPES Phase 2".
  - "**Label aliases are not yet expanded.**"
- **Secret effect and 1Password.** https://ailang.sunholo.com/docs/guides/secret-approvals (2026-06-23): "AILANG's `Secret` effect resolves 1Password references (`op://Vault/Item/field`) behind a **declared, capability-gated, flow-controlled** effect."
  - Phone approval: "resolution can be gated on a **human approval pushed to your phone**".
  - Status on the same page: "Code-complete — deploy-gated".
- **Secrets could leak into traces (their own P0, still Planned).**
  - Design doc `planned/v0_36_0/m-trace-label-aware.md` (2026-09-09): "`std/secret` documents a guarantee the runtime does not provide."
  - The same doc: "The reporter measured eighteen verbatim copies of a live Google bearer token in the trace".
  - Partially fixed in v0.36.0. CHANGELOG: "at `standard`, an IFC-labelled value crossing a traced call boundary is no longer written to the trace … At `deep` it is still 4". Also: "effect args and results are still recorded at `standard`".
  - A value-blind switch exists: "`AILANG_TRACE_VALUES=off` … with each value replaced by a size descriptor".
  - Env redaction defaults on. env-vars ref: "`AILANG_REDACT_ENV` \| `on` \| off disables redaction of sensitive environment values in traces and errors."
- **A label-laundering hole was fixed in v0.36.0.** CHANGELOG: "a closure could launder an IFC label past a `{not secret}` sink".

---

## 3. Verification

### 3.1 Contracts
- **`requires`/`ensures`.** https://ailang.sunholo.com/docs/guides/contracts (page date 2026-04-30): "AILANG supports **design-by-contract** programming through `requires` and `ensures` clauses."
  - Z3 and runtime modes: "machine-checkable — both at runtime and at compile time via Z3 SMT solving."
- **Runtime checking is opt-in.** Same page: "Enable runtime contract verification with the `--verify-contracts` flag". A violation is a panic: "panic: contract violation: requires: (divisor != 0) at basic.ail:21:12".
- **Static proof with Z3.** Same page: "`ailang verify` uses the Z3 SMT solver to **mathematically prove** that your contracts hold for **all possible inputs**."
  - Result states: "`VERIFIED` (proven correct), `VIOLATION` (counterexample found), or `SKIPPED` (outside fragment)". Counterexamples are printed (e.g. "Counterexample: unitPrice: Int = 0 qty: Int = 1").
  - Flags: `--json`, `--strict` ("fail if any function can't be verified"), `--timeout` ("default: 5s"), `--verbose` (SMT-LIB dump).
  - Z3 is installed separately: "Install Z3 via `brew install z3` … or download from [Z3 releases] and set `AILANG_Z3_PATH`".
- **What Z3 can check** (same page, "Currently supported"):
  - int, bool, string, list, enum/ADT, records including nested ones.
  - Z3 string and sequence theories.
  - Cross-function inlining via `define-fun`.
  - "Recursive functions: bounded unrolling (Dafny-style, depth 1-10, default 2)".
  - Per-function `@verify(depth: N)`.
  - Higher-order `map`/`filter`/`foldl` "with **known lambda arguments**".
  - Bounded quantifiers `forall i: lo..hi => P(i)`.
  - **Pure functions only:** "Must be pure: `! {}` (no effects)".
- **Effectful functions are skipped, not proven.** "Effectful functions \| Nondeterminism breaks proofs \| Fundamental — effects are inherently nondeterministic"; the CLI output reads "⚠ SKIPPED effectfulFunc … Reason: Function "effectfulFunc" has effects".
- **Bounded ≠ full proof.** "Bounded verification is **sound but incomplete** … Full induction proofs are a future goal."
- **Where this comes from.** "This feature implements techniques from the **ARC (Automated Reasoning Checks)** system developed by AWS" (Bayless et al. 2025).
- **Version history** (same page): runtime contracts v0.6.2; Z3 `ailang verify` v0.7.4; bounded recursion v0.8.0.
  - The implementation-status page says "SMT Backend \| Complete \| Z3 integration, cross-function inlining" (page date 2026-08-17).
  - The IFC guide says "AILANG already shipped the Z3 piece in v0.9.x".
  - **These disagree on the version** (v0.7.4 vs v0.9.x).
- **Combined check for agents.** `ailang ai-check` / `ailang check --verify`. https://ailang.sunholo.com/docs/reference/cli (page date 2026-09-21): "Type-check a file or directory (--verify adds contract verification)".
- **In-browser Z3 demo.** Landing page (v0.42.0) lists demo tags "WASM Z3 AI Effect". Contracts page: "Z3 Verify Demo … Watch Z3 mathematically prove correctness or find counterexamples".
- **Contracts in examples:**
  - A prompt-injection benchmark uses `ailang verify`: "✗ VIOLATION injectedForward" (IFC guide, 2026-08-17).
  - A deontic/obligations package advertises "Z3-provable settlement math". https://ailang.sunholo.com/docs/packages/sunholo/deontic ("Last Updated 2026-09-16T06:48:09Z", v0.3.0, "experimental").

### 3.2 Static checks besides contracts
- **Strict fallbacks lint.** https://ailang.sunholo.com/docs/guides/strict-fallbacks (page date 2026-07-24): "AILANG statically detects the **"`Ok` contains a default/empty value"** anti-pattern in `Result`-returning functions."
  - Advisory under `check`, hard error at publish: "`ailang check --package dir/` \| **Hard error**, exits **1** — the publish boundary fails loudly."
- **IFC labels are compile-time checks** (§2.10).

### 3.3 Type system

**Shipped:**
- Hindley-Milner with row polymorphism (README: "Type inference - Hindley-Milner with row polymorphism").
- Type classes: implementation-status says "Hindley-Milner, row polymorphism, type classes"; the intro says "(Num, Eq, Ord, Show)".
- ADTs with exhaustiveness. Intro (page date 2026-09-04): "ADTs with exhaustiveness checking catch invalid states at compile time". Contracts page: "exhaustive pattern matching (enforced by the compiler)".
- Pattern guards: limitations page says "Pattern guards — Implemented in v0.6.2".
- `deriving (Eq)` and container equality: CHANGELOG v0.42.0 (2026-09-22): "`==` now works on lists, Option, Result, tuples and derived records".

**Not implemented or planned** (limitations page, "Verified at v0.33.1 (2026-08-17)"):
- `?` operator: "`r?` still produces `PAR_NO_PREFIX_PARSE`".
- Typed quasiquotes.
- CSP / session types: "deferred to v1.0.0+".
- User-definable effect handlers: roadmap v1.1.0 "M-EFFECT-HANDLERS: User-Definable Effect Handlers". The contracts page says "AILANG has no statements"; the vision page says "Mediated through kernel".

**Language constraints:**
- No loops. Contracts page: "AILANG has no `for` or `while` loops."
- Recursion cap and no TCO. Limitations: "`ailang run` caps evaluator recursion at **10,000 frames** by default … The evaluator has no tail-call elimination".
- Quadratic cons. Limitations: "Prepending with `::` is quadratic".
- Y-combinator rejected by the occurs check.

**Termination: the docs disagree.**
- https://ailang.sunholo.com/docs/reference/no-loops (page date 2025-12-24, "v0.3.14+") says: "AILANG enforces **structural recursion** to guarantee termination for all accepted recursive programs."
- The bibliography softens this: "AILANG aims for total functions with provable termination."
- The limitations page describes only a runtime recursion cap.
- **Do not cite a termination guarantee without testing it.**

**Type classes are fixed.** https://ailang.sunholo.com/docs/architecture/types (2025-12-24): "Current implementation has hardcoded type class instances (Num, Eq, Ord, Show)."
- User-defined type classes are roadmap v1.1.0: "M-REFLECT: Structural Reflection & User-Defined Type Classes".

**Row polymorphism for records is flagged partial on the syntax page.** https://ailang.sunholo.com/docs/reference/language-syntax (2026-07-01; header "AILANG v0.6.0"): "Row Polymorphism (Partial - requires AILANG_RECORDS_V2=1)".
- **Effect-row** polymorphism is documented as working (effects page; ai-effect `runTools`).

**Effect errors carry provenance.** https://ailang.sunholo.com/docs/reference/errors/typ_effect_row_mismatch (2026-05-06): "each extra label is annotated with the source span where it was introduced."

**Soundness fixes are documented.**
- option-vs-result (2026-05-11): "Since v0.18.10, the AILANG typechecker rejects pattern matches that mix the two ADTs."
- CHANGELOG v0.42.0: "An `Eq` constraint whose type still held a type variable was never checked."

**Design axioms** (https://ailang.sunholo.com/docs/references/axioms, 2025-12-19). Twelve, including:
- A1 "Determinism Is a Semantic Invariant"
- A4 "Authority Must Be Explicit" ("Ambient authority is treated as a design error.")
- A5 "Verification Should Be Local, Bounded, and Automatable"
- A9 "Cost Is Part of Meaning"
- A11 "Failure Must Be Representable"
- A12 "The Language Is a System Boundary"

Self-scored 23/24 in `axiom_scorecard.json` (v0.15.0).

### 3.4 Testing
- **Inline tests** on pure functions. Effects page: "Use inline tests for pure functions: `pure func double(x: int) -> int tests [ (0, 0), … ]`".
- **Property-based testing.** https://ailang.sunholo.com/docs/guides/testing (page date 2026-04-20) is titled "Property-based testing for deterministic AI code synthesis". Details in §5 (tooling reader).
- **Effect mocking is not implemented.** Effects page: "### Mocking Effects (Planned)". The AI effect has a deterministic stub: "`--ai-stub`".

---

## 4. AI and agent features

### 4.1 AI as an effect
- https://ailang.sunholo.com/docs/guides/ai-effect (page date 2026-05-05): "The AI effect (`std/ai`) is a **general-purpose AI oracle** - an opaque string-to-string interface for calling LLMs".
- **Providers and routing.**
  - Built-in providers: Anthropic, OpenAI, Google (API key or ADC), Ollama, OpenRouter.
  - Model selection is operator-side: `--ai <model>`.
  - Custom providers are config-only. https://ailang.sunholo.com/docs/guides/custom-ai-providers (page date 2026-05-05): "Declare an `[[ai_provider]]` block in your `ailang.toml`, and AILANG registers it as a first-class provider with full budget tracking, AI capability gating, and trace integration."
- **Typed failures** (v0.17.0). `callResult` returns `Result[string, AIError]`, and the ten error codes are named, including `RateLimit`, `ContextLength`, `BudgetExhausted` (ai-effect page).
- **Tool loops in AILANG** (v0.17.0). "`step` (one model turn) and `runTools` (loop driver)"; "The `dispatch` callback's effects propagate via row polymorphism — pass a dispatch with `! {FS, Process}` … and `runTools` infers `! {AI, FS, Process}` automatically." Provider tool support: Anthropic, Gemini, OpenAI, OpenRouter yes; Ollama "no — typed reject".
- **AI modes in the type** (v0.15.0).
  - https://ailang.sunholo.com/docs/guides/ai-routing (page date 2026-06-05): "`!{AI[mode=routeable]}` \| Opts into runtime provider routing".
  - Reserved and not implemented: "`!{AI[mode=replay-only]}` \| Reserved (parser accepts; runtime stub)".
- **Routing provenance in traces.** Same page: "Every routed call records the resolved model, fallback chain, prompt/completion/cached tokens and USD cost in the trace's `ResolvedRoute` payload."
  - Replay does not use it yet: "the replay engine itself is currently trace-naive — it reruns the source file with a fresh AI handler".
  - No budget enforcement on routing: "AILANG-side budget enforcement (halt on exceed) is also out of scope".
- **Streaming and WebSocket.** `std/ai/streaming` (Experimental); Gemini Live WebSocket demo (landing page). Details in §5.
- **Web search for programs** (v0.40.x). agent-tool-policy: "`webSearch(query, max)` and `webFetch(url)` are `{Net}` effects backed by a fixed endpoint on `ollama.com`; the runtime reads `OLLAMA_API_KEY` itself, so the program never holds a key".

### 4.2 MCP
- **Two MCP servers.** https://ailang.sunholo.com/docs/guides/agent-mcp (page date 2026-07-29): "AILANG ships *two* MCP servers".
  1. **Hosted, read-only knowledge server.** "`mcp.ailang.sunholo.com` is a remote [Model Context Protocol] server that exposes ~21 typed tools". The intro and for-ai-agents pages say "21+ typed tools".
  2. **Local execution MCP** (in `ailang_bootstrap`). README: "`ailang_prompt`, `ailang_check`, `ailang_run`, `ailang_builtins`, `ailang_eval`".
- **Hosted server is version-scoped.** "Version-scoped tools take an optional `for_version` argument".
  - Built with AILANG's own effect caps: "Cloud Run service runs `ailang serve-api --mcp-http --routes-only --caps FS,Env`".
  - Tools are written in AILANG: "The MCP tools are written in AILANG itself".
- **Any AILANG module can be served as an MCP server.** https://ailang.sunholo.com/docs/guides/serve-api (page date 2026-09-11): "Expose AILANG functions as MCP tools for use with Claude Desktop, Cursor, and other MCP clients."
  - Supports "`ailang serve-api --mcp ./api/`" (stdio) and "`--mcp-http`".
  - The same command also serves REST, OpenAPI 3.1, Swagger/ReDoc, and "Google's A2A protocol … enabled with the `--a2a` flag".
- **Auth gap on serve-api.** Same page, "Authentication (v0.9.4+)": "Meta endpoints (`/api/_health`, `/api/_meta/*`), MCP, and A2A bypass auth".
- **Claude Code and Codex plugins.** README: "`/plugin marketplace add sunholo-data/ailang_bootstrap`" and "codex plugin marketplace add sunholo-data/ailang_bootstrap --ref stable".

### 4.3 The agent sandbox lane (`ailang_only`)
Covered in §2.3–2.8 (agent-tool-policy). Coordinator guide (page date 2026-09-17): "the lane where an agent executes programs only by submitting AILANG source to a policy it cannot edit"; "that lane is the default shape for new agents".

### 4.4 Determinism, replay, traces
- **Program traces.** https://ailang.sunholo.com/docs/guides/traces (page date 2026-04-10): "AILANG captures detailed execution traces when programs run — every function call, effect invocation, contract check, and budget change."
  - Event types: `module_start` (with "granted capabilities"), `function_enter/exit`, `effect`, `contract_check`, `budget_delta`, `error`, `module_end`.
- **Replay.** Same page: "The replay command re-executes the source program and compares the new trace against a baseline".
  - Exit codes "0 \| Traces match — deterministic / 1 \| Traces differ".
  - Nondeterministic effects are skipped: "Non-deterministic effects (like `Net.httpGet`, `Clock.now`, `IO.readLine`) are automatically flagged with `"deterministic": false` … The replay comparator skips argument/result comparison for these events".
  - **So replay re-runs the program. It does not substitute recorded effect results.** Recorded-effect modes (`Net[mode=recorded]`, `FS[mode=fixture]`) are planned (parameterised-effects guide, "Phase 5").
- **Training-data export.** "Export high-quality traces as fine-tuning data for AI models" (`ailang export-training`, scored 0.0–1.0).
- **Deterministic clock and seeding.**
  - Effects page: "`ailang run --clock-mode fixed --clock-start 1000 program.ail`".
  - `AILANG_SEED` for `Rand[mode=seeded]`: "a `seeded`-mode draw with no `AILANG_SEED` provided is a loud typed error".
- **Replay contracts per mode** (v1.0.0 work, shipped for Rand). Parameterised-effects guide: "the replay-contract taxonomy in `internal/replay` maps each legal `(effect, mode)` pair to `{deterministic, re-sampleable, opaque}`".
- **OTEL.** Intro: "Three-tier OTEL Tracing (v0.12.0) - `--trace-tier off|standard|deep`". Program traces can "Also emit OTEL spans (for Cloud Trace integration)".
- **Audit logs for policy runs.** agent-tool-policy: "The admission line on a run's stderr carries `security_mode`, `caps`, `entry`, `timeout_ms`, `budgets`, `limits` and `module_graph` (`digest`, `files`, `bytes`)".
  - Rows bank "`policy_digest` (sha256 of the policy bytes)".
  - **This is an audit record, not a signed attestation.** I searched the docs for "attestation", "in-toto", "receipt" and "signed" in the program-run sense; see §7b.

### 4.5 Multi-agent coordination, fleet and operations
Summarised from the 22 operations pages (full notes in §4.6).
- **Coordinator daemon.** https://ailang.sunholo.com/docs/guides/coordinator (page date 2026-09-17): "The coordinator watches for messages across multiple inboxes, routes them to configured agents, and executes tasks in isolated git worktrees."
  - Fleet snapshot: "What the production fleet actually runs (2026-09-17): 41 agents — 38 `pi`, 2 `codex`, 1 `motoko`, and no `claude`".
- **Human approval gates.** Coordinator: "where merge and handoff are combined into a single approval action". Approvals via dashboard, CLI or GitHub labels ("Approve from GitHub mobile app").
- **Messaging bus.** https://ailang.sunholo.com/docs/guides/agent-messaging (page date 2026-09-15): SimHash and neural search. "Messages can carry a semantic envelope — a set of named embedding vectors".
- **Mission loop.** https://ailang.sunholo.com/docs/guides/mission-bootstrap (page date 2026-09-05): "a scheduled outer loop that picks the top item off a written backlog, routes it through a design → plan → execute → evaluate inner loop of specialised agents".
- **Vendor independence.** https://ailang.sunholo.com/docs/guides/mission-model-fleet (page date 2026-08-26): "The evaluator must not share a vendor with the executor. Not just a different model — a different vendor."
- **Agent-run receipts** (JSONL; agent dispatch, not program runs). https://ailang.sunholo.com/docs/guides/mission-role-dispatch (page date 2026-09-18): "It records the normalized request, model plan and registry digest, candidate rejections, selected route, adapter result, session, finish reason, usage and cost provenance."
  - No sandbox here: "The command does not verify the declared Git revision or create a sandbox."
- **Secret approval by phone** (§2.10).
- **Package cascade with cost caps.** https://ailang.sunholo.com/docs/guides/autonomous-package-updates (page date 2026-04-30): "Each package owner sets [cascade] max_cost_usd in their ailang.toml (default $1.00)."
- **Effect-widening warning on publish.** agent-messaging: "`effect-widening-warning` if the effect ceiling expanded" (routed to "Policy review").
- **Observability.** https://ailang.sunholo.com/docs/guides/telemetry (page date 2026-09-08): "AILANG includes comprehensive OpenTelemetry (OTEL) instrumentation for distributed tracing and observability."
  - Every LLM call gets a span with `ai.cost_usd`.
- **Weaker points on the same pages:**
  - Cloud agents bypass Claude Code permissions. https://ailang.sunholo.com/docs/guides/cloud-messaging-integration (page date 2026-09-15): "The agent runs with `--dangerously-skip-permissions` which bypasses all `settings.json` deny rules. PreToolUse hooks are the only enforcement mechanism that still fires in this mode."
  - Capability requests in the Hub are inferred from text. https://ailang.sunholo.com/docs/guides/collaboration-hub (page date 2026-09-15): "Analyzes directive text for FS/Net/IO patterns".
  - Merge scope bounds nothing by default. Coordinator: "leaving it unset defaults to `**/*`, which bounds nothing".
  - The Net effect bypasses the test proxy boundary. https://ailang.sunholo.com/docs/guides/development-workflow (page date 2026-08-21): "Decision D5 deliberately leaves this route open".
  - Telemetry can drop data. Telemetry page: "Failed batches and work interrupted before flush can be lost; this change adds no durable spool or replay."
  - Unknown workspaces fail open. https://ailang.sunholo.com/docs/guides/workspaces (page date 2026-01-25): "Unknown workspaces default to "public" (if exists)".

### 4.6 Operations pages: condensed notes
All pages below were read in full by the sub-readers. Quotes are verbatim.

| Page (URL) | Page date | Key claims (verbatim) |
|---|---|---|
| https://ailang.sunholo.com/docs/guides/coordinator | 2026-09-17 | "The coordinator watches for messages across multiple inboxes, routes them to configured agents, and executes tasks in isolated git worktrees."; "What the production fleet actually runs (2026-09-17): 41 agents"; "ailang_only restricts the agent to read/edit/write + ailang_check/ailang_run/builtins_search/examples_search/ailang_cli — no shell"; "Fully autonomous (dangerous!)"; "leaving it unset defaults to `**/*`, which bounds nothing"; "Each approval decision creates an OTEL span for observability" |
| https://ailang.sunholo.com/docs/guides/coordinator-setup | 2026-06-23 | "When auto_approve_handoffs: false, each stage requires human approval before triggering the next agent."; prerequisite "ailang version >= v0.6.6" |
| https://ailang.sunholo.com/docs/guides/coordinator-workers | 2026-09-15 | "The Bearer auth middleware fails closed: with COORDINATOR_API_KEY unset every request to a Bearer route is rejected with 401"; "until M-V1-SIMPLIFY-S3 M5, 2026-09-15, unset meant open"; "worker_tags are routing attributes, NOT AILANG's --caps IO,FS effect-system capabilities" |
| https://ailang.sunholo.com/docs/guides/collaboration-hub | 2026-09-15 | "It provides real-time visibility into autonomous agent execution, approval workflows, and multi-agent pipelines."; capability approvals: "Analyzes directive text for FS/Net/IO patterns"; "Default approval timeout is 60 seconds. If no human approves in time, the directive is cancelled." |
| https://ailang.sunholo.com/docs/guides/cloud-messaging-integration | 2026-09-15 | "The coordinator can only encrypt (not decrypt); the agent can only decrypt (not encrypt)"; "The agent runs with `--dangerously-skip-permissions` which bypasses all `settings.json` deny rules."; "Inbox-level filtering provides functional isolation"; "Dead letter \| Messages moved to ailang-dead-letter topic after 5 failures" |
| https://ailang.sunholo.com/docs/guides/agent-messaging | 2026-09-15 | "effect-widening-warning if the effect ceiling expanded"; "Messages can carry a semantic envelope — a set of named embedding vectors"; "The public MCP (mcp.ailang.sunholo.com) writes to prod Firestore" |
| https://ailang.sunholo.com/docs/guides/telemetry | 2026-09-08 | "AILANG includes comprehensive OpenTelemetry (OTEL) instrumentation for distributed tracing and observability."; "All AI providers emit spans for API calls"; "Failed batches and work interrupted before flush can be lost; this change adds no durable spool or replay." |
| https://ailang.sunholo.com/docs/guides/notification-channels | 2026-05-30 | "Fail-closed registration — a channel registers only if its secret is present."; "Status (v0.24.0): outbound-only." |
| https://ailang.sunholo.com/docs/guides/notify-daemon | 2026-07-13 | "Coordinator tasks that need approval (⏳), complete (✅), or fail (❌) ping the maintainer immediately."; "Windows / Linux notifications (macOS only)." |
| https://ailang.sunholo.com/docs/guides/mission-bootstrap | 2026-09-05 | "a scheduled outer loop that picks the top item off a written backlog, routes it through a design → plan → execute → evaluate inner loop"; "API keys stripped from the loop's environment so it runs on a subscription, never a metered key." |
| https://ailang.sunholo.com/docs/guides/mission-iteration | 2026-09-08 | "The binary owns dispatch, resource limits, durable ownership, artifact checks, and recovery."; "Windows execution fails before dispatch" |
| https://ailang.sunholo.com/docs/guides/mission-model-fleet | 2026-08-26 | "Every role names at least two vendors. That is a hard rule, not an aspiration"; "The evaluator must not share a vendor with the executor." |
| https://ailang.sunholo.com/docs/guides/mission-role-dispatch | 2026-09-18 | "The command does not verify the declared Git revision or create a sandbox."; "timeout of 1–1800 seconds; positive token and USD ceilings."; "This is not a hard ceiling on actual billing or a quota reservation." |
| https://ailang.sunholo.com/docs/guides/workspaces | 2026-01-25 | "Workspaces provide multi-tenant isolation for the AILANG Dashboard."; "Unknown workspaces default to "public" (if exists)" |
| https://ailang.sunholo.com/docs/guides/state-system-workflow | 2026-08-17 | "Built into AILANG itself (Go implementation), provides persistent message passing between agents." |
| https://ailang.sunholo.com/docs/guides/agent-workflows | 2026-09-04 | "Interactive approval (view diff, chat history, approve/reject)"; "GitHub issues automatically flow into the agent pipeline." |
| https://ailang.sunholo.com/docs/guides/database-architecture | 2026-07-21 | "AILANG uses three SQLite databases with cross-references."; "DON'T expect TRACEPARENT propagation through Claude Code — it's not supported". This contradicts telemetry's cross-process linking claim. |
| https://ailang.sunholo.com/docs/guides/autonomous-package-updates | 2026-04-30 | "v1 is always-PR. No package version is auto-merged or auto-published downstream."; "Each package owner sets [cascade] max_cost_usd in their ailang.toml (default $1.00)."; future: "Adds signed publishing, admission policy, effect ceilings" |
| https://ailang.sunholo.com/docs/guides/hooks-setup | 2026-09-04 | "AILANG uses Claude Code's native HTTP hooks (type: "http") for telemetry and agent integration."; "HTTP hooks fail silently: Claude Code won't block if the server is down" |
| https://ailang.sunholo.com/docs/guides/claude-code-integration | 2026-09-04 | "every merge goes through human approval" |
| https://ailang.sunholo.com/docs/guides/agent-integration | 2026-08-17 | "ailang check gives structured errors designed for machine repair — check before running, and re-check after every edit." |
| https://ailang.sunholo.com/docs/guides/development-workflow | 2026-08-21 | "Default make test and CI test lanes set HTTP_PROXY and HTTPS_PROXY to http://127.0.0.1:9."; "Decision D5 deliberately leaves this route open" |
| https://ailang.sunholo.com/docs/feedback | 2026-04-29 | "We do not accept code pull requests for compiler, runtime, or standard library changes." |
| https://ailang.sunholo.com/docs/guides/evaluation/harness-setup | 2026-09-07 | "The executor uses codex exec --json --model <model> --dangerously-bypass-approvals-and-sandbox." |
| https://ailang.sunholo.com/docs/guides/evaluation/browser-auth-profiles | 2026-08-26 | "without any AI model ever receiving a password, a canonical profile, or the authority to change one."; "Authenticated sessions are not yet cleared for production use against real accounts." |

---

## 5. Tooling

| Area | What AILANG documents | Source (URL, page date) | Verbatim quote |
|---|---|---|---|
| Runtime | Tree-walking interpreter by default; opt-in bytecode VM | /docs/reference/implementation-status (2026-08-17); roadmap | "**Evaluator** \| Complete \| Tree-walking interpreter with modules". The `run` flag `--bytecode` ("Run via the bytecode VM instead of the evaluator") is in source help. The CHANGELOG notes "the bytecode VM (`--bytecode`, opt-in)". |
| Go codegen | Compile to Go; `extern func` implemented in Go | https://ailang.sunholo.com/docs/guides/go-interop (2026-04-20) | "Compile-time Codegen: Generate Go code with `ailang compile --emit-go`"; codegen "First call: ~0.001ms (native Go function)" |
| Go embedding | Embed the interpreter in Go hosts | same | "The `internal/embed` package lets you embed AILANG as a scripting/extension language in Go applications." |
| FFI and effects | `extern func` carries no effect row; effects become host-implemented Go interfaces | same | "extern func find_path(world: World, from: Coord, to: Coord) -> Path"; "AILANG effects (Rand, Clock, FS, Net, Env, AI) are compiled to Go interface calls." |
| "Compiles to Go" framing | why-ailang (2026-07-10) says it is not interpreted, which **conflicts** with the interpreter default above | https://ailang.sunholo.com/docs/why-ailang | "AILANG isn't interpreted — it compiles to typed, idiomatic Go code" |
| WASM / browser | Full interpreter in WASM, React component, JS effect handlers; release artifact `ailang-wasm.tar.gz` | https://ailang.sunholo.com/docs/guides/wasm-integration (2026-09-14) | "Complete AILANG interpreter compiled to WASM"; "Override any effect's operations with JavaScript callbacks. Auto-grants the named capability." |
| Playground | Browser REPL page; 9 live demos on sunholo.com | https://ailang.sunholo.com/docs/playground (2025-12-05); /docs/demos (2026-05-20) | "AILANG provides 9 interactive browser-based demos at www.sunholo.com/ailang-demos." |
| REPL | `ailang repl` with type display and an effects inspector | README; https://ailang.sunholo.com/docs/reference/repl-commands (2026-04-20) | "λ> :type \x. x + x" → "∀α. Num α ⇒ α → α"; ":effects <expr> - Inspect type and effects without evaluation" |
| Error registry | A machine-readable `error_codes.json` on every release | https://ailang.sunholo.com/docs/reference/errors (2026-07-13) | "Every release publishes error_codes.json as a release asset." |
| LSP | Built into the binary: diagnostics, hover, definition, references, symbols | https://ailang.sunholo.com/docs/guides/lsp (2026-05-16) | "gets diagnostics, hover types, go-to-definition, find-references, and document symbols"; out of scope: "completion, signature help, code actions, formatting, rename, …" |
| LSP contradiction | vision page (2026-02-12) predates the LSP | /docs/vision | "No **LSP/IDE servers** — AIs use CLI/API, not text editors" |
| Editors | `ailang editor install vscode\|vim\|neovim` | https://ailang.sunholo.com/docs/guides/editor-setup (2026-08-19) | "it builds the VSIX from the binary's embedded assets and hands it to whichever editor CLI it finds" |
| Formatter | `ailang fmt` | /docs/reference/formatter (2026-07-19); prompt | "Formatting never changes program meaning: Parse(fmt(x)) ≡ Parse(x)." (quoted from the prompt by the eval sub-reader) |
| Package manager and registry | `ailang.toml`, `ailang.lock`, exact pins, content and interface hashes, public GCS registry, `[effects].max` ceilings, `[bin]` shims, AGENT.md | https://ailang.sunholo.com/docs/guides/packages (2026-09-17) | "Packages declare their maximum allowed effects:" / "max = ["IO"]  # Only IO allowed; Net, FS, etc. would be a compile error" |
| Registry gates | Validator compiles, proves contracts with Z3 and checks effects; never runs package code | https://ailang.sunholo.com/docs/guides/package-publishing (2026-09-17) | "only your machine (the validator never executes package code)"; "A refuted contract is a gate everywhere." |
| Registry identity | Scoped publisher keys; no signing | same | "The key is the only identity."; "No version yanking yet." |
| Package catalogue | 56 `sunholo/*` packages + `world/core` listed on the site (auto-generated pages with Stability and Effects fields) | https://ailang.sunholo.com/docs/packages/sunholo | e.g. deontic page: "Stability experimental Effects IO" |
| Stdlib | 42 top-level modules + `std/ai/streaming` (stability page); "44 modules" (discovery page) | /docs/reference/stability (2026-07-12); /docs/guides/ai-stdlib-discovery (2026-07-14) | "Enumerated from `ls std/*.ail` (42 top-level modules)" |
| Streaming I/O | WebSocket, SSE, stdin lines, subprocess stdout, one deterministic multiplexed loop | https://ailang.sunholo.com/docs/guides/streaming (2026-04-20) | "all multiplexed through a single deterministic event loop" |
| Serving | REST + OpenAPI 3.1 + Swagger/ReDoc + MCP + A2A from `serve-api`; `ailang init web-app` React scaffold | /docs/guides/serve-api (2026-09-11) | "Serve AILANG module exports as auto-generated REST endpoints" |
| Semantic memory effects | `SharedMem` (CAS KV) and `SharedIndex` (SimHash/embedding search) | https://ailang.sunholo.com/docs/guides/semantic-caching-how-to (2026-09-04) | "SharedMem + SharedIndex is the cognitive working memory for AI agents." |
| Knowledge injection for coding agents | μRAG over hooks/MCP; brain cache | /docs/guides/microrag (2026-06-23) | "returns the single most relevant ≤150-token pointer" |
| Testing | Unit tests, QuickCheck-style properties with shrinking, inline `tests [...]` | /docs/guides/testing (2026-04-20) | "Shrinking: If failure, find minimal counterexample" |
| Diagnostics | Structured error codes, `--json`, `ailang check --format agent` | /docs/reference/cli (2026-09-21) | "`ailang check --format agent` selects a third rendering" |
| CI | `setup-ailang` GitHub Action | /docs/guides/getting-started (2026-09-04) | "with platform auto-detect, SHA256 verification, and binary caching" |
| Performance claims | Serve-api concurrency; list cost warnings | serve-api; limitations | "Sequential 5x DOCX parse: 285ms (57ms × 5) / Concurrent 5x DOCX parse: 261ms". Limitations (2026-08-21): "Prepending with `::` is quadratic; evaluator recursion is capped at 10,000 frames" |
| Release-gating latency probes | Six workload programs | /docs/guides/debugging (2026-09-21) | "`benchmarks/workloads/` holds six self-contained `.ail` programs that act as release-gating latency probes" |

---

## 6. Evaluation and benchmarks AILANG publishes

**Caveat.** The live dashboard pages (/docs/benchmarks/performance, /elo, /explorer, /gallery, /value, /os-model-leaderboard, /codebase-stats) render their numbers client-side. In static HTML they show "Loading benchmark data…". The numbers below come from the **data files those pages load**, fetched 2026-09-25. Each file is labelled; they are not page prose.

### 6.1 Current dashboard data
Source: https://ailang.sunholo.com/benchmarks/latest.json, which contains `"version":"v0.32.0"`, `"timestamp":"2026-08-27T17:23:05+02:00"`, `"totalRuns":1711`. **The cloud baseline is one month and ten releases old** (v0.32.0 vs v0.42.0).

**Overall, standard mode** (per-language aggregates in `languages`):

| | AILANG | Python |
|---|---|---|
| 0-shot success | 68.3% (873 runs) | 82.8% (838 runs) |
| final (after 1 self-repair) | 76.1% | 83.5% |
| agent mode (claude/codex/opencode harnesses) | 94.9% (257 runs; claude 96.4%, codex 94.3%, opencode 93.75%) | not run in agent mode in this file |

**By tier** (`tiers`):

| tier (benchmarks) | AILANG | Python |
|---|---|---|
| smoke (23) | 95.3% (43 runs) | 100% (46) |
| **core (23)** | **92.1% (252)** | **89.4% (246)** |
| stretch (25) | 81.9% (419) | 84.8% (420) |
| frontier (8) | 27.5% (142) | 57.4% (108) |
| vision (9) | 50.0% (14) | 83.3% (12) |

The evaluation README says core is the headline: "The Core tier pass rate is the primary headline metric on the dashboard and the number quoted in release notes." (https://ailang.sunholo.com/docs/guides/evaluation, page date 2026-08-17)

**By model** (`models.*.languages.*.successRate`, standard mode, all tiers):
- **AILANG ahead:** claude-fable-5 91.1 vs 64.2; claude-opus-5 94.6 vs 90.6; claude-sonnet-5 87.0 vs 86.8; gemini-3-6-flash 87.5 vs 86.8.
- **Python ahead in the other 14:**

| model | AILANG | Python |
|---|---|---|
| claude-sonnet-4-6 | 73.2 | 81.1 |
| gemini-3-1-pro | 83.8 | 91.4 |
| gemini-3-5-flash-lite | 58.9 | 73.6 |
| gemini-3-flash | 79.3 | 91.8 |
| gpt5-4-mini | 79.8 | 89.4 |
| gpt5-6-luna | 62.2 | 74.3 |
| gpt5-6-sol | 80.0 | 97.1 |
| gpt5-6-terra | 81.1 | 94.3 |
| or-deepseek-v4-flash | 67.6 | 82.9 |
| or-deepseek-v4-pro | 54.1 | 71.4 |
| or-glm-5-2 | 62.2 | 85.7 |
| or-kimi-k2-7-code | 64.9 | 80.0 |
| or-kimi-k3 | 83.8 | 91.4 |
| or-minimax-m3 | 51.4 | 60.0 |

Run counts per model are 35–89.

**Local models.** Source: https://ailang.sunholo.com/benchmarks/os/latest.json, with `"ailang_version":"v0.40.2"`, `"generated":"2026-09-21"`, `"trials":4`. AILANG only:
- motoko-local-qwen3-8-27b: 100% (core and stretch)
- opencode-qwen3-8-27b: 85.2% (core 95.8, stretch 87.5, frontier 33.3)
- pi-qwen3-8-27b: 61.4%

**Axiom scorecard.** Source: https://ailang.sunholo.com/benchmarks/axiom_scorecard.json, `"version":"v0.15.0"`, `2026-05-04`. Self-assessed: "totalScore": 23 / 24. Methodology: "Manual assessment against AILANG Design Axioms".

### 6.2 Dated snapshots in prose
- **Capability threshold.** https://ailang.sunholo.com/docs/guides/evaluation/model-capability-threshold (page date 2026-08-27; banner "DATED SNAPSHOT — not auto-refreshed"; numbers "standard mode, v0.23.0", June 2026).
  - Thesis: "above a certain capability level, models score higher on AILANG than on Python for the same coding tasks."
  - Tier rows: "Frontier … \| 80–90% \| 78–93% \| AILANG ≥ Python"; "Weak (GPT-5-mini, GPT-5) \| 14–15% \| 69–74% \| Python +55–59 pts".
  - Correlation: "AILANG% ~ SWE-bench Verified \| 0.70".
- **Three-camps self-audit.** https://ailang.sunholo.com/docs/guides/three-camps-self-audit (page date 2026-05-21; run 2026-05-20/21; claude-haiku-4-5 only; 49 smoke+core benchmarks).
  - "Python \| 38/49 \| 77.5%"; "AILANG \| 36/49 \| 73.4%"; "MoonBit \| 29/49 \| 59.1%"; "Aver \| 15/49 \| 30.6%"; Vera install-blocked.
  - On AILANG-strength benchmarks: "AILANG \| 12/16 \| 75.0%" vs "Python \| 11/16 \| 68.7%".
- **Intro page** (2026-09-04): "Core tier is the headline AILANG-vs-Python metric (87.3% vs 81.0% on v0.12.0 baseline)".
- **Codebase stats** (2026-06-23): "v0.21.x: 100% run_correct on VeraBench with Claude Haiku 4.5; AILANG an official VeraBench target".
- **Repo talk doc** (v0.10.15, Apr 2026; not on site):
  - "v0.9.1.1 eval baseline, 612 runs across 6 models"
  - "Claude Sonnet 4.6 \| 82.0% (41/50) \| 72.0% (36/50) \| +10.0%"
  - "Gemini 3.1 Pro \| 37.3% (19/51) \| 66.7% (34/51) \| -29.4%"
  - First eval: "Pass rate: 0%." at v0.3.5.
- **Blog numbers** (secondary):
  - https://www.sunholo.com/blog/if-you-cant-replay-it/ (2026-05-03, "AILANG v0.14.2 (April 2026)"): "In raw 0-shot generation Python still edges AILANG (76% vs 71.5%)"; "add a repair loop and AILANG flips it (82% vs 79%)"; "AILANG dominates with Claude (100% vs 92.6%) and Gemini (93% vs 86%)".
  - https://www.sunholo.com/blog/who-needs-fable-local-models-ailang/ (2026-06-22): "Claude Fable scored 97.3% in AILANG creation and it did it in one-shot"; "Motoko + Qwen3.6 35B could now ace 100% of the benchmarks, for free."

### 6.3 Eval infrastructure (what the evaluation pages describe)
- **Harnesses.** Claude Code, Codex, opencode, Pi, motoko, and Vertex Managed Agents. Cost-and-speed-budgets page (2026-06-23): "The 5 executors (claude/opencode/managed_agents/codex/pi) call budget.Add(input, output)".
- **Pinned Python baseline.** "Pinned version: Python 3.12" (evaluation README).
- **Measurement rigour.** https://ailang.sunholo.com/docs/guides/evaluation/measurement-contract (2026-07-29): canary gate, validity quarantine, paired McNemar ("No p-value below 10 discordant pairs.").
- **Honest about variance.** Local-ollama page (2026-09-11): "single-trial pass rates swing 5–7 benchmarks across consecutive runs of the same model on the same seed".
- **Frozen, hashed teaching prompts.** eval-loop page (2026-08-27): "Frozen prompt versions are also protected by the CI gate make check-prompt-freeze."
- **Prompt-injection benchmark.** IFC guide: it "scores models on producing code that `ailang verify` accepts as safe *and* correctly trips on the injected variant" (three-camps comparison, 2026-08-17).
- **The eval runs themselves are not sandboxed by the harnesses.** https://ailang.sunholo.com/docs/guides/evaluation/harness-setup (2026-09-07):
  - "The executor uses codex exec --json --model <model> --dangerously-bypass-approvals-and-sandbox."
  - "--format json --dangerously-skip-permissions" (opencode).
  - Managed Agents runs in a Google sandbox whose "network.allowlist is wildcard".

---

## 7a. Where AILANG is ahead of Sabline

This list is deliberately generous. "Ahead" means AILANG documents something that Sabline, as the task describes it, does not have, or AILANG's own evidence shows it doing more. Each item carries an AILANG quote and URL. **Check every item against Sabline's current state before publishing;** the description I was given of Sabline is short.

### Language and effect system
1. **More effects with first-class runtime controls: `Process`, `Stream`, `AI`, `Secret`, `SharedMem`/`SharedIndex`, `Declassify`.**
   - The Process effect has a binary allowlist pinned at startup and subcommand narrowing.
   - https://ailang.sunholo.com/docs/reference/effects (2026-09-11): "`git:status,git:commit,gh:pr:list` allows `git status …`, `git commit …` and `gh pr list …` and refuses every other invocation".
   - Sabline's listed effects are io, env, fs, net, clock, rand, ffi.
2. **Per-function budgets written in the signature, including a minimum.** Charged hierarchically.
   - https://ailang.sunholo.com/docs/reference/capability-budgets (2026-07-24): "`func i() -> () ! {IO @limit=5, Net @min=1 @limit=3} { ... }`".
   - Underrun check: "If a function with `@min` doesn't perform enough operations, it fails with a `BudgetUnderrunError`".
   - Sabline's counts, as described, are operator-side.
3. **Budgets on both sides that compose.** An operator run-wide ceiling plus source per-function limits; "a source @limit can only tighten" (agent-tool-policy, 2026-09-23, v0.41.0).
4. **Open-vocabulary information-flow labels, with a declassification effect you can grep for.**
   - https://ailang.sunholo.com/docs/guides/ifc-labels (2026-08-17): "Labels are not a fixed vocabulary"; labels join ("`string<email ⊔ pii>`").
   - Sinks refuse a label: "`T{not LABEL}`".
   - Declassification is visible: "every sanitiser is locatable by `grep -r '! {Declassify}'`".
   - This goes further than a single `Secret of T` type: `<pii>`, `<tenant-a>`, `<llm>`, `<email>` and so on.
5. **Secrets resolved from a vault, gated by a human on a phone.**
   - https://ailang.sunholo.com/docs/guides/secret-approvals (2026-06-23): "resolves 1Password references (`op://Vault/Item/field`)"; "gated on a **human approval pushed to your phone**"; "Fail closed".
   - The same page says it is "Code-complete — deploy-gated".
6. **Effect modes in the type.** `Rand[mode=os|seeded|crypto]` each has a replay contract; `AI[mode=routeable]` must be declared before provider routing (parameterised-effects, 2026-07-28; ai-routing, 2026-06-05).
7. **Effect-row polymorphism across agent tool loops.** ai-effect (2026-05-05): "`runTools` infers `! {AI, FS, Process}` automatically".
8. **Package effect ceilings, checked by the compiler and again by the registry.**
   - packages (2026-09-17): "max = ["IO"]  # Only IO allowed; Net, FS, etc. would be a compile error"; "Verifies effect ceilings match `[effects].max`".
   - The interface hash covers effects: "Interface hash (SHA256 of exports + effects — stays same on internal refactor)".
   - Publish warns on widening: "`effect-widening-warning` — when effect ceiling expanded".
   - Sabline may have partial parity through its own dependency tooling; compare.
9. **Env vars allowlisted by name, with redaction in traces on by default.**
   - env-vars (2026-09-19): "`AILANG_REDACT_ENV` \| `on`".
   - The `--allow-env` flag appears in source; the docs only say "(with an allowlist)" (effects page).

### Runtime confinement, policy and network hardening (as of v0.41.0)
10. **An operator policy file with supervised execution.** One TOML file sets: caps, one FS root, write-deny globs, host allowlist, whole-run `timeout_ms`, output/source/module-graph byte caps, pinned entrypoint, pinned AI provider, and per-effect aggregate `[budgets]`.
    - The worker runs "in its own process group with a control pipe"; "every widening flag … is refused **by name**" (agent-tool-policy, 2026-09-23).
    - The admission line banks "`module_graph` (`digest`, `files`, `bytes`)" and "`policy_digest` (sha256 of the policy bytes)".
    - I found no Sabline equivalent to the whole-run timeout, output cap or module-graph freeze in the description given. Check.
11. **Write-protecting the agent's own supply chain.** "`fs_deny_write` … `".github/**"`, `".pi/**"`, `"Makefile"`, `"*.yml"`"; "`.git/**` is always implied in restricted mode" (agent-tool-policy).
12. **Confined git adapter.** "the argv is **built** from a per-subcommand schema … global/system config disabled … `.git/` is read-only" (agent-tool-policy).
13. **Network hardening defaults.** Each item below is documented; compare one by one with Sabline's `net:host:port`.
    - "HTTPS enforcement (configurable)"; "Private IP blocking"; "DNS rebinding prevention" (effects page).
    - Per-hop redirect re-authorisation and stripping of "`Authorization`/`Cookie`/`Proxy-Authorization` … across origins".
    - "Loopback, private, link-local and metadata addresses are refused in restricted mode with no override" (agent-tool-policy).
    - Body cap: "Net body cap \| Each HTTP response body \| 5 MB" (debugging, 2026-09-21).
14. **Kernel-anchored FS containment and a matching checker.** debugging (2026-09-21): "all FS operations go through one `os.Root` handle"; "what `sandbox-check` says is what `readFile` will do".
15. **A public, reproducible security self-audit with counterexample tests.**
    - Design doc `m-executor-policy-hardening.md`: "every counterexample test was written first and failed on the audited baseline".
    - CHANGELOG v0.41.0: "on the audited baseline 118 rows failed". (Strength: transparency. Weakness: see 7b.)

### Verification
16. **Broad Z3 fragment with counterexamples.** contracts (2026-04-30):
    - Strings via Z3 string theory; lists via sequences; records via datatypes; ADTs.
    - Cross-function `define-fun` inlining.
    - Bounded recursion unrolling ("depth 1-10, default 2"), with per-function `@verify(depth: N)`.
    - HOFs "with **known lambda arguments**"; bounded `forall`.
    - `--json`, `--strict`.
    - Counterexamples such as "Counterexample: discountPercent=101, age=YOUTH, tier=LOW".
17. **Contracts are proven when a package is published.** package-publishing (2026-09-17): "The validator verifies `requires`/`ensures` contracts package-wide"; "A refuted contract is a gate everywhere."
18. **Z3 in the browser.** Landing page (v0.42.0) demo tags "WASM Z3"; demos page: "Static contract verification with the Z3 theorem prover."
19. **Property-based testing with shrinking, plus inline tests.** testing (2026-04-20): "Shrinking: If failure, find minimal counterexample".
20. **A static "no silent fallback" lint that becomes a hard error at publish.** strict-fallbacks (2026-07-24): "`ailang check --package dir/` \| **Hard error**".

### AI and agents
21. **AI calls as a typed effect across many providers.**
    - Anthropic, OpenAI, Google (API key or ADC), Ollama, OpenRouter "~100 models", and config-only custom providers ("no Go code, no binary fork"; custom-ai-providers, 2026-05-05).
    - Typed `AIError`, a deterministic `--ai-stub`, streaming, and in-language `step`/`runTools` tool loops (ai-effect, 2026-05-05).
22. **Routing provenance and cost in traces.** ai-routing (2026-06-05): "records the resolved model, fallback chain, prompt/completion/cached tokens and USD cost".
23. **Any module becomes an MCP, A2A or REST/OpenAPI server with one command.** serve-api (2026-09-11): "Expose AILANG functions as MCP tools"; "Google's A2A protocol is enabled with the `--a2a` flag".
24. **A hosted public docs MCP with version-scoped tools, plus a local execution MCP.** agent-mcp (2026-07-29): "exposes ~21 typed tools"; "Version-scoped tools take an optional `for_version` argument".
25. **Claude Code and Codex plugins.** README: "/plugin marketplace add sunholo-data/ailang_bootstrap"; "codex plugin marketplace add sunholo-data/ailang_bootstrap --ref stable".
26. **A production agent lane where agents run code only through policy-gated AILANG.** coordinator (2026-09-17): "the lane where an agent executes programs only by submitting AILANG source to a policy it cannot edit"; fleet "41 agents".
27. **Multi-agent orchestration shipped in the same binary:**
    - coordinator, inboxes, worktrees, human approval gates (dashboard, CLI, GitHub labels, mobile), reject-with-feedback loops, a messaging bus with semantic search, mission loops, vendor-independence rules, notification daemons, a web dashboard (coordinator; agent-messaging; mission-*; collaboration-hub).
    - Intro (2026-09-04): "AILANG ships the loop *around* the code, not just the code itself".
28. **Per-attempt agent receipts and durable agent work-item execution.**
    - mission-role-dispatch (2026-09-18): "The JSONL receipt is exclusively created with mode 0600."
    - mission-iteration (2026-09-08): leases, fencing, frozen resume, reconciliation.
    - These are receipts about agent dispatch, not program runs. They are not signed.
29. **Tracing tiers, OTEL export, and training-data export.**
    - traces (2026-04-10): "`ailang replay trace.jsonl`"; "Export high-quality traces as fine-tuning data for AI models".
    - Intro: "`--trace-tier off|standard|deep`".
    - Value-blind mode: debugging: "`AILANG_TRACE_VALUES=off` records the complete call tree with no payloads."
30. **In-language semantic memory for agents.** semantic-caching-how-to (2026-09-04): "SharedMem + SharedIndex is the cognitive working memory for AI agents."

### Tooling and distribution
31. **Single Go binary with Go codegen and a Go embedding API.** go-interop (2026-04-20): "Generate Go code with `ailang compile --emit-go`". Sabline is Python, with a Rust runtime in progress.
32. **WASM build with a React component, a browser playground and 9 live demos.** wasm-integration (2026-09-14); demos (2026-05-20).
33. **An LSP built into the binary, plus one-command installs for VS Code forks, Vim and Neovim.** lsp (2026-05-16); editor-setup (2026-08-19).
34. **A public package registry.**
    - Exact pins, content and interface hashes, "no code runs at install time" (per the blog; the docs say the validator never executes package code).
    - Scoped publisher keys, a machine-readable quality report, auto-generated package doc pages, and `[bin]` command shims (packages; package-publishing).
    - 56 `sunholo/*` packages are listed on the site.
35a. **Diagnostics built for machines.**
    - A per-release `error_codes.json` with "code, category, summary, and fix_hint fields" (errors index, 2026-07-13).
    - Effect-row mismatch errors give the source span of each extra effect (typ_effect_row_mismatch, 2026-05-06).
    - REPL "`:effects <expr>` - Inspect type and effects without evaluation" (repl-commands, 2026-04-20).
    - A fail-closed formatter with an agent-hook exit-code contract (formatter, 2026-07-19).
35. **A broad stdlib (42–44 modules).** Includes XML, HTML5, YAML, ZIP/TAR/GZIP/deflate, JWT, crypto, RE2 regex, datetime, streaming and web search (stdlib, 2026-07-14; stability, 2026-07-12).
36. **Supply-chain signals.** Keyless cosign-signed release archives with SHA256SUMS, an installer that verifies them, and OpenSSF Scorecard / Best Practices, SonarCloud and CodeQL badges (SECURITY.md; README). The SLSA claim is not visible on the release assets; see §1.
37. **Release cadence and governance documents.** 173 GitHub releases in a year (v0.42.0 on 2026-09-23); SECURITY.md sets response times: "Acknowledgement: within 3 business days"; "critical issues within 14 days". GOVERNANCE.md exists.

### Evaluation and evidence
38. **Much larger public evaluation.**
    - 18 cloud models; agent harnesses: Claude Code, Codex, opencode, Pi, motoko, Managed Agents.
    - Pinned Python 3.12 baseline, tiers, ELO, cost and speed, paired statistics, canaries.
    - A nightly local rig with N≥3 trials, a public dashboard and downloadable data (§6).
39. **Published AILANG-vs-Python numbers, including losses.**
    - Core tier 92.1% vs 89.4%; frontier tier 27.5% vs 57.4%; overall 0-shot 68.3% vs 82.8% (latest.json, v0.32.0, 2026-08-27).
    - Agent mode 94.9% (257 runs).
    - Peer comparison: AILANG 73.4%, Python 77.5%, MoonBit 59.1%, Aver 30.6% (three-camps self-audit, 2026-05-21).
40. **Frozen, hashed teaching prompts, and runtime syntax injection.** eval-loop: "Frozen prompt versions are also protected by the CI gate make check-prompt-freeze."; microRAG A/B "+4 benchmarks … from 30/34 to 34/34" (capability-threshold snapshot, v0.23.0).
41. **A published competitive-landscape survey placing AILANG among 16 AI-native languages.** three-camps-comparison (2026-08-17). It also has a peer runner harness for MoonBit and Aver.

## 7b. Where the docs show no equivalent to a Sabline feature

All searches were run 2026-09-25 over the 144 Markdown sources, the 205 rendered pages, the repo root docs, `docs/LIMITATIONS.md`, `llms.txt` and the CHANGELOG where noted. Each line says what I searched.

1. **OS-level confinement under the interpreter.** AILANG's docs (read 2026-09-25) describe no seccomp, Landlock, macOS sandbox profile or Windows job-object confinement.
   - Searched: "seccomp", "landlock", "sandbox_init", "sandbox-exec", "gvisor", "firecracker", "nsjail", "bubblewrap" (0 hits).
   - What they do describe: `os.Root` path containment and process-group kill.
   - They hand CPU and memory to the host: "does not bound CPU or memory (host isolation is the container's job)"; "Windows and `GOOS=js` refuse restricted mode" (agent-tool-policy).
   - A blog post says the opposite: "If your AI uses AILANG then you don't need sandboxes, containers…" (https://www.sunholo.com/blog/introducing-daneel/, 2026-09-19).
2. **Port-level network grants.** The docs describe no port-scoped grant. `--net-allow-domains` and `net_allow` are domain or host lists. Searched "port" together with net_allow / net-allow / allowlist in the effects, agent-tool-policy and LIMITATIONS pages and the CHANGELOG v0.41.0 entries.
3. **Several path grants, or a read-only path grant, on a normal run.**
   - The docs describe one FS root per run (`AILANG_FS_SANDBOX` / `fs_sandbox`).
   - Read-only exists only as `fs_deny_write` globs inside that root, and only in policy mode.
   - They describe no `fs:read:<path>`-style grant. Searched "fs_sandbox", "AILANG_FS_SANDBOX", "read-only", "fs_deny_write".
4. **Refusals the program cannot catch, as a stated guarantee.**
   - The docs do not state whether refusals can be caught.
   - Allowlist refusals are documented as `Err` values the program matches on: `DisallowedHost`, `NotAllowed`, AI `BudgetExhausted`.
   - Searched "catch", "uncatchable", "cannot be caught", "recover".
5. **A pre-run report of everything a program can touch** (paths, hosts, counts), like `sabline audit`. The docs describe no such report. The closest documented tools:
   - `ailang run --policy` admission (a yes/no subset check that names `missing_from_policy`);
   - `ailang docs --all-functions` (stdlib effect rows);
   - `ailang iface` (module interface JSON);
   - package `[effects].max`;
   - serve-api `/api/_meta/modules`.
   - Searched "audit" (hits are about approvals, design reviews and dashboards), "policy-check", "iface", "effects_used".
6. **Automatic runtime fallback for contracts the prover cannot discharge.**
   - The docs describe runtime contract checking as an opt-in flag: "Enable runtime contract verification with the `--verify-contracts` flag" (contracts page). The prompt calls it an "alternative to static verification".
   - Z3 skips effectful functions: "Effectful functions \| Nondeterminism breaks proofs".
   - Searched "fallback" and "verify-contracts" on the contracts page, the prompt and the CLI reference.
7. **Fallibility declared in signatures.** The docs describe no fallibility annotation; errors are `Result`/`Option` values. Searched "fallib", "throws", "raises" (0 relevant hits).
8. **Signed receipts or attestations for program runs** (in-toto or similar). The docs describe none. What exists:
   - release archives signed with cosign;
   - admission lines with policy and module-graph digests;
   - unsigned JSONL receipts for agent dispatch.
   - Searched "attest", "in-toto", "intoto", "receipt", "provenance", "signed".
9. **An effect or capability for FFI.** The docs describe none for `extern func` (Go codegen FFI). The example signature has no effect row, and the listed extern restrictions concern generics, names and return types. Searched go-interop for "extern", "effect", "caps".
10. **Budgets over contracted resources beyond counts** (bytes per path, per host). Operator ceilings are counts per effect label (`[budgets] FS = 100`) plus global byte caps (`max_fs_transfer_bytes`, `max_output_bytes`). The docs describe no per-path or per-host count. Searched agent-tool-policy and capability-budgets.

**Also check.** These are AILANG's self-reported gaps, which may be Sabline strengths:
- IFC sink enforcement is "intraprocedural", and cross-module sinks "rely on Z3 contracts" (ifc-labels).
- Labelled secrets still reach `deep` traces (debugging, 2026-09-21: "A `string<secret>` value crossing a traced call boundary is written to the trace in full").
- Parameterised modes other than Rand are not dispatched at runtime.
- "the runtime currently treats all modes identically" (prompt v0.16.x). The parameterised-effects guide says Rand dispatch shipped in "Phase 3 (v1.0.0 …)". **These disagree.**
- The AI effect's HTTP client "is not the Net authorizer" (LIMITATIONS).
- Before v0.41.0 (2026-09-21) the FS sandbox and domain allowlist could be escaped (§2.8).

---

## 8. What this contradicts or refines in the earlier notes

**Earlier note:** "grants are whole categories (`--caps Net`) plus call counts; `@limit` written in the function signature, e.g. `func fetchData() -> string ! {Net @limit=5}`"

| Part of the note | Verdict | Evidence |
|---|---|---|
| `--caps` grants whole effect categories | **Still true** of `--caps` itself | Planned design doc `m-effect-scope-params.md` (2026-07-11): "Capabilities today are effect-granular: `--caps Rand` grants ALL Rand operations." Signature-level scopes (`FS[scope=…]`, host allowlists as scopes) are planned or future work, now targeted at v1.1.0. |
| …so a grant cannot be narrowed | **Refine: the operator can narrow outside the type** | Effects page (2026-09-11): `--net-allow-domains` domain allowlist; `AILANG_FS_SANDBOX` directory root; `--process-allowlist` binaries and subcommands (`git:status`); `--net-allow-http/localhost/metadata`; `--net-timeout`; `--process-timeout`/`--process-max-output`. `--allow-env` (env-var names) is in source help text; the docs only say "(with an allowlist)". |
| "plus call counts" | **Refine: two kinds of count** | (1) Source `@limit`/`@min`, per invocation, charged to every active ancestor frame (effects page). (2) Operator `[budgets]` in the policy TOML: an aggregate ceiling per run that source `@limit` "can only tighten". Shipped v0.41.0 (2026-09-21). |
| "`@limit` written in the function signature" | **True for source budgets**, but no longer the only place | Operator counts now live in `agent-policy.toml` `[budgets]` (agent-tool-policy page, 2026-09-23). No plain `ailang run` flag sets an operator count; it is policy-file only. |
| Implied: the program cannot tell which host it may reach | **Refine** | A disallowed host comes back as a value: "`DisallowedHost(string) -- Domain not in allowlist`" (examples/ai-api-integration, 2026-07-10). The program can match on it and continue. |
| Implied: the operator cannot bypass source budgets | **Refine** | Plain `ailang run` has "`--no-budgets`" to bypass source budgets (effects page). It is refused under `--policy` (CHANGELOG v0.39.0), and operator budgets are "untouched by `--no-budgets`" (CHANGELOG v0.41.0). |
| Implied: FS/Net restrictions were sound | **Only since v0.41.0** | Design doc `m-executor-policy-hardening.md` (2026-09-21) reproduced sandbox escape via `../` and symlinks, and allowlist escape via redirect. Fixed in v0.41.0 with `os.Root` and per-hop authorisation. |

**Blog post:** https://www.sunholo.com/blog/what-is-your-ai-allowed-to-touch/
- Author and date: "Mark Edmondson, Founder". `article:published_time` = 2026-04-26. Tags: ai-delegation, capabilities, security, ailang. Second of a six-part series.
- Release current on that date: **v0.14.1** (GitHub releases API). v0.14.2 was published 2026-04-26T22:23Z. v0.15.0, which added parameterised effects, followed on 2026-05-04.
- Checked against today's docs:

| Blog claim (verbatim, 2026-04-26) | Status against docs read 2026-09-25 |
|---|---|
| "every function declares its permissions in its type signature, and the runtime refuses to execute anything that hasn't been explicitly granted" | **Consistent** (effects page). Nuances: `--caps ALL` exists ("development only!"); `--caps auto` infers the grant set from the entrypoint (source help text; packages guide "caps auto"). |
| "Run it without granting `Net` at the command line and it refuses to execute — not a warning, a hard stop." | **Consistent** for a missing capability. Allowlist refusals (host, process) come back as `Err` values the program handles; that is a different refusal. |
| "Add `@limit=5` and the function gets exactly five network calls before the runtime cuts it off." | **Consistent, with a scope nuance.** Budgets are **per invocation**: "Each function **call** gets a fresh budget" (capability-budgets). Five per call, not five per program. Nested calls also charge ancestor frames. `--no-budgets` bypasses this on plain `ailang run`. |
| Tier 2 "Infrastructure Controls" … "Can't scope per-function or per-call" versus Tier 3 "Checked at compile time, enforced at runtime" / "Per-function granularity with budgets" | **Consistent.** Worth adding: AILANG's own finer controls (host allowlist, FS root, process allowlist) are invocation or policy flags, i.e. tier-2-like and outside the signature. The effects page says so: "The allowlist is a property of the **invocation**, not of the program's signature". |
| Example `func fetchData() -> string ! {Net @limit=5}` with "-- Run: ailang run --caps Net --entry main app.ail" | **Syntax consistent** with the capability-budgets page (`! {Net @limit=100}`). |
| Five-row "capability envelope" (spend money, send messages, read data, external actions, call other agents) | **An advisory checklist, not an AILANG feature.** The blog says "AILANG is one answer." |

- **Not in the blog but relevant.** Since the post: v0.26.0 `Secret` effect and IFC-enforced secrets; v0.39.0 `ailang run --policy`; v0.41.0 hardened confinement plus operator budgets. A page that cites only the blog **understates** AILANG's current narrowing.

---

## 9. Inconsistencies and stale content in AILANG's own docs

Don't quote these pages as current without checking. Most useful first.

1. **Blog vs docs on isolation.**
   - Blog (2026-09-19): "If your AI uses AILANG then you don't need sandboxes, containers, or buying 100 Mac minis to ensure separation".
   - agent-tool-policy (2026-09-23): "does not bound CPU or memory (host isolation is the container's job)".
2. **Interpreter vs "compiles to Go".**
   - why-ailang (2026-07-10): "AILANG isn't interpreted — it compiles to typed, idiomatic Go code".
   - implementation-status: "Tree-walking interpreter"; `ailang run` uses the evaluator, and codegen is `--emit-go`.
3. **LSP.** vision (2026-02-12): "No **LSP/IDE servers**". README and the LSP guide say the LSP ships (from v0.20.x per codebase-stats).
4. **implementation-status (2026-08-17) is stale.**
   - It lists "Pattern guards parsed but not evaluated" and "String interpolation (use `++` concatenation)" as open.
   - limitations (verified 2026-08-17) lists both as resolved (v0.6.2, v0.12.1).
5. **When Z3 verification shipped.** contracts: "Phase 1 (v0.7.4) — Static verification with Z3". ifc-labels / three-camps: "shipped in v0.9.x".
6. **Parameterised-mode runtime dispatch.**
   - Teaching prompt v0.16.x (per the eval sub-reader): "the runtime currently treats all modes identically (mode-aware dispatch lands later)".
   - parameterised-effects guide: "Phase 3 (v1.0.0, M-EFFECT-REPLAY-CONTRACTS) makes the Rand modes differ at runtime." The guide labels this v1.0.0 while the release is v0.42.0.
   - The same guide's Future-work list still calls Phase 3 future.
7. **AI routing page contradicts itself.** It documents `!{AI[mode=routeable]}` as shipped in v0.15.0, and under "Deferred (intentionally)" still says "AILANG effects are flat label-strings today, not parameterised rows".
8. **module_execution** (commit 2026-07-10): "Effects are type-checked but not enforced at runtime in v0.2.0." followed by "Runtime effect enforcement is live". Its header says v0.5.11; its footer says "December 2025".
9. **Budget charging semantics.**
   - vision (2026-02-12): "Callers are charged the callee's declared budget (semantic charging)".
   - effects page (2026-09-11): actual operations "charge the current (innermost) frame **and** all active ancestor frames".
10. **Operator budgets vs capability grants.** capability-budgets (2026-07-24) says budgets are checked per call only. It predates the v0.41.0 operator `[budgets]` and does not mention them.
11. **serve-api.** One table says effects are "Pure functions only"; the same page documents `--caps` for effectful handlers. Separately, MCP and A2A "bypass auth".
12. **Teaching prompt markdown vs live page.**
    - Committed `docs/docs/prompts/current.md` (2026-07-28) is v0.16.3 with an H1 of v0.16.2. The live `/docs/prompts/current` serves v0.16.6.
    - `llms.txt` is dated "Last updated: 2026-05-16" and bundles prompt v0.16.0.
13. **SLSA.** SECURITY.md says every release since v0.15.x carries `multiple.intoto.jsonl`. The release assets I checked (v0.15.1, v0.20.0, v0.30.0, v0.40.2, v0.41.0, v0.42.0) have none.
14. **There is no `main` branch.**
    - `gh api …/branches/main` returns 404, and `https://github.com/sunholo-data/ailang/blob/main/docs/LIMITATIONS.md` returns HTTP 404 (checked 2026-09-25).
    - So every docs link of the form `blob/main/...` is dead. That includes the agent-tool-policy "execution policy residuals" link, CHANGELOG links on implementation-status and intro, the strict-fallbacks example link, and the release notes' `web/README.md`.
    - GOVERNANCE.md still describes "merging to `main`" and "promoting `dev` → `main`".
15. **Fleet and executor pages disagree about which executors exist.**
    - Coordinator pages say "(currently Claude Code)" but also "no `claude`" in the fleet.
    - Gemini is retired but still appears in several examples.
    - Executor counts: 4, 5 or 6 depending on the page.
16. **Examples that under-declare effects** (doc errors or real permissiveness; test before citing).
    - semantic-caching-vs-vectordb: `cached_git_diff … ! {IO, SharedMem, SharedIndex}` runs `_shell("git diff ${commit}")`.
    - semantic-search: `_ollama_embed(…) ! {IO}` makes network calls.
    - semantic-caching-how-to: `get_or_compute … ! {SharedMem}` calls `_clock_now`.
17. **Workspaces page** calls "Unknown workspaces default to "public"" a "Safe Default".
18. **Eval pages.**
    - "four tiers" but five listed.
    - The capability-threshold snapshot gives three different thresholds (80% / ≥70% / ~55% SWE-bench).
    - Model counts 14 vs 19.
    - model-configuration is still "October 2025".
    - Two different default models.
19. **Reference pages, from the reference sub-reader.**
    - **Partial application.** language-syntax shows `add(5)` "Partial application (currying)". The errors index says "AILANG has strict arity and no partial application".
    - **Loops and CSP.** language-syntax shows `loop { … }` / `spawn` under "Concurrency (CSP)" with no planned marker. no-loops excludes `loop`, and limitations defers CSP.
    - **Effect handlers.** They are described as adopted: lineage says "explicit handlers"; the effect-row error page says "Wrap the effectful call in a handler that eliminates the effect". But user-definable handlers are only on the roadmap (v1.1.0).
    - **Wrong effect in an example.** architecture/types shows `readFile : string -> ! {IO | e} string`; elsewhere readFile needs FS.
    - **Stale syntax page.** language-syntax is headed "AILANG v0.6.0" and still lists quasiquotes as "Planned v0.4.0+".
    - **Design-docs index drift.** The md says "1072 design documents across 131 versions"; the live page says "1109 … 141 versions".
    - **Package inconsistencies.**
      - deontic is described as "Pure obligation-reasoning engine" but lists effect IO.
      - The decisions package says its calls are "outside the AI effect's budget/trace-cost accounting", which is relevant to AI spend ceilings.
20. **Package pages.**
    - The motoko-extension page says the validator runs `_smoke.ail`. package-publishing says "the validator never executes package code".
    - "immutable once published" vs the superuser "`unpublish` of anything".
    - `[effects].max` is a compile error in packages, but only a "badge" at `experimental` stability in package-publishing.

---

## 10. URL ledger

Everything was accessed **2026-09-25**. "Page date" is the last git commit on `dev` touching the page source. "Registry Last Updated" is the date printed on auto-generated package pages.

### 10.1 Failed, empty or JS-only
| URL | Result |
|---|---|
| https://www.sunholo.com/sitemap.xml | **404** (GitHub Pages "Page not found"). I used the blog index instead. |
| https://github.com/sunholo-data/ailang/blob/main/docs/LIMITATIONS.md, and any `blob/main/...` link | **404**: the repo has no `main` branch (`gh api …/branches/main` → 404) |
| https://ailang.sunholo.com/docs/benchmarks/performance, /elo, /explorer, /gallery, /value, /os-model-leaderboard, /codebase-stats | HTTP 200, but numbers render client-side. **Read the underlying data files instead** (below). |
| https://ailang.sunholo.com/docs/packages/explorer, /docs/packages/graph | HTTP 200, JS-only ("Loading packages from registry...") |
| https://ailang.sunholo.com/ (landing) | HTTP 200. The benchmark strip is client-side ("Loading benchmarks..."); the rest is static. |
| Package pages' "version history" widget | Client-side ("Loading version history from registry...") on every `/docs/packages/sunholo/*` page |
| GitHub release body for v0.42.0 | Present but has no changelog content ("## What's Changed" is empty) |

**No docs-site page returned an error.** All 205 sitemap URLs returned HTTP 200.

### 10.2 Other sources read
**GitHub API** (`gh api`):
- `repos/sunholo-data/ailang`
- `…/releases/latest`
- `…/releases?per_page=100` (2 pages, 173 releases)
- `…/tags`
- `…/contributors`
- `…/branches`
- `…/releases/tags/{v0.41.0,v0.40.2,v0.30.0,v0.20.0,v0.15.1}` (assets)
- `…/contents/.github/workflows`
- `…/git/trees/dev?recursive=1`
- `…/commits?path=…` (144 docs files)
- `repos/sunholo-data/ailang_bootstrap`

**Raw repo files** (dev):
- README.md, CHANGELOG.md, changelogs/v0.32-current.md, SECURITY.md, GOVERNANCE.md, ARCHITECTURE.md, AGENTS.md, CONTRIBUTING.md, MOTOKO.md (downloaded; I relied on README, SECURITY and GOVERNANCE)
- docs/LIMITATIONS.md, docs/VISION.md, docs/README.md, docs/TESTING.md, docs/talk-building-a-language.md, docs/docs-sync-findings.md, docs/guides/inline_tests.md, docs/guides/module-imports.md, docs/reference/reserved-keywords.md, docs/testing/REGRESSION_GUARDS.md
- docs/src/constants/version.js
- .github/workflows/release.yml (grep for SLSA)
- cmd/ailang/main_run.go and cmd/ailang/run_policy.go (flag definitions only; **source, not docs**, labelled wherever used)

**Design docs read** (dev):
- implemented/v0_39_0/m-agent-ailang-only-execution.md (head, status)
- implemented/v0_41_0/m-executor-policy-hardening.md (full)
- planned/v1_0_0/m-effect-refinement.md (status)
- planned/v1_0_0/m-effect-scope-params.md (full)
- planned/v1_1_0/m-agent-safe-runner.md (head)
- planned/v0_36_0/m-trace-label-aware.md (head)
- planned/v0_31_0/m-mem-budget-runtime.md (status)
- planned/v0_33_1/m-net-effect-proxy-boundary.md (status)
- rejected/m-fs-runtime-caps.md (full)

The repo has **1,749** files under `design_docs/`. I did **not** read all of them. They are indexed on /docs/design-docs, which was read in full.

**Docs-site data files:**
- https://ailang.sunholo.com/sitemap.xml (205 URLs)
- https://ailang.sunholo.com/benchmarks/latest.json (v0.32.0, 2026-08-27)
- https://ailang.sunholo.com/benchmarks/os/latest.json (v0.40.2, 2026-09-21)
- https://ailang.sunholo.com/benchmarks/axiom_scorecard.json (v0.15.0, 2026-05-04)
- https://ailang.sunholo.com/llms.txt ("Last updated: 2026-05-16")

**Blog** (https://www.sunholo.com/blog/): the index was read. These posts were fetched; publish dates are from `article:published_time`.
- **Read in full:**
  - what-is-your-ai-allowed-to-touch (2026-04-26), the target post
- **Read in relevant part:**
  - introducing-daneel (2026-09-19)
  - if-you-cant-replay-it (2026-05-03)
  - who-needs-fable-local-models-ailang (2026-06-22)
  - ailang-v09 (2026-03-20)
- **Grepped only**, for capability, sandbox, Z3, replay and policy claims:
  - model-menagerie (2026-08-28), verification-trust-abstraction (2026-08-03), hand-decisions-to-machines (2026-08-11), ai-loop-engineering-dark-software-factory (2026-07-19), ai-workflows-beyond-extraction (2026-07-13), ai-coding-an-ai-coding-harness (2026-06-29), ap-accounts-payable-ai-workflow (2026-06-08), ida-driving-ai-talk-2026 (2026-06-02), any-ai-that-cant-say-i-dont-know (2026-05-24), ai-freedom-tight-brief (2026-05-17), dont-ask-the-ai (2026-05-10), wrong-question-ai-trust (2026-04-19), ailang-parse-launch (2026-04-13), ailang-demos-launch (2026-03-25), press-introducing-ailang (2025-10-15)
- **Not fetched:** older non-AILANG posts (cognitive-design, dynamic-output-mdx, subconscious-genai, ai-protocol-revolution, website-builder, aipla-update, using-ai-to-buy-and-sell-a-house, upcoming-talks-2026-q2, ai-platform-physics-students, ai-protocols-in-paradise-opatija).

### 10.3 Docs site, all 205 sitemap URLs
Each page was read in full: by me, or by one of the five parallel sub-readers, working from the Markdown source or, for generated pages, the rendered text.
- **Older teaching-prompt pages** (`/docs/prompts/v0.8.2` … `v0.16.5`) were **diffed** against their successors, not read line by line.
- **`/docs/prompts/current`**, the live v0.16.6 page, was read in full.

| Path (https://ailang.sunholo.com…) | HTTP | Page date | Source file (docs/docs/…) | Note |
|---|---|---|---|---|
| `/docs` | 200 | 2026-09-04 | intro.mdx |  |
| `/docs/architecture` | 200 | 2026-09-04 | architecture/index.md |  |
| `/docs/architecture/adding-operators` | 200 | 2025-12-17 | architecture/adding-operators.md |  |
| `/docs/architecture/anf` | 200 | 2025-12-24 | architecture/anf.md |  |
| `/docs/architecture/debug-tools` | 200 | 2025-12-17 | architecture/debug-tools.mdx |  |
| `/docs/architecture/types` | 200 | 2025-12-24 | architecture/types.md |  |
| `/docs/benchmarks/codebase-stats` | 200 | 2026-06-23 | benchmarks/codebase-stats.mdx | charts load client-side |
| `/docs/benchmarks/elo` | 200 | 2026-06-12 | benchmarks/elo.md | ratings load client-side |
| `/docs/benchmarks/explorer` | 200 | 2026-07-13 | benchmarks/explorer.md | tables load client-side ("Loading benchmark data…") |
| `/docs/benchmarks/gallery` | 200 | 2026-07-13 | benchmarks/gallery.md | gallery loads client-side ("Loading benchmarks…") |
| `/docs/benchmarks/os-model-leaderboard` | 200 | 2026-07-21 | benchmarks/os-model-leaderboard.md | table loads client-side (read /benchmarks/os/latest.json) |
| `/docs/benchmarks/overview` | 200 | 2026-07-13 | benchmarks/overview.md |  |
| `/docs/benchmarks/performance` | 200 | 2026-07-13 | benchmarks/performance.md | numbers load client-side (read /benchmarks/latest.json) |
| `/docs/benchmarks/value` | 200 | 2026-05-05 | benchmarks/value.md | dashboard loads client-side |
| `/docs/demos` | 200 | 2026-05-20 | demos.mdx |  |
| `/docs/design-docs` | 200 | 2026-09-11 | design-docs.md |  |
| `/docs/examples` | 200 | 2026-09-04 | examples.mdx |  |
| `/docs/examples/ai-api-integration` | 200 | 2026-07-10 | examples/ai-api-integration.mdx |  |
| `/docs/feedback` | 200 | 2026-04-29 | feedback.mdx |  |
| `/docs/guides/agent-integration` | 200 | 2026-08-17 | guides/agent-integration.mdx |  |
| `/docs/guides/agent-mcp` | 200 | 2026-07-29 | guides/agent-mcp.md |  |
| `/docs/guides/agent-messaging` | 200 | 2026-09-15 | guides/agent-messaging.md |  |
| `/docs/guides/agent-tool-policy` | 200 | 2026-09-23 | guides/agent-tool-policy.md |  |
| `/docs/guides/agent-workflows` | 200 | 2026-09-04 | guides/agent-workflows.mdx |  |
| `/docs/guides/ai-effect` | 200 | 2026-05-05 | guides/ai-effect.mdx |  |
| `/docs/guides/ai-prompt-guide` | 200 | 2025-12-17 | guides/ai-prompt-guide.mdx |  |
| `/docs/guides/ai-routing` | 200 | 2026-06-05 | guides/ai-routing.md |  |
| `/docs/guides/ai-stdlib-discovery` | 200 | 2026-07-14 | guides/ai-stdlib-discovery.md |  |
| `/docs/guides/ailang-vs-agents` | 200 | 2026-08-17 | guides/ailang-vs-agents.mdx |  |
| `/docs/guides/autonomous-package-updates` | 200 | 2026-04-30 | guides/autonomous-package-updates.md |  |
| `/docs/guides/benchmarking` | 200 | 2026-08-27 | guides/benchmarking.md |  |
| `/docs/guides/brain-cache` | 200 | 2026-07-31 | guides/brain-cache.md |  |
| `/docs/guides/build-a-motoko-extension` | 200 | 2026-05-09 | guides/build-a-motoko-extension.md |  |
| `/docs/guides/claude-code-integration` | 200 | 2026-09-04 | guides/claude-code-integration.mdx |  |
| `/docs/guides/cloud-messaging-integration` | 200 | 2026-09-15 | guides/cloud-messaging-integration.md |  |
| `/docs/guides/collaboration-hub` | 200 | 2026-09-15 | guides/collaboration-hub.md |  |
| `/docs/guides/contracts` | 200 | 2026-04-30 | guides/contracts.mdx |  |
| `/docs/guides/coordinator` | 200 | 2026-09-17 | guides/coordinator.md |  |
| `/docs/guides/coordinator-setup` | 200 | 2026-06-23 | guides/coordinator-setup.md |  |
| `/docs/guides/coordinator-workers` | 200 | 2026-09-15 | guides/coordinator-workers.md |  |
| `/docs/guides/custom-ai-providers` | 200 | 2026-05-05 | guides/custom-ai-providers.md |  |
| `/docs/guides/database-architecture` | 200 | 2026-07-21 | guides/database-architecture.md |  |
| `/docs/guides/debugging` | 200 | 2026-09-21 | guides/debugging.md |  |
| `/docs/guides/development-workflow` | 200 | 2026-08-21 | guides/development-workflow.md |  |
| `/docs/guides/editor-setup` | 200 | 2026-08-19 | guides/editor-setup.md |  |
| `/docs/guides/evaluation` | 200 | 2026-08-17 | guides/evaluation/README.mdx |  |
| `/docs/guides/evaluation/architecture` | 200 | 2026-06-23 | guides/evaluation/architecture.md |  |
| `/docs/guides/evaluation/browser-auth-profiles` | 200 | 2026-08-26 | guides/evaluation/browser-auth-profiles.md |  |
| `/docs/guides/evaluation/browser-sessions` | 200 | 2026-08-25 | guides/evaluation/browser-sessions.md |  |
| `/docs/guides/evaluation/cost-and-speed-budgets` | 200 | 2026-06-23 | guides/evaluation/cost-and-speed-budgets.md |  |
| `/docs/guides/evaluation/eval-loop` | 200 | 2026-08-27 | guides/evaluation/eval-loop.md |  |
| `/docs/guides/evaluation/harness-setup` | 200 | 2026-09-07 | guides/evaluation/harness-setup.md |  |
| `/docs/guides/evaluation/local-ollama` | 200 | 2026-09-11 | guides/evaluation/local-ollama.md |  |
| `/docs/guides/evaluation/measurement-contract` | 200 | 2026-07-29 | guides/evaluation/measurement-contract.md |  |
| `/docs/guides/evaluation/model-capability-threshold` | 200 | 2026-08-27 | guides/evaluation/model-capability-threshold.md |  |
| `/docs/guides/evaluation/model-configuration` | 200 | 2026-06-23 | guides/evaluation/model-configuration.md |  |
| `/docs/guides/examples-search` | 200 | 2026-01-02 | guides/examples-search.mdx |  |
| `/docs/guides/extension-packages` | 200 | 2026-05-09 | guides/extension-packages.md |  |
| `/docs/guides/getting-started` | 200 | 2026-09-04 | guides/getting-started.mdx |  |
| `/docs/guides/go-interop` | 200 | 2026-04-20 | guides/go-interop.md |  |
| `/docs/guides/hooks-setup` | 200 | 2026-09-04 | guides/hooks-setup.mdx |  |
| `/docs/guides/ifc-labels` | 200 | 2026-08-17 | guides/ifc-labels.mdx |  |
| `/docs/guides/lsp` | 200 | 2026-05-16 | guides/lsp.md |  |
| `/docs/guides/microrag` | 200 | 2026-06-23 | guides/microrag.md |  |
| `/docs/guides/mission-bootstrap` | 200 | 2026-09-05 | guides/mission-bootstrap.md |  |
| `/docs/guides/mission-iteration` | 200 | 2026-09-08 | guides/mission-iteration.md |  |
| `/docs/guides/mission-model-fleet` | 200 | 2026-08-26 | guides/mission-model-fleet.md |  |
| `/docs/guides/mission-role-dispatch` | 200 | 2026-09-18 | guides/mission-role-dispatch.md |  |
| `/docs/guides/module_execution` | 200 | 2026-07-10 | guides/module_execution.mdx |  |
| `/docs/guides/motoko-extension-development` | 200 | 2026-05-17 | guides/motoko-extension-development.md |  |
| `/docs/guides/notification-channels` | 200 | 2026-05-30 | guides/notification-channels.md |  |
| `/docs/guides/notify-daemon` | 200 | 2026-07-13 | guides/notify-daemon.md |  |
| `/docs/guides/package-publishing` | 200 | 2026-09-17 | guides/package-publishing.md |  |
| `/docs/guides/packages` | 200 | 2026-09-17 | guides/packages.md |  |
| `/docs/guides/parameterised-effects` | 200 | 2026-07-28 | guides/parameterised-effects.md |  |
| `/docs/guides/quick-start-examples` | 200 | 2026-06-23 | guides/quick-start-examples.mdx |  |
| `/docs/guides/secret-approvals` | 200 | 2026-06-23 | guides/secret-approvals.md |  |
| `/docs/guides/semantic-caching-how-to` | 200 | 2026-09-04 | guides/semantic-caching-how-to.mdx |  |
| `/docs/guides/semantic-caching-vs-vectordb` | 200 | 2026-08-17 | guides/semantic-caching-vs-vectordb.md |  |
| `/docs/guides/semantic-search` | 200 | 2026-04-20 | guides/semantic-search.md |  |
| `/docs/guides/serve-api` | 200 | 2026-09-11 | guides/serve-api.md |  |
| `/docs/guides/state-system-workflow` | 200 | 2026-08-17 | guides/state-system-workflow.mdx |  |
| `/docs/guides/streaming` | 200 | 2026-04-20 | guides/streaming.md |  |
| `/docs/guides/strict-fallbacks` | 200 | 2026-07-24 | guides/strict-fallbacks.md |  |
| `/docs/guides/telemetry` | 200 | 2026-09-08 | guides/telemetry.md |  |
| `/docs/guides/testing` | 200 | 2026-04-20 | guides/testing.md |  |
| `/docs/guides/three-camps-comparison` | 200 | 2026-08-17 | guides/three-camps-comparison.md |  |
| `/docs/guides/three-camps-self-audit` | 200 | 2026-05-21 | guides/three-camps-self-audit.md |  |
| `/docs/guides/traces` | 200 | 2026-04-10 | guides/traces.md |  |
| `/docs/guides/wasm-ai-step-byo-key` | 200 | 2026-05-13 | guides/wasm-ai-step-byo-key.md |  |
| `/docs/guides/wasm-integration` | 200 | 2026-09-14 | guides/wasm-integration.md |  |
| `/docs/guides/workspaces` | 200 | 2026-01-25 | guides/workspaces.md |  |
| `/docs/packages` | 200 | 2026-09-18 | packages/index.mdx |  |
| `/docs/packages/explorer` | 200 | 2026-03-24 | packages/explorer.mdx | JS-only ("Loading packages from registry...") |
| `/docs/packages/graph` | 200 | 2026-03-24 | packages/graph.mdx | JS-only graph |
| `/docs/packages/sunholo` | 200 | generated page | (generated) |  |
| `/docs/packages/sunholo/a2ui` | 200 | registry "Last Updated" 2026-04-24 | (generated) | pkg v0.2.0 |
| `/docs/packages/sunholo/agui` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.2.1 |
| `/docs/packages/sunholo/ail_diag` | 200 | registry "Last Updated" 2026-08-28 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/ailang_parse` | 200 | registry "Last Updated" 2026-09-23 | (generated) | pkg v0.43.1 |
| `/docs/packages/sunholo/auth` | 200 | registry "Last Updated" 2026-03-27 | (generated) | pkg v0.4.1 |
| `/docs/packages/sunholo/billing_entitlements` | 200 | registry "Last Updated" 2026-05-15 | (generated) | pkg v0.4.2 |
| `/docs/packages/sunholo/billing_proposals` | 200 | registry "Last Updated" 2026-05-15 | (generated) | pkg v0.3.2 |
| `/docs/packages/sunholo/billing_service_api` | 200 | registry "Last Updated" 2026-05-15 | (generated) | pkg v0.5.9 |
| `/docs/packages/sunholo/billing_store` | 200 | registry "Last Updated" 2026-05-15 | (generated) | pkg v0.9.3 |
| `/docs/packages/sunholo/billing_stripe` | 200 | registry "Last Updated" 2026-04-20 | (generated) | pkg v0.1.6 |
| `/docs/packages/sunholo/config` | 200 | registry "Last Updated" 2026-04-20 | (generated) | pkg v0.1.2 |
| `/docs/packages/sunholo/daneel_ext_abi` | 200 | registry "Last Updated" 2026-09-15 | (generated) | pkg v0.4.0 |
| `/docs/packages/sunholo/daneel_ext_activity` | 200 | registry "Last Updated" 2026-09-14 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/daneel_ext_calendar` | 200 | registry "Last Updated" 2026-09-15 | (generated) | pkg v0.2.4 |
| `/docs/packages/sunholo/daneel_ext_design` | 200 | registry "Last Updated" 2026-09-14 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/daneel_ext_help` | 200 | registry "Last Updated" 2026-09-14 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/daneel_ext_search` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/daneel_ext_writer` | 200 | registry "Last Updated" 2026-09-16 | (generated) | pkg v0.2.0 |
| `/docs/packages/sunholo/decisions` | 200 | registry "Last Updated" 2026-09-19 | (generated) | pkg v0.4.0 |
| `/docs/packages/sunholo/deontic` | 200 | registry "Last Updated" 2026-09-16 | (generated) | pkg v0.3.0 |
| `/docs/packages/sunholo/discord` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.5.0 |
| `/docs/packages/sunholo/duckdb` | 200 | registry "Last Updated" 2026-08-25 | (generated) | pkg v0.1.3 |
| `/docs/packages/sunholo/email` | 200 | registry "Last Updated" 2026-09-18 | (generated) | pkg v0.3.4 |
| `/docs/packages/sunholo/eparse` | 200 | registry "Last Updated" 2026-09-18 | (generated) | pkg v1.1.0 |
| `/docs/packages/sunholo/external_backend` | 200 | registry "Last Updated" 2026-08-31 | (generated) | pkg v0.2.0 |
| `/docs/packages/sunholo/firebase_auth` | 200 | registry "Last Updated" 2026-04-20 | (generated) | pkg v0.1.2 |
| `/docs/packages/sunholo/firestore` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.7.3 |
| `/docs/packages/sunholo/gcp_auth` | 200 | registry "Last Updated" 2026-04-20 | (generated) | pkg v0.8.1 |
| `/docs/packages/sunholo/gcs_storage` | 200 | registry "Last Updated" 2026-08-07 | (generated) | pkg v0.1.3 |
| `/docs/packages/sunholo/gemini_agents` | 200 | registry "Last Updated" 2026-09-21 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/gemini_files` | 200 | registry "Last Updated" 2026-08-06 | (generated) | pkg v0.2.1 |
| `/docs/packages/sunholo/gemini_live` | 200 | registry "Last Updated" 2026-05-12 | (generated) | pkg v0.4.1 |
| `/docs/packages/sunholo/gmail` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.4.1 |
| `/docs/packages/sunholo/http_helpers` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.1.5 |
| `/docs/packages/sunholo/linkedin` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.5.1 |
| `/docs/packages/sunholo/logging` | 200 | registry "Last Updated" 2026-03-25 | (generated) | pkg v0.4.0 |
| `/docs/packages/sunholo/motoko_ext_a2a` | 200 | registry "Last Updated" 2026-05-17 | (generated) | pkg v0.2.2 |
| `/docs/packages/sunholo/motoko_ext_abi` | 200 | registry "Last Updated" 2026-05-17 | (generated) | pkg v2.2.0 |
| `/docs/packages/sunholo/motoko_ext_ai_compat` | 200 | registry "Last Updated" 2026-07-20 | (generated) | pkg v0.2.2 |
| `/docs/packages/sunholo/motoko_ext_ailang_docs` | 200 | registry "Last Updated" 2026-07-28 | (generated) | pkg v0.1.5 |
| `/docs/packages/sunholo/motoko_ext_compaction_ai` | 200 | registry "Last Updated" 2026-07-28 | (generated) | pkg v0.3.2 |
| `/docs/packages/sunholo/motoko_ext_compose` | 200 | registry "Last Updated" 2026-07-28 | (generated) | pkg v0.2.6 |
| `/docs/packages/sunholo/motoko_ext_context_mode` | 200 | registry "Last Updated" 2026-07-28 | (generated) | pkg v0.2.4 |
| `/docs/packages/sunholo/motoko_ext_decision_framework` | 200 | registry "Last Updated" 2026-05-17 | (generated) | pkg v0.2.2 |
| `/docs/packages/sunholo/motoko_ext_exa_search` | 200 | registry "Last Updated" 2026-07-28 | (generated) | pkg v0.2.8 |
| `/docs/packages/sunholo/motoko_ext_fmt` | 200 | registry "Last Updated" 2026-07-30 | (generated) | pkg v0.4.2 |
| `/docs/packages/sunholo/motoko_ext_mcp` | 200 | registry "Last Updated" 2026-05-17 | (generated) | pkg v0.2.7 |
| `/docs/packages/sunholo/motoko_ext_microrag` | 200 | registry "Last Updated" 2026-05-17 | (generated) | pkg v0.4.2 |
| `/docs/packages/sunholo/motoko_ext_omnigraph` | 200 | registry "Last Updated" 2026-07-28 | (generated) | pkg v0.2.4 |
| `/docs/packages/sunholo/motoko_ext_test_dummy` | 200 | registry "Last Updated" 2026-05-17 | (generated) | pkg v0.2.2 |
| `/docs/packages/sunholo/oauth` | 200 | registry "Last Updated" 2026-09-08 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/ollama_stream` | 200 | registry "Last Updated" 2026-07-23 | (generated) | pkg v0.1.0 |
| `/docs/packages/sunholo/registry_validator` | 200 | registry "Last Updated" 2026-09-17 | (generated) | pkg v0.1.2 |
| `/docs/packages/sunholo/test_pkg` | 200 | registry "Last Updated" 2026-05-02 | (generated) | pkg v0.1.3 |
| `/docs/packages/sunholo/test_pkg_consumer` | 200 | registry "Last Updated" 2026-05-02 | (generated) | pkg v0.0.2 |
| `/docs/packages/sunholo/testing_utils` | 200 | registry "Last Updated" 2026-03-24 | (generated) | pkg v0.1.1 |
| `/docs/packages/world` | 200 | generated page | (generated) |  |
| `/docs/packages/world/core` | 200 | registry "Last Updated" 2026-09-21 | (generated) | pkg v0.1.0 |
| `/docs/playground` | 200 | 2025-12-05 | playground.mdx | interactive REPL is JS/WASM; static text only |
| `/docs/prompts` | 200 | 2025-12-17 | prompts/index.md |  |
| `/docs/prompts/current` | 200 | 2026-07-28 | prompts/current.md |  |
| `/docs/prompts/python` | 200 | 2026-05-19 | prompts/python.md |  |
| `/docs/prompts/v0.11.4` | 200 | 2026-05-19 | prompts/v0.11.4.md |  |
| `/docs/prompts/v0.12.1` | 200 | 2026-05-19 | prompts/v0.12.1.md |  |
| `/docs/prompts/v0.16.0` | 200 | 2026-05-19 | prompts/v0.16.0.md |  |
| `/docs/prompts/v0.16.1` | 200 | 2026-08-13 | prompts/v0.16.1.md |  |
| `/docs/prompts/v0.16.2` | 200 | 2026-08-13 | prompts/v0.16.2.md |  |
| `/docs/prompts/v0.16.3` | 200 | 2026-08-13 | prompts/v0.16.3.md |  |
| `/docs/prompts/v0.16.4` | 200 | 2026-08-13 | prompts/v0.16.4.md |  |
| `/docs/prompts/v0.16.5` | 200 | 2026-08-13 | prompts/v0.16.5.md |  |
| `/docs/prompts/v0.16.6` | 200 | (generated from prompts/v0.16.6.md; no docs md) | (generated) |  |
| `/docs/prompts/v0.8.2` | 200 | 2026-05-19 | prompts/v0.8.2.md |  |
| `/docs/prompts/v0.9.0` | 200 | 2026-05-19 | prompts/v0.9.0.md |  |
| `/docs/recipes/ai-token-streaming` | 200 | 2026-05-05 | recipes/ai-token-streaming.md |  |
| `/docs/recipes/ai-tool-loop` | 200 | 2026-05-05 | recipes/ai-tool-loop.md |  |
| `/docs/reference/arrays` | 200 | 2025-12-17 | reference/arrays.md |  |
| `/docs/reference/capability-budgets` | 200 | 2026-07-24 | reference/capability-budgets.mdx |  |
| `/docs/reference/cli` | 200 | 2026-09-21 | reference/cli.md |  |
| `/docs/reference/effects` | 200 | 2026-09-11 | reference/effects.md |  |
| `/docs/reference/env-vars` | 200 | 2026-09-19 | reference/env-vars.md |  |
| `/docs/reference/errors` | 200 | 2026-07-13 | reference/errors/index.md |  |
| `/docs/reference/errors/mod007` | 200 | 2026-07-13 | reference/errors/mod007.md |  |
| `/docs/reference/errors/mod013` | 200 | 2026-05-06 | reference/errors/mod013.md |  |
| `/docs/reference/errors/typ_effect_row_mismatch` | 200 | 2026-05-06 | reference/errors/typ_effect_row_mismatch.md |  |
| `/docs/reference/formatter` | 200 | 2026-07-19 | reference/formatter.md |  |
| `/docs/reference/implementation-status` | 200 | 2026-08-17 | reference/implementation-status.md |  |
| `/docs/reference/language-syntax` | 200 | 2026-07-01 | reference/language-syntax.md |  |
| `/docs/reference/limitations` | 200 | 2026-08-21 | reference/limitations.md |  |
| `/docs/reference/modules` | 200 | 2026-05-13 | reference/modules.md |  |
| `/docs/reference/no-loops` | 200 | 2025-12-24 | reference/no-loops.md |  |
| `/docs/reference/option-vs-result` | 200 | 2026-05-11 | reference/option-vs-result.md |  |
| `/docs/reference/repl-commands` | 200 | 2026-04-20 | reference/repl-commands.md |  |
| `/docs/reference/stability` | 200 | 2026-07-12 | reference/stability.md |  |
| `/docs/reference/std-extension` | 200 | 2026-08-25 | reference/std-extension.md |  |
| `/docs/reference/std-package` | 200 | 2026-08-25 | reference/std-package.md |  |
| `/docs/reference/std-xml` | 200 | 2026-05-14 | reference/std-xml.md |  |
| `/docs/reference/std-yaml` | 200 | 2026-07-14 | reference/std-yaml.md |  |
| `/docs/reference/stdlib` | 200 | 2026-07-14 | reference/stdlib.md |  |
| `/docs/references` | 200 | 2026-08-17 | references/index.md |  |
| `/docs/references/axioms` | 200 | 2025-12-19 | references/axioms.mdx |  |
| `/docs/references/design-lineage` | 200 | 2025-12-19 | references/design-lineage.mdx |  |
| `/docs/references/philosophical-foundations` | 200 | 2025-12-19 | references/philosophical-foundations.mdx |  |
| `/docs/roadmap` | 200 | 2026-09-09 | roadmap/index.md |  |
| `/docs/start-here/evaluating` | 200 | 2026-05-01 | start-here/evaluating.mdx |  |
| `/docs/start-here/for-ai-agents` | 200 | 2026-05-01 | start-here/for-ai-agents.mdx |  |
| `/docs/start-here/quick-start` | 200 | 2026-05-01 | start-here/quick-start.mdx |  |
| `/docs/vision` | 200 | 2026-02-12 | vision.mdx |  |
| `/docs/why-ailang` | 200 | 2026-07-10 | why-ailang.mdx |  |
| `/` | 200 | landing (src/pages); shows v0.42.0 | (generated) | benchmarks strip loads client-side ("Loading benchmarks...") |

---

## 11. Appendix: package catalogue (57 package pages, rendered text, read 2026-09-25)
From https://ailang.sunholo.com/docs/packages/sunholo ("56 packages published by sunholo") plus /docs/packages/world/core. The "updated" column is the page's registry "Last Updated" date. "(blank)" means the package page leaves Stability empty.

| package | latest | stability | effects | updated | description (verbatim fragment) |
|---|---|---|---|---|---|
| a2ui | 0.2.0 | experimental | Pure | 2026-04-24 | "Build A2UI component trees and serialize to flat adjacency-list JSON." |
| agui | 0.2.1 | (blank) | IO | 2026-09-17 | "Typed AG-UI core subset … No network transport." |
| ail_diag | 0.1.0 | experimental | Pure | 2026-08-28 | "Parse AILANG toolchain output (check/doctor) into structured, code-tagged diagnostics" |
| ailang_parse | 0.43.1 | experimental | IO, FS, AI, Env, Net, Clock, Process | 2026-09-23 | "Universal document parsing for Office, PDF, and image formats" (57 modules) |
| auth | 0.4.1 | experimental | Pure | 2026-03-27 | "Pure API key validation (SHA-256 hash comparison, constant-time) and bearer token extraction" |
| billing_entitlements | 0.4.2 | experimental | Pure | 2026-05-15 | "Pure billing policy: plan catalog lookup, entitlement resolution…" |
| billing_proposals | 0.3.2 | experimental | Pure | 2026-05-15 | "AI agents propose plan changes, humans approve." |
| billing_service_api | 0.5.9 | experimental | Net, FS, Env, IO | 2026-05-15 | "HTTP handlers for billing Cloud Run service." |
| billing_store | 0.9.3 | experimental | IO, Net, FS, Env | 2026-05-15 | "Firestore CRUD for billing records…" |
| billing_stripe | 0.1.6 | experimental | Net, Env | 2026-04-20 | "Stripe API adapter…" |
| config | 0.1.2 | experimental | Env | 2026-04-20 | "Load and validate config from environment variables…" |
| daneel_ext_abi | 0.4.0 | (blank) | IO, FS, Process, Clock, Net, Env, AI | 2026-09-15 | no description |
| daneel_ext_activity | 0.1.0 | (blank) | same 7 effects | 2026-09-14 | no description |
| daneel_ext_calendar | 0.2.4 | (blank) | same 7 effects | 2026-09-15 | no description |
| daneel_ext_design | 0.1.0 | (blank) | same 7 effects | 2026-09-14 | no description |
| daneel_ext_help | 0.1.0 | (blank) | same 7 effects | 2026-09-14 | no description |
| daneel_ext_search | 0.1.0 | (blank) | same 7 effects | 2026-09-17 | no description |
| daneel_ext_writer | 0.2.0 | (blank) | same 7 effects | 2026-09-16 | no description |
| decisions | 0.4.0 | experimental | Net, Env, IO | 2026-09-19 | "Ask a System One decision model … typed questions about a JSON state" |
| deontic | 0.3.0 | experimental | IO | 2026-09-16 | "Pure obligation-reasoning engine" … "with Z3-provable settlement math including per-diem statutory interest" |
| discord | 0.5.0 | (blank) | Net, IO | 2026-09-17 | "Bot REST client…" |
| duckdb | 0.1.3 | experimental | IO, Process, FS | 2026-08-25 | "Pure AILANG DuckDB client using std/process." |
| email | 0.3.4 | experimental | IO, Process, Env, Declassify | 2026-09-18 | "seven ready-made MCP tools" … "Offline, no AI effect." |
| eparse | 1.1.0 | experimental | IO, Process, Env, FS, Clock, AI, Declassify | 2026-09-18 | no description; "No exports listed." |
| external_backend | 0.2.0 | experimental | Process, IO | 2026-08-31 | "Confines the Process effect so callers stay effect-thin." |
| firebase_auth | 0.1.2 | experimental | Net, Env | 2026-04-20 | "Firebase ID token verification via REST API or local JWT/RSA signature validation" |
| firestore | 0.7.3 | experimental | Net, FS, Env | 2026-09-17 | "Firestore REST API client for AILANG." |
| gcp_auth | 0.8.1 | experimental | FS, Net, Env | 2026-04-20 | "Exchange GCP ADC refresh tokens for access tokens…" |
| gcs_storage | 0.1.3 | experimental | Net, FS, Env, Clock | 2026-08-07 | "Generic GCS operations for AILANG services." |
| gemini_agents | 0.1.0 | experimental | Net, FS, Env, IO | 2026-09-21 | "The agent ids are a proven closed set." |
| gemini_files | 0.2.1 | experimental | Net, FS, Env, Clock | 2026-08-06 | "Upload large files (PDF, images) for Gemini AI calls." |
| gemini_live | 0.4.1 | experimental | Pure | 2026-05-12 | "WebSocket protocol helpers for Gemini Live API…" |
| gmail | 0.4.1 | experimental | Net, IO | 2026-09-17 | "Pure composition separated from the effectful call so the security-critical half is testable without a network or a credential." |
| http_helpers | 0.1.5 | experimental | Net | 2026-09-17 | "Build HTTP requests with auth headers, parse JSON responses, standard error handling" |
| linkedin | 0.5.1 | experimental | Net, FS, Env, Declassify, IO | 2026-09-17 | "(Net @limit=1, requires text length 1..3000)"; "IFC-Declassify-typed so the raw URN cannot leak." |
| logging | 0.4.0 | experimental | Pure | 2026-03-25 | "via Debug ghost effect. No IO cascade, no effect declarations needed. Zero-cost in release mode." |
| motoko_ext_a2a | 0.2.2 | (blank) | Net, FS, Env, Rand, IO | 2026-05-17 | no description |
| motoko_ext_abi | 2.2.0 | **stable** | Pure | 2026-05-17 | "Bumping ExtensionHooks is a major version bump." |
| motoko_ext_ai_compat | 0.2.2 | (blank) | AI, IO, Process, FS, Env, Net, SharedMem, Clock, Stream | 2026-07-20 | no description |
| motoko_ext_ailang_docs | 0.1.5 | experimental | Process, FS, Env | 2026-07-28 | "Wraps the public AILANG docs MCP server (mcp.ailang.sunholo.com/mcp/) as 23 motoko tools" |
| motoko_ext_compaction_ai | 0.3.2 | (blank) | AI, IO, Process, FS, Env, Net, SharedMem, Clock, Stream | 2026-07-28 | "AI-powered conversation compaction extension." |
| motoko_ext_compose | 0.2.6 | (blank) | IO, AI, Net, Stream, Process, FS, Env, Clock, SharedMem | 2026-07-28 | no description (18 modules) |
| motoko_ext_context_mode | 0.2.4 | (blank) | IO, Process, FS, Env, SharedMem, Clock, SharedIndex | 2026-07-28 | no description |
| motoko_ext_decision_framework | 0.2.2 | experimental | Pure | 2026-05-17 | "Prompt-patch extension that injects the four-decision ladder…" |
| motoko_ext_exa_search | 0.2.8 | (blank) | Process, FS, Env | 2026-07-28 | no description |
| motoko_ext_fmt | 0.4.2 | experimental | IO, Process, FS, AI, Env, Net, SharedMem, Clock, Stream | 2026-07-30 | "Intercepts WriteFile on .ail files via on_tool_handle…" |
| motoko_ext_mcp | 0.2.7 | (blank) | Process, FS, Env, IO | 2026-05-17 | no description |
| motoko_ext_microrag | 0.4.2 | experimental | IO, Process, FS, AI, Env, Net, SharedMem, Clock, Stream | 2026-05-17 | "Auto-injects AILANG knowledge retrieval into WriteFile tool results…" |
| motoko_ext_omnigraph | 0.2.4 | (blank) | Process, FS, Env, SharedMem, IO | 2026-07-28 | no description |
| motoko_ext_test_dummy | 0.2.2 | experimental | Env | 2026-05-17 | "Minimal echo extension for motoko_agent." |
| oauth | 0.1.0 | experimental | FS, Net, IO | 2026-09-08 | "Run the OAuth2 installed-app flow end to end from AILANG…" |
| ollama_stream | 0.1.0 | experimental | Stream | 2026-07-23 | "Stream tokens from a local Ollama server line-by-line…" |
| registry_validator | 0.1.2 | experimental | IO, FS | 2026-09-17 | "Validate AILANG packages … Written in AILANG." |
| test_pkg | 0.1.3 | experimental | Pure | 2026-05-02 | "Minimal test package…" |
| test_pkg_consumer | 0.0.2 | (blank) | Pure | 2026-05-02 | "Smoke-test dependent of sunholo/test_pkg…" |
| testing_utils | 0.1.1 | experimental | Pure | 2026-03-24 | "Pure assertion helpers for testing…" |
| world/core | 0.1.0 | (blank) | Pure | 2026-09-21 | "the Z3-proven validity contracts" |

**Totals:**
- 1 of 57 packages is stable; 19 package pages leave stability blank.
- 13 packages are Pure.
- Declassify appears as an effect on 3 packages (email, eparse, linkedin).
- SharedIndex appears on 1 package, Rand on 1.
- The decisions package states: "Calls are ! {Net, Env}, non-deterministic (bank the distribution, never argmax alone), and outside the AI effect's budget/trace-cost accounting."

