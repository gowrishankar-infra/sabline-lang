# How people describe the "code runs with more authority than its task needs" problem

Collected 2026-09-25. Read-only research. I loaded every quote below from the page or API response at the URL given. HN text came from the hn.algolia.com items API, GitHub text from the GitHub REST/GraphQL API (`gh api`), Stack Exchange text from api.stackexchange.com, Cursor forum text from its Discourse JSON, and blog text from a raw fetch. No quote comes from a search-result snippet. Reddit could not be loaded at all (see **Blocked**), so this file has no Reddit quotes.

Legend:
- **Who** is exactly one of `individual`, `company` or `researcher`.
- **Has the problem?** marks whether the speaker is a user or maintainer who has the problem (H) or a vendor or researcher describing it (V/R).
- **Engagement** was read on 2026-09-25. HN's API does not expose per-comment votes, so HN comments show their parent story's points and comment count.

---

## Part 1: 30 verbatim phrasings

### A. Secrets exposure (agents reading .env, keys, tokens)

**1.** "[BUG] Claude loads my projects .env into its bash environment (!)"
- https://github.com/anthropics/claude-code/issues/401 · GitHub issue title · 2025-03-08 · rasmuscnielsen · **individual** (H)
- Aspect: secrets exposure
- Engagement: 54 reactions (all +1), 64 comments

**2.** "the endpoint returns an auth error and ur bot starts searching willy nilly for auth credentials to stuff into a curl command"
- https://github.com/anthropics/claude-code/issues/9637 · GitHub issue body · 2025-10-16 · walt93 · **individual** (H)
- Title of the same issue: "[BUG] Claude Code AGGRESSIVELY reads secrets out of .env files and leaks them to your servers in so doing"
- Aspect: secrets exposure; agent reaches for credentials on its own
- Engagement: 0 reactions, 5 comments

**3.** "Claude Code has no first-class way to handle secrets."
- https://github.com/anthropics/claude-code/issues/29910 · GitHub issue body · 2026-03-01 · brianbowden ("I lead engineering at a startup…") · **individual** (H)
- Aspect: secrets exposure; secrets handling for agents
- Engagement: 45 reactions, 15 comments

**4.** "Codex can read `.env` files inside the workspace (e.g. via `cat .env`) without any denylist or explicit confirmation."
- https://github.com/openai/codex/issues/13778 · GitHub issue body (title: "Codex reading files like .env!") · 2026-03-06 · kriss145 · **individual** (H)
- Aspect: secrets exposure
- Engagement: 10 reactions, 7 comments

**5.** "we need a file like .gitignore that allows the user to define files that cline can't read."
- https://github.com/cline/cline/issues/1359 · GitHub issue body (title "[P0] .clineignore") · 2025-01-21 · ocasta181 (repo CONTRIBUTOR; the P0 tag suggests it was filed from the maintainer side) · **individual** (H)
- Aspect: secrets exposure; file deny-list
- Engagement: 9 reactions, 3 comments

**6.** "How can I exclude file for any operation in cursor as if the file would not exist? This is crucial to me, as some files might contain secrets that should never leave my machine."
- https://forum.cursor.com/t/cursorignore-not-being-used/7494/5 · Cursor forum reply · 2024-09-13 · chris-rl · **individual** (H)
- Aspect: secrets exposure
- Engagement: topic has 3,817 views, 33 posts and 57 likes; this post has 4 likes

**7.** "I now have to stop using cursor because I might have leaked internal company (luckily only non-critical development) secrets to external servers, both Cursor and Claude."
- https://forum.cursor.com/t/env-file-question/60165 · Cursor forum opening post (".env file question") · 2025-03-06 · SomeUser123 · **individual** (H)
- Aspect: secrets exposure
- Engagement: 11,986 views, 19 posts, 6 likes on this post

**8.** "Secrets management with Agents feels absent today." … "The agent can `cat .env`."
- https://news.ycombinator.com/item?id=46825555 · Ask HN: "How are you managing secrets with AI agents?" · 2026-01-30 · m-hodges · **individual** (H)
- Aspect: secrets exposure
- Engagement: 2 points, 5 comments

