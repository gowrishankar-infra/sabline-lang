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

> [!NOTE]
> Every summary below has been checked against its sources by a person. An entry is not published until that is done.

A verdict is never `STOPPED` on reasoning: `check_incidents.py` re-runs every recorded command on every push, and an entry whose program stops refusing fails the build before a release is made from it.

## How these were chosen

This is a selection, not a survey. An incident is here only if it is **from 2023 onward**, **in the lane** - code that ran with more authority than it should have - and **backed by a primary source**: a vendor post-mortem, a CVE record, or the researcher's own write-up. Nothing goes in without one.

**These are not all the incidents in this lane, and the counts are not a measurement of the field.** A verdict count is a count of what is in this catalogue, not a claim about how common each shape is. What is left out on purpose: anything before 2023; prompt injection where no code ran, which is `OUT OF SCOPE` rather than a gap and is why EchoLeak and CamoLeak are listed that way; and anything that cannot be sourced to a primary report - one incident, an agent that deleted a production database (Replit, July 2025), was dropped for exactly that reason.

## STOPPED

The shape, written in Sabline and run under a budget granting what the task needs, is refused - and the refusal is recorded and re-run on every push.

### The @solana/web3.js backdoor, 1.95.6 and 1.95.7

2024-12-03 - [incidents/solana-web3js-backdoor/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/solana-web3js-backdoor/) - the line that does the work: `sabline.lock`

On 3 December 2024 an account with publish rights to `@solana/web3.js` was
compromised through a spear-phishing email, and two unauthorised versions,
1.95.6 and 1.95.7, were put on npm. The maintainers' advisory records that
the injected code stole private key material and that the risk fell on
applications which handle private keys directly, such as bots. The versions
went up at about 3:20pm UTC; a clean 1.95.8 was published at 8:25pm UTC, and
npm removed 1.95.6 and 1.95.7 entirely at about 12:22am UTC on 4 December.
Code added to five existing key-handling methods, including
`Keypair.fromSecretKey()` and `Keypair.fromSeed()`, captured private key
material and sent it to a server the attacker controlled.

