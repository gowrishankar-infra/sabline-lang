//! Which loops provably end: syntactic, the same with and without the
//! prover. `sabline/termination.py`, rule for rule.
//!
//! One shape is `terminates`: a condition that is, or has as an `and`
//! conjunct, `v < E`, `v <= E`, `v > E` or `v >= E` (v on either side),
//! where E mentions nothing the body binds and calls only pure functions,
//! and every path through the body moves v by exactly one step toward E,
//! with v assigned nowhere else in the body. A path that returns or fails
//! leaves the loop and needs no step.
//!
//! From 9.0 (decisions/0006 section c, amended 2026-10-08), a loop that
//! shape does not reach is `input-bounded` when its exit is keyed to the
//! first empty `read_line()` - `bounded_by_input` names the two shapes -
//! and everything else is `unshown`. `check --strict` refuses an
//! `unshown` loop with E612; nothing else does.

use std::collections::{BTreeSet, HashMap, HashSet};

use crate::nodes::{Expr, Function, Stmt};
use crate::show::expr_str;
use crate::tables::{builtin, builtin_reached, is_fallible};

/// One loop's verdict, as `loop_termination` gives it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoopVerdict {
    /// The `while`'s line.
    pub line: u32,
    /// `terminates`, `input-bounded` or `unshown`.
    pub verdict: &'static str,
    /// Why, in a sentence.
    pub why: String,
}

/// `_names_bound_in(stmts)`: every name assigned or bound anywhere inside
/// these statements, nested blocks included.
fn names_bound_in(stmts: &[Stmt], out: &mut HashSet<String>) {
    for s in stmts {
        match s {
            Stmt::Assign { name, .. } | Stmt::Let { name, .. } => {
                out.insert(name.clone());
            }
            Stmt::If { then, other, .. } => {
                names_bound_in(then, out);
                names_bound_in(other, out);
            }
            Stmt::While { body, .. } => names_bound_in(body, out),
            Stmt::Check { ok_name, fail_name, ok_body, fail_body, .. } => {
                if let Some(n) = ok_name {
                    if !n.is_empty() {
                        out.insert(n.clone());
                    }
                }
                out.insert(fail_name.clone());
                names_bound_in(ok_body, out);
                names_bound_in(fail_body, out);
            }
            Stmt::Block { stmts, .. } => names_bound_in(stmts, out),
            Stmt::Return { .. } | Stmt::ExprStmt { .. } | Stmt::FailStmt { .. } => {}
        }
    }
}

fn bound_in(stmts: &[Stmt]) -> HashSet<String> {
    let mut out = HashSet::new();
    names_bound_in(stmts, &mut out);
    out
}

/// `_limit_is_invariant(expr, bound, table)`.
fn limit_is_invariant(
    e: &Expr,
    bound: &HashSet<String>,
    table: &HashMap<&str, &Function>,
) -> bool {
    match e {
        Expr::Num { .. } | Expr::FloatNum { .. } | Expr::Str { .. } | Expr::Bool { .. } => {
            true
        }
        Expr::Var { name, .. } => !bound.contains(name),
        Expr::Neg { value, .. } => limit_is_invariant(value, bound, table),
        Expr::BinOp { op, left, right, .. } => {
            matches!(op.as_str(), "+" | "-" | "*" | "/" | "%")
                && limit_is_invariant(left, bound, table)
                && limit_is_invariant(right, bound, table)
        }
        Expr::FieldGet { obj, .. } => limit_is_invariant(obj, bound, table),
        Expr::Call { name, args, .. } => {
            let reached = builtin_reached(name, |n| table.contains_key(n));
            let pure = match reached.and_then(builtin) {
                Some(row) => row.effects.is_empty() && !reached.is_some_and(is_fallible),
                None => table
                    .get(name.as_str())
                    .is_some_and(|f| f.effects.is_empty() && !f.can_fail),
            };
            pure && args.iter().all(|a| limit_is_invariant(a, bound, table))
        }
        _ => false,
    }
}

