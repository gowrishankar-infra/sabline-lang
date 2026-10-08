#!/usr/bin/env python3
"""Adversarial loops for the termination rule (SPEC.md section 9.5).

The rule claims `terminates` for exactly one shape: a counter that moves
one step toward a limit the body leaves alone. Every program here is
built to look like that shape while not being it - or to be it while
looking odd - and states the verdict each of its loops must get. A
wrong verdict is a bug in the analysis, never in this file.

Needs no theorem prover: the rule is syntactic, so this behaves
identically with and without z3.

    python check_termination.py                   the Python package
    python check_termination.py --runtime rust    sabline-rt (9.0, M2)

Every question here is the checkers', so under `--runtime rust` every
case is asked of sabline-rt and held to the same verdicts.
"""
import os
import subprocess
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sabline  # noqa: E402
import suite_runtime  # noqa: E402
from suite_dirs import isolate  # noqa: E402

RUNTIME = "python"

# its own directory, so two runs at once do not collide
WORK = str(isolate("check_termination"))

T, U = "terminates", "unshown"
# the third verdict (9.0; decisions/0006 section c, amended 2026-10-08)
B = "input-bounded"

# (name, verdicts of every loop in source order, program)
CASES = [
    ("counter up with <", [T], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(3)) }
'''),
    ("counter up with <=", [T], '''
fn f(n: Int) -> Int {
    let i = 0
    while i <= n {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(3)) }
'''),
    ("counter down with >", [T], '''
fn f(n: Int) -> Int {
    let i = n
    while i > 0 {
        i = i - 1
    }
    return i
}
fn main() uses io { print(f(3)) }
'''),
    ("a decrementing loop to 0 with >=", [T], '''
fn f(n: Int) -> Int {
    let i = n
    let turns = 0
    while i >= 0 {
        turns = turns + 1
        i = i - 1
    }
    return turns
}
fn main() uses io { print(f(3)) }
'''),
    ("counter stepping the wrong way (up, limit below)", [U], '''
fn f(n: Int) -> Int {
    let i = n
    while i > 0 {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(0)) }
'''),
    ("counter stepping the wrong way (down, limit above)", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i - 1
    }
    return i
}
fn main() uses io { print(f(0)) }
'''),
    ("counter stepping the wrong way with <=", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i <= n {
        i = i - 1
    }
    return i
}
fn main() uses io { print(f(-1)) }
'''),
    ("counter stepped by 2", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i + 2
    }
    return i
}
fn main() uses io { print(f(4)) }
'''),
    ("step written as 1 + i (not the recognised spelling)", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = 1 + i
    }
    return i
}
fn main() uses io { print(f(4)) }
'''),
    ("counter stepped twice on one path", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i + 1
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(4)) }
'''),
    ("counter reassigned inside an if on one path only", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        if i == 2 {
            i = i + 1
        }
    }
    return i
}
fn main() uses io { print(f(0)) }
'''),
    ("counter stepped on both arms of an if", [T], '''
