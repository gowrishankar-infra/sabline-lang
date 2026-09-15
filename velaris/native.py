"""Stage 7, native code: pure functions compiled to machine code with llvmlite.
"""
import sys

from . import state as _state
from .errors import VelarisError
from .nodes import (
    Assign,
    BinOp,
    Bool,
    Call,
    ExprStmt,
    FloatNum,
    Function,
    If,
    Let,
    Neg,
    Not,
    Num,
    Return,
    Str,
    Var,
    While,
)
from .tables import INT_MAX, INT_MIN, builtin_reached
from typing import Any, cast

# ---------------------------------------------------------------------------
# 4d. NATIVE COMPILER (v0.9) — compile pure Int functions to machine code
#     via LLVM. Eligible: params and return are Int; body uses only math,
#     comparisons, and/or/not, if, while, let/assign, and calls to other
#     eligible functions. No effects; contracts are allowed once PROVEN
#     (an unproven promise still needs its runtime check); no '/';
#     lists and text may be READ (bounds-guarded), not built.
# ---------------------------------------------------------------------------


def native_eligible(funcs: list[Function],
                    proven: set[str] | frozenset[str] = frozenset()) -> set[str]:
    table = {f.name: f for f in funcs}

    def locally_ok(fn: Function) -> Any:
        if fn.effects or fn.can_fail or fn.type_vars:
            return None
        if (fn.requires or fn.ensures) and fn.name not in proven:
            return None       # unproven promises still need runtime checks
        if fn.return_type not in ("Int", "Float", "Bool"):
            return None      # text results stay interpreted: returning a
                             # struct by value is platform-specific ABI
        if any(pt not in ("Int", "Float", "Bool", "List of Int", "Text")
               for _, pt in fn.params):
            return None
        list_params = {p for p, t in fn.params if t == "List of Int"}
        text_params = {p for p, t in fn.params if t == "Text"}
        calls, ok = set(), [True]
        local_text = set(text_params)

        def text_valued(e: Any) -> bool:
            if isinstance(e, Str):
                return True
            if isinstance(e, Var):
                return e.name in local_text
            if isinstance(e, Call):
                callee = table.get(e.name)
                return callee is not None and callee.return_type == "Text"
            if isinstance(e, BinOp) and e.op == "+":
                return text_valued(e.left)
            return False

        def note_text(stmts: Any) -> None:           # locals that hold text
            for s in stmts:
                if isinstance(s, (Let, Assign)) and text_valued(s.value):
                    local_text.add(s.name)
                elif isinstance(s, If):
                    note_text(s.then)
                    note_text(s.other)
                elif isinstance(s, While):
                    note_text(s.body)
        note_text(fn.body)
        note_text(fn.body)              # twice: assignments after use

        def we(e: Any) -> None:
            if isinstance(e, Str):
                return                  # text literals are compiled in
            if isinstance(e, (Num, FloatNum, Bool, Var)):
                return
            if (isinstance(e, Call) and e.name in ("length", "get")
                    and e.args and isinstance(e.args[0], Var)
                    and e.args[0].name in list_params):
                for a in e.args[1:]:
                    we(a)
                return
            if (isinstance(e, Call) and e.name in ("length", "code_at")
                    and e.args and text_valued(e.args[0])):
                we(e.args[0])
                for a in e.args[1:]:
                    we(a)
                return
            if isinstance(e, (Not, Neg)):
                we(e.value)
            elif isinstance(e, BinOp):
                if e.op in ("/", "%"):
                    ok[0] = False       # backend semantics differ on negatives
                else:
                    we(e.left)
                    we(e.right)
            elif isinstance(e, Call):
                if builtin_reached(e.name, table) is not None \
                        or e.name not in table:
                    ok[0] = False
                else:
                    calls.add(e.name)
                    for a in e.args:
                        we(a)
            else:
                ok[0] = False          # Str, ListLit

        def ws(s: Any) -> None:
            if isinstance(s, (Let, Assign)):
                we(s.value)
            elif isinstance(s, Return):
                if s.value is None:
                    ok[0] = False
                else:
                    we(s.value)
            elif isinstance(s, If):
                we(s.cond)
                for x in s.then + s.other:
                    ws(x)
            elif isinstance(s, While):
                if s.invariants:
                    ok[0] = False      # invariant checks must not be skipped
                we(s.cond)
                for x in s.body:
                    ws(x)
            elif isinstance(s, ExprStmt):
                we(s.expr)
            else:
                ok[0] = False

        for s in fn.body:
            ws(s)
        return calls if ok[0] else None

    cand = {}
    for f in funcs:
        c = locally_ok(f)
        if c is not None:
            cand[f.name] = c
    changed = True
    while changed:                      # drop anyone calling a non-candidate
        changed = False
        for name in list(cand):
            if not cand[name] <= set(cand):
                del cand[name]
                changed = True
    # A directly or mutually recursive function is NOT compiled to native
    # (7.1.2): the interpreter's E609 depth guard (call_function) has no
    # equivalent in native code, so a recursion that never bottoms out would
    # loop unbounded in native code instead of stopping. Interpreting it
    # keeps E609. Find every function that can reach itself through the
    # call graph and drop it, then drop anyone left calling a dropped one.
    reach = {n: set(cand[n] & set(cand)) for n in cand}
    grew = True
    while grew:
        grew = False
        for n in reach:
            add = set().union(*(reach[m] for m in reach[n])) if reach[n] \
                else set()
            if not add <= reach[n]:
                reach[n] |= add
                grew = True
    for n in [n for n in cand if n in reach[n]]:
        del cand[n]
    changed = True
    while changed:
        changed = False
        for name in list(cand):
            if not cand[name] <= set(cand):
                del cand[name]
                changed = True
    return set(cand)


