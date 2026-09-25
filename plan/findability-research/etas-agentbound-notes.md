# ETAS and AgentBound: related-work notes for the Sabline paper

Read 2026-09-25. Everything below comes from the sources listed in this section. Nothing is filled in from memory.

## Sources and load status

| Source | Status |
|---|---|
| arXiv API `export.arxiv.org/api/query?id_list=2607.17780,2510.21236` | Loaded |
| ETAS abstract page, full HTML (`arxiv.org/html/2607.17780`, v1) and PDF v1 (27 pp.) | Loaded. Read the whole HTML; checked figure and theorem numbering against the PDF. |
| ETAS repo `github.com/etas-project/etas`: README, CITATION.cff, API metadata | Loaded |
| AgentBound abstract pages v1, v2 and v3; full HTML (v3) and PDF v3 (25 pp.) | Loaded. Read the whole HTML text. **The arXiv HTML shows Figs. 3 and 9 as "TODO", and its figure numbers differ from the PDF.** Figure numbers below follow the **PDF/FSE** numbering: HTML Fig. 1 is PDF Listing 1, and HTML Figs. 6-10 are PDF Figs. 3-7. |
| AgentBound replication package, Zenodo 10.5281/zenodo.19571298: README, LICENSE, `sandbox-runtime-permissions.md`, `sandbox/python/README.md`, STATUS | Loaded. I downloaded only the 3.2 MB `repository.tar.gz`, not the 3.5 GB `servers.tar.gz`. |
| Crossref record for 10.1145/3808103 | Loaded |
| arXiv BibTeX export for both ids | Loaded |

The AgentBound paper links no GitHub repository of its own. Its code is in the Zenodo package.

---

## 1. ETAS: An Effect-Typed Language for Agent Systems

### Citation

Huiri Tan, Yikun Wang, Puyang Zhang, Shangyu Li, Jiasi Shen (all at The Hong Kong University of Science and Technology). *ETAS: An Effect-Typed Language for Agent Systems.* arXiv:2607.17780v1 [cs.PL], submitted 20 July 2026. It is cross-listed in cs.AI, cs.LG and cs.MA. v1 is the only version. arXiv lists no venue, journal reference or comments. DOI (arXiv DataCite): 10.48550/arXiv.2607.17780. The paper body spells the name "Etas"; the arXiv title uses "ETAS".

```bibtex
@misc{tan2026etas,
  title         = {{ETAS}: An Effect-Typed Language for Agent Systems},
  author        = {Tan, Huiri and Wang, Yikun and Zhang, Puyang and Li, Shangyu and Shen, Jiasi},
  year          = {2026},
  eprint        = {2607.17780},
  archivePrefix = {arXiv},
  primaryClass  = {cs.PL},
  doi           = {10.48550/arXiv.2607.17780},
  url           = {https://arxiv.org/abs/2607.17780},
  note          = {Version 1, 20 July 2026}
}
```

### Summary

ETAS is a programming language for agent systems. Flows, agents, model inference, model-callable tools, typed prompts, scoped memory, approvals, handlers and traces are all semantic constructs of the language rather than framework conventions (§1, §2). Its core calculus, Core Etas (§3), separates values from computations. It types each computation with three things: an *escaping effect row*, a *requested-action trace abstraction*, and a set of residual checks. As a result, a request that a handler intercepts still appears in the trace even after it stops escaping (§4.1-4.2).

A terminating spec calculus handles type, callable and trace constraints together (§4.3, Fig. 8). Trace specs combine allow `+p`, deny `-p` and before-obligation `p >> q` rules. They normalise to TraceSpecAlgebra (Fig. 10) and compile to finite monitors. The checker then discharges these monitors by abstract interpretation: it either proves the property, rejects the program, or emits an explicit residual runtime check (§4.4).

