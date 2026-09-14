#!/usr/bin/env python3
"""Every wrong program must be refused, and for the right reason.

The example suite checks that bad programs are rejected. This checks
something stricter: that each one is rejected with the *specific* error
the language promises, so a guarantee cannot quietly degrade into a
different guarantee.

    python check_refusals.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"
sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

try:                       # proof-only refusals cannot be checked without
    import z3              # the prover: those programs simply run
    HAVE_Z3 = True
    del z3
except ImportError:
    HAVE_Z3 = False

CASES = [
    ("a promise that is false", "E700", True, '''
fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    return price - 10
}

fn main() uses io {
    print(discount(50))
}
'''),
    ("an effect that was not declared", "E300", False, '''
fn sneaky(price: Int) -> Int {
    print("leaking " + price)
    return price
}

fn main() uses io {
    print(sneaky(10))
}
'''),
    ("reaching the network without saying so", "E300", False, '''
fn quiet(url: Text) -> Text or fail {
    return try fetch(url)
}

fn main() uses io, net {
    print("hi")
}
'''),
    ("calling Python without the ffi effect", "E300", False, '''
fn quiet(x: Text) -> Text or fail {
    return try py("os", "getcwd", [x])
}

fn main() uses io {
    print("hi")
}
'''),
    ("ignoring a failure", "E520", False, '''
fn main() uses io {
    let answer = ask("a number:")
    print(to_int(answer) * 2)
}
'''),
    ("ignoring a map lookup that can fail", "E520", False, '''
fn main() uses io {
    let ages = {"a": 1}
    print(get(ages, "b"))
}
'''),
    ("dividing by something that can be zero", "E706", True, '''
fn share(total: Int, people: Int) -> Int
    requires people >= 0
{
    return total / people
}

fn main() uses io {
    print(share(10, 2))
}
'''),
    ("reading past the end of a list", "E705", True, '''
fn second(xs: List of Int) -> Int
    requires length(xs) >= 1
{
    return get(xs, 1)
}

fn main() uses io {
    print(second([1, 2]))
}
'''),
    ("breaking a promise about a record's list", "E700", True, '''
record Basket {
    owner: Text
    items: List of Int
}

fn add(b: Basket, price: Int) -> Basket
    ensures length(result.items) == length(b.items) + 2
{
    return Basket(owner: b.owner, items: push(b.items, price))
}

fn main() uses io {
    print(add(Basket(owner: "g", items: [1]), 2))
}
'''),
    ("breaking a promise about a map", "E700", True, '''
fn bump(m: Map of Text to Int, k: Text) -> Map of Text to Int
    ensures get_or(result, k, 0) == get_or(m, k, 0) + 2
{
    return put(m, k, get_or(m, k, 0) + 1)
}

fn main() uses io {
    print(get_or(bump({"a": 1}, "a"), "a", 0))
}
'''),
    ("a real-number identity that floats do not obey", "E700", True, '''
fn add_twice(x: Float) -> Float
    ensures result == x + 0.2
{
    return x + 0.1 + 0.1
}

fn main() uses io {
    print(add_twice(1.0))
}
'''),
    ("mixing whole numbers and decimals", "E501", False, '''
fn main() uses io {
    print(1 + 1.5)
}
'''),
    ("calling a library function that needs more", "E701", True, '''
import "std.vel"

fn main() uses io {
    let empty: List of Int = []
    print(max_of(empty))
}
'''),
    ("an inline function using a name that exists nowhere", "E402", False, '''
import "std.vel"

fn main() uses io {
    print(keep_if([1, 5], fn(n: Int) -> Bool { return n > nothing_here }))
}
'''),
    ("asking a namespace for something it lacks", "E200", False, '''
import "examples/lib/geo.vel" as geo

fn main() uses io {
    print(geo.area(3, 4))
}
'''),
    ("a local name colliding with an import", "E514", False, '''
import "std.vel" as std

fn main() uses io {
    let std = 5
    print(std)
}
'''),
    ("the wrong number of values for the text holes", "E406", False, '''
fn main() uses io {
    print(format("{} and {}", 1))
}
'''),
    ("a promise on an inline function that is false", "E700", True, '''
import "std.vel"

fn main() uses io {
    print(apply_to_each([1, 2], fn(n: Int) -> Int
        ensures result >= n
    {
        return n - 1
    }))
}
'''),
    ("a loop invariant that does not hold", "E703", True, '''
fn count(n: Int) -> Int
    requires n >= 0
{
    let i = 0
    while i < n
    invariant i > 0
    {
        i = i + 1
    }
    return i
}

fn main() uses io {
    print(count(3))
}
'''),
    ("returning the wrong type", "E503", False, '''
fn broken(x: Int) -> Int {
    return "text"
}

fn main() uses io {
    print(broken(1))
}
'''),
    ("printing a value that must not escape", "E560", False, '''
fn main() uses io, env {
    let key = env("API_KEY", "")
    print("the key is " + key)
}
'''),
    ("letting a secret out without saying why", "E561", False, '''
fn main() uses io, env, declassify {
    let key = env("API_KEY", "")
    let why = "made up while running"
    print(declassify(key, why))
}
'''),
    ("a Secret of a Secret", "E562", False, '''
fn hold(k: Secret of Secret of Text) -> Int {
    return 1
}

fn main() uses io {
    print(hold(1))
}
'''),
    ("branching on a value derived from a secret", "E563", False, '''
fn main() uses io, env {
    let key = env("API_KEY", "")
    if key == "" {
        print("not set")
    }
}
'''),
]

# refused only by `velaris check --strict`; the same programs run normally
STRICT_CASES = [
    ("a loop whose end cannot be shown", "E612", True, '''
fn by_twos(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i + 2
    }
    return i
}

fn main() uses io {
    print(by_twos(7))
}
'''),
]


def main() -> int:
    # its own directory and proof cache, so two runs at once do not collide.
    # One case imports examples/lib/geo.vel relative to itself, so that
    # library is copied to the same place beside the scratch file.
    work = isolate("check_refusals")
    shutil.copytree(HERE / "examples" / "lib", work / "examples" / "lib")
    skipped = 0
    passed = failed = 0
    print(f"{len(CASES)} programs that must be refused")
    print("-" * 62)
    for name, want, needs_prover, source in CASES:
        if needs_prover and not HAVE_Z3:
            print("  skip %-5s    %s (needs the prover)" % (want, name))
            skipped += 1
            continue
        path = work / "_refusal_check.vel"
        path.write_text(source.lstrip(), encoding="utf-8")
        run = subprocess.run(
            [sys.executable, str(VELARIS), str(path), "--no-cache"],
            capture_output=True, text=True, timeout=300, cwd=HERE)
        output = (run.stderr or "") + (run.stdout or "")
        if run.returncode == 0:
            print(f"  NOT REFUSED  {name}")
            print(f"               expected {want}, the program ran")
            failed += 1
        elif want in output:
            print(f"  ok {want:<5}    {name}")
            passed += 1
        else:
            first = next((ln for ln in output.splitlines()
                          if "error[" in ln), output.strip()[:70])
            print(f"  WRONG REASON {name}")
            print(f"               expected {want}, got: {first[:90]}")
            failed += 1
        path.unlink(missing_ok=True)
    for name, want, needs_prover, source in STRICT_CASES:
        if needs_prover and not HAVE_Z3:
            print("  skip %-5s    %s (--strict needs the prover)"
                  % (want, name))
            skipped += 1
            continue
        path = work / "_refusal_check.vel"
        path.write_text(source.lstrip(), encoding="utf-8")
        plain = subprocess.run(
            [sys.executable, str(VELARIS), str(path), "--no-cache"],
            capture_output=True, text=True, timeout=300, cwd=HERE)
        run = subprocess.run(
            [sys.executable, str(VELARIS), "check", str(path), "--strict"],
            capture_output=True, text=True, timeout=300, cwd=HERE)
        output = (run.stderr or "") + (run.stdout or "")
        if plain.returncode != 0:
            print(f"  WRONG        {name}: refused WITHOUT --strict too")
            failed += 1
        elif run.returncode == 0:
            print(f"  NOT REFUSED  {name} (under --strict)")
            failed += 1
        elif want in output:
            print(f"  ok {want:<5}    {name} (--strict only)")
            passed += 1
        else:
            print(f"  WRONG REASON {name}: expected {want}, got: "
                  f"{output.strip()[:90]}")
            failed += 1
        path.unlink(missing_ok=True)
    print("-" * 62)
    note = f", {skipped} skipped (no prover installed)" if skipped else ""
    print(f"{passed} refused correctly, {failed} not{note}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
