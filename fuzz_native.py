#!/usr/bin/env python3
"""Generate random Velaris programs; demand that both engines agree.

Native compilation is only allowed to be faster, never different. This
builds random pure functions over Ints, Floats, lists and text, runs
each program interpreted and natively, and fails loudly on any
disagreement - including a crash on one side only.

    python fuzz_native.py            # 200 programs
    python fuzz_native.py 1000       # more
    python fuzz_native.py 200 --seed 7
"""
import random
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
VELARIS = HERE / "velaris.py"
sys.path.insert(0, str(HERE))
from suite_dirs import isolate  # noqa: E402

# its own directory and proof cache: two runs at once, each with its own
# random seed, must not run each other's program
WORK = isolate("fuzz_native")


def rnd_int(r):
    return str(r.randint(-40, 40))


def expr(r, vars_int, depth=0):
    """A random Int expression over the given variables."""
    choices = ["num", "var", "add", "sub", "mul", "cmp", "call_len"]
    if depth > 2:
        choices = ["num", "var"]
    pick = r.choice(choices)
    if pick == "num" or not vars_int:
        return rnd_int(r)
    if pick == "var":
        return r.choice(vars_int)
    if pick == "cmp":
        a, b = expr(r, vars_int, depth + 1), expr(r, vars_int, depth + 1)
        return f"({a} {r.choice(['+', '-'])} {b})"
    if pick == "call_len":
        return rnd_int(r)
    a, b = expr(r, vars_int, depth + 1), expr(r, vars_int, depth + 1)
    op = {"add": "+", "sub": "-", "mul": "*"}[pick]
    return f"({a} {op} {b})"


def gen_program(r) -> str:
    """One random program: a pure function plus a main that prints it."""
    shape = r.choice(["ints", "loop", "list", "text", "float", "branch"])
    if shape == "ints":
        body = f"    return {expr(r, ['a', 'b'])}\n"
        sig = "fn f(a: Int, b: Int) -> Int"
        call = f"f({rnd_int(r)}, {rnd_int(r)})"
    elif shape == "branch":
        body = (f"    if a > b {{\n        return {expr(r, ['a', 'b'])}\n"
                f"    }}\n    return {expr(r, ['a', 'b'])}\n")
        sig = "fn f(a: Int, b: Int) -> Int"
        call = f"f({rnd_int(r)}, {rnd_int(r)})"
    elif shape == "loop":
        body = ("    let total = 0\n    let i = 0\n"
                f"    while i < n {{\n"
                f"        total = total + {expr(r, ['i', 'total'])}\n"
                "        i = i + 1\n    }\n    return total\n")
        sig = "fn f(n: Int) -> Int"
        call = f"f({r.randint(0, 12)})"
    elif shape == "list":
        body = ("    let total = 0\n    let i = 0\n"
                "    while i < length(xs) {\n"
                f"        total = total + get(xs, i) * {r.randint(1, 4)}\n"
                "        i = i + 1\n    }\n    return total\n")
        sig = "fn f(xs: List of Int) -> Int"
        items = ", ".join(rnd_int(r) for _ in range(r.randint(1, 6)))
        call = f"f([{items}])"
    elif shape == "text":
        body = ("    let n = 0\n    let i = 0\n"
                "    while i < length(t) {\n"
                f"        if code_at(t, i) > {r.randint(60, 110)} {{\n"
                "            n = n + 1\n        }\n"
                "        i = i + 1\n    }\n    return n\n")
        sig = "fn f(t: Text) -> Int"
        word = "".join(r.choice("abcXYZ 09é漢") for _ in range(r.randint(0, 12)))
        call = f'f("{word}")'
    else:                                   # float
        body = (f"    return x * {r.randint(1, 5)}.5 + {r.randint(0, 9)}.25\n")
        sig = "fn f(x: Float) -> Float"
        call = f"f({r.randint(-20, 20)}.{r.randint(0, 99)})"
    return f"{sig} {{\n{body}}}\n\nfn main() uses io {{\n    print({call})\n}}\n"


def run(path, native: bool):
    args = [sys.executable, str(VELARIS), str(path)]
    if not native:
        args.append("--no-native")
    p = subprocess.run(args, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


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
    bad = 0
    for k in range(n):
        src = gen_program(r)
        tmp.write_text(src, encoding="utf-8")
        rc_n, out_n, err_n = run(tmp, True)
        rc_i, out_i, err_i = run(tmp, False)
        if (rc_n, out_n) != (rc_i, out_i):
            bad += 1
            print("\nDISAGREEMENT between native and interpreted:")
            print(src)
            print(f"  native      exit {rc_n}: {out_n!r}  {err_n[:200]}")
            print(f"  interpreted exit {rc_i}: {out_i!r}  {err_i[:200]}")
            if bad >= 3:
                break
        if (k + 1) % 25 == 0:
            print(f"  {k + 1}/{n} agree")
    tmp.unlink(missing_ok=True)
    if bad:
        print(f"\n{bad} disagreement(s) - this is a bug, not a preference")
        return 1
    print(f"\nall {n} programs: native and interpreted agree exactly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