A small-step semantics distinguishes request, handled, commit and denied events and enforces monitors and effect boundaries (§5, Fig. 11). §6 *states* preservation, progress, type soundness, effect soundness, policy safety and handler trace transparency, each with a proof sketch. A Rust prototype is described in §7 and evaluated through four case-study programs in §8.

### Threat model and what it enforces

- **The paper has no explicit threat model and names no adversary.** Its implicit assumption is that model output is nondeterministic and not trusted. §5.2 says "no model output can cause an unmediated host operation". §6.5 says the theorems "do not assert that model outputs are correct, stable, or safe".
- **Trusted parties:** the programmer, the trace specs, deployment grants, and the public contracts that host bindings export (§7.2).
- **Compile time:**
  - type and effect checking;
  - the inferred row must be covered by the declared row, `ε_i ⊑ ε_d` (§4.2);
  - trace-spec monitor discharge, which proves, rejects or leaves a residual check (§4.4);
  - handler arm checks, which allow at most one `resume` per path (§4.1);
  - secret and prompt-trust checks, where a `SecretValue` cannot go into a prompt unless it is declassified (§2, Table 2);
  - tool-surface warnings, for example when an exposed tool can run a shell (§8.1).
- **Run time:** the interpreter mediates every `perform`.
  - *Request enforcement* checks the request against the monitor state for the current trace prefix.
  - Handler dispatch happens next. Handlers "do not grant authority" (§3.3).
  - *Commit enforcement* checks the effect boundary `ε_b` and the commit transition before the default dispatcher runs (§5.2-5.4). An implementation "may add deployment-grant, tool-exposure, or sandbox predicates", but the core rules leave them out (§5.2).
  - Model output is schema-validated (§5.2). Token and attempt limits are interpreter facilities that sit outside the formal core (§2, §7.3).
- **OS level:** the design names sandboxing only as an abstract commit predicate. It is "not [a] separate component of the core calculus" (§5), and §7 describes no OS-level mechanism.
- **Code covered:** only programs written in ETAS (`.es`). Host services are reached through bindings that declare their contracts (§7.2-7.3).

### Evaluation

§8 is "artifact-oriented" and poses four research questions: RQ1 expressiveness, RQ2 static detection, RQ3 runtime evidence and RQ4 optimisation. The evidence is four programs in Fig. 12:

- (a) context engineering: a trace spec denies reads of secret memory;
- (b) harness engineering: model, tools, limits, and denial of shell execution;
- (c) loop engineering: a bounded repair loop in which CI and review must come before a protected merge;
- (d) optimisation: narrowing the tool surface, hoisting and deduplicating a loop-invariant search, and running independent iterations in parallel.

The answers are qualitative: "Yes, for the evaluated patterns" (RQ1), "Yes for the modeled properties, with residualization" (RQ2), "Yes at prototype scope" (RQ3) and "Yes" (RQ4, meaning candidates are identified; §8.2). **The paper reports no quantitative results:** no timings, benchmark suites, attack corpora or user studies. §1 itself calls §7-§8 the prototype and "evaluation plan".

### Implementation

- **Language and structure:** Rust. The pipeline is source → AST → HIR → checked HIR → interpreter, and the interpreter runs checked HIR directly (§7.1, §7.3).
- **Features:** package metadata that carries authority and trace-spec summaries (§7.2), checkpoint/resume, and replay (README: `etas replay`, `etas resume`).
- **Repos:** `github.com/etas-project/etas` for the CLI, driver and package manager, plus `etas-core`, `etas-frontend`, `etas-interpreter`, `etas-edk` and `etas-ide`.
- **Licence:** dual MIT / Apache-2.0 (README, CITATION.cff).
- **Maturity:** the README says it is "highly experimental … Do not use Etas for production or security-critical systems". Only "Phase 1" is implemented, meaning the frontend and checked-HIR interpreter. The AIR/FIR runtime and optimiser are not in the user path. "Protocol-state analysis, the full concurrency surface" are incomplete, and `etas policy` is marked "Explicitly unsupported".
- **Repo activity:** the repo was created on 2026-07-21 and last pushed on 2026-09-23. It has 5 stars and no releases or tags.