**9.** "Is it possible to ensure that the agents don't get access to sensitive directories in the device such as ~/.ssh and ~/.gnupg?"
- https://security.stackexchange.com/questions/287296/safety-of-cryptographic-keys-when-an-ai-agent-is-present-in-the-device · Security SE question body (title: "Safety of cryptographic keys when an AI agent is present in the device") · 2026-09-11 · Lakshit Singh Bisht · **individual** (H)
- Aspect: secrets exposure; agent file access
- Engagement: score 0, 103 views, 3 answers

### B. Sandboxing agent-run and LLM-generated code

**10.** "I would very much like to give the agent more independence with command execution, but cannot do so without more restrictions to what it can do."
- https://github.com/Aider-AI/aider/issues/4679 · GitHub issue body ("Sandboxing Support") · 2025-12-02 · dwt · **individual** (H)
- Aspect: sandboxing agent code. The same issue says docker "still cannot sandbox network access, which is a big problem".
- Engagement: 5 reactions, 4 comments

**11.** "It seems these two will blindly execute any code that is fed to it from the llm"
- https://github.com/langchain-ai/langchain/issues/1026 · GitHub issue body ("Security concerns") · 2023-02-13 · duckdoom4 · **individual** (H)
- Aspect: running LLM-generated code (this thread led to CVE-2023-29374)
- Engagement: 19 reactions, 31 comments

**12.** "I don't understand why people think it's a good idea to run coding agents as their own user on their own machines."
- https://news.ycombinator.com/item?id=45039319 · HN comment on the Nx/s1ngularity thread · 2025-08-27 · cowpig · **individual** (H)
- Aspect: sandboxing agent code; ambient user authority
- Engagement: parent story "Malicious versions of Nx and some supporting plugins were published" has 443 points and 433 comments

**13.** "I don't want it inadvertently deleting the wrong things or reading my SSH keys."
- https://news.ycombinator.com/item?id=46398588 · HN comment · 2025-12-27 · nl · **individual** (H)
- Context sentence: "I want to have a "container" … that I can let an AI agent run commands in but is safely sandboxed from the rest of my computer."
- Aspect: sandboxing agent code; secrets
- Engagement: parent story "Sandbox: Run untrusted AI code safely, fast" has 80 points and 29 comments

**14.** "There are a lot of AI tools which run with full permission to execute shell commands or similar."
- https://news.ycombinator.com/item?id=44666473 · HN comment on the Amazon Q wiper-prompt story · 2025-07-24 · dylnuge · **individual** (H)
- Aspect: agent runs with too much authority
- Engagement: parent story "AWS merges malicious PR into Amazon Q" has 63 points and 20 comments

**15.** "Giving agents enough permission to be useful seems at odds with least-privilege."
- https://news.ycombinator.com/item?id=46719363 · Ask HN: "Best practice securing secrets on local machines working with agents?" · 2026-01-22 · xinbenlv · **individual** (H)
- Aspect: least privilege for agents; secrets
- Engagement: 10 points, 12 comments

### C. MCP / tool permissions

**16.** "I shouldn’t have to decide between giving a model access to *everything* I can access, or *nothing*." … "MCP says every model is a sysadmin"
- https://news.ycombinator.com/item?id=44103863 · HN comment on "GitHub MCP exploited" · 2025-05-27 · brookst · **individual** (H)
- Aspect: MCP permissions; all-or-nothing access
- Engagement: parent story has 508 points and 297 comments

**17.** "I'd like to run the filesystem server in a read only mode."
- https://github.com/modelcontextprotocol/servers/issues/632 · GitHub issue body ("Configurable write permissions for filesystem server") · 2025-02-17 · gar1t · **individual** (H)
- Aspect: MCP permissions
- Engagement: 1 reaction, 2 comments

**18.** "people want general agents which do not have to be unlocked on a repository-by-repository basis. That's why they give them tokens with those access permissions, trusting the LLM blindly."
- https://news.ycombinator.com/item?id=44101043 · HN comment · 2025-05-26 · lbeurerkellner (Luca Beurer-Kellner, the Invariant Labs author of the GitHub-MCP report; the comment says "the approach we've been working on") · **researcher** (R)
- Aspect: MCP permissions; over-broad tokens
- Engagement: parent story has 508 points and 297 comments

**19.** "⚠️ Installing will grant access to everything on your computer."
- https://github.com/modelcontextprotocol/mcpb/issues/177 · This is Claude Desktop's install warning for MCP extensions, quoted in a proposal filed by "datHere, Inc. (qsv MCP Server maintainers)" · 2026-01-07 · **company** (V; they are asking for a fix)
- The same proposal adds: "The warning provides **no granularity** about actual filesystem access scope."
- Aspect: MCP permissions; knowing what a tool will touch before installing it
- Engagement: 1 reaction, 2 comments

