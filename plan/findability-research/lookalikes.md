# Projects that sound like Sabline, checked against their own docs

Read on 2026-09-25. Every URL below was fetched on that date. Quotes come from the project's own site, README, package registry entry or IETF datatracker page. Where a page could not be read, the entry says so.

**How the pages were read:** the fetch tool passes page text through a small summarising model. The quotes below are what it returned as verbatim. They are short and consistent across repeated fetches, but check any quote against the live page before you print it.

**Sabline, for comparison:** a language whose function signatures declare effects (io, env, fs, net, clock, rand, ffi). The operator runs a program under a budget (`--allow net:api.example.com`), and the runtime refuses anything outside it. It also emits an audit record, in-toto attestations and run receipts, and has an MCP server.

---

## Part 1: the six names on the owner's list

### 1. AgentBudget

One project uses this name for AI agents. `sahiljagtap08/agentbudget` is the author's copy of the same repo, not a separate project. The other "budget agent" results are unrelated marketing templates (Jotform, Domo, beam.ai).

- **URLs read:** https://github.com/AgentBudget/agentbudget , https://agentbudget.dev/ , https://pypi.org/pypi/agentbudget/json , https://registry.npmjs.org/@agentbudget/agentbudget
- **What it does:** it is an in-process SDK. It wraps your LLM, tool and API calls, keeps a running dollar cost for one agent session, and raises an exception once a set dollar limit is reached.
- **Quote (PyPI):** "AgentBudget is an open-source Python SDK that puts a hard dollar limit on any AI agent session."
- **Quote (README):** "Raises `BudgetExhausted`. No more calls allowed." / "Not an LLM proxy. Wraps your existing client calls in-process."
- **Language:** Python (PyPI `agentbudget` 0.4.0, uploaded 2026-05-30). The site also lists Go and TypeScript SDKs. The npm package is `@agentbudget/agentbudget` 0.3.1. The registry has no plain `agentbudget` package (404), although the README says `npm install agentbudget`.
- **Licence:** Apache-2.0
- **Kind:** library/SDK
- **Enforces at run time?** Yes, for money only. It stops further calls once the dollar limit is hit.
- **Versus Sabline:** it limits how many dollars an agent session spends on LLM and API calls, not which files, hosts or environment variables code may touch.

### 2. PolicyLayer

One company runs policylayer.com. Its own pages describe three different products, which looks like two pivots over the past year. Pages that disagree with each other are still live.

