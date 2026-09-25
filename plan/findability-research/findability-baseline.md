# Findability baseline

Where Sabline stands in search on 2026-09-25, before any findability work: what
comes up for thirty ways people really describe the problem Sabline addresses,
and what comes up for the project's two names. It is a baseline to measure later
changes against, not a plan.

> [!NOTE]
> **Taken** 2026-09-25. **Search tool:** the WebSearch tool in Claude Code
> (Anthropic's hosted web search; US region; it returns 9-10 results a query and
> does not say which index it uses, so these are not Google's rankings).
> **Not reachable:** Google Search and DuckDuckGo by direct fetch (Google served
> a page with no results; DuckDuckGo served a CAPTCHA), and all four AI
> assistants (below). Each query was run once; a result list from a web search
> moves day to day, so read one run as a sample, not a measurement.

## What it shows

- **Sabline appears in none of the 33 problem searches**, under either name:
  the 30 phrasings below and three written in Sabline's own terms. That
  includes "language where function signatures declare effects runtime refuses
  AI-written code", which is close to the project's own one-line description;
  its top result is an unrelated arXiv paper (ETAS).
- **The bare names find something else.** "Sabline" returns ten pages about the
  plant (*Arenaria*, French common name) and a French singer; "Velaris" returns
  a fictional city, a customer-success company, a Viasat product and a lab
  automation group. Neither shows the project in its first 9-10 results.
- **Qualified names find only the repositories.** "Sabline programming
  language" returns the repository and nine of its pull-request and release
  pages; no page on sabline.dev appears for any query, including
  `site:sabline.dev`.
- **Where the problem searches go instead:** for agent-specific phrasings, the
  agent's own issue tracker ranks first (claude-code #401, #9637, #29910;
  codex #13778); vendor articles (knostic.ai, fast.io, WorkOS, ThreatLocker,
  NVIDIA) and dev.to posts fill the rest; arXiv papers rank for
  research-flavoured wording. **Phrasings about packages and dependencies
  declaring what they may touch (20, 22, 23) return mostly irrelevant pages**:
  the demand is visible on Hacker News, the answers are not in the results.

## The names

| Query | Top results, in order | The project? |
|---|---|---|
| `Sabline` | fr.wiktionary.org *sabline*; calanques-parcnational.fr *Sabline de Provence*; en.wikipedia.org *Sablons*; *Sablon*; florealpes.com *Arenaria serpyllifolia*; truffaut.com (two plant listings); senteursduquercy.com *Arenaria montana*; *Germaine Sablon*; florealpes.com *Arenaria multicaulis* | No |
| `Velaris` | acourtofthornsandroses.fandom.com *Velaris*; linkedin.com/company/velaris; velaris.io *The AI Customer Success Platform*; an Instagram post; viasat.com *Velaris, Satellite connectivity for UAVs*; velariscity.com; velaris.com (lab automation group); en.wikipedia.org *Polaris (disambiguation)*; goodreads.com | No |
| `Sabline programming language` | github.com/gowrishankar-infra/sabline-lang; PR #92; release v8.6.0; PR #103; PR #94; pypi.org/project/sabline-lang; PRs #98, #113, #105, #108 | Yes, all ten |
| `Velaris programming language` | github.com/gowrishankar-infra/velaris-lang (redirects); pypi.org/project/velaris-lang/4.3.2; releases v4.2.1, v7.1.1; sabline-lang repository; releases v8.2.0, v7.2.0; VS Code Marketplace *Velaris*; github.com/VelarOS-AI/VelarScript | Yes, eight of nine |
| `sabline.dev` | release v8.6.0; PR #92; PR #102; sabline-canary; pypi velaris-lang 8.6.0; sabline-spec; pypi sabline-lang 8.6.0; sabline-lang; PR #105 | Repositories only, no sabline.dev page |
| `site:sabline.dev` | sabline-canary; release v8.6.0; PR #92; pypi sabline-lang 8.6.0; PR #102; sabline-spec; VS Code Marketplace *Sabline*; en.wikipedia.org *Sablons*; sabline-lang | No sabline.dev page |

