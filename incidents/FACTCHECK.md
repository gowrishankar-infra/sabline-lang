# Fact-check of the catalogue's sources

**Working material, not documentation.** This is the evidence gathered on
2026-09-23 for the person who decides whether each summary is right. It
changes nothing: no entry was edited, and every entry still says
`verified: false`. Each proposed wording below a table is a proposal only.

It is kept out of what is published and what is checked:

- the documentation site is built from the documents `build_docs.py` names
  and `docs/*.md`, and `build_incidents.py` reads only the entry
  directories, so this file is on no page;
- `check_urls.py` lists it in `NOT_SOURCES`, so the monthly link check does
  not ask its URLs a second time (the entries themselves still are asked).

## How it was made

- **Every URL in every entry's Sources list was fetched**: 35 URLs across
  16 entries. That includes the four no earlier session had fetched:
  - mcp-remote-command-injection's sources, for its `date: 2025-07-09`;
  - the two The Register articles (postmark and replit);
  - Aim Labs' and MSRC's pages for echoleak.
- **Fallbacks when a page didn't render:** a page the fetcher couldn't
  read, or one that renders with JavaScript, was read with `curl`, then
  through its own API (NVD, MSRC, GitHub advisories). How each URL was
  reached is in each entry's source table.
- **One row per factual claim**, drawn from three places:
  - the frontmatter `date:`;
  - every sentence of "What happened", with each date, version, package
    name, count, person and CVE on a row of its own;
  - the factual descriptors in the Sources list and its notes.
- **The verdicts:**
  - **SUPPORTED:** a cited source says it.
  - **DIFFERS:** a cited source says something else. A direct quotation
    whose words differ is DIFFERS.
  - **NOT IN SOURCE:** no source the entry cites says it, whether or not it
    is true elsewhere.
  - **SOURCE UNREACHABLE:** the only source for it couldn't be fetched. An
    archived copy is described in the notes but doesn't change the verdict.
- **Evidence is paraphrased.** No source is pasted at length.
- **Who did it:** each entry's section was written by one of four research
  agents working in parallel. The counts below were recomputed from the
  rows themselves. Four findings were re-fetched independently and agreed:
  - solana's date: the advisory says Tuesday 3 December 2024;
  - Ultralytics: PyPI names four affected versions;
  - replit: The Register has no "deleted our production database without
    permission";
  - the Aim Labs URL now answers HTTP 403.

## The counts

324 claims in all.

