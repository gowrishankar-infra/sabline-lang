#!/usr/bin/env python3
"""A platform that lets its customers write Velaris.

A SaaS team wants its customers to write their own rules - a discount, a
routing decision, a validation - and has to decide, before one of them
runs on the team's machines, what it may touch. For a rule that computes
money it also has to know the arithmetic holds, which no sandbox can
answer.

    POST /scripts           a customer submits source. It is audited and
                            stored with its capability surface, and what
                            it declares comes back. Nothing runs.
    GET  /scripts/{id}      what that script declares - the page a
                            customer is shown before enabling it.
    POST /scripts/{id}/run  runs it on a pool whose budget is the
                            platform's, never the script's.

Two guards, and they are not the same guard. The audit reads the text:
it says what a script declares, and submission is refused when that is
wider than the platform permits, naming the grants that would have to be
added. The pool enforces: its budget is installed by the worker before
the program is read, a program cannot widen it, and a refusal cannot be
caught. Where the audit cannot read a path, host or module - a value
built while running - it widens to the plain effect and the gate refuses
that; the pool never depends on the audit having been right.

    pip install fastapi uvicorn
    python -m uvicorn app:app --app-dir examples/platform

Storage is a dict in this process. README.md says what a real one adds.
"""
import re
import sys
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse

# so the example runs from a clone; pip install velaris-lang makes this
# line unnecessary
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import velaris  # noqa: E402

# ---- the platform's policy, in one place ------------------------------

# What a customer's script may touch here: the console, and the
# platform's own API. No files, no other host, no Python.
PLATFORM_ALLOW = "io,net:api.example.com@20"
TIMEOUT_S, MEMORY_MB = 5, 256
# How long, and in how much memory, the audit of a submission may take. A
# customer's source is read by the compiler before anything runs, and a
# source can be written to stall that; the audit stops at these (8.1).
AUDIT_TIMEOUT_S, AUDIT_MEMORY_MB = 20, 1024


def grants(spec: str) -> list:
    """A budget as separate grants. `ffi:a,b` is one grant: its module
    names follow it as bare items, which is how the grammar has them."""
    out: list = []
    for item in spec.split(","):
        if out and ":" not in item and item not in velaris.ALL_EFFECTS:
            out[-1] += "," + item
        else:
            out.append(item)
    return out


# The pool gets the budget entire. The submission gate compares only what
# a script may TOUCH, not how much of it: an audit bounds operations only
# where the text fixes them, and the count is the pool's to enforce at
# run time either way.
SURFACE = velaris.Budget.parse(re.sub(r"@\d+", "", PLATFORM_ALLOW))

# One pool, one budget, for every customer's script. It is parsed here,
# once; pool.run takes no allow argument, so there is nowhere for a
# caller or a program to ask for more. Workers are closed at exit.
POOL = velaris.Pool(size=2, allow=set(grants(PLATFORM_ALLOW)),
                    timeout=TIMEOUT_S, max_memory_mb=MEMORY_MB)

SCRIPTS: dict = {}          # an example: no database, no tenants

app = FastAPI(title="Velaris scripts")


# ---- what the platform reads off an audit -----------------------------

def would_need_granting(asked: str) -> list:
    """Every grant in `asked` this platform does not already cover - what
    an operator would have to add to PLATFORM_ALLOW to accept it."""
    return [g for g in grants(asked)
            if SURFACE.covers(velaris.Budget.parse(g))]


def problems(items: list) -> list:
    """A customer sent text, not a file, so the temporary path Velaris
    gave it is noise."""
    return [{k: v for k, v in p.as_dict().items() if k != "file"}
            for p in items]