**2a. Current homepage (what the site leads with today)**
- **URL read:** https://policylayer.com/
- **What it does:** a hosted service with an MCP interface. It stores a team's rules for coding agents as a signed, versioned "playbook" and sends questions the playbook does not cover to the person who owns that decision.
- **Quote:** "The system of record for AI agent authority" / "Your team's decisions, in one playbook every agent works from. When something is not covered, the agent asks the right person."
- **Kind:** hosted service. Setup is `npx @policylayer/setup`, and agents use it through the MCP tools `get_playbook`, `ask_policy`, `get_answers` and `record_decision`.
- **Licence / language:** not stated.
- **Enforces?** It advises. The agent loads the playbook and asks questions, and the page says an unanswered question "pauses only that task". The homepage does not describe blocking calls.
- **The Glama MCP connector listing** (https://glama.ai/mcp/connectors/com.policylayer/policylayer, last tested 2026-09-24) uses the same description and shows its health check as "Unhealthy".

**2b. MCP gateway/proxy ("Intercept"), still on the same site**
- **URLs read:** https://policylayer.com/solutions , https://policylayer.com/blog/bain-three-layers-agentic-ai-policy-enforcement (dated 10 April 2026) , https://registry.npmjs.org/@policylayer/intercept
- **What it does:** a proxy between agents and MCP servers. It checks every tool call against YAML policy before the call runs, then allows it, denies it, rate-limits it or holds it for approval.
- **Quote (/solutions):** "Every tool call is checked against your policy before it runs and gets one of four outcomes."
- **Quote (blog):** "PolicyLayer is a proxy that sits between AI agents and MCP servers."
- **Package:** npm `@policylayer/intercept` 1.4.0, "Policy-as-code enforcement for MCP tool calls", Apache-2.0, created 2026-03-02, last modified 2026-04-09. **The repo it points to (github.com/policylayer/intercept) returned 404 on 2026-09-25.**
- **Enforces?** Yes, at the MCP transport layer.

**2c. Crypto wallet spending controls (the earliest product)**
- **URLs read:** https://registry.npmjs.org/@policylayer/sdk , https://dev.to/policylayer/how-to-add-spending-controls-to-any-mcp-agent-k09 (the company's own dev.to account)
- **What it does:** an SDK that approves or refuses each transaction an agent's crypto wallet tries to make, using per-transaction and daily limits, without holding the private keys.
- **Quote (npm):** "Non-custodial spending controls for AI agent wallets. Enforce limits without holding keys."
- **Package:** npm `@policylayer/sdk` 1.4.0, MIT, created 2025-12-08, last modified 2026-03-02. **Its repo (github.com/PolicyLayer/PolicyLayer) returned 404 on 2026-09-25.**
- The public GitHub org (https://github.com/PolicyLayer) now mainly holds an MCP-server "registry" checker (`mcp`, `mcp-precheck`, `scan-action`) and forks of MCP servers.

- **Versus Sabline (all three):** PolicyLayer governs an agent's tool calls, or wallet payments, from outside the code. It does not constrain what a program's own code can do, and the current product only advises.

### 3. AIIR

AIIR here means **AI Integrity Receipts from Invariant Systems, Inc.** Two unrelated GitHub accounts also use the name: "Aiir" (https://github.com/aiir, verified domain aiir.com, radio software, "Create Radio") and "AIIR Group" (https://github.com/aiir-team, "Artificial Intelligence Independent Research Group", ML papers). Neither overlaps Sabline.

- **URLs read:** https://pypi.org/pypi/aiir/json (PyPI JSON API), https://github.com/chainguard-actions/invariant-systems-ai-aiir , https://github.com/invariant-systems-ai , https://invariantsystems.io
- **Fetch problems:** **https://github.com/invariant-systems-ai/aiir returned 404 on 2026-09-25**, even though PyPI still links to it. The org page lists only 3 public repos, and `aiir` is not one of them. The pypi.org HTML page would not render ("A required part of this site couldn't load"), so I used the JSON API. invariantsystems.io does not mention AIIR.
- **What it does:** a CLI/library that writes a tamper-evident, content-addressed JSON receipt for each git commit. The receipt records whatever AI involvement the commit metadata declares (trailers, bot authors), and receipts can be verified offline, optionally signed with Sigstore or wrapped as in-toto statements.
- **Quote (PyPI):** "AIIR records declared AI involvement and verifies receipt integrity; it does not detect hidden or undeclared AI use."
- **Language:** Python ≥3.9, zero dependencies. PyPI `aiir` 1.7.0, uploaded 2026-06-13. Chainguard publishes a "hardened" mirror of its GitHub Action.
- **Licence:** Apache-2.0
- **Kind:** library + CLI + GitHub Action
- **Enforces?** No. It records and verifies after the fact.
- **Versus Sabline:** it records who (or what) wrote a commit, not what a program is allowed to do when it runs. Both use in-toto, but AIIR's attestations are about authorship.

### 4. workproof

Several unrelated projects use this name. The npm package `workproof` is (a).

**4a. workproof, the git engineering report (npm `workproof`)**
- **URLs read:** https://github.com/Bubblegunn/workproof , https://registry.npmjs.org/workproof , https://github.com/shivam-070208/workproof (a fork of Bubblegunn's)
- **What it does:** a CLI you run inside a private git repo. It produces a report of thirteen git-derived figures about one author, such as commit share, surviving lines and declared AI-assisted commits, without showing any code, plus a hash anyone can recompute.
- **Quote:** "workproof turns a git repository into a verifiable engineering report for one author, without showing any code."
- **Language:** TypeScript/Node. npm `workproof` 0.5.0, created 2026-09-05, last modified 2026-09-21, maintainer Efe Genc.
- **Licence:** MIT
- **Kind:** CLI + GitHub Action. It writes `report.intoto.json` (an in-toto v1 Statement) and can be signed with Sigstore.
- **Enforces?** No. It measures and reports only. Its README says "It is not a legal document."
- **Versus Sabline:** it summarises a developer's past git history for a reader, and does not run or constrain any code.

**4b. WorkProof Runtime (ahmedsaturki). This one's vocabulary overlaps most.**
- **URL read:** https://github.com/ahmedsaturki/workproof-runtime
- **What it does:** a Node/TypeScript runtime that executes "digital work" jobs. It reconciles their external effects, verifies outcomes, keeps proof records and recovers work after a worker fails, behind an authenticated control plane.
- **Quote:** "Outcome-first digital work runtime: execute real work, reconcile external effects, verify outcomes, preserve proof, manage proof lifecycle, recover execution after worker loss"
- **Language:** TypeScript, Node ≥24.15. Not published to npm. Stable release v3.8.14.
- **Licence:** Apache-2.0
- **Enforces?** It applies its own risk and mutation policies to the jobs it runs, per the README ("The runtime remains the authority for execution, risk policy, effects…").
- **Versus Sabline:** it is a job runner and proof store for work items, not a language that limits what a given program may touch.

**4c. WorkProof schema (TalentProof)**
- **URL read:** https://github.com/TalentProof/workproof-schema
- **What it does:** an open JSON-Schema specification for describing a professional's skills from verifiable work evidence rather than self-reported claims.
- **Quote:** "An open specification for verified professional knowledge graphs."
- **Licence:** MIT. **Kind:** spec. **Enforces?** No.
- **Versus Sabline:** a data format for CVs and credentials, unrelated to running code.

**4d. Other unrelated "WorkProof"s** (one line each, all read 2026-09-25):
- https://github.com/gavalidivya0-arch/WorkProof : "WorkProof is a modern, verified portfolio and Trust Score platform designed specifically for freelancers." (TypeScript/Next.js; no licence shown)
- https://github.com/rusil3473/workproof-ai : a mobile app that turns contractor phones into photo "field proof" tools, with signed milestone sign-offs and payment payouts (TypeScript, MIT).
- https://workproof.me/ : a hosted app for timestamped, tamper-evident workplace incident records ("Write down what happened. We lock the date so no one can say you made it up later.").
- https://workproof.solutions/ : **the fetch returned only the page title "Workflow AS Demo Lab" (likely a JS-only page)**. The search-result title (a snippet, not read on the page) was "WorkProof - AI-Powered Employment Verification".

**Near-namesake: OpenWorkProof (dengyier). Different name, but a searcher could mix it up with workproof.**
- **URL read:** https://github.com/dengyier/OpenWorkProof
- **What it does:** a protocol plus Python reference implementation in which each agent tool call needs a signed "PolicyDecision" before it runs and produces a signed receipt afterwards (WorkOrder → CapabilityGrant → PolicyDecision → ActionReceipt → …).
- **Quote:** "Open protocol for AI agent work contracts and verifiable execution — authorization, evidence, and acceptance for multi-agent systems"
- **Language:** Python (PyPI `openworkproof` 1.4.0), with MCP and GitHub Action adapters. **Licence:** Apache-2.0.
- **Enforces?** Yes, pre-execution authorisation of tool calls.
- **Versus Sabline:** it authorises an agent's tool calls with signed decisions. It does not constrain the effects inside a program.

### 5. Bunbox

Several unrelated things use this name. Only (5a) overlaps Sabline. The owner's list may have meant it, or may have meant the better-known framework (5b); I cannot tell which.

**5a. Bunbox (`@bunboxnode/bunbx`), a package manager for AI agents. This is the Sabline-like one.**
- **URLs read:** https://github.com/gmh5225/Bunbox , https://registry.npmjs.org/@bunboxnode/bunbx
- **What it does:** a package manager and MCP server for coding agents. Packages declare what they may access (network, filesystem, eval, subprocesses), and at install time Bunbox scans their source with regex patterns. It refuses to install packages whose code uses undeclared access or contains secrets, and it also checks publishers' DID signatures and keeps an append-only witness log.
- **Quote (README/npm):** "Static auditing that blocks undeclared network, filesystem, eval, and command execution."
- **Language:** JavaScript/TypeScript, installed with Bun (`bun install -g @bunboxnode/bunbx`). npm 1.0.10, created 2026-05-20, last modified 2026-05-21. The repo has 0 stars and 24 commits, and npm lists no repository or homepage.
- **Licence:** MIT (npm metadata). No licence is shown on the GitHub page.
- **Enforces?** Only at install time, by static pattern scanning. The README I read describes no run-time sandbox or permission check while package code runs.
- **Versus Sabline:** it checks packages when they are installed by searching their source for patterns. Sabline's runtime refuses each operation outside the operator's budget while the program runs.

**5b. Bunbox, the full-stack web framework (bunbox.org)**
- **URLs read:** https://bunbox.org/ , https://github.com/demattosanthony/bunbox , https://registry.npmjs.org/@ademattos/bunbox
- **What it does:** a React/TypeScript web framework on the Bun runtime with file-based routing, SSR, typed APIs and WebSockets.
- **Quote:** "A simple full-stack framework built on Bun - 100x simpler than Next.js"
- **Licence:** MIT. npm `@ademattos/bunbox` 0.3.11 (last modified 2025-12-22). **Kind:** library/framework. **Enforces?** No. It has no sandboxing or permission features.
- **Versus Sabline:** a web-app framework with no security model. The only thing it shares is the word "box".

**5c. Other unrelated "bunbox"s**
- npm `bunbox` (https://registry.npmjs.org/bunbox): "A framework to build APIs with bun", v0.0.1, 2024-01-23, by Vidur Murali (github.com/vyder/bunbox). Abandoned.
- GitHub `HealthSamurai/bunbox`: "FHIR R4 Server using Bun" (seen in GitHub search results only).
- **bunbox.ai: fetch returned 404 (both www and bare domain).** A search snippet (not read on the page) described it as an AI email-thread summariser.

### 6. IETF "Permit Receipts" Internet-Draft

- **Exact name:** `draft-lee-orprg-permit-receipts-00`
- **Title:** "Permit Receipts for Permit-Before-Commit Authorization of AI-Agent and Workload External Effects"
- **Revision:** -00, the only revision
- **Author:** Yong Bok Lee (Y. B. Lee), Meridian Verity Group, Sheridan, WY, USA
- **Date of revision:** 4 June 2026. Expires 6 December 2026. Datatracker shows "Last updated 2026-07-18 (Latest revision 2026-06-04)".
- **Status:** Active individual Internet-Draft, no stream. The draft header says "Intended status: Standards Track", and the datatracker lists the intended RFC status as "(None)". The draft does not expand "ORPRG" and names no IETF or IRTF group.
- **URLs read:** https://datatracker.ietf.org/doc/draft-lee-orprg-permit-receipts/ , https://datatracker.ietf.org/doc/html/draft-lee-orprg-permit-receipts-00 , datatracker search for "permit"
- **What it does:** it proposes a data model and verifier rules for a signed "PermitReceipt". The receipt authorises one specific external action by an agent or workload (tool call, data egress, transaction and so on), and a verifier must check it before the action is committed.
- **Quote (abstract):** "This document defines requirements and an abstract data model for PermitReceipts used in permit-before-commit authorization of AI-agent and workload external effects."
- **Kind:** spec (draft), with no implementation. **Enforces?** No; it only describes what a verifier should enforce. Its model has an optional `"budget"` field ("optional structured limit").
- **Versus Sabline:** it defines a wire-level permission slip for one external action, checked at an effect boundary outside the program. It is not a language or runtime.

**Nearby drafts a searcher may confuse with it** (titles from the datatracker search, 2026-09-25):
- `draft-munoz-scitt-permit-profile-01`, "A SCITT Profile for Pre-Execution AI Action Authorization Records", Christian Munoz (Keel API, Inc.), 18 July 2026, Informational, individual. It calls its record a "Permit".
- `draft-xkumakichi-xaip-receipts-03`, "Signed Execution Receipts for AI Agent Tool Calls (XAIP Receipts)", 2026-07-02.
- `draft-schrock-ep-bounded-capability-receipts-06`, "Bounded Capability Receipts and Durable Spend Control for Agent Actions", 2026-09-09.
- About 28 active agent "receipt" drafts exist in total (e.g. `draft-sahu-agent-action-receipts-00`, `draft-marques-asqav-compliance-receipts-09`, `draft-wang-ccs-runtime-verification-00`). "Receipt" is a crowded word at the IETF right now.

---

## Part 2: other projects a searcher could confuse with Sabline

These showed up when searching for Sabline's own problem (effects for AI-written code, capability budgets, execution receipts, MCP gateways with policy, sandboxes for AI code).

### 7. AILANG (Sunholo). Closest overlap of anything found.
- **URLs read:** https://github.com/sunholo-data/ailang , https://ailang.sunholo.com/ , https://www.sunholo.com/blog/what-is-your-ai-allowed-to-touch/ (developer's blog, 2026-04-26) , https://github.com/sunholo-data/ailang-demos
- **What it does:** a purely functional language for AI-generated code. Function types list effect capabilities (IO, FS, Net, Clock, AI), the operator grants them with `ailang run --caps …`, and the runtime refuses ungranted effects. Per-function call-count limits (`@limit=N`) are called "capability budgets".
- **Quotes:** "Effect system - Capability-based security (IO, FS, Net, Clock, AI)" (README). "Run it without granting `Net` at the command line and it refuses to execute — not a warning, a hard stop." (blog). "Capabilities are statically visible and constrained by budget." (docs site).
- **Language:** implemented in Go. It also ships MCP tools (`ailang_run`, `ailang_check`, …). **Licence:** Apache-2.0. **Kind:** language + runtime.
- **Enforces?** Yes, at run time. Ungranted capabilities stop the program, and `@limit` caps the number of calls.
- **Versus Sabline:** this is the same idea. In the docs I read, the grants are whole categories (`--caps Net`) plus call counts. I saw no per-host or per-path budgets (Sabline's `--allow net:api.example.com`) and no audit, attestation or receipt output, though they may exist in docs I did not read.

### 8. Boruna
- **URL read:** https://github.com/escapeboy/boruna
- **What it does:** a Rust VM and language for deterministic LLM workflows. Every side effect (LLM, HTTP, database, filesystem) must be declared and permitted by policy, and each run can write a hash-chained evidence bundle that can be replayed.
- **Quote:** "Capability enforcement — every side effect (LLM calls, HTTP, database, filesystem) is declared and policy-gated at the VM level."
- **Language:** Rust. **Licence:** MIT. **Kind:** language + workflow runtime, with an MCP server (14 tools).
- **Enforces?** Yes, in the VM at run time. It also records evidence bundles (`--record`).
- **Versus Sabline:** it orchestrates multi-step LLM workflows (a DAG of steps, approval gates) for regulated audit, rather than general-purpose scripts. Its "evidence bundles" are close to Sabline's receipts.

### 9. Vera
- **URL read:** https://github.com/aallan/vera
- **What it does:** a statically typed, purely functional language for LLMs to write. It has mandatory contracts, typed algebraic effects in signatures (e.g. `effects(<Http, Inference>)`) and Z3 verification, and compiles to WebAssembly.
- **Quote:** "A function that calls an LLM says so in its signature. A caller that doesn't permit `<Inference>` cannot invoke it."
- **Language:** compiler written in Python, targets Wasm. **Licence:** MIT. **Kind:** language.
- **Enforces?** It checks effects at compile time. The README I read describes no operator-granted run-time budget.
- **Versus Sabline:** effects are checked by the type system when the program is compiled. Nothing I read describes an operator narrowing them to specific hosts or paths at run time.

### 10. Agent Receipts / Obsigna
- **URLs read:** https://github.com/agent-receipts/obsigna , https://github.com/agent-receipts/obsigna/tree/main/mcp-proxy
- **What it does:** an open protocol and toolset (Go, TypeScript and Python SDKs, plus an MCP proxy) for signed, hash-chained receipts of each AI agent action. The proxy can also score each tool call's risk and pass, flag, pause or block it.
- **Quotes:** "Agent Receipts is an open protocol for producing cryptographically signed, tamper-evident records of AI agent actions." / "Actions: `pass` (log only), `flag` (log + highlight), `pause` (wait for approval), `block` (reject)."
- **Licence:** Apache-2.0 (the spec is MIT). **Kind:** spec + SDKs + proxy.
- **Enforces?** Mainly records. The MCP proxy can also block or pause calls.
- **Versus Sabline:** it produces receipts for an agent's tool calls from outside, and does not constrain the effects inside a program.

### 11. agent-custody
- **URL read:** https://github.com/ch4r10t33r/agent-custody
- **What it does:** an MCP gateway that checks each agent tool call against Cedar policy. It writes a signed receipt for every call, allowed or denied, to a Merkle transparency log, and includes an offline verifier.
- **Quote:** "Denied calls never reach the tool and still produce a receipt."
- **Language:** TypeScript and Python. **Licence:** Apache-2.0. **Kind:** gateway + SDK + verifier.
- **Enforces?** Yes, at the gateway at run time.
- **Versus Sabline:** it applies policy to an agent's MCP tool calls at a gateway, not to the effects of a program's own code.

### 12. Wassette (Microsoft)
- **URLs read:** https://github.com/microsoft/wassette , https://microsoft.github.io/wassette/latest/faq.html
- **What it does:** an MCP server that runs agent tools as WebAssembly components in the Wasmtime sandbox. Filesystem, network and environment access is denied unless a `policy.yaml` or a grant tool allows it.
- **Quote:** "Wassette enforces permissions at the runtime level, so unauthorized access attempts are prevented rather than just logged."
- **Language:** Rust. **Licence:** MIT. **Kind:** runtime/MCP server. The README says "not production ready yet".
- **Enforces?** Yes, in the Wasm sandbox at run time.
- **Versus Sabline:** it sandboxes compiled Wasm tool components per host and path using a policy file. It is not a language with effects in signatures, and it produces no audit or receipt output that I saw.

---

## Fetch failures and gaps (2026-09-25)

| URL | Result |
|---|---|
| https://github.com/invariant-systems-ai/aiir (and its README) | 404. It is not among the org's public repos, though PyPI still links to it |
| https://pypi.org/project/aiir/ | Page did not render ("A required part of this site couldn't load"). The PyPI JSON API worked |
| https://www.npmjs.com/package/@policylayer/sdk | 403. The npm registry JSON API worked |
| https://github.com/policylayer/intercept , https://github.com/PolicyLayer/PolicyLayer | 404 (repos named in npm metadata) |
| https://www.bunbox.ai/ , https://bunbox.ai/ | 404. The only description of it is a search snippet |
| https://workproof.solutions/ | Only the page title "Workflow AS Demo Lab" came back (likely JS-only) |
| https://registry.npmjs.org/agentbudget | 404. No unscoped npm package, despite the README's `npm install agentbudget` |

Nothing here is filled in from search snippets unless it is labelled as a snippet.

---

## Added after the agent's pass (read from arXiv's API, 2026-09-25)

### 13. ETAS
- **URL read:** https://arxiv.org/abs/2607.17780 (v1, 2026-07-20; Huiri Tan, Yikun Wang, Puyang Zhang, Shangyu Li, Jiasi Shen)
- **What it does:** a research programming language for agent systems in which agents, tool calls, prompts, memory, approvals, policies and traces are part of the language. It tracks effect rows and requested action traces in the type system, checks them against allow/deny/temporal specs, and leaves residual obligations to runtime checks. It is implemented in Rust.
- **Quote (abstract):** "ETAS provides a programming-language foundation for reasoning about authorization, nondeterminism, recovery, and audit evidence before and during agent execution."
- **Versus Sabline:** it is a language for orchestrating agents and their actions, whereas Sabline is a language for the scripts an agent writes. It was the top result for the search "language where function signatures declare effects runtime refuses AI-written code".

### 14. AgentBound
- **URL read:** https://arxiv.org/abs/2510.21236 (2025-10-24; Christoph Bühler, Matteo Biagiola, Luca Di Grazia, Guido Salvaneschi)
- **What it does:** an access-control framework for MCP servers. A declarative permission policy modelled on Android's is enforced around an unmodified server. Policies can be generated from source code (80.9% accuracy on 296 servers).
- **Quote (abstract):** "AgentBound combines a declarative policy mechanism, inspired by the Android permission model, with a policy enforcement engine that contains malicious behavior without requiring MCP server modifications."
- **Versus Sabline:** it confines existing MCP servers written in any language, whereas Sabline bounds programs written in Sabline. It appeared fifth for phrasing 13.
