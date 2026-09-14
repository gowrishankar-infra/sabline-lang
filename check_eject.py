#!/usr/bin/env python3
"""velaris eject: an ejected program builds and runs with nothing from this
project, and its budget still holds.

Every check here runs the ejected directory with an interpreter from a
fresh virtual environment made for the purpose - no velaris-lang installed
in it, no PYTHONPATH, run with -I from another directory - so what is
tested is what a user who copied the directory elsewhere would have.

    python check_eject.py
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_eject")
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


def velaris_cli(*words, cwd=None):
    return subprocess.run([sys.executable, str(HERE / "velaris.py"), *words],
                          capture_output=True, text=True, cwd=cwd,
                          timeout=600)


def clean_env() -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("PYTHON") and not k.startswith("VELARIS_")}
    env["VELARIS_CACHE_DIR"] = str(WORK / "cache")
    return env


def main() -> int:
    print("velaris eject (8.1)")
    print("-" * 62)

    # a fresh environment with nothing in it
    venv = WORK / "venv"
    made = subprocess.run([sys.executable, "-m", "venv", "--without-pip",
                           str(venv)], capture_output=True, text=True,
                          timeout=300)
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    ok("a fresh virtual environment, with no pip and no packages",
       made.returncode == 0 and py.exists(), made.stderr)
    elsewhere = WORK / "elsewhere"
    elsewhere.mkdir()
    bare = subprocess.run([str(py), "-I", "-c", "import velaris"],
                          capture_output=True, text=True, cwd=elsewhere,
                          env=clean_env(), timeout=120)
    ok("...in which velaris cannot be imported",
       bare.returncode != 0 and "velaris" in bare.stderr, bare.stderr)

    out = WORK / "ej" / "discount"
    done = velaris_cli("eject", "examples/discount.vel", "-o", str(out),
                       cwd=HERE)
    ok("velaris eject examples/discount.vel writes the directory",
       done.returncode == 0 and (out / "main.py").is_file()
       and (out / "runtime" / "velaris.py").is_file()
       and (out / "program" / "discount.vel").is_file()
       and (out / "runtime" / "stdlib" / "money.vel").is_file(),
       done.stdout + done.stderr)
    for name in ("README.md", "requirements.txt", "proofs.json", "build.py",
                 "SHA256SUMS", "LICENSE"):
        ok(f"...with {name}", (out / name).is_file())
    ok("...and the runtime is this Velaris, byte for byte",
       (out / "runtime" / "velaris.py").read_bytes()
       == (HERE / "velaris.py").read_bytes())

    # it builds: every Python file compiles in the fresh environment, and
    # build.py names the PyInstaller command
    built = subprocess.run([str(py), "-I", "-m", "compileall", "-q",
                            str(out)], capture_output=True, text=True,
                           cwd=elsewhere, env=clean_env(), timeout=300)
    ok("it builds: every Python file in it compiles in the fresh "
       "environment", built.returncode == 0, built.stdout + built.stderr)
    command = subprocess.run([str(py), "-I", str(out / "build.py"),
                              "--print"], capture_output=True, text=True,
                             cwd=elsewhere, env=clean_env(), timeout=120)
    ok("...and build.py names the one-executable PyInstaller command",
       command.returncode == 0 and "PyInstaller" in command.stdout
       and "--onefile" in command.stdout and "runtime" in command.stdout,
       command.stdout + command.stderr)

    ran = subprocess.run([str(py), "-I", str(out / "main.py")],
                         capture_output=True, text=True, cwd=elsewhere,
                         env=clean_env(), timeout=600)
    ok("it runs in the fresh environment, from another directory, and "
       "computes what the program computes",
       ran.returncode == 0 and "payable  INR 112.90" in ran.stdout,
       ran.stdout[-300:] + ran.stderr[-300:])

    sums = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    good = all(hashlib.sha256((out / line[66:]).read_bytes()).hexdigest()
               == line[:64] for line in sums)
    listed = {line[66:] for line in sums}
    ok("SHA256SUMS holds the sha256 of every other file, and each matches",
       good and {"main.py", "runtime/velaris.py", "program/discount.vel",
                 "README.md", "proofs.json"} <= listed, sums[:3])

    record = json.loads((out / "proofs.json").read_text(encoding="utf-8"))
    ok("proofs.json records the budget, the version, and what was proven",
       record.get("schema") == "velaris.eject/1"
       and record.get("velaris_version") == velaris.VERSION
       and record.get("budget") == "io"
       and record.get("prover") is bool(velaris.HAVE_Z3)
       and any(f["name"] == "discount_for" for f in record["functions"]),
       str(record)[:300])
    statuses = {f["status"] for f in record["functions"]
                if f["requires"] or f["ensures"]}
    ok("...proven with the prover, checked at run time without it",
       ("proven" in statuses) if velaris.HAVE_Z3
       else ("proven" not in statuses), statuses)

    pins = (out / "requirements.txt").read_text(encoding="utf-8")
    from importlib import metadata
    for dist in ("z3-solver", "llvmlite"):
        try:
            want = f"{dist}=={metadata.version(dist)}"
            ok(f"requirements.txt pins {dist} to the version installed",
               want in pins, pins)
        except metadata.PackageNotFoundError:
            ok(f"requirements.txt says {dist} was not installed",
               f"# {dist} was not installed" in pins
               and f"{dist}==" not in pins, pins)

    readme = (out / "README.md").read_text(encoding="utf-8")
    ok("the README says what holds and what does not",
       "What holds once ejected" in readme and "What does not" in readme
       and "The budget is enforced" in readme
       and "The proofs are a record, not a promise" in readme)

    proved = subprocess.run([str(py), "-I", str(out / "main.py"), "--prove"],
                            capture_output=True, text=True, cwd=elsewhere,
                            env=clean_env(), timeout=600)
    ok("main.py --prove checks the promises again, with the copied runtime",
       proved.returncode == 0 and "ok -" in proved.stdout,
       proved.stdout + proved.stderr)

    # ---- the budget holds once ejected ----------------------------------
    asked = subprocess.run([str(py), "-I", str(out / "main.py"),
                            "--allow", "net"], capture_output=True, text=True,
                           cwd=elsewhere, env=clean_env(), timeout=120)
    ok("main.py refuses --allow: the budget is fixed at eject time",
       asked.returncode == 2 and "fixed at eject time" in asked.stderr,
       asked.stderr)

    program = out / "program" / "discount.vel"
    ejected = program.read_bytes()      # restored byte for byte: a text
    text = program.read_text(encoding="utf-8")  # round trip can change EOLs
    widened = (re.sub(r"\bfn main\(\) uses io\b", "fn old_main() uses io",
                      text, count=1)
               + '\nfn main() uses io, net {\n'
                 '    check fetch("https://collector.example.org/x") {\n'
                 '        ok body { print("FETCHED " + body) }\n'
                 '        fail why { print("could not fetch") }\n'
                 '    }\n    old_main()\n}\n')
    program.write_text(widened, encoding="utf-8")
    refused = subprocess.run([str(py), "-I", str(out / "main.py")],
                             capture_output=True, text=True, cwd=elsewhere,
                             env=clean_env(), timeout=600)
    ok("a program changed after ejecting is not run: main.py names the "
       "file that differs", refused.returncode == 2
       and "program/discount.vel" in refused.stderr, refused.stderr)
    anyway = subprocess.run([str(py), "-I", str(out / "main.py"),
                             "--changed-ok"], capture_output=True, text=True,
                            cwd=elsewhere, env=clean_env(), timeout=600)
    ok("...and with --changed-ok it runs and is refused net (E310), before "
       "anything is fetched",
       anyway.returncode == 1 and "E310" in anyway.stderr
       and "'net'" in anyway.stderr and "FETCHED" not in anyway.stdout,
       anyway.stdout[-200:] + anyway.stderr[-300:])
    program.write_bytes(ejected)

    runtime = out / "runtime" / "velaris.py"
    original = runtime.read_bytes()
    runtime.write_bytes(original + b"\n# changed after ejecting\n")
    tampered = subprocess.run([str(py), "-I", str(out / "main.py"),
                               "--changed-ok"], capture_output=True,
                              text=True, cwd=elsewhere, env=clean_env(),
                              timeout=600)
    runtime.write_bytes(original)
    ok("a changed runtime is never run, --changed-ok or not: it is what "
       "enforces the budget", tampered.returncode == 2
       and "runtime/velaris.py" in tampered.stderr
       and "payable" not in tampered.stdout, tampered.stderr)
    into = subprocess.run([str(py), "-I", str(out / "main.py"), "--receipt",
                           str(out / "main.py")], capture_output=True,
                          text=True, cwd=elsewhere, env=clean_env(),
                          timeout=120)
    ok("main.py refuses a --receipt that would land in its own directory",
       into.returncode == 2 and "--receipt" in into.stderr
       and (out / "main.py").read_text(encoding="utf-8").startswith(
           "#!/usr/bin/env python3"), into.stderr)
    receipt = WORK / "ejected-receipt.json"
    kept = subprocess.run([str(py), "-I", str(out / "main.py"), "--receipt",
                           str(receipt)], capture_output=True, text=True,
                          cwd=elsewhere, env=clean_env(), timeout=600)
    doc = json.loads(receipt.read_text(encoding="utf-8")) \
        if receipt.exists() else {}
    ok("...and writes one elsewhere: the ejected program's receipt, under "
       "the fixed budget", kept.returncode == 0
       and doc.get("predicate", {}).get("budget") == "io"
       and doc.get("predicate", {}).get("exit", {}).get("outcome") == "ok",
       kept.stderr[-200:] + str(doc)[:200])

    # a budget that could let one run rewrite the next
    inside = velaris_cli("eject", "examples/discount.vel", "-o",
                         str(WORK / "ej" / "writes"), "--allow",
                         f"io,fs:write:{(WORK / 'ej').as_posix()}", cwd=HERE)
    ok("eject refuses a budget that lets the program write into the "
       "ejected directory", inside.returncode == 2
       and "refused" in inside.stderr
       and not (WORK / "ej" / "writes").exists(), inside.stderr)
    plain = velaris_cli("eject", "examples/discount.vel", "-o",
                        str(WORK / "ej" / "plain"), "--allow", "io,fs",
                        cwd=HERE)
    ok("...and plain fs, which writes anywhere", plain.returncode == 2
       and "plain fs" in plain.stderr, plain.stderr)
    rel = WORK / "ej" / "relative"
    relative = velaris_cli("eject", "examples/discount.vel", "-o", str(rel),
                           "--allow", "io,fs:write:./out", cwd=HERE)
    ok("a relative write grant is allowed at eject", relative.returncode == 0,
       relative.stderr)
    where_it_reaches = subprocess.run(
        [str(py), "-I", str(rel / "main.py")], capture_output=True, text=True,
        cwd=rel, env=clean_env(), timeout=600)
    ok("...but main.py refuses to start where ./out would be inside its own "
       "directory", where_it_reaches.returncode == 2
       and "write into this directory" in where_it_reaches.stderr,
       where_it_reaches.stderr)
    from_outside = subprocess.run(
        [str(py), "-I", str(rel / "main.py")], capture_output=True, text=True,
        cwd=elsewhere, env=clean_env(), timeout=600)
    ok("...and runs where it is not", from_outside.returncode == 0,
       from_outside.stderr[-300:])
    pylib = WORK / "pylib"
    pylib.mkdir()
    writes_code = WORK / "ej" / "pylib-writer"
    made = velaris_cli("eject", "examples/discount.vel", "-o", str(writes_code),
                       "--allow", f"io,fs:write:{pylib.as_posix()}", cwd=HERE)
    on_path = dict(clean_env(), PYTHONPATH=str(pylib))
    launched = subprocess.run([str(py), str(writes_code / "main.py")],
                              capture_output=True, text=True, cwd=elsewhere,
                              env=on_path, timeout=600)
    ok("main.py refuses a budget that writes into a directory Python imports "
       "from (here a PYTHONPATH entry, where a sitecustomize.py would run in "
       "the next Python started)", made.returncode == 0
       and launched.returncode == 2 and "imports from" in launched.stderr,
       made.stderr[-200:] + launched.stderr[-300:])
    isolated = subprocess.run([str(py), "-I", str(writes_code / "main.py")],
                              capture_output=True, text=True, cwd=elsewhere,
                              env=on_path, timeout=600)
    ok("...and still refuses under -I, since the next Python may be started "
       "without it", isolated.returncode == 2
       and "imports from" in isolated.stderr, isolated.stderr[-300:])

    again = velaris_cli("eject", "examples/discount.vel", "-o", str(out),
                        cwd=HERE)
    forced = velaris_cli("eject", "examples/discount.vel", "-o", str(out),
                         "--force", cwd=HERE)
    stranger = WORK / "ej" / "not-ours"
    stranger.mkdir()
    (stranger / "notes.txt").write_text("mine\n", encoding="utf-8")
    theirs = velaris_cli("eject", "examples/discount.vel", "-o",
                         str(stranger), "--force", cwd=HERE)
    ok("eject does not overwrite a directory without --force, and never one "
       "it did not make",
       again.returncode == 2 and forced.returncode == 0
       and theirs.returncode == 2
       and (stranger / "notes.txt").read_text(encoding="utf-8") == "mine\n",
       f"{again.returncode} {forced.returncode} {theirs.returncode}")

    broken = WORK / "broken.vel"
    broken.write_text("fn main() uses io {\n    print(1 +)\n}\n",
                      encoding="utf-8")
    nope = velaris_cli("eject", str(broken), "-o", str(WORK / "ej" / "no"))
    ok("a program that does not compile is not ejected",
       nope.returncode == 1 and not (WORK / "ej" / "no").exists(),
       nope.stderr)

    print("-" * 62)
    print(f"{PASS} correct, {FAIL} wrong")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
