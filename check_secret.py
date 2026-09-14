#!/usr/bin/env python3
"""Secret of T: a value the type system will not let out (SPEC.md 3.1).

Every case here is a whole program, compiled or run by the real
compiler. The suite covers what an information-flow type has to get
right, and the places a hole would be:

  * every emitting builtin refuses a Secret argument, with E560 naming
    the value and where the secret came from
  * so does every fallible builtin, because a failure's reason is text
    the program can print and the runtime builds it out of the values
    it was given
  * a structure is not a way around it: a record field, a list element
    and a map value each make the whole thing carry the secret
  * a secret cannot be laundered through a helper, through a generic
    function with effects, through a 'fail' reason, or through a
    signature that says it returns a plain value
  * every pure operation over a secret keeps the secret, a comparison
    included: `key == c` is a Secret of Bool, nothing prints one, and
    nothing branches on one (E563) - because in a loop a plain Bool
    would read the whole key out a character at a time, which this
    suite demonstrates and then refuses
  * a promise may be about a secret, where a branch may not: a broken
    promise stops the run, cannot be caught and cannot accumulate
  * declassify is refused without the effect declared, refused by the
    budget without the grant, and refused without a reason written in
    the call; with all three it works, and the audit records it
  * velaris.audit/1's secrets section reports the sources, whether the
    program declassifies, and each reason
  * the tracer and a broken promise print <secret>, not the value
  * and an honest program that uses a secret correctly still runs

Needs no theorem prover: every rule here is a type rule.

    python check_secret.py
"""
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"

sys.path.insert(0, str(HERE))
import velaris  # noqa: E402
from suite_dirs import isolate  # noqa: E402

# its own directory and proof cache, so two runs at once do not collide
SCRATCH = isolate("check_secret") / "_secret_check.vel"

PASS = [0]
FAIL = [0]


def ok(label: str, good: bool, detail: str = "") -> None:
    if good:
        PASS[0] += 1
        print(f"  ok    {label}")
    else:
        FAIL[0] += 1
        print(f"  WRONG {label}" + (f"\n          {detail}" if detail else ""))


def check(source: str) -> tuple:
    SCRATCH.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(VELARIS), "check", str(SCRATCH), "--no-cache"],
        capture_output=True, text=True, timeout=300, cwd=str(HERE))
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def run(source: str, allow: str) -> tuple:
    SCRATCH.write_text(source, encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(VELARIS), str(SCRATCH), "--allow", allow],
        capture_output=True, text=True, timeout=300, cwd=str(HERE))
    return done.returncode, (done.stdout or "") + (done.stderr or "")


def said(out: str) -> str:
    """What the program printed, without the compiler's notes about what
    is not installed - so a run without the prover compares the same."""
    return "\n".join(ln for ln in out.splitlines()
                     if not ln.startswith("note: ")).strip()


def refused(label: str, source: str, code: str, says=()) -> None:
    """This program must not compile, with this code, saying these."""
    got, out = check(source)
    missing = [s for s in says if s not in out]
    ok(label, got != 0 and code in out and not missing,
       f"expected {code}" + (f" saying {list(says)}" if says else "")
       + ", got: " + " | ".join(out.strip().splitlines()[:2]))


def compiles(label: str, source: str) -> None:
    """This program must compile."""
    got, out = check(source)
    ok(label, got == 0, out.strip()[:160])


def prints(label: str, source: str, allow: str, want: str) -> None:
    """This program must run and print exactly this."""
    got, out = run(source, allow)
    ok(label, got == 0 and said(out) == want,
       f"wanted {want!r}, got {said(out)!r}")


def audit_of(source: str) -> dict:
    SCRATCH.write_text(source, encoding="utf-8")
    return velaris.audit(source, path=str(SCRATCH)).as_dict()


# every case that starts from a key in the environment starts from this
KEY = 'fn main() uses io, env {\n    let key = env("API_KEY", "")\n'

print("SECRET")
print("-" * 62)
print("a Secret reaches nothing that emits it")
print("-" * 62)

# ---- 1. every builtin that emits refuses a Secret --------------------------
refused("a Secret cannot be printed",
        KEY + "    print(key)\n}\n", "E560",
        says=["Secret of Text", "env(), line 2", "print"])