/// `_steps_along_paths(stmts, v, op)`: how many one-step moves of `v` each
/// path that runs to the end of `stmts` makes, or `None` (the reference's
/// `BAD`) when `v` is touched any other way.
fn steps_along_paths(stmts: &[Stmt], v: &str, op: &str) -> Option<BTreeSet<i64>> {
    let want = if op == "<" || op == "<=" { "+" } else { "-" };
    let mut counts: BTreeSet<i64> = BTreeSet::from([0]);
    let combine = |counts: &BTreeSet<i64>, add: &BTreeSet<i64>| -> BTreeSet<i64> {
        counts.iter().flat_map(|c| add.iter().map(move |x| c + x)).collect()
    };
    for st in stmts {
        match st {
            Stmt::Assign { name, value, .. } if name == v => {
                let one_step = matches!(value, Expr::BinOp { op: o, left, right, .. }
                    if o == want
                        && matches!(left.as_ref(), Expr::Var { name: l, .. } if l == v)
                        && matches!(right.as_ref(), Expr::Num { value: n } if n == "1"));
                if !one_step {
                    return None;
                }
                counts = counts.iter().map(|c| c + 1).collect();
            }
            Stmt::Let { name, .. } if name == v => return None,
            Stmt::Return { .. } | Stmt::FailStmt { .. } => return Some(BTreeSet::new()),
            Stmt::If { then, other, .. } => {
                let a = steps_along_paths(then, v, op)?;
                let b = steps_along_paths(other, v, op)?;
                let both: BTreeSet<i64> = a.union(&b).copied().collect();
                counts = combine(&counts, &both);
            }
            Stmt::Check { ok_name, fail_name, ok_body, fail_body, .. } => {
                if ok_name.as_deref() == Some(v) || fail_name == v {
                    return None;
                }
                let a = steps_along_paths(ok_body, v, op)?;
                let b = steps_along_paths(fail_body, v, op)?;
                let both: BTreeSet<i64> = a.union(&b).copied().collect();
                counts = combine(&counts, &both);
            }
            Stmt::While { body, .. } => {
                if bound_in(body).contains(v) {
                    return None; // moved a number of times
                }
            }
            Stmt::Block { stmts, .. } => {
                let inner = steps_along_paths(stmts, v, op)?;
                counts = combine(&counts, &inner);
            }
            _ => {}
        }
        if counts.iter().any(|c| *c > 1) {
            return None;
        }
    }
    Some(counts)
}

fn conjuncts(cond: &Expr) -> Vec<&Expr> {
    match cond {
        Expr::BinOp { op, left, right, .. } if op == "and" => {
            let mut out = conjuncts(left);
            out.extend(conjuncts(right));
            out
        }
        _ => vec![cond],
    }
}

fn flip(op: &str) -> Option<&'static str> {
    match op {
        "<" => Some(">"),
        "<=" => Some(">="),
        ">" => Some("<"),
        ">=" => Some("<="),
        _ => None,
    }
}

fn judge(
    cond: &Expr,
    body: &[Stmt],
    table: &HashMap<&str, &Function>,
) -> (&'static str, String) {
    let bound = bound_in(body);
    for c in conjuncts(cond) {
        let Expr::BinOp { op, left, right, .. } = c else {
            continue;
        };
        let Some(flipped) = flip(op) else {
            continue;
        };
        let op_static: &str = op.as_str();
        for (side, other, o) in [(left, right, op_static), (right, left, flipped)] {
            let Expr::Var { name: v, .. } = side.as_ref() else {
                continue;
            };
            if !bound.contains(v) {
                continue; // never moves: not a counter
            }
            if !limit_is_invariant(other, &bound, table) {
                return (
                    "unshown",
                    format!("the limit '{}' changes inside the loop", expr_str(other)),
                );
            }
            let Some(steps) = steps_along_paths(body, v, o) else {
                return (
                    "unshown",
                    format!("'{v}' is not moved by exactly one step toward the limit on every path"),
                );
            };
            if !steps.is_empty() && steps != BTreeSet::from([1]) {
                return (
                    "unshown",
                    format!("some path through the body leaves '{v}' where it was"),
                );
            }
            return (
                "terminates",
                format!("'{v}' moves one step toward '{}' every turn", expr_str(other)),
            );
        }
    }
    ("unshown", "no counter walking toward a limit in the loop's condition".to_string())
}

/// `INPUT_BOUNDED`: the third verdict (9.0), a loop that leaves on the
/// first empty `read_line()`.
pub const INPUT_BOUNDED: &str = "input-bounded";

/// `_reads_a_line(expr, table)`: a call of the builtin `read_line()`.
fn reads_a_line(e: &Expr, table: &HashMap<&str, &Function>) -> bool {
    matches!(e, Expr::Call { name, args, .. }
        if args.is_empty()
            && builtin_reached(name, |n| table.contains_key(n)) == Some("read_line"))
}

/// `_length_of(expr, name, table)`: `length(name)`, the builtin.
fn length_of(e: &Expr, name: &str, table: &HashMap<&str, &Function>) -> bool {
    matches!(e, Expr::Call { name: called, args, .. }
        if args.len() == 1
            && builtin_reached(called, |n| table.contains_key(n)) == Some("length")
            && matches!(&args[0], Expr::Var { name: v, .. } if v == name))
}

/// `_tests_empty(expr, name, table)`: `Some(true)` when `e` tests `name`
/// for empty, `Some(false)` when it tests it for not empty - SPEC.md 9.5's
/// shapes and no others, each with its sides either way round.
fn tests_empty(e: &Expr, name: &str, table: &HashMap<&str, &Function>) -> Option<bool> {
    let Expr::BinOp { op, left, right, .. } = e else {
        return None;
    };
    if !matches!(op.as_str(), "==" | "!=" | "<" | ">") {
        return None;
    }
    let turned = match op.as_str() {
        "<" => ">",
        ">" => "<",
        other => other,
    };
    for (side, o, other) in [(left, op.as_str(), right), (right, turned, left)] {
        let is_var = matches!(side.as_ref(), Expr::Var { name: v, .. } if v == name);
        if is_var && matches!(other.as_ref(), Expr::Str { value } if value.is_empty()) {
            match o {
                "==" => return Some(true),
                "!=" => return Some(false),
                _ => {}
            }
        }
        if length_of(side, name, table)
            && matches!(other.as_ref(), Expr::Num { value } if value == "0")
        {
            match o {
                "==" => return Some(true),
                "!=" | ">" => return Some(false),
                _ => {}
            }
        }
    }
    None
}

