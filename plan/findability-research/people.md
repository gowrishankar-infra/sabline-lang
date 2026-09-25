# People and outlets who wrote about Sabline's catalogued incidents

Research only, done 2026-09-25. Nobody was contacted. I loaded every link below on 2026-09-24/25, using WebFetch or curl. I checked every quote word for word against the live page, and all are under 25 words. Some "about" pages list email addresses, Signal or Discord. I left those out on purpose and list only the public profile links each person gives on their own site. Where a site blocked me or redirected, I say so.

Ranked roughly by how closely what they wrote matches Sabline's thesis (code, and especially AI-written or agent-run code, gets more authority than it needs).

---

## 1. Simon Willison: blog and newsletter (individual; also counts as an outlet)

- **Role, per his own page:** creator of Datasette, co-creator of Django; blogging since 2002 ([about](https://simonwillison.net/about/)).
- **Catalogued incidents he wrote about:**
  - MCP tool poisoning: [Model Context Protocol has prompt injection security problems](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/), 2025-04-09
  - GitHub MCP private-repo leak: [GitHub MCP Exploited: Accessing private repositories via MCP](https://simonwillison.net/2025/May/26/github-mcp-exploited/), 2025-05-26
  - EchoLeak: [EchoLeak: Microsoft 365 Copilot zero-click](https://simonwillison.net/2025/Jun/11/echoleak/), 2025-06-11
  - Links GitHub MCP and EchoLeak together: [The lethal trifecta for AI agents](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/), 2025-06-16
  - Slopsquatting: [quote post of Andrew Nesbitt crediting Seth Larson](https://simonwillison.net/2025/Apr/12/andrew-nesbitt/), 2025-04-12
- **Angle:** named the "lethal trifecta" (private data + untrusted content + a way to send data out) and argues filters and guardrails can't fix it; the only fix is never giving an agent all three at once.
- **Where he publishes:** simonwillison.net; newsletter simonw.substack.com; Mastodon @simon@simonwillison.net; Bluesky simonwillison.net; X @simonw; GitHub simonw (all listed on his about page).
- **Why he might care:** "The only way to stay safe there is to avoid that lethal trifecta combination entirely." ([lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/)). A budget without `net` takes the "send it out" leg away from a run, which is his argument applied to one run. (Correction, 2026-09-25: an earlier draft said Sabline makes a trifecta-shaped program "fail to type-check". It does not. A program granted both a read and a send can pass on data it read, unless the data is a `Secret of T`; docs/competitors.md says so under CaMeL.) In the same post he calls "95% of attacks" caught "very much a failing grade".

## 2. Seth Larson: Python Software Foundation

- **Role, per his own page:** "Security Developer-in-Residence at the Python Software Foundation"; maintains urllib3 and truststore ([about](https://sethmlarson.dev/about)). The position is sponsored by Alpha-Omega.
- **Catalogued incidents he wrote about:**
  - Ultralytics: [Supply-chain attack analysis: Ultralytics](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/), PyPI blog, 2024-12-11. The page's author block names Seth Larson.
  - Slopsquatting: he coined the word in a conversation, not in an article. Andrew Nesbitt [credited him on 2025-04-08](https://mastodon.social/@andrewnez/114302875075999244). Seth's own posts: ["Do I have to add 'coined slopsquatting' to my resume now?"](https://fosstodon.org/@sethmlarson/114328275927451797) (2025-04-13), and [a reply agreeing that Bar Lanyado's "package hallucination" is the better name](https://fosstodon.org/@sethmlarson/114422100662523404) (2025-04-29).
- **Angle:** analysis from the package registry's side. Trusted Publishing and attestations narrowed what the attacker could do and made it traceable. He gives hardening advice for publishers, including a direct mention of xz as a reason to ban opaque files.
- **Where he publishes:** sethmlarson.dev (RSS); Mastodon sethmlarson@mastodon.social and sethmlarson@fosstodon.org; Bluesky sethmlarson.dev; GitHub sethmlarson (all listed on his about page).
- **Why he might care:** he split CPython's release pipeline into isolated stages because "This drastically reduces the number of dependencies, each representing a small amount of risk" ([Isolating risk in the CPython release process](https://sethmlarson.dev/security-developer-in-residence-weekly-report-35), 2024-05-02). In the Ultralytics post he likes short-lived credentials because they "have limited time-bounded value if exfiltrated". Both are arguments for limiting blast radius.

## 3. Andrew Nesbitt: Ecosyste.ms, Homebrew maintainer

- **Role, per his own page:** "My main project is Ecosyste.ms"; working with Alpha-Omega this year ([about](https://nesbitt.io/about/)). The sandboxing post says he helps maintain Homebrew.
- **Catalogued incidents he wrote about:**
  - Slopsquatting: [the Mastodon post that popularised the term](https://mastodon.social/@andrewnez/114302875075999244) (2025-04-08, crediting Seth Larson); [Slopsquatting meets Dependency Confusion](https://nesbitt.io/2025/12/10/slopsquatting-meets-dependency-confusion.html), 2025-12-10
  - Ultralytics, Nx, tj-actions: [GitHub Actions is the weakest link](https://nesbitt.io/2026/04/28/github-actions-is-the-weakest-link.html), 2026-04-28
  - Shai-Hulud, Nx: [Package Manager Sandboxing](https://nesbitt.io/2026/09/24/package-manager-sandboxing.html), 2026-09-24 (published the day before this research)
- **Angle:** package-ecosystem view. Most recent supply-chain incidents trace back to a GitHub Actions feature working as documented. Package managers and coding agents are now both adopting sandboxes (Seatbelt, Landlock, bubblewrap) for the same reason.
- **Where he publishes:** nesbitt.io (RSS); Mastodon @andrewnez@mastodon.social; Bluesky andrewnez.bsky.social; GitHub andrew; X @teabass (all listed on his about page).
- **Why he might care:** he sorts the fixes for install-time code into three kinds: gate it, confine it, or replace it "with data that is interpreted rather than executed" ([Package Manager Sandboxing](https://nesbitt.io/2026/09/24/package-manager-sandboxing.html)). He also notes that agent vendors adopted sandboxes because "these tools run unreviewed code, and asking permission each time stopped working." Sabline's approach, where the language refuses what the run was not granted, sits closest to "confine it", but only for code written in Sabline, not for npm or pip install scripts. This is probably the timeliest hook in the list.

## 4. Russ Cox: research!rsc

- **Role, per his own page:** swtch.com lists Go, Plan 9 and others under "Projects". It gives no current employer, so I don't state one.
- **Catalogued incidents he wrote about:**
  - xz-utils: [Timeline of the xz open source attack](https://research.swtch.com/xz-timeline), 2024-04-01 (updated 04-03); [The xz attack shell script](https://research.swtch.com/xz-script), 2024-04-02
- **Angle:** careful forensic reconstruction of how "Jia Tan" earned maintainer trust, and how liblzma ended up loaded inside sshd through a libsystemd patch.
- **Where he publishes:** research.swtch.com (RSS). His site lists no social handles.
- **Why he might care:** "True isolation would require a completely memory-safe language, with no escape hatch into untyped code." ([Our Software Dependency Problem](https://research.swtch.com/deps), 2019-01-23). This is close to Sabline's own argument for a language-level boundary. Caveat: he wrote it in 2019, before LLMs, about dependencies in general.

## 5. Luca Beurer-Kellner: Invariant Labs (now part of Snyk)

- **Role, per his own page:** GitHub bio says "Building secure and reliable agentic systems at Invariant Labs" ([github.com/lbeurerkellner](https://github.com/lbeurerkellner)). ETH Zurich names him Invariant's founding Chief Scientist and reports the Snyk acquisition ([ETH news](https://inf.ethz.ch/news-and-events/spotlights/infk-news-channel/2025/06/eth-spin-off-aquired-by-snyk.html), June 2025).
- **Catalogued incidents he wrote about:**
  - Tool poisoning: [MCP Security Notification: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks), 2025-04-01, with Marc Fischer
  - GitHub MCP toxic agent flow: [GitHub MCP Exploited](https://invariantlabs.ai/blog/mcp-github-vulnerability), 2025-05-26, with Marco Milanta
  - Related paper: [Design Patterns for Securing LLM Agents against Prompt Injections](https://arxiv.org/abs/2506.08837), 2025-06-10, first author of 14
- **Angle:** discovered both attacks, and argues the GitHub leak is "a fundamental architectural issue that must be addressed at the agent system level", not a bug in GitHub's server.
- **Where he publishes:** invariantlabs.ai blog (still up); Snyk contributor page; GitHub lbeurerkellner. His X handle shows up in search results, but his own GitHub profile doesn't list it, so I've left it out.
- **Why he might care:** the paper proposes "principled design patterns for building AI agents with provable resistance to prompt injection". He also co-created LMQL, a programming language for LLMs presented at PLDI'23 ([arXiv 2212.06094](https://arxiv.org/abs/2212.06094)), so he works in language design himself. **Caveat:** Invariant's recommended fix leans on runtime guardrails, which they sell. The GitHub MCP post says token permissions "often impose rigid constraints that limit an agent's functionality."

## 6. Rami McCarthy: Wiz

- **Role, per his own page:** "Currently, I work on security, for the internet, at Wiz." ([about](https://ramimac.me/about))
- **Catalogued incidents he wrote about:**
  - tj-actions: [GitHub Action supply chain attack: reviewdog/action-setup](https://www.wiz.io/blog/new-github-action-supply-chain-attack-reviewdog-action-setup), 2025-03-17. This is the follow-up that found the reviewdog link in the tj-actions chain.
  - Nx s1ngularity: [s1ngularity's aftermath](https://www.wiz.io/blog/s1ngularitys-aftermath), 2025-09-03. It quotes the malware calling `claude --dangerously-skip-permissions`, `gemini --yolo` and `q --trust-all-tools`.
  - MCP generally (tool poisoning, Simon's post): [Research Briefing: MCP Security](https://www.wiz.io/blog/mcp-security-research-briefing), 2025-04-17
  - His site ramimac.me keeps a running index of supply-chain incidents.
- **Angle:** incident-response forensics: impact numbers, attacker techniques (TTPs), what to look for in logs. The Nx post measures how well the AI-assisted part of the malware actually worked.
- **Where he publishes:** ramimac.me (RSS); Wiz blog; Bluesky ramimac.me; GitHub ramimac; X @ramimacisabird (all linked from his site).
- **Why he might care:** "Consider sandboxing MCP servers: Use containerization, network egress controls, and/or syscall filtering to restrict impact." He also advises: "Treat MCP servers like packages with elevated privileges." ([MCP briefing](https://www.wiz.io/blog/mcp-security-research-briefing)). He adds that such controls won't stop a malicious server from triggering other tools, and that is the gap a language-level boundary could fill.

## 7. Juri Strumpflohner: Nx (maintainer post-mortem)

- **Role, per his own page:** "Sr. Director of Developer Experience at Nx" ([juri.dev](https://juri.dev/), [about](https://juri.dev/about)).
- **Catalogued incident he wrote about:**
  - Nx s1ngularity: [S1ngularity - What Happened, How We Responded, What We Learned](https://nx.dev/blog/s1ngularity-postmortem), 2025-09-05. This is the maintainer's post-mortem.
- **Angle:** an honest account of how the attack worked: a `pull_request_target` workflow with an injectable PR title, and a repo still on GitHub's old read/write default for workflow tokens. After the attack Nx moved to Trusted Publishing and requires 2FA on every publish.
- **Where he publishes:** juri.dev; nx.dev blog; X @juristr, GitHub juristr, Bluesky juri.dev, YouTube (all listed on juri.dev).
- **Why he might care:** "But the impact must be limited even in those cases." ([post-mortem](https://nx.dev/blog/s1ngularity-postmortem)). His about page also says he is most interested in "how coding agents integrate with CI/CD pipelines". **Caveat:** the "task sandboxing" in Nx 22.7 ([release post](https://nx.dev/blog/nx-22-7-release), 2026-04-27) traces I/O to keep the build cache correct. It is not a security boundary, so don't cite it as evidence he cares about security sandboxing.

## 8. Michael Bargury: Zenity (Amazon Q)

- **Role, per his own page:** "Co-founder and CTO at Zenity"; review board member at Black Hat and the OWASP Agentic Security Initiative; Dark Reading columnist ([about](https://www.mbgsec.com/about/)).
- **Catalogued incident he wrote about:**
  - Amazon Q 1.84.0 wiper: [Reconstructing a timeline for Amazon Q prompt infection](https://www.mbgsec.com/posts/2025-07-24-constructing-a-timeline-for-amazon-q-prompt-infection/), 2025-07-24; follow-up [Someone Is Cleaning Up Evidence](https://www.mbgsec.com/posts/2025-07-26-tracking-down-the-amazon-q-attacker-through-deleted-prs/), 2025-07-26
- **Angle:** rebuilt the commit and tag history in public from GH Archive. He points out that the injected payload ran `q --trust-all-tools --no-interactive`.
- **Where he publishes:** mbgsec.com (RSS); X @mbrg0; Bluesky mbrg0.bsky.social; GitHub mbrg (all listed on his site).
- **Why he might care:** "Hard boundaries are not applicable to probabilistic AI models. But they are applicable to AI systems." ([Why Aren't We Making Any Progress In Security From AI](https://www.mbgsec.com/posts/2025-07-19-data-flow-controls-wont-save-us/), 2025-07-19). **Expect pushback** from the same post: "The main issue with hard boundaries is that they nerf the agent."

## 9. William Woodruff: Astral (previously Trail of Bits), author of zizmor

- **Role, per his own page:** "i write open source software for a living; currently for astral, previously for trail of bits" ([about](https://yossarian.net/about)). The brief listed him as Trail of Bits; that is out of date.
- **Catalogued incidents he wrote about:**
  - Ultralytics: [zizmor would have caught the Ultralytics workflow vulnerability](https://blog.yossarian.net/2024/12/06/zizmor-ultralytics-injection), 2024-12-06, written as events unfolded. The PyPI blog calls this the complete account.
  - xz, Ultralytics, tj-actions, Nx, web3.js and Shai-Hulud, listed as examples: [We should all be using dependency cooldowns](https://blog.yossarian.net/2025/11/21/We-should-all-be-using-dependency-cooldowns), 2025-11-21
- **Angle:** GitHub Actions misconfiguration (a `pull_request_target` "pwn request" plus cache poisoning), and the argument that cooldowns are "a free, easy, and incredibly effective way" to stop most supply-chain attacks. That post does not discuss sandboxing or capabilities.
- **Where he publishes:** blog.yossarian.net; GitHub woodruffw; Mastodon @yossarian@yossarian.net (both listed on yossarian.net).
- **Why he might care:** partly. He warns that over-scoped credentials mean "the impact of a compromised or leaked credential can be much broader than the specific system it was stolen from" ([You shouldn't trust Trusted Publishing](https://blog.yossarian.net/2026/07/07/You-shouldnt-trust-trusted-publishing), 2026-07-07). His focus is credentials and CI, not what the code itself is allowed to do.

## 10. tl;dr sec, Clint Gibler (outlet)

- **Role, per the tl;dr sec author page:** "Head of Security Research @semgrep; Creator of tl;dr sec newsletter" ([author page](https://tldrsec.com/authors/clint-gibler)). A search-result snippet of his LinkedIn said "Leading Cyber @ OpenAI". I could not load LinkedIn to check, so treat his current affiliation as unconfirmed.
- **Catalogued incidents covered (each an issue of the weekly newsletter):**
  - tj-actions: [#271](https://tldrsec.com/p/tldr-sec-271), 2025-03-20
  - Tool poisoning: [#274](https://tldrsec.com/p/tldr-sec-274), 2025-04-10
  - GitHub MCP: [#281](https://tldrsec.com/p/tldr-sec-281), 2025-05-29
  - EchoLeak: [#284](https://tldrsec.com/p/tldr-sec-284), 2025-06-19
  - Nx s1ngularity: [#296](https://tldrsec.com/p/tldr-sec-296), 2025-09-11
  - Shai-Hulud: [#297](https://tldrsec.com/p/tldr-sec-297), 2025-09-18
  - postmark-mcp: [#299](https://tldrsec.com/p/tldr-sec-299), 2025-10-02
- **Angle:** curated summaries with short opinions. He was sceptical of the tool-poisoning write-up ("a bit overhype-y") while granting that it was useful.
- **Where he publishes:** tldrsec.com (newsletter); GitHub clintgibler (profile links to tldrsec.com).
- **Why he might care:** on runtime guardrails and context-aware access controls for agents: "People have identified this is a problem, but solutions are still quite nascent, so it'll be neat to see how this sorts out." ([#281](https://tldrsec.com/p/tldr-sec-281)). This is an outlet pitch ("here is a new approach"), not a claim that he already agrees.

---

## Who covers which catalogued incident

| Incident | Shortlist coverage | Other sourced writers (below) |
|---|---|---|
| mcp-remote CVE-2025-6514 | none | Or Peles (JFrog) |
| MCP tool poisoning | Willison, Beurer-Kellner, McCarthy, tl;dr sec | |
| GitHub MCP toxic agent flow | Willison, Beurer-Kellner, tl;dr sec | |
| postmark-mcp | tl;dr sec | Idan Dardikman (Koi) |
| Nx s1ngularity | Strumpflohner, McCarthy, Nesbitt, Woodruff (list), tl;dr sec | |
| Shai-Hulud | Nesbitt, Woodruff (list), tl;dr sec | |
| tj-actions | McCarthy, Nesbitt, Woodruff (list), tl;dr sec | |
| @solana/web3.js | Woodruff (list only) | Steven Luscher (advisory only) |
| Ultralytics | Larson, Woodruff, Nesbitt | |
| xz-utils | Cox, Woodruff (list) | Andres Freund (discoverer) |
| Amazon Q 1.84.0 wiper | Bargury | |
| CircleCI Jan 2023 | none | Rob Zuber (CircleCI's own report) |
| EchoLeak | Willison, tl;dr sec | Aim Labs (site blocked, see below) |
| CamoLeak | none | Omer Mayraz (Legit) |
| Slopsquatting | Larson (coined), Nesbitt (popularised), Willison | Bar Lanyado (Lasso) |

"(list)" means the incident is named as an example, not analysed.

## Also sourced, lower priority (vendor researchers, no personal site found)

- **Idan Dardikman (Koi): postmark-mcp.** [First Malicious MCP in the Wild](http://web.archive.org/web/20250929094654/https://www.koi.security/blog/postmark-mcp-npm-malicious-backdoor-email-theft), 2025-09-25. **The original URL is dead:** koi.security redirects to koi.ai, which redirects to a Palo Alto Networks product page. Palo Alto [completed its acquisition of Koi on 2026-04-14](https://www.paloaltonetworks.com/company/press/2026/palo-alto-networks-completes-acquisition-of-koi-to-secure-the-agentic-endpoint). I read the Wayback snapshot, and Sabline's catalogue should link to it too. The strongest quote in this research: "There's literally no security model here. No sandbox. No containment. Nothing." His current affiliation after the acquisition is unverified.
- **Omer Mayraz (Legit Security): CamoLeak.** [CamoLeak: Critical GitHub Copilot Vulnerability Leaks Private Source Code](https://www.legitsecurity.com/blog/camoleak-critical-github-copilot-vulnerability-leaks-private-source-code), 2025-10-08 (updated 2026-02-12). Relevant quote: "Copilot operates with the same permissions as the user making the request", which is exactly the ambient-authority problem.
- **Or Peles (JFrog): mcp-remote.** [Critical RCE Vulnerability in mcp-remote: CVE-2025-6514](https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability/), 2025-07-09. Byline: "JFrog Senior Security Researcher". His mitigation advice is limited to "Only connect to trusted MCP Servers, using HTTPS", with nothing on bounding what the client can do.
- **Bar Lanyado (Lasso): package hallucination.** [Diving Deeper into AI Package Hallucinations](https://www.lasso.security/blog/ai-package-hallucinations), 2024-03-28, which says the original research was done "while working at Vulcan Cyber". The 2023 Vulcan post now redirects to an unrelated Tenable page. He also [said publicly on Mastodon](https://mastodon.social/@LanyB/114419939168087826) (2025-04-29) that "package hallucination" is his earlier term, and Seth Larson agreed. His recommendations are to verify LLM answers and vet unfamiliar packages. **Nothing he wrote suggests interest in language-level bounds.**
- **Marc Fischer (Invariant CEO):** co-author of the tool-poisoning post. On the Snyk deal: "We understand agent systems as a new type of software that requires novel and innovative approaches to provide strong security guarantees." ([ETH news](https://inf.ethz.ch/news-and-events/spotlights/infk-news-channel/2025/06/eth-spin-off-aquired-by-snyk.html))

## Checked and dropped

- **Andres Freund (xz discoverer):** [oss-security post](https://www.openwall.com/lists/oss-security/2024/03/29/4), 2024-03-29. It is the primary source, but anarazel.de only says "nothing interesting", he has no profile page, and I found nothing he wrote about limiting what code can reach. He is worth citing, but I have nothing to base an approach on.
- **Johann Rehberger (Embrace The Red):** wrote in depth about other Amazon Q Developer bugs during his Month of AI Bugs ([RCE via prompt injection](https://embracethered.com/blog/posts/2025/amazon-q-developer-remote-code-execution/), 2025-08-19; the fix shipped in v1.85, the same release that removed the wiper). None of the posts I checked mention the 1.84.0 wiper itself, so he is next to the catalogue rather than in it.
- **Aim Labs (EchoLeak):** aim.security returned **HTTP 403** to both WebFetch and curl, so I could not confirm the authors. Willison and tl;dr sec cover EchoLeak instead.
- **Steven Luscher (@solana/web3.js):** published the [GitHub advisory GHSA-jcxm-7wvp-g6p5](https://github.com/solana-foundation/solana-web3.js/security/advisories/GHSA-jcxm-7wvp-g6p5) on 2024-12-04. It is a short notice, not an analysis.
- **Rob Zuber (CircleCI CTO):** [Jan 4, 2023 security incident report](https://circleci.com/blog/jan-4-2023-incident-report/), 2023-01-12. A company post-mortem and the only CircleCI source I found. I didn't look further.
- **Sarah Gooding (Socket):** [slopsquatting explainer](https://socket.dev/blog/slopsquatting-how-ai-hallucinations-are-fueling-a-new-class-of-supply-chain-attacks), 2025-04-08. Vendor news, and Larson and Nesbitt are better sources for the same story.
- **StepSecurity (Varun Sharma, tj-actions discovery):** tl;dr sec #271 cites it, but I did not load StepSecurity's own post, so I don't list it.

## Notes for the catalogue itself

1. **The postmark-mcp link has rotted.** Point it at the Wayback snapshot above.
2. **Slopsquatting credit:** Larson coined it in conversation and Nesbitt popularised it (2025-04-08). Lanyado says "package hallucination" is his earlier name, and Larson agreed on 2025-04-29. Lanyado's first research was at Vulcan Cyber in 2023, before he joined Lasso.
3. **Changed affiliations since the incidents:** Woodruff has moved to Astral. Snyk now owns Invariant (the blog is still up). Palo Alto Networks now owns Koi (the blog is gone).