### Where ETAS is ahead of Sabline

1. **A formal calculus with stated metatheory.** It has a core syntax (§3.1, Fig. 3), bidirectional typing with spec conformance (§4.1, Figs. 5-6) and a small-step semantics (§5, Fig. 11). §6 states six results: Lemma 1 Preservation, Lemma 2 Progress, Thm 3 Type soundness, Thm 4 Effect soundness, Thm 5 Policy safety and Thm 6 Handler trace transparency. Each has a proof sketch; a mechanised proof is future work. Sabline has no calculus.
2. **Temporal and trace policies.** Trace specs express ordering obligations as well as allow and deny rules. An example is `ApprovalBefore<A> = +Approval.request & +A & (Approval.request >> A)` (§2, §4.3, Fig. 10). They compile to finite monitors and are enforced on the trace prefix at run time (§4.4, §5.3). Sabline tracks only per-effect grants and counts.
3. **Static proof with residual checks, applied to authorisation policy.** Abstract interpretation over monitor states proves a policy, rejects the program, or emits a runtime obligation, and Thm 5 covers all three cases (§4.4, §6.4). Sabline does the same kind of prove-or-check-at-run-time for requires/ensures contracts, but not for authorisation policy.
4. **Requested actions are kept apart from committed ones.** The persistent requested-action trace is separate from the escaping effect row, and events are split into request, handled, commit and denied (§3.2, §4.2, §5.2). A denied or mocked request therefore stays visible to policy and audit.
5. **Effect handlers that cannot hide requests or grant authority.** Handlers can mock, dry-run, replay or recover (§2, §3.3, §5.4, Thm 6).
6. **First-class agent constructs.** Model inference is a distinguished action, `Agentic.infer<g,T>`, so its nondeterminism is marked in the program (§3.3, §5.2). Tool surfaces come from `@tools`, and an agent may request only the tools it exposes (§3.3). The language also has typed prompts with trust labels, typed memory regions, approvals and `@limits` (§1, §2). Sabline has no inference, tool-surface or approval constructs.
7. **Resource-indexed effects with containment derived from evidence.** For example, `Memory.read<ProjectMemory> ⊇ Memory.read<ProjectMemory.Reports>`, and read authority does not imply write authority (§4.2).
8. **A unified, terminating spec calculus** with higher-order spec functions covering type, callable and trace constraints (§4.3, Fig. 8).
9. **Separate compilation of authority.** Package metadata exports the effect, action, tool and trace-spec contracts of imported modules (§7.2).
10. **Checkpoint/resume and recovery semantics.** Deterministic code is recomputed, while agent calls, external reads, approvals and non-idempotent writes are replayed from checkpoints, and "Resampling a model call is distinct from replay" (§5.3). Sabline has receipts; check whether this distinction goes beyond what Sabline's replay does before claiming it.
11. **Optimisation opportunities justified by effect and trace facts** (§8.2). This is design-level only: "a separate optimization representation and production scheduler are outside the current prototype" (§7.3).
12. **A Rust implementation of the compiler and interpreter already exists** (§7). Sabline's Rust runtime is still in progress.

### Where Sabline covers something ETAS does not (only what the paper states)

