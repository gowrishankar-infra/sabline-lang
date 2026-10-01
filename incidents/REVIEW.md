# The review that set the flags

On **2026-10-01** every entry in this catalogue was read against the sources
it was written from, and `verified:` was set to `true` on all fifteen. This
file records who decided what, so that "a person checked this" is a claim
with a date and a list behind it rather than a flag in a file.

Until this review, every entry said `verified: false`:
`build_incidents.py` counted each one, named it, linked its sources and
withheld the summary, and neither the per-incident pages nor the flagship
existed. Setting the flags is what publishes them.

## What was read

A reading pack built from this repository: each entry's "What happened" as
it would be published, its replay as recorded in `refusal.txt`, its Sources
list, and every row of [FACTCHECK.md](FACTCHECK.md) that the fact-check of
2026-09-23 did not mark `SUPPORTED` - 53 flagged rows across 14 entries,
plus the 7 source-provenance notes. The pack re-fetched nothing; the four
sources added by the changes below were fetched during the review and
checked against the sentences they now support.

The sixteenth entry in FACTCHECK.md, `replit-agent-database-deletion`, was
dropped from the catalogue before this review for want of a primary source
and has no entry directory. It was not reviewed, and its rows stay in
FACTCHECK.md as a record of why it is not here.

## The decisions

Eleven entries were approved as written. Four were approved subject to a
change, and the change was made before the flag was set.

| # | Entry | Verdict | Decision |
|---|---|---|---|
| 1 | solana-web3js-backdoor | STOPPED | approved as written |
| 2 | mcp-remote-command-injection | STOPPED | approved as written |
| 3 | package-hallucination | PARTIAL | approved as written |
| 4 | tj-actions-changed-files | PARTIAL | **changed**: source added |
| 5 | mcp-tool-poisoning | PARTIAL | approved as written |
| 6 | nx-s1ngularity | PARTIAL | approved as written |
| 7 | shai-hulud-npm-worm | PARTIAL | approved as written |
| 8 | postmark-mcp-bcc-exfiltration | PARTIAL | approved as written |
| 9 | circleci-oauth-token-theft | NOT COVERED | approved as written |
| 10 | xz-utils-backdoor | NOT COVERED | approved as written |
| 11 | ultralytics-pypi-cache-poisoning | NOT COVERED | **changed**: source added |
| 12 | github-mcp-toxic-agent-flow | NOT COVERED | approved as written |
| 13 | amazon-q-extension-wiper | NOT COVERED | **changed**: wrong command named |
| 14 | echoleak-m365-copilot | OUT OF SCOPE | **changed**: source replaced, summary reworded |
| 15 | camoleak-copilot-chat | OUT OF SCOPE | approved as written |

## The four changes

**4. tj-actions-changed-files - StepSecurity's report added to Sources.**
FACTCHECK.md's provenance note said the Wiz post repeats StepSecurity's
report and that the report itself was not cited. It is now cited directly.
The source was fetched and says what the entry's description of it says:
Harden-Runner's anomaly detection found the compromise on 14 March 2025
when an unexpected endpoint appeared in a run's network traffic, every
release tag was moved to one malicious commit, and the injected script
dumps the Runner Worker process's secrets into the workflow log. The
description claims no more than that: the page records the detection but
does not itself claim sole discovery.

**11. ultralytics-pypi-cache-poisoning - William Woodruff's analysis added
to Sources.** The summary already named it, by way of PyPI's post deferring
to it, without citing it; FACTCHECK.md's provenance note said so. The post
was fetched and carries what the entry rests on it for: the
`pull_request_target` trigger in `format.yml`, the branch name interpolated
unquoted into `git pull origin ${{ github.head_ref || github.ref }}`, and
the cache poisoning that followed.

**13. amazon-q-extension-wiper - `aws s3 rb` corrected to `aws s3 rm`.**
The summary lists the payload's commands correctly (`ec2
terminate-instances`, `s3 rm`, `iam delete-user`), but "The shape, in
Sabline" then named `aws s3 rb`, which is not one of them - `rb` removes a
bucket, `rm` removes objects, and `rm` is what the payload used. This entry
has no replay program and no recorded evidence, so there was nothing to
re-record.

**14. echoleak-m365-copilot - the unreachable source replaced, and the
summary reworded to what the new one supports.** Aim Labs' write-up was the
entry's primary source and has answered HTTP 403 since August 2025; twelve
of the fact-check's rows rested on it alone. In its place the entry cites
Pavan Reddy and Aditya Sanjay Gujral, "EchoLeak: The First Real-World
Zero-Click Prompt Injection Exploit in a Production LLM System",
arXiv:2509.10540, published at the AAAI Fall Symposium Series 2025. MSRC
stays. Aim Labs stays too, but only as an archived copy read through the
Wayback Machine, and the entry says that is what it is. The promise that
every sentence resting on Aim Labs alone is marked as such was removed:
the account no longer rests on it.

The summary's second sentence was rewritten to say only what the paper
supports - an email worded to read as a normal request to the recipient and
so past Microsoft's XPIA classifier, needing no action from the victim,
pulled in by Copilot's ordinary retrieval when the user later asked Copilot
a question, its hidden instructions putting sensitive data from the user's
context into an image link that is fetched automatically through a
Microsoft Teams URL the content security policy allows, sending the data to
the attacker's server. Three things the old sentence said are gone, because
the paper does not support them: that the email was **never opened by the
victim** (the paper claims no user interaction, which is not the same
claim), that the later question was **unrelated** (its own examples,
"Summarize my recent emails", are not), and the list **chat history,
OneDrive, SharePoint, Teams** (the paper itemises no categories).
