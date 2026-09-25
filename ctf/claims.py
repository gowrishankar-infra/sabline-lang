#!/usr/bin/env python3
"""The claims of the Sabline CTF (8.7, plan/8.7.md section 4).

A claim is a fixed budget, one thing no program under that budget can do,
and the observers the judge uses to see whether a submission did it. The
attacker writes the program (and, where a deployment would forward them,
the words after `--`); the judge fixes everything else.

This module is data and has no side effects. `ctf/judge.py` reads it, builds
a fresh set of canaries for each run, runs the submission against the pinned,
published Sabline on Linux, and applies the observers named here. The
observers are the judge's own - file hashes, a listener's log, a scan for a
nonce, the tool door's transcript, the prover's answer against the run's -
never the submission's exit code or transcript.

**Confinement is per claim, not one level for all of them.** `min_confinement`
below is the least the judge holds a scored run of that claim to, and a run
that did not reach it is not scored. It is `full` for the file, io and ffi
claims; `partial` for C4, whose net grant names a host no kernel here holds
by name, and for C8, whose program carries a promise and so starts the
prover's threads before the confinement is applied; `none` for C6 and C7,
scored by the tool door, whose runs write no receipt to read a level from.
Nothing here is "every run is fully confined", and no page about this CTF
should say so.

Placeholders a claim's budget may contain, filled by the judge per run:

    {READ}    a directory the run may read (io,fs:read:{READ})
    {WRITE}   a directory the run may write (io,fs:write:{WRITE})
    {HOST}    a host:port the run may reach, a decoy listener the judge owns

The observers:

    nonce_in_output   a fresh nonce is planted in a file or the environment
                      the claim forbids; the claim is broken if the nonce
                      appears in the run's stdout, its stderr, or any file it
                      wrote under its workspace
    canary_diff       the run is made twice, at the same paths, with the same
                      seed, clock, arguments and receipt path, and only the
                      planted nonces differing; a difference in stdout, in
                      stderr, or in the files the run wrote, is information
                      flowing from the nonce and a break - so an encoded leak
                      (reversed, hex, anything) counts, and one written with
                      `log`, which goes to stderr, counts as much as one
                      printed. Stderr is compared as normalise_stderr leaves
                      it: two notes of the runtime's that carry no free text
                      are dropped, and the seconds in the prover's
                      abandoned-proof note become a placeholder, so the
                      timing cannot masquerade as a leak and the rest of
                      that line, the function's name included, is still
                      compared. A run that does not finish is not scored.
    outside_write     the judge hashes every tree the run can reach - the
                      whole of the run's root, its own working directory
                      included - but the one directory the budget lets it
                      write, before and after; any path created, changed or
                      removed is a break. Hashing only a tree further out
                      would miss a write that escaped no further than the
                      run's own directory, which is outside the grant just
                      the same
    listener          a second loopback listener the judge owns, on a port
                      the budget does not name; a connection arriving at it
                      is a break. It is the only egress observed: a
                      connection to another host, or to a port with no
                      listener, is not seen by this version
    tool_transcript   the judge hosts the tool door and logs the calls; a
                      call that reaches the host outside the granted argument
                      pattern, past the grant's call ceiling, or past the
                      manifest's cost ceiling, is a break. Both ceilings are
                      checked, and the manifest's numbers are set so that
                      each of them can bind: at 15 credits a call against a
                      ceiling of 40, the cost bites at the third call and the
                      grant's count of three at the fourth
    secret_diff       the run is made twice with two secret values that
                      differ only in the secret; a difference in what the
                      program wrote, on either stream, is a break (so any
                      encoding of a leak counts, `log` to stderr included)
    prover_lie        the judge reads the prover's answer from `sabline audit
                      --json`, runs the program with a receipt, and reads the
                      run's exit from that receipt - never from what the
                      program printed. A promise the prover called proven,
                      in a program whose every promise it called proven, and
                      an ensures the receipt says broke (E601), is the prover
                      lying and the claim broken

`runner` says how the judge starts the run: `plain` is `sabline run`, `eval`
is `sabline eval` under its profile, `tools` is `sabline run --tools` with
the manifest the claim names, `prover` is `sabline audit --json` and then
`sabline run` with a receipt.
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
    # name, and for the prover claim, whose program carries a promise and so
    # starts the prover's threads before the confinement is applied; "none"
    # for the claims scored by the tool door, whose runs make no receipt to
    # read a level from.
    min_confinement: str = "full"
    # extra grants the judge folds into the budget for the runners that
    # need a canary of their own (the tool manifest, the eval profile)
    manifest: str = ""
    note: str = ""


OBSERVERS = (
    "nonce_in_output",
    "canary_diff",
    "outside_write",
    "listener",
    "tool_transcript",
    "secret_diff",
    "prover_lie",
)
RUNNERS = ("plain", "eval", "tools", "prover")

# The claims, in the order plan/8.7.md gives them.
CLAIMS: tuple[Claim, ...] = (
    Claim(
        id="C1",
        budget="io",
        invariant="reads any file of the user's",
        observers=("nonce_in_output", "canary_diff", "outside_write",
                   "listener"),
        note="The default budget: the console and nothing else. A file "
             "read needs 'fs', which this run has not got. The nonce is a "
             "file in the run's own directory; the run is made twice, with "
             "only the nonce differing.",
    ),
    Claim(
        id="C2",
        budget="io,fs:read:{READ}",
        invariant="reads outside the one directory it may read",
        observers=("nonce_in_output", "canary_diff", "outside_write",
                   "listener"),
        note="Nonces are planted outside {READ}: one in the run's own "
             "working directory, one in a tree outside every grant. A file "
             "inside {READ} holds no secret. The run is made twice, with "
             "only the nonces differing.",
    ),
    Claim(
        id="C3",
        budget="io,fs:write:{WRITE}",
        invariant="writes outside the one directory it may write",
        observers=("outside_write",),
        note="Every tree the run can reach but {WRITE} is hashed before and "
             "after - the run's own working directory included, since a "
             "write that lands there is outside the grant as surely as one "
             "that lands further away.",
    ),
    Claim(
        id="C4",
        budget="io,net:{HOST}",
        invariant="connects to a second loopback listener the judge owns, "
                  "on a port the budget does not name",
        observers=("listener", "outside_write"),
        min_confinement="partial",
        note="{HOST} is a decoy listener the judge owns; a second listener, "
             "on another loopback port, is the canary, and a connection "
             "arriving at it is the only egress this version observes. A "
             "connection to another host, or to a port with no listener, "
             "is not seen, so the claim is that narrow; observing egress "
             "more broadly (a network namespace or a packet capture round "
             "the run) is future work. A net grant names a host, which no "
             "kernel here holds, so the run is partial by design and the "
             "canary listener is what carries the evidence.",
    ),
    Claim(
        id="C5",
        budget="io,fs:read:{READ}",
        invariant="reads the environment",
        observers=("nonce_in_output", "canary_diff"),
        note="A budget without 'env'. The nonce is an environment variable; "
             "'env' is refused in every spelling. The run is made twice, "
             "with only the nonce differing.",
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
        invariant="passes the tool door's argument pattern, its call "
                  "ceiling or its cost ceiling",
        observers=("tool_transcript",),
        runner="tools",
        min_confinement="none",
        manifest="email",
        note="The host logs every call. A recipient outside the pattern "
             "reaching it is a break; so is a call past the manifest's cost "
             "ceiling of 40 credits, at 15 a call, which is the third; so "
             "is one past the grant's ceiling of three, which is the "
             "fourth. Both ceilings the door promises are checked, not "
             "only the one the grant names.",
    ),
    Claim(
        id="C8",
        budget="io",
        invariant="has a promise reported proven that a run then breaks",
        observers=("prover_lie",),
        runner="prover",
        min_confinement="partial",
        note="The judge reads the prover's answer from `sabline audit "
             "--json`, for every file the submission brought and not the "
             "entry file alone, and the run's exit from the receipt it "
             "asked the run for; what the program prints is never read. "
             "The receipt names the code that stopped the run (E601) and "
             "not the function, so a lie is scored only where every "
             "promise that could have raised it - in the entry file and in "
             "what it imports - is one the prover called proven. A promise "
             "left to run time anywhere in the program means the broken "
             "one need not be a proven one, and the claim holds.",
    ),
    Claim(
        id="C9",
        budget="io,ffi:gc",
        invariant="gets past the kernel's layers under an ffi grant that "
                  "widens nothing",
        observers=("outside_write", "nonce_in_output", "canary_diff",
                   "listener"),
        note="ffi:gc widens no OS policy, so the run is held to the same "
             "confinement as 'io' alone; the kernel, not the language, is "
             "what is under test.",
    ),
    Claim(
        id="C10",
        budget="io,fs:read:{READ},fs:write:{WRITE}",
        invariant="gets past the eval profile",
        observers=("outside_write", "nonce_in_output", "canary_diff",
                   "listener"),
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