refused("a Secret cannot be logged",
        KEY + "    log(key)\n}\n", "E560")
refused("a Secret cannot be written to a file",
        'fn main() uses io, env, fs {\n'
        '    write_file("out.txt", env("API_KEY", ""))\n}\n',
        "E560", says=["write_file", "fs"])
refused("a Secret cannot be the path read_file is given",
        'fn go() -> Text uses env, fs or fail {\n'
        '    return try read_file(env("API_KEY", ""))\n'
        '}\n\n'
        'fn main() uses io, env, fs {\n'
        '    check go() {\n'
        '        ok t {\n            print("read")\n        }\n'
        '        fail w {\n            print(w)\n        }\n'
        '    }\n}\n',
        "E560", says=["read_file"])
refused("a Secret cannot be the URL fetch is given",
        'fn go() -> Text uses env, net or fail {\n'
        '    return try fetch(env("API_KEY", ""))\n'
        '}\n\n'
        'fn main() uses io, env, net {\n'
        '    check go() {\n'
        '        ok t {\n            print("got")\n        }\n'
        '        fail w {\n            print(w)\n        }\n'
        '    }\n}\n',
        "E560", says=["fetch"])
refused("a Secret cannot be the body post is given",
        'fn go() -> Text uses env, net or fail {\n'
        '    return try post("https://example.com", env("API_KEY", ""))\n'
        '}\n\n'
        'fn main() uses io, env, net {\n'
        '    check go() {\n'
        '        ok t {\n            print("sent")\n        }\n'
        '        fail w {\n            print(w)\n        }\n'
        '    }\n}\n',
        "E560")
refused("a Secret cannot be passed to Python",
        'fn main() uses io, env, ffi {\n'
        '    check py("os", "getenv", [env("API_KEY", "")]) {\n'
        '        ok v {\n            print("called")\n        }\n'
        '        fail w {\n            print(w)\n        }\n'
        '    }\n}\n',
        "E560", says=["ffi"])
refused("a Secret cannot become an exit code",
        KEY + "    exit_with(length(key))\n}\n", "E560",
        says=["Secret of Int"])
refused("a Secret cannot be the name env() is asked for",
        'fn main() uses io, env {\n'
        '    let which = env("WHICH", "")\n'
        '    let value = env(which, "")\n'
        '    print("done")\n}\n',
        "E560", says=["env"])
refused("a Secret cannot be a failure's reason",
        'fn go() -> Int uses env or fail {\n'
        '    fail env("API_KEY", "")\n'
        '}\n\n'
        'fn main() uses io, env {\n'
        '    check go() {\n'
        '        ok n {\n            print(n)\n        }\n'
        '        fail w {\n            print(w)\n        }\n'
        '    }\n}\n',
        "E560", says=["reason"])

# ---- 2. nor any builtin that can fail --------------------------------------
# A failure's reason is text the program can print, and the runtime
# writes it out of the values it was given: to_int quotes the text it
# could not read. Nothing at run time knows which value was secret.
print()
print("nor anything that can fail, whose reason the runtime writes")
print("-" * 62)
refused("to_int refuses a Secret: its reason quotes what it was given",
        KEY + '    check to_int(key) {\n'
              '        ok n {\n            print("a number")\n        }\n'
              '        fail w {\n            print(w)\n        }\n'
              '    }\n}\n',
        "E560", says=["to_int", "can fail"])
refused("parse_money refuses one for the same reason",
        KEY + '    check parse_money(key, "INR") {\n'
              '        ok m {\n            print("ok")\n        }\n'
              '        fail w {\n            print(w)\n        }\n'
              '    }\n}\n',
        "E560", says=["parse_money"])
refused("json_get refuses one",
        KEY + '    check json_get(key, "a") {\n'
              '        ok v {\n            print("ok")\n        }\n'
              '        fail w {\n            print(w)\n        }\n'
              '    }\n}\n',
        "E560", says=["json_get"])
refused("add_or_fail refuses one",
        KEY + '    check add_or_fail(length(key), 1) {\n'
              '        ok v {\n            print("ok")\n        }\n'
              '        fail w {\n            print(w)\n        }\n'
              '    }\n}\n',
        "E560", says=["add_or_fail"])