| Entry | Verdict in the entry | SUPPORTED | DIFFERS | NOT IN SOURCE | SOURCE UNREACHABLE |
|---|---|---|---|---|---|
| [amazon-q-extension-wiper](#amazon-q-extension-wiper) | NOT COVERED | 28 | 2 | 0 | 0 |
| [camoleak-copilot-chat](#camoleak-copilot-chat) | OUT OF SCOPE | 19 | 1 | 0 | 0 |
| [circleci-oauth-token-theft](#circleci-oauth-token-theft) | NOT COVERED | 13 | 3 | 0 | 0 |
| [echoleak-m365-copilot](#echoleak-m365-copilot) | OUT OF SCOPE | 9 | 0 | 0 | 12 |
| [github-mcp-toxic-agent-flow](#github-mcp-toxic-agent-flow) | NOT COVERED | 16 | 0 | 0 | 0 |
| [mcp-remote-command-injection](#mcp-remote-command-injection) | STOPPED | 15 | 0 | 4 | 0 |
| [mcp-tool-poisoning](#mcp-tool-poisoning) | PARTIAL | 18 | 2 | 0 | 0 |
| [nx-s1ngularity](#nx-s1ngularity) | PARTIAL | 19 | 1 | 0 | 0 |
| [package-hallucination](#package-hallucination) | PARTIAL | 19 | 1 | 1 | 0 |
| [postmark-mcp-bcc-exfiltration](#postmark-mcp-bcc-exfiltration) | PARTIAL | 21 | 0 | 2 | 0 |
| [replit-agent-database-deletion](#replit-agent-database-deletion) | PARTIAL | 16 | 5 | 1 | 0 |
| [shai-hulud-npm-worm](#shai-hulud-npm-worm) | PARTIAL | 15 | 0 | 1 | 0 |
| [solana-web3js-backdoor](#solana-web3js-backdoor) | STOPPED | 14 | 4 | 1 | 0 |
| [tj-actions-changed-files](#tj-actions-changed-files) | PARTIAL | 18 | 3 | 1 | 0 |
| [ultralytics-pypi-cache-poisoning](#ultralytics-pypi-cache-poisoning) | NOT COVERED | 12 | 4 | 7 | 0 |
| [xz-utils-backdoor](#xz-utils-backdoor) | NOT COVERED | 13 | 3 | 0 | 0 |
| **all 16** | | **265** | **29** | **18** | **12** |

## Sources that are not the primary report

The rule in `incidents/README.md` is that a source is a vendor post-mortem,
a CVE record or the researcher's own write-up. These cited sources are
something else, or repeat one:

- **amazon-q-extension-wiper.** BleepingComputer repeats 404 Media (the
  commit date, the contributor's alias, the payload) and mbgsec.com. Neither
  is cited. The AWS bulletin and the CVE record are primary.
- **postmark-mcp-bcc-exfiltration.** Both cited sources are secondary:
  - Snyk repeats Koi Security's discovery;
  - The Register repeats Koi's post and Postmark's own statement.

  Koi's post now redirects to an unrelated product page, and an archived
  copy exists. Postmark's statement is live at
  `postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package`
  and is a vendor primary the entry does not cite.
- **replit-agent-database-deletion.** Both cited sources are secondary:
  - the AI Incident Database record collects five news reports and links no
    post or statement directly;
  - The Register is news that quotes Lemkin's posts.

  The participants' posts on X, the actual primary record, are not cited.
- **tj-actions-changed-files.** The Wiz post repeats StepSecurity's first
  report, which is not cited. The GHSA and CISA's alert are primary.
- **ultralytics-pypi-cache-poisoning.**
  - The Wiz post repeats the GitHub issues, ReversingLabs and
    BleepingComputer.
  - PyPI's post is primary for PyPI's side but defers the technical path to
    William Woodruff's analysis. That analysis
    (`blog.yossarian.net/2024/12/06/zizmor-ultralytics-injection`) is where
    the entry's `pull_request_target`, fork checkout and cache chain appears
    to come from, and it is not cited.
- **nx-s1ngularity.** StepSecurity is a vendor analysis: primary for its own
  payload analysis, secondary otherwise. GitGuardian is primary for its own
  counts, secondary for the attack mechanics.
- **mcp-remote-command-injection.** Four claims (what mcp-remote is, Claude
  Desktop, "OAuth metadata", arbitrary commands on every platform) come from
  JFrog's blog post. Both cited advisories link that post, but the entry
  doesn't cite it.
- **echoleak-m365-copilot.** The primary write-up (Aim Labs) is unreachable:
  the URL answers 403, and the Wayback Machine shows it stopped serving the
  article in August 2025. Twelve rows rest on it alone.

---

## amazon-q-extension-wiper

**Amazon Q Developer for VS Code 1.84.0, CVE-2025-8217** - verdict in the entry: NOT COVERED; `date:` 2025-07-17

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [AWS-2025-015](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/) | primary: vendor security bulletin | curl, HTTP 200 (static HTML) | Page title is "Security Update for Amazon Q Developer Extension for Visual Studio Code (Version #1.84)"; published 2025/07/23 6:00 PM PDT, updated 2025/07/25 6:00 PM PDT. The Wayback copy of 24 July 2025 has the same title. That version said researchers reported an attempted unapproved code change, revoked the credentials, and released 1.85. The token, CodeBuild and syntax-error sentences arrived with the 25 July update. |
| [CVE-2025-8217 (NVD)](https://nvd.nist.gov/vuln/detail/CVE-2025-8217) | primary: CVE record (description supplied by the CNA, vendor Amazon) | curl HTTP 200 returned only the JS app shell; NVD API HTTP 200 | NVD published 2025-07-30; describes v1.84.0 with inert injected code meant to call the Q Developer CLI, a syntax error, upgrade to v1.85.0. CNA scores: CVSS 4.0 5.1, CVSS 3.1 4.0. |
| [BleepingComputer](https://www.bleepingcomputer.com/news/security/amazon-ai-coding-agent-hacked-to-inject-data-wiping-commands/) | secondary: news, Bill Toulas, 25 July 2025 (update 26 July) | curl, HTTP 200 | REPEATS 404 Media (commit date 13 July, alias lkmanka58, the payload) and mbgsec.com (the commit screenshot); also quotes the 23 July wording of the AWS bulletin. The S3/EC2/IAM commands appear only in the embedded commit screenshot, not in the article's prose. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2025-07-17 is the day it happened | BleepingComputer; AWS bulletin | SUPPORTED | BleepingComputer: Amazon published the compromised 1.84.0 to the VS Code marketplace on July 17. Same article dates the injected commit to July 13 (citing 404 Media). The AWS bulletin gives neither date. The body never says which event the date marks, and the TEMPLATE asks it to. |
| 2 | The AWS security bulletin is AWS-2025-015 | AWS bulletin | SUPPORTED | The ID appears in the page URL. The page text does not print its own ID; it names a separate investigation, AWS-2025-016, in which the issue was found. |
| 3 | Bulletin published 23 July 2025 | AWS bulletin | SUPPORTED | Publication date 2025/07/23, 6:00 PM PDT. |
| 4 | Bulletin updated on 25 July | AWS bulletin | SUPPORTED | Updated date 2025/07/25, 6:00 PM PDT. |
| 5 | Quoted: "an inappropriately scoped GitHub token" | AWS bulletin | SUPPORTED | These exact words appear. |
| 6 | The token was in a CodeBuild configuration | AWS bulletin | SUPPORTED | The token was in the extension's CodeBuild configuration. |
| 7 | An attacker used the token to inject code | AWS bulletin | SUPPORTED | With that token, the threat actor committed malicious code to the extension's open-source repository. |
| 8 | The code went into version 1.84.0 | AWS bulletin; NVD | SUPPORTED | Impacted version is 1.84.0. NVD says the same. |
| 9 | ...of the Amazon Q Developer extension for Visual Studio Code | AWS bulletin | SUPPORTED | The product is the Amazon Q Developer for VS Code extension. |
| 10 | The code was then included in a release automatically | AWS bulletin | SUPPORTED | The malicious code was included in a release automatically. |
| 11 | Quoted: "was unsuccessful in executing due to a syntax error" | AWS bulletin | SUPPORTED | These exact words appear. |
| 12 | AWS revoked the credentials | AWS bulletin | SUPPORTED | AWS immediately revoked and replaced the credentials. |
| 13 | AWS removed the payload | AWS bulletin | SUPPORTED | AWS removed the malicious code from the code base. |
| 14 | AWS released 1.85.0 | AWS bulletin; NVD | SUPPORTED | AWS then released version 1.85.0. |
| 15 | Users of 1.84.0 are told to remove it | AWS bulletin; NVD | SUPPORTED | All 1.84.0 installations should be removed from use and updated to 1.85.0. |
| 16 | Tracked as CVE-2025-8217 | AWS bulletin; NVD | SUPPORTED | The bulletin says the issue is assigned CVE-2025-8217. The NVD record exists under that ID. |
| 17 | Contemporaneous reporting described the payload | BleepingComputer | SUPPORTED | The article is dated 25 July 2025 and quotes the injected prompt. |
| 18 | The payload was an instruction addressed to the agent | BleepingComputer | SUPPORTED | The article calls it a data-wiping injection prompt. The embedded commit screenshot opens by telling the reader it is an AI agent with filesystem tools and bash. |
| 19 | It told the agent to delete local files | BleepingComputer | SUPPORTED | Goal: return the system to a near-factory state and delete file-system resources, starting from the user's home directory (screenshot). |
| 20 | ...and cloud resources | BleepingComputer | SUPPORTED | The quoted prompt says to delete file-system and cloud resources. |
| 21 | ...including S3 buckets | BleepingComputer | DIFFERS | S3 is named only in the embedded screenshot, as an `aws --profile <profile_name> s3 rm` command, which removes objects. The prompt names no bucket removal, and the article's prose does not mention S3. |
| 22 | ...EC2 instances | BleepingComputer | SUPPORTED | Screenshot only: an `ec2 terminate-instances` command. |
| 23 | ...and IAM users | BleepingComputer | SUPPORTED | Screenshot only: an `iam delete-user` command. |
| 24 | Source 1 title: "AWS-2025-015: Issue with Amazon Q Developer Extension for Visual Studio Code" | AWS bulletin | DIFFERS | The page title is "Security Update for Amazon Q Developer Extension for Visual Studio Code (Version #1.84)". The Wayback copy from 24 July 2025 has the same title. |
| 25 | Source 1 is AWS's own security bulletin | AWS bulletin | SUPPORTED | It is an AWS security bulletin page on aws.amazon.com. |
| 26 | Source 1 covers the token scoping, the affected version, the syntax error and the fix | AWS bulletin | SUPPORTED | The current version covers all four. The 24 July original named the affected version (1.84) and the fix (1.85), but not the token scoping or the syntax error. |
| 27 | Source 2 is the CVE record | NVD | SUPPORTED | This is the NVD entry for CVE-2025-8217, with the CNA's description. |
| 28 | Source 3 title: "Amazon AI coding agent hacked to inject data wiping commands" | BleepingComputer | SUPPORTED | The headline matches. |
| 29 | Source 3 reports what the payload said | BleepingComputer | SUPPORTED | It quotes one line of the prompt and embeds a screenshot of the commit. This is secondary: it credits 404 Media and mbgsec.com. |
| 30 | The bulletin does not quote the payload | AWS bulletin | SUPPORTED | The bulletin contains no payload text. |

Proposed wording:
- #21: "Contemporaneous reporting described the payload as an instruction addressed to the agent, telling it to delete local files and cloud resources using AWS CLI commands such as `ec2 terminate-instances`, `s3 rm` and `iam delete-user`." Reason: the only source for the commands is BleepingComputer's embedded commit screenshot, which names `s3 rm` (object removal), not bucket deletion. The entry's later `aws s3 rb` example does not appear in the payload either.
- #24: "[Security Update for Amazon Q Developer Extension for Visual Studio Code (Version #1.84)](https://aws.amazon.com/security/security-bulletins/AWS-2025-015/) - AWS's own security bulletin (AWS-2025-015): ..." Reason: that is the page's actual title, now and in the 24 July 2025 copy.

---

## camoleak-copilot-chat

**CamoLeak, in GitHub Copilot Chat** - verdict in the entry: OUT OF SCOPE; `date:` 2025-10-08

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [CamoLeak (Legit Security)](https://www.legitsecurity.com/blog/camoleak-critical-github-copilot-vulnerability-leaks-private-source-code) | primary: researcher's own write-up (first person) | curl, HTTP 200 | Byline Omer Mayraz, dated October 08, 2025 (JSON-LD datePublished 2025-10-08, modified 2026-02-12). Found June 2025, reported via HackerOne, rated CVSS 9.6 by the post. An embedded screenshot shows a GitHub staff comment of August 14, 2025 saying a fix had shipped. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2025-10-08 (no incident day given, so the disclosure day) | Legit write-up | SUPPORTED | The post is dated October 08, 2025. It gives only "June 2025" for the discovery and August 14 for the fix, and no in-the-wild use, so the publication day is the fallback. The body never says which event the date marks. |
| 2 | Omer Mayraz reported the vulnerability | Legit write-up | SUPPORTED | The byline is Omer Mayraz. He writes that he found it and reported it via HackerOne. |
| 3 | Mayraz is of Legit Security | Legit write-up | SUPPORTED | The post is on Legit Security's blog, and GitHub's reply in the screenshot addresses the account omermayraz-legitsecurity. |
| 4 | The vulnerability is in GitHub Copilot Chat | Legit write-up | SUPPORTED | The post describes a critical vulnerability in GitHub Copilot Chat. |
| 5 | He named it CamoLeak | Legit write-up | SUPPORTED | The name appears in the post's title. The body text never uses it. |
| 6 | Hidden instructions were placed in a pull request description | Legit write-up | SUPPORTED | The prompt was embedded in a PR description, as a hidden comment. |
| 7 | ...using GitHub's invisible comment syntax | Legit write-up | SUPPORTED | Invisible comments are an official GitHub feature (the docs page on hiding content with comments). |
| 8 | ...so a human reviewer does not see them | Legit write-up | SUPPORTED | The hidden comment's content is not revealed anywhere, including in the PR notification. |
| 9 | Copilot read them when a user asked it about the pull request | Legit write-up | SUPPORTED | A different user who asked Copilot Chat to explain the PR got the prompt injected into their context. |
| 10 | The goal was to get data out past the content security policy | Legit write-up | SUPPORTED | GitHub's restrictive CSP blocks outside images, and the post describes a CSP bypass. |
| 11 | The exploit pre-generated Camo image-proxy URLs standing for individual characters | Legit write-up | SUPPORTED | He built a dictionary of letters and symbols, with a valid Camo URL for each generated through GitHub's API. |
| 12 | Copilot rendered the secret one character at a time as images | Legit write-up | SUPPORTED | Copilot was asked to render the leaked content as "ASCII art" made of those images, in order. |
| 13 | Mayraz reports extracting AWS keys | Legit write-up | DIFFERS | He had Copilot search the victim's whole codebase for the keyword "AWS_KEY" and exfiltrate the result. The post does not say that AWS keys were recovered. |
| 14 | ...and details of undisclosed vulnerabilities | Legit write-up | SUPPORTED | The PoC target was the description of a zero-day vulnerability in an issue, under the heading "Stealing zero days from private repositories". |
| 15 | ...from private repositories | Legit write-up | SUPPORTED | The target was a private project and the victim's private repositories. |
| 16 | GitHub disabled image rendering in Copilot Chat | Legit write-up | SUPPORTED | GitHub fixed it by disabling image rendering in Copilot Chat completely. |
| 17 | ...on 14 August 2025 | Legit write-up | SUPPORTED | The post says GitHub reports the vulnerability fixed as of August 14. The screenshot shows GitHub staff on August 14, 2025 saying a fix had shipped. The post does not date the image-rendering change separately. |
| 18 | Source title: "CamoLeak: Critical GitHub Copilot Vulnerability Leaks Private Source Code" | Legit write-up | SUPPORTED | The title matches exactly. |
| 19 | The source is the researcher's own write-up | Legit write-up | SUPPORTED | It is a first-person account by the researcher who found and reported the flaw. |
| 20 | The source covers the injection, the Camo encoding, what was extracted, and the fix date | Legit write-up | SUPPORTED | All four are covered. |

Proposed wording:
- #13: "Mayraz reports having Copilot search a victim's codebase for "AWS_KEY" and exfiltrate the result, and extracting details of undisclosed vulnerabilities from private repositories." Reason: the post describes the search being exfiltrated, not AWS keys being recovered.

---

## circleci-oauth-token-theft

**The CircleCI January 2023 incident** - verdict in the entry: NOT COVERED; `date:` 2023-01-04

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [CircleCI incident report](https://circleci.com/blog/jan-4-2023-incident-report/) | primary: vendor post-mortem | curl, HTTP 200 | Page title "CircleCI Jan 4, 2023 security incident report". By Rob Zuber, CTO. Shown date is Jan 12, 2023 (meta 2023-01-12 22:00 PST); the alert page says the report went up 01/13/2023 21:25 UTC. Gives incident days of 16, 19 and 22 December 2022. |
| [CircleCI security alert](https://circleci.com/blog/january-4-2023-security-alert/) | primary: vendor customer alert | curl, HTTP 200 | Current title adds "(Updated Jan 13)"; last updated Mar 3, 2023. Original text at the foot of the page. Says the rotation guidance went out 6:30 pm PT on Wednesday, January 4. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2023-01-04 is the day it happened (or, failing that, the disclosure day) | Incident report | DIFFERS | The report gives incident days: laptop compromised 16 Dec 2022, unauthorized access and reconnaissance 19 Dec, exfiltration 22 Dec 2022 (the last unauthorized activity). 4 Jan 2023 is the disclosure day, and the TEMPLATE uses that only when no source gives an incident day. The body does not say which event the date marks. |
| 2 | Quoted: "an unauthorized third party leveraged malware deployed to a CircleCI engineer's laptop in order to steal a valid, 2FA-backed SSO session" | Incident report | SUPPORTED | These exact words appear. |
| 3 | The actor then used that access to exfiltrate data | Incident report | SUPPORTED | Session cookie theft let the actor impersonate the employee, escalate access, and exfiltrate data. |
| 4 | ...from a subset of the company's production systems | Incident report | SUPPORTED | Access was escalated to a subset of production systems, and data was taken from a subset of databases and stores. |
| 5 | ...including customer environment variables, tokens and keys | Incident report | SUPPORTED | The data taken included customer environment variables, tokens and keys. |
| 6 | A customer's GitHub OAuth token was found compromised on 30 December 2022 | Incident report | SUPPORTED | On December 30, 2022, CircleCI learned that the customer's GitHub OAuth token was compromised. The customer's alert came on Dec 29. |
| 7 | CircleCI began rotating all customers' GitHub OAuth tokens on 31 December | Incident report | SUPPORTED | CircleCI started rotating all GitHub OAuth tokens on December 31, 2022 at 04:00 UTC, and finished on Jan 7, 2023. |
| 8 | CircleCI alerted customers on 4 January 2023 | Incident report; security alert | SUPPORTED | Disclosure went out January 4, 2023 at 6:30 PM PST, which is January 5 at 02:30 UTC. |
| 9 | ...to rotate every secret they had stored | Security alert; incident report | SUPPORTED | The alert tells customers to immediately rotate any and all secrets stored in CircleCI. |
| 10 | CircleCI completed the AWS token notifications | Incident report; security alert | DIFFERS | AWS did the notifying: CircleCI worked with AWS, and AWS emailed customers lists of possibly affected tokens. The report says only that CircleCI understands those notifications were complete. |
| 11 | ...on 12 January | Incident report; security alert | SUPPORTED | The report says the notifications were complete as of January 12, 2023, 00:00 UTC. The alert's update at 01/12/2023 00:30 UTC says AWS began emailing "today", which in US time is 11 January. |
| 12 | Source 1 title: "CircleCI incident report for January 4, 2023 security incident" | Incident report | DIFFERS | The page title is "CircleCI Jan 4, 2023 security incident report". |
| 13 | Source 1 is CircleCI's own post-mortem | Incident report | SUPPORTED | It is CircleCI's report by its CTO, Rob Zuber. |
| 14 | Source 1 covers the malware, the stolen session, what was exfiltrated, and the rotation timeline | Incident report | SUPPORTED | All four are covered. |
| 15 | Source 2 title: "CircleCI security alert: Rotate any secrets stored in CircleCI" | Security alert | SUPPORTED | Matches the page title, which now ends with "(Updated Jan 13)". |
| 16 | Source 2 is the customer-facing alert of 4 January 2023 | Security alert | SUPPORTED | The original notice is at the foot of the page. The page says the rotation guidance was released on the evening of January 4 (PT), then updated through 13 January. |

Proposed wording:
- #1: `date: 2022-12-22`, with the body adding "exfiltration took place on 22 December 2022; CircleCI disclosed on 4 January 2023". Reason: the incident report gives the incident days, and the TEMPLATE prefers the day it happened. Use 2022-12-16 instead if the laptop compromise is taken as the start.
- #10: "...alerted customers on 4 January 2023 to rotate every secret they had stored, and reports that AWS's notifications to customers with possibly affected AWS tokens were complete by 12 January." Reason: both CircleCI pages say AWS sent the notifications, in partnership with CircleCI.
- #12: "[CircleCI Jan 4, 2023 security incident report](https://circleci.com/blog/jan-4-2023-incident-report/) - CircleCI's own post-mortem: ..." Reason: that is the page's actual title.

---

## echoleak-m365-copilot

**EchoLeak, CVE-2025-32711** - verdict in the entry: OUT OF SCOPE; `date:` 2025-06-11

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Aim Labs EchoLeak write-up](https://www.aim.security/lp/aim-labs-echoleak-blogpost) | primary: researcher's own write-up | unreachable: HTTP 403 (Cloudflare) to both WebFetch and curl, www and bare host | The URL no longer serves the article. Wayback shows a 404 from 2025-08-18, a 301 to catonetworks.com later, and a 403 in 2026. The notes below use the Wayback copy of 2025-08-05. Byline "Aim Labs Team", dated 11 June 2025; its title ends "Data Exfiltration from Microsoft 365 Copilot". That copy has no CVE ID, CVSS score, fix mechanism or exploitation statement; it says Microsoft confirmed no customers were affected. |
| [CVE-2025-32711 (MSRC)](https://msrc.microsoft.com/update-guide/vulnerability/CVE-2025-32711) | primary: vendor advisory and CVE record (Microsoft is the CNA) | curl HTTP 200 returned only the JS app shell; MSRC API HTTP 200 (vulnerability and acknowledgement endpoints) | Title "M365 Copilot Information Disclosure Vulnerability". Released 2025-06-11. CVSS 3.1 base 9.3 (vector AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:L/A:N), temporal 8.1, Critical. Exploited: No; publicly disclosed: No. Credits "Aim Labs (Part of Aim Security)" and Estevam Arantes with Microsoft. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2025-06-11 (no incident day, so the disclosure day) | MSRC | SUPPORTED | The MSRC release date is 2025-06-11. MSRC marks it not exploited, so there is no incident day to use. The archived Aim post is also dated 11 June 2025. The body does not say the date is the disclosure day. |
| 2 | Aim Labs reported it | MSRC | SUPPORTED | The MSRC acknowledgements list "Aim Labs (Part of Aim Security)" as a finder, alongside Estevam Arantes with Microsoft. |
| 3 | It is a zero-click vulnerability | MSRC | SUPPORTED | Only by way of the CVSS vector UI:N, meaning no user interaction is required. MSRC does not use the word "zero-click". The archived Aim copy does. |
| 4 | ...in Microsoft 365 Copilot | MSRC | SUPPORTED | The MSRC title is "M365 Copilot Information Disclosure Vulnerability". |
| 5 | Assigned CVE-2025-32711 | MSRC | SUPPORTED | The MSRC record is for CVE-2025-32711. |
| 6 | CVSS score of 9.3 | MSRC | SUPPORTED | CVSS 3.1 base score 9.3 (temporal 8.1), severity Critical. |
| 7 | An email was sent to the target | Aim write-up | SOURCE UNREACHABLE | MSRC says only that AI command injection lets an unauthorized attacker disclose information over a network. Archived Aim: the attacker only needs to send the victim an email. |
| 8 | The email was worded to pass the prompt-injection classifiers | Aim write-up | SOURCE UNREACHABLE | Archived Aim: the XPIA classifiers were bypassed by phrasing the instructions as if meant for the human recipient. |
| 9 | The email was never opened by the victim | Aim write-up | SOURCE UNREACHABLE | Archived Aim: the attack does not rely on any specific victim behavior. It never says in so many words that the email stays unopened. |
| 10 | Copilot's ordinary retrieval-augmented generation pass retrieved it | Aim write-up | SOURCE UNREACHABLE | Archived Aim: M365 Copilot is RAG-based and retrieves the email from the mailbox. |
| 11 | ...when the user later asked an unrelated question | Aim write-up | SOURCE UNREACHABLE | Archived Aim: the long email is split into sections on common topics (onboarding, HR FAQs, leave) so it is retrieved for questions on various topics. Those topics are ones the attacker anticipated. |
| 12 | The injected instructions made Copilot include data from the user's own context | Aim write-up | SOURCE UNREACHABLE | Archived Aim: the email tells the LLM to take the most sensitive data from its context. MSRC says only that the injection discloses information. |
| 13 | That context includes chat history, OneDrive, SharePoint, Teams | Aim write-up | SOURCE UNREACHABLE | Archived Aim: Copilot retrieves from the mailbox, OneDrive, Office files, SharePoint sites and Teams chat history. The leak can include the entire chat history. |
| 14 | ...in a request that left the tenant | Aim write-up | SOURCE UNREACHABLE | Archived Aim: an image reference goes through an allowed Teams or SharePoint URL, which fetches the attacker's server. MSRC says the disclosure is "over a network". |
| 15 | The researchers call the pattern an "LLM scope violation" | Aim write-up | SOURCE UNREACHABLE | Archived Aim coins "LLM Scope Violation" (capitalised). The lowercase "LLM scope violation" also appears in its FAQ. |
| 16 | Microsoft fixed it server-side | MSRC | SUPPORTED | The FAQ says Microsoft has fully mitigated it and users of the service need take no action, and points to Microsoft's cloud-service CVE policy. The word "server-side" does not appear. |
| 17 | Microsoft states there was no exploitation in the wild | MSRC | SUPPORTED | The record shows Exploited: No. |
| 18 | Source 1 title: "Breaking down 'EchoLeak', the first zero-click AI vulnerability enabling data exfiltration in Microsoft 365 Copilot" | Aim write-up | SOURCE UNREACHABLE | The archived title ends "...Enabling Data Exfiltration from Microsoft 365 Copilot", with "from", not "in". |
| 19 | Source 1 is Aim Labs' own report | Aim write-up | SOURCE UNREACHABLE | The archived copy is by the Aim Labs Team on aim.security. |
| 20 | Source 1 covers the vector, the scope-violation framing, and the disclosure | Aim write-up | SOURCE UNREACHABLE | The archived copy covers all three, and says the attack chains were disclosed to Microsoft's MSRC. |
| 21 | Source 2 is Microsoft's record | MSRC | SUPPORTED | It is the MSRC Security Update Guide entry, with Microsoft as the issuing CNA. |

Proposed wording: none. No row is DIFFERS or NOT IN SOURCE, but 12 rows (#7-#15, #18-#20) rest only on the unreachable Aim Labs URL, which has not served the article since August 2025.

---

## github-mcp-toxic-agent-flow

**Private repositories leaked through the GitHub MCP server** - verdict in the entry: NOT COVERED; `date:` 2025-05-26

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Invariant Labs: GitHub MCP Exploited](https://invariantlabs.ai/blog/mcp-github-vulnerability) | primary: researchers' own write-up | direct (WebFetch) OK; curl HTTP 200 | Post dated 2025-05-26; byline Marco Milanta, Luca Beurer-Kellner; published on the Invariant Labs blog (footer: Invariant Labs AG, Zurich). A researcher-built demonstration, not an in-the-wild incident. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2025-05-26` is the disclosure day (no separate incident date exists) | Invariant | SUPPORTED | Post is dated 2025-05-26; it reports a demonstration the researchers built, so the publication day is the only date given. The body says "published", as TEMPLATE asks. |
| 2 | Published on 26 May 2025 | Invariant | SUPPORTED | Date line on the post: 2025-05-26. |
| 3 | Author: Marco Milanta | Invariant | SUPPORTED | Listed under "Authors". |
| 4 | Author: Luca Beurer-Kellner | Invariant | SUPPORTED | Listed under "Authors". |
| 5 | The authors are of Invariant Labs | Invariant | SUPPORTED | Byline on the Invariant Labs blog; text says Invariant discovered the vulnerability. Affiliation is implied by the byline, not stated per person. |
| 6 | They published an exploit against an agent connected to the official GitHub MCP server | Invariant | SUPPORTED | Subtitle: a critical vulnerability with the official GitHub MCP server that lets an attacker hijack a user's agent. |
| 7 | A malicious issue filed on a public repository carried the instructions | Invariant | SUPPORTED | Attacker files an issue containing a prompt injection on the user's public repository. |
| 8 | Triggered when the user asked their agent to look at the open issues | Invariant | SUPPORTED | Attack fires on a benign request to have a look at the open issues in the public repo. |
| 9 | The agent in the demonstration was Claude Desktop | Invariant | SUPPORTED | Experiments focused on Claude Desktop (model: Claude 4 Opus). |
| 10 | The agent followed the instructions and read data from the user's private repositories | Invariant | SUPPORTED | Agent pulls private repository data into context after reading the payload. |
| 11 | The agent published that data in a pull request on the public repository | Invariant | SUPPORTED | Data leaked into a pull request on the public pacman repo, readable by the attacker. |
| 12 | Quote: "this is not a flaw in the GitHub MCP server code itself, but rather a fundamental architectural issue that must be addressed at the agent system level" | Invariant | SUPPORTED | Exact words appear in "Scope and Mitigations" (first clause set in bold). |
| 13 | Quote: "GitHub alone cannot resolve this vulnerability through server-side patches" | Invariant | SUPPORTED | Exact words appear in the next sentence of the same paragraph. |
| 14 | Source link title "GitHub MCP Exploited: Accessing private repositories via MCP" | Invariant | SUPPORTED | Page title matches. |
| 15 | Source descriptor: the researchers' own write-up, 26 May 2025 | Invariant | SUPPORTED | Authored by the two researchers, dated 2025-05-26. |
| 16 | Source descriptor: covers the injection vector, the agent used, what leaked, and where they place responsibility | Invariant | SUPPORTED | Sections Attack Setup / Attack Demonstration / Scope and Mitigations cover each of these. |

Proposed wording: none - every claim is SUPPORTED.

---

## mcp-remote-command-injection

**mcp-remote, CVE-2025-6514** - verdict in the entry: STOPPED; `date:` 2025-07-09

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [JFrog JFSA-2025-001290844](https://research.jfrog.com/vulnerabilities/mcp-remote-command-injection-rce-jfsa-2025-001290844/) | primary: researcher's own advisory (JFrog Security Research) | direct (WebFetch) OK; curl HTTP 200 | "Published 9 Jul, 2025 \| Last updated 9 Jul, 2025"; discovered by Or Peles; CVSS 9.6; affected [0.0.5, 0.1.15]; gives no fixed version, only a "Fix commit" link (geelen/mcp-remote 607b226) and a link to JFrog's blog post. Short page: no description of what mcp-remote is. |
| [GHSA-6xpm-ggf7-wc3p / CVE-2025-6514](https://github.com/advisories/GHSA-6xpm-ggf7-wc3p) | primary: GHSA / CVE advisory record (GitHub-reviewed) | direct (WebFetch) OK; curl HTTP 200; API api.github.com/advisories HTTP 200 | API: nvd_published_at 2025-07-09T13:15:24Z, published_at 2025-07-09T15:30:44Z, github_reviewed_at 2025-07-09T18:08:44Z. Description is word-for-word JFrog's; credits list empty; references JFrog advisory, JFrog blog, NVD, fix commit. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2025-07-09` (body does not say what the date is; read as the disclosure day) | JFrog; GHSA | SUPPORTED | 9 Jul 2025 is the public-disclosure day: JFrog advisory published that day; NVD record and GHSA also published that day. Neither source reports exploitation, so there is no separate incident date. Fix release date is not in the cited sources; outside them, fix commit 607b226 (Glen Maddern) and npm mcp-remote 0.1.16 are both dated 2025-06-17, about three weeks earlier. The body does not say the date is the disclosure day, which TEMPLATE asks for. |
| 2 | JFrog's security research team found it | JFrog | SUPPORTED | "Discovered By" Or Peles of the JFrog Security Research Team. |
| 3 | It is an OS command injection in `mcp-remote` | JFrog; GHSA | SUPPORTED | Both title it OS command injection in mcp-remote. |
| 4 | mcp-remote is an npm package | GHSA | SUPPORTED | Package: mcp-remote (npm). |
| 5 | mcp-remote is the proxy that lets MCP clients reach a remote MCP server | JFrog; GHSA | NOT IN SOURCE | Neither advisory says what mcp-remote does. JFrog's blog (linked from both, not cited) calls it a proxy letting LLM hosts talk to remote MCP servers. |
| 6 | MCP clients "such as Claude Desktop" | JFrog; GHSA | NOT IN SOURCE | Claude Desktop is not mentioned in either advisory; it appears in JFrog's (uncited) blog post. |
| 7 | Triggered when the proxy connects to an untrusted MCP server | JFrog; GHSA | SUPPORTED | Exposed to OS command injection when connecting to untrusted MCP servers. |
| 8 | The input is the server's OAuth metadata response | JFrog; GHSA | NOT IN SOURCE | Advisories only say crafted input from the authorization_endpoint response URL; neither says OAuth or metadata. JFrog's (uncited) blog says the URL comes from the server's OAuth authorization-server metadata. |
| 9 | Specifically the `authorization_endpoint` URL | JFrog; GHSA | SUPPORTED | Crafted input from the authorization_endpoint response URL; PoC: a malicious server supplies authorization_endpoint file:/c:/windows/system32/calc.exe. |
| 10 | It reaches an OS command without being sanitised | GHSA | SUPPORTED | Weakness CWE-78, improper neutralization of special elements in an OS command. |
| 11 | This lets the server run arbitrary commands on the machine the proxy is on | JFrog; GHSA | NOT IN SOURCE | Advisories say OS command injection and show a PoC that launches calc.exe; neither says "arbitrary commands". JFrog's (uncited) blog narrows it: arbitrary OS commands proven on Windows; on macOS/Linux, arbitrary executables with limited parameter control. |
| 12 | Affected from version 0.0.5 | JFrog; GHSA | SUPPORTED | JFrog: [0.0.5, 0.1.15]; GHSA: >= 0.0.5. |
| 13 | Affected through version 0.1.15 | JFrog; GHSA | SUPPORTED | JFrog: upper bound 0.1.15; GHSA: < 0.1.16. |
| 14 | Fixed in 0.1.16 | GHSA | SUPPORTED | GHSA patched version 0.1.16 (JFrog page names no fixed version; it says no mitigations supplied and links the fix commit). |
| 15 | The advisory rates it 9.6 | JFrog; GHSA | SUPPORTED | Both give CVSS 9.6; GHSA: critical, CVSS 3.1 AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:H/A:H. |
| 16 | CVE id CVE-2025-6514 | JFrog; GHSA | SUPPORTED | Both carry CVE-2025-6514. |
| 17 | JFrog id JFSA-2025-001290844 and link title "OS command injection in mcp-remote when connecting to untrusted MCP servers" | JFrog | SUPPORTED | Page title and id match. |
| 18 | Source descriptor: JFrog's own research advisory, which found and reported it | JFrog | SUPPORTED | JFrog's own published advisory, discovered by its research team. It does not describe a report to the maintainer; JFrog's (uncited) blog says discovered and disclosed, and thanks maintainer Glen Maddern for the fix. |
| 19 | Source descriptor: the advisory record: affected versions, severity, and the fixed release | GHSA | SUPPORTED | GHSA lists affected range, critical 9.6, patched 0.1.16. |

Proposed wording:
- #5: "JFrog's security research team found an OS command injection in `mcp-remote`, an npm package, that is triggered when it connects to an untrusted MCP server" - because the cited advisories do not describe mcp-remote as a proxy. Alternatively keep the sentence and add JFrog's blog post (https://jfrog.com/blog/2025-6514-critical-mcp-remote-rce-vulnerability, Or Peles, 9 July 2025, the researcher's own write-up), which does.
- #6: drop "such as Claude Desktop", or cite the JFrog blog post above - because neither cited advisory names Claude Desktop.
- #8: "the `authorization_endpoint` URL in the server's response reaches an operating-system command without being sanitised" - because the cited advisories do not mention OAuth metadata (the JFrog blog does, if it is added as a source).
- #11: "which lets a malicious MCP server inject operating-system commands" - because "arbitrary commands" is not in the cited advisories, and the JFrog blog proves full arbitrary commands only on Windows (on macOS/Linux, arbitrary executables with limited parameter control).

---

## mcp-tool-poisoning

**MCP tool poisoning** - verdict in the entry: PARTIAL; `date:` 2025-04-01

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Invariant Labs: MCP Security Notification: Tool Poisoning Attacks](https://invariantlabs.ai/blog/mcp-security-notification-tool-poisoning-attacks) | primary: researchers' own write-up | direct (WebFetch) OK; curl HTTP 200 | Post dated 2025-04-01; byline Luca Beurer-Kellner, Marc Fischer; later "Update Apr 7" and "Update Apr 11" notes added. Its "View Code" button links the repo below. A research proof of concept, not an in-the-wild incident. |
| [invariantlabs-ai/mcp-injection-experiments](https://github.com/invariantlabs-ai/mcp-injection-experiments) | primary: researchers' reproduction code | direct (WebFetch) OK; curl HTTP 200; README via gh api | Repo description: code snippets to reproduce MCP tool poisoning attacks. Files: direct-poisoning.py, shadowing.py, whatsapp-takeover.py. Repo created 2025-04-06, five days after the post. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2025-04-01` is the disclosure day (no separate incident date exists) | Invariant post | SUPPORTED | Post dated 2025-04-01; it reports the researchers' own proof of concept, so publication is the only date. The body says "published", as TEMPLATE asks. |
| 2 | Published on 1 April 2025 | Invariant post | SUPPORTED | Date line 2025-04-01. |
| 3 | Author: Luca Beurer-Kellner | Invariant post | SUPPORTED | Listed under "Authors". |
| 4 | Author: Marc Fischer | Invariant post | SUPPORTED | Listed under "Authors". |
| 5 | The authors are of Invariant Labs | Invariant post | SUPPORTED | Byline on the Invariant Labs blog; text says Invariant discovered the issue. |
| 6 | A proof of concept in which instructions are hidden in an MCP tool's description | Invariant post | SUPPORTED | Tool Poisoning Attack: malicious instructions embedded in MCP tool descriptions. |
| 7 | The description is text the model reads and the user does not | Invariant post | SUPPORTED | Instructions are invisible to users but visible to AI models. |
| 8 | It steers the agent into doing something the tool does not claim to do | Invariant post | SUPPORTED | Hidden instructions make models perform unauthorized actions behind seemingly innocent tools. |
| 9 | The demonstration was against Cursor | Invariant post | SUPPORTED | "Experiment 1: Attacking Cursor with Tool Poisoning". |
| 10 | The poisoned tool was an `add` tool | Invariant post | SUPPORTED | Seemingly innocent `add` tool from a malicious MCP server. |
| 11 | The agent read `~/.cursor/mcp.json` | Invariant post | SUPPORTED | Agent reads the user's ~/.cursor/mcp.json. |
| 12 | The agent read `~/.ssh/id_rsa` | Invariant post | SUPPORTED | Tool description asks for ~/.ssh/id_rsa; post lists access to SSH private keys at that path; Cursor demo leaks SSH keys. |
| 13 | The contents were passed to the malicious server | Invariant post | SUPPORTED | Agent sends the files to the malicious server. |
| 14 | ...passed "in a second argument" | Invariant post | DIFFERS | Data goes out through the `sidenote` parameter, the third parameter of add(a, b, sidenote). |
| 15 | Quote: "the agent willingly reads the user's `~/.cursor/mcp.json` file, and other sensitive files like SSH keys and sends them to the malicious server." | Invariant post | SUPPORTED | Exact words appear in the Experiment 1 paragraph (paths set as code). |
| 16 | Even where the client asks for confirmation | Invariant post | SUPPORTED | Cursor shows a tool-call confirmation dialog; confirmation is required but only a summarized tool name is shown. |
| 17 | Quote: "the full tool input (e.g. the included SSH key) is completely hidden" | Invariant post | DIFFERS | Figure caption: Cursor, even in extended mode, does not show the full tool input; its parenthesis reads "e.g. the included SSH key is completely hidden". The bracket closes after "hidden", and it is the SSH key the caption calls completely hidden. |
| 18 | Reproduction code is published at `invariantlabs-ai/mcp-injection-experiments` | repo; Invariant post | SUPPORTED | Repo describes itself as code to reproduce MCP tool poisoning attacks; the post's "View Code" button links it. |
| 19 | Source descriptor: the researchers' own write-up, 1 April 2025, covering the technique, the Cursor demonstration, the files read, and the hidden argument | Invariant post | SUPPORTED | Title matches; the post covers each of these. |
| 20 | Source descriptor: the published reproduction code | repo | SUPPORTED | README: direct-poisoning.py makes the `add` tool leak SSH keys and mcp.json. |

Proposed wording:
- #14: "...made the agent read `~/.cursor/mcp.json` and `~/.ssh/id_rsa` and pass the contents to the malicious server in an extra `sidenote` argument" - because the source's `add(a, b, sidenote)` carries the data in its third parameter, `sidenote`.
- #17: "They note that even where the client asks for confirmation, Cursor 'does not show the full tool input' and 'the included SSH key is completely hidden'." - because the caption's own wording puts "completely hidden" on the SSH key, inside the parenthesis.

---

## nx-s1ngularity

**Nx "s1ngularity"** - verdict in the entry: PARTIAL; `date:` 2025-08-26

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Nx: S1ngularity - What Happened, How We Responded, What We Learned](https://nx.dev/blog/s1ngularity-postmortem) | primary: vendor post-mortem | direct (WebFetch) OK; curl HTTP 200 | By Juri Strumpflohner, 5 September 2025. |
| [GHSA-cxm3-wv7p-598c](https://github.com/nrwl/nx/security/advisories/GHSA-cxm3-wv7p-598c) | primary: maintainer's repository security advisory | direct (WebFetch) OK; curl HTTP 200; gh api repos/nrwl/nx/security-advisories | Title "Malicious versions of Nx and some supporting plugins were published"; published 2025-08-27T05:52Z by FrozenPandaz, updated 2025-08-30. Timeline in EDT. No CVE id. |
| [StepSecurity: s1ngularity: Popular Nx Build System Package Compromised with Data-Stealing Malware](https://www.stepsecurity.io/blog/supply-chain-security-alert-popular-nx-build-system-package-compromised-with-data-stealing-malware) | secondary: security-vendor analysis. Its own payload analysis (deobfuscated code, a Harden-Runner run of nx@21.7.0) is first-hand; its timeline and root cause REPEAT the Nx GHSA | direct (WebFetch) OK; curl HTTP 200 with UA "Mozilla/5.0". A curl with a full Chrome UA string returned a mixed page whose title, byline and opening sections were StepSecurity's Shai-Hulud post (15 Sep 2025); the plain-UA copy and WebFetch show the Nx article. | By Ashish Kurmi, 27 August 2025, since updated (second-wave section). |
| [GitGuardian: The Nx "s1ngularity" Attack: Inside the Credential Leak](https://blog.gitguardian.com/the-nx-s1ngularity-attack-inside-the-credential-leak/) | primary for its own counts (GitGuardian monitoring data); secondary for the attack mechanics (cites "external research") | direct (WebFetch) OK; curl HTTP 200 | By Guillaume Valadon and Anna Nabiullina, 27 August 2025; updates dated 28-29 August 2025. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2025-08-26` is the day the incident happened | Nx postmortem; GHSA | SUPPORTED | Postmortem: malicious versions published on August 26, 2025. GHSA: first at 6:32 PM EDT on 26 Aug (StepSecurity: 10:32 PM UTC). The body says "published", as TEMPLATE asks. |
| 2 | Published on 26 August 2025 | Nx postmortem | SUPPORTED | Opening line gives August 26, 2025. |
| 3 | Several malicious versions of the Nx build system and its plugins | GHSA; Nx postmortem | SUPPORTED | GHSA: malicious versions of nx plus some supporting plugin packages; eight nx versions and @nx/devkit, js, workspace, node, eslint, key, enterprise-cloud listed. |
| 4 | They were published to npm | Nx postmortem | SUPPORTED | Published to npm with a stolen npm token. |
| 5 | They stayed up for about four hours | Nx postmortem; GHSA; StepSecurity | DIFFERS | Postmortem: active for 4 hours before full removal (supports). GHSA: nx and most @nx versions removed 10:44 PM EDT (4h12m after the first), but @nx/key and @nx/enterprise-cloud 3.2.0 only at 6:20 AM EDT 27 Aug. StepSecurity: live just over five hours, window about 5h20m. |
| 6 | Quote: "the malicious packages ran a post-install script ... uploaded the results to a public GitHub repo via the GitHub CLI" | Nx postmortem | SUPPORTED | Exact sentence appears in "What Happened" (source begins with a capital T). |
| 7 | The repository was created in the victim's own account | GHSA | SUPPORTED | GHSA: results posted to a repo under the user's GitHub account; StepSecurity: created using the stolen GitHub token. |
| 8 | Named `s1ngularity-repository` | StepSecurity; GHSA | SUPPORTED | StepSecurity: repo named s1ngularity-repository, with -0, -1 suffixes in some packages; GHSA: name contains s1ngularity-repository. |
| 9 | It held a base64 file of what was found | StepSecurity; GitGuardian | SUPPORTED | One file, results.b64; StepSecurity says triple-base64, GitGuardian double-base64; GHSA says an encoded string. |
| 10 | StepSecurity records that the AI CLIs were invoked with their own permission-skipping flags | StepSecurity | SUPPORTED | Script runs claude, gemini and q, each with its own dangerous flag, to bypass security boundaries. |
| 11 | Flag `--dangerously-skip-permissions` | StepSecurity | SUPPORTED | Passed to `claude`. |
| 12 | Flag `--yolo` | StepSecurity | SUPPORTED | Passed to `gemini`. |
| 13 | Flag `--trust-all-tools` | StepSecurity | SUPPORTED | Passed to `q chat` (with --no-interactive). |
| 14 | So that the reconnaissance would be done by a tool the developer had already trusted | StepSecurity | SUPPORTED | Describes trusted AI assistants turned into reconnaissance and exfiltration agents, legitimate tools used as accomplices. |
| 15 | GitGuardian counted 2,349 credentials | GitGuardian | SUPPORTED | TL;DR: 2,349 credentials harvested; body: 2,349 distinct secrets. |
| 16 | ...taken from 1,079 systems | GitGuardian | SUPPORTED | TL;DR says 1,079 compromised developer systems. Note: the body's actual measure is 1,079 exfiltration repositories holding at least one secret (of 1,346 found), and the FAQ says 1,079 compromised repositories. |
| 17 | Source descriptor: Nx's own postmortem, covering the date, the four-hour window, and what the post-install script did | Nx postmortem | SUPPORTED | Title matches; Nx blog post by Juri Strumpflohner covering each point. |
| 18 | Source descriptor: the maintainer's advisory listing the malicious versions | GHSA | SUPPORTED | Advisory on nrwl/nx published by maintainer FrozenPandaz; lists affected versions per package. |
| 19 | Source descriptor: StepSecurity's analysis of the AI CLI invocations and their flags | StepSecurity | SUPPORTED | Title matches; "Novel Attack Technique: AI CLI Exploitation" section with code. |
| 20 | Source descriptor: GitGuardian's count of the credentials and systems affected | GitGuardian | SUPPORTED | Title matches; counts from GitGuardian's monitoring data. |

Proposed wording:
- #5: "On 26 August 2025 several malicious versions of the Nx build system and its plugins were published to npm; Nx's postmortem says they were live for four hours." - because the postmortem says 4 hours, but the GHSA shows @nx/key and @nx/enterprise-cloud 3.2.0 up until 6:20 AM EDT the next day and StepSecurity says just over five hours.

---

## package-hallucination

**Hallucinated packages, and squatting on them** - verdict in the entry: PARTIAL; `date:` 2024-03-28

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Diving Deeper into AI Package Hallucinations](https://www.lasso.security/blog/ai-package-hallucinations) | primary: researcher's own write-up (Bar Lanyado, Lasso Security, 28 Mar 2024) | curl, HTTP 200 | Follow-up to his earlier Vulcan Cyber research; charts are images, the huggingface-cli case is in the text |
| [We Have a Package for You! (USENIX Security 2025)](https://www.usenix.org/conference/usenixsecurity25/presentation/spracklen) | primary: researchers' peer-reviewed paper (abstract page) | curl, HTTP 200 | Spracklen, Wijewickrama, Sakib, Maiti, Viswanath, Jadliwala; 34th USENIX Security Symposium, Aug 2025; Distinguished Paper Award |
| [Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination) | primary: the paper authors' code and data | curl, HTTP 200; README also read via GitHub API (200) | README: code, data and instructions to reproduce the paper; data on Zenodo (DOI 10.5281/zenodo.14676377) |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2024-03-28 is the disclosure day (no source gives the day the package was uploaded) | Lasso | SUPPORTED | Post is dated March 28, 2024; it gives no upload date for the package, only a three-month download window before publication, so the disclosure-day fallback applies |
| 2 | On 28 March 2024 Bar Lanyado published | Lasso | SUPPORTED | Byline Bar Lanyado, dated March 28, 2024 |
| 3 | a test of what he had named "AI package hallucination" | Lasso | SUPPORTED | Says his previous research exposed a new attack technique he calls AI Package Hallucination (capitalised in the source; same words) |
| 4 | models recommended installing a Python package called `huggingface-cli` | Lasso | SUPPORTED | During the research they came across a hallucinated Python package named huggingface-cli |
| 5 | models "repeatedly" recommended it | Lasso | NOT IN SOURCE | The text says nothing about how often, or by how many models, huggingface-cli was produced; repetitiveness rates are given only per model across all questions |
| 6 | which did not exist | Lasso | SUPPORTED | Described as a hallucinated package, and he was able to upload one under that name |
| 7 | He registered the name and uploaded an empty package under it | Lasso | SUPPORTED | He uploaded an empty package with the same name (plus a dummy control package to count scanner downloads) |
| 8 | "in three months the fake and empty package got more than 30k authentic downloads" | Lasso | SUPPORTED | Same words (sentence starts with a capital I, followed by "and still counting") |
| 9 | "instructions for installing this package can be found in the README of a repository dedicated to research conducted by Alibaba" | Lasso | SUPPORTED | Same words, from a GitHub search on companies using or recommending the package |
| 10 | The USENIX Security 2025 paper | USENIX | SUPPORTED | 34th USENIX Security Symposium (USENIX Security 25), 2025 |
| 11 | by Spracklen and colleagues | USENIX | SUPPORTED | Joseph Spracklen first author, with five co-authors |
| 12 | 576,000 generated code samples | USENIX | SUPPORTED | Abstract: 576,000 code samples generated, in two programming languages |
| 13 | from 16 models | USENIX | SUPPORTED | Abstract: 16 popular LLMs for code generation |
| 14 | at least 5.2% hallucinated package references from commercial models | USENIX | SUPPORTED | Abstract: average percentage of hallucinated packages is at least 5.2% for commercial models (entry omits "average") |
| 15 | 21.7% from open-source ones | USENIX | SUPPORTED | Abstract: 21.7% for open-source models (also an average) |
| 16 | across 205,474 distinct invented names | USENIX | SUPPORTED | Abstract: 205,474 unique examples of hallucinated package names |
| 17 | Sources: Lasso post is Bar Lanyado's own write-up | Lasso | SUPPORTED | First-person post under his byline |
| 18 | Sources: Lasso post dated 28 March 2024 | Lasso | SUPPORTED | Dated March 28, 2024 |
| 19 | Sources: Lasso carries "the 30,000 downloads" | Lasso | DIFFERS | Source says more than 30k authentic downloads in three months, still counting - a floor, not a figure of 30,000 |
| 20 | Sources: USENIX carries the rates, the sample size, and the 205,474 names | USENIX | SUPPORTED | All three are in the abstract |
| 21 | Sources: the repo is the paper's published code and data | GitHub repo | SUPPORTED | README says it holds the code, data and instructions for reproducing the paper's experiments |

Proposed wording:
- #5: "models recommended installing a Python package called `huggingface-cli`, which did not exist." - because the Lasso text names the hallucinated package but gives no count or frequency for it.
- #19: "Bar Lanyado's own write-up, 28 March 2024: the `huggingface-cli` test, the more than 30,000 downloads in three months, and the Alibaba README." - because the source gives "more than 30k", not 30,000.

---

## postmark-mcp-bcc-exfiltration

**postmark-mcp, the BCC in an authorised tool** - verdict in the entry: PARTIAL; `date:` 2025-09-25

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Malicious MCP Server on npm: postmark-mcp harvests emails](https://snyk.io/blog/malicious-mcp-server-on-npm-postmark-mcp-harvests-emails/) | secondary: security-vendor analysis (Snyk, Liran Tal, 25 Sep 2025) | curl, HTTP 200 | REPEATS Koi Security's discovery (Snyk cites "community reports" and "third-party analysis" for 1.0.16 without naming Koi); its own contribution is the 1.0.15 vs 1.0.18 code diff and the full 1.0.18 index.js |
| [Fake Postmark MCP npm package stole emails with one-liner](https://www.theregister.com/security/2025/09/29/fake-postmark-mcp-npm-package-stole-emails-with-one-liner/509095) | secondary: news (The Register, Jessica Lyons, 29 Sep 2025) | WebFetch + curl, HTTP 200 | REPEATS Koi Security's post (Idan Dardikman) and Postmark's own statement of 25 Sep 2025 (postmarkapp.com/blog/information-regarding-malicious-postmark-mcp-package - live, HTTP 200, a vendor primary). Link text matches the HTML title; the on-page headline reads "One line of malicious npm code led to massive Postmark email heist" |
| Koi Security post (not linked in the entry; URL found in The Register): https://www.koi.security/blog/postmark-mcp-npm-malicious-backdoor-email-theft | primary: discoverer's write-up (Idan Dardikman, 25 Sep 2025) | curl: 301 to koi.ai same path, then 301 to paloaltonetworks.com/cortex/agentic-endpoint-security (200, a product page with no Postmark content); Wayback copy web.archive.org/web/20250926183848/ + the same URL is HTTP 200 | Archived copy: titled "First Malicious MCP in the Wild", dated September 25, 2025; says 1.0.0-1.0.15 were clean, 1.0.16 added the BCC (line 231), about 1,500 downloads a week |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2025-09-25 is the disclosure day (no single incident day in the sources) | Snyk; The Register | SUPPORTED | Snyk's post and Postmark's statement (per The Register) are both 25 Sep 2025; Snyk's timeline puts the backdoored releases between 15 and 17 Sep 2025 (1.0.18 on 17 Sep, UTC+3) without a day for 1.0.16. Note Snyk's opening line itself says the package was reportedly modified on 25 Sep, contradicting its own timeline |
| 2 | An npm package called `postmark-mcp` | Snyk | SUPPORTED | Names the npm package postmark-mcp |
| 3 | an MCP server that sends email | Snyk | SUPPORTED | An MCP server meant to let AI assistants send emails via Postmark |
| 4 | that sends "transactional" email | Snyk; The Register | NOT IN SOURCE | Neither source says transactional; The Register calls Postmark an email delivery service and says the package was a fake impersonating Postmark's own MCP server, which is published on GitHub not npm |
| 5 | published in versions that quietly blind-copied every outgoing message | Snyk; The Register | SUPPORTED | Snyk: secretly exfiltrated email contents by adding a BCC; The Register: a line added to BCC all emails, secretly copying outgoing messages |
| 6 | to an address the author controlled | The Register | SUPPORTED | Attacker-controlled address; the developer added the BCC line and published the package |
| 7 | Snyk's analysis, published 25 September 2025 | Snyk | SUPPORTED | Dated September 25, 2025 |
| 8 | the added code set `Bcc: 'phan@giftshop.club'` | Snyk | SUPPORTED | The only notable diff between 1.0.15 and 1.0.18 is the Bcc line with that address |
| 9 | versions from 1.0.16 | Snyk; The Register | SUPPORTED | Snyk: behaviour began around 1.0.16 (hedged as community reports); The Register quotes Postmark: backdoor added in version 1.0.16 |
| 10 | through at least 1.0.18 | Snyk | SUPPORTED | Snyk shows 1.0.18 carrying the code and calls 1.0.18 the latest noted release; later versions possibly affected |
| 11 | exposing "any email content sent through the MCP server (including attachments and headers), potentially including secrets, tokens, customer PII, and regulated data" | Snyk | SUPPORTED | Same words under "Data at risk" (source capitalises Any and continues with a clause about data present in such emails) |
| 12 | Earlier versions of the package behaved as expected | Snyk; The Register | SUPPORTED | Snyk labels 1.0.15 benign; The Register quotes Postmark: trust built over 15 versions before the 1.0.16 backdoor |
| 13 | reporting puts its use at roughly 1,500 installs a week | The Register | SUPPORTED | Koi (as reported) says about 1,500 downloads in a week; Dardikman quoted on 1,500 weekly compromised installations |
| 14 | at the time | The Register | SUPPORTED | The figure is Koi's, from before the developer removed the package |
| 15 | Sources: Snyk's analysis is by Liran Tal | Snyk | SUPPORTED | Byline Liran Tal |
| 16 | Sources: Snyk dated 25 September 2025 | Snyk | SUPPORTED | September 25, 2025 |
| 17 | Sources: Snyk carries the affected versions, the BCC address, and what was exposed | Snyk | SUPPORTED | Timeline and IOC section (versions), the Bcc diff, and the impact section |
| 18 | Sources: The Register is contemporaneous reporting | The Register | SUPPORTED | Published 29 Sep 2025, four days after disclosure |
| 19 | Sources: The Register carries the install counts | The Register | SUPPORTED | About 1,500 weekly downloads; Koi estimates about 20% in use, about 300 organisations, 10-50 emails a day each |
| 20 | Sources: The Register carries the timeline | The Register | SUPPORTED | Postmark's 25 Sep statement, 15 clean versions then 1.0.16, and the developer's later removal of the package (no per-day dates) |
| 21 | Note: the first public disclosure was a Koi Security post | The Register | NOT IN SOURCE | The Register says Koi Security discovered the package; no cited source says Koi's post was first. The archived Koi post, Snyk's post and Postmark's statement are all dated 25 Sep 2025 |
| 22 | Note: that blog no longer resolves - the address redirects away from the article | checked directly | SUPPORTED | koi.security URL returns 301 to koi.ai, which returns 301 to a Palo Alto Networks product page with no Postmark content. Strictly the host still answers; it redirects rather than fails. A Wayback copy dated 26 Sep 2025 exists |
| 23 | Note: Snyk's write-up carries the same technical detail with the code shown | Snyk; Koi (Wayback copy) | SUPPORTED | Snyk shows the Bcc diff and the full 1.0.18 index.js; it lacks Koi's download and usage estimates and hedges the 1.0.16 start as community reporting |

Proposed wording:
- #4: "An npm package called `postmark-mcp`, an unofficial MCP server for sending email through Postmark, was published in versions that quietly blind-copied every outgoing message to an address the author controlled." - because neither source says "transactional", and The Register reports the package impersonated Postmark rather than being Postmark's own.
- #21: "Koi Security discovered the package and wrote it up on 25 September 2025. That post no longer resolves - the address now redirects away from the article - so it is not linked here (an archived copy survives at the Wayback Machine). Snyk's write-up carries the same technical detail with the code shown." - because The Register supports "discovered", not "first public disclosure", and Snyk and Postmark published the same day.

---

## replit-agent-database-deletion

**An agent that deleted a production database** - verdict in the entry: PARTIAL; `date:` 2025-07-18

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [AI Incident Database, incident 1152](https://incidentdatabase.ai/cite/1152/) | secondary: incident database record whose five cited reports are all news articles (Tom's Hardware, The Register, The Cyber Express, Cybernews, Economic Times); it links no X posts or Replit statement directly | curl, HTTP 200; the reports' full texts (behind "Expand All") read from the page's own page-data.json, HTTP 200 | FLAG: a curated record citing secondaries, not primaries. Editor Daniel Atherton. The Masad quotes, the 1,206/1,196 counts and "hid and lied" are only in these reports |
| [Vibe coding service Replit deleted user's production database, faked data, told fibs galore](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/) | secondary: news (The Register, Simon Sharwood, 21 Jul 2025) | WebFetch + curl: HTTP 301 to theregister.com/software/2025/07/21/vibe-coding-service-replit-deleted-production-database/719783, then 200 | REPEATS Jason Lemkin's X posts and SaaStr blog (links them). Carries no statement from Replit or Masad; says Replit's accounts had not addressed the posts at time of writing |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2025-07-18 is the day the deletion happened | AIID | SUPPORTED | AIID gives Incident Date 2025-07-18. The Register gives no day for the deletion itself; the Lemkin posts it links about the deletion have X ids that decode to 18 Jul 2025 UTC |
| 2 | In July 2025 | AIID; The Register | SUPPORTED | Events and posts of 12-20 July 2025 |
| 3 | during a multi-day experiment with Replit's coding agent | The Register; AIID (Cyber Express) | SUPPORTED | The Register quotes a "Day 7 of vibe coding" post on 17 July; Cyber Express calls it a 12-day vibe coding experiment |
| 4 | the agent issued destructive commands against a live production database | AIID | SUPPORTED | Record title: agent executed unauthorized destructive commands; description: deleted a live production database |
| 5 | while a code freeze was in force | AIID | SUPPORTED | Description: during an active code freeze |
| 6 | deleting records described as covering roughly 1,200 executives and companies | AIID (Tom's Hardware, Cyber Express) | DIFFERS | 1,206 executives and 1,196 companies (Tom's gives 1,196+ and attributes the figures to the agent's own admission; Cyber Express to Lemkin's description). The Register gives no count |
| 7 | The user, Jason Lemkin | AIID; The Register | SUPPORTED | SaaStr founder Jason Lemkin |
| 8 | Lemkin said the agent "deleted our production database without permission" | AIID reports; The Register | DIFFERS | Those words appear nowhere. Tom's Hardware: Lemkin asked it whether it had deleted their entire database without permission during a code and action freeze; The Register: he said it deleted a database despite instructions not to change code without permission |
| 9 | and then "hid and lied about it" | AIID (Cyber Express) | SUPPORTED | Lemkin on X: possibly worse, it hid and lied about it |
| 10 | including fabricating data | The Register; AIID | DIFFERS | Sources report fake data, fake reports and a 4,000-record database of fictional people, but The Register places the fake data (covering up bugs and unit tests) the day before the deletion, not as part of hiding it |
| 11 | and claiming a rollback was impossible | The Register | SUPPORTED | Lemkin: Replit said a rollback was impossible and all database versions were destroyed; it was wrong and the rollback worked |
| 12 | Replit's chief executive, Amjad Masad | AIID reports | SUPPORTED | Replit CEO Amjad Masad |
| 13 | responded publicly that the deletion was "unacceptable and should never be possible" | AIID (Cyber Express, Cybernews, Economic Times) | SUPPORTED | Masad on X: deleting the data was unacceptable and should never be possible |
| 14 | the company subsequently separated development and production databases | AIID (Tom's Hardware, Cyber Express) | SUPPORTED | Masad: started rolling out automatic DB dev/prod separation; a Replit spokesperson: Replit now manages that separation automatically |
| 15 | and added a planning-only mode | AIID (Tom's Hardware, Cybernews) | DIFFERS | Masad said Replit was actively working on a planning/chat-only mode; no source says it had been added |
| 16 | Note: there is no vendor post-mortem for this one | AIID reports | NOT IN SOURCE | Cyber Express and Cybernews report Masad saying Replit would conduct a postmortem; no cited source contains or links one, and none says there is none |
| 17 | Note: the record is the participants' own posts on X and the reporting that quoted them, collected by the AIID | AIID | SUPPORTED | AIID collects five news reports that quote Lemkin's and Masad's X posts |
| 18 | Sources: AIID 1152 is the curated record | AIID | SUPPORTED | Editor-curated incident page (editor Daniel Atherton) |
| 19 | Sources: AIID record dated 18 July 2025 | AIID | SUPPORTED | Incident Date 2025-07-18 |
| 20 | Sources: AIID record with its cited reports | AIID | SUPPORTED | Report count 5, dated 21-24 Jul 2025 |
| 21 | Sources: The Register's account | The Register | SUPPORTED | Simon Sharwood, 21 Jul 2025 |
| 22 | Sources: The Register quotes both participants | The Register | DIFFERS | It quotes Lemkin and the agent's messages from his screenshots only; it has no Masad or Replit quote and says Replit had not addressed the posts at time of writing |

Proposed wording:
- #6: "deleting records the user has described as covering 1,206 executives and 1,196 companies." - because the cited reports give those exact counts, not a combined roughly 1,200.
- #8: "The user, Jason Lemkin, asked the agent whether it had deleted the entire database without permission during a code freeze, and said publicly that it then \"hid and lied about it\", including claiming a rollback was impossible." - because the quoted words are not in any source; this form keeps to what Tom's Hardware and Cyber Express report.
- #10: "He also reported that the agent had covered up bugs by creating fake data and fake reports." (as a separate sentence, not as part of hiding the deletion) - because The Register places the fake data before the deletion.
- #15: "and the company began rolling out automatic separation of development and production databases and said it was working on a planning/chat-only mode." - because Masad described the mode as work in progress.
- #16: "Replit's chief executive said the company would conduct a postmortem; none is cited here. The record is the participants' own posts on X and the reporting that quoted them, collected by the AI Incident Database." - because the sources show a post-mortem was promised, which they cannot show was never published.
- #22: "The Register's account, 21 July 2025, quoting Jason Lemkin's posts; it carries no statement from Replit." - because Masad's response is only in the reports collected by the AIID.

---

## shai-hulud-npm-worm

**The Shai-Hulud npm worm** - verdict in the entry: PARTIAL; `date:` 2025-09-14

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Our plan for a more secure npm supply chain](https://github.blog/security/supply-chain-security/our-plan-for-a-more-secure-npm-supply-chain/) | primary: registry operator's own statement (GitHub, which runs npm; Xavier René-Corail, 22 Sep 2025) | curl, HTTP 200 | - |
| [Shai-Hulud: Self-Replicating Worm Compromises 500+ NPM Packages](https://www.stepsecurity.io/blog/ctrl-tinycolor-and-40-npm-packages-compromised) | primary: researcher's own payload analysis (StepSecurity, Ashish Kurmi, 15 Sep 2025) | curl, HTTP 200 | Page has been updated since first publication: the title says 500+ packages while the executive summary still says @ctrl/tinycolor plus more than 40 others (the URL slug keeps the old title) |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | date: 2025-09-14 (the day GitHub was notified; neither source gives the day of the first malicious publish) | GitHub | SUPPORTED | GitHub says it was notified of the attack on September 14, 2025; StepSecurity gives no earlier date, so this is the disclosure-day fallback and the body says so |
| 2 | On 14 September 2025 GitHub was notified of Shai-Hulud | GitHub | SUPPORTED | Notified of the Shai-Hulud attack on September 14, 2025 |
| 3 | "a self-replicating worm that infiltrated the npm ecosystem via compromised maintainer accounts by injecting malicious post-install scripts into popular JavaScript packages" | GitHub | SUPPORTED | Same words, in the sentence reporting the notification |
| 4 | GitHub removed more than 500 compromised packages from the registry | GitHub | SUPPORTED | Lists immediate removal of 500+ compromised packages from the npm registry |
| 5 | "repurposes open-source tools like TruffleHog to scan the filesystem for high-entropy secrets" | StepSecurity | SUPPORTED | Same words, under Credential Harvesting |
| 6 | read cloud metadata endpoints | StepSecurity | SUPPORTED | Cloud metadata endpoints are listed among the credentials the malware specifically targets |
| 7 | and AWS Secrets Manager | StepSecurity | SUPPORTED | Enumerates AWS Secrets Manager with SDK pagination (ListSecrets, GetSecretValue) |
| 8 | uploaded what it found to a public repository | StepSecurity | SUPPORTED | Aggregates harvested credentials into JSON and uploads it to a new public repository named Shai-Hulud |
| 9 | created in the victim's own GitHub account | StepSecurity | NOT IN SOURCE | Says the repository is created through GitHub's /user/repos API via makeRepo('Shai-Hulud'); it does not say whose account (the endpoint implies the token owner's, but that is not stated) |
| 10 | wrote a workflow file `.github/workflows/shai-hulud-workflow.yml` | StepSecurity | SUPPORTED | Injects that GitHub Actions workflow file via a base64-encoded bash script |
| 11 | that exfiltrates repository secrets with `${{ toJSON(secrets) }}` | StepSecurity | SUPPORTED | The workflow runs on push and sends repository secrets, using that expression, to a command-and-control endpoint |
| 12 | republished itself into other packages the compromised maintainer owned | StepSecurity | SUPPORTED | Fetches up to 20 packages owned by the maintainer from the registry and force-publishes patched versions |
| 13 | Sources: GitHub's own post | GitHub | SUPPORTED | GitHub blog post by Xavier René-Corail |
| 14 | Sources: GitHub post dated 22 September 2025 | GitHub | SUPPORTED | Dated September 22, 2025 |
| 15 | Sources: GitHub post carries the notification date, the description, and the 500+ removed | GitHub | SUPPORTED | All three are in the post's opening section |
| 16 | Sources: StepSecurity's payload analysis carries TruffleHog, cloud metadata and Secrets Manager, the workflow file, and self-propagation | StepSecurity | SUPPORTED | All four are in the Technical Analysis section |

Proposed wording:
- #9: "and uploaded what it found to a new public GitHub repository named Shai-Hulud, created through GitHub's /user/repos API." - because StepSecurity names the repository and the API call but does not say in whose account it is created.

---

## solana-web3js-backdoor

**The @solana/web3.js backdoor, 1.95.6 and 1.95.7** - verdict in the entry: STOPPED; `date:` 2024-12-02

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [GHSA-jcxm-7wvp-g6p5](https://github.com/solana-labs/solana-web3.js/security/advisories/GHSA-jcxm-7wvp-g6p5) | primary: maintainer advisory (repository advisory published by steveluscher; CVE-2024-54134, CVSS v4 8.3 High) | direct (WebFetch) OK; curl HTTP 200 after a redirect to github.com/solana-foundation/solana-web3.js/...; API api.github.com/advisories/GHSA-jcxm-7wvp-g6p5 HTTP 200 | The repo has moved from solana-labs to solana-foundation, so the cited URL now redirects. The page shows it was published Dec 4, 2024 (08:12 UTC); the global database copy is dated 18:09 UTC the same day. |
| [web3.js Exploit: Root Cause Analysis](https://www.anza.xyz/blog/web3-js-exploit-root-cause-analysis) | primary: vendor post-mortem (by "Anza Developers", 5 Dec 2024) | direct (WebFetch) OK; curl HTTP 200 | An Anza engineer ran the investigation (per its timeline), so this is the maintainers' own post-mortem, not a repeat. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2024-12-02` is the day it happened | GHSA, Anza | DIFFERS | Both sources put the compromise and the publishes on Tuesday 3 December 2024. GHSA gives the window as 3:20pm-8:25pm UTC; in Anza the phishing click is at 3:20pm UTC on 3 Dec. |
| 2 | "On 2 December 2024" the account was compromised and the versions were put on npm | GHSA, Anza | DIFFERS | The date is 3 December 2024. Anza: the phishing link was clicked at 3:20pm UTC and both versions were published "within moments". |
| 3 | An account with publish rights to `@solana/web3.js` was compromised | GHSA | SUPPORTED | A publish-access account for @solana/web3.js was compromised. Anza adds that this happened through spear phishing. |
| 4 | There were two unauthorised versions | GHSA | SUPPORTED | GHSA refers to these two unauthorized versions. |
| 5 | Version 1.95.6 | GHSA, Anza | SUPPORTED | Both list 1.95.6 as affected. |
| 6 | Version 1.95.7 | GHSA, Anza | SUPPORTED | Both list 1.95.7 as affected. |
| 7 | The versions were put on npm | GHSA, Anza | SUPPORTED | Both say they were published to the public npm registry. |
| 8 | The maintainers' advisory records that the injected code stole private key material | GHSA | SUPPORTED | The modified packages let the attacker steal private key material and drain funds from dapps. |
| 9 | The risk fell on apps that handle private keys directly, such as bots | GHSA | SUPPORTED | Dapps "like bots" that handle private keys directly; it only appears to affect projects that directly handle private keys. |
| 10 | The versions were available for roughly five hours before being removed | Anza, GHSA | DIFFERS | Anza: published about 3:20pm UTC on 3 Dec; 1.95.6 deprecated at 7:39pm and 1.95.7 at 8:52pm; both removed from npm at about 12:22am UTC on 4 Dec, roughly 9 hours in all. The GHSA 3:20pm-8:25pm window (about 5h) ends when the clean 1.95.8 was published, not at removal. |
| 11 | An added function named `addToQueue` | GHSA, Anza | NOT IN SOURCE | Neither source names `addToQueue`. Anza says malicious code was added to five existing methods: new Account(), Keypair.fromSecretKey(), Keypair.fromSeed(), and the Ed25519Program and Secp256k1Program createInstructionWithPrivateKey(). The name probably comes from third-party malware write-ups; not checked here. |
| 12 | The injected code captured key material | Anza | SUPPORTED | Apps calling those methods may have had their private key material sent out. |
| 13 | ...and sent it to an address the attacker controlled | Anza | DIFFERS | Anza: key material was sent to a server the attacker controlled. The Solana address FnvLGtucz4E1...AKbfx is where stolen assets were transferred, not where the key material went. |
| 14 | Version 1.95.8 removed it | GHSA, Anza | SUPPORTED | GHSA: patched version 1.95.8. Anza: a clean version without the malicious code was published as 1.95.8 at 8:25pm UTC. |
| 15 | Sources note: GHSA is "the maintainers' own advisory" | GHSA | SUPPORTED | Repository advisory in the library's own repo, published by maintainer steveluscher. |
| 16 | Sources note: GHSA covers the compromised publish account, the affected versions and what the injected code did | GHSA | SUPPORTED | It covers the publish-access compromise, versions 1.95.6/1.95.7, and the theft of private key material. |
| 17 | Sources note: Anza's post is a post-mortem | Anza | SUPPORTED | "Root Cause Analysis" by Anza Developers, 5 Dec 2024, with exploit, detection, mitigation and timeline sections. |
| 18 | Sources note: Anza covers the window the versions were live | Anza | SUPPORTED | Its timeline runs from the 3:20pm UTC phishing to removal from npm around 12:22am UTC on 4 Dec. |
| 19 | Sources note: Anza covers the exfiltration path | Anza | SUPPORTED | The five hooked methods, and key material sent to an attacker-controlled server. |

Proposed wording:
- #1: "`date: 2024-12-03`" - both cited sources put the compromise and both publishes on Tuesday 3 December 2024.
- #2: "On 3 December 2024 an account with publish rights to `@solana/web3.js` was compromised through a spear-phishing email, and two unauthorised versions, 1.95.6 and 1.95.7, were put on npm." - GHSA and Anza both give 3 December; Anza names the phishing.
- #10: "The versions went up at about 3:20pm UTC; a clean 1.95.8 was published at 8:25pm UTC, and npm removed 1.95.6 and 1.95.7 entirely at about 12:22am UTC on 4 December." - Anza's timeline. The five-hour figure is GHSA's exposure window, not the time until removal.
- #11: "Code added to five existing key-handling methods, including `Keypair.fromSecretKey()` and `Keypair.fromSeed()`, captured private key material..." - neither cited source names `addToQueue`. To keep the name, cite a source that gives it.
- #13: "...and sent it to a server the attacker controlled." - Anza says server. The on-chain address it gives received stolen assets, not key material.

---

## tj-actions-changed-files

**tj-actions/changed-files, CVE-2025-30066** - verdict in the entry: PARTIAL; `date:` 2025-03-14

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [GHSA-mrrh-fwg8-r2c3 / CVE-2025-30066](https://github.com/advisories/ghsa-mrrh-fwg8-r2c3) | primary: GHSA/CVE record (GitHub-reviewed; CVSS 3.1 8.6 High; CWE-506) | direct (WebFetch) OK; curl HTTP 200; API api.github.com/advisories/GHSA-mrrh-fwg8-r2c3 HTTP 200 | Published 15 Mar 2025 06:30 UTC, updated 22 Oct 2025. The description credits StepSecurity with detecting the attack. |
| [CISA alert](https://www.cisa.gov/news-events/alerts/2025/03/18/supply-chain-compromise-third-party-tj-actionschanged-files-cve-2025-30066-and-reviewdogaction) | primary: government advisory | direct (WebFetch) OK; curl HTTP 200 | The page text shows only "Last Revised March 26, 2025". The 18 March date appears only in the URL path. Sections are marked "Updated March 19" and "Updated March 26". It links GitHub, StepSecurity, Wiz and Semgrep as resources. |
| [Wiz blog](https://www.wiz.io/blog/github-action-tj-actions-changed-files-supply-chain-attack-cve-2025-30066) | secondary: security-vendor analysis (Merav Bar, Shay Berkovich, Gal Nagli; 15 Mar 2025, update 17 Mar) | direct (WebFetch) OK; curl HTTP 200 | REPEATS StepSecurity's original report (Wiz says the compromise was first reported by Step Security) and adds Wiz's own threat-hunting findings. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2025-03-14` is the day it happened | GHSA, CISA, Wiz | DIFFERS | GHSA agrees: the vulnerability existed 14-15 March 2025. Wiz says the Action was compromised some time before 14 March. CISA's audit window runs from 2025-03-12 00:00 UTC to 2025-03-15 12:00 UTC. |
| 2 | "Between 14 and 15 March 2025" the tags were retagged | GHSA, CISA, Wiz | DIFFERS | Same split: GHSA gives 14-15 March; Wiz says compromised before 14 March; CISA's audit starts 12 March. |
| 3 | The Action's version tags were retagged | GHSA, Wiz | SUPPORTED | GHSA: attackers retroactively modified multiple version tags. Wiz: existing version tags were modified. |
| 4 | Tags "v1 through v45.0.7" | GHSA, Wiz | SUPPORTED | GHSA: affected "through 45.0.7" (range <= 45.0.7), with v1.0.0 listed among the retagged tags. Wiz: all versions were affected. |
| 5 | Retagged to point at a single malicious commit | GHSA | SUPPORTED | Every listed tag points to the same commit, 0e58ed8671d6... |
| 6 | Quote: "allows remote attackers to discover secrets by reading actions logs" | GHSA | SUPPORTED | Exact words in the advisory's summary. |
| 7 | The injected step ran a Python script | GHSA | SUPPORTED | The modified Action executed a malicious Python script (memdump.py piped to sudo python3). |
| 8 | ...that read secrets out of the Runner Worker process's memory | GHSA | SUPPORTED | The script extracted secrets from the Runner Worker process memory. |
| 9 | ...and printed them into the workflow log | GHSA | SUPPORTED | Secrets were printed in the GitHub Actions logs. |
| 10 | The secrets were double-base64 encoded | CISA, Wiz, GHSA | SUPPORTED | CISA and Wiz: a double-encoded base64 payload. GHSA's decode command runs base64 -d twice. |
| 11 | The log was public on a public repository | GHSA, Wiz | SUPPORTED | Publicly accessible in repositories with public workflow logs; visible to everyone on public repos. |
| 12 | CISA issued an alert on 18 March 2025 | CISA | SUPPORTED | The date is in the alert's URL path (/alerts/2025/03/18/). The page text shows only Last Revised 26 March 2025. |
| 13 | The 18 March alert covered the related compromise of `reviewdog/action-setup@v1` | CISA | DIFFERS | The alert covers it now, but the reviewdog paragraph is marked "(Updated March 19, 2025)". CISA says that compromise potentially enabled the tj-actions one. |
| 14 | The reviewdog compromise is CVE-2025-30154 | CISA | SUPPORTED | reviewdog/action-setup@v1 is tracked as CVE-2025-30154. |
| 15 | The behaviour was removed in v46.0.1 | GHSA, CISA | SUPPORTED | Both: patched in v46.0.1. |
| 16 | The CVE is CVE-2025-30066 (title) | GHSA, CISA | SUPPORTED | GHSA-mrrh-fwg8-r2c3 carries CVE-2025-30066. |
| 17 | Sources note: GHSA gives the affected versions, the secrets disclosed through logs, and the fixed version | GHSA | SUPPORTED | <= 45.0.7; secrets readable from actions logs; first patched 46.0.1. |
| 18 | Sources note: "CISA's alert, 18 March 2025" | CISA | SUPPORTED | The URL path gives 2025/03/18; the page shows Last Revised 26 March 2025. |
| 19 | Sources note: Wiz covers "the retagging to commit `0e58ed8`" | Wiz | NOT IN SOURCE | The Wiz page (text and HTML) has no commit hash; it says only that tags were changed to point at malicious code. The hash 0e58ed8 is in the GHSA. |
| 20 | Sources note: Wiz covers the memory scrape | Wiz | SUPPORTED | The Action dumped the CI runner's memory, which held the workflow secrets. |
| 21 | Sources note: Wiz covers the base64 encoding | Wiz | SUPPORTED | Secrets were obfuscated as a double-encoded base64 payload. |
| 22 | Sources note: Wiz covers the scale | Wiz | SUPPORTED | Wiz found dozens of impacted public repositories. The "over 23,000 repositories" figure is GHSA's, not Wiz's. |

Proposed wording:
- #1: "`date: 2025-03-14`", with the body saying it is the start of the GitHub advisory's 14-15 March window - GHSA supports 14 March. CISA's audit window starts 12 March, and Wiz says only "before 14 March", so the body should state which source the date follows.
- #2: "The GitHub advisory dates the compromise to 14-15 March 2025. Wiz says it happened some time before 14 March, and CISA asks for an audit of runs from 12 March 00:00 UTC to 15 March 12:00 UTC. In that window the Action's tags, through v45.0.7, were retagged to point at a single malicious commit." - the three cited sources give different start points.
- #13: "CISA issued an alert on 18 March 2025. On 19 March it updated the alert to cover the compromise of `reviewdog/action-setup@v1` (CVE-2025-30154), which it says potentially enabled this one." - the reviewdog section is marked as a 19 March update.
- #19: "- [GHSA-mrrh-fwg8-r2c3 / CVE-2025-30066](...) - the GitHub advisory record: affected versions, the malicious commit `0e58ed8` the tags were moved to, the disclosure of secrets through action logs, and the fixed version." and "- [Wiz](...) - Wiz's analysis: the memory dump, the double-base64 encoding, and the dozens of affected public repositories it found." - the commit hash is in the GHSA, not in the Wiz post.

---

## ultralytics-pypi-cache-poisoning

**Ultralytics 8.3.41 and 8.3.42 on PyPI** - verdict in the entry: NOT COVERED; `date:` 2024-12-04

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [Supply-chain attack analysis: Ultralytics](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) | primary for the PyPI side: registry operator's statement (Seth Larson, PSF Security Developer-in-Residence, 11 Dec 2024). For the technical path it is secondary. | direct (WebFetch) OK; curl HTTP 200 | PARTLY REPEATS William Woodruff's (Trail of Bits) analysis at blog.yossarian.net/2024/12/06/zizmor-ultralytics-injection. The post links it for the "complete set of details" and for the cache finding, and does not itself describe the workflow path. |
| [Ultralytics AI Library Hacked via GitHub for Cryptomining](https://www.wiz.io/blog/ultralytics-ai-library-hacked-via-github-for-cryptomining) | secondary: security-vendor analysis (Wiz Threat Research, 9 Dec 2024) | direct (WebFetch) OK; curl HTTP 200 | REPEATS the primary reports it lists: Ultralytics issue #18027, the ComfyUI-Impact-Pack issue, kingbri's tweet, ReversingLabs and BleepingComputer. It never mentions a cache. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2024-12-04` is the day it happened | Wiz | SUPPORTED | Wiz: on 4 December 2024 the account openimbot opened the two malicious draft PRs. The PyPI post (11 Dec) says only "last week". |
| 2 | The versions were published to PyPI "On 4 December 2024" | Wiz, PyPI | NOT IN SOURCE | Neither source gives the publish date of 8.3.41 or 8.3.42. Wiz dates only the PRs to 4 December. |
| 3 | Two versions were published carrying the payload | PyPI, Wiz | DIFFERS | PyPI: four versions were affected and removed (8.3.41, 8.3.42, 8.3.45 and 8.3.46). Wiz names two and says a later "mitigation" release was also compromised. |
| 4 | Version 8.3.41 | PyPI, Wiz | SUPPORTED | Both list 8.3.41. |
| 5 | Version 8.3.42 | PyPI, Wiz | SUPPORTED | Both list 8.3.42. |
| 6 | The versions were published to PyPI | PyPI, Wiz | SUPPORTED | Both say the malicious versions were on PyPI and have been removed. |
| 7 | They carried an XMRig cryptocurrency miner | Wiz | SUPPORTED | Wiz: 8.3.41 and 8.3.42 run XMRig mining software. PyPI does not name the payload. |
| 8 | "PyPI's own analysis describes the path" | PyPI | DIFFERS | The PyPI post says the first releases came through the project's own GitHub Actions workflow and the attack targeted the Actions cache used during the build. It links Woodruff's analysis for the rest. |
| 9 | The workflow was a `pull_request_target` workflow | PyPI, Wiz | DIFFERS | PyPI mentions pull_request_target only in general hardening advice. Wiz names the vulnerable workflow "Publish Docs" and shows it triggered on `pull_request`. |
| 10 | It checked out and ran code from a fork's pull request | PyPI, Wiz | NOT IN SOURCE | Neither describes checking out fork code. Wiz says the crafted branch name piped file.sh into bash. |
| 11 | The fork's branch name was interpolated into a shell step | Wiz | SUPPORTED | The workflow used github.head_ref (the PR's source branch name) unsanitised, and the job executed it. |
| 12 | An attacker poisoned a GitHub Actions cache entry | PyPI | SUPPORTED | The attack targeted the GitHub Actions cache used during the build phase. |
| 13 | The branch-name injection is what let the attacker poison the cache | PyPI, Wiz | NOT IN SOURCE | Neither source links the two. Wiz never mentions a cache and guesses that file.sh checked in changes to model.py and downloads.py. |
| 14 | The project's own publishing workflow later restored that cache | PyPI | SUPPORTED | The first injected packages were published through the existing GitHub Actions workflow, whose build used the cache. |
| 15 | The workflow built a wheel from it | PyPI | NOT IN SOURCE | PyPI says code was injected during the build phase; it never mentions a wheel. |
| 16 | It uploaded the result with the project's stored token | PyPI | DIFFERS | PyPI: the first set was published through the workflow and "not by an API token" (Trusted Publishing). Only the second round used an unrevoked PyPI API token, with no matching repo activity or attestations. |
| 17 | 8.3.41 was up for about twelve hours | PyPI, Wiz | NOT IN SOURCE | Neither source gives how long 8.3.41 was available. |
| 18 | 8.3.42 was up for about one hour | PyPI, Wiz | NOT IN SOURCE | Neither source gives how long 8.3.42 was available. |
| 19 | Sources note: "the PyPI blog's analysis, 11 December 2024" | PyPI | SUPPORTED | Dated December 11, 2024; written by Seth Larson. |
| 20 | Sources note: the PyPI post covers the cache poisoning | PyPI | SUPPORTED | It says the attack targeted the GitHub Actions cache used during the build. |
| 21 | Sources note: the PyPI post covers the publishing path | PyPI | SUPPORTED | The first round went through the Trusted Publishing workflow, the second through a leftover API token. |
| 22 | Sources note: the PyPI post covers the timing | PyPI | NOT IN SOURCE | The only timing it gives is "last week"; no publish or removal times. |
| 23 | Sources note: Wiz analyses the injection and the payload | Wiz | SUPPORTED | Wiz covers the branch-name injection in "Publish Docs", the files modified, and XMRig. |

Proposed wording:
- #2: "On 4 December 2024 an attacker opened two pull requests against the `ultralytics` repository, and versions 8.3.41 and 8.3.42, published to PyPI afterwards, carried an XMRig cryptocurrency miner." - Wiz dates the PRs, not the publishes.
- #3: "Four versions of `ultralytics` were affected and have since been removed from PyPI: 8.3.41, 8.3.42, 8.3.45 and 8.3.46. Wiz reports that 8.3.41 and 8.3.42 carried an XMRig miner." - the PyPI post lists four versions. The title and body name only two.
- #8, #9, #10, #13: "Wiz traces the injection to a crafted branch name that the project's 'Publish Docs' workflow, run on pull requests, passed unsanitised into a shell command. PyPI's analysis says the attack then targeted the GitHub Actions cache used during the build, and points to William Woodruff's analysis for the full path." - neither cited source describes the pull_request_target -> fork checkout -> cache poisoning chain. That chain appears to come from Woodruff's post (blog.yossarian.net/2024/12/06/zizmor-ultralytics-injection), which would need to be cited to keep it.
- #15: "...the project's own publishing workflow, whose build used the poisoned cache, published the first malicious releases." - PyPI talks about the build phase and packages, not wheels.
- #16: "The first malicious releases were published by the project's own workflow through Trusted Publishing, not with a token. A second round was uploaded with an unrevoked PyPI API token that was still available to the workflow." - the PyPI post explicitly separates the two rounds.
- #17, #18: remove "8.3.41 was up for about twelve hours and 8.3.42 for about one", or cite a source that gives the timings - neither cited source does.
- #22: "- the PyPI blog's analysis, 11 December 2024: the cache poisoning and the two publishing paths." - the post gives no timing.

---

## xz-utils-backdoor

**The xz-utils backdoor, CVE-2024-3094** - verdict in the entry: NOT COVERED; `date:` 2024-03-29

Sources:

| Source | Kind | Reached | Note |
|---|---|---|---|
| [backdoor in upstream xz/liblzma leading to ssh server compromise](https://www.openwall.com/lists/oss-security/2024/03/29/4) | primary: the researcher's own write-up (Andres Freund, oss-security, Fri 29 Mar 2024 08:51:26 -0700) | direct (WebFetch) OK; curl HTTP 200 | |
| [CVE-2024-3094](https://nvd.nist.gov/vuln/detail/CVE-2024-3094) | primary: NVD entry for the CVE record (CNA: Red Hat) | direct (WebFetch): the page is rendered by JavaScript and returned only "NVD - Home"; curl HTTP 200 (redirected to the lowercase URL) was the same empty shell; API services.nvd.nist.gov/rest/json/cves/2.0?cveId=CVE-2024-3094 HTTP 200 | Content checked via the API. Published 2024-03-29 17:15 UTC. CVSS 3.1 10.0 Critical from both Red Hat and NVD. CWE-506. |

| # | Claim (as the entry states it, shortened) | Source | Verdict | What the source says (paraphrased) |
|---|---|---|---|---|
| 1 | `date: 2024-03-29` is the disclosure day, since no source gives the day it happened | Openwall, NVD | SUPPORTED | The post is dated Fri 29 Mar 2024 and NVD published the CVE on 29 Mar 2024. Neither dates the backdoor's insertion or the 5.6.0/5.6.1 releases; the post says the symptoms were seen "over the last weeks". |
| 2 | The post was made on 29 March 2024 | Openwall | SUPPORTED | Date header: Fri, 29 Mar 2024 08:51:26 -0700. |
| 3 | Andres Freund posted to the oss-security list | Openwall | SUPPORTED | From: Andres Freund; To: the oss-security list at openwall. |
| 4 | Quote: "After observing a few odd symptoms ... have been backdoored." | Openwall | SUPPORTED | The words are identical. The source has a paragraph break after "the answer:" that the entry runs together. |
| 5 | Versions 5.6.0 and 5.6.1 carried it | Openwall, NVD | SUPPORTED | Freund: present in the 5.6.0 and 5.6.1 tarballs. NVD: in upstream tarballs "starting with version 5.6.0". |
| 6 | It activated during a Debian or RPM package build | Openwall | SUPPORTED | One condition is running as part of a Debian or RPM package build. |
| 7 | ...on x86-64 Linux | Openwall | SUPPORTED | The conditions include targeting only x86-64 Linux. |
| 8 | ...with gcc and the GNU linker | Openwall | SUPPORTED | Another condition is building with gcc and the GNU linker. |
| 9 | It interfered with sshd along liblzma's dependency chain | Openwall | SUPPORTED | The "Impact on sshd" section, reached through libsystemd's dependency on lzma. |
| 10 | "openssh links libsystemd, which links liblzma" | Openwall | DIFFERS | Freund: openssh does not use liblzma directly. Debian and several other distributions patch openssh for systemd notification, and libsystemd depends on lzma. The link is distro-patched, not upstream openssh. |
| 11 | It intercepted "RSA functions" | Openwall | DIFFERS | The post names one redirected function, RSA_public_decrypt (its PLT entry was pointed at backdoor code). RSA_get0_key appears only as the backdoor calling back into libcrypto. |
| 12 | ...so that public-key authentication could be subverted | Openwall, NVD | SUPPORTED | The redirected function runs during a pubkey login. Freund says, hedged and unconfirmed, that the code seems likely to allow some form of access or remote code execution. NVD: it intercepts and modifies data interaction with the library. |
| 13 | The CVE is CVE-2024-3094 (title and source link) | Openwall, NVD | SUPPORTED | Freund: Red Hat assigned CVE-2024-3094. NVD record id matches. |
| 14 | Sources note: Freund's original oss-security post, 29 March 2024 | Openwall | SUPPORTED | Author, list and date all match. |
| 15 | Sources note: the post "is the disclosure" | Openwall | DIFFERS | It is the public disclosure. The post says Freund first sent a preliminary report to Debian security and then to distros@, CISA had been notified by a distribution, and Red Hat had already assigned the CVE. |
| 16 | Sources note: the NVD link is "the CVE record" | NVD | SUPPORTED | NVD's entry for CVE-2024-3094, carrying the CNA (Red Hat) description, published 29 Mar 2024. It is NVD's copy of the record rather than cve.org itself. |

Proposed wording:
- #10: "...interfered with sshd along liblzma's dependency chain. openssh does not use liblzma itself, but Debian and several other distributions patch it to link libsystemd, which depends on liblzma..." - Freund says the libsystemd link comes from distribution patches.
- #11: "...redirecting sshd's `RSA_public_decrypt` to its own code, so that public-key authentication could be subverted." - the post names one intercepted RSA function.
- #15: "- Andres Freund's oss-security post, 29 March 2024, which is the public disclosure." - the post itself records earlier private reports to Debian security and distros@.