fn f(n: Int) -> Int {
    let i = 0
    let odd = 0
    while i < n {
        if i % 2 == 1 {
            odd = odd + 1
            i = i + 1
        } else {
            i = i + 1
        }
    }
    return odd
}
fn main() uses io { print(f(5)) }
'''),
    ("counter stepped, then reset on one path", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i + 1
        if i == 3 {
            i = 0
        }
    }
    return i
}
fn main() uses io { print(f(2)) }
'''),
    ("counter copied to itself on one path", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < n {
        i = i + 1
        if i == n {
            i = i
        }
    }
    return i
}
fn main() uses io { print(f(2)) }
'''),
    ("limit that the body changes", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    let m = n
    while i < m {
        m = m - 1
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(4)) }
'''),
    ("limit changed only inside a nested if", [U], '''
fn f(n: Int, cut: Bool) -> Int {
    let i = 0
    let m = n
    while i < m {
        if cut {
            m = 0
        }
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(4, true)) }
'''),
    ("loop on length(xs) where xs is pushed to inside", [U], '''
fn f(xs: List of Int) -> Int {
    let i = 0
    let ys = xs
    while i < length(ys) {
        if length(ys) < 6 {
            ys = push(ys, i)
        }
        i = i + 1
    }
    return length(ys)
}
fn main() uses io { print(f([1, 2])) }
'''),
    ("loop on length(xs) where xs is left alone", [T], '''
fn f(xs: List of Int) -> Int {
    let i = 0
    let total = 0
    while i < length(xs) {
        total = total + get(xs, i)
        i = i + 1
    }
    return total
}
fn main() uses io { print(f([1, 2])) }
'''),
    ("a for loop over the result of a pure builtin (split)", [T], '''
fn f(line: Text) -> Int {
    let n = 0
    for part in split(line, " ") {
        if length(part) > 0 {
            n = n + 1
        }
    }
    return n
}
fn main() uses io { print(f("a b")) }
'''),
    ("limit is the length of a pure builtin's result", [T], '''
fn f(line: Text) -> Int {
    let i = 0
    while i < length(split(line, ",")) {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f("a,b")) }
'''),
    ("limit is a builtin that reads outside the program", [U], '''
fn f() -> Int uses io {
    let i = 0
    while i < length(args()) {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f()) }
'''),
    ("limit is a pure user function", [T], '''
fn size(xs: List of Int) -> Int {
    return length(xs)
}
fn f(xs: List of Int) -> Int {
    let i = 0
    while i < size(xs) {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f([1, 2])) }
'''),
    ("limit is a function with an effect", [U], '''
fn roll() -> Int uses rand {
    return random(3)
}
fn f() -> Int uses rand {
    let i = 0
    while i < roll() {
        i = i + 1
    }
    return i
}
fn main() uses io, rand { print(f()) }
'''),
    ("nested loops where only the inner qualifies", [U, T], '''
fn f(n: Int) -> Int {
    let done = false
    let count = 0
    while not done {
        let j = 0
        while j < n {
            count = count + 1
            j = j + 1
        }
        done = true
    }
    return count
}
fn main() uses io { print(f(3)) }
'''),
    ("nested loops where the inner moves the outer counter", [U, T], '''
fn f(n: Int) -> Int {
    let i = 0
    let count = 0
    while i < n {
        let j = 0
        while j < 2 {
            i = i + 1
            j = j + 1
        }
        count = count + 1
    }
    return count
}
fn main() uses io { print(f(4)) }
'''),
    ("nested loops that both qualify", [T, T], '''
fn f(n: Int) -> Int {
    let i = 0
    let count = 0
    while i < n {
        let j = 0
        while j < n {
            count = count + 1
            j = j + 1
        }
        i = i + 1
    }
    return count
}
fn main() uses io { print(f(3)) }
'''),
    ("a flag-only loop", [U], '''
fn f() -> Int {
    let done = false
    let turns = 0
    while not done {
        turns = turns + 1
        if turns == 3 {
            done = true
        }
    }
    return turns
}
fn main() uses io { print(f()) }
'''),
    ("a text comparison as the only condition", [U], '''
fn f() -> Int {
    let word = "go"
    let turns = 0
    while word != "stop" {
        turns = turns + 1
        if turns == 2 {
            word = "stop"
        }
    }
    return turns
}
fn main() uses io { print(f()) }
'''),
    ("an early exit via a flag AND a counter", [T], '''
fn f(xs: List of Int, wanted: Int) -> Int {
    let i = 0
    let found = false
    let at = -1
    while i < length(xs) and not found {
        if get(xs, i) == wanted {
            found = true
            at = i
        }
        i = i + 1
    }
    return at
}
fn main() uses io { print(f([4, 8], 8)) }
'''),
    ("a counter joined to a flag with or", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    let stop = false
    while i < n or not stop {
        i = i + 1
        stop = true
    }
    return i
}
fn main() uses io { print(f(1)) }
'''),
    ("a loop whose counter is a float", [U], '''
fn f() -> Float {
    let x = 0.0
    while x < 10.0 {
        x = x + 1.0
    }
    return x
}
fn main() uses io { print(f()) }
'''),
    ("the step inside a check block, on both arms", [T], '''
fn f(words: List of Text) -> Int {
    let i = 0
    let sum = 0
    while i < length(words) {
        check to_int(get(words, i)) {
            ok n {
                sum = sum + n
                i = i + 1
            }
            fail why {
                i = i + 1
            }
        }
    }
    return sum
}
fn main() uses io { print(f(["1", "x"])) }
'''),
    ("the step inside a check block, on the ok arm only", [U], '''