refused("slice refuses a list that holds one",
        KEY + '    let xs = [key]\n'
              '    check slice(xs, 0, 1) {\n'
              '        ok ys {\n            print("ok")\n        }\n'
              '        fail w {\n            print(w)\n        }\n'
              '    }\n}\n',
        "E560", says=["slice"])

# ---- 3. a structure is not a way around it ---------------------------------
print()
print("nor does a structure carry one past the check")
print("-" * 62)
refused("a record holding a Secret cannot be printed",
        'record Call {\n    url: Text\n    auth: Secret of Text\n}\n\n'
        'fn main() uses io, env {\n'
        '    let c = Call(url: "https://example.com", '
        'auth: env("API_KEY", ""))\n'
        '    print(c)\n}\n',
        "E560", says=["is Call", "env(), line 7"])
refused("nor one that holds it only through another record",
        'record Inner {\n    auth: Secret of Text\n}\n\n'
        'record Outer {\n    name: Text\n    inner: Inner\n}\n\n'
        'fn main() uses io, env {\n'
        '    let o = Outer(name: "x", inner: Inner(auth: env("K", "")))\n'
        '    print(o)\n}\n',
        "E560", says=["is Outer"])
refused("a list of Secrets cannot be printed",
        KEY + "    print([key, key])\n}\n", "E560",
        says=["List of Secret of Text"])
refused("a map whose values are Secrets cannot be printed",
        KEY + '    print({"k": key})\n}\n', "E560",
        says=["Map of Text to Secret of Text"])
refused("a list of records that hold one cannot be printed",
        'record Call {\n    auth: Secret of Text\n}\n\n'
        'fn main() uses io, env {\n'
        '    print([Call(auth: env("API_KEY", ""))])\n}\n',
        "E560", says=["List of Call"])
refused("a field taken out of a record is still a Secret",
        'record Call {\n    auth: Secret of Text\n}\n\n'
        'fn main() uses io, env {\n'
        '    let c = Call(auth: env("API_KEY", ""))\n'
        '    print(c.auth)\n}\n',
        "E560", says=["Secret of Text"])

# ---- 4. it cannot be laundered ---------------------------------------------
print()
print("nor can it be laundered")
print("-" * 62)
refused("a Secret through two helpers is still a Secret",
        'fn one(s: Secret of Text) -> Secret of Text {\n'
        '    return s\n}\n\n'
        'fn two(s: Secret of Text) -> Secret of Text {\n'
        '    return one(s)\n}\n\n'
        'fn main() uses io, env {\n'
        '    print(two(env("API_KEY", "")))\n}\n',
        "E560", says=["env(), line 10"])
refused("a signature that does not say Secret cannot return one",
        'fn load() -> Text uses env {\n'
        '    return env("API_KEY", "")\n}\n\n'
        'fn main() uses io, env {\n    print(load())\n}\n',
        "E503", says=["Secret of Text"])
# A generic body is checked once, with its type variables standing for
# nothing in particular, so it may compare a T or hand one to to_text
# and give the answer back as an ordinary value. No type variable is
# ever bound to a type that carries a secret.
refused("no type variable is bound to a Secret: an effectful generic",
        'fn show(x: T) uses io for any T {\n    print(x)\n}\n\n'
        'fn main() uses io, env {\n'
        '    show(env("API_KEY", ""))\n}\n',
        "E560", says=["generic", "T could be a secret"])
refused("...nor a pure one, which would be an oracle: contains_item",
        'import "std.vel"\n\n'
        'fn main() uses io, env {\n'
        '    let key = env("API_KEY", "")\n'
        '    let guess = env("GUESS", "a")\n'
        '    print(contains_item([guess], key))\n}\n',
        "E560", says=["contains_item", "generic"])
refused("...nor index_of, which hands back a position",
        'import "std.vel"\n\n'
        'fn main() uses io, env {\n'
        '    let key = env("API_KEY", "")\n'
        '    let guess = env("GUESS", "a")\n'
        '    print(index_of([guess, key], key))\n}\n',
        "E560", says=["index_of"])
