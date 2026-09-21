# Crosswalk

This page maps what Sabline guarantees, and what it says it leaves open, onto four frameworks written for AI agents: the OWASP Top 10 for Agentic Applications, the OWASP Agent Control Standard, AIUC-1 and the NIST AI Risk Management Framework 1.0. It has one row for every control each framework lists, and each row gives exactly one of four words:

- **enforced** - Sabline's runtime or compiler refuses it.
- **recorded** - Sabline writes a record that a person or a tool can check afterwards, but does not stop it.
- **partial** - some of the control is covered, and the row says which part is not.
- **not addressed** - nothing in Sabline does it.

The project wrote this page, as it wrote [COMPLIANCE.md](../COMPLIANCE.md); no third party has assessed it. COMPLIANCE.md maps the same guarantees onto the OWASP Top 10 for LLM Applications and the OWASP MCP Top 10.

## How a row is judged

- A control is read as its framework writes it, for a system in which agent-written code runs as Sabline. Code that is not Sabline is outside every row - THREAT_MODEL.md's "Code not written in Sabline" - and the rows do not repeat it.
- A control whose outcome is an organisation's policy, process, plan, role, training, consultation or incident response is **not addressed**: a language cannot do those. Where a Sabline record could feed such a process, the row says so in one clause, and the status stays.
- Where a row could be read two ways, it takes the weaker word, and the cell says why.
- **No row on this page is enforced or recorded.** Every control here asks for more than the refusal or the record Sabline makes - at the least a granted `ffi` module, whose behaviour Sabline does not bound, the model's own text, which Sabline does not read, or a process only an organisation can run. Where the covered part of a partial row is a refusal or a record, the cell says which.

| Framework | Controls | enforced | recorded | partial | not addressed |
|---|---|---|---|---|---|
| OWASP Top 10 for Agentic Applications | 10 | 0 | 0 | 7 | 3 |
| OWASP Agent Control Standard (ACS) | 16 | 0 | 0 | 0 | 16 |
| AIUC-1 | 53 | 0 | 0 | 15 | 38 |
| NIST AI RMF 1.0 | 72 | 0 | 0 | 12 | 60 |

## Reading the columns

- **Control** is the framework's own identifier and title, copied from the publisher (see Sources).
- **Sabline** first names the guarantees the row rests on, by their names in the README's "Why Sabline" table - Effects are visible; Promises are proven; Failure is unignorable; Secrets cannot be printed, or looked at; Fast where it's safe - or says "No guarantee." Then it says what is covered and what is not. "Known open:" names rows of THREAT_MODEL.md's Known open table; "Not defended:" names entries of its "What it explicitly does NOT defend against" list.
- **Where** names the mechanism, as THREAT_MODEL.md's "What it defends against" table names it, and the suite that tests it. A mechanism marked (8.3) is new in 8.3.

## Sources

Read on 2026-09-15.