What a reader lands on from a name search is a pull request titled, for
example, *decisions/0006: decided - four accepted into M2, M4 and M6, two held
back* - written for the project, not for someone arriving with the problem.

### Other things with these names

| Name | What | Competes how |
|---|---|---|
| Sabline | *Arenaria* (sandwort), the French common name; garden-centre listings | Owns the bare name in results; different field entirely |
| Sabline | github.com/fikiribienvenuregis/Sabline | An empty repository, 0 stars; no conflict today |
| Velaris | velaris.io, a customer-success platform | Same market; the reason for the 8.6.0 rename |
| Velaris | The city in *A Court of Thorns and Roses* | Owns the bare name in results |
| Velaris | Viasat's UAV satellite service; velaris.com lab automation | Unrelated fields |
| Velaris | github.com/jiaweifreshair/velaris-agent (16 stars), a "personal decision engine" agent | Same name inside the AI-agent space |
| Velar- | github.com/VelarOS-AI/VelarScript, "an extensible application-layer programming language for the AI era" (its GitHub description) | Near-name in the same results as the old name |

Neither name has ever appeared on Hacker News: an exact search
(`typoTolerance=false`) for `sabline`, `sabline-lang` and `velaris-lang` returns
0 hits, and the same search for `velaris` returns 3, all the word "velarised". `sabline` and `velaris`
are not taken on npm; `sabline-lang` and `velaris-lang` are this project's.

## The thirty phrasings

Each phrasing is quoted from the page linked, as its author wrote it. **Who**
is individual, company or researcher. **Query** is what was searched: the
phrasing as written, or its searchable part where the sentence was long. The
top five results are listed in the order returned; none of the 30 lists (9-10
results each) contains Sabline or Velaris.

### Secrets: agents reading `.env`, keys and tokens

