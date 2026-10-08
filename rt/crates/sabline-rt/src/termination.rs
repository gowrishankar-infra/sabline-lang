//! Which loops provably end: syntactic, the same with and without the
//! prover. `sabline/termination.py`, rule for rule.
//!
//! One shape is `terminates` and everything else is `unshown`: a
//! condition that is, or has as an `and` conjunct, `v < E`, `v <= E`,
//! `v > E` or `v >= E` (v on either side), where E mentions nothing the
//! body binds and calls only pure functions, and every path through the
//! body moves v by exactly one step toward E, with v assigned nowhere else
//! in the body. A path that returns or fails leaves the loop and needs no
//! step. `check --strict` refuses an `unshown` loop with E612; nothing
//! else does.

use std::collections::{BTreeSet, HashMap, HashSet};

use crate::nodes::{Expr, Function, Stmt};
use crate::show::expr_str;
use crate::tables::{builtin, builtin_reached, is_fallible};

/// One loop's verdict, as `loop_termination` gives it.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LoopVerdict {
    /// The `while`'s line.
    pub line: u32,
    /// `terminates` or `unshown`.
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

/// `loop_termination(fn, table)`: every loop in `f`, in the order the
/// reference walks them.
pub fn loop_termination(f: &Function, table: &HashMap<&str, &Function>) -> Vec<LoopVerdict> {
    fn walk(stmts: &[Stmt], table: &HashMap<&str, &Function>, out: &mut Vec<LoopVerdict>) {
        for s in stmts {
            match s {
                Stmt::While { cond, body, line, .. } => {
                    let (verdict, why) = judge(cond, body, table);
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
