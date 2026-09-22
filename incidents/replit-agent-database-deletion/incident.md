---
slug: replit-agent-database-deletion
title: An agent that deleted a production database
date: 2025-07-18
lane: agent
verdict: PARTIAL
budget_line: ffi:json
verified: false
---

## What happened

In July 2025, during a multi-day experiment with Replit's coding agent, the
agent issued destructive commands against a live production database while a
code freeze was in force, deleting records the user has described as
covering roughly 1,200 executives and companies. The user, Jason Lemkin,
said publicly that the agent "deleted our production database without
permission" and then "hid and lied about it", including fabricating data and
claiming a rollback was impossible. Replit's chief executive, Amjad Masad,
responded publicly that the deletion was "unacceptable and should never be
possible", and the company subsequently separated development and production
databases and added a planning-only mode.

> **Sourcing, stated plainly.** There is no vendor post-mortem for this one.
> The record is the participants' own posts on X and the reporting that
> quoted them, collected by the AI Incident Database. It is the weakest
> sourcing of any entry here, and it is listed so that a reader checking
> these summaries knows that before they start.

## Sources

- [AI Incident Database, incident 1152](https://incidentdatabase.ai/cite/1152/) - the curated record, dated 18 July 2025, with its cited reports.
- [Vibe coding service Replit deleted user's production database, faked data, told fibs galore](https://www.theregister.com/2025/07/21/replit_saastr_vibe_coding_incident/) - The Register's account, quoting both participants.

## The shape, in Sabline

An agent with a credential did something destructive with it. There are two
halves, and Sabline answers the first and not the second - which is why
this entry exists.

The first half: getting to the database at all. `drop_table.vel` uses the
standard library's `db` module, which reaches sqlite through Python. Under
the budget a program gets when nobody sets one, that is refused (E310):
`py_new` needs `ffi`, and this run has `io`. Under a budget that grants
Python but names a different module - `ffi:json` - it is refused again, and
this time the refusal names what it wanted (E311).

The second half: once the grant is right, the drop goes through. The last
step in this entry is `dropped`, exit 0, and a receipt that records `ffi`
used and no refusals. That is not a bug in the recording; it is what this
catalogue is for.

## The one line that does the work

    --allow io,ffi:json,fs:read:./data,fs:write:./data

`ffi:json` is the line - a Python grant that names one module and so
refuses every other. Widening it to `ffi:sqlite3,ffi:_sqlite3` is the whole
difference between the second step and the third, and that is the point:
the `ffi:` list works entirely at the boundary. It decides whether the
program may talk to a database, and says nothing about what it says once it
can.

## What this does not cover

Nothing in a Sabline budget distinguishes a read from a write or a drop
inside an effect it has granted: `fs:write:./data` is any write to that
directory, `ffi:sqlite3` is any statement that module will run, and a
`net:` host grant is any request to that host. THREAT_MODEL.md says this of
`net` already - a count bounds how many operations a run makes, not "whether
a request is a GET or a POST" - and the same is true of files and of
granted Python.