fn f(words: List of Text) -> Int {
    let i = 0
    let sum = 0
    while i < length(words) {
        check to_int(get(words, i)) {
            ok n {
                sum = sum + n
                i = i + 1
            }
            fail why {
                sum = sum
            }
        }
    }
    return sum
}
fn main() uses io { print(f(["1", "2"])) }
'''),
    ("a return on one path and a step on the other", [T], '''
fn f(xs: List of Int) -> Int {
    let i = 0
    while i < length(xs) {
        if get(xs, i) < 0 {
            return get(xs, i)
        }
        i = i + 1
    }
    return 0
}
fn main() uses io { print(f([3, -2])) }
'''),
    ("a return on one path and NO step on the other", [U], '''
fn f(xs: List of Int, n: Int) -> Int {
    let i = 0
    while i < n {
        if i < length(xs) {
            return get(xs, i)
        }
    }
    return 0
}
fn main() uses io { print(f([3], 1)) }
'''),
    ("the counter on the right-hand side of the comparison", [T], '''
fn f(limit: Int) -> Int {
    let i = 0
    while limit > i {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(3)) }
'''),
    ("two counters moving toward each other", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    let j = n
    while i < j {
        i = i + 1
        j = j - 1
    }
    return i
}
fn main() uses io { print(f(6)) }
'''),
    ("a counter compared against itself", [U], '''
fn f(n: Int) -> Int {
    let i = 0
    while i < i + 1 and i < n {
        i = i + 1
    }
    return i
}
fn main() uses io { print(f(2)) }
'''),
    ("while true", [U], '''
fn f() -> Int {
    let i = 0
    while true {
        i = i + 1
        if i == 3 {
            return i
        }
    }
    return i
}
fn main() uses io { print(f()) }
'''),
    ("a for loop over a range", [T], '''
fn f(n: Int) -> Int {
    let total = 0
    for i in 0 to n {
        total = total + i
    }
    return total
}
fn main() uses io { print(f(4)) }
'''),
    ("a for loop over a list that is pushed to inside", [U], '''
fn f(xs: List of Int) -> Int {
    let ys = xs
    for x in ys {
        if length(ys) < 5 {
            ys = push(ys, x)
        }
    }
    return length(ys)
}
fn main() uses io { print(f([1])) }
'''),
    ("a for loop whose body moves its own counter", [U], '''
fn f(n: Int) -> Int {
    let turns = 0
    for i in 0 to n {
        i = i + 1
        turns = turns + 1
    }
    return turns
}
fn main() uses io { print(f(6)) }
'''),
    ("a loop inside an inline function", [T], '''
import "std.vel"

fn main() uses io {
    let kept = keep_if([1, 2, 3], fn(n: Int) -> Bool {
        let i = 0
        while i < n {
            i = i + 1
        }
        return i > 1
    })
    print(length(kept))
}
'''),
    # ---- bounded by its input (9.0) -------------------------------------
    # read_line() answers "" at the end of input and on every call after
    # it, so a loop is bounded by its input only when it leaves on the
    # first empty read. Every near miss below is a loop that can run
    # forever once its input ends, and must stay unshown.
    ("18a: a flag cleared when the line read is empty", [B], '''
fn main() uses io {
    let count = 0
    let going = true
    while going {
        let line = read_line()
        if line == "" {
            going = false
        } else {
            count = count + 1
        }
    }
    print(count)
}
'''),
    ("THE COUNTEREXAMPLE: a flag cleared only when the line is \"x\"", [U], '''
fn main() uses io {
    let going = true
    while going {
        let line = read_line()
        if line == "x" {
            going = false
        }
    }
}
'''),
    ("07d: reads every turn, leaves only on \"quit\"", [U], '''
fn main() uses io {
    let line = ""
    let seen = 0
    while line != "quit" {
        line = read_line()
        seen = seen + 1
    }
    print(seen)
}
'''),
    ("18e: reads once before the loop, never inside it", [U], '''
fn main() uses io {
    let count = 0
    let line = read_line()
    while line != "" {
        count = count + 1
    }
    print(count)
}
'''),
    ("a read on one arm of an if only", [U], '''
fn main() uses io {
    let going = true
    let tick = 0
    while going {
        tick = tick + 2
        if tick > 4 {
            let line = read_line()
            if line == "" {
                going = false
            }
        }
    }
}
'''),
    ("the condition tests the line read: while line != \"\"", [B], '''
fn main() uses io {
    let count = 0
    let line = read_line()
    while line != "" {
        count = count + 1
        line = read_line()
    }
    print(count)
}
'''),
    ("...written \"\" != line", [B], '''
fn main() uses io {
    let line = read_line()
    while "" != line {
        line = read_line()
    }
}
'''),
    ("...written length(line) > 0", [B], '''
fn main() uses io {
    let line = read_line()
    while length(line) > 0 {
        line = read_line()
    }
}
'''),
    ("...written 0 < length(line)", [B], '''
fn main() uses io {
    let line = read_line()
    while 0 < length(line) {
        line = read_line()
    }
}
'''),
    ("...with another conjunct, which can only end it sooner", [B], '''
fn main() uses io {
    let ready = true
    let line = read_line()
    while line != "" and ready {
        line = read_line()
    }
}
'''),
    ("...with an or, which can keep it going", [U], '''
fn main() uses io {
    let more = true
    let line = read_line()
    while line != "" or more {
        line = read_line()
    }
}
'''),
    ("the flag cleared in the else arm of a not-empty test", [B], '''
fn main() uses io {
    let count = 0
    let going = true
    while going {
        let line = read_line()
        if length(line) != 0 {
            count = count + 1
        } else {
            going = false
        }
    }
    print(count)
}
'''),
    ("the flag cleared on length(line) == 0", [B], '''
fn main() uses io {
    let going = true
    while going {
        let line = read_line()
        if length(line) == 0 {
            going = false
        }
    }
}
'''),
    ("the flag set back to true later in the turn", [U], '''
fn main() uses io {
    let going = true
    while going {
        let line = read_line()
        if line == "" {
            going = false
        }
        going = true
    }
}
'''),
    ("the flag cleared somewhere else as well", [U], '''
fn main() uses io {
    let count = 0
    let going = true
    while going {
        let line = read_line()
        if line == "" {
            going = false
        }
        count = count + 1
        if count > 9 {
            going = false
        }
    }
}
'''),
    ("the flag cleared on one path of the empty arm only", [U], '''
fn main() uses io {
    let strict = false
    let going = true
    while going {
        let line = read_line()
        if line == "" {
            if strict {
                going = false
            }
        }
    }
}
'''),
    ("the line overwritten after it is read", [U], '''
fn main() uses io {
    let line = read_line()
    while line != "" {
        line = read_line()
        line = "more"
    }
}
'''),
    ("the empty test before the read, not after it", [U], '''
fn main() uses io {
    let going = true
    let line = "start"
    while going {
        if line == "" {
            going = false
        }
        line = read_line()
    }
}
'''),
    ("the test on a different text than the one read", [U], '''
fn main() uses io {
    let other = "x"
    let line = read_line()
    while other != "" {
        line = read_line()
    }
    print(line)
}
'''),
    ("a reader inside a counted loop: each gets its own verdict", [T, B], '''
fn main() uses io {
    let i = 0
    while i < 3 {
        let line = read_line()
        while line != "" {
            line = read_line()
        }
        i = i + 1
    }
}
'''),
    ("recursion instead of a loop", [], '''
fn count_down(n: Int) -> Int
    requires n >= 0
    ensures result >= 0
{
    if n == 0 {
        return 0
    }
    return count_down(n - 1)
}
fn main() uses io { print(count_down(3)) }
'''),
]


