# The CircleCI breach, replayed in Sabline

<!-- description: NOT COVERED: CircleCI's incident report records that "an unauthorized third party leveraged malware deployed to a CircleCI engineer's laptop in order to steal ... -->

**The CircleCI January 2023 incident**, 2022-12-22. Also called the CircleCI incident, rotate your CircleCI secrets. ([The name in use](https://news.ycombinator.com/item?id=34390449).) Verdict: **`NOT COVERED`** - nothing in Sabline addresses this shape.

> [!NOTE]
> **This is the shape of the attack, not a claim that Sabline would have prevented the real event.** The real one happened in a language, a package manager, a build system or an agent framework that Sabline neither runs nor bounds. What this page shows is narrower and checkable: the same shape written in Sabline, the command, what the runtime printed, and the one line of budget that did the work - or, where nothing here addresses the shape, that.

## What happened

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

## The shape, in Sabline

Secrets that a build system held on its customers' behalf were taken out of
the build system. No program of the customers' ran with too much authority;
the authority that was misused was the platform's own, and the theft
happened on an employee's machine and in production infrastructure.

It is in this catalogue because it is the canonical case of the thing a
budget is supposed to be about - credentials in a build - and it is worth
being exact about why a budget is not the answer to it. Sabline's rules
concern what a program may reach while it runs. A secret sitting in a CI
provider's store, read by that provider's own code, is not inside any
program's budget; what the operator can do about it is rotation, scope and
storage, none of which is a language feature.

## What this does not cover

The whole shape: the trust boundary here is the platform's, and
THREAT_MODEL.md's own boundary starts at "the user running sabline", who is
trusted - "anything running as that user is that user".

## Sources

- [CircleCI Jan 4, 2023 security incident report](https://circleci.com/blog/jan-4-2023-incident-report/) - CircleCI's own post-mortem: the malware, the stolen session, what was exfiltrated, and the rotation timeline.
- [CircleCI security alert: Rotate any secrets stored in CircleCI](https://circleci.com/blog/january-4-2023-security-alert/) - the customer-facing alert of 4 January 2023.

The entry, its program and its recorded run are in [incidents/circleci-oauth-token-theft/](https://github.com/gowrishankar-infra/sabline-lang/blob/main/incidents/circleci-oauth-token-theft/). Every incident, with its verdict, is in [the catalogue](incidents.md).
