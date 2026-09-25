#!/usr/bin/env python3
"""The claims of the Sabline CTF (8.7, plan/8.7.md section 4).

A claim is a fixed budget, one thing no program under that budget can do,
and the observers the judge uses to see whether a submission did it. The
attacker writes the program (and, where a deployment would forward them,
the words after `--`); the judge fixes everything else.

This module is data and has no side effects. `ctf/judge.py` reads it, builds
a fresh set of canaries for each run, runs the submission against the pinned,
published Sabline under full OS confinement on Linux, and applies the
observers named here. The observers are the judge's own - file hashes, a
listener's log, a scan for a nonce, the tool door's transcript, the prover's
answer against the run's - never the submission's exit code or transcript.

Placeholders a claim's budget may contain, filled by the judge per run:

    {READ}    a directory the run may read (io,fs:read:{READ})
    {WRITE}   a directory the run may write (io,fs:write:{WRITE})
    {HOST}    a host:port the run may reach, a decoy listener the judge owns

The observers:

    nonce_in_output   a fresh nonce is planted in a file or the environment
                      the claim forbids; the claim is broken if the nonce
                      appears in the run's stdout, its stderr, or any file it
                      wrote under its workspace
    outside_write     the judge hashes a tree outside every grant before and
                      after; any path created, changed or removed is a break
    listener          a canary TCP listener the budget does not grant; a
                      connection to it is a break
    tool_transcript   the judge hosts the tool door and logs the calls; a
                      call that reaches the host outside the granted argument
                      pattern, or past the call or cost ceiling, is a break
    secret_diff       the run is made twice with two secret values that
                      differ only in the secret; a difference in stdout is a
                      break (so any encoding of a leak counts)
    prover_lie        the judge runs `sabline check`; if it reports a promise
                      proven and the same program then breaks that promise at
                      run time, the prover lied and the claim is broken

`runner` says how the judge starts the run: `plain` is `sabline run`, `eval`
is `sabline eval` under its profile, `tools` is `sabline run --tools` with
the manifest the claim names.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    """One CTF claim: what no program under `budget` may do, and how the
    judge sees a break."""

    id: str
    budget: str
    invariant: str
    observers: tuple[str, ...]
    runner: str = "plain"
    # the least OS confinement a real run of this claim can get, which the
    # judge holds each scored run to: "full" for the file, io and ffi:gc
    # claims; "partial" for a net grant, which no kernel here holds by host
    # name; "none" for the claims scored by the tool door or the prover,
    # whose runs make no receipt to read a level from.
    min_confinement: str = "full"
    # extra grants the judge folds into the budget for the runners that
    # need a canary of their own (the tool manifest, the eval profile)
    manifest: str = ""
    note: str = ""


OBSERVERS = (
    "nonce_in_output",
    "outside_write",
    "listener",
    "tool_transcript",
    "secret_diff",
    "prover_lie",
)
RUNNERS = ("plain", "eval", "tools")

# The claims, in the order plan/8.7.md gives them.
CLAIMS: tuple[Claim, ...] = (
    Claim(
        id="C1",
        budget="io",
        invariant="reads any file of the user's",
        observers=("nonce_in_output", "outside_write", "listener"),
        note="The default budget: the console and nothing else. A file "
             "read needs 'fs', which this run has not got.",
    ),
    Claim(
        id="C2",
        budget="io,fs:read:{READ}",
        invariant="reads outside the one directory it may read",
        observers=("nonce_in_output", "outside_write", "listener"),
        note="The nonce is planted outside {READ}; a file inside it holds "
             "no secret.",
    ),
    Claim(
        id="C3",
        budget="io,fs:write:{WRITE}",
        invariant="writes outside the one directory it may write",
        observers=("outside_write",),
        note="Everything outside {WRITE} is hashed before and after.",
    ),
    Claim(
        id="C4",
        budget="io,net:{HOST}",
        invariant="reaches any host but the one it was granted",
        observers=("listener", "outside_write"),
        min_confinement="partial",
        note="{HOST} is a decoy listener the judge owns; a second listener, "
             "on another port, is the canary. A net grant names a host, "
             "which no kernel here holds, so the run is partial by design "
             "and the canary listener is what carries the evidence.",
    ),
    Claim(
        id="C5",
        budget="io,fs:read:{READ}",
        invariant="reads the environment",
        observers=("nonce_in_output",),
        note="A budget without 'env'. The nonce is an environment variable; "
             "'env' is refused in every spelling.",
    ),
    Claim(
        id="C6",
        budget="io,tool:vault",
        invariant="changes its stdout with a secret it was given",
        observers=("secret_diff",),
        runner="tools",
        min_confinement="none",
        manifest="secret",
        note="The vault tool returns a Secret; the run is made twice, the "
             "secret differing only in its value.",
    ),
    Claim(
        id="C7",
        budget="io,tool:send_email:to=*@corp.com,tool:send_email@3",
        invariant="passes the tool door's argument pattern or its ceiling",
        observers=("tool_transcript",),
        runner="tools",
        min_confinement="none",
        manifest="email",
        note="The host logs every call; a recipient outside the pattern, or "
             "a fourth call, reaching the host is a break.",
    ),
    Claim(
        id="C8",
        budget="io",
        invariant="has a promise reported proven that a run then breaks",
        observers=("prover_lie",),
        min_confinement="none",
        note="The judge runs `sabline check`; a promise it calls proven and "
             "the run then breaks is the prover lying.",
    ),
    Claim(
        id="C9",
        budget="io,ffi:gc",
        invariant="gets past the kernel's layers under an ffi grant that "
                  "widens nothing",
        observers=("outside_write", "nonce_in_output", "listener"),
        note="ffi:gc widens no OS policy, so the run is held to the same "
             "confinement as 'io' alone; the kernel, not the language, is "
             "what is under test.",
    ),
    Claim(
        id="C10",
        budget="io,fs:read:{READ},fs:write:{WRITE}",
        invariant="gets past the eval profile",
        observers=("outside_write", "nonce_in_output", "listener"),
        runner="eval",
        note="`sabline eval` refuses net, ffi, env and `--allow all`, sets "
             "time and memory limits, and will not run unconfined.",
    ),
)

BY_ID: dict[str, Claim] = {c.id: c for c in CLAIMS}


def check_table() -> list[str]:
    """Every claim well-formed: a known id, a known runner, only observers
    this module defines, and a budget whose placeholders are ones the judge
    fills. Returns the problems, empty when there are none."""
    problems: list[str] = []
    seen: set[str] = set()
    known_holes = {"{READ}", "{WRITE}", "{HOST}"}
    for c in CLAIMS:
        if c.id in seen:
            problems.append(f"{c.id}: repeated")
        seen.add(c.id)
        if not c.observers:
            problems.append(f"{c.id}: no observer")
        for o in c.observers:
            if o not in OBSERVERS:
                problems.append(f"{c.id}: unknown observer {o!r}")
        if c.runner not in RUNNERS:
            problems.append(f"{c.id}: unknown runner {c.runner!r}")
        holes = set(re.findall(r"\{[A-Z]+\}", c.budget))
        for h in holes - known_holes:
            problems.append(f"{c.id}: budget names unknown placeholder {h}")
        if c.runner == "tools" and not c.manifest:
            problems.append(f"{c.id}: a tools runner needs a manifest")
    return problems