# `sabline check --strict` refuses a loop not shown to end (E612) and
# nothing else: a loop bounded by its input passes it (plan/9.0.md, M2's
# exit criteria). (name, passes --strict, program)
STRICT = [
    ("18a passes --strict: bounded by its input", True, CASES[[
        n for n, _, _ in CASES].index(
            "18a: a flag cleared when the line read is empty")][2]),
    ("the counterexample is E612 under --strict", False, CASES[[
        n for n, _, _ in CASES].index(
            "THE COUNTEREXAMPLE: a flag cleared only when the line is \"x\"")][2]),
    ("while line != \"\" passes --strict", True, CASES[[
        n for n, _, _ in CASES].index(
            "the condition tests the line read: while line != \"\"")][2]),
]


def passes_strict(source: str) -> bool:
    """Whether `check --strict` passes the program. Under --runtime rust,
    the half of --strict that is the checkers': no problem, and no loop of
    the program's own left unshown - which is all E612 reads."""
    path = os.path.join(WORK, "_termination_strict.vel")
    with open(path, "w", encoding="utf-8") as f:
        f.write(source.lstrip())
    try:
        if RUNTIME == "rust":
            document = suite_runtime.check_document(path)
            return not document["errors"] and not any(
                lp["verdict"] == "unshown"
                for lp in suite_runtime.own_loops(document, path))
        done = subprocess.run([sys.executable, os.path.join(HERE, "sabline.py"),
                               "check", path, "--strict"],
                              capture_output=True, text=True)
        if done.returncode != 0 and "E612" not in done.stdout + done.stderr:
            raise AssertionError(f"refused, but not with E612: {done.stdout}")
        return done.returncode == 0
    finally:
        os.unlink(path)