refused("...nor first, harmless as it looks",
        'import "std.vel"\n\n'
        'fn main() uses io, env {\n'
        '    let xs = [env("API_KEY", "")]\n'
        '    let head = first(xs)\n'
        '    print("took one")\n}\n',
        "E560", says=["first"])
compiles("a generic that says Secret in its signature is the way to write "
         "one",
         'fn pass(s: Secret of T) -> Secret of T for any T {\n'
         '    return s\n}\n\n'
         'fn main() uses io, env {\n'
         '    let k = env("K", "")\n'
         '    let same = pass(k)\n'
         '    print("held")\n}\n')
refused("to_text does not launder one",
        KEY + "    print(to_text(key))\n}\n", "E560")
refused("format does not launder one",
        KEY + '    print(format("key {}", key))\n}\n', "E560")
refused("json_of does not launder one",
        KEY + "    print(json_of(key))\n}\n", "E560")
refused("upper does not launder one",
        KEY + "    print(upper(key))\n}\n", "E560")
refused("joining text to one does not launder it",
        KEY + '    print("key: " + key)\n}\n', "E560")
refused("a Secret cannot be assigned into a plain variable",
        KEY + '    let plain = "x"\n    plain = key\n    print(plain)\n}\n',
        "E501", says=["Secret of Text"])
refused("a Secret cannot be pushed into a plain list",
        KEY + '    let xs = ["a"]\n    print(push(xs, key))\n}\n', "E501")
refused("a Secret of a Secret is not a type",
        'fn f(x: Secret of Secret of Text) -> Int {\n'
        '    return 1\n}\n\n'
        'fn main() uses io {\n    print(f(1))\n}\n',
        "E562")

# ---- 5. every pure operation keeps it, a comparison included ---------------
print()
print("every pure operation keeps it, a comparison included")
print("-" * 62)
refused("the length of a Secret is a Secret",
        KEY + "    print(length(key))\n}\n", "E560", says=["Secret of Int"])
refused("a comparison gives a Secret of Bool, not a Bool",
        KEY + '    let same = key == ""\n    print(same)\n}\n',
        "E560", says=["Secret of Bool"])
refused("...and so does comparing a Secret of Int with an Int",
        KEY + "    print(length(key) < 10)\n}\n",
        "E560", says=["Secret of Bool"])
refused("contains() over a Secret gives one too",
        KEY + '    print(contains(key, "a"))\n}\n',
        "E560", says=["Secret of Bool"])
refused("and-ing a Secret of Bool keeps it secret",
        'fn admin(flag: Secret of Bool) -> Secret of Bool {\n'
        '    return flag and true\n}\n\n'
        'fn main() uses io, env {\n'
        '    print(admin(env("A", "") == ""))\n}\n',
        "E560", says=["Secret of Bool"])

# What is about the container rather than about what it holds is not
# secret: how many secrets a list holds was decided by the pushes the
# program made, and a program cannot have made those depend on a
# secret - that would need a branch on one.
prints("the count of a list of secrets is an ordinary Int, so a program "
       "can walk one",
       'fn main() uses io, env {\n'
       '    let xs = [env("A", ""), env("B", "")]\n'
       '    let n = 0\n'
       '    for x in xs {\n'
       '        n = n + 1\n'
       '    }\n'
       '    print(format("{} of {}", n, length(xs)))\n}\n',
       "env,io", "2 of 2")
prints("...and whether a map holds a key is too",
       'fn main() uses io, env {\n'
       '    let m = {"a": env("A", "")}\n'
       '    if has(m, "a") {\n        print("present")\n    }\n}\n',
       "env,io", "present")

# ---- 6. and nothing branches on one ----------------------------------------
print()
print("and nothing branches on one (E563)")
print("-" * 62)
refused("an 'if' does not branch on a Secret of Bool",
        KEY + '    if key == "" {\n        print("not set")\n'
              '    } else {\n        print("set")\n    }\n}\n',
        "E563", says=["Secret of Bool", "env(), line 2"])
refused("nor on one a function declared",
        'fn admin(flag: Secret of Bool) -> Text {\n'
        '    if flag {\n        return "yes"\n    }\n'
        '    return "no"\n}\n\n'
        'fn main() uses io {\n    print("x")\n}\n',
        "E563", says=["Secret of Bool"])