- [GHSA-jcxm-7wvp-g6p5](https://github.com/solana-labs/solana-web3.js/security/advisories/GHSA-jcxm-7wvp-g6p5) - the maintainers' own advisory: the compromised publish account, the affected versions, and what the injected code did.
- [web3.js Exploit: Root Cause Analysis](https://www.anza.xyz/blog/web3-js-exploit-root-cause-analysis) - Anza's post-mortem: the window the versions were live, and the exfiltration path.

### mcp-remote, CVE-2025-6514

2025-07-09 - [incidents/mcp-remote-command-injection/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-remote-command-injection/) - the line that does the work: `ffi:json`

JFrog's security research team found an OS command injection in
`mcp-remote`, an npm package. JFrog's write-up describes it as the proxy
that lets MCP clients such as Claude Desktop reach a remote MCP server. It is
triggered when the proxy connects to an untrusted MCP server: crafted input
from the server's `authorization_endpoint` response - its OAuth
authorization-server metadata, per JFrog's write-up - reaches an
operating-system command without being sanitised, which lets a malicious
server inject operating-system commands on the machine the proxy is on
(JFrog proves full arbitrary commands on Windows, and executables with
limited parameter control on macOS and Linux). It affects versions 0.0.5
through 0.1.15 and is fixed in 0.1.16; the advisory rates it 9.6. It was
disclosed on 9 July 2025.

- [OS command injection in mcp-remote when connecting to untrusted MCP servers (JFSA-2025-001290844)](https://research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/) - JFrog's own research advisory, which found and reported it.
- [CVE-2025-6514: Critical mcp-remote RCE Vulnerability](https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/) - JFrog's own blog write-up (Or Peles, 9 July 2025): what mcp-remote is, the OAuth metadata path, the client (Claude Desktop), and which platforms allow arbitrary commands. The two advisories link it; the four sentences above that the advisories do not carry come from here.
- [GHSA-6xpm-ggf7-wc3p / CVE-2025-6514](https://github.com/advisories/GHSA-6xpm-ggf7-wc3p) - the advisory record: affected versions, severity, and the fixed release.

## PARTIAL

Part of the shape is refused and part is not; both halves are recorded.

### Hallucinated packages, and squatting on them

2024-03-28 - [incidents/package-hallucination/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/package-hallucination/) - the line that does the work: `import "lib/..."`

On 28 March 2024 Bar Lanyado published a test of what he had named "AI
package hallucination": models recommended installing a Python package
called `huggingface-cli`, which did not exist. He registered the
name and uploaded an empty package under it, and reports that "in three
months the fake and empty package got more than 30k authentic downloads",
and that "instructions for installing this package can be found in the
README of a repository dedicated to research conducted by Alibaba". The
USENIX Security 2025 paper by Spracklen and colleagues measured the
phenomenon across 576,000 generated code samples from 16 models, finding at
least 5.2% hallucinated package references from commercial models and 21.7%
from open-source ones, across 205,474 distinct invented names.

- [Diving Deeper into AI Package Hallucinations](https://www.lasso.security/blog/ai-package-hallucinations) - Bar Lanyado's own write-up, 28 March 2024: the `huggingface-cli` test, the more than 30,000 downloads in three months, and the Alibaba README.
- [We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen) - USENIX Security 2025: the rates, the sample size, and the 205,474 names.
- [Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination) - the paper's published code and data.

### tj-actions/changed-files, CVE-2025-30066

2025-03-14 - [incidents/tj-actions-changed-files/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/tj-actions-changed-files/) - the line that does the work: `env`

The GitHub advisory dates the compromise to 14-15 March 2025 (Wiz puts it
some time before 14 March, and CISA asks for an audit of runs from 12 March
00:00 UTC to 15 March 12:00 UTC); in that window the tags of the
`tj-actions/changed-files` GitHub Action, v1 through v45.0.7, were retagged
to point at a single malicious commit. The GitHub advisory records that the
Action then "allows remote attackers to discover secrets by reading actions
logs": the injected step ran a Python script that read secrets out of the
Runner Worker process's memory and printed them, double-base64 encoded, into
the workflow log - public, on a public repository. CISA issued an alert on 18
March 2025, and updated it on 19 March to cover the related compromise of
`reviewdog/action-setup@v1` (CVE-2025-30154), which it says potentially
enabled this one. The behaviour was removed in v46.0.1.

- [GHSA-mrrh-fwg8-r2c3 / CVE-2025-30066](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3) - the GitHub advisory record: affected versions, the malicious commit `0e58ed8` the tags were moved to, the disclosure of secrets through action logs, and the fixed version.
- [Harden-Runner detection: tj-actions/changed-files action is compromised](https://www.stepsecurity.io/blog/harden-runner-detection-tj-actions-changed-files-action-is-compromised) - StepSecurity's own report: Harden-Runner's anomaly detection found the compromise on 14 March 2025, when an unexpected endpoint appeared in a run's network traffic; the report names the single malicious commit every release tag was moved to, and the Python script that dumps the Runner Worker process's secrets into the workflow log.
- [Supply Chain Compromise of Third-Party tj-actions/changed-files (CVE-2025-30066) and reviewdog/action-setup@v1 (CVE-2025-30154)](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction) - CISA's alert, 18 March 2025.
- [GitHub Action tj-actions/changed-files supply chain attack](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066) - Wiz's analysis: the memory scrape, the double-base64 encoding, and the dozens of affected public repositories it found.

### MCP tool poisoning

2025-04-01 - [incidents/mcp-tool-poisoning/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/mcp-tool-poisoning/) - the line that does the work: `--max-allow io`

On 1 April 2025 Luca Beurer-Kellner and Marc Fischer of Invariant Labs
published a proof of concept in which instructions hidden in an MCP tool's
*description* - text the model reads and the user does not - steer an agent
into doing something the tool does not claim to do. In their demonstration
against Cursor, a poisoned `add` tool made the agent read
`~/.cursor/mcp.json` and `~/.ssh/id_rsa` and pass the contents to the
malicious server in an extra `sidenote` argument: "the agent willingly reads
the user's `~/.cursor/mcp.json` file, and other sensitive files like SSH keys
and sends them to the malicious server." They note that even where the client
asks for confirmation, Cursor "does not show the full tool input" and "the
included SSH key is completely hidden". Reproduction code is published at
`invariantlabs-ai/mcp-injection-experiments`.

- [MCP Security Notification: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks) - the researchers' own write-up, 1 April 2025: the technique, the Cursor demonstration, the files read, and the hidden argument.
- [invariantlabs-ai/mcp-injection-experiments](https://github.com/invariantlabs-ai/mcp-injection-experiments) - the published reproduction code.

### Nx "s1ngularity"

2025-08-26 - [incidents/nx-s1ngularity/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/nx-s1ngularity/) - the line that does the work: `ffi:json`

On 26 August 2025 several malicious versions of the Nx build system and its
plugins were published to npm; Nx's postmortem says they were live for about
four hours. Nx's own postmortem records that "the malicious packages ran a post-install script
that scanned user systems for sensitive data, attempted to use local AI
tools (like Claude and Gemini), and uploaded the results to a public GitHub
repo via the GitHub CLI" - the repository being created in the victim's own
account, named `s1ngularity-repository`, holding a base64 file of what was
found. StepSecurity's analysis records that the AI command-line tools were
invoked with their own permission-skipping flags
(`--dangerously-skip-permissions`, `--yolo`, `--trust-all-tools`) so that
the reconnaissance would be done by a tool the developer had already
trusted. GitGuardian counted 2,349 credentials taken from 1,079 systems.

- [S1ngularity - What Happened, How We Responded, What We Learned](https://nx.dev/blog/s1ngularity-postmortem) - Nx's own postmortem: the date, the four-hour window, and what the post-install script did.
- [GHSA-cxm3-wv7p-598c](https://github.com/nrwl/nx/security/advisories/GHSA-cxm3-wv7p-598c) - the maintainer's advisory listing the malicious versions.
- [s1ngularity: Popular Nx Build System Package Compromised with Data-Stealing Malware](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware) - StepSecurity's analysis: the AI CLI invocations and their flags.
- [The Nx "s1ngularity" Attack: Inside the Credential Leak](https://blog.gitguardian.com/the-nx-s1ngularity-attack-inside-the-credential-leak/) - GitGuardian's count of the credentials and systems affected.

### The Shai-Hulud npm worm

2025-09-14 - [incidents/shai-hulud-npm-worm/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/shai-hulud-npm-worm/) - the line that does the work: `fs:read:.`

On 14 September 2025 GitHub was notified of Shai-Hulud, described in its own
write-up as "a self-replicating worm that infiltrated the npm ecosystem via
compromised maintainer accounts by injecting malicious post-install scripts
into popular JavaScript packages"; GitHub removed more than 500 compromised
packages from the registry. StepSecurity's analysis of the payload reports
that it "repurposes open-source tools like TruffleHog to scan the filesystem
for high-entropy secrets", read cloud metadata endpoints and AWS Secrets
Manager, and uploaded what it found to a new public GitHub repository named
Shai-Hulud, created through GitHub's `/user/repos` API. It also wrote a
workflow file,
`.github/workflows/shai-hulud-workflow.yml`, that exfiltrates repository
secrets with `${{ toJSON(secrets) }}`, and republished itself into other
packages the compromised maintainer owned.

- [Our plan for a more secure npm supply chain](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-chain/) - GitHub's own post, 22 September 2025: the notification date, the description of the worm, and the 500+ packages removed.
- [Shai-Hulud: Self-Replicating Worm Compromises 500+ NPM Packages](https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised) - StepSecurity's analysis of the payload: TruffleHog, the cloud metadata and Secrets Manager calls, the injected workflow file, and the self-propagation.

### postmark-mcp, the BCC in an authorised tool

2025-09-25 - [incidents/postmark-mcp-bcc-exfiltration/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/postmark-mcp-bcc-exfiltration/) - the line that does the work: `tool:send_email:to=*@corp.com`

An npm package called `postmark-mcp`, an unofficial MCP server for sending
email through Postmark, was published in versions that quietly blind-copied
every outgoing message to an address the author controlled. Snyk's analysis,
published 25
September 2025, records that the added code set
`Bcc: 'phan@giftshop.club'` and that versions from 1.0.16 through at least
1.0.18 carried it, exposing "any email content sent through the MCP server
(including attachments and headers), potentially including secrets, tokens,
customer PII, and regulated data". Earlier versions of the package behaved
as expected; reporting puts its use at roughly 1,500 installs a week at the
time.

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

CircleCI's incident report records that "an unauthorized third party
leveraged malware deployed to a CircleCI engineer's laptop in order to steal
a valid, 2FA-backed SSO session"; the actor then used that access to
exfiltrate data from a subset of the company's production systems, including
customer environment variables, tokens and keys. A customer's GitHub OAuth
token was found compromised on 30 December 2022, CircleCI began rotating all
customers' GitHub OAuth tokens on 31 December, and alerted customers on 4
January 2023 to rotate every secret they had stored; the exfiltration itself
took place on 22 December 2022. CircleCI reports that AWS's notifications to
customers with possibly affected AWS tokens were complete by 12 January.

- [CircleCI Jan 4, 2023 security incident report](https://circleci.com/blog/jan-4-2023-incident-report/) - CircleCI's own post-mortem: the malware, the stolen session, what was exfiltrated, and the rotation timeline.
- [CircleCI security alert: Rotate any secrets stored in CircleCI](https://circleci.com/blog/january-4-2023-security-alert/) - the customer-facing alert of 4 January 2023.

### The xz-utils backdoor, CVE-2024-3094

2024-03-29 - [incidents/xz-utils-backdoor/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/xz-utils-backdoor/) - the line that does the work: no budget line: nothing here refuses it

On 29 March 2024 Andres Freund posted to the oss-security list: "After
observing a few odd symptoms around liblzma (part of the xz package) on
Debian sid installations over the last weeks (logins with ssh taking a lot
of CPU, valgrind errors) I figured out the answer: The upstream xz
repository and the xz tarballs have been backdoored." Versions 5.6.0 and
5.6.1 carried it. It activated during a Debian or RPM package build on
x86-64 Linux with gcc and the GNU linker, and interfered with sshd along
liblzma's dependency chain: openssh does not use liblzma itself, but Debian
and several other distributions patch it to link libsystemd, which depends on
liblzma. It redirected sshd's `RSA_public_decrypt` to its own code, so that
public-key authentication could be subverted.

- [backdoor in upstream xz/liblzma leading to ssh server compromise](https://www.openwall.com/lists/oss-security/2024/03/29/4) - Andres Freund's original oss-security post, 29 March 2024, which is the public disclosure.
- [CVE-2024-3094](https://nvd.nist.gov/vuln/detail/CVE-2024-3094) - the CVE record.

### Ultralytics 8.3.41 and 8.3.42 on PyPI

2024-12-04 - [incidents/ultralytics-pypi-cache-poisoning/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/ultralytics-pypi-cache-poisoning/) - the line that does the work: no budget line: nothing here refuses it

On 4 December 2024 an attacker opened two pull requests against the
`ultralytics` repository. Wiz traces the injection to a crafted branch name
that the project's "Publish Docs" workflow, run on pull requests, passed
unsanitised into a shell command. PyPI's analysis says the attack then
targeted the GitHub Actions cache used during the build, and that the first
malicious releases were published by the project's own workflow through
Trusted Publishing - not with a token - while a second round was uploaded
with an unrevoked PyPI API token still available to the workflow; it points
to William Woodruff's analysis for the full path. PyPI lists four affected
versions, since removed: 8.3.41, 8.3.42, 8.3.45 and 8.3.46. Wiz reports that
8.3.41 and 8.3.42 carried an XMRig cryptocurrency miner.

- [Supply-chain attack analysis: Ultralytics](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) - the PyPI blog's analysis, 11 December 2024: the cache poisoning and the two publishing paths. It defers the technical path to William Woodruff's analysis, which it links.
- [Ultralytics AI Library Hacked via GitHub for Cryptomining](https://www.wiz.io/blog/ultralytics-ai-library-hacked-via-github-for-cryptomining) - Wiz's analysis: the branch-name injection in the "Publish Docs" workflow, and the XMRig payload.
- [zizmor would have caught the Ultralytics workflow vulnerability](https://blog.yossarian.net/2024/12/06/zizmor-ultralytics-injection) - William Woodruff's own analysis, the one the PyPI blog defers to: the `pull_request_target` trigger in `format.yml`, the branch name interpolated unquoted into `git pull origin ${{ github.head_ref || github.ref }}`, and the cache poisoning that followed.

### Private repositories leaked through the GitHub MCP server

2025-05-26 - [incidents/github-mcp-toxic-agent-flow/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/github-mcp-toxic-agent-flow/) - the line that does the work: no budget line: nothing here refuses it

On 26 May 2025 Marco Milanta and Luca Beurer-Kellner of Invariant Labs
published an exploit against an agent connected to the official GitHub MCP
server. A malicious issue filed on a public repository carried instructions;
when the user asked their agent - Claude Desktop, in the demonstration - to
look at the open issues, the agent followed them, read data out of the
user's private repositories, and published it in a pull request on the
public one. The researchers are explicit that "this is not a flaw in the
GitHub MCP server code itself, but rather a fundamental architectural issue
that must be addressed at the agent system level", and that "GitHub alone
cannot resolve this vulnerability through server-side patches".

- [GitHub MCP Exploited: Accessing private repositories via MCP](https://invariantlabs.ai/blog/mcp-github-vulnerability) - the researchers' own write-up, 26 May 2025: the injection vector, the agent used, what leaked, and where they place responsibility.

### Amazon Q Developer for VS Code 1.84.0, CVE-2025-8217

2025-07-17 - [incidents/amazon-q-extension-wiper/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/amazon-q-extension-wiper/) - the line that does the work: no budget line: nothing here refuses it

AWS's security bulletin AWS-2025-015, published 23 July 2025 and updated on
25 July, records that an attacker used "an inappropriately scoped GitHub
token" in a CodeBuild configuration to inject code into version 1.84.0 of
the Amazon Q Developer extension for Visual Studio Code, which was then
included in a release automatically. AWS states it "was unsuccessful in
executing due to a syntax error", revoked the credentials, removed the
payload, and released 1.85.0; users of 1.84.0 are told to remove it. It is
tracked as CVE-2025-8217. Contemporaneous reporting described the payload
as an instruction addressed to the agent, telling it to delete local files
and cloud resources using AWS CLI commands such as `ec2 terminate-instances`,
`s3 rm` and `iam delete-user`.

- [Security Update for Amazon Q Developer Extension for Visual Studio Code (Version #1.84)](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/) - AWS's own security bulletin (AWS-2025-015): the token scoping, the affected version, the syntax error, and the fix.
- [CVE-2025-8217](https://nvd.nist.gov/vuln/detail/CVE-2025-8217) - the CVE record.
- [Amazon AI coding agent hacked to inject data wiping commands](https://www.bleepingcomputer.com/news/security/amazon-ai-coding-agent-hacked-to-inject-data-wiping-commands/) - reporting on what the payload said, which the bulletin does not quote.

## OUT OF SCOPE

Prompt injection where no code ran - listed so the boundary is visible, not counted as a gap.

### EchoLeak, CVE-2025-32711

2025-06-11 - [incidents/echoleak-m365-copilot/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/echoleak-m365-copilot/) - the line that does the work: no budget line: nothing here refuses it

Aim Labs reported a zero-click vulnerability in Microsoft 365 Copilot,
assigned CVE-2025-32711 with a CVSS score of 9.3. An email worded to read
as a normal request to the recipient (bypassing Microsoft's XPIA
classifier), needing no action from the victim, was pulled in by Copilot's
retrieval when the user later asked Copilot a question; its hidden
instructions made Copilot put sensitive data from the user's context into
an image link, fetched automatically through a Microsoft Teams URL allowed
by the content security policy, sending the data to the attacker's server.
The researchers call the underlying pattern an "LLM scope violation".
Microsoft fixed it server-side and states there was no exploitation in the
wild.

- [CVE-2025-32711](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2025-32711) - Microsoft's advisory and CVE record (Microsoft is the CNA): the CVE id, the CVSS score, the acknowledgement of Aim Labs, the server-side fix, and that there was no exploitation in the wild.
- [EchoLeak: The First Real-World Zero-Click Prompt Injection Exploit in a Production LLM System](https://arxiv.org/abs/2509.10540) - Pavan Reddy and Aditya Sanjay Gujral, arXiv:2509.10540, published at the AAAI Fall Symposium Series 2025: the email phrased as a normal request to the human recipient and so past the XPIA classifier, the ordinary retrieval pass that pulled it into Copilot's context, the reference-style image link the chat UI fetches as it renders, and the Microsoft Teams preview URL allowed by the content security policy. The account above rests on this paper.
- [Breaking down 'EchoLeak', the first zero-click AI vulnerability enabling data exfiltration in Microsoft 365 Copilot](https://www.aim.security/lp/aim-labs-echoleak-blogpost) - Aim Labs' own report, which describes the vector and the scope-violation framing. **The page has not served the article since August 2025** (it answers HTTP 403 now); it is cited as an archived copy, read through the Wayback Machine.

### CamoLeak, in GitHub Copilot Chat

2025-10-08 - [incidents/camoleak-copilot-chat/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/camoleak-copilot-chat/) - the line that does the work: no budget line: nothing here refuses it

Omer Mayraz of Legit Security reported a vulnerability in GitHub Copilot
Chat, which he named CamoLeak. Hidden instructions placed in a pull request
description - using GitHub's invisible comment syntax, so a human reviewer
does not see them - were read by Copilot when a user asked it about the pull
request. To get data out past the content security policy, the exploit
pre-generated a set of GitHub Camo image-proxy URLs standing for individual
characters, and had Copilot render the secret it had read one character at a
time as images. Mayraz reports having Copilot search a victim's codebase for
"AWS_KEY" and exfiltrate the result, and extracting details of undisclosed
vulnerabilities from private repositories. GitHub disabled image rendering in
Copilot Chat on 14 August 2025.

- [CamoLeak: Critical GitHub Copilot Vulnerability Leaks Private Source Code](https://www.legitsecurity.com/blog/camoleak-critical-github-copilot-vulnerability-leaks-private-source-code) - the researcher's own write-up: the injection, the Camo encoding, what was extracted, and the fix date.

## Adding one, and checking one

The entries live in [incidents/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/) in this repository, one directory each, with `incidents/TEMPLATE.md` for a new one. `incidents/README.md` gives the rules: what counts as a source, what each verdict means, and exactly what is normalised in a recorded refusal so the same bytes appear on every machine. `python incident_evidence.py` re-runs the evidence, `python check_incidents.py` is what CI runs, and `python build_incidents.py` writes this page.