### D. Dependencies, packages and CI actions that hold more authority than their job needs

**20.** "When declaring dependencies, you'd also declare the permissions of those dependencies. So a package like `tinycolor` would never need network or disk access."
- https://news.ycombinator.com/item?id=45260961 · HN comment on Shai-Hulud · 2025-09-16 · tarruda · **individual** (H)
- Aspect: dependency took more authority; per-package permissions
- Engagement: parent story "Shai-Hulud malware attack: Tinycolor and over 40 NPM packages compromised" has 1,233 points and 1,019 comments

**21.** "To me it's quite unexpected/scary that installing a package on my dev machine can execute arbitrary code before I ever have a chance to inspect the package"
- https://news.ycombinator.com/item?id=45263142 · HN comment on Shai-Hulud · 2025-09-16 · theodorejb · **individual** (H)
- Aspect: knowing what code does before running it; install-time authority
- Engagement: same parent story, 1,233 points and 1,019 comments

**22.** "\"All the executable files I run are trusted and have access to all my personal files\" doesn't work anymore in 2025."
- https://news.ycombinator.com/item?id=45049665 · HN comment on the Nx/s1ngularity thread · 2025-08-28 · fph · **individual** (H)
- Aspect: ambient authority; dependency took more authority
- Engagement: parent story has 443 points and 433 comments

**23.** "there's no reason an action like this ever needed network access."
- https://news.ycombinator.com/item?id=43369246 · HN comment on tj-actions/changed-files · 2025-03-15 · XorNot · **individual** (H)
- Aspect: network egress; CI action took more authority
- Engagement: parent story "Tj-actions/changed-files GitHub Action Compromised – used by over 23K repos" has 273 points and 298 comments

**24.** "Why does a compression library have the ability to \"install an audit hook into the dynamic linker\" or anything else that isn't compressing data?"
- https://news.ycombinator.com/item?id=39870691 · HN comment on the xz backdoor · 2024-03-30 · mac-chaffee · **individual** (H)
- Aspect: dependency took more authority
- Engagement: parent story "Backdoor in upstream xz/liblzma leading to SSH server compromise" has 4,549 points and 1,849 comments

**25.** "does npm allow the installation code to do whatever it wants on a system?"
- https://security.stackexchange.com/questions/234033/how-much-damage-can-a-malicious-package-do-with-just-npm-install-package · Security SE question body (title: "How much damage can a malicious package do with just "npm install <package>"?") · 2020-07-01 · user237586 · **individual** (H)
- Aspect: dependency took more authority; knowing what code does before running it
- Engagement: score 3, 631 views, 2 answers

### E. Researcher and company framings

**26.** "If your agent combines these three features, an attacker can easily trick it into accessing your private data and sending it to that attacker."
- https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/ · blog · 2025-06-16 · Simon Willison · **researcher** (R)
- Same post: "The problem with Model Context Protocol—MCP—is that it encourages users to mix and match tools from different sources that can do different things."
- Aspect: exfiltration ("lethal trifecta": private data + untrusted content + external communication)
- Engagement: HN "My Lethal Trifecta talk…" (item 44846922) has 430 points and 115 comments. "lethal trifecta" appears in 242 HN comments and 22 HN story titles.

**27.** "keeps credentials out of the agent's reach"
- Full sentence: "So he built IronCurtain, which sandboxes LLM-generated code, enforces policy in plain English, and keeps credentials out of the agent's reach."
- https://tldrsec.com/p/tldr-sec-321 · tl;dr sec newsletter #321 ("Sandboxing AI Agents…") · 2026-03-26 · Clint Gibler · **researcher** (R)
- Aspect: secrets exposure; sandboxing agent code
- Engagement: n/a

**28.** "Without network isolation, a compromised agent could exfiltrate sensitive files like SSH keys"
- https://www.anthropic.com/engineering/claude-code-sandboxing · company engineering blog ("Beyond permission prompts…") · published 2025-10-20 · Anthropic · **company** (V)
- Same post: permission prompts "can lead to ‘approval fatigue’, where users might not pay close attention to what they're approving"
- Aspect: network egress; secrets exposure
- Engagement: n/a