refused("a 'while' does not either",
        KEY + '    let n = 0\n'
              '    while key == "" {\n        n = n + 1\n    }\n'
              '    print(n)\n}\n',
        "E563", says=["while"])

# This is why. With a plain Bool from ==, a comparison is not one bit:
# in a loop it reads the key out a character at a time, and the program
# prints what it read. The program below is that attack, and it is
# refused - at the branch, before the print.
ORACLE = (
    'fn main() uses io, env {\n'
    '    let key = env("API_KEY", "abc")\n'
    '    let alphabet = chars("abcdefghijklmnopqrstuvwxyz")\n'
    '    let found = ""\n'
    '    let at = 0\n'
    '    while at < 3 {\n'
    '        for c in alphabet {\n'
    '            if code_at(key, at) == code_at(c, 0) {\n'
    '                found = found + c\n'
    '            }\n'
    '        }\n'
    '        at = at + 1\n'
    '    }\n'
    '    print("recovered: " + found)\n}\n')
refused("the loop that would read a secret out character by character "
        "is refused, at the branch", ORACLE, "E563",
        says=["Secret of Bool"])

# The same program with the secret declassified first: it runs, it
# recovers the key, and the audit says it let the secret out and why.
# That is the trade the language offers - not silence, a statement.
EXTRACT = (
    'fn main() uses io, env, declassify {\n'
    '    let key = env("API_KEY", "abc")\n'
    '    let shown = declassify(key,\n'
    '    "this program exists to show what declassify costs")\n'
    '    let alphabet = chars("abcdefghijklmnopqrstuvwxyz")\n'
    '    let found = ""\n'
    '    let at = 0\n'
    '    while at < length(shown) {\n'
    '        for c in alphabet {\n'
    '            if code_at(shown, at) == code_at(c, 0) {\n'
    '                found = found + c\n'
    '            }\n'
    '        }\n'
    '        at = at + 1\n'
    '    }\n'
    '    print("recovered: " + found)\n}\n')
prints("...and with declassify the same program runs", EXTRACT,
       "declassify,env,io", "recovered: abc")
doc = audit_of(EXTRACT)
ok("...with the audit saying it let the secret out, and why",
   doc["secrets"]["declassifies"] is True
   and doc["secrets"]["declassifications"][0]["reason"]
   == "this program exists to show what declassify costs"
   and "declassify" in doc["effects"]
   and "declassify" in doc["safe_command"],
   str(doc["secrets"]))
code, out = run(EXTRACT, "env,io")
ok("...and an operator who withholds the grant stops it (E310)",
   code != 0 and "E310" in out and "recovered" not in said(out),
   said(out)[:140])

# A promise is not a branch: it cannot be caught, it stops the run, and
# it cannot accumulate - so a Secret of Bool is allowed in one.
compiles("a promise may be about a secret, where a branch may not",
         'fn hold(k: Secret of Text) -> Secret of Text\n'
         '    requires length(k) > 0\n'
         '{\n    return k\n}\n\n'
         'fn main() uses io {\n    print("x")\n}\n')

# ---- 7. declassify ---------------------------------------------------------
print()
print("declassify is the only way out, and says so three times")
print("-" * 62)
DECL = ('fn main() uses io, env, declassify {\n'
        '    let key = env("API_KEY", "none")\n'
        '    print(declassify(key, "REASON"))\n}\n')
refused("declassify without the effect declared is refused",
        DECL.replace("uses io, env, declassify", "uses io, env"),
        "E300", says=["declassify"])
refused("declassify needs a reason written in the call",
        'fn main() uses io, env, declassify {\n'
        '    let key = env("API_KEY", "none")\n'
        '    let why = "built while running"\n'
        '    print(declassify(key, why))\n}\n',
        "E561", says=["written as text"])
refused("declassify refuses an empty reason",
        DECL.replace("REASON", "   "), "E561", says=["empty"])
refused("declassify refuses something that is not a Secret",
        'fn main() uses io, declassify {\n'
        '    print(declassify("plain", "why"))\n}\n',
        "E561", says=["takes a Secret"])
