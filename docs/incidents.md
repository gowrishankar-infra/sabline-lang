# Incidents

Real, publicly reported incidents from 2023 onward in the lane Sabline is written for: AI agent failures and software supply-chain attacks where code ran with more authority than it should have. For each one, whether a program of the same **shape**, written in Sabline and run under a budget, is refused.

> [!NOTE]
> **These are the shapes of the attacks. This is not a claim that adopting Sabline would have prevented the real events.** None of them involved a Sabline program. Every one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What an entry shows is narrower and checkable: given the same shape, here is the program, the command, what the runtime actually printed, and the one line of budget that did the work. Where nothing here addresses the shape, the entry says so, and the reason is in the [known-open table](known-open.html).

## The counts

13 incidents in scope, and 2 listed as out of scope. Every entry links the report it was written from.

| Verdict | Count | What it means |
|---|---|---|
| `STOPPED` | 2 | the shape, written in Sabline and run under a budget granting what the task needs, is refused - and the refusal is recorded and re-run on every push |
| `PARTIAL` | 6 | part of the shape is refused and part is not; both halves are recorded |
| `NOT COVERED` | 5 | nothing in Sabline addresses this shape |
| `UNVERIFIED` | 0 | it may be covered; no repro was built, so nothing is claimed |
| `OUT OF SCOPE` | 2 | prompt injection where no code ran - listed so the boundary is visible, not counted as a gap |

> [!KNOWN-OPEN]
> **15 of 15 summaries have not been checked against their sources by a person**, so they are not published. Each is named below with its verdict and its sources, and its summary is withheld until someone reads those sources and sets `verified: true` in the entry. The counts above are of entries, not of checked entries. What is published for a withheld entry is the part a machine checks - the verdict, which `check_incidents.py` re-runs, and the links - and what is withheld is the part only a person can check: the account of what happened.

A verdict is never `STOPPED` on reasoning: `check_incidents.py` re-runs every recorded command on every push, and an entry whose program stops refusing fails the build before a release is made from it.

## How these were chosen

This is a selection, not a survey. An incident is here only if it is **from 2023 onward**, **in the lane** - code that ran with more authority than it should have - and **backed by a primary source**: a vendor post-mortem, a CVE record, or the researcher's own write-up. Nothing goes in without one.

**These are not all the incidents in this lane, and the counts are not a measurement of the field.** A verdict count is a count of what is in this catalogue, not a claim about how common each shape is. What is left out on purpose: anything before 2023; prompt injection where no code ran, which is `OUT OF SCOPE` rather than a gap and is why EchoLeak and CamoLeak are listed that way; and anything that cannot be sourced to a primary report - one incident, an agent that deleted a production database (Replit, July 2025), was dropped for exactly that reason.

## STOPPED

The shape, written in Sabline and run under a budget granting what the task needs, is refused - and the refusal is recorded and re-run on every push.

### The @solana/web3.js backdoor, 1.95.6 and 1.95.7

2024-12-03 - [incidents/solana-web3js-backdoor/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/solana-web3js-backdoor/) - the line that does the work: `sabline.lock`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/solana-web3js-backdoor/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/solana-web3js-backdoor/incident.md).*