1. **OS-level confinement.** ETAS keeps sandboxing abstract: "Concrete deployment grants, tool exposure, and sandbox descriptors refine the implementation of dispatch, but they are not separate components of the core calculus" (§5). §5.2 adds "The core rules omit them", and §7 describes routing to host services, not an OS mechanism. Sabline's Landlock+seccomp layer beneath the interpreter is a concrete version of what ETAS leaves abstract. Say "the paper does not describe", not "ETAS cannot".
2. **Secret flows to sinks other than the model.** ETAS says its prompt-trust mechanism "targets the narrower problem of exposing untrusted or secret flows into privileged model inputs without requiring a full dependent information-flow system" (§9). *If* Sabline's `Secret of T` constrains flows to network, file and output sinks, that scope is exactly what ETAS says it narrows away from. Confirm Sabline's sink coverage before writing this.
3. **Per-grant counts.** The operational limits ETAS describes are token, attempt and loop limits. "Runtime limits and retry budgets are implemented as orthogonal interpreter facilities; they are not part of the Core Etas formalism" (§7.3; also §2). The paper does not describe per-resource call counts like Sabline's `@100`.
4. **Maturity and scale are stated as open.** "The case studies do not yet establish trace completeness at production scale" (§8.1, RQ3). RQ1's evidence "covers three compact patterns, not general claims about large-program ergonomics" (§8.1). The README warns against security-critical use. Use this as context, not as a Sabline capability claim.

**Do not claim these as Sabline differentiators, because ETAS has them too:**

- **Secret handling:** `SecretValue` cannot enter a prompt without declassification (§2, Table 2).
- **Operator-side grants:** "deployment permissions" in the abstract and §5; the README's runtime profiles include network `allow` lists and `--allow-effects`.
- **A pre-run effect report:** `etas effects` (README), and the deployment-plan summary in Table 2.
- **Traces with replay:** §5.3, §7.3.
- **No mechanised proof:** ETAS does not have one either (§6).

The paper never mentions MCP, SMT/Z3, or requires/ensures contracts. That absence is not a stated limitation, so cite it cautiously if at all.

### Quotes (all under 30 words)

1. §6: "The prototype currently implements the corresponding checks as compiler and interpreter invariants; a mechanized proof is future work."
2. §6.5 (closing paragraph): "whatever the model returns, the surrounding program cannot commit an undeclared, unauthorized, or unmonitored external action without crossing an explicit residual check or raising a typed enforcement error"
3. §2 ("Handled does not mean invisible"): "Thus the handler eliminates the caller’s control obligation but not the audit fact that the program requested email."

Alternates: §4.4 "Every accepted but unproved transition is therefore an explicit runtime obligation". §1 "Handlers may interpret selected action requests for testing, replay, recovery, or host adaptation, but handlers do not grant authority."

### Draft related-work paragraph (128 words)

ETAS \cite{tan2026etas} is an effect-typed language in which agents, model inference, tools, prompts, memory and approvals are language constructs. Each computation carries an escaping effect row and an abstraction of the actions it may request; trace specifications with allow, deny and ordering constraints compile to monitors, discharged statically where possible and otherwise left as explicit runtime checks, and handlers can mock an action without hiding the request. ETAS is ahead of Sabline in having a core calculus with stated preservation, progress, effect-soundness and policy-safety theorems (with proof sketches), and in expressing temporal policies; Sabline bounds only per-effect grants and counts. ETAS serves programmers who embed model calls in agent programs; Sabline bounds scripts a model writes, under an operator budget backed by OS confinement, which ETAS leaves abstract.

---

## 2. AgentBound: Securing Execution Boundaries of AI Agents

### Citation

Christoph Bühler, Matteo Biagiola, Luca Di Grazia, Guido Salvaneschi. The authors are at the University of St. Gallen; Biagiola is also at USI Lugano. *AgentBound: Securing Execution Boundaries of AI Agents.*

- **arXiv:** 2510.21236 [cs.CR], cross-listed in cs.AI and cs.SE; ACM class D.2.0. Versions: v1 on 24 Oct 2025, v2 on 29 Oct 2025, v3 on 24 Apr 2026. v3 is the version I read.
- **Published version:** *Proceedings of the ACM on Software Engineering* 3(FSE), Article FSE096, 24 pages (pp. 2141-2164 per Crossref), publication date July 2026, presented at FSE 2026 in Montreal.
- **DOI:** 10.1145/3808103. The arXiv DataCite DOI is 10.48550/arXiv.2510.21236.
- **History and licence:** received 2025-09-12, accepted 2026-03-24. The paper is licensed CC BY 4.0.
- **Citation request:** the v3 PDF opens with "To cite this work please refer to the FSE'26 paper". The v1, v2 and v3 abstracts are the same apart from minor wording.