def compile_native(funcs: list[Function],
                   proven: set[str] | frozenset[str] = frozenset()) -> dict[Any, Any]:
    """Native code is an optimisation, never a requirement: if anything
    about this machine's backend disagrees with us, the program runs
    interpreted and behaves exactly the same, just slower."""
    try:
        return _compile_native(funcs, proven)
    except Exception:
        return {}


def _compile_native(funcs: list[Function],
                    proven: set[str] | frozenset[str] = frozenset()) -> dict[Any, Any]:
    eligible = native_eligible(funcs, proven)
    if not eligible:
        return {}
    try:
        from llvmlite import ir, binding
    except ImportError:
        print("note: llvmlite is not installed - running fully interpreted "
              "(for native speed: pip install llvmlite)", file=sys.stderr)
        return {}

    i64 = ir.IntType(64)
    f64 = ir.DoubleType()
    i64p = ir.PointerType(i64)
    i32 = ir.IntType(32)
    i32p = ir.PointerType(i32)
    TEXT = ir.LiteralStructType([i32p, i64])
    LTY = {"Int": i64, "Bool": i64, "Float": f64, "Text": TEXT}


    def llvm_params(fn: Any) -> Any:
        out = []
        for _, pt in fn.params:
            if pt == "List of Int":
                out += [i64p, i64]        # data pointer, then length
            elif pt == "Text":
                out += [i32p, i64]        # code points, then length
            else:
                out.append(LTY[pt])
        return out
    module = ir.Module(name="velaris")
    oob = ir.GlobalVariable(module, i64, name="velaris_oob")
    oob.initializer = i64(0)
    oob_idx = ir.GlobalVariable(module, i64, name="velaris_oob_idx")
    oob_idx.initializer = i64(0)
    oob_len = ir.GlobalVariable(module, i64, name="velaris_oob_len")
    oob_len.initializer = i64(0)
    arena = ir.GlobalVariable(module, i32p, name="velaris_arena")
    arena.initializer = ir.Constant(i32p, None)
    arena_cap = ir.GlobalVariable(module, i64, name="velaris_arena_cap")
    arena_cap.initializer = i64(0)
    arena_used = ir.GlobalVariable(module, i64, name="velaris_arena_used")
    arena_used.initializer = i64(0)
    arena_full = ir.GlobalVariable(module, i64, name="velaris_arena_full")
    arena_full.initializer = i64(0)
    overflowed = ir.GlobalVariable(module, i64, name="velaris_overflow")
    overflowed.initializer = i64(0)
    ovf_fns = {}
    for op_name in ("sadd", "ssub", "smul"):
        fty = ir.FunctionType(
            ir.LiteralStructType([i64, ir.IntType(1)]), [i64, i64])
        ovf_fns[op_name] = ir.Function(
            module, fty, name=f"llvm.{op_name}.with.overflow.i64")
    lit_count = [0]
    table = {f.name: f for f in funcs}
    llvm_fns = {}
    for name in eligible:
        fn = table[name]
        fty = ir.FunctionType(LTY[cast(str, fn.return_type)], llvm_params(fn))
        llvm_fns[name] = ir.Function(module, fty, name=name)

    def var_types(fn: Function) -> dict[Any, Any]:
        """Sequentially infer each local's Velaris type for typed allocas."""
        tenv = dict(fn.params)

        def te(e: Any) -> str:
            if isinstance(e, Num):
                return "Int"
            if isinstance(e, Str):
                return "Text"
            if isinstance(e, FloatNum):
                return "Float"
            if isinstance(e, Bool):
                return "Bool"
            if isinstance(e, Var):
                return tenv[e.name]
            if isinstance(e, Not):
                return "Bool"
            if isinstance(e, Neg):
                return te(e.value)
            if isinstance(e, Call):
                if e.name in ("length", "get", "code_at"):
                    return "Int"        # builtin reads used natively
                return cast(str, table[e.name].return_type)
            if isinstance(e, BinOp):
                if e.op in ("and", "or", "==", "!=", "<", ">", "<=", ">="):
                    return "Bool"
                return te(e.left)      # '+' on Text gives Text
            return "Int"

        def ts(stmts: Any) -> None:
            for s in stmts:
                if isinstance(s, (Let, Assign)):
                    tenv.setdefault(s.name, te(s.value))
                elif isinstance(s, If):
                    ts(s.then)
                    ts(s.other)
                elif isinstance(s, While):
                    ts(s.body)
        ts(fn.body)
        return tenv

    def collect_names(stmts: Any, out: Any) -> None:
        for s in stmts:
            if isinstance(s, (Let, Assign)):
                out.add(s.name)
            elif isinstance(s, If):
                collect_names(s.then, out)
                collect_names(s.other, out)
            elif isinstance(s, While):
                collect_names(s.body, out)

    CMP = {"==": "==", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">="}

    for name in eligible:
        fn = table[name]
        lf = llvm_fns[name]
        entry = lf.append_basic_block("entry")
        b = ir.IRBuilder(entry)
        slots = {}
        tenv = var_types(fn)
        names = {p for p, _ in fn.params}
        collect_names(fn.body, names)
        lists = {}                     # name -> (data pointer, length)
        list_names = {p for p, t in fn.params if t == "List of Int"}
        for n in sorted(names - list_names):
            slots[n] = b.alloca(LTY[tenv.get(n, "Int")], name=n)
        ai = 0
        for pname, ptype in fn.params:
            if ptype == "Text":
                data, ln = lf.args[ai], lf.args[ai + 1]
                data.name, ln.name = pname + "_data", pname + "_len"
                tv = b.insert_value(
                    b.insert_value(ir.Constant(TEXT, ir.Undefined), data, 0),
                    ln, 1)
                slots[pname] = b.alloca(TEXT, name=pname)
                b.store(tv, slots[pname])
                ai += 2
            elif ptype == "List of Int":
                data, ln = lf.args[ai], lf.args[ai + 1]
                data.name, ln.name = pname + "_data", pname + "_len"
                lists[pname] = (data, ln)
                ai += 2
            else:
                lf.args[ai].name = pname
                b.store(lf.args[ai], slots[pname])
                ai += 1

        def txt_ptr(v: Any) -> Any:
            return b.extract_value(v, 0)

        def txt_len(v: Any) -> Any:
            return b.extract_value(v, 1)

        def make_text(ptr: Any, ln: Any) -> Any:
            t = b.insert_value(ir.Constant(TEXT, ir.Undefined), ptr, 0)
            return b.insert_value(t, ln, 1)

        def arena_alloc(n: Any) -> tuple[Any, ...]:
            """Bump-allocate n code points; flag (don't crash) if full."""
            used = b.load(arena_used)
            cap = b.load(arena_cap)
            room = b.icmp_signed("<=", b.add(used, n), cap)
            ok_bb = lf.append_basic_block("arena_ok")
            full_bb = lf.append_basic_block("arena_full")
            cont_bb = lf.append_basic_block("arena_done")
            b.cbranch(room, ok_bb, full_bb)
            b.position_at_end(ok_bb)
            base = b.load(arena)
            slot = b.gep(base, [used])
            b.store(b.add(used, n), arena_used)
            b.branch(cont_bb)
            b.position_at_end(full_bb)
            b.store(i64(1), arena_full)      # caller grows and retries
            fallback = b.load(arena)
            b.branch(cont_bb)
            b.position_at_end(cont_bb)
            phi = b.phi(i32p)
            phi.add_incoming(slot, ok_bb)
            phi.add_incoming(fallback, full_bb)
            room_phi = b.phi(ir.IntType(1))
            room_phi.add_incoming(ir.Constant(ir.IntType(1), 1), ok_bb)
            room_phi.add_incoming(ir.Constant(ir.IntType(1), 0), full_bb)
            return phi, room_phi

        def copy_into(dst: Any, src_ptr: Any, n: Any, tag: Any) -> None:
            """Copy n code points, one at a time (small texts, no libc)."""
            i_slot = b.alloca(i64, name=tag + "_i")
            b.store(i64(0), i_slot)
            head = lf.append_basic_block(tag + "_head")
            body = lf.append_basic_block(tag + "_body")
            done = lf.append_basic_block(tag + "_done")
            b.branch(head)
            b.position_at_end(head)
            iv = b.load(i_slot)
            b.cbranch(b.icmp_signed("<", iv, n), body, done)
            b.position_at_end(body)
            iv2 = b.load(i_slot)
            b.store(b.load(b.gep(src_ptr, [iv2])), b.gep(dst, [iv2]))
            b.store(b.add(iv2, i64(1)), i_slot)
            b.branch(head)
            b.position_at_end(done)

        def ee(e: Any) -> Any:                    # emit expression (i64 or double)
            if isinstance(e, Num):
                return i64(e.value)
            if isinstance(e, Str):
                pts = [ord(c) for c in e.value]
                lit_count[0] += 1
                arr_ty = ir.ArrayType(i32, max(len(pts), 1))
                g = ir.GlobalVariable(module, arr_ty,
                                      name=f"text_lit_{lit_count[0]}")
                g.global_constant = True
                g.initializer = ir.Constant(
                    arr_ty, [ir.Constant(i32, p) for p in pts] or
                    [ir.Constant(i32, 0)])
                ptr = b.gep(g, [i64(0), i64(0)])
                return make_text(ptr, i64(len(pts)))
            if isinstance(e, FloatNum):
                return ir.Constant(f64, e.value)
            if isinstance(e, Bool):
                return i64(1 if e.value else 0)
            if isinstance(e, Var):
                return b.load(slots[e.name])
            if isinstance(e, Not):
                return b.xor(ee(e.value), i64(1))
            if isinstance(e, Neg):
                v = ee(e.value)
                if v.type == f64:
                    return b.fsub(ir.Constant(f64, 0.0), v)
                # 0 - v overflows for the smallest Int: E407, as the
                # interpreter says. Until 8.2 it wrapped to itself, and a
                # promise proven about -n broke (advisory-int-negation.md)
                pair = b.call(ovf_fns["ssub"], [i64(0), v])
                was = b.load(overflowed)
                b.store(b.select(b.extract_value(pair, 1), i64(1), was),
                        overflowed)
                return b.extract_value(pair, 0)
            if (isinstance(e, Call) and e.name in ("length", "code_at")
                    and e.args and not (isinstance(e.args[0], Var)
                                        and e.args[0].name in lists)):
                tv = ee(e.args[0])
                if tv.type != TEXT:
                    raise NotImplementedError("length on a non-text value")
                data, ln = txt_ptr(tv), txt_len(tv)
                if e.name == "length":
                    return ln
                idx = ee(e.args[1])
                inside = b.and_(b.icmp_signed(">=", idx, i64(0)),
                                b.icmp_signed("<", idx, ln))
                ok_bb = lf.append_basic_block("char_ok")
                bad_bb = lf.append_basic_block("char_out")
                cont_bb = lf.append_basic_block("char_done")
                b.cbranch(inside, ok_bb, bad_bb)
                b.position_at_end(ok_bb)
                ch = b.zext(b.load(b.gep(data, [idx])), i64)
                b.branch(cont_bb)
                b.position_at_end(bad_bb)
                b.store(i64(1), oob)
                b.store(idx, oob_idx)
                b.store(ln, oob_len)
                b.branch(cont_bb)
                b.position_at_end(cont_bb)
                phi = b.phi(i64)
                phi.add_incoming(ch, ok_bb)
                phi.add_incoming(i64(0), bad_bb)
                return phi
            if (isinstance(e, Call) and e.name in ("length", "get")
                    and e.args and isinstance(e.args[0], Var)
                    and e.args[0].name in lists):
                data, ln = lists[e.args[0].name]
                if e.name == "length":
                    return ln
                idx = ee(e.args[1])
                inside = b.and_(b.icmp_signed(">=", idx, i64(0)),
                                b.icmp_signed("<", idx, ln))
                ok_bb = lf.append_basic_block("read_ok")
                bad_bb = lf.append_basic_block("read_out")
                cont_bb = lf.append_basic_block("read_done")
                b.cbranch(inside, ok_bb, bad_bb)
                b.position_at_end(ok_bb)          # in range: real read
                val = b.load(b.gep(data, [idx]))
                b.branch(cont_bb)
                b.position_at_end(bad_bb)         # out of range: no read,
                b.store(i64(1), oob)              # just record it
                b.store(idx, oob_idx)
                b.store(ln, oob_len)
                b.branch(cont_bb)
                b.position_at_end(cont_bb)
                phi = b.phi(i64)
                phi.add_incoming(val, ok_bb)
                phi.add_incoming(i64(0), bad_bb)
                return phi
            if isinstance(e, Call):
                args_ll = []
                callee = table.get(e.name)
                want = [t for _, t in callee.params] if callee else []
                for pos, a in enumerate(e.args):
                    if pos < len(want) and want[pos] == "Text":
                        tv = ee(a)
                        args_ll += [txt_ptr(tv), txt_len(tv)]
                        continue
                    if isinstance(a, Var) and a.name in lists:
                        args_ll += list(lists[a.name])
                    else:
                        args_ll.append(ee(a))
                return b.call(llvm_fns[e.name], args_ll)
            left = None                   # a '+' emits its left side once
            if isinstance(e, BinOp) and e.op == "+":
                lv = left = ee(e.left)
                if lv.type == TEXT:
                    rv = ee(e.right)
                    if rv.type != TEXT:
                        raise NotImplementedError
                    ln_l, ln_r = txt_len(lv), txt_len(rv)
                    total = b.add(ln_l, ln_r)
                    dst, had_room = arena_alloc(total)
                    # no room means NO copying: the caller grows the
                    # buffer and runs the whole call again
                    do_bb = lf.append_basic_block("cat_do")
                    skip_bb = lf.append_basic_block("cat_skip")
                    end_bb = lf.append_basic_block("cat_end")
                    b.cbranch(had_room, do_bb, skip_bb)
                    b.position_at_end(do_bb)
                    copy_into(dst, txt_ptr(lv), ln_l, "cpl")
                    copy_into(b.gep(dst, [ln_l]), txt_ptr(rv), ln_r, "cpr")
                    did_bb = b.block          # loops moved us elsewhere
                    b.branch(end_bb)
                    b.position_at_end(skip_bb)
                    skipped_bb = b.block
                    b.branch(end_bb)
                    b.position_at_end(end_bb)
                    ln_phi = b.phi(i64)
                    ln_phi.add_incoming(total, did_bb)
                    ln_phi.add_incoming(i64(0), skipped_bb)
                    return make_text(dst, ln_phi)
            if isinstance(e, BinOp):
                if e.op == "and":
                    return b.and_(ee(e.left), ee(e.right))
                if e.op == "or":
                    return b.or_(ee(e.left), ee(e.right))
                # the left side of a '+' was emitted above. Until 8.2 it was
                # emitted again here, so a chain of n additions emitted 2**n
                # trees and a 20-term sum never finished compiling
                l = left if left is not None else ee(e.left)  # noqa: E741
                r = ee(e.right)
                flt = l.type == f64

                def checked(kind: Any, value: Any) -> Any:
                    """Same answer as interpreted: too big is an error."""
                    pair = b.call(ovf_fns[kind], [l, r])
                    bit = b.extract_value(pair, 1)
                    was = b.load(overflowed)
                    b.store(b.select(bit, i64(1), was), overflowed)
                    return b.extract_value(pair, 0)

                if e.op == "+":
                    return b.fadd(l, r) if flt else checked("sadd", None)
                if e.op == "-":
                    return b.fsub(l, r) if flt else checked("ssub", None)
                if e.op == "*":
                    return b.fmul(l, r) if flt else checked("smul", None)
                if flt:
                    return b.zext(b.fcmp_ordered(CMP[e.op], l, r), i64)
                return b.zext(b.icmp_signed(CMP[e.op], l, r), i64)
            raise AssertionError("unreachable")

        def truthy(e: Any) -> Any:
            return b.icmp_signed("!=", ee(e), i64(0))

        def es(stmts: Any) -> None:                              # emit statements
            for s in stmts:
                if b.block.is_terminated:
                    return
                if isinstance(s, (Let, Assign)):
                    b.store(ee(s.value), slots[s.name])
                elif isinstance(s, Return):
                    b.ret(ee(s.value))
                elif isinstance(s, ExprStmt):
                    ee(s.expr)
                elif isinstance(s, If):
                    bb_then = lf.append_basic_block("then")
                    bb_else = lf.append_basic_block("else")
                    bb_cont = lf.append_basic_block("cont")
                    b.cbranch(truthy(s.cond), bb_then, bb_else)
                    b.position_at_end(bb_then)
                    es(s.then)
                    if not b.block.is_terminated:
                        b.branch(bb_cont)
                    b.position_at_end(bb_else)
                    es(s.other)
                    if not b.block.is_terminated:
                        b.branch(bb_cont)
                    b.position_at_end(bb_cont)
                elif isinstance(s, While):
                    bb_cond = lf.append_basic_block("wcond")
                    bb_body = lf.append_basic_block("wbody")
                    bb_end = lf.append_basic_block("wend")
                    b.branch(bb_cond)
                    b.position_at_end(bb_cond)
                    b.cbranch(truthy(s.cond), bb_body, bb_end)
                    b.position_at_end(bb_body)
                    es(s.body)
                    if not b.block.is_terminated:
                        b.branch(bb_cond)
                    b.position_at_end(bb_end)

        es(fn.body)
        if not b.block.is_terminated:
            b.ret(ir.Constant(f64, 0.0)
                  if fn.return_type == "Float" else i64(0))

    for init in ("initialize", "initialize_native_target",
                 "initialize_native_asmprinter"):
        try:                   # each may be required or deprecated,
            getattr(binding, init)()       # depending on llvmlite version
        except (RuntimeError, AttributeError):
            pass
    target = binding.Target.from_default_triple()
    tm = target.create_target_machine(opt=3)
    backing = binding.parse_assembly(str(module))
    backing.verify()
    try:                                    # optimize IR if this API exists
        pto = binding.create_pipeline_tuning_options()
        pto.speed_level = 3
        pb = binding.create_pass_builder(tm, pto)
        pb.getModulePassManager().run(backing, pb)
    except Exception:
        try:
            pmb = binding.PassManagerBuilder()
            pmb.opt_level = 3
            pm = binding.ModulePassManager()
            pmb.populate(pm)
            pm.run(backing)
        except Exception:
            pass                            # unoptimized native is still fast
    engine = binding.create_mcjit_compiler(backing, tm)
    engine.finalize_object()
    _state._NATIVE_KEEPALIVE.append(engine)

    import ctypes
    CT: dict[str, Any] = {"Int": ctypes.c_int64, "Bool": ctypes.c_int64,
          "Float": ctypes.c_double}
    I64P = ctypes.POINTER(ctypes.c_int64)
    I32P = ctypes.POINTER(ctypes.c_uint32)
    oob_addr = engine.get_global_value_address("velaris_oob")
    idx_addr = engine.get_global_value_address("velaris_oob_idx")
    len_addr = engine.get_global_value_address("velaris_oob_len")
    flag = ctypes.cast(oob_addr, I64P)
    ovf_cell = ctypes.cast(
        engine.get_global_value_address("velaris_overflow"), I64P)
    flag_i = ctypes.cast(idx_addr, I64P)
    flag_n = ctypes.cast(len_addr, I64P)

    class CText(ctypes.Structure):
        _fields_ = [("data", ctypes.POINTER(ctypes.c_uint32)),
                    ("length", ctypes.c_int64)]

    arena_state: dict[str, Any] = {"buf": (ctypes.c_uint32 * (1 << 16))(),
                                   "cap": 1 << 16}
    arena_ptr_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena"),
        ctypes.POINTER(ctypes.POINTER(ctypes.c_uint32)))
    arena_cap_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena_cap"), I64P)
    arena_used_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena_used"), I64P)
    arena_full_cell = ctypes.cast(
        engine.get_global_value_address("velaris_arena_full"), I64P)

    def install_arena() -> None:
        arena_ptr_cell[0] = ctypes.cast(
            arena_state["buf"], ctypes.POINTER(ctypes.c_uint32))
        arena_cap_cell[0] = arena_state["cap"]
    install_arena()

    def grow_arena() -> None:
        arena_state["cap"] *= 4
        arena_state["buf"] = (ctypes.c_uint32 * arena_state["cap"])()
        install_arena()

    def wrap(fn: Any, raw: Any) -> Any:
        types = [pt for _, pt in fn.params]

        def out_of_range() -> Any:
            # A whole number past 64 bits would wrap in machine code. Nothing
            # in Velaris makes one from 8.2; if something did, it stops here
            # rather than become another number.
            return VelarisError("E407", "a number too big to hold reached "
                                f"'{fn.name}' (whole numbers go from "
                                f"{INT_MIN} to {INT_MAX})", fn.line)
        wants_bool = fn.return_type == "Bool"
        wants_text = fn.return_type == "Text"

        def call(*vals: Any) -> Any:
            cargs = []
            keep = []                    # keep buffers alive for the call
            for t, v in zip(types, vals):
                if t == "Text":
                    buf: ctypes.Array[Any] = (ctypes.c_uint32 * len(v))(
                        *[ord(c) for c in v])
                    keep.append(buf)
                    cargs += [ctypes.cast(buf, I32P), len(v)]
                elif t == "List of Int":
                    if any(not INT_MIN <= x <= INT_MAX for x in v):
                        raise out_of_range()
                    buf = (ctypes.c_int64 * len(v))(*v)
                    keep.append(buf)
                    cargs += [ctypes.cast(buf, I64P), len(v)]
                else:
                    if t == "Int" and not INT_MIN <= v <= INT_MAX:
                        raise out_of_range()
                    cargs.append(v)
            for _attempt in range(6):
                flag[0] = 0
                ovf_cell[0] = 0
                arena_used_cell[0] = 0
                arena_full_cell[0] = 0
                r = raw(*cargs)
                if ovf_cell[0]:
                    ovf_cell[0] = 0
                    raise VelarisError("E407",
                        "this arithmetic made a number too big to hold "
                        f"(whole numbers go from {INT_MIN} to "
                        f"{INT_MAX})", fn.line,
                        fixes=["keep the numbers smaller",
                               "or work in smaller units, like cents "
                               "instead of rupees"])
                if not arena_full_cell[0]:
                    break
                grow_arena()          # too small: bigger buffer, run again
            else:
                raise VelarisError("E607",
                    "this text grew too large to build", fn.line,
                    fixes=["build shorter pieces of text"])
            if flag[0]:                  # the read was refused, not made
                i, n = flag_i[0], flag_n[0]
                flag[0] = 0
                what = ("text" if any(t == "Text" for t in types)
                        else "list")
                unit = "character" if what == "text" else "item"
                raise VelarisError("E602",
                    f"position {i} is outside the {what} "
                    f"(it has {n} {unit}(s))", fn.line,
                    fixes=["positions go from 0 to length - 1",
                           "check with length(...) before using get"])
            if wants_text:
                return "".join(chr(r.data[i]) for i in range(r.length))
            return bool(r) if wants_bool else r
        return call

    out = {}
    for name in eligible:
        fn = table[name]
        ctypes_args: list[Any] = []
        for _, pt in fn.params:
            if pt == "Text":
                ctypes_args += [I32P, ctypes.c_int64]
            elif pt == "List of Int":
                ctypes_args += [I64P, ctypes.c_int64]
            else:
                ctypes_args.append(CT[pt])
        proto = ctypes.CFUNCTYPE(CT[cast(str, fn.return_type)], *ctypes_args)
        raw = proto(engine.get_function_address(name))
        out[name] = wrap(fn, raw)
    return out