| Framework | Publisher's source | Version | Identifiers verified |
|---|---|---|---|
| OWASP Top 10 for Agentic Applications | [genai.owasp.org resource page](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/); [OWASP's announcement](https://genai.owasp.org/2025/12/09/owasp-top-10-for-agentic-applications-the-benchmark-for-agentic-security-in-the-age-of-autonomous-ai/) | for 2026, published 2025-12-09 | yes; the full document's text was not read (see the section) |
| OWASP Agent Control Standard (ACS) | [genai.owasp.org resource page](https://genai.owasp.org/resource/agent-control-standard-acs/); [specification repository](https://github.com/GenAI-Security-Project/agent-control-standard) | specification v0.1.0, release v0.1.1; page dated 2026-09-01 | yes; ACS assigns no control identifiers (see the section) |
| AIUC-1 | [standard.aiuc-1.com](https://standard.aiuc-1.com/llms.txt) | release of 2026-07-15 | yes |
| NIST AI RMF 1.0 | [AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/); [NIST AI 100-1](https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf) | AI RMF 1.0, January 2023 | yes; each subcategory's text checked against NIST AI 100-1 |

## OWASP Top 10 for Agentic Applications

The identifiers and titles are OWASP's, from the GenAI Security Project's announcement of 2025-12-09 and its resource page for the document. The full document was not reached for this draft, so each row is judged against its title and the one-line description OWASP's announcement gives it. Read the rows again against the document's own text before this page is published.

| Control | Sabline | Status | Where |
|---|---|---|---|
| ASI01 Agent Goal Hijack | No guarantee. Sabline does not read a model's instructions or see its goal change. What a hijacked agent's Sabline program can reach is still the operator's budget, but that is ASI02's row: nothing here stops the hijack, so the weaker word. Not defended: The meaning of text. | not addressed | none |
| ASI02 Tool Misuse | Effects are visible. Covered, as a refusal: an effect, path, host, port, Python module or count outside the operator's budget is refused when it is attempted and cannot be caught, whatever the program declares; neither door grants a caller more than its `--max-allow`. Not covered: a granted effect misused inside its grant - any write under a granted directory, any request to a granted host. Known open: A granted `ffi` module; Native code. Not defended: Rate, and the meaning of a request; What a granted host does with a request. | partial | The effect budget, the module allow-list, scoped fs and net grants and counts (E310, E311, E313, E314, E315) - `check_sandbox.py`, `check_library.py`; `--max-allow` on both doors - `check_library.py`; `sabline eval`, with no net and no ffi - `check_eval.py` (8.3) |
| ASI03 Identity & Privilege Abuse | Secrets cannot be printed, or looked at; Effects are visible. Covered, as a refusal: `env` is an effect of its own; a value from `env()` or `read_file_secret()` cannot be printed, written, sent, handed to Python, put in a failure's reason or branched on (E560, E563); the HTTP door removes its token from the environment before any worker starts; a program cannot change the budget it runs under, except through a granted `ffi` module. Covered, as a record: each `declassify`, with its reason, in the audit and in the receipt. Not covered: identity - the door's token is one principal, with no identity per caller and no way to revoke one holder - and whatever the operating-system user running Sabline can already do. Known open: Secrets arriving another way; Timing and other side channels; The user running sabline. Not defended: The door's token, once it is out; The MCP server's caller. | partial | `Secret of T` - `check_secret.py`, `check_refusals.py`; `env` as its own effect - `check_sandbox.py`; the bearer token and the rate limit - `check_library.py`, `check_adversarial.py` D1; `check_self_budget.py` |
| ASI04 Agentic Supply Chain Vulnerabilities | Effects are visible. Covered, as a refusal: a pull request whose code needs more than `sabline.capabilities` declares fails, when that check is required; `sabline add` refuses different bytes for a vendored library without `--force`, and `sabline deps --verify` fails on one that changed; the Action's `permissions-ratchet` input fails a pull request that widens a workflow's `permissions:` (8.3); `sabline verify` fails an attestation or a receipt whose predicate type or subject digests do not match (8.3). Covered, as a record: `sabline mcp-verify` reports each tool whose description or schema differs from the signed manifest; `sabline deps-diff` reports what an upgrade gained and never fails the job; each release is signed, carries an SBOM and has its wheel built twice and compared. Not covered: what a package that is not Sabline does, which `deps-diff` reports as unknown (exit 3); other MCP servers and agent-to-agent components; a server that behaves differently behind a matching description. Known open: A granted `ffi` module; Native code; An ejected directory. Not defended: What `mcp-verify` does not see; What the capability ratchet does not see; What `sabline deps-diff` does not see; A tampered compiler. | partial | The capability ratchet - `check_ratchet.py`; `sabline deps-diff` - `check_deps.py`; the signed MCP tool manifest and `sabline mcp-verify` - `check_library.py` and the release workflow; `sabline.lock` and `deps --verify` - `check_library.py`, `check_self_budget.py` (sections E and F); release signing and the SBOM - the release workflow (SECURITY.md); `permissions-ratchet` - `check_permissions.py`; `sabline verify` - `check_library.py`, `check_adversarial.py` (8.3) |
| ASI05 Unexpected Code Execution | Effects are visible. Covered, as a refusal: without an `ffi` grant a Sabline program has no shell, no `eval` and no way to deserialize code (docs/structurally-impossible, 8.3); through a granted module, a call that reaches an object owned by a module outside the grants is refused (E311), and so is one whose owning module cannot be determined; `sabline eval` grants no ffi (8.3); and from 8.4 a run in a process of its own - the command line, `run(timeout=...)`, a pool, both doors, `sabline eval` - is also held by the operating system, so that a fault in the interpreter is refused by the kernel: on Linux fully (Landlock and seccomp-bpf: no file outside the grants, no socket without `net`, no new process), on macOS partly (writes, the network and new processes; reads only under the home directory), on Windows partly (no second process; no write at all under a budget that grants none; reads and the network not held), the level and its reason reported in the receipt. Not covered: `ffi:os` or `ffi:subprocess`, once granted, is a shell; output that a caller goes on to run. Known open: A granted `ffi` module; Native code; Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined; Writes to where Python imports from. Not defended: The meaning of text. | partial | The module allow-list and its walk of the attribute chain - `check_sandbox.py`, `check_adversarial.py`; docs/structurally-impossible - `check_impossible.py`; `sabline eval` - `check_eval.py` (8.3); confinement - `check_confine.py` (8.4) |
| ASI06 Memory & Context Poisoning | No guarantee. Sabline keeps no agent memory or context. The nearest thing is a different control: a pool resets a reused worker's state before the next program, and no proof result is kept between runs, which bounds what one program leaves the next, not what an agent remembers. | not addressed | none (nearest: `sabline.Pool` - `check_pool.py`; the removed proof cache - `check_adversarial.py` CACHE-1 to CACHE-10) |
| ASI07 Insecure Inter-Agent Communication | No guarantee. Sabline defines no message between agents. Its doors take programs from a caller, and are themselves not defended on the wire: the HTTP door speaks plain HTTP, and one token is one principal. Not defended: The door's token, once it is out. | not addressed | none |
| ASI08 Cascading Failures | Failure is unignorable; Promises are proven. Covered, as a refusal: a call that can fail and is neither checked nor passed up does not compile (E520); a promise the code does not keep is refused before running, or checked while running where it cannot be proven; a refused effect stops the program and cannot be caught; a run past its time or memory limit is stopped (E610, E611), and a pool replaces any worker whose run was not clean. Covered, as a record: the receipt's `exit` says how a run ended. Not covered: what the pipeline around a run does with a failed one; a function that is wrong and promises nothing; failures passed between agents. Not defended: Logic errors with no contract; The prover's reach; Resource use below the limits. | partial | Fallibility in the signature - `check_fallible.py`; the prover - `check_refusals.py`, `check_prover_lies.py`, `fuzz_native.py`; time and memory limits - `check_library.py`, `check_pool.py`; `sabline.receipt/1` - `check_library.py` |
| ASI09 Human-Agent Trust Exploitation | Effects are visible; Promises are proven. Covered, as a refusal: what a program says about itself is checked, not believed - a program that performs an effect no signature on its call graph declares does not compile, and a promise reported proven is one the prover proved. Covered, as a record: `sabline audit` gives a reviewer the effects, paths, hosts, modules, proofs and declassifications read from the text, and `sabline review` a risk word computed from those facts alone, not from anything the model wrote about the change. Not covered: what the model tells a person in prose; whether the person reads the audit; whether a declassification's stated reason is true. Not defended: The meaning of text; Where a declassified value goes; What an attestation does not say. | partial | `sabline audit` - `check_library.py`, `check_metamorphic.py`, `check_self_budget.py`; the prover - `check_prover_lies.py`; `sabline review` - `check_ratchet.py` |
| ASI10 Rogue Agents | Effects are visible. Covered, as a refusal: the budget holds whatever a program does or says, and a program cannot change what it is allowed to do or what its audit says, except through a granted `ffi` module, which can reach the runtime within its own run. Covered, as a record: the receipt of a run holds its budget, effect counts, refusals, declassifications and how it ended; `sabline receipts diff` names new hosts or paths, counts above the previous maximum and a first declassification, against the program's audit and its earlier receipts (8.3); `sabline replay` re-runs the recorded bytes under the recorded seed, clock, budget and ceilings, refuses different bytes and names any difference (8.3); both doors write one line per call. Not covered: the model's alignment; anything done outside a Sabline run; a receipt edited after it was written, unless something outside Sabline signed it. Known open: The user running sabline; What a receipt shows that is not a value; A granted `ffi` module; Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined. Not defended: What a receipt does not say; What the invocation log does not hold. | partial | The effect budget - `check_sandbox.py`; `check_self_budget.py`; `sabline.Pool` - `check_pool.py`; `sabline.receipt/1` - `check_library.py`, `check_adversarial.py` R1-R5; the invocation log - `check_library.py`; `sabline receipts diff` and `sabline replay` - `check_receipts.py` (8.3) |

## OWASP Agent Control Standard (ACS)

A document by this name exists. The OWASP GenAI Security Project published the Agent Control Standard on 2026-09-01. It is not a list of controls: it is a wire specification. An agent under observation (the Observed Agent) stops at hooks such as `toolCallRequest` and asks a Guardian Agent, which answers with one of five dispositions - allow, deny, modify, ask or defer. Conformance is a mandatory ACS-Core baseline plus six optional profiles, and in v0.1.0 every conformance claim is self-declared and checked by nobody.

ACS assigns no control identifiers. The rows below use the conformance document's own names for the ACS-Core elements and the profiles, with the section of the Instrument Specification each one points to.

Nothing in Sabline sends or answers an ACS message, so every row is not addressed. Where a Sabline mechanism does something near what an element does, the row names it, to show how far apart the two are. Being near is not conforming.

| Control | Sabline | Status | Where |
|---|---|---|---|
| ACS-Core: Handshake - handshake/hello with ClientHello/ServerHello (Instrument Specification §4 Capability Negotiation Handshake) | No guarantee. Sabline has no handshake; a door's ceilings are fixed when it starts, not negotiated with a caller. | not addressed | none |
| ACS-Core: Request/response envelope - JSON-RPC 2.0 with ACS extensions; request_id, timestamp, acs_version, metadata required on every request (§3 Wire Format) | No guarantee. The HTTP door takes JSON and the MCP server speaks MCP; neither is ACS's JSON-RPC envelope. | not addressed | none |
| ACS-Core: Hook taxonomy - At minimum sessionStart, userMessage or agentTrigger, toolCallRequest, toolCallResult, agentResponse, sessionEnd (§5 Hook Taxonomy) | Effects are visible. The nearest thing: every effect is checked against the budget at the moment it is attempted. That check is inside the runtime and asks nothing outside it. | not addressed | none (nearest: the effect budget - `check_sandbox.py`) |
| ACS-Core: Dispositions - All five (ALLOW, DENY, MODIFY, ASK, DEFER) with required fields (§6 Disposition Vocabulary) | Effects are visible. The nearest thing: the budget has two answers, carry on or stop, and a stop cannot be caught. There is no modify, ask or defer, and no Guardian gives the answer. | not addressed | none (nearest: the effect budget - `check_sandbox.py`) |
| ACS-Core: SessionContext and Intent - session_id, chain_hash (rolling SHA-256), append-only ContextEntry chain, chain head published on responses (§8 SessionContext and Intent) | No guarantee. Sabline keeps no session and no hash chain across steps; a receipt describes one run and names its program by sha256. | not addressed | none (nearest: `sabline.receipt/1` - `check_library.py`) |
| ACS-Core: Replay protection - request_id (UUID) and timestamp on every request; Guardians MUST reject replays (§10.3 Replay protection) | No guarantee. The HTTP door limits requests per token and per address, which is not replay protection. `sabline replay` (8.3) shares the word and not the purpose: it re-runs a recorded program, and rejects no repeated request. | not addressed | none |
| ACS-Core: Baseline integrity - every request and response carries a signature over the canonical envelope (HMAC-SHA256 baseline) (§10 Cryptographic Signatures) | No guarantee. Sabline signs no message, receipt or attestation; the release workflow signs Sabline's own artifacts with sigstore. Not defended: What a receipt does not say; What an attestation does not say. | not addressed | none (nearest: release signing - the release workflow) |
| ACS-Core: Decision honoring - the Observed Agent MUST wait for the Guardian's decision up to the negotiated timeout and apply it; on_decision_failure posture (default proceed), every fail-open proceed recorded (§6.4 Honoring decisions (normative)) | Effects are visible. The nearest thing: a budget refusal fails closed and cannot be caught, where ACS's default posture on a decision failure is to proceed. But Sabline has no outside decision for a run to wait on. | not addressed | none (nearest: the effect budget - `check_sandbox.py`) |
| ACS-Core: Liveness - system/ping (§13 Liveness / System Methods) | No guarantee. The HTTP door answers `GET /health`; that is not `system/ping`. | not addressed | none |
| ACS-Core: Wrapped MCP - protocols/MCP/* (Hooks: protocols/MCP) | No guarantee. Sabline runs an MCP server; it does not wrap MCP traffic in ACS hooks. | not addressed | none |
| ACS-Trace - OTel + OCSF event emission per step (Trace Events) | No guarantee. Sabline emits no OpenTelemetry spans or OCSF events; its records are the receipt and the invocation log, in formats of its own. | not addressed | none (nearest: the invocation log and `sabline.receipt/1` - `check_library.py`) |
| ACS-Inspect - agbom/snapshot + canonical AgBOM serialization (Inspect) | No guarantee. Sabline produces no AgBOM. `sabline attest` states what one program may do, and each release carries a CycloneDX SBOM of Sabline itself; neither is an inventory of an agent's models, tools and dependencies. | not addressed | none (nearest: `sabline attest` - `check_library.py`) |
| ACS-Inspect-Dynamic - agbom/changed on mutation (Inspect) | No guarantee. Nothing in Sabline reports a component changing during a session. | not addressed | none |
| ACS-Provenance - Field-level Provenance objects (§7 Provenance) | Secrets cannot be printed, or looked at. The nearest thing: a `Secret` keeps where it came from through every operation, at compile time, for two builtins' results. ACS-Provenance asks for a provenance object on every data-bearing field on the wire. | not addressed | none (nearest: `Secret of T` - `check_secret.py`) |
| ACS-Crypto - ML-DSA-65 / SLH-DSA-128s signatures (§10 Cryptographic Signatures) | No guarantee. Sabline signs nothing with ML-DSA-65 or SLH-DSA-128s. | not addressed | none |
| ACS-Audit - request_hash on every ContextEntry (ACS-Audit) | No guarantee. Sabline has no ContextEntry chain for a `request_hash` to go in; the invocation log's `source_sha256` is a digest of a program's text, not of an ACS request. | not addressed | none (nearest: the invocation log - `check_library.py`) |

## AIUC-1

The identifiers and titles are AIUC-1's, from its release of 2026-07-15. AIUC-1 marks E007 and E014 retired; they keep their rows.

| Control | Sabline | Status | Where |
|---|---|---|---|
| A001 Establish input data policy | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| A002 Establish output data policy | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| A003 Limit AI agent data access | Effects are visible. Covered, as a refusal: a program reads and writes only under its `fs:` grants, resolved with realpath so `..` and symbolic links cannot leave them, reaches only granted hosts and ports, reads the environment only with `env`, and does each at most `@N` times. Not covered: access by user role, agent role or context - a budget belongs to a run or a pool, and the door cannot tell token holders apart; and whatever a granted directory or host holds. Known open: A granted `ffi` module. Not defended: What a granted path contains; A pool worker's budget, once chosen. | partial | Scoped fs and net grants, counts, `env` as its own effect - `check_sandbox.py`, `check_library.py` |
| A004 Protect IP & trade secrets | No guarantee. Nothing in Sabline knows which data is intellectual property or a trade secret. A file read with `read_file_secret()` is protected as any `Secret` is, which is A008's row, so the weaker word here. | not addressed | none |
| A005 Prevent cross-customer data exposure | Effects are visible. Covered, as a refusal: a pool fixes its budget when it is made, re-asserts it before every program, replaces a worker unless its run was clean and resets a reused worker's state; the doors hold a request's imports to the directory they serve (E515); the reference platform's pool refuses an effect it does not grant, even to a script put in its store past the gate. Not covered: two customers handed one pool share one budget, and whatever both can reach on disk; the door cannot tell two token holders apart. Known open: A granted `ffi` module. Not defended: A pool worker's budget, once chosen; The door's token, once it is out. | partial | `sabline.Pool` - `check_pool.py`; the import root - `check_library.py`, `check_adversarial.py` I1, I2; examples/platform - `check_platform.py` |
| A006 Prevent PII leakage | Secrets cannot be printed, or looked at. Covered, as a refusal: a value from `read_file_secret()` or `env()` cannot be printed, written, sent or handed to Python. Kept out of Sabline's own records: a receipt and the invocation log hold no value a program handled. Not covered: nothing detects personal data, and personal data read any other way is ordinary text a program may print. Known open: Secrets arriving another way; What a receipt shows that is not a value; Timing and other side channels. | partial | `Secret of T` - `check_secret.py`; `sabline.receipt/1` and the invocation log - `check_library.py` |
| A007 Prevent IP violations | No guarantee. Whether an output infringes is a question about what text means, which Sabline does not ask. Not defended: The meaning of text. | not addressed | none |
| A008 Prevent leakage of credentials and secrets | Secrets cannot be printed, or looked at. Covered, as a refusal: a value from `env()` or `read_file_secret()` cannot be printed, written, sent, handed to Python, put in a failure's reason or branched on (E560, E563), and `declassify` needs the effect, the grant and a reason written in the call; the HTTP door never takes its token as an argument and removes it from its workers' environment. Covered, as a record: the audit's `secrets` section lists each declassification and its reason, and the token is struck from every log line. Not covered: a secret in a user's input or a model's prompt; a credential hard-coded in generated source; credential storage. Known open: Secrets arriving another way; What a receipt shows that is not a value; Timing and other side channels. Not defended: Where a declassified value goes; What a granted `ffi` module reads for itself. | partial | `Secret of T` - `check_secret.py`, `check_refusals.py`, `check_sandbox.py`; the bearer token - `check_library.py` |
| B001 Third-party testing of adversarial robustness | No guarantee. Commissioning a third party to test a system is an organisation's act. Sabline's own adversarial suites test Sabline, not the system it runs in. | not addressed | none |
| B002 Detect adversarial input | No guarantee. Sabline reads programs, not what a model is given. The check ceiling stops source written to stall the checker (E613, E614); that is hostile code, not adversarial input. Not defended: The meaning of text. | not addressed | none (nearest: the check ceiling - `check_library.py`) |
| B003 Manage public release of technical details | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| B004 Prevent AI endpoint scraping | No guarantee. The HTTP door allows at most `--rate-limit` requests a minute per token and per address, but the door runs programs and is not a model endpoint, so the weaker word. | not addressed | none (nearest: the rate limit - `check_library.py`, `check_adversarial.py` D1) |
| B005 Implement real-time input filtering | No guarantee. Sabline filters no input to a model. Not defended: The meaning of text. | not addressed | none |
| B006 Prevent unauthorized AI agent actions | Effects are visible. Covered, as a refusal: an action outside the operator's budget - an effect, path, host, port, module or count - is refused when it is attempted and cannot be caught; a door refuses a request for more than its ceilings; `sabline eval` grants no net and no ffi and holds hard time and memory ceilings (8.3); from 8.4 the operating system holds the same budget under the interpreter - fully on Linux, partly on macOS and on Windows - and `sabline eval` refuses to run where it holds none of it. Not covered: an action inside a grant that is still outside what was intended; a granted `ffi` module, which can reach the runtime itself. Known open: A granted `ffi` module; Native code; Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined; Writes to where Python imports from. Not defended: Rate, and the meaning of a request. | partial | The effect budget, scoped grants and counts - `check_sandbox.py`, `check_library.py`; `--max-allow` - `check_library.py`; `check_self_budget.py`; `sabline eval` - `check_eval.py` (8.3) |
| B007 Enforce user access privileges to AI systems | No guarantee. Covered, as a refusal: the HTTP door refuses every caller without its bearer token, with the same 401 on every path, refuses `--no-auth` on any address but loopback, and holds every holder of the token to its ceilings. Not covered: user accounts, roles and admin privileges; revoking one holder; access reviews; who an MCP client lets call the MCP server. Not defended: The door's token, once it is out; `--no-auth`; The MCP server's caller. | partial | The bearer token and `--max-allow` - `check_library.py` |
| B008 Protect AI system deployment environment | No guarantee. Covered: each Sabline release is signed, carries an SBOM and has its wheel built twice and compared, so a person can check what they install; the door's token stays out of arguments, logs and workers' environment; from 8.4 each worker of a door or a pool asks the operating system to hold its budget (full on Linux, partial on macOS and on Windows), and `sabline doctor` says what the machine offers. Not covered: encryption - the HTTP door speaks plain HTTP - and the host, its accounts and its network. Known open: Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined; The user running sabline; An ejected directory; The fault-injection hook. Not defended: A tampered compiler. | partial | Release signing, the SBOM and the double build - the release workflow (SECURITY.md); the bearer token - `check_library.py` |
| B009 Limit output over-exposure | No guarantee. The requirement is about what a model's outputs reveal. Sabline keeps values out of its own receipts and logs, and from 8.1 an import error shows nothing of the file it read; that limits Sabline's output, not the model's, so the weaker word. Known open: What a receipt shows that is not a value. | not addressed | none (nearest: `sabline.receipt/1` and the import root - `check_library.py`) |
| B010 Promote secure patterns in generated code | Effects are visible; Failure is unignorable; Secrets cannot be printed, or looked at; Promises are proven. Covered, as a refusal, for generated Sabline: no shell, no `eval` and no deserialization of code without an `ffi` grant (8.3); a failure cannot be ignored (E520); a secret cannot be printed; a promise the code does not keep is refused; a run given no budget gets `io`. Covered in the standard library: log builtins escape CR, LF, ESC and NUL, and `csv.vel` quotes fields as RFC 4180 does (8.3). Not covered: patterns for authentication and transport security; generated code in any other language. Not defended: Logic errors with no contract. | partial | docs/structurally-impossible and log escaping - `check_impossible.py`; `csv.vel` quoting - `check_properties.py` (8.3); `check_fallible.py`; `check_secret.py`; `check_refusals.py`; the default budget - `check_sandbox.py` |
| C001 Define AI risk taxonomy | No guarantee. THREAT_MODEL.md is Sabline's account of its own risks, not an organisation's taxonomy. | not addressed | none |
| C002 Conduct pre-deployment testing | Promises are proven; Failure is unignorable. Covered: before a program runs, `sabline check` refuses one that does not compile or breaks a promise, `sabline audit` reports what it can do, `sabline test --from-contracts` generates inputs that meet `requires` with Z3 and checks `ensures` while running (8.3), and the GitHub Action fails the job on anything that does not compile or a promise that cannot be kept. Not covered: testing the model and the agent across risk categories, under a review an organisation runs; Sabline checks one kind of artifact inside that activity, so partial and no more. Known open: A program that stalls a review. Not defended: Logic errors with no contract; The prover's reach. | partial | The prover - `check_refusals.py`, `check_prover_lies.py`; `sabline audit` - `check_library.py`; the GitHub Action (EMBEDDING.md); `sabline test --from-contracts` - `check_from_contracts.py` (8.3) |
| C003 Prevent harmful outputs | No guarantee. Whether an output is harmful is a question about what text means. Not defended: The meaning of text. | not addressed | none |
| C004 Prevent out-of-scope outputs | No guarantee. Whether an output is out of scope is a question about what text means. Not defended: The meaning of text. | not addressed | none |
| C005 Prevent agent-specific high risk outputs | No guarantee. The outputs are defined by each agent's risk taxonomy, which Sabline does not read; an action a Sabline program takes is B006's row. Not defended: The meaning of text. | not addressed | none |
| C006 Prevent output vulnerabilities | Effects are visible. Covered, as a refusal: generated Sabline code runs only inside the budget, so code that would exfiltrate or inject beyond it is refused; log builtins escape CR, LF, ESC and NUL, and `csv.vel` quotes fields (8.3). Not covered: what a consumer does with a program's output - THREAT_MODEL.md says never to pipe it into a shell - text that harms as words, and labelling untrusted content. Not defended: The meaning of text. | partial | The effect budget - `check_sandbox.py`; log escaping - `check_impossible.py`; `csv.vel` quoting - `check_properties.py` (8.3) |
| C007 Flag high risk outputs for human review | Effects are visible. Covered, as a record: where the output is a program, `sabline review` reports a risk word computed from capability facts, the Action posts it on the pull request, and `sabline receipts diff` names a run's new hosts or paths, higher counts and first declassification (8.3). Not covered: outputs that are text; flagging by the organisation's own risk taxonomy; holding anything for a person - the review stops no merge (the ratchet does, in ASI04's row). Known open: A program that stalls a review. | partial | `sabline review` - `check_ratchet.py`; the Action's pull-request comment (EMBEDDING.md); `sabline receipts diff` - `check_receipts.py` (8.3) |
| C008 Monitor AI risk categories | No guarantee. The categories are content risks, which Sabline does not monitor. | not addressed | none |
| C009 Enable real-time feedback and intervention | No guarantee. A run can be stopped from outside, as any process can, and `sabline eval` records that it was (8.3); nothing collects a user's feedback or lets a user intervene, so the weaker word. | not addressed | none (nearest: `sabline eval` - `check_eval.py`, 8.3) |
| C010 Third-party testing for harmful outputs | No guarantee. Third-party testing is an organisation's act. | not addressed | none |
| C011 Third-party testing for out-of-scope outputs | No guarantee. Third-party testing is an organisation's act. | not addressed | none |
| C012 Third-party testing for customer-defined risk | No guarantee. Third-party testing is an organisation's act. | not addressed | none |
| D001 Prevent hallucinated outputs | No guarantee. A proven `ensures` bounds what a function returns, not what a model says. | not addressed | none |
| D002 Third-party testing for hallucinations | No guarantee. Third-party testing is an organisation's act. | not addressed | none |
| D003 Restrict unsafe tool calls | Effects are visible. Covered, as a refusal: a call that reaches an effect, path, host, port, module or count outside the program's grants is refused and cannot be caught; a door refuses a tool call that asks for more than its ceilings. Not covered: a call inside its grants that is still unsafe - a request's method or size, a decision beyond the task; a granted `ffi` module. Known open: A granted `ffi` module; Native code; Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined. Not defended: Rate, and the meaning of a request. | partial | The effect budget, the module allow-list, scoped grants and counts - `check_sandbox.py`; `--max-allow` - `check_library.py` |
| D004 Third-party testing of tool calls | No guarantee. Third-party testing is an organisation's act. | not addressed | none |
| E001 AI failure plan for security breaches | No guarantee. Organisational; a language cannot do it. SECURITY.md is Sabline's own process for a broken guarantee, not a failure plan for the system. | not addressed | none |
| E002 AI failure plan for harmful outputs | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E003 AI failure plan for hallucinations | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E004 Assign accountability | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E005 Document data storage security | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E006 Conduct vendor due diligence | No guarantee. Organisational; a language cannot do it. What Sabline publishes about itself - signatures, the SBOM, THREAT_MODEL.md and SECURITY.md - is material for due diligence on Sabline. | not addressed | none |
| E007 [Retired] Document system change approvals | No guarantee. Organisational; a language cannot do it. Retired by AIUC-1. An edit to `sabline.capabilities` puts a widening in a diff a person approves; the approval is the person's. | not addressed | none |
| E008 Review internal processes | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E009 Monitor third-party access | Effects are visible. Covered, as a refusal: a program reaches only granted hosts and ports, at most `@N` times. Covered, as a record: the receipt counts a run's network operations and lists its refusals by code, effect and line; each door's log line holds the budget granted, the effects performed and what was refused, naming the host. Not covered: which granted host a run reached and what it sent; sessions; alerting; third parties' access to the organisation's own systems. Not defended: What a granted host does with a request; What the invocation log does not hold. | partial | Scoped net grants and counts - `check_sandbox.py`; `sabline.receipt/1` and the invocation log - `check_library.py` |
| E010 Establish AI acceptable use policy | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E011 Record processing locations | No guarantee. A receipt names no processing location, and nothing else in Sabline records one. | not addressed | none |
| E012 Document regulatory compliance | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E013 Implement quality management system | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| E014 [Retired] Share transparency reports | No guarantee. Organisational; a language cannot do it. Retired by AIUC-1. | not addressed | none |
| E015 Log AI system activity | Effects are visible; Secrets cannot be printed, or looked at. Covered, as a record: `run()` and `Pool.run()` return a receipt of every run - the program by digest, the budget, effect counts, refusals, declassifications and how it ended, marked incomplete when the run was killed; `sabline eval` requires one and writes it outside the budget or streams it to a URL (8.3); both doors write one line per call, which no setting turns off. Not covered: agent outputs, which a receipt holds none of by design; keeping and protecting the logs; activity outside Sabline runs; a command-line run writes a receipt only with `--receipt`, and none when it is killed from outside. Known open: The user running sabline; What a receipt shows that is not a value. Not defended: What a receipt does not say; What the invocation log does not hold. | partial | `sabline.receipt/1` - `check_library.py`, `check_adversarial.py` R1-R5; the invocation log - `check_library.py`; `sabline eval` - `check_eval.py` (8.3) |
| E016 Implement AI disclosure mechanisms | No guarantee. Sabline tells no user they are dealing with an AI system. | not addressed | none |
| E017 Document system transparency policy | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| F001 Prevent AI cyber misuse | Effects are visible. Covered, as a refusal: a Sabline program an agent writes cannot reach a host, port, path or module outside the operator's grants, so a program meant as an attack is bounded by them. Not covered: a plain `net` grant is any host; misuse through text, or through code in another language; the content guardrails the requirement has in mind. Known open: A granted `ffi` module; Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined. Not defended: Rate, and the meaning of a request; The meaning of text. | partial | Scoped net grants and the module allow-list - `check_sandbox.py` |
| F002 Prevent catastrophic misuse | No guarantee. Nothing in Sabline addresses catastrophic misuse. | not addressed | none |

## NIST AI RMF 1.0

All 72 subcategories, with NIST's text. NIST writes outcomes for an organisation. A subcategory whose outcome is a policy, process, practice, plan, role, training or consultation is not addressed, and says so. A subcategory whose outcome is a property of the AI system or of its documentation is judged on what Sabline supplies for its own part of the system.

| Control | Sabline | Status | Where |
|---|---|---|---|
| GOVERN 1.1 Legal and regulatory requirements involving AI are understood, managed, and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 1.2 The characteristics of trustworthy AI are integrated into organizational policies, processes, procedures, and practices. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 1.3 Processes, procedures, and practices are in place to determine the needed level of risk management activities based on the organization's risk tolerance. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 1.4 The risk management process and its outcomes are established through transparent policies, procedures, and other controls based on organizational risk priorities. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 1.5 Ongoing monitoring and periodic review of the risk management process and its outcomes are planned and organizational roles and responsibilities clearly defined, including determining the frequency of periodic review. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 1.6 Mechanisms are in place to inventory AI systems and are resourced according to organizational risk priorities. | No guarantee. Organisational; a language cannot do it. `sabline.capabilities` records the capability surface of one repository's programs, which is not an inventory of AI systems. | not addressed | none |
| GOVERN 1.7 Processes and procedures are in place for decommissioning and phasing out AI systems safely and in a manner that does not increase risks or decrease the organization’s trustworthiness. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 2.1 Roles and responsibilities and lines of communication related to mapping, measuring, and managing AI risks are documented and are clear to individuals and teams throughout the organization. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 2.2 The organization’s personnel and partners receive AI risk management training to enable them to perform their duties and responsibilities consistent with related policies, procedures, and agreements. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 2.3 Executive leadership of the organization takes responsibility for decisions about risks associated with AI system development and deployment. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 3.1 Decision-making related to mapping, measuring, and managing AI risks throughout the lifecycle is informed by a diverse team (e.g., diversity of demographics, disciplines, experience, expertise, and backgrounds). | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 3.2 Policies and procedures are in place to define and differentiate roles and responsibilities for human-AI configurations and oversight of AI systems. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 4.1 Organizational policies and practices are in place to foster a critical thinking and safety-first mindset in the design, development, deployment, and uses of AI systems to minimize potential negative impacts. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 4.2 Organizational teams document the risks and potential impacts of the AI technology they design, develop, deploy, evaluate, and use, and they communicate about the impacts more broadly. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 4.3 Organizational practices are in place to enable AI testing, identification of incidents, and information sharing. | No guarantee. Organisational; a language cannot do it. Receipts, the invocation log and SECURITY.md's private reporting channel are inputs to such practices, not the practices. | not addressed | none |
| GOVERN 5.1 Organizational policies and practices are in place to collect, consider, prioritize, and integrate feedback from those external to the team that developed or deployed the AI system regarding the potential individual and societal impacts related to AI risks. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 5.2 Mechanisms are established to enable the team that developed or deployed AI systems to regularly incorporate adjudicated feedback from relevant AI actors into system design and implementation. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| GOVERN 6.1 Policies and procedures are in place that address AI risks associated with third-party entities, including risks of infringement of a third-party’s intellectual property or other rights. | No guarantee. Organisational; a language cannot do it. `sabline deps-diff` reports what a third-party Sabline library gained; the policy is the organisation's. | not addressed | none |
| GOVERN 6.2 Contingency processes are in place to handle failures or incidents in third-party data or AI systems deemed to be high-risk. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 1.1 Intended purposes, potentially beneficial uses, context-specific laws, norms and expectations, and prospective settings in which the AI system will be deployed are understood and documented. Considerations include: the specific set or types of users along with their expectations; potential positive and negative impacts of system uses to individuals, communities, organizations, society, and the planet; assumptions and related limitations about AI system purposes, uses, and risks across the development or product AI lifecycle; and related TEVV and system metrics. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 1.2 Interdisciplinary AI actors, competencies, skills, and capacities for establishing context reflect demographic diversity and broad domain and user experience expertise, and their participation is documented. Opportunities for interdisciplinary collaboration are prioritized. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 1.3 The organization’s mission and relevant goals for AI technology are understood and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 1.4 The business value or context of business use has been clearly defined or – in the case of assessing existing AI systems – re-evaluated. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 1.5 Organizational risk tolerances are determined and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 1.6 System requirements (e.g., “the system shall respect the privacy of its users”) are elicited from and understood by relevant AI actors. Design decisions take socio-technical implications into account to address AI risks. | No guarantee. Organisational; a language cannot do it. Once a capability requirement is written down, `sabline.capabilities` can hold code to it (ASI04's row); eliciting it is not Sabline's. | not addressed | none |
| MAP 2.1 The specific tasks and methods used to implement the tasks that the AI system will support are defined (e.g., classifiers, generative models, recommenders). | No guarantee. Organisational; a language cannot do it. A budget writes down what a task may touch; defining the task is not Sabline's. | not addressed | none |
| MAP 2.2 Information about the AI system’s knowledge limits and how system output may be utilized and overseen by humans is documented. Documentation provides sufficient information to assist relevant AI actors when making decisions and taking subsequent actions. | No guarantee. It asks for the model's knowledge limits and how its output is overseen; Sabline documents neither. | not addressed | none |
| MAP 2.3 Scientific integrity and TEVV considerations are identified and documented, including those related to experimental design, data collection and selection (e.g., availability, representativeness, suitability), system trustworthiness, and construct validation. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 3.1 Potential benefits of intended AI system functionality and performance are examined and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 3.2 Potential costs, including non-monetary costs, which result from expected or realized AI errors or system functionality and trustworthiness – as connected to organizational risk tolerance – are examined and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 3.3 Targeted application scope is specified and documented based on the system’s capability, established context, and AI system categorization. | No guarantee. Organisational; a language cannot do it. `sabline.capabilities` records what code may reach, not an application's scope. | not addressed | none |
| MAP 3.4 Processes for operator and practitioner proficiency with AI system performance and trustworthiness – and relevant technical standards and certifications – are defined, assessed, and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 3.5 Processes for human oversight are defined, assessed, and documented in accordance with organizational policies from the govern function. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 4.1 Approaches for mapping AI technology and legal risks of its components – including the use of third-party data or software – are in place, followed, and documented, as are risks of infringement of a third party’s intellectual property or other rights. | No guarantee. Organisational; a language cannot do it. The audit's `ffi_modules` and `ffi_native`, `sabline deps-diff` and `sabline.lock` report the third-party software a Sabline program reaches; none of them maps legal or intellectual-property risk. | not addressed | none |
| MAP 4.2 Internal risk controls for components of the AI system, including third-party AI technologies, are identified and documented. | Effects are visible. Covered: Sabline documents its own controls and what each does not cover, each claim naming the suite that tests it (THREAT_MODEL.md), and `sabline audit` and `sabline attest` document what one program may do. Not covered: the controls of every other component, third-party AI technologies among them. | partial | THREAT_MODEL.md; `sabline audit` and `sabline attest` - `check_library.py` |
| MAP 5.1 Likelihood and magnitude of each identified impact (both potentially beneficial and harmful) based on expected use, past uses of AI systems in similar contexts, public incident reports, feedback from those external to the team that developed or deployed the AI system, or other data are identified and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MAP 5.2 Practices and personnel for supporting regular engagement with relevant AI actors and integrating feedback about positive, negative, and unanticipated impacts are in place and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 1.1 Approaches and metrics for measurement of AI risks enumerated during the map function are selected for implementation starting with the most significant AI risks. The risks or trustworthiness characteristics that will not – or cannot – be measured are properly documented. | No guarantee. Covered: what Sabline does not measure or bound is written down - THREAT_MODEL.md's list of what it does not defend against, and its Known open table. Not covered: selecting approaches and metrics, which is organisational. | partial | THREAT_MODEL.md |
| MEASURE 1.2 Appropriateness of AI metrics and effectiveness of existing controls are regularly assessed and updated, including reports of errors and potential impacts on affected communities. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 1.3 Internal experts who did not serve as front-line developers for the system and/or independent assessors are involved in regular assessments and updates. Domain experts, users, AI actors external to the team that developed or deployed the AI system, and affected communities are consulted in support of assessments as necessary per organizational risk tolerance. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 2.1 Test sets, metrics, and details about the tools used during TEVV are documented. | No guarantee. Covered, as a record: a receipt holds the parameters a run had - seed, frozen clock, budget, time and memory ceilings - and under `sabline eval` the confinement level (8.3); `sabline replay` re-runs a recorded run under them (8.3). Not covered: the test sets and the metrics, which are the organisation's. | partial | `sabline.receipt/1` - `check_library.py`; `sabline eval` - `check_eval.py`; `sabline replay` - `check_receipts.py` (8.3) |
| MEASURE 2.2 Evaluations involving human subjects meet applicable requirements (including human subject protection) and are representative of the relevant population. | No guarantee. Sabline runs no evaluation with human subjects. | not addressed | none |
| MEASURE 2.3 AI system performance or assurance criteria are measured qualitatively or quantitatively and demonstrated for conditions similar to deployment setting(s). Measures are documented. | Promises are proven. Covered: a function's `requires`, `ensures` and `invariant` are proven by Z3 before it runs, with a counterexample when one is false, or checked while it runs where they cannot be proven; `sabline test --from-contracts` generates inputs that meet `requires` and checks `ensures` while running (8.3). Not covered: the model's performance; a function with no contract; any condition of deployment a contract does not state. Not defended: Logic errors with no contract; The prover's reach. | partial | The prover - `check_refusals.py`, `check_prover_lies.py`; `sabline test --from-contracts` - `check_from_contracts.py` (8.3) |
| MEASURE 2.4 The functionality and behavior of the AI system and its components – as identified in the map function – are monitored when in production. | Effects are visible. Covered, as a record: a receipt of every library and pool run, one line per call on both doors, and `sabline receipts diff` against the program's audit and its earlier receipts (8.3). Not covered: watching those records, which is organisational; the model and every other component. Known open: The user running sabline. | partial | `sabline.receipt/1` and the invocation log - `check_library.py`; `sabline receipts diff` - `check_receipts.py` (8.3) |
| MEASURE 2.5 The AI system to be deployed is demonstrated to be valid and reliable. Limitations of the generalizability beyond the conditions under which the technology was developed are documented. | Promises are proven; Failure is unignorable. Covered: proven promises, failures that must be handled, and native code held equal to the interpreter by differential testing; Sabline's own limits are written down (THREAT_MODEL.md, benchmark/RESULTS.md). Not covered: the model's validity and reliability; a function that promises nothing. Not defended: Logic errors with no contract; The prover's reach. | partial | The prover - `check_refusals.py`, `check_prover_lies.py`; `fuzz_native.py`; `check_fallible.py`; benchmark/RESULTS.md |
| MEASURE 2.6 The AI system is evaluated regularly for safety risks – as identified in the map function. The AI system to be deployed is demonstrated to be safe, its residual negative risk does not exceed the risk tolerance, and it can fail safely, particularly if made to operate beyond its knowledge limits. Safety metrics reflect system reliability and robustness, real-time monitoring, and response times for AI system failures. | Failure is unignorable; Promises are proven. Covered, as a refusal: a program fails safely in the sense a runtime can give - a refused effect stops it and cannot be caught, a failure cannot be ignored, a run past its time or memory limit is stopped, and a pool worker whose run was not clean is replaced. Not covered: regular safety evaluation, real-time monitoring and response times, which are organisational; the memory cap on macOS, which is best-effort. Not defended: Memory caps on macOS. | partial | The effect budget - `check_sandbox.py`; `check_fallible.py`; time and memory limits - `check_library.py`, `check_pool.py`; `check_hostile.py` |
| MEASURE 2.7 AI system security and resilience – as identified in the map function – are evaluated and documented. | Effects are visible. Covered: Sabline's own security is evaluated and written down - THREAT_MODEL.md names the suite behind each claim, the benchmark compares it with Deno and plain Python, and `sabline conformance` runs sabline-spec's corpus - and `sabline audit` documents one program's surface. Not covered: the security and resilience of the system Sabline runs in, and the evaluation activity itself. Known open: A granted `ffi` module; Confinement on Linux: what it leaves; Confinement on macOS: partial; Confinement on Windows: partial; Runs that are not confined; A program that stalls a review. | partial | THREAT_MODEL.md; benchmark/RESULTS.md; `sabline conformance`; `sabline audit` - `check_library.py` |
| MEASURE 2.8 Risks associated with transparency and accountability – as identified in the map function – are examined and documented. | Effects are visible. Covered: the audit, the attestation, the receipt and the invocation log make a program and its runs checkable, and THREAT_MODEL.md writes down what each does not say. Not covered: examining the transparency and accountability risks of the system, which is organisational. Not defended: What an attestation does not say; What a receipt does not say; What the invocation log does not hold. | partial | `sabline audit`, `sabline attest`, `sabline.receipt/1` and the invocation log - `check_library.py`; THREAT_MODEL.md |
| MEASURE 2.9 The AI model is explained, validated, and documented, and AI system output is interpreted within its context – as identified in the map function – to inform responsible use and governance. | No guarantee. It asks for the model to be explained; Sabline explains programs, not models. | not addressed | none |
| MEASURE 2.10 Privacy risk of the AI system – as identified in the map function – is examined and documented. | No guarantee. `Secret of T` covers values from two builtins, meant for credentials; nothing in Sabline examines or documents privacy risk to people (AIUC-1 A006's row), so the weaker word. Known open: Secrets arriving another way; Timing and other side channels. | not addressed | none |
| MEASURE 2.11 Fairness and bias – as identified in the map function – are evaluated and results are documented. | No guarantee. Nothing in Sabline evaluates fairness or bias. | not addressed | none |
| MEASURE 2.12 Environmental impact and sustainability of AI model training and management activities – as identified in the map function – are assessed and documented. | No guarantee. Nothing in Sabline assesses environmental impact. | not addressed | none |
| MEASURE 2.13 Effectiveness of the employed TEVV metrics and processes in the measure function are evaluated and documented. | No guarantee. Organisational; a language cannot do it. Sabline's suites test Sabline; they are not the organisation's TEVV. | not addressed | none |
| MEASURE 3.1 Approaches, personnel, and documentation are in place to regularly identify and track existing, unanticipated, and emergent AI risks based on factors such as intended and actual performance in deployed contexts. | No guarantee. Organisational; a language cannot do it. `sabline receipts diff` - `check_receipts.py` (8.3) compares a run with its audit and with earlier runs, a record such an approach can use. | not addressed | none |
| MEASURE 3.2 Risk tracking approaches are considered for settings where AI risks are difficult to assess using currently available measurement techniques or where metrics are not yet available. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 3.3 Feedback processes for end users and impacted communities to report problems and appeal system outcomes are established and integrated into AI system evaluation metrics. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 4.1 Measurement approaches for identifying AI risks are connected to deployment context(s) and informed through consultation with domain experts and other end users. Approaches are documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 4.2 Measurement results regarding AI system trustworthiness in deployment context(s) and across the AI lifecycle are informed by input from domain experts and relevant AI actors to validate whether the system is performing consistently as intended. Results are documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MEASURE 4.3 Measurable performance improvements or declines based on consultations with relevant AI actors, including affected communities, and field data about context-relevant risks and trustworthiness characteristics are identified and documented. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 1.1 A determination is made as to whether the AI system achieves its intended purposes and stated objectives and whether its development or deployment should proceed. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 1.2 Treatment of documented AI risks is prioritized based on impact, likelihood, and available resources or methods. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 1.3 Responses to the AI risks deemed high priority, as identified by the map function, are developed, planned, and documented. Risk response options can include mitigating, transferring, avoiding, or accepting. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 1.4 Negative residual risks (defined as the sum of all unmitigated risks) to both downstream acquirers of AI systems and end users are documented. | No guarantee. Covered: Sabline's own residual risks are written down - THREAT_MODEL.md's Known open and residual-risk tables, each with what to do. Not covered: the residual risks of the system Sabline is part of. | partial | THREAT_MODEL.md |
| MANAGE 2.1 Resources required to manage AI risks are taken into account – along with viable non-AI alternative systems, approaches, or methods – to reduce the magnitude or likelihood of potential impacts. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 2.2 Mechanisms are in place and applied to sustain the value of deployed AI systems. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 2.3 Procedures are followed to respond to and recover from a previously unknown risk when it is identified. | No guarantee. Organisational; a language cannot do it. SECURITY.md is Sabline's procedure for a broken guarantee of its own, not the system's. | not addressed | none |
| MANAGE 2.4 Mechanisms are in place and applied, and responsibilities are assigned and understood, to supersede, disengage, or deactivate AI systems that demonstrate performance or outcomes inconsistent with intended use. | Effects are visible. Covered, as a refusal: a program that reaches outside its budget is stopped and cannot carry on; a run past its time or memory limit is killed; closing a pool kills every worker; `sabline eval` records whether a run stopped itself or was stopped from outside (8.3). Not covered: assigning the responsibility; deciding, beyond the budget, what is inconsistent with intended use; deactivating the model or the agent. | partial | The effect budget - `check_sandbox.py`; time and memory limits and closing a pool - `check_library.py`, `check_pool.py`; `sabline eval` - `check_eval.py` (8.3) |
| MANAGE 3.1 AI risks and benefits from third-party resources are regularly monitored, and risk controls are applied and documented. | Effects are visible. Covered, as a refusal: `sabline capabilities check` fails code that needs more than the repository declares, and `sabline deps --verify` a vendored library that changed. Covered, as a record: `sabline deps-diff` on each upgrade, `sabline mcp-verify` against the signed manifest, and the audit's `ffi_native` for a granted module that ships compiled code. Not covered: the regular monitoring itself; models and data; what a package that is not Sabline does. Known open: A granted `ffi` module; Native code; An ejected directory. Not defended: What `sabline deps-diff` does not see. | partial | The capability ratchet - `check_ratchet.py`; `sabline deps-diff` - `check_deps.py`; `sabline mcp-verify` - `check_library.py`; `sabline.lock` and `deps --verify` - `check_library.py`, `check_self_budget.py` (sections E and F) |
| MANAGE 3.2 Pre-trained models which are used for development are monitored as part of AI system regular monitoring and maintenance. | No guarantee. Sabline monitors no pre-trained model. | not addressed | none |
| MANAGE 4.1 Post-deployment AI system monitoring plans are implemented, including mechanisms for capturing and evaluating input from users and other relevant AI actors, appeal and override, decommissioning, incident response, recovery, and change management. | No guarantee. Organisational; a language cannot do it. Receipts, the invocation log and the capability ratchet are records and a check such a plan can use. | not addressed | none |
| MANAGE 4.2 Measurable activities for continual improvements are integrated into AI system updates and include regular engagement with interested parties, including relevant AI actors. | No guarantee. Organisational; a language cannot do it. | not addressed | none |
| MANAGE 4.3 Incidents and errors are communicated to relevant AI actors, including affected communities. Processes for tracking, responding to, and recovering from incidents and errors are followed and documented. | No guarantee. Organisational; a language cannot do it. SECURITY.md's advisories communicate Sabline's own defects, not the system's incidents. | not addressed | none |

## Every guarantee, and where it lands

The five guarantees in the README's "Why Sabline" table. SECURITY.md's Goal A, Soundness, is what "Promises are proven" promises, and Goal B, Honesty, is "Effects are visible" as a declaration. Goal C, Confinement - the budget that holds whatever a program declares - has no row of its own in the README's table, so the rows that rest on the effect budget are listed under "Effects are visible", the guarantee the budget makes true at run time.

### Effects are visible

- OWASP Agentic Top 10: ASI02 (partial), ASI03 (partial), ASI04 (partial), ASI05 (partial), ASI09 (partial), ASI10 (partial)
- OWASP ACS: ACS-Core: Hook taxonomy (not addressed), ACS-Core: Dispositions (not addressed), ACS-Core: Decision honoring (not addressed)
- AIUC-1: A003 (partial), A005 (partial), B006 (partial), B010 (partial), C006 (partial), C007 (partial), D003 (partial), E009 (partial), E015 (partial), F001 (partial)
- NIST AI RMF: MAP 4.2 (partial), MEASURE 2.4 (partial), MEASURE 2.7 (partial), MEASURE 2.8 (partial), MANAGE 2.4 (partial), MANAGE 3.1 (partial)

### Promises are proven

- OWASP Agentic Top 10: ASI08 (partial), ASI09 (partial)
- AIUC-1: B010 (partial), C002 (partial)
- NIST AI RMF: MEASURE 2.3 (partial), MEASURE 2.5 (partial), MEASURE 2.6 (partial)

### Failure is unignorable

- OWASP Agentic Top 10: ASI08 (partial)
- AIUC-1: B010 (partial), C002 (partial)
- NIST AI RMF: MEASURE 2.5 (partial), MEASURE 2.6 (partial)

### Secrets cannot be printed, or looked at

- OWASP Agentic Top 10: ASI03 (partial)
- OWASP ACS: ACS-Provenance (not addressed)
- AIUC-1: A006 (partial), A008 (partial), B010 (partial), E015 (partial)

### Fast where it's safe

No control in these four frameworks names this. Native code is inside the guard rather than a control of its own: `fuzz_native.py` holds native and interpreted runs to the same results, and several of SECURITY.md's resolved advisories were false promises that went unchecked once compiled to native code. It lands on this page only as a risk to "Promises are proven".

### Rows that rest on no guarantee

These rows cover part of a control through a mechanism that is not one of the five guarantees - the HTTP door's token, release signing, THREAT_MODEL.md's own documentation, the receipt's run parameters:

- AIUC-1: B007 (partial), B008 (partial)
- NIST AI RMF: MEASURE 1.1 (partial), MEASURE 2.1 (partial), MANAGE 1.4 (partial)

## Every known-open item, and where it lands

Each row of THREAT_MODEL.md's Known open table, with the controls on this page that it leaves open. None of these rows is a broken guarantee; each is a stated limit.

### Timing and other side channels

How long a run takes, its CPU and cache use, and the size and timing of its output are not measured or bounded, and a program can signal through any of them.

It leaves open:

- OWASP Agentic Top 10: ASI03 (partial)
- AIUC-1: A006 (partial), A008 (partial)
- NIST AI RMF: MEASURE 2.10 (not addressed)

### A granted `ffi` module

Within a granted module, that module's whole behaviour is granted; the allow-list narrows which module a call reaches, not what the module does.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI04 (partial), ASI05 (partial), ASI10 (partial)
- AIUC-1: A003 (partial), A005 (partial), B006 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial), MANAGE 3.1 (partial)

### Native code

A granted module may be or ship compiled code with no source and no bound; the audit's `ffi_native` reports it where it is found.

It leaves open:

- OWASP Agentic Top 10: ASI02 (partial), ASI04 (partial), ASI05 (partial)
- AIUC-1: B006 (partial), D003 (partial)
- NIST AI RMF: MANAGE 3.1 (partial)

### Secrets arriving another way

`Secret of T` marks only what `env()` and `read_file_secret()` return; a secret from anywhere else is an ordinary value.

It leaves open:

- OWASP Agentic Top 10: ASI03 (partial)
- AIUC-1: A006 (partial), A008 (partial)
- NIST AI RMF: MEASURE 2.10 (not addressed)

### Confinement on Linux: what it leaves

Full confinement holds files, the network and processes to the budget. It does not hold a host named in a `net:` grant, a credential location under a broad grant, `env`, or a hard link or bind mount that was inside a granted path before the run; and it is no better than the kernel.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### Confinement on macOS: partial

Writes, the network and new processes are held by a sandbox profile; reads are refused only under the home directory and /Volumes; and Apple has deprecated the mechanism.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### Confinement on Windows: partial

A second process is refused, every privilege is removed from the token, and a budget with no write grant can write nothing of the user's. Reads, the network, and writes under a budget that grants any, are not held.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### Runs that are not confined

An in-process `sabline.run()` with no limit, the REPL, `sabline test` and `sabline bench` are not confined, and a budget that grants `ffi:os`, `ffi:subprocess`, plain `ffi` or a module the table does not name widens the OS policy to nothing enforced. A confined process still runs as the user.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial), ASI10 (partial)
- AIUC-1: B006 (partial), B008 (partial), D003 (partial), F001 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### The fault-injection hook

`SABLINE_FAULT_INJECT`, read from the environment a run was started with, makes the runtime attempt one fixed effect so the honesty test can show the kernel refusing it. A program cannot set it, and it performs nothing the person who set it could not.

It leaves open:

- AIUC-1: B008 (partial)

### What a receipt shows that is not a value

A receipt keeps out every value, but holds the exit status, where the run stopped, its counts and its wall time, which a program that declassified something can choose.

It leaves open:

- OWASP Agentic Top 10: ASI10 (partial)
- AIUC-1: A006 (partial), A008 (partial), B009 (not addressed), E015 (partial)

### Writes to where Python imports from

A write grant to a directory on some Python's import path lets a program leave code the next Python process runs.

It leaves open:

- OWASP Agentic Top 10: ASI05 (partial)
- AIUC-1: B006 (partial)

### An ejected directory

An ejected directory keeps the Sabline it was ejected with, and its launcher cannot check itself.

It leaves open:

- OWASP Agentic Top 10: ASI04 (partial)
- AIUC-1: B008 (partial)
- NIST AI RMF: MANAGE 3.1 (partial)

### A program that stalls a review

`sabline review` compiles every program with no ceiling, so a program built to exhaust the type checker holds it, and the Action's comment step, until the job times out.

It leaves open:

- AIUC-1: C002 (partial), C007 (partial)
- NIST AI RMF: MEASURE 2.7 (partial)

### A predicate type is a name on a domain

The two predicate types name sabline.dev; whoever holds a domain decides what its pages say, and a type is an identifier, not a signature.

It leaves open:

- OWASP Agentic Top 10: ASI04 (partial)
- AIUC-1: B008 (partial)

### The user running sabline

Anything running as the user who runs Sabline can edit the program, the budget, a receipt after it is written, or Sabline itself.

It leaves open:

- OWASP Agentic Top 10: ASI03 (partial), ASI10 (partial)
- AIUC-1: B008 (partial), E015 (partial)
- NIST AI RMF: MEASURE 2.4 (partial)

No known-open item lands on an ACS row, since every ACS row is not addressed for a reason that comes first: Sabline implements none of ACS.