refused("declassify refuses a record that merely holds one",
        'record Call {\n    auth: Secret of Text\n}\n\n'
        'fn main() uses io, env, declassify {\n'
        '    let c = Call(auth: env("API_KEY", ""))\n'
        '    print(declassify(c, "why"))\n}\n',
        "E561", says=["inside it"])
prints("declassify with the effect and the grant lets the value out",
       DECL, "declassify,env,io", "none")
code, out = run(DECL, "env,io")
ok("declassify without the grant is refused while running (E310)",
   code != 0 and "E310" in out and "none" not in said(out),
   said(out)[:140])
prints("what declassify gives back is an ordinary Text",
       'fn main() uses io, env, declassify {\n'
       '    let key = env("API_KEY", "abcd")\n'
       '    let plain = declassify(key, "this demo shows it")\n'
       '    print(upper(plain) + " " + length(plain))\n}\n',
       "declassify,env,io", "ABCD 4")
prints("...and a Secret of Bool declassifies into a branch",
       'fn main() uses io, env, declassify {\n'
       '    let key = env("API_KEY", "")\n'
       '    let empty = declassify(key == "",\n'
       '    "whether a key is set at all is not the key")\n'
       '    if empty {\n        print("not set")\n'
       '    } else {\n        print("set")\n    }\n}\n',
       "declassify,env,io", "not set")

# ---- 8. read_file_secret ---------------------------------------------------
print()
print("read_file_secret, the other source")
print("-" * 62)
refused("read_file_secret hands back a Secret",
        'fn main() uses io, fs {\n'
        '    check read_file_secret("nothing.txt") {\n'
        '        ok body {\n            print(body)\n        }\n'
        '        fail why {\n            print("could not read it")\n'
        '        }\n    }\n}\n',
        "E560", says=["read_file_secret(), line 2"])
prints("...and a program that keeps it runs",
       'fn main() uses io, fs {\n'
       '    check read_file_secret("nothing.txt") {\n'
       '        ok body {\n            print("read something")\n'
       '        }\n'
       '        fail why {\n            print("could not read it")\n'
       '        }\n    }\n}\n',
       "fs:read,io", "could not read it")

# ---- 9. what velaris.audit/1 says ------------------------------------------
print()
print("what velaris.audit/1 says about both (velaris-spec 8.6)")
print("-" * 62)
doc = audit_of(KEY + '    print("a key was read")\n}\n')
ok("the audit reports env as a source of secrets",
   doc["secrets"]["sources"] == ["env"], str(doc["secrets"]))
ok("...and says the program never declassifies",
   doc["secrets"]["declassifies"] is False
   and doc["secrets"]["declassifications"] == [], str(doc["secrets"]))
ok("...and declassify is not among its effects",
   "declassify" not in doc["effects"], str(doc["effects"]))

doc = audit_of(DECL)
ok("a program that declassifies says so in the audit",
   doc["secrets"]["declassifies"] is True, str(doc["secrets"]))
ok("...with the reason and the function it happened in",
   doc["secrets"]["declassifications"] == [
       {"reason": "REASON", "function": "main", "line": 3}],
   str(doc["secrets"]["declassifications"]))
ok("...and declassify is an effect, so a budget can refuse it",
   "declassify" in doc["effects"] and "declassify" in doc["safe_command"],
   str(doc["effects"]) + " " + doc["safe_command"])

doc = audit_of('fn main() uses io, fs, declassify {\n'
               '    check read_file_secret("k.txt") {\n'
               '        ok body {\n'
               '            print(declassify(body, "printed on purpose"))\n'
               '        }\n'
               '        fail why {\n            print(why)\n        }\n'
               '    }\n}\n')
ok("read_file_secret is reported as a source too",
   doc["secrets"]["sources"] == ["read_file_secret"], str(doc["secrets"]))
ok("...and a program with both sources reports both",
   audit_of('fn main() uses io, env, fs {\n'
            '    let a = env("A", "")\n'
            '    check read_file_secret("k.txt") {\n'
            '        ok body {\n            let both = a == body\n'
            '            print("read both")\n        }\n'
            '        fail why {\n            print(why)\n        }\n'
            '    }\n}\n')["secrets"]["sources"]
   == ["env", "read_file_secret"], "")