def declaration(report) -> dict:
    """What a script says about itself, from the audit alone. Every field
    here comes from velaris.audit/1, whose shape is stable."""
    return {
        "effects": report.effects,
        "hosts": report.net_hosts,
        "paths": report.fs_paths,
        "modules": report.ffi_modules,
        "module_built_at_runtime": report.ffi_any,
        "narrowest_budget": report.safe_command.split("--allow ", 1)[1],
        "most_operations": report.counts,
        "proven_share": report.proven_share,
        "prover_ran": report.prover,
        "contracts": [{"function": f["name"], "requires": f["requires"],
                       "ensures": f["ensures"], "status": f["status"]}
                      for f in report.functions
                      if f["requires"] or f["ensures"]],
        "warnings": report.warnings,
        "audit_schema": report.schema,
        "velaris_version": report.velaris_version,
    }


def as_shown(script: dict) -> dict:
    """A stored script as the platform shows it to a customer."""
    return {"id": script["id"], "name": script["name"],
            "declares": script["declares"],
            "runs_under": PLATFORM_ALLOW,
            "limits": {"timeout_s": TIMEOUT_S, "memory_mb": MEMORY_MB}}


def stored(sid: str) -> dict:
    script = SCRIPTS.get(sid)
    if script is None:
        raise HTTPException(404, "no such script")
    return script


# ---- the three endpoints ----------------------------------------------

@app.get("/")
def policy() -> dict:
    """What this platform permits, and what it holds."""
    return {"platform_allows": PLATFORM_ALLOW,
            "limits": {"timeout_s": TIMEOUT_S, "memory_mb": MEMORY_MB},
            "velaris_version": velaris.VERSION,
            "scripts": [{"id": s["id"], "name": s["name"]}
                        for s in SCRIPTS.values()]}


@app.post("/scripts", status_code=201)
def submit(source: str = Body(..., media_type="text/plain"),
           name: str = "untitled"):
    """Audit it, decide, store it. This never runs the script."""
    report = velaris.audit(source, timeout=AUDIT_TIMEOUT_S,
                           max_memory_mb=AUDIT_MEMORY_MB)
    stopped = [p for p in report.problems if p.code in ("E613", "E614")]
    if stopped:
        return JSONResponse(status_code=422, content={
            "error": "the audit did not finish within this platform's "
                     "limits, so this cannot be enabled",
            "problems": problems(stopped),
            "limits": {"audit_timeout_s": AUDIT_TIMEOUT_S,
                       "audit_memory_mb": AUDIT_MEMORY_MB}})
    if not report.ok:
        return JSONResponse(status_code=400, content={
            "error": "this does not compile, so it cannot be enabled",
            "problems": problems(report.problems)})
    asked = report.safe_command.split("--allow ", 1)[1]
    refused = SURFACE.covers(velaris.Budget.parse(asked))
    if refused:
        return JSONResponse(status_code=403, content={
            # covers() names the first thing that does not fit, in
            # Velaris's own words
            "error": refused,
            "declares": asked,
            "platform_allows": PLATFORM_ALLOW,
            "would_need_granting": would_need_granting(asked)})
    sid = uuid.uuid4().hex[:12]
    SCRIPTS[sid] = {"id": sid, "name": name, "source": source,
                    "declares": declaration(report)}
    return as_shown(SCRIPTS[sid])


@app.get("/scripts/{sid}")
def inspect(sid: str) -> dict:
    """What this script declares, as a customer is shown it."""
    return as_shown(stored(sid))


@app.post("/scripts/{sid}/run")
def run(sid: str) -> dict:
    """Run it under the platform's budget - not the script's. The pool
    was made with one budget, pool.run takes no allow argument, and the
    worker reinstalls that budget before every program."""
    result = POOL.run(stored(sid)["source"])
    return {
        "outcome": velaris.run_outcome(result),
        "output": result.output,
        "logs": result.logs,
        "refused": velaris.run_refusals(result),
        "stopped_by": (f"the {TIMEOUT_S}s time limit" if result.timed_out
                       else f"the {MEMORY_MB} MB memory limit"
                       if result.out_of_memory else None),
        "effects_used": result.effects_used,
        "problems": problems(result.problems),
        "ran_under": PLATFORM_ALLOW,
    }
