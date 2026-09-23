---
slug: ultralytics-pypi-cache-poisoning
title: Ultralytics 8.3.41 and 8.3.42 on PyPI
date: 2024-12-04
lane: supply-chain
verdict: NOT COVERED
budget_line: none
verified: false
---

## What happened

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

## Sources

- [Supply-chain attack analysis: Ultralytics](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) - the PyPI blog's analysis, 11 December 2024: the cache poisoning and the two publishing paths. It defers the technical path to William Woodruff's analysis, which it links.
- [Ultralytics AI Library Hacked via GitHub for Cryptomining](https://www.wiz.io/blog/ultralytics-ai-library-hacked-via-github-for-cryptomining) - Wiz's analysis: the branch-name injection in the "Publish Docs" workflow, and the XMRig payload.

## The shape, in Sabline

The payload did not arrive through a compromised credential or a malicious
dependency. It arrived through the build: a cache entry the build trusted,
restored by a workflow that was working exactly as written.
Sabline has no build system, produces no wheels, and has nothing that
inspects a pipeline. A budget starts existing when a program starts running,
and by then the artefact is whatever the build made it.

The nearest thing in this repository is not a Sabline feature at all:
`sabline capabilities check` and `sabline review` watch what a Sabline
project's *source* may reach, commit by commit, and the Action's
`permissions:` are held by `check_permissions.py`. Neither would have seen a
poisoned cache.

## What this does not cover

The whole shape. Nothing in Sabline observes a build, a cache, a workflow
trigger or an artefact's provenance at the point it is made.