- [GHSA-jcxm-7wvp-g6p5](https://github.com/solana-labs/solana-web3.js/security/advisories/GHSA-jcxm-7wvp-g6p5) - the maintainers' own advisory: the compromised publish account, the affected versions, and what the injected code did.
- [web3.js Exploit: Root Cause Analysis](https://www.anza.xyz/blog/web3-js-exploit-root-cause-analysis) - Anza's post-mortem: the window the versions were live, and the exfiltration path.

### mcp-remote, CVE-2025-6514

2025-07-09 - [incidents/mcp-remote-command-injection/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-remote-command-injection/) - the line that does the work: `ffi:json`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/mcp-remote-command-injection/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-remote-command-injection/incident.md).*

- [OS command injection in mcp-remote when connecting to untrusted MCP servers (JFSA-2025-001290844)](https://research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/) - JFrog's own research advisory, which found and reported it.
- [CVE-2025-6514: Critical mcp-remote RCE Vulnerability](https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/) - JFrog's own blog write-up (Or Peles, 9 July 2025): what mcp-remote is, the OAuth metadata path, the client (Claude Desktop), and which platforms allow arbitrary commands. The two advisories link it; the four sentences above that the advisories do not carry come from here.
- [GHSA-6xpm-ggf7-wc3p / CVE-2025-6514](https://github.com/advisories/GHSA-6xpm-ggf7-wc3p) - the advisory record: affected versions, severity, and the fixed release.

## PARTIAL

Part of the shape is refused and part is not; both halves are recorded.

### Hallucinated packages, and squatting on them

2024-03-28 - [incidents/package-hallucination/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/package-hallucination/) - the line that does the work: `import "lib/..."`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/package-hallucination/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/package-hallucination/incident.md).*

- [Diving Deeper into AI Package Hallucinations](https://www.lasso.security/blog/ai-package-hallucinations) - Bar Lanyado's own write-up, 28 March 2024: the `huggingface-cli` test, the more than 30,000 downloads in three months, and the Alibaba README.
- [We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen) - USENIX Security 2025: the rates, the sample size, and the 205,474 names.
- [Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination) - the paper's published code and data.

### tj-actions/changed-files, CVE-2025-30066

2025-03-14 - [incidents/tj-actions-changed-files/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/tj-actions-changed-files/) - the line that does the work: `env`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/tj-actions-changed-files/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/tj-actions-changed-files/incident.md).*

- [GHSA-mrrh-fwg8-r2c3 / CVE-2025-30066](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3) - the GitHub advisory record: affected versions, the malicious commit `0e58ed8` the tags were moved to, the disclosure of secrets through action logs, and the fixed version.
- [Supply Chain Compromise of Third-Party tj-actions/changed-files (CVE-2025-30066) and reviewdog/action-setup@v1 (CVE-2025-30154)](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction) - CISA's alert, 18 March 2025.
- [GitHub Action tj-actions/changed-files supply chain attack](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066) - Wiz's analysis: the memory scrape, the double-base64 encoding, and the dozens of affected public repositories it found.

### MCP tool poisoning

2025-04-01 - [incidents/mcp-tool-poisoning/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-tool-poisoning/) - the line that does the work: `--max-allow io`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/mcp-tool-poisoning/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-tool-poisoning/incident.md).*

- [MCP Security Notification: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks) - the researchers' own write-up, 1 April 2025: the technique, the Cursor demonstration, the files read, and the hidden argument.
- [invariantlabs-ai/mcp-injection-experiments](https://github.com/invariantlabs-ai/mcp-injection-experiments) - the published reproduction code.

### Nx "s1ngularity"

2025-08-26 - [incidents/nx-s1ngularity/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/nx-s1ngularity/) - the line that does the work: `ffi:json`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/nx-s1ngularity/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/nx-s1ngularity/incident.md).*

- [S1ngularity - What Happened, How We Responded, What We Learned](https://nx.dev/blog/s1ngularity-postmortem) - Nx's own postmortem: the date, the four-hour window, and what the post-install script did.
- [GHSA-cxm3-wv7p-598c](https://github.com/nrwl/nx/security/advisories/GHSA-cxm3-wv7p-598c) - the maintainer's advisory listing the malicious versions.
- [s1ngularity: Popular Nx Build System Package Compromised with Data-Stealing Malware](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware) - StepSecurity's analysis: the AI CLI invocations and their flags.
- [The Nx "s1ngularity" Attack: Inside the Credential Leak](https://blog.gitguardian.com/the-nx-s1ngularity-attack-inside-the-credential-leak/) - GitGuardian's count of the credentials and systems affected.

### The Shai-Hulud npm worm

2025-09-14 - [incidents/shai-hulud-npm-worm/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/shai-hulud-npm-worm/) - the line that does the work: `fs:read:.`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/shai-hulud-npm-worm/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/shai-hulud-npm-worm/incident.md).*

- [Our plan for a more secure npm supply chain](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-chain/) - GitHub's own post, 22 September 2025: the notification date, the description of the worm, and the 500+ packages removed.
- [Shai-Hulud: Self-Replicating Worm Compromises 500+ NPM Packages](https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised) - StepSecurity's analysis of the payload: TruffleHog, the cloud metadata and Secrets Manager calls, the injected workflow file, and the self-propagation.

### postmark-mcp, the BCC in an authorised tool

2025-09-25 - [incidents/postmark-mcp-bcc-exfiltration/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/postmark-mcp-bcc-exfiltration/) - the line that does the work: `tool:send_email:to=*@corp.com`

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/postmark-mcp-bcc-exfiltration/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/postmark-mcp-bcc-exfiltration/incident.md).*

- [Malicious MCP Server on npm: postmark-mcp harvests emails](https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/) - Snyk's analysis by Liran Tal, 25 September 2025: the affected versions, the BCC address, and what was exposed.
- [Information regarding malicious "postmark-mcp" package](https://postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package) - Postmark's own statement, 25 September 2025: that the package was an unofficial one impersonating Postmark, and that the backdoor was added in version 1.0.16.
- [Fake Postmark MCP npm package stole emails with one-liner](https://www.theregister.com/security/2025/09/29/fake-postmark-mcp-npm-package-stole-emails-with-one-liner/509095) - contemporaneous reporting, for the install counts and the timeline.

> Koi Security discovered the package and wrote it up on 25 September 2025.
> That post no longer resolves - the address now redirects away from the
> article - so it is not linked here; an archived copy survives at the
> Wayback Machine. Snyk's write-up carries the same technical detail with the
> code shown.

## NOT COVERED

Nothing in Sabline addresses this shape.

### The CircleCI January 2023 incident

2022-12-22 - [incidents/circleci-oauth-token-theft/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/circleci-oauth-token-theft/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/circleci-oauth-token-theft/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/circleci-oauth-token-theft/incident.md).*

- [CircleCI Jan 4, 2023 security incident report](https://circleci.com/blog/jan-4-2023-incident-report/) - CircleCI's own post-mortem: the malware, the stolen session, what was exfiltrated, and the rotation timeline.
- [CircleCI security alert: Rotate any secrets stored in CircleCI](https://circleci.com/blog/january-4-2023-security-alert/) - the customer-facing alert of 4 January 2023.

### The xz-utils backdoor, CVE-2024-3094

2024-03-29 - [incidents/xz-utils-backdoor/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/xz-utils-backdoor/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/xz-utils-backdoor/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/xz-utils-backdoor/incident.md).*

- [backdoor in upstream xz/liblzma leading to ssh server compromise](https://www.openwall.com/lists/oss-security/2024/03/29/4) - Andres Freund's original oss-security post, 29 March 2024, which is the public disclosure.
- [CVE-2024-3094](https://nvd.nist.gov/vuln/detail/CVE-2024-3094) - the CVE record.

### Ultralytics 8.3.41 and 8.3.42 on PyPI

2024-12-04 - [incidents/ultralytics-pypi-cache-poisoning/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/ultralytics-pypi-cache-poisoning/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/ultralytics-pypi-cache-poisoning/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/ultralytics-pypi-cache-poisoning/incident.md).*

- [Supply-chain attack analysis: Ultralytics](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) - the PyPI blog's analysis, 11 December 2024: the cache poisoning and the two publishing paths. It defers the technical path to William Woodruff's analysis, which it links.
- [Ultralytics AI Library Hacked via GitHub for Cryptomining](https://www.wiz.io/blog/ultralytics-ai-library-hacked-via-github-for-cryptomining) - Wiz's analysis: the branch-name injection in the "Publish Docs" workflow, and the XMRig payload.

### Private repositories leaked through the GitHub MCP server

2025-05-26 - [incidents/github-mcp-toxic-agent-flow/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/github-mcp-toxic-agent-flow/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/github-mcp-toxic-agent-flow/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/github-mcp-toxic-agent-flow/incident.md).*

- [GitHub MCP Exploited: Accessing private repositories via MCP](https://invariantlabs.ai/blog/mcp-github-vulnerability) - the researchers' own write-up, 26 May 2025: the injection vector, the agent used, what leaked, and where they place responsibility.

### Amazon Q Developer for VS Code 1.84.0, CVE-2025-8217

2025-07-17 - [incidents/amazon-q-extension-wiper/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/amazon-q-extension-wiper/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/amazon-q-extension-wiper/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/amazon-q-extension-wiper/incident.md).*

- [Security Update for Amazon Q Developer Extension for Visual Studio Code (Version #1.84)](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/) - AWS's own security bulletin (AWS-2025-015): the token scoping, the affected version, the syntax error, and the fix.
- [CVE-2025-8217](https://nvd.nist.gov/vuln/detail/CVE-2025-8217) - the CVE record.
- [Amazon AI coding agent hacked to inject data wiping commands](https://www.bleepingcomputer.com/news/security/amazon-ai-coding-agent-hacked-to-inject-data-wiping-commands/) - reporting on what the payload said, which the bulletin does not quote.

## OUT OF SCOPE

Prompt injection where no code ran - listed so the boundary is visible, not counted as a gap.

### EchoLeak, CVE-2025-32711

2025-06-11 - [incidents/echoleak-m365-copilot/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/echoleak-m365-copilot/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/echoleak-m365-copilot/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/echoleak-m365-copilot/incident.md).*

- [CVE-2025-32711](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2025-32711) - Microsoft's advisory and CVE record (Microsoft is the CNA): the CVE id, the CVSS score, the acknowledgement of Aim Labs, the server-side fix, and that there was no exploitation in the wild.
- [Breaking down 'EchoLeak', the first zero-click AI vulnerability enabling data exfiltration in Microsoft 365 Copilot](https://www.aim.security/lp/aim-labs-echoleak-blogpost) - Aim Labs' own report, which describes the vector and the scope-violation framing. **The page has not served the article since August 2025** (it answers HTTP 403 now); it is cited as an archived copy, read through the Wayback Machine, and every sentence below that rests on it alone is marked as such.

### CamoLeak, in GitHub Copilot Chat

2025-10-08 - [incidents/camoleak-copilot-chat/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/camoleak-copilot-chat/) - the line that does the work: no budget line: nothing here refuses it

*The summary of this incident is written and not yet checked against the sources below, so it is not published. It is in [incidents/camoleak-copilot-chat/incident.md](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/camoleak-copilot-chat/incident.md).*

- [CamoLeak: Critical GitHub Copilot Vulnerability Leaks Private Source Code](https://www.legitsecurity.com/blog/camoleak-critical-github-copilot-vulnerability-leaks-private-source-code) - the researcher's own write-up: the injection, the Camo encoding, what was extracted, and the fix date.

## Adding one, and checking one

The entries live in [incidents/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/) in this repository, one directory each, with `incidents/TEMPLATE.md` for a new one. `incidents/README.md` gives the rules: what counts as a source, what each verdict means, and exactly what is normalised in a recorded refusal so the same bytes appear on every machine. `python incident_evidence.py` re-runs the evidence, `python check_incidents.py` is what CI runs, and `python build_incidents.py` writes this page.