```bibtex
@misc{buhler2026agentbound,
  title         = {{AgentBound}: Securing Execution Boundaries of {AI} Agents},
  author        = {B{\"u}hler, Christoph and Biagiola, Matteo and Di Grazia, Luca and Salvaneschi, Guido},
  year          = {2026},
  eprint        = {2510.21236},
  archivePrefix = {arXiv},
  primaryClass  = {cs.CR},
  doi           = {10.1145/3808103},
  url           = {https://arxiv.org/abs/2510.21236},
  note          = {v3, 24 April 2026. Published in Proc. ACM Softw. Eng. 3(FSE), Article FSE096 (FSE 2026)}
}
```

arXiv's own export uses `year={2026}` and puts a URL in its `doi` field. The version above uses a plain DOI. Because the authors ask for the FSE version, you may prefer this entry:

```bibtex
@article{buhler2026agentbound_fse,
  title   = {{AgentBound}: Securing Execution Boundaries of {AI} Agents},
  author  = {B{\"u}hler, Christoph and Biagiola, Matteo and Di Grazia, Luca and Salvaneschi, Guido},
  journal = {Proceedings of the ACM on Software Engineering},
  volume  = {3},
  number  = {FSE},
  articleno = {FSE096},
  pages   = {2141--2164},
  year    = {2026},
  doi     = {10.1145/3808103},
  note    = {FSE 2026. arXiv:2510.21236}
}
```

### Summary