**29.** "Amazon Q Developer for VS Code Extension had an inappropriately scoped GitHub token in their CodeBuild configuration."
- https://aws.amazon.com/security/security-bulletins/AWS-2025-015/ · AWS security bulletin (CVE-2025-8217) · published 2025-07-23, updated 2025-07-25 · AWS · **company** (V)
- Aspect: CI credential took more authority
- Engagement: n/a

**30.** "the campaign weaponized installed AI CLI tools by prompting them with dangerous flags (--dangerously-skip-permissions, --yolo, --trust-all-tools) to steal filesystem contents"
- https://www.wiz.io/blog/s1ngularity-supply-chain-attack · Wiz blog (Merav Bar, Rami McCarthy) · 2025-08-27 · **company** (V)
- Aspect: an agent's own authority turned against the user; secrets exposure
- Engagement: n/a

**Mix of the 30:** 23 individual (#1-17, #20-25), 3 researcher (#18, #26, #27) and 4 company (#19, #28-30). 24 come from people who have the problem: the 23 individuals, of whom #5 is a project contributor, plus #19, a company asking for a fix.

### Additional verified phrasings (overflow; same verification standard)

| Quote | URL | Who | Aspect / engagement |
|---|---|---|---|
| "Currently, the permissions are granted at the level of tools. For example, either shell can run unrestricted, or it will ask me about every command." | https://github.com/aaif-goose/goose/issues/2659 (2025-05-24, mrzv) | individual | MCP/tool permissions granularity; 2 reactions |
| "Does CrewAI have some sort of sandbox implemented to help protect against malicious code execution?" | https://github.com/crewAIInc/crewAI/issues/67 (2024-01-06, SeaDude) | individual | sandboxing agent code; 3 reactions, 3 comments |
| "Tools that have write access should be handled more carefully than read-only tools." | https://github.com/modelcontextprotocol/python-sdk/issues/322 (2025-03-19, zilto) | individual | MCP permissions; 1 reaction |
| "MCP gives agents unrestricted access to every tool a server exposes by default." | https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/2498 (2026-03-30, AgentsID) | company | MCP permissions; 2 upvotes, 35 comments |
| "Why you shouldn't connect to untrusted MCP servers" (subtitle) | https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/ (2025-07-09, JFrog, Or Peles) | company | MCP trust (CVE-2025-6514) |
| "E.g. when I run `fd`, `rg` or similar such tool, why should it have Internet access?" | https://news.ycombinator.com/item?id=43369437 (2025-03-15, ashishb) | individual | network egress; tj-actions thread 273 pts/298 c |
| "probably 99% of project dependencies don't need I/O capabilities at all." | https://news.ycombinator.com/item?id=43372209 (2025-03-15, pdimitar) | individual | dependency authority; tj-actions thread |
| "no library should be able to open a file or do network requests without explicit granular permissions." | https://news.ycombinator.com/item?id=45261707 (2025-09-16, nahuel0x) | individual | dependency authority; Shai-Hulud thread 1,233 pts |
| "is there a way on mac to limit npm file access to the specific project?" | https://news.ycombinator.com/item?id=45261719 (2025-09-16, pingou) | individual | dependency authority |
| "The bigger issue here is that npm has such unrestricted and unsupervised access to the entire environment at all." | https://news.ycombinator.com/item?id=45264725 (2025-09-16, chuckadams) | individual | dependency authority |
| "The problem we have right now is that any linked code can do anything, both at build time and at runtime." | https://news.ycombinator.com/item?id=39872439 (2024-03-30, josephg) | individual | dependency authority; xz thread 4,549 pts |
| "Personally, I'd expect Claude Code not to have such far-reaching access across my filesystem if it only asks me for permission to work and run things within a given project." | https://news.ycombinator.com/item?id=45039232 (2025-08-27, CER10TY) | individual | agent filesystem scope; Nx thread 443 pts |
| "I realized it had read my .env file and performed operations on my API keys." | https://news.ycombinator.com/item?id=48273095 (2026-05-25, lelandfe) | individual | secrets; story "Microsoft Copilot Cowork Exfiltrates Files" 264 pts/49 c |
| "…thinking "fuck this" while they back out and make a non-expiring classic token with access to everything." | https://news.ycombinator.com/item?id=44104998 (2025-05-27, ljm) | individual | over-broad tokens; GitHub MCP thread 508 pts |
| "Why can an attacker's prompt access a repo the attacker does not have access to? That's the biggest issue here." | https://news.ycombinator.com/item?id=45557246 (2025-10-12, charcircuit) | individual | exfiltration/permissions; CamoLeak story 235 pts/43 c |
| "Don't use an MCP server with permission (capability) to do more than you want" | https://news.ycombinator.com/item?id=45046878 (2025-08-28, OJFord) | individual | MCP permissions; Nx thread |
| "That's what makes LLM security so infuriatingly difficult: we don't know how to fix these problems!" | https://news.ycombinator.com/item?id=44259295 (2025-06-12, simonw) | researcher | prompt injection; EchoLeak story 228 pts/86 c |
| "Is it safe to run arbitrary code in a GitHub Actions job whose GITHUB_TOKEN has no permissions?" | https://stackoverflow.com/questions/79274740 (2024-12-12, AAriam) | individual | CI authority/network; score 0, 66 views |
| "Recent ESLint hack or how can we protect ourselves from installing malicious npm packages?" | https://security.stackexchange.com/questions/189489 (2018-07-13, alecxe) | individual | dependency authority; score 8, 1,409 views |
| "Ask HN: AI agent devs, how do you sandbox LLM generated code?" | https://news.ycombinator.com/item?id=42132329 (2024-11-14, ATechGuy) | individual | sandboxing LLM code; 6 pts/3 c |

### Wording patterns that recur (my synthesis, not a quote)
- **Possessive, concrete nouns:** "my .env", "my SSH keys", "~/.ssh and ~/.gnupg", "my API keys", "my personal files", "my filesystem". People rarely write "credentials" in the abstract.
- **"Why does X have/need Y?"** An unrelated job holding a capability: "why should it have Internet access?", "Why does a compression library have the ability…", "no reason an action like this ever needed network access".
- **Dissatisfaction with all-or-nothing access:** "access to everything I can access, or nothing", "either shell can run unrestricted, or it will ask me about every command", "grant access to everything on your computer", "a non-expiring classic token with access to everything".
- **Asking to declare permissions up front:** "declare the permissions of those dependencies", "explicit granular permissions", "read only mode", "a file like .gitignore that… cline can't read".
- **Secrets "leaving the machine":** "secrets that should never leave my machine", "leaks them to your servers", "leaked … secrets to external servers".
- **"Before":** "before I ever have a chance to inspect", "Installing will grant…". People want to know what code will touch at install or run time.

---

## Part 2: What people call each incident

HN counts come from the hn.algolia.com API with `typoTolerance=false` and a quoted phrase. "titles" means `restrictSearchableAttributes=title`, `tags=story`; "comments" means `tags=comment`. Algolia tokenizes hyphens as spaces, so "Shai-Hulud" = "Shai Hulud" and "xz-utils" = "xz utils". Counts for generic tokens ("Amazon Q", "Ultralytics", "web3.js", "changed-files", "GitHub MCP", "postmark") include unrelated uses.

| # | Incident | Names in use (one URL each) | Most common (evidence) |
|---|---|---|---|
| 1 | mcp-remote RCE | **"CVE-2025-6514"** / **"mcp-remote"**: https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/ ("Critical RCE Vulnerability in mcp-remote: CVE-2025-6514 Threatens LLM Clients") | Little public discussion: 0 HN story titles for either name and 0 HN comments with the CVE id. The vendor name "CVE-2025-6514" is effectively the only name. |
| 2 | MCP tool poisoning | **"Tool Poisoning Attacks"**: https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks and HN https://news.ycombinator.com/item?id=43601612 · **"MCP Rug Pull"**: https://news.ycombinator.com/item?id=44206121 ("SchemaPin prevents "MCP Rug Pull" attacks") | **"tool poisoning"**: 11 HN titles, 19 comments. "rug pull"+MCP: 8 stories, 13 comments. |
| 3 | GitHub MCP private-repo leak | **"GitHub MCP exploited"**: https://news.ycombinator.com/item?id=44097390 (508 pts) · **"Toxic Agent Flows"**: https://invariantlabs.ai/blog/mcp-github-vulnerability ("so-called Toxic Agent Flows") · **"Claude 4 and GitHub MCP will leak your private GitHub repositories"**: https://news.ycombinator.com/item?id=44100082 (248 pts) · "toxic flow analysis": https://news.ycombinator.com/item?id=44737879 | Descriptive **"GitHub MCP exploit(ed)"**. "toxic agent flow" has 0 HN titles and 0 comments, so it is Invariant's own term. |
| 4 | postmark-mcp BCC backdoor | **"postmark-mcp"**: https://news.ycombinator.com/item?id=45395925 ("PSA: Declare an incident if someone on your team installed the postmark-MCP") · **"First Malicious MCP in the Wild" / "the Postmark Backdoor"**: https://news.ycombinator.com/item?id=45384340 · **"Fake Postmark MCP NPM package"**: https://news.ycombinator.com/item?id=45422805 | **"postmark-mcp"** (package name). 4 stories, 7 comments, max 14 pts. |
| 5 | Nx "s1ngularity" | **"s1ngularity"**: https://www.wiz.io/blog/s1ngularity-supply-chain-attack, https://nx.dev/blog/s1ngularity-postmortem (Nx's own postmortem "S1ngularity - What Happened…"), https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware ("s1ngularity: Popular Nx Build System Package Compromised with Data-Stealing Malware") · **"Nx compromised"**: https://news.ycombinator.com/item?id=45038653 (493 pts) · **"Nx attack"**: https://news.ycombinator.com/item?id=45059583 · **"the nx incident"**: https://news.ycombinator.com/item?id=45175608 | Split. Vendors and Nx use **"s1ngularity"** (6 HN titles, 10 comments, all low-point). HN's big threads say **"Nx"** ("Nx compromised" 9 titles incl. 493 pts; "Malicious versions of Nx…" 443 pts). A guide should say both: "the Nx (s1ngularity) attack". |
| 6 | Shai-Hulud npm worm | **"Shai-Hulud"**: https://news.ycombinator.com/item?id=45260741 (1,233 pts) · **"Shai-Hulud 2.0"**: https://news.ycombinator.com/item?id=46059348 · **"SHA1-Hulud – The Second Coming"**: https://news.ycombinator.com/item?id=46033291 · **"npm worm"**: https://news.ycombinator.com/item?id=47104510 ("Shai-Hulud-Style NPM Worm…") | **"Shai-Hulud"** by far: 55 HN titles, 160 comments; titles of 1,233, 1,038 and 391 pts. |
| 7 | tj-actions/changed-files | **"tj-actions/changed-files"**: https://news.ycombinator.com/item?id=43367987 (273 pts/298 c) · **"CVE-2025-30066"**: https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction · **"the tj-actions attack"**: https://news.ycombinator.com/item?id=43478659 · **"tj-actions hack"**: https://news.ycombinator.com/item?id=43926389 · related **"reviewdog"**: https://news.ycombinator.com/item?id=43393002 | **"tj-actions"** / "tj-actions/changed-files": 7 titles, 51 comments. The CVE id has 0 HN comments. |
| 8 | @solana/web3.js backdoor | **"Solana/Web3.js" supply chain attack**: https://news.ycombinator.com/item?id=42312192 · **"Solana Web3.js Library Backdoored"**: https://news.ycombinator.com/item?id=42322739 | Descriptive **"Solana web3.js (backdoor / supply chain attack)"**. Low engagement: 3 titles, max 17 pts. "web3.js backdoor" has 0 comments. |
| 9 | Ultralytics PyPI compromise | **"Supply-chain attack analysis: Ultralytics"**: https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/ · **"Analysis of supply-chain attack on Ultralytics"**: https://news.ycombinator.com/item?id=42388607 (98 pts) · **"Ultralytics AI model hijacked… cryptominer"**: https://news.ycombinator.com/item?id=42351722 · **"the Ultralytics workflow vulnerability"**: https://news.ycombinator.com/item?id=42356345 · "Ultralytics attack": https://news.ycombinator.com/item?id=47582653 | **"the Ultralytics (supply-chain) attack"**. No catchy name exists. |
| 10 | xz-utils backdoor | **"xz backdoor"**: https://news.ycombinator.com/item?id=39877267 (1,323 pts) · **"xz Utils backdoor"**: https://news.ycombinator.com/item?id=39891607 · **"Jia Tan"**: https://news.ycombinator.com/item?id=39918340 · **"CVE-2024-3094"**: https://news.ycombinator.com/item?id=39896541 · **"backdoor in upstream xz/liblzma"** (original report): https://www.openwall.com/lists/oss-security/2024/03/29/4 · "xz attack": https://news.ycombinator.com/item?id=49735542 · "xz hack": https://news.ycombinator.com/item?id=49387515 | **"the xz backdoor"**: 60 titles, 296 comments. "xz utils backdoor": 90 comments. "xz attack": 81. "xz incident": 38. "xz hack": 24. **"Jia Tan"** (the persona) appears in 384 comments and is still used in 2026 as shorthand. The CVE id is rare (14 comments). |
| 11 | Amazon Q extension wiper prompt | **"malicious PR into Amazon Q"**: https://news.ycombinator.com/item?id=44663016 · **"malicious 'wiping' command"**: https://news.ycombinator.com/item?id=44675557 · **"CVE-2025-8217"**: https://aws.amazon.com/security/security-bulletins/AWS-2025-015/ · **"Malicious script injected into Amazon Q Developer for VS Code"**: https://news.ycombinator.com/item?id=44782618 | No settled name. Descriptive "Amazon Q malicious PR / wiper". The CVE id has 0 HN mentions. Max 75 pts. |
| 12 | CircleCI Jan 2023 breach | **"CircleCI security alert: Rotate any secrets"**: https://news.ycombinator.com/item?id=34255319 (304 pts) · **"CircleCI Jan 4, 2023 security incident"**: https://circleci.com/blog/jan-4-2023-incident-report/ · **"CircleCI breach"**: https://news.ycombinator.com/item?id=34390449 · "CircleCI says hackers stole encryption keys…": https://news.ycombinator.com/item?id=34386017 (390 pts) | No dominant name. "CircleCI incident" / "CircleCI breach" each have about 3-4 titles and 2-3 comments. Remembered as "rotate all your CircleCI secrets". |
| 13 | EchoLeak (M365 Copilot) | **"EchoLeak"**: https://news.ycombinator.com/item?id=44250774 (228 pts/86 c) · **"0-click / zero-click AI"**: https://news.ycombinator.com/item?id=44383995 ("Zero-click AI data leak flaw uncovered in Microsoft 365 Copilot") · **"CVE-2025-32711"**: https://news.ycombinator.com/item?id=44592024 | **"EchoLeak"**: 2 titles, 7 comments. The CVE id has 3 comments. |
| 14 | CamoLeak (GitHub Copilot Chat) | **"CamoLeak"**: https://news.ycombinator.com/item?id=45553422 (235 pts/43 c) | **"CamoLeak"** is the only name. 2 titles, 0 comments use it. |
| 15 | Package hallucination | **"Slopsquatting"**: https://news.ycombinator.com/item?id=44810695 (105 pts/49 c) · **"Package Hallucinations"**: https://news.ycombinator.com/item?id=41703726 · **"AI package hallucination"**: https://news.ycombinator.com/item?id=36226200 · **"hallucinated packages"**: https://news.ycombinator.com/item?id=44165780 | **"slopsquatting"**: 7 titles, 14 comments. "package hallucination": 7 titles, 1 comment. "hallucinated package" 9 comments and "hallucinated packages" 8 comments (these overlap); "hallucinated" packages 5 titles. |

Related umbrella term: **"lethal trifecta"** (Simon Willison) is used far more than any single MCP incident name: 22 HN titles and 242 comments. Examples: https://news.ycombinator.com/item?id=44846922 (430 pts), https://news.ycombinator.com/item?id=45387155 ("How to stop AI's "lethal trifecta"", 115 pts/116 c), https://news.ycombinator.com/item?id=45223102 ("Show HN: An MCP Gateway to block the lethal trifecta").

---

## Part 3: Demand evidence (engagement)

**HN stories (points / comments):**

| Story | Points / comments |
|---|---|
| xz backdoor (39865810) | 4,549 / 1,849 |
| Shai-Hulud (45260741) | 1,233 / 1,019 |
| Shai-Hulud Returns (46032539) | 1,038 / 775 |
| GitHub MCP exploited (44097390) | 508 / 297 |
| Nx compromised, "malware uses Claude code CLI" (45038653) | 493 / 39 |
| Malicious versions of Nx (45034496) | 443 / 433 |
| Lethal Trifecta talk (44846922) | 430 / 115 |
| CircleCI "hackers stole encryption keys" (34386017) | 390 / 147 |
| CircleCI "Rotate any secrets" (34255319) | 304 / 84 |
| tj-actions (43367987) | 273 / 298 |
| Microsoft Copilot Cowork Exfiltrates Files (48272354) | 264 / 49 |
| CamoLeak (45553422) | 235 / 43 |
| EchoLeak (44250774) | 228 / 86 |
| "How to stop AI's lethal trifecta" (45387155) | 115 / 116 |
| Slopsquatting (44810695) | 105 / 49 |
| Ultralytics analysis (42388607) | 98 / 31 |
| "Sandbox: Run untrusted AI code safely, fast" (46326281) | 80 / 29 |
| Amazon Q wiping command (44675557) | 75 / 12 |
| postmark-mcp PSA (45395925) | 14 / 4 |

User-written Ask HNs are small: the secrets-with-agents Ask HN has 10 / 12, and "how do you sandbox LLM generated code" has 6 / 3.

**GitHub issues (reactions / comments):**

| Issue | Reactions / comments |
|---|---|
| anthropics/claude-code#32733 "[FEATURE] Secure secrets injection for Claude Code on the web" | 208 (174 +1) / 10 |
| anthropics/claude-code#1304 "Need for dedicated .claudeignore file…" | 79 / 32 |
| anthropics/claude-code#401 (.env loaded into bash) | 54 / 64 |
| anthropics/claude-code#29910 (built-in secrets management) | 45 / 15 |
| langchain#1026 | 19 / 31 |
| anthropics/claude-code#2637 "Secure env variables by adding .claudeignore" | 12 / 8 |
| codex#13778 | 10 / 7 |
| cline#1359 | 9 / 3 |
| aider#4679 | 5 / 4 |

Counter-signal: anthropics/claude-code#5105 "[FEATURE REQUEST] Allow Claude Code to access gitignored files" has 110 reactions and 60 comments. Many users also want agents to see more files, so restriction features must not get in the way.

**Cursor forum:**
- ".env file question": 11,986 views
- "Environment Secrets and Code Security": 6,878 views
- ".cursorignore not being used": 3,817 views, 57 likes

**Stack Exchange:**
- SO "How can I safely run untrusted python code?" (2015): 4,868 views
- Security SE ESLint/npm question: 1,409 views
- Security SE "npm install damage": 631 views
- Security SE AI-agent keys question (2026-09-11): 103 views

Stack Exchange has very few AI-agent-specific questions. Title searches for "LLM", "AI agent" and "agent sandbox" on security.SE and SO returned almost nothing on this topic. The problem is discussed on HN, GitHub trackers and vendor forums instead.

---

## Blocked / not loaded

- **Reddit, all routes blocked. No Reddit quotes are used.**
  - `https://old.reddit.com/r/ClaudeAI/search.json?q=.env+secrets&restrict_sr=1&sort=top&t=all&limit=10` returned HTTP 302 to `https://old.reddit.com/login/?reason=lor2…` (login wall).
  - `https://www.reddit.com/r/mcp/search.json?q=security&restrict_sr=1&sort=top&limit=10` returned HTTP 403 with a "Blocked" page.
  - `https://api.reddit.com/r/mcp/search?q=security…` returned HTTP 403.
  - WebFetch refused both `https://old.reddit.com/r/mcp/search?...` and `https://www.reddit.com/r/ClaudeAI/search/?q=.env%20secrets` ("unable to fetch from old.reddit.com / www.reddit.com").
  - The PullPush mirror (`https://api.pullpush.io/reddit/search/submission/?q=sandbox&subreddit=mcp`) returned HTTP 429: "This website does not provide free scraping resources for agents."
  - WebSearch with `site:reddit.com` returned no reddit.com results.
- **Koi Security postmark-mcp post:** `https://www.koi.security/blog/postmark-mcp-npm-malicious-backdoor-email-theft` now serves a Palo Alto Networks marketing page. The original post was not loaded, so its names come only from HN titles.
- **tl;dr sec:** pages loaded but show "Login / Subscribe". Only the text visible in the page (#321) was used.
- **Harness tj-actions blog:** a search snippet titled it "Assessing the tj-actions supply chain attack…", but the loaded page's title is "GitHub Actions Supply Chain Attack: tj-actions Fix". I did not use the snippet title.
- **Not found verbatim:** the example phrasing "why does a VS Code extension have permission to delete my files" did not turn up on HN (Algolia comment search after July 2025). The closest verified wording is #14 above.
- **Not covered:** Risky Business, and The Register and Ars comment sections.
