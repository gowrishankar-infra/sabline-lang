"""sabline repl.
"""
import os

from .version import VERSION, _INSTALL_DIR
from .errors import SablineError
from .lexer import lex
from .nodes import ExprStmt, Function
from .parser import Parser
from .loader import load_program
from .values import FailSignal, ReturnSignal, to_text
from .effects import check_effects
from .checker import check_types
from .prover import check_proofs
from .runtime import build_runtime
from typing import Any


def repl() -> int:
    print(f"Sabline {VERSION} - interactive session.")
    print("Definitions (fn / record / import) are fully checked before "
          "joining;\nloose lines are checked while running. "
          "Type exit to leave.")
    sess_funcs: list[Function] = []
    sess_recs: list[Any] = []
    env: dict[Any, Any] = {}
    rt = build_runtime(sess_funcs)

    while True:
        try:
            line = input("sabline> ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.strip() in ("exit", "quit", ":q"):
            return 0
        if not line.strip():
            continue
        depth = line.count("{") - line.count("}")
        while depth > 0:
            try:
                more = input("   ...  ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            line += "\n" + more
            depth += more.count("{") - more.count("}")
        try:
            toks = lex(line)
        except SablineError as e:
            print(e.human("<repl>"))
            continue
        kind = toks[0].text if toks and toks[0].kind == "KEYWORD" else ""
        try:
            if kind in ("fn", "record", "import"):
                fs, rs, imps = Parser(toks).parse_program()
                for ipath, _ in imps:
                    if not os.path.exists(ipath):
                        shipped = os.path.join(
                            _INSTALL_DIR,
                            "stdlib", os.path.basename(ipath))
                        if os.path.exists(shipped):
                            ipath = shipped
                    ifuncs, irecs = load_program(ipath)
                    fs += ifuncs
                    rs += irecs
                cand_f = {f.name: f for f in sess_funcs}
                cand_r = {r.name: r for r in sess_recs}
                for f in fs:
                    if f.name in cand_f:
                        print(f"(replacing fn {f.name})")
                    cand_f[f.name] = f
                for r in rs:
                    if r.name in cand_r:
                        print(f"(replacing record {r.name})")
                    cand_r[r.name] = r
                new_f, new_r = list(cand_f.values()), list(cand_r.values())
                errs: list[Any] = []
                check_effects(new_f, errs)
                check_types(new_f, new_r, errs)
                if not errs:
                    check_proofs(new_f, new_r, errs)
                if errs:
                    for err in errs:
                        print(err.human("<repl>"))
                    print("(not accepted)")
                    continue
                sess_funcs[:] = new_f
                sess_recs[:] = new_r
                rt = build_runtime(list(sess_funcs))
                names = [f.name for f in fs] + [r.name for r in rs]
                print("defined: " + ", ".join(names))
            else:
                p = Parser(toks)
                stmts = []
                while p.peek().kind != "EOF":
                    stmts.append(p.parse_statement())
                for s in stmts:
                    if isinstance(s, ExprStmt):
                        v = rt["eval"](s.expr, env)
                        if v is not None:
                            print(to_text(v))
                    else:
                        rt["run"](s, env)
        except FailSignal as f:
            print("failed: " + to_text(f.reason))
        except ReturnSignal:
            print("('return' only works inside a function)")
        except SablineError as e:
            print(e.human("<repl>"))
        except RecursionError:
            print("(too much recursion)")