/// `_bindings_of(stmts, name)`: every statement anywhere inside these that
/// binds `name`, nested blocks and loops included.
fn bindings_of<'a>(stmts: &'a [Stmt], name: &str, out: &mut Vec<&'a Stmt>) {
    for s in stmts {
        match s {
            Stmt::Assign { name: n, .. } | Stmt::Let { name: n, .. } => {
                if n == name {
                    out.push(s);
                }
            }
            Stmt::If { then, other, .. } => {
                bindings_of(then, name, out);
                bindings_of(other, name, out);
            }
            Stmt::While { body, .. } => bindings_of(body, name, out),
            Stmt::Check { ok_name, fail_name, ok_body, fail_body, .. } => {
                if ok_name.as_deref() == Some(name) || fail_name == name {
                    out.push(s);
                }
                bindings_of(ok_body, name, out);
                bindings_of(fail_body, name, out);
            }
            Stmt::Block { stmts, .. } => bindings_of(stmts, name, out),
            Stmt::Return { .. } | Stmt::ExprStmt { .. } | Stmt::FailStmt { .. } => {}
        }
    }
}

fn bound_by<'a>(stmts: &'a [Stmt], name: &str) -> Vec<&'a Stmt> {
    let mut out = Vec::new();
    bindings_of(stmts, name, &mut out);
    out
}

/// `_bounded_by_input(loop, table)`: the input-bounded verdict and its
/// reason, or `None`. A statement of the body itself binds `r` to
/// `read_line()` and nothing else in the body binds `r`; and either the
/// condition (or an `and` conjunct) tests that `r` is not empty, or it is
/// a flag `f` whose only assignment in the body is `f = false`, a
/// statement of the arm of a later `if` of the body taken when `r` is
/// empty.
fn bounded_by_input(
    cond: &Expr,
    body: &[Stmt],
    table: &HashMap<&str, &Function>,
) -> Option<(&'static str, String)> {
    for (i, read) in body.iter().enumerate() {
        let (Stmt::Let { name: r, value, .. } | Stmt::Assign { name: r, value, .. }) = read
        else {
            continue;
        };
        if !reads_a_line(value, table) {
            continue;
        }
        let bound = bound_by(body, r);
        if bound.len() != 1 || !std::ptr::eq(bound[0], read) {
            continue;
        }
        for c in conjuncts(cond) {
            if tests_empty(c, r, table) == Some(false) {
                return Some((
                    INPUT_BOUNDED,
                    format!(
                        "every turn reads a line into '{r}', and the loop leaves on the first \
                         empty read"
                    ),
                ));
            }
            let Expr::Var { name: f, .. } = c else {
                continue;
            };
            let flags = bound_by(body, f);
            let clear = match flags.as_slice() {
                [only @ Stmt::Assign { value: Expr::Bool { value: false }, .. }] => *only,
                _ => continue,
            };
            for later in &body[i + 1..] {
                let Stmt::If { cond: test, then, other, .. } = later else {
                    continue;
                };
                let arm: &[Stmt] = match tests_empty(test, r, table) {
                    Some(true) => then,
                    Some(false) => other,
                    None => &[],
                };
                if arm.iter().any(|s| std::ptr::eq(s, clear)) {
                    return Some((
                        INPUT_BOUNDED,
                        format!(
                            "every turn reads a line into '{r}', and '{f}' is cleared on the \
                             first empty read"
                        ),
                    ));
                }
            }
        }
    }
    None
}

/// `loop_termination(fn, table)`: every loop in `f`, in the order the
/// reference walks them.
pub fn loop_termination(f: &Function, table: &HashMap<&str, &Function>) -> Vec<LoopVerdict> {
    fn walk(stmts: &[Stmt], table: &HashMap<&str, &Function>, out: &mut Vec<LoopVerdict>) {
        for s in stmts {
            match s {
                Stmt::While { cond, body, line, .. } => {
                    let (mut verdict, mut why) = judge(cond, body, table);
                    if verdict == "unshown" {
                        if let Some((v, w)) = bounded_by_input(cond, body, table) {
                            (verdict, why) = (v, w);
                        }
                    }
                    out.push(LoopVerdict { line: *line, verdict, why });
                    walk(body, table, out);
                }
                Stmt::If { then, other, .. } => {
                    walk(then, table, out);
                    walk(other, table, out);
                }
                Stmt::Check { ok_body, fail_body, .. } => {
                    walk(ok_body, table, out);
                    walk(fail_body, table, out);
                }
                Stmt::Block { stmts, .. } => walk(stmts, table, out),
                _ => {}
            }
        }
    }
    let mut out = Vec::new();
    walk(&f.body, table, &mut out);
    out
}
