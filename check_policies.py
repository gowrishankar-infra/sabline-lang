#!/usr/bin/env python3
"""policies/: the OPA policy and its Kyverno twin ask what they say.

With `opa` on PATH (or the binary OPA names): `opa check` and `opa test` on
policies/opa, then `opa eval` of the policy against Statements `velaris
attest` writes now - one program inside the platform's lists, and ones
outside them. Without it those are skipped, with a notice saying so. The
Kyverno policy is read (as YAML with PyYAML when it is installed, by its
lines otherwise) and held to the fields image verification needs; running
it takes a cluster and a signed image, which a test suite does not have.

    python check_policies.py
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_policies")
OPA_DIR = HERE / "policies" / "opa"
KYVERNO = HERE / "policies" / "kyverno" / "require-capability-attestation.yaml"
PASS = FAIL = 0


def ok(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok      {label}")
    else:
        FAIL += 1
        print(f"  BROKEN  {label}")
        if detail:
            print(f"          {str(detail)[:400]}")


def notice(text):
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::notice::{text}")
    print(f"  skipped {text}")


INSIDE = ('fn ping() -> Text uses net or fail {\n'
          '    return try fetch("https://api.example.com/v1")\n}\n\n'
          'fn main() uses io, net {\n'
          '    check ping() {\n'
          '        ok body { print(body) }\n'
          '        fail why { print("no answer") }\n    }\n}\n')

OUTSIDE = ('fn send(t: Text) -> Text uses net or fail {\n'
           '    return try post("https://collector.example.org/in", t)\n}\n\n'
           'fn main() uses io, fs, net {\n'
           '    check read_file("notes.txt") {\n'
           '        ok t {\n'
           '            check send(t) {\n'
           '                ok r { print("sent") }\n'
           '                fail w { print("not sent") }\n'
           '            }\n'
           '        }\n'
           '        fail why { print("no notes") }\n    }\n}\n')

COMPUTED = ('fn ping(h: Text) -> Text uses net or fail {\n'
            '    return try fetch(format("https://{}/v1", h))\n}\n\n'
            'fn main() uses io, net {\n'
            '    check ping("api.example.com") {\n'
            '        ok body { print(body) }\n'
            '        fail why { print("no") }\n    }\n}\n')

PLATFORM = {"platform": {"effects": ["io", "net"],
                         "hosts": ["api.example.com"]}}


def main() -> int:
    print("policies/: what a policy asks of an attestation (8.1)")
    print("-" * 62)
    rego = (OPA_DIR / "capability.rego").read_text(encoding="utf-8")
    ok("the OPA policy names the capability/v1 predicate type velaris "
       "writes", f'"{velaris.CAPABILITY_PREDICATE_TYPE}"' in rego)

    opa = shutil.which(os.environ.get("OPA", "opa"))
    if opa is None:
        notice("opa is not installed, so policies/opa was not run; install "
               "it (or set OPA) to run `opa test` and `opa eval` here")
    else:
        checked = subprocess.run([opa, "check", str(OPA_DIR)],
                                 capture_output=True, text=True, timeout=120)
        ok("opa check: the policy and its tests compile",
           checked.returncode == 0, checked.stdout + checked.stderr)
        tested = subprocess.run([opa, "test", str(OPA_DIR), "-v"],
                                capture_output=True, text=True, timeout=120)
        ok("opa test: a pass and a fail, and the edges, as written",
           tested.returncode == 0 and "FAIL" not in tested.stdout
           and "PASS" in tested.stdout, tested.stdout + tested.stderr)

        data = WORK / "platform.json"
        data.write_text(json.dumps(PLATFORM), encoding="utf-8")

        def deny_for(label, source):
            program = WORK / f"{label}.vel"
            program.write_text(source, encoding="utf-8")
            statement = WORK / f"{label}.intoto.json"
            statement.write_text(json.dumps(velaris.attest(str(program))[0]),
                                 encoding="utf-8")
            done = subprocess.run(
                [opa, "eval", "--format", "json",
                 "-d", str(OPA_DIR / "capability.rego"), "-d", str(data),
                 "-i", str(statement), "data.velaris.capability.deny"],
                capture_output=True, text=True, timeout=120)
            try:
                value = json.loads(done.stdout)["result"][0][
                    "expressions"][0]["value"]
            except Exception:
                value = None
            return value, done

        denied, done = deny_for("inside", INSIDE)
        ok("opa eval admits a Statement velaris attest wrote for a program "
           "inside the lists", denied == [], f"{denied} {done.stderr}")
        denied, done = deny_for("outside", OUTSIDE)
        ok("opa eval refuses one outside them, naming the effect and the "
           "host",
           isinstance(denied, list)
           and "net host collector.example.org is outside the allow-list"
           in denied
           and any(d.startswith("effect fs is outside") for d in denied),
           f"{denied} {done.stderr}")
        denied, done = deny_for("computed", COMPUTED)
        ok("...and one whose host is built while it runs",
           isinstance(denied, list) and any("built while the program runs"
                                            in d for d in denied),
           f"{denied} {done.stderr}")

    kyverno = shutil.which(os.environ.get("KYVERNO", "kyverno"))
    if kyverno is None:
        notice("the kyverno CLI is not installed, so the policy was not "
               "loaded by Kyverno itself; its fields are checked below")
    else:
        pod = WORK / "pod.yaml"
        pod.write_text("apiVersion: v1\nkind: Pod\nmetadata:\n  name: other\n"
                       "spec:\n  containers:\n    - name: app\n"
                       "      image: docker.io/library/busybox:1.36\n",
                       encoding="utf-8")
        loaded = subprocess.run([kyverno, "apply", str(KYVERNO), "--resource",
                                 str(pod)], capture_output=True, text=True,
                                timeout=120)
        said = loaded.stdout + loaded.stderr
        ok("the kyverno CLI loads the policy - a field it does not know "
           "would leave it loading no rule at all",
           loaded.returncode == 0 and "Applying 0 policy rule" not in said
           and "policy rule(s)" in said, said[-300:])
    text = KYVERNO.read_text(encoding="utf-8")
    try:
        import yaml
    except ImportError:
        yaml = None
    if yaml is None:
        notice("PyYAML is not installed, so the Kyverno policy was read by "
               "its lines")
        for needle in ("apiVersion: kyverno.io/v1", "kind: ClusterPolicy",
                       "failureAction: Enforce", "required: true",
                       "predicateType: "
                       + velaris.CAPABILITY_PREDICATE_TYPE,
                       "issuer: \"https://token.actions.githubusercontent.com\"",
                       "key: \"{{ audit.ok }}\""):
            ok(f"the Kyverno policy holds `{needle}`", needle in text)
    else:
        doc = yaml.safe_load(text)
        rule = doc["spec"]["rules"][0]
        verify = rule["verifyImages"][0]
        attestation = verify["attestations"][0]
        keyless = attestation["attestors"][0]["entries"][0]["keyless"]
        conditions = attestation["conditions"][0]["all"]
        ok("the Kyverno policy is a ClusterPolicy on Pods",
           doc["apiVersion"] == "kyverno.io/v1"
           and doc["kind"] == "ClusterPolicy"
           and rule["match"]["any"][0]["resources"]["kinds"] == ["Pod"])
        ok("...that refuses, rather than audits, an image without the "
           "attestation",
           verify["failureAction"] == "Enforce" and verify["required"] is True
           and verify["verifyDigest"] is True)
        ok("...of the capability/v1 predicate type velaris writes",
           attestation["predicateType"] == velaris.CAPABILITY_PREDICATE_TYPE)
        ok("...signed keylessly by a named workflow, logged in Rekor",
           keyless["issuer"] == "https://token.actions.githubusercontent.com"
           and keyless["subject"].startswith("https://github.com/")
           and keyless["rekor"]["url"] == "https://rekor.sigstore.dev")
        ok("...whose audit is velaris.audit/1 and compiled",
           {"key": "{{ audit.schema }}", "operator": "Equals",
            "value": "velaris.audit/1"} in conditions
           and {"key": "{{ audit.ok }}", "operator": "Equals",
                "value": True} in conditions, conditions)

    print("-" * 62)
    print(f"{PASS} correct, {FAIL} wrong")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
