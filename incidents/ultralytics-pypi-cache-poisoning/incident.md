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

On 4 December 2024 two versions of the `ultralytics` Python package,
8.3.41 and 8.3.42, were published to PyPI carrying an XMRig cryptocurrency
miner. PyPI's own analysis describes the path: a `pull_request_target`
workflow in the project's GitHub Actions setup checked out and ran code from
a fork's pull request with the fork's branch name interpolated into a shell
step, which let an attacker poison a GitHub Actions cache entry; the
project's own publishing workflow later restored that cache, built a wheel
from it, and uploaded the result with the project's stored token. 8.3.41 was
up for about twelve hours and 8.3.42 for about one.

## Sources

- [Supply-chain attack analysis: Ultralytics](https://blog.pypi.org/posts/2024-12-11-ultralytics-attack-analysis/) - the PyPI blog's analysis, 11 December 2024: the cache poisoning, the publishing path, and the timing.
- [Ultralytics AI Library Hacked via GitHub for Cryptomining](https://www.wiz.io/blog/ultralytics-ai-library-hacked-via-github-for-cryptomining) - Wiz's analysis of the injection and the payload.

## The shape, in Sabline

The payload did not arrive through a compromised credential or a malicious
dependency. It arrived through the build: a cache entry the build trusted,
restored into a wheel by a workflow that was working exactly as written.
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
