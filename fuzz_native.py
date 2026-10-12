#!/usr/bin/env python3
"""Generate random Sabline programs; demand that both engines agree.

Native compilation is only allowed to be faster, never different. This
builds random pure functions over Ints, Floats, lists and text, runs
each program interpreted and natively, and fails loudly on any
disagreement - in the exit status, in stdout, or in stderr, which is
where a run's coded error is: its code, its words, its line and its
fixes. Some programs are made to stop - a number past 64 bits, a read
outside a list or a text, a loop that only a stop ends, a call the left
side of an `and` exists to guard - because that is where two engines
differ when they differ (9.0: until then the native engine named
neither the operator nor the read, at the function's line, did not
short-circuit `and`, and looped forever where the interpreter stopped,
and this compared stdout alone).

    python fuzz_native.py            # 200 programs
    python fuzz_native.py 1000       # more
    python fuzz_native.py 200 --seed 7
"""
import random
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
SABLINE = HERE / "sabline.py"
sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

# its own directory: two runs at once, each with its own random seed, must
# not run each other's program
WORK = isolate("fuzz_native")

# what a run says on stderr that is not about the program: the native run
# on a machine with no llvmlite says so, and then runs interpreted
NOT_THE_PROGRAM = ("note: llvmlite is not installed",)


def rnd_int(r: Any) -> str:
    return str(r.randint(-40, 40))


def big_int(r: Any) -> str:
    """A whole number near the edge of 64 bits, either sign."""
    n = r.choice([2 ** 31 + r.randint(0, 99), 2 ** 62 + r.randint(0, 99),
                  2 ** 63 - 1 - r.randint(0, 99), 3037000500])
    return str(n if r.random() < 0.7 else -n)


def expr(r: Any, vars_int: Any, depth: int = 0, big: bool = False) -> Any:
    """A random Int expression over the given variables."""
    choices = ["num", "var", "add", "sub", "mul", "cmp", "call_len"]
    if depth > 2:
        choices = ["num", "var"]
    pick = r.choice(choices)
    if pick == "num" or not vars_int:
        return big_int(r) if big and r.random() < 0.4 else rnd_int(r)
    if pick == "var":
        return r.choice(vars_int)
    if pick == "cmp":
        a = expr(r, vars_int, depth + 1, big)
        b = expr(r, vars_int, depth + 1, big)
        return f"({a} {r.choice(['+', '-'])} {b})"
    if pick == "call_len":
        return rnd_int(r)
    a, b = expr(r, vars_int, depth + 1, big), expr(r, vars_int, depth + 1, big)
    op = {"add": "+", "sub": "-", "mul": "*"}[pick]
    return f"({a} {op} {b})"


