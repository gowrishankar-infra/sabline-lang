---
slug: a-short-kebab-case-name
title: What the incident is called, in a few words
date: 2025-01-01
lane: supply-chain | agent
verdict: STOPPED | PARTIAL | NOT COVERED | UNVERIFIED | OUT OF SCOPE
budget_line: the one grant that does the work, or none
verified: false
---

<!--
`date` is the day the incident happened where a source gives one, and the
day it was disclosed where none does; the body says which. It is only used
to order the page. `slug` must be the directory's name. `verified` stays
`false` until a person has read the sources below and checked every
sentence of "What happened" against them.
-->


## What happened

Two to four sentences. Facts only, each one traceable to a source below.
Dates, versions and counts as the source gives them. No adjectives that the
source does not support, and no sentence about Sabline.

## Sources

- [Title of the primary report](https://example.com/) - vendor post-mortem,
  CVE record, or the researcher's own write-up. Say which it is.
- [A second source](https://example.com/) - optional, for a detail the
  primary report does not carry.

## The shape, in Sabline

What the attack did, reduced to the thing a budget can see: reads a
credential and sends it out; takes a string from a server and hands it to
the shell; calls a tool with an argument outside the grant. Then the
program, the command, and what it printed - all of it recorded by
`incident_evidence.py`, not written by hand.

For `NOT COVERED`, `UNVERIFIED` and `OUT OF SCOPE`, this section says what
the shape is and stops there.

## The one line that does the work

Name the single grant, or the single rule, the refusal turns on:

    --allow io,fs:read:./data

and one sentence on why that line and not another.

## What this does not cover

For `PARTIAL`, `NOT COVERED` and `UNVERIFIED`: one plain sentence, no
hedging, on the part of this incident Sabline does not address. The same
sentence goes into the known-open table, docs/known-open.md, so the gap is in the
threat model and not only here.

For `STOPPED`, say instead what the budget must be for the refusal to hold,
since a wide enough budget refuses nothing.