def verdicts_of(source: str) -> tuple[Any, ...]:
    """(verdicts in source order, errors) for a program."""
    path = os.path.join(WORK, "_termination_check.vel")
    with open(path, "w", encoding="utf-8") as f:
        f.write(source.lstrip())
    if RUNTIME == "rust":
        try:
            document = suite_runtime.check_document(path)
        finally:
            os.unlink(path)
        return ([lp["verdict"] for lp in suite_runtime.own_loops(document, path)],
                document["errors"])
    try:
        report = sabline.inspect_source(path, source.lstrip())
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    # only this program's loops: an import brings the library's own
    # functions into the report, and their loops are not under test
    own = os.path.abspath(path)
    loops = [lp for fn in report["functions"]
             if os.path.abspath(fn["file"]) == own
             for lp in fn.get("loops", [])]
    loops += [lp for lp in report.get("inline_loops", [])
              if os.path.abspath(lp["file"]) == own]
    loops.sort(key=lambda lp: lp["line"])
    return [lp["verdict"] for lp in loops], report["errors"]


def main(argv: list[str]) -> int:
    global RUNTIME
    RUNTIME = suite_runtime.chosen(argv)
    passed = failed = skipped = 0
    print(f"{len(CASES)} adversarial programs, "
          f"{sum(len(v) for _, v, _ in CASES)} loops, asked of "
          f"{'sabline-rt' if RUNTIME == 'rust' else 'the Python package'}")
    print("-" * 62)
    for name, want, source in CASES:
        try:
            got, errors = verdicts_of(source)
        except Exception as e:                # a crash is the worst answer
            print(f"  CRASH        {name}: {type(e).__name__}: {e}")
            failed += 1
            continue
        if errors:
            print(f"  DOES NOT COMPILE  {name}: "
                  f"[{errors[0]['code']}] {errors[0]['message'][:60]}")
            failed += 1
        elif got == want:
            print(f"  ok {', '.join(want) or 'no loops':<28} {name}")
            passed += 1
        else:
            print(f"  WRONG        {name}")
            print(f"               expected {want}, got {got}")
            failed += 1
    for name, passes, source in STRICT:
        if RUNTIME == "python" and not sabline.HAVE_Z3:
            # without the prover `check --strict` refuses every program, by
            # design, for the promises it cannot check (check_refusals.py
            # skips its --strict case for the same reason); sabline-rt's
            # half of --strict needs no prover and is asked either way
            print(f"  skip --strict                {name} (--strict needs "
                  f"the prover)")
            skipped += 1
            continue
        try:
            got = passes_strict(source)
        except Exception as e:
            print(f"  CRASH        {name}: {type(e).__name__}: {e}")
            failed += 1
            continue
        if got == passes:
            print(f"  ok {'--strict':<28} {name}")
            passed += 1
        else:
            print(f"  WRONG        {name}: --strict "
                  f"{'refused it' if passes else 'passed it'}")
            failed += 1
    print("-" * 62)
    print(f"{passed} right, {failed} wrong"
          + (f", {skipped} skipped" if skipped else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