ok("a program with no secret at all reports none",
   audit_of("fn main() uses io {\n    print(1)\n}\n")["secrets"]
   == {"sources": [], "declassifies": False, "declassifications": []}, "")

bad = audit_of(KEY + "    print(key)\n}\n")
ok("a program refused for leaking one still names its source",
   bad["ok"] is False
   and any(p["code"] == "E560" for p in bad["problems"])
   and bad["secrets"]["sources"] == ["env"], str(bad["secrets"]))

doc = audit_of('fn a(k: Secret of Text) -> Text uses declassify {\n'
               '    return declassify(k, "first reason")\n}\n\n'
               'fn main() uses io, env, declassify {\n'
               '    let k = env("K", "")\n'
               '    print(a(k))\n'
               '    print(declassify(k, "second reason"))\n}\n')
ok("every declassification is listed, in its own function",
   [(d["function"], d["reason"]) for d in doc["secrets"]
    ["declassifications"]]
   == [("a", "first reason"), ("main", "second reason")],
   str(doc["secrets"]["declassifications"]))

# ---- 10. an honest program -------------------------------------------------
print()
print("and an honest program still runs")
print("-" * 62)
prints("a program that uses a secret correctly runs",
       'record Request {\n    url: Text\n    auth: Secret of Text\n}\n\n'
       'fn build(key: Secret of Text, url: Text) -> Request {\n'
       '    return Request(url: url, auth: "Bearer " + key)\n}\n\n'
       'fn main() uses io, env {\n'
       '    let key = env("API_KEY", "k")\n'
       '    let r = build(key, "https://example.com/v1")\n'
       '    print("GET " + r.url)\n'
       '    print("a key was attached, and is not in this output")\n}\n',
       "env,io",
       "GET https://example.com/v1\n"
       "a key was attached, and is not in this output")
code, out = run((HERE / "examples" / "secret.vel").read_text(
    encoding="utf-8"), "env,io")
ok("examples/secret.vel runs and prints no key",
   code == 0 and "authorization: Bearer <the key" in out, said(out)[:120])
code, out = run((HERE / "examples" / "secret_bad.vel").read_text(
    encoding="utf-8"), "env,io")
ok("examples/secret_bad.vel is refused with E560 naming env()",
   code != 0 and "E560" in out and "env(), line" in out, said(out)[:160])

# ---- 11. and nothing prints one behind the program's back ------------------
print()
print("and nothing prints one behind the program's back")
print("-" * 62)
SCRATCH.write_text(
    'fn keep(key: Secret of Text) -> Secret of Text {\n'
    '    return key\n}\n\n'
    'fn main() uses io, env {\n'
    '    let key = env("API_KEY", "sesame")\n'
    '    let held = keep(key)\n'
    '    print("held one")\n}\n', encoding="utf-8")
done = subprocess.run(
    [sys.executable, str(VELARIS), "trace", str(SCRATCH),
     "--allow", "env,io"],
    capture_output=True, text=True, timeout=300, cwd=str(HERE))
trace = (done.stdout or "") + (done.stderr or "")
ok("velaris trace prints <secret> in place of the value",
   "sesame" not in trace and "<secret>" in trace, trace.strip()[:200])

SCRATCH.write_text(
    'fn keep(key: Secret of Text) -> Secret of Text\n'
    '    requires length(key) > 99\n'
    '{\n    return key\n}\n\n'
    'fn main() uses io, env {\n'
    '    let key = env("API_KEY", "sesame")\n'
    '    let held = keep(key)\n'
    '    print("held one")\n}\n', encoding="utf-8")
done = subprocess.run(
    [sys.executable, str(VELARIS), str(SCRATCH), "--allow", "env,io"],
    capture_output=True, text=True, timeout=300, cwd=str(HERE))
broke = (done.stdout or "") + (done.stderr or "")
ok("a broken promise about a secret prints <secret>, not the value",
   done.returncode != 0 and "sesame" not in broke and "<secret>" in broke,
   broke.strip()[:200])

SCRATCH.unlink(missing_ok=True)
print("-" * 62)
print(f"{PASS[0]} right, {FAIL[0]} wrong")
sys.exit(1 if FAIL[0] else 0)