**1.** "[BUG] Claude loads my projects .env into its bash environment (!)" -
[claude-code #401](https://github.com/anthropics/claude-code/issues/401),
2025-03-08, individual. 54 reactions, 64 comments.
Query: `Claude loads my projects .env into its bash environment`
1. claude-code #401 (the issue itself)
2. claude-code #16619, *.env file automatically loaded into bash environment for tool calls*
3. knostic.ai, *Claude Code Automatically Loads .env Secrets, Without Telling You*
4. claude-code #3403, *unexpected loading of project's .env file when executing shell commands*
5. github.com/midwire/bash.env, CLAUDE.md

**2.** "the endpoint returns an auth error and ur bot starts searching willy nilly
for auth credentials to stuff into a curl command" -
[claude-code #9637](https://github.com/anthropics/claude-code/issues/9637),
2025-10-16, individual.
Query: `Claude Code reads secrets out of .env files and leaks them` (the issue's title)
1. claude-code #9637 (the issue itself)
2. claude-code #58173, *Claude repeatedly leaks secrets from .env files despite explicit memory rule*
3. knostic.ai, *From .env to Leakage: Mishandling of Secrets by Coding Agents*
4. dev.to, *Claude Code Is Reading Your .env File Right Now*
5. knostic.ai, *Claude Code Automatically Loads .env Secrets*

**3.** "Claude Code has no first-class way to handle secrets." -
[claude-code #29910](https://github.com/anthropics/claude-code/issues/29910),
2026-03-01, individual. 45 reactions.
Query: the phrasing as written
1. claude-code #29910 (the issue itself)
2. code.claude.com, *Best practices for Claude Code*
3. backslash.security, *Claude Code Security Best Practices*
4. egghead.io, *Protect Secrets from Being Read by Claude Code*
5. noboxdev.com, *Claude Code Security Best Practices*

**4.** "Codex can read `.env` files inside the workspace (e.g. via `cat .env`)
without any denylist or explicit confirmation." -
[codex #13778](https://github.com/openai/codex/issues/13778), 2026-03-06,
individual.
Query: `Codex can read .env files inside the workspace without any denylist`
1. codex #13778 (the issue itself)
2. codex discussion #5523, *How can sensitive files remain uncompromised when using Codex CLI?*
3. dev.to, *Eight coding agents, eight deny-list formats*
4. dev.to, *AI Coding Agent Security: Practical Guardrails for Claude Code, Copilot, and Codex*
5. learn.chatgpt.com, *Permissions*

**5.** "we need a file like .gitignore that allows the user to define files that
cline can't read." - [cline #1359](https://github.com/cline/cline/issues/1359),
2025-01-21, individual.
Query: the phrasing as written
1. docs.cline.bot, *.clineignore*
2. cline discussion #850
3. cline's own .gitignore
4. freecodecamp.org, *.gitignore File*
5. docs.github.com, *Ignoring files*

**6.** "some files might contain secrets that should never leave my machine." -
[Cursor forum](https://forum.cursor.com/t/cursorignore-not-being-used/7494/5),
2024-09-13, individual. Topic: 3,817 views.
Query: `exclude file in Cursor, secrets that should never leave my machine`
1. truefoundry.com, *Cursor Security: Risks, Privacy & Best Practices*
2. rapidevelopers.com, *Prevent Code Leaks in Cursor*
3. medium.com (Artem Kuchumov), *.cursorignore File Every Developer Needs*
4. tothenew.com, *The Developer's Cursor Checklist*
5. simplyscan.io, *Managing Your Cursor Library*

**7.** "I might have leaked internal company (luckily only non-critical
development) secrets to external servers, both Cursor and Claude." -
[Cursor forum](https://forum.cursor.com/t/env-file-question/60165),
2025-03-06, individual. 11,986 views.
Query: `I might have leaked internal company secrets to external servers, both Cursor and Claude`
1. knostic.ai, *How AI Assistants Leak Secrets in Your IDE*
2. knostic.ai, *From .env to Leakage*
3. ironpeak.be, *Leaking secrets from the claud*
4. hackernoon.com, *What the Claude Code Leak Reveals About Hidden AI Security Risks*
5. venturebeat.com, *Claude Code's source code appears to have leaked* (a different "leak")

**8.** "Secrets management with Agents feels absent today." -
[Ask HN](https://news.ycombinator.com/item?id=46825555), 2026-01-30, individual.
Query: `How are you managing secrets with AI agents` (the thread's title)
1. fast.io, *AI Agent Secrets Management: Best Practices for 2026*
2. the Ask HN thread itself
3. docs.aws.amazon.com, *Use secrets safely with AI Coding Agents*
4. workos.com, *How to manage API keys, tokens, and secrets for AI agents*
5. fast.io, *7 Best Secret Management Tools for AI Agents*

**9.** "Is it possible to ensure that the agents don't get access to sensitive
directories in the device such as ~/.ssh and ~/.gnupg?" -
[Security Stack Exchange](https://security.stackexchange.com/questions/287296/safety-of-cryptographic-keys-when-an-ai-agent-is-present-in-the-device),
2026-09-11, individual. 103 views.
Query: `ensure AI agents don't get access to sensitive directories such as ~/.ssh and ~/.gnupg`
1. dev.to, *Your AI Agent Has Root Access to Your Laptop. Here's How to Fix That.*
2. arxiv.org 2605.18991, *Agent Security is a Systems Problem*
3. threatlocker.com, *Credential security and AI agents*
4. arxiv.org 2512.15688, *BashArena*
5. nono.sh, *How to Isolate AI Agents with Kernel-Level Security*

### Sandboxing agent-run and model-written code

**10.** "I would very much like to give the agent more independence with command
execution, but cannot do so without more restrictions to what it can do." -
[aider #4679](https://github.com/Aider-AI/aider/issues/4679), 2025-12-02,
individual.
Query: `give the agent more independence with command execution but restrict what it can do sandboxing`
1. charmbracelet/crush #1541, *Support Sandboxing*
2. aider #4679 (the issue itself)
3. arxiv.org 2606.13474
4. developer.nvidia.com, *Practical Security Guidance for Sandboxing Agentic Workflows*
5. augmentcode.com, *What Is an Agent Execution Sandbox?*

**11.** "It seems these two will blindly execute any code that is fed to it from
the llm" - [langchain #1026](https://github.com/langchain-ai/langchain/issues/1026),
2023-02-13, individual. 19 reactions, 31 comments.
Query: `blindly execute any code that is fed to it from the llm`
1. medium.com (Philipp Kaindl), *Secure execution of code generated by Large Language Models*
2. neuraltrust.ai, *Code Injection in LLM Applications*
3. moveworks.com, *Secure code execution in LLMs*
4. apxml.com, *LLM Code Execution Tools & Sandboxing*
5. cloudsecurityalliance.org, *LLMs Writing Code? Cool. LLMs Executing It? Dangerous*

**12.** "I don't understand why people think it's a good idea to run coding agents
as their own user on their own machines." -
[HN, Nx thread](https://news.ycombinator.com/item?id=45039319), 2025-08-27,
individual.
Query: `why run coding agents as their own user on their own machines`
1. dev.to, *Your AI Agents Need Their Own Computers*
2. coder.com, *Coder's AI Stack*
3. dev.to, *Why AI Agents Should Have Their Own Computers*
4. dev.to, *Self-hosting an AI coding agent workbench*
5. langchain.com, *Give your agent its own computer*

**13.** "I don't want it inadvertently deleting the wrong things or reading my SSH
keys." - [HN](https://news.ycombinator.com/item?id=46398588), 2025-12-27,
individual.
Query: `I don't want it inadvertently deleting the wrong things or reading my SSH keys AI agent sandbox`
1. fast.io, *AI Agent Sandbox Environment - Setup Guide 2026*
2. developer.nvidia.com, *Practical Security Guidance for Sandboxing Agentic Workflows*
3. firecrawl.dev, *AI Agent Sandbox: How to Safely Run Autonomous Agents in 2026*
4. levelup.gitconnected.com, *A Technical Guide to AI Agent Sandboxing*
5. arxiv.org 2510.21236, *AgentBound: Securing Execution Boundaries of AI Agents*

**14.** "There are a lot of AI tools which run with full permission to execute
shell commands or similar." -
[HN, Amazon Q thread](https://news.ycombinator.com/item?id=44666473),
2025-07-24, individual.
Query: `AI tools which run with full permission to execute shell commands`
1. eclipse-theia/theia #16772, *Shell Command Execution Tool for AI Agents*
2. lmstudio.ai, *shell-command-runner*
3. dev.to, *I'm an AI With Shell Access. Here's a Tool That Guards What I Can Do.*
4. youtrack.jetbrains.com LLM-26405
5. docs.celesto.ai, *Shell Tool*

**15.** "Giving agents enough permission to be useful seems at odds with
least-privilege." - [Ask HN](https://news.ycombinator.com/item?id=46719363),
2026-01-22, individual.
Query: the phrasing as written
1. threatlocker.com, *The principle of least privilege for AI agents*
2. zenity.io, *Least Agency: Why Least Privilege Isn't Enough to Secure AI Agents*
3. strongdm.com, *Principle of Least Privilege Explained*
4. cequence.ai, *Least Privilege Access for AI Agents*
5. modality.org, *The Permission Problem*

### MCP and tool permissions

**16.** "I shouldn't have to decide between giving a model access to *everything*
I can access, or *nothing*." -
[HN, GitHub MCP thread](https://news.ycombinator.com/item?id=44103863),
2025-05-27, individual. Thread: 508 points, 297 comments.
Query: `MCP giving a model access to everything I can access, or nothing`
1. activepieces.com, *Model Context Protocol (MCP): Everything You Need To Know*
2. medium.com, *Model Context Protocol (MCP) for dummies*
3. vercel.com, *MCP explained: An FAQ*
4. modelcontextprotocol.io, *What is the Model Context Protocol?*
5. descope.com, *What Is the Model Context Protocol*

All ten are general MCP explainers; none addresses the complaint.

**17.** "I'd like to run the filesystem server in a read only mode." -
[modelcontextprotocol/servers #632](https://github.com/modelcontextprotocol/servers/issues/632),
2025-02-17, individual.
Query: `run the MCP filesystem server in a read only mode`
1. github.com/LincolnBurrows2017/filesystem-mcp
2. mcpservers.org, *Readonly File System MCP Server*
3. docs.stacklok.com, *Filesystem MCP server guide*
4. github.com/danielsuguimoto/readonly-filesystem-mcp
5. mcpmarket.com, *Readonly Filesystem*

**18.** "people want general agents which do not have to be unlocked on a
repository-by-repository basis. That's why they give them tokens with those
access permissions, trusting the LLM blindly." -
[HN](https://news.ycombinator.com/item?id=44101043), 2025-05-26, researcher
(Luca Beurer-Kellner, Invariant Labs).
Query: `agents given tokens with broad access permissions, trusting the LLM blindly`
1. workos.com, *API security best practices for the age of AI agents*
2. stytch.com, *Handling AI agent permissions*
3. osohq.com, *AI Agents and Context-Aware Permissions*
4. axiomatics.com, *Securing AI*
5. truefoundry.com, *LLM Access Control*

**19.** "⚠️ Installing will grant access to everything on your computer." -
Claude Desktop's warning, quoted in
[modelcontextprotocol/mcpb #177](https://github.com/modelcontextprotocol/mcpb/issues/177),
2026-01-07, company (datHere, asking for a fix).
Query: `Installing will grant access to everything on your computer MCP extension`
1. forums.realmacsoftware.com, *MCP Server install Claude Desktop*
2. mcpb #177 (the issue itself)
3. learn.microsoft.com, *Register an MCP server from an app with package identity*
4. learn.microsoft.com, *Securely containing MCP servers on Windows*
5. modelcontextprotocol.io, *Connect to local MCP servers*

### Packages, dependencies and CI actions with more authority than the job

**20.** "When declaring dependencies, you'd also declare the permissions of those
dependencies. So a package like `tinycolor` would never need network or disk
access." - [HN, Shai-Hulud thread](https://news.ycombinator.com/item?id=45260961),
2025-09-16, individual. Thread: 1,233 points, 1,019 comments.
Query: `declare the permissions of dependencies so a package would never need network or disk access`
1. david-gilbertson.medium.com, *npm package permissions - an idea*
2. pkg.go.dev, gio `app/permission` (a fork)
3. pkg.go.dev, gio `app/permission` (another fork)
4. pkg.go.dev, gio `app/permission` (another fork)
5. gio.realy.lol, `app/permission`

**21.** "To me it's quite unexpected/scary that installing a package on my dev
machine can execute arbitrary code before I ever have a chance to inspect the
package" - [HN, Shai-Hulud thread](https://news.ycombinator.com/item?id=45263142),
2025-09-16, individual.
Query: `installing a package can execute arbitrary code before I have a chance to inspect it`
1. nodesource.com, *Why Installing an npm Package Can Execute Code on Your Machine*
2. medium.com, *Pipask: Check Your Python Dependencies Before They Bite*
3. nhimg.org, *What breaks when npm package installs are allowed to execute code before inspection?*
4. dev.to, *Scanning npm Packages for Malware Before You Install*
5. medium.com (Ochrona), *Arbitrary Code Execution During Python Package Installation*

**22.** "\"All the executable files I run are trusted and have access to all my
personal files\" doesn't work anymore in 2025." -
[HN, Nx thread](https://news.ycombinator.com/item?id=45049665), 2025-08-28,
individual.
Query: `all the executable files I run are trusted and have access to all my personal files`
1. help.comodo.com, *Trusted Files* (three antivirus help pages)
2. support.microsoft.com, *Trusted documents*
3. devhut.net, *Microsoft Office Trusted Documents*

Nothing in the ten results is about the problem.

**23.** "there's no reason an action like this ever needed network access." -
[HN, tj-actions thread](https://news.ycombinator.com/item?id=43369246),
2025-03-15, individual. Thread: 273 points, 298 comments.
Query: `no reason a GitHub action like this ever needed network access`
1. drdroid.io, *GitHub Actions Failed to access repository*
2. drdroid.io, *GitHub Actions Job failed due to network issues*
3. repost.aws, *GitHub Actions on EC2 without internet access*
4. dev.to, *Can't Access a Service Container in GitHub Actions?*
5. github.blog, *Review network access settings for the self-hosted runners*

Nothing in the top five is about an action holding authority it did not need;
GitHub community discussion #24975, *Is there a way to run an action step
without networking?*, is eighth.

**24.** "Why does a compression library have the ability to \"install an audit
hook into the dynamic linker\" or anything else that isn't compressing data?" -
[HN, xz thread](https://news.ycombinator.com/item?id=39870691), 2024-03-30,
individual. Thread: 4,549 points, 1,849 comments.
Query: `why does a compression library have the ability to install an audit hook into the dynamic linker`
1. github.com/matinraayai/audit_hook
2. linux.die.net, *rtld-audit(7)*
3. man.archlinux.org, *rtld-audit(7)*
4. thecout.com, *Backdooring Linux with Linker Envs the right way*
5. a USPTO patent

**25.** "does npm allow the installation code to do whatever it wants on a
system?" - [Security Stack Exchange](https://security.stackexchange.com/questions/234033/how-much-damage-can-a-malicious-package-do-with-just-npm-install-package),
2020-07-01, individual. 631 views.
Query: `how much damage can a malicious package do with just npm install` (the question's title)
1. microsoft.com security blog, *Malicious npm packages abuse dependency confusion* (2026-05-29)
2. stepsecurity.io, *Malicious node-ipc Versions Published to npm*
3. unit42.paloaltonetworks.com, *The npm Threat Landscape*
4. fortinet.com, *Malicious Packages Hidden in NPM*
5. docs.snyk.io, *Malicious packages*

### Researcher and company framings

**26.** "If your agent combines these three features, an attacker can easily
trick it into accessing your private data and sending it to that attacker." -
[Simon Willison, *The lethal trifecta*](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/),
2025-06-16, researcher. "lethal trifecta" is in 22 HN titles and 242 comments.
Query: `lethal trifecta AI agent access private data and send it to attacker`
1. osohq.com, *Understanding the Lethal Trifecta of AI Agents*
2. simonwillison.net, *The lethal trifecta for AI agents* (the source)
3. hiddenlayer.com, *How the Lethal Trifecta Expose Agentic AI*
4. labs.cloudsecurityalliance.org, *The AI Agent Lethal Trifecta*
5. arxiv.org 2512.08104, *AgentCrypt*

**27.** "keeps credentials out of the agent's reach" -
[tl;dr sec #321](https://tldrsec.com/p/tldr-sec-321), 2026-03-26, researcher
(Clint Gibler).
Query: `sandbox LLM-generated code and keep credentials out of the agent's reach`
1. virtuslab.com, *Sandboxing LLM coding agents: part1*
2. octopus.com, *Sandboxing AI Agents*
3. armosec.io, *AI Agent Sandboxing & Progressive Enforcement*
4. blaxel.ai, *Sandbox Management for AI Coding Agents*
5. huggingface.co, smolagents *Secure code execution*

**28.** "Without network isolation, a compromised agent could exfiltrate
sensitive files like SSH keys" -
[Anthropic engineering blog](https://www.anthropic.com/engineering/claude-code-sandboxing),
2025-10-20, company.
Query: the phrasing as written
1. anthropic.com, *Making Claude Code more secure and autonomous with sandboxing* (the source)
2. docs.gitlab.com, *Security threats in agentic systems*
3. arxiv.org 2604.02837, *Towards Secure Agent Skills*
4. arxiv.org 2604.10577, *The Blind Spot of Agent Safety*
5. mintmcp.com, *How to Sandbox Claude Code*

**29.** "Amazon Q Developer for VS Code Extension had an inappropriately scoped
GitHub token in their CodeBuild configuration." -
[AWS-2025-015](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/),
2025-07-23, company.
Query: `inappropriately scoped GitHub token CodeBuild Amazon Q Developer extension`
1. aws.amazon.com, AWS-2025-015 (the source)
2. github.com/aws/aws-toolkit-vscode advisory GHSA-7g7f-ff96-5gcw
3. reversinglabs.com, *How AWS averted an AI coding supply chain disaster*
4. itnews.com.au, *Code syntax error prevented hacked AWS AI dev extension from running*
5. techtarget.com, *AWS Kiro 'user error' reflects common AI coding review gap*

**30.** "the campaign weaponized installed AI CLI tools by prompting them with
dangerous flags (--dangerously-skip-permissions, --yolo, --trust-all-tools) to
steal filesystem contents" -
[Wiz, s1ngularity](https://www.wiz.io/blog/s1ngularity-supply-chain-attack),
2025-08-27, company.
Query: `malware weaponized AI CLI tools dangerously-skip-permissions yolo to steal filesystem contents`
1. trendmicro.com, *Weaponized AI Assistants & Credential Thieves*
2. snyk.io, *Weaponizing AI Coding Agents for Malware in the Nx Malicious Package*
3. stepsecurity.io, *Bitwarden CLI Hijacked on npm*
4. socradar.io, *Bitwarden CLI Hijacked in npm Supply Chain Attack*
5. cybersecuritynews.com, *Beware of Weaponized AI Tool Installers*

### Three in Sabline's own terms

| Query | Top five | Sabline? |
|---|---|---|
| `run an AI-written script safely without reading it` | medium.com, *Read before you run*; dev.to, *Securing AI-Generated Bash Scripts Before You Run Them*; daily.dev; likeclaw.ai, *Sandboxed Code Execution*; github.com/conorbronsdon/avoid-ai-writing | No |
| `language where function signatures declare effects runtime refuses AI-written code` | arxiv.org 2607.17780, *ETAS: An Effect-Typed Language for Agent Systems*; dev.to; medium.com; arxiv.org 2504.15936, *An effectful object calculus*; dev.to | No |
| `limit what an AI-generated script can access files network environment variables` | vercel.com, *Sandbox*; aurascape.ai; briangershon.com; bitwarden.com; infisical.com | No |

## The AI assistants

**None of the four could be reached from this session**, so there are no
answers to record:

| Assistant | What happened |
|---|---|
| ChatGPT | `chatgpt.com/?q=` returned HTTP 403 to a direct fetch |
| Perplexity | `perplexity.ai/search?q=` returned HTTP 403 |
| Google AI Mode | `google.com/search?udm=50&q=` returned a page with no results and no AI answer |
| Claude (claude.ai) | Not attempted: it needs the account's login, and the Chrome extension that would carry that session was not connected |

The browser route needs the Claude in Chrome extension connected. The ten
phrasings to ask when it is, chosen to cover each aspect of the problem and the
highest-engagement threads: **1, 9, 13, 15, 16, 19, 20, 21, 23 and 26** above,
each asked verbatim in a new conversation, answer recorded verbatim with the
date and the model named.

## The site and the listings

Observations that bear on findability, recorded here and not acted on:

- **No sabline.dev page is in the index this tool searches.** `sabline.dev`
  serves no `robots.txt` and no `sitemap.xml` (both 404, GitHub Pages'
  not-found page); its home page carries `<link rel="canonical"
  href="https://sabline.dev/">`.
- **The repository's homepage field still says `https://velaris-lang.dev/`**,
  which answers 301 to sabline.dev.
- **The one-line description differs on every listing:**

  | Where | Text |
  |---|---|
  | GitHub description | "A programming language where signatures declare types, effects, and machine-checked promises — proven with Z3, compiled with LLVM. Built for trusting AI-written code. (Formerly Velaris.)" |
  | PyPI summary | "The language where you can trust code you didn't write - signatures declare types, effects, and machine-checked promises." |
  | npm description | "Run code you did not write. A language where a signature declares its effects and promises, and the runtime refuses anything you did not allow." |
  | README heading | "An AI wrote you a script. Run it anyway." |

- **The GitHub topics** are `compiler`, `effect-system`, `formal-verification`,
  `llvm`, `programming-language`, `python`, `smt-solver`, `static-analysis`,
  `theorem-proving`, `z3`: the vocabulary of how Sabline is built. None of the
  words the 30 phrasings use - agent, MCP, secrets, sandbox, supply chain,
  permissions - is among them.

## This file

Written at `docs/findability-baseline.md` on 2026-09-25 and moved here,
unchanged but for this section, when it was committed with the research it
draws on: every `docs/*.md` is rendered onto sabline.dev and link-checked,
and this page quotes other people's words and lists other sites' search
results, which is not what the site is for. Nothing in `plan/` is
published. [measurement.md](measurement.md) is how it is re-taken each
month.
