#!/usr/bin/env python3
"""examples/platform must refuse what it says it refuses.

The example is a reference for platform teams, so the two guarantees it
claims are asserted here rather than described: a script whose declared
capability surface is wider than the platform permits never reaches
storage, and a script that reaches for an effect the pool does not grant
is refused while it runs - whatever the gate decided about it.

    python check_platform.py

fastapi is a dependency of the example, never of Sabline. Without it
(or without the http client its test client needs) this suite skips.
"""
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from suite_dirs import isolate  # noqa: E402

isolate("check_platform")             # its own directory

HAVE_PROVER = sabline.HAVE_Z3

READS_A_FILE = ('fn peek(p: Text) -> Text uses fs or fail {\n'
                '    return try read_file(p)\n}\n\n'
                'fn main() uses io, fs {\n'
                '    check peek("sabline.py") {\n'
                '        ok body { print("read it") }\n'
                '        fail why { print("could not") }\n    }\n}\n')

# the host is built while running, so the audit cannot name it and says
# plain net - which a platform granting one host does not cover
COMPUTED_HOST = ('fn ping(h: Text) -> Text uses net or fail {\n'
                 '    return try fetch(format("https://{}/v1", h))\n}\n\n'
                 'fn main() uses io, net {\n'
                 '    check ping("api.example.com") {\n'
                 '        ok body { print(body) }\n'
                 '        fail why { print("no") }\n    }\n}\n')

NAMES_THE_HOST = ('fn ping() -> Text uses net or fail {\n'
                  '    return try fetch("https://api.example.com/v1")\n}\n\n'
                  'fn main() uses io, net {\n'
                  '    check ping() {\n'
                  '        ok body { print(body) }\n'
                  '        fail why { print("no answer") }\n    }\n}\n')

WONT_PROVE = ('fn discount(price: Int) -> Int\n'
              '    ensures result >= 0\n{\n    return 0 - price\n}\n\n'
              'fn main() uses io {\n    print(discount(5))\n}\n')

NEVER_ENDS = ('fn main() uses io {\n    let i = 0\n    while i >= 0 {\n'
              '        i = i + 1\n        if i > 1000000 {\n'
              '            i = 0\n        }\n    }\n    print(1)\n}\n')

# written to stall the audit, not to run: nine hundred functions, each one
# expression chained just under the parser's limit - valid Sabline that
# takes the checker many seconds to read
INFLATED = "".join(
    f"fn f{i}(n: Int) -> Int {{ return {'+'.join(['n'] * 999)} }}\n"
    for i in range(900)) + "fn main() uses io { print(f0(1)) }\n"

# and a promise written to stall the prover: a cube over floating point,
# which Z3 decides by bit-blasting 64-bit values
CRAFTED = ("fn f(x: Float, y: Float, z: Float) -> Float\n"
           "    requires x > 1.0 and y > 1.0 and z > 1.0\n"
           "    ensures result * result * result == x * y * z * x\n"
           "{\n    return x * y * z\n}\n"
           "fn main() uses io { print(f(2.0, 3.0, 4.0)) }\n")