def gen_program(r: Any) -> str:
    """One random program: a pure function plus a main that prints it."""
    shape = r.choice(["ints", "loop", "list", "text", "float", "branch",
                      "overflow", "doubling", "list_out", "text_out",
                      "nested", "guarded", "negate"])
    helper = ""
    if shape == "ints":
        body = f"    return {expr(r, ['a', 'b'])}\n"
        sig = "fn f(a: Int, b: Int) -> Int"
        call = f"f({rnd_int(r)}, {rnd_int(r)})"
    elif shape == "branch":
        body = (f"    if a > b {{\n        return {expr(r, ['a', 'b'])}\n"
                f"    }}\n    return {expr(r, ['a', 'b'])}\n")
        sig = "fn f(a: Int, b: Int) -> Int"
        call = f"f({rnd_int(r)}, {rnd_int(r)})"
    elif shape == "overflow":
        # past 64 bits or not, by chance: E407 names the operator and the
        # line where it happened, in both
        body = (f"    let c = {expr(r, ['a', 'b'], big=True)}\n"
                f"    return {expr(r, ['a', 'b', 'c'], big=True)}\n")
        sig = "fn f(a: Int, b: Int) -> Int"
        call = f"f({big_int(r)}, {rnd_int(r)})"
    elif shape == "doubling":
        # a loop only E407 ends: wrapped, the number would reach 0 and stay
        # there, and native code that kept going would never stop
        body = ("    let i = a\n    while i != 7 {\n"
                f"        i = i * {r.choice([2, 3, -2, 10])}\n"
                "    }\n    return i\n")
        sig = "fn f(a: Int) -> Int"
        call = f"f({r.randint(1, 5)})"
    elif shape == "loop":
        body = ("    let total = 0\n    let i = 0\n"
                f"    while i < n {{\n"
                f"        total = total + {expr(r, ['i', 'total'])}\n"
                "        i = i + 1\n    }\n    return total\n")
        sig = "fn f(n: Int) -> Int"
        call = f"f({r.randint(0, 12)})"
    elif shape in ("list", "list_out"):
        bound = "length(xs)" if shape == "list" else "k"
        body = ("    let total = 0\n    let i = 0\n"
                f"    while i < {bound} {{\n"
                f"        total = total + get(xs, i) * {r.randint(1, 4)}\n"
                "        i = i + 1\n    }\n    return total\n")
        sig = ("fn f(xs: List of Int) -> Int" if shape == "list"
               else "fn f(xs: List of Int, k: Int) -> Int")
        n = r.randint(1, 6)
        items = ", ".join(rnd_int(r) for _ in range(n))
        call = (f"f([{items}])" if shape == "list"
                else f"f([{items}], {n + r.randint(-1, 3)})")
    elif shape in ("text", "text_out"):
        bound = "length(t)" if shape == "text" else "k"
        body = ("    let n = 0\n    let i = 0\n"
                f"    while i < {bound} {{\n"
                f"        if code_at(t, i) > {r.randint(60, 110)} {{\n"
                "            n = n + 1\n        }\n"
                "        i = i + 1\n    }\n    return n\n")
        sig = ("fn f(t: Text) -> Int" if shape == "text"
               else "fn f(t: Text, k: Int) -> Int")
        word = "".join(r.choice("abcXYZ 09é漢") for _ in range(r.randint(0, 12)))
        call = (f'f("{word}")' if shape == "text"
                else f'f("{word}", {len(word) + r.randint(-1, 3)})')
    elif shape == "nested":
        # one native function stopping inside another: the interpreter
        # says where, in the callee
        helper = (f"fn g(a: Int, b: Int) -> Int {{\n"
                  f"    return {expr(r, ['a', 'b'], big=True)}\n}}\n\n")
        body = (f"    let x = g(a, {rnd_int(r)})\n"
                f"    return g(x, {big_int(r)}) + 1\n")
        sig = "fn f(a: Int) -> Int"
        call = f"f({big_int(r) if r.random() < 0.5 else rnd_int(r)})"
    elif shape == "guarded":
        # the right side of `and`/`or` runs only when the left side does
        # not decide it - here it would stop the run if it ran
        helper = ("fn g(a: Int) -> Int {\n"
                  "    return a * 4611686018427387904\n}\n\n")
        op, test = r.choice([("and", "a < 0"), ("or", "a > 0")])
        body = (f"    if {test} {op} g(a) > 0 {{\n        return 1\n    }}\n"
                "    return 2\n")
        sig = "fn f(a: Int) -> Int"
        call = f"f({r.choice([-3, 0, 3])})"
    elif shape == "negate":
        # minus the smallest whole number is E407, at the '-'
        body = ("    let m = -9223372036854775807 - a\n"
                "    return -m\n")
        sig = "fn f(a: Int) -> Int"
        call = f"f({r.choice([0, 1, 2])})"
    else:                                   # float
        body = (f"    return x * {r.randint(1, 5)}.5 + {r.randint(0, 9)}.25\n")
        sig = "fn f(x: Float) -> Float"
        call = f"f({r.randint(-20, 20)}.{r.randint(0, 99)})"
    return (f"{helper}{sig} {{\n{body}}}\n\nfn main() uses io {{\n"
            f"    print({call})\n}}\n")


def run(path: Any, native: bool) -> tuple[Any, ...]:
    args = [sys.executable, str(SABLINE), str(path)]
    if not native:
        args.append("--no-native")
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60,
                           stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return "did not stop in 60 seconds", "", ""
    err = "\n".join(line for line in p.stderr.strip().splitlines()
                    if not line.startswith(NOT_THE_PROGRAM))
    return p.returncode, p.stdout.strip(), err


def main() -> int:
    n = 200
    seed = random.randrange(1 << 30)
    argv = sys.argv[1:]
    if argv and argv[0].isdigit():
        n = int(argv[0])
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])
    r = random.Random(seed)
    print(f"fuzzing {n} programs (seed {seed})")
    tmp = WORK / "_fuzz.vel"
    bad = stopped = 0
    for k in range(n):
        src = gen_program(r)
        tmp.write_text(src, encoding="utf-8")
        native = run(tmp, True)
        interpreted = run(tmp, False)
        if "error[" in interpreted[2]:
            stopped += 1
        if native != interpreted:
            bad += 1
            print("\nDISAGREEMENT between native and interpreted:")
            print(src)
            for name, (rc, out, err) in (("native", native),
                                         ("interpreted", interpreted)):
                print(f"  {name:<12}exit {rc}: {out!r}")
                for line in err.splitlines()[:6]:
                    print(f"  {'':<12}{line}")
            if bad >= 3:
                break
        if (k + 1) % 25 == 0:
            print(f"  {k + 1}/{n} agree")
    tmp.unlink(missing_ok=True)
    if bad:
        print(f"\n{bad} disagreement(s) - this is a bug, not a preference")
        return 1
    print(f"\nall {n} programs: native and interpreted agree exactly - exit "
          f"status, stdout and stderr; {stopped} of them stopped with a "
          f"coded error")
    return 0


if __name__ == "__main__":
    sys.exit(main())