AgentBound presents itself as "the first access control framework for MCP servers" (abstract; this is the authors' claim). It has two parts. **AgentManifest** is a JSON manifest that lists generic capabilities from an 18-entry vocabulary. The vocabulary was derived systematically: 16 agent use-cases from the literature were mapped to Android permissions, then pruned and merged against macOS TCC, and desktop-system capabilities were added (§3.1, Tables 1-2). **AgentBox** is a Docker-based enforcement engine. It runs each *unmodified* server in a container, and the user consents to runtime permissions (a concrete path, env-var name or host/port) that must be covered by the manifest. The container enforces them with mounts, an environment whitelist and iptables egress rules (§3.1 "Manifests", §3.2-3.3). **AgentManifestGen** is a two-stage LLM pipeline that writes manifests from a server's source and documentation (§3.1, §3.3). §4 evaluates completeness against 296 popular MCP servers (RQ1), security against malicious servers (RQ2), and overhead on macOS and Debian (RQ3).

### Threat model and what it enforces

- **Adversary:** someone who controls one or more malicious MCP servers and aims at confidentiality, integrity or availability. The agent "is assumed to behave as intended" (§2.3, adapted from Song et al.).
- **Attack vectors in scope:** MCP prompt injection, tool poisoning, puppet attacks, rug pulls and MCP application-level attacks (including SQL injection and supply-chain attacks). They count only when the attack reaches system resources (the filesystem, network or OS interfaces).
- **Out of scope:** attacks that manipulate only the LLM's reasoning or output. Attacks inside the policy are the "semantic gap" (§2.3, §5).
- **Enforcement, part 1 (at launch):** runtime permissions are checked against the manifest. If one is not covered, execution aborts, and the user is asked to consent to each permission (§3.1).
- **Enforcement, part 2 (OS level, during execution):** the container runs deny-by-default. Filesystem scopes are bind mounts, env vars are whitelisted, and egress is limited to allowed hostnames that are resolved to IPs and turned into iptables rules (§3.2-3.3).
- **Only three capability groups are actually enforced:** filesystem, environment variables and network. Devices, location, clipboard and notifications would need "a native companion application", and device mounts are "all-or-nothing" (§3.3).
- **No static checking of server code.** Manifest generation reads the source, but it is an LLM inference step, not a verifier.
- **Code covered:** any MCP server, unmodified. The implementation installs servers from npm or PyPI (§3.3), and the paper notes that 93.3% of MCP servers are JavaScript or Python (§3.1). The artifact integrates through stdio (`SandboxedMCPStdio`).

### Evaluation (§4; figure numbers are PDF/FSE)

**RQ1 Completeness (§4.1).**
- **Dataset:** the top 300 PulseMCP servers by GitHub stars (59 to 63,215 stars), of which 296 were usable.
- **Manifest generation:** gpt-5-mini produced 5 intermediate manifests per server and gpt-5 consolidated them. The API cost was $99.25.
- **Capability prevalence (Fig. 3):** network.client 83.1%, system.env.read 79.6%, filesystem.read 74.1%, filesystem.write 49.3%, network.server 30.6%.
- **Android-vocabulary comparison (Fig. 4):** INTERNET 90.5%. The mobile-only permissions it found turned out to be false positives: those servers reach phones over ADB, which is really `system.exec`.
- **Developer review:** the authors opened GitHub issues for the top 96 servers. 74% got no response, 17.7% were accepted, 4.2% are still under discussion and 4.2% were rejected. The paper reports "80.9% accurate and precise, while recall is 100%". My inference, not stated in the paper: 80.9% matches 17 accepted out of 21 resolved responses.
- **Manual comparison (§4.1.4):** on 48 servers, generated manifests matched hand-written ones on 787 of 816 capability decisions, which is 96.5% accuracy with precision 0.94 and recall 0.96. 28 of 48 servers matched exactly. The worst case was Clerk at 76.5%. Of the 29 mismatches, 23 were false negatives and 6 false positives.

**RQ2 Security (§4.2).**
- **A.1-A.3, the authors' own SSH-key exfiltration server:**
  - A.1, native: the key is exfiltrated.
  - A.2, network blocked: the server reads the key but cannot send it.
  - A.3, fully sandboxed: the server cannot read the key.
- **B.1-B.4, from Song et al.'s MCP-Artifact:**
  - Blocked: B.1 Google Maps (API host rewritten to an IP address) and B.3 mcp-weather-server (API host rewritten).
  - Not blocked: B.2 mcp_server_time (a puppet attack that redirects crypto transfers to a *permitted* endpoint) and B.4 wechat-mcp (SQL injection that stays inside the boundary).
- **C.1-C.10, from the Damn Vulnerable MCP Server challenge:**
  - Preventable: C.2, C.3, C.4 and C.5.
  - Mitigated: C.8 and C.9.
  - Depends on the attack vector: C.10.
  - Not preventable: C.1 and C.6 (prompt injection into the LLM) and C.7 (an application flaw that does not target system resources).
- **Summary:** AgentBound prevents "all the malicious attacks that target system resources and do not stay within the control boundaries (9 attacks in total)" (Fig. 5, Fig. 6).

**RQ3 Efficiency (§4.3, Fig. 7).**
- **Setup:** a MacBook Pro (M3 Pro) with Docker Desktop, and a Debian 12 VM with 16 cores and Docker 28.4.0.
- **Startup (mean of 5 runs, sandboxed vs native, ms):**

  | Server | macOS sandboxed | macOS native | Debian sandboxed | Debian native |
  |---|---|---|---|---|
  | ExtractSSHKey | 359.4 | 156.6 | 608.4 | 175.8 |
  | Google Maps | 237.4 | 79.2 | 394.6 | 76 |
  | Weather | 643.3 | 553.9 | 856.6 | 620.2 |
  | Server Time | 502.2 | 342.2 | 675.9 | 495 |
  | WeChat | 887.6 | 567 | 955.1 | 679.3 |

  The text summarises this as "roughly 150 ms to 300 ms" of overhead on macOS and "up to 400 ms" on Debian. Computed from the table, the differences are 89-321 ms on macOS and 181-433 ms on Debian.
- **Per operation:** read file, write file, read env and fetch URL, 1000 runs × 1000 operations each. The overhead is +0.6 ms on average on macOS and +0.29 ms on Debian.

### Implementation

- **Code:** the `mcp_sandbox` Python integration layer; its `SandboxedMCPStdio` class wraps the normal MCP stdio client and is used with the OpenAI Agents SDK. There are Docker images for npm and PyPI servers, plus an entrypoint that installs the package and then applies the iptables rules. The artifact also contains the AgentManifestGen tooling, a PulseMCP downloader, a malicious-server generator, and benchmarks.
- **Availability:** the Zenodo replication package 10.5281/zenodo.19571298 (published 2026-04-14; concept DOI 10.5281/zenodo.19468200). **Licence: the Zenodo record lists CC BY 4.0, but the `LICENSE` file inside the archive is GNU AGPL-3.0.**
- **Maturity:** a research artifact. The README targets the "Functional, Reusable, Available" badges; this is a stated target, not a confirmed award. It lists these limits:
  - the quickstart needs an `OPENAI_API_KEY`;
  - recollecting the dataset depends on the live PulseMCP service;
  - the artifact "does not claim to solve semantic prompt/tool poisoning in general".

### Where AgentBound is ahead of Sabline

1. **It confines unmodified third-party MCP servers regardless of their implementation language,** because the container is the boundary (§1, §3.2). The implementation installs from npm or PyPI (§3.3). Sabline bounds only programs written in Sabline and does not confine other MCP servers.
2. **It generates policies automatically from existing source code** with AgentManifestGen (§3.1, §3.3), and validates them in two ways: developer review of 96 servers (80.9%) and manual manifests for 48 servers (96.5%) (§4.1.3-4.1.4).
3. **It includes an empirical study of real MCP servers:** capability prevalence across 296 popular servers and engagement with developers through GitHub issues (§4.1.2-4.1.3, Figs. 3-4).
4. **It is evaluated against third-party malicious-server sets** (Song et al.'s MCP-Artifact and the Damn Vulnerable MCP Server) as well as an in-house exfiltration server. It reports honestly which attacks it cannot stop (§4.2, Figs. 5-6).
5. **It measures overhead on two platforms,** macOS with Docker Desktop and Debian, covering both startup and per-operation cost (§4.3, Fig. 7).
6. **Its capability vocabulary was derived systematically** from the literature, Android permissions and macOS TCC. It covers peripherals, clipboard, location, notifications, process control and exec, which is broader than Sabline's effect set, although only filesystem, env and network are enforced today (§3.1, Table 2, §3.3).
7. **Policy has two levels:** portable manifests bundled with the server and reusable across agent frameworks, plus per-execution runtime permissions that the user consents to (§3.1 "Manifests", §3.2).
8. **It is peer-reviewed** (FSE 2026 / PACMSE) and has an archived artifact on Zenodo.

### Where Sabline covers something AgentBound does not (only what the paper states)

1. **Behaviour inside the granted policy.** §5: "AgentBound cannot prevent attacks that do not violate the declared policy". The examples are B.2 (altered parameters to a permitted endpoint) and B.4 (SQL injection). AgentBound controls whether a secret env var is *visible* through its environment whitelist (§3.2). The paper describes nothing about where that value flows afterwards. Sabline works inside the granted surface, but only for programs written in Sabline: it has per-function effect declarations, requires/ensures contracts proved by Z3 or checked at run time, and `Secret of T` flow control. Do not claim that Sabline stops B.2 or B.4-style attacks.
2. **Program analysis as the complementary layer.** §5 says "semantic and configuration-related issues are usually handled by complementary approaches, like anomaly detection or program analysis". Sabline's compile-time checks are such an approach, for its own programs.
3. **Declarations checked against code versus inferred from it.** AgentBound manifests are LLM-inferred and "still requir[e] review to address false positives (over-approximated capabilities) and rare false negatives (missed capabilities)" (§5). §4.1.4 found 23 false negatives and 6 false positives out of 816. In Sabline, the compiler checks declared effects against the code, and `sabline audit` reports them. In AgentBound, a false negative only denies an operation at run time, while a false positive over-grants.

**How they differ in trust base (a difference, not a stated gap).** AgentBound's "trusted computing base includes Docker itself, Linux kernel features (namespaces, cgroups, iptables) … and the PyPI and Node.js runtimes" (§5). Sabline needs no container runtime; on Linux it confines through Landlock and seccomp directly. Its own trust base includes its Python interpreter, and its macOS and Windows confinement is partial.

**Do not claim:**

- **A pre-run declared surface:** AgentBound has one too, in the manifest description and capabilities that are shown for human review (§3.1).
- **Operator/user-scoped grants on paths, env vars and hosts:** AgentBound has these as runtime permissions (§3.1).

**Caution:** the paper's design installs the server package "before network restrictions are applied" (§3.3), and it does not discuss install-time code. That is an observation, not a limitation the paper states.

### Quotes (all under 30 words)

1. Abstract: "AgentBound combines a declarative policy mechanism, inspired by the Android permission model, with a policy enforcement engine that contains malicious behavior without requiring MCP server modifications."
2. §5 (Limitations of the approach): "AgentBound cannot prevent attacks that do not violate the declared policy."
3. §2.3: "Attacks that manipulate only the reasoning process or output of the LLM, without resulting in system resource access or modification, are out of scope."

Alternate, §5: "AgentBound’s trusted computing base includes Docker itself, Linux kernel features (namespaces, cgroups, iptables) that implement isolation, and the PyPI and Node.js runtimes."

### Draft related-work paragraph (129 words)

AgentBound \cite{buhler2026agentbound} applies an Android-style permission model to MCP servers: each server ships a manifest of generic capabilities, the user instantiates them as concrete paths, variables and hosts at launch, and a Docker container enforces the result without modifying the server. It is ahead of Sabline in reach and evidence: it confines unmodified third-party servers from npm and PyPI, generates manifests from source with an LLM (80.9\% accuracy on developer review), characterises 296 popular servers, and blocks the resource-targeting attacks in public malicious-server sets at under a millisecond per operation. It states that attacks staying within the declared policy, such as altered arguments to a permitted host, are beyond it. Sabline works inside that boundary, checking declared effects, contracts and secret flows, but only for programs written in Sabline.

---

## Discrepancies to be aware of

- **AgentBound, 96.5% vs 96.4%:** manual-evaluation accuracy is 96.5% in §4.1.4 but 96.4% in the RQ1 summary box. Cite 96.5% with the section.
- **AgentBound, capability count:** Table 2 lists 18 capabilities, but §4.1.4 computes "816 capabilities (17 capabilities by 48 MCP servers)". The artifact's `permission-system.md` lists 17 (it omits clipboard.write), while its code enum has 18. Avoid stating the count, or say "18 (Table 2)".
- **AgentBound, "0.6 ms on average":** the introduction's figure is the macOS number only; Debian is 0.29 ms. Startup overhead is separate, at roughly 150-400 ms.
- **AgentBound, figure numbers:** the arXiv HTML numbers figures differently from the PDF and renders Figs. 3 and 9 as "TODO". Cite PDF/FSE numbers.
- **ETAS, "state" vs "prove":** the theorems are *stated* with proof sketches, not machine-checked (abstract: "We state …"; §6). Write "states" or "gives proof sketches", not "proves".
- **ETAS, Table 1:** the capability comparison against other frameworks, in which ETAS scores ✓ everywhere, is the authors' own assessment.