def main() -> int:                        # noqa: C901 - a suite, not logic
    passed = failed = 0

    def ok(label: Any, condition: Any, detail: str = "") -> None:
        nonlocal passed, failed
        if condition:
            print(f"  ok       {label}")
            passed += 1
        else:
            print(f"  BROKEN   {label}")
            if detail:
                print(f"           {detail}")
            failed += 1

    def skip(label: Any, why: Any) -> None:
        print(f"  skipped  {label}")
        print(f"           {why}")

    print("a platform that lets its customers write Sabline")
    print("-" * 62)

    try:
        sys.path.insert(0, str(HERE / "examples" / "platform"))
        import app as platform                                # noqa: E402
        from fastapi.testclient import TestClient              # noqa: E402
        client = TestClient(platform.app)
    except Exception as e:                 # fastapi, or its test client
        skip("examples/platform is exercised end to end", f"{e}")
        print("-" * 62)
        print("0 correct, 0 wrong")
        return 0

    try:
        discount = (HERE / "examples" / "discount.vel").read_text(
            encoding="utf-8")

        # ---- a submission inside the platform's budget ---------------
        r = client.post("/scripts?name=discount", content=discount)
        body = r.json()
        ok("a script whose surface is inside the platform's budget is "
           "accepted", r.status_code == 201 and "id" in body,
           f"{r.status_code} {str(body)[:160]}")
        sid = body.get("id", "")
        declares = body.get("declares", {})
        ok("and what comes back is what it declares, not what it does",
           declares.get("effects") == ["io"]
           and declares.get("narrowest_budget") == "io"
           and declares.get("hosts") == {"hosts": [], "any": False}
           and declares.get("paths", {}).get("read") == []
           and declares.get("modules") == []
           and declares.get("most_operations") == {"fs": 0, "net": 0}
           and declares.get("audit_schema") == "sabline.audit/1",
           str(declares)[:200])
        ok("submitting runs nothing: the pool has not started a worker",
           platform.POOL.started == 0, f"{platform.POOL.started} started")

        # ---- the proven discount, as a customer would be shown it ----
        got = client.get(f"/scripts/{sid}")
        shown = got.json().get("declares", {})
        contracts = {c["function"]: c["status"]
                     for c in shown.get("contracts", [])}
        ok("GET /scripts/{id} shows the same declaration submission "
           "returned", got.status_code == 200 and shown == declares,
           f"{got.status_code} {str(shown)[:160]}")
        ok("the discount rule's promises are in the declaration, by "
           "function",
           {"discount_for", "total_after", "charged_per_line"}
           <= set(contracts)
           and any("result >= money(0, \"INR\")" in e
                   for e in next(c["ensures"] for c in shown["contracts"]
                                 if c["function"] == "discount_for")),
           str(contracts))
        if HAVE_PROVER:
            ok("and every one of them is proven before anything runs - "
               "the thing no sandbox can show",
               shown.get("prover_ran") is True
               and shown.get("proven_share") == 100.0
               and set(contracts.values()) == {"proven"},
               f"{shown.get('proven_share')} {contracts}")
        else:
            ok("without a prover the declaration says so rather than "
               "claiming a proven share that means nothing",
               shown.get("prover_ran") is False
               and "proven" not in set(contracts.values()),
               f"{shown.get('prover_ran')} {contracts}")

        # ---- a submission the platform's budget does not cover -------
        r = client.post("/scripts?name=reads-a-file", content=READS_A_FILE)
        refused = r.json()
        ok("a script that reads a file is refused at submission, naming "
           "what would have to be granted",
           r.status_code == 403
           and refused.get("would_need_granting") == ["fs:read"]
           and refused.get("declares") == "fs:read,io"
           and "fs" in refused.get("error", ""),
           f"{r.status_code} {str(refused)[:160]}")

        r = client.post("/scripts?name=computed-host",
                        content=COMPUTED_HOST)
        refused = r.json()
        ok("a host built while running declares plain net, which a "
           "platform granting one host refuses",
           r.status_code == 403
           and refused.get("declares") == "io,net"
           and refused.get("would_need_granting") == ["net"],
           f"{r.status_code} {str(refused)[:160]}")

        r = client.post("/scripts?name=names-the-host",
                        content=NAMES_THE_HOST)
        ok("the same program naming the host in a literal is accepted",
           r.status_code == 201
           and r.json()["declares"]["narrowest_budget"]
           == "io,net:api.example.com",
           f"{r.status_code} {str(r.json())[:160]}")

        r = client.post("/scripts?name=wont-prove", content=WONT_PROVE)
        if HAVE_PROVER:
            ok("a rule whose promise cannot be kept is refused with the "
               "counterexample, not stored",
               r.status_code == 400
               and any(p["code"] == "E700"
                       for p in r.json().get("problems", [])),
               f"{r.status_code} {str(r.json())[:160]}")
        else:
            skip("a rule whose promise cannot be kept is refused at "
                 "submission", "no prover: that promise is checked while "
                 "it runs, which is correct without z3-solver")

        # ---- the pool is the guard, whatever the gate decided ---------
        # a script that never passed submission, put straight into the
        # store: the budget a worker installs does not consult the gate
        platform.SCRIPTS["ungated"] = {"id": "ungated", "name": "ungated",
                                       "source": READS_A_FILE,
                                       "declares": {}}
        ran = client.post("/scripts/ungated/run").json()
        ok("a run refuses an effect outside the pool's budget, even for "
           "a script the gate never saw",
           ran.get("outcome") == "refused"
           and ran.get("refused") == [{"by": "budget", "code": "E310",
                                       "what": "fs"}]
           and ran.get("output") == "",
           str(ran)[:200])
        ok("and the refusal names the budget the run had, which is the "
           "platform's", ran.get("ran_under") == platform.PLATFORM_ALLOW
           and platform.POOL.allow == sabline.Budget.parse(
               platform.PLATFORM_ALLOW).spec(),
           f"{ran.get('ran_under')} vs {platform.POOL.allow}")

        # ---- a run that does what it said it would -------------------
        ran = client.post(f"/scripts/{sid}/run").json()
        ok("the discount rule runs, and prints what it computes",
           ran.get("outcome") == "ok"
           and "payable  INR 112.90" in ran.get("output", "")
           and ran.get("refused") == [] and ran.get("stopped_by") is None,
           str(ran)[:200])

        # ---- a limit, rather than an effect, stops a run --------------
        r = client.post("/scripts?name=never-ends", content=NEVER_ENDS)
        spin = r.json()
        ok("a loop that is not shown to end is said so in the "
           "declaration, before anyone enables it",
           r.status_code == 201
           and any("termination is not shown" in w
                   for w in spin["declares"]["warnings"]),
           str(spin.get("declares", {}).get("warnings"))[:160])
        ran = client.post(f"/scripts/{spin['id']}/run").json()
        ok("and the run says which limit stopped it",
           ran.get("outcome") == "timeout"
           and ran.get("stopped_by") == f"the {platform.TIMEOUT_S}s time "
                                        f"limit",
           str(ran)[:200])

        # ---- a submission written to stall the audit itself (8.1) -----
        # the audit is the first thing that reads a customer's text, so it
        # is the first thing a hostile text aims at; it stops at the
        # platform's audit limit, and nothing is stored
        saved = platform.AUDIT_TIMEOUT_S
        platform.AUDIT_TIMEOUT_S = 2
        try:
            for label, text, needs_prover in (
                    ("an inflated expression", INFLATED, False),
                    ("a crafted contract", CRAFTED, True)):
                if needs_prover and not HAVE_PROVER:
                    skip(f"{label} is stopped at the audit limit",
                         "no prover: that promise is checked while it runs, "
                         "and nothing stalls")
                    continue
                before = len(platform.SCRIPTS)
                began = time.monotonic()
                r = client.post(f"/scripts?name={label}", content=text)
                took = time.monotonic() - began
                body = r.json()
                ok(f"{label} is stopped at the platform's audit limit "
                   f"(E613), answered in seconds, and not stored",
                   r.status_code == 422
                   and [p["code"] for p in body.get("problems", [])]
                   == ["E613"]
                   and body.get("limits", {}).get("audit_timeout_s") == 2
                   and took < 60 and len(platform.SCRIPTS) == before,
                   f"{r.status_code} {took:.1f}s {str(body)[:160]}")
        finally:
            platform.AUDIT_TIMEOUT_S = saved
    finally:
        platform.POOL.close()

    print("-" * 62)
    print(f"{passed} correct, {failed} wrong")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
