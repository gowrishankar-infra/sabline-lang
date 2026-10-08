//! Stage 4, the effect checker: a function may cause only the effects it
//! declares, transitively. `sabline/effects.py`, rule for rule.
//!
//! Two walks, as in the reference: `walk` over a body, which refuses an
//! effect the function does not declare (E300), and `walk_pure` over a
//! promise, which refuses any effect at all and any `try` (E310). Each
//! stops at the first refusal in a function, and the next function is
//! checked anyway, so a check reports at most one of these per function.
//!
//! What each walk does not look inside is copied as well, because it is
//! what decides which programs pass: neither walk enters a `Block` (the
//! parser flattens every one it makes, so none reaches here from a file),
//! and neither enters a `Closure` (a function value is lifted, and checked
//! as the function it was lifted into).

use std::collections::{HashMap, HashSet};

use crate::errors::SablineError;
use crate::loader::{blame, stdlib_dir, unknown_function};
use crate::nodes::{Expr, Function, Stmt};
use crate::pypath;
use crate::tables::{builtin, builtin_reached, is_builtin, is_new_builtin, ALL_EFFECTS};

/// `local_names_of(fn)`: the parameters, and every name a `let`, an
/// assignment or a `check` arm binds - not looking inside a `Block`, as
/// the reference does not.
pub fn local_names_of(f: &Function) -> HashSet<String> {
    let mut out: HashSet<String> = f.params.iter().map(|(p, _)| p.clone()).collect();
    fn gather(stmts: &[Stmt], out: &mut HashSet<String>) {
        for s in stmts {
            match s {
                Stmt::Let { name, .. } | Stmt::Assign { name, .. } => {
                    out.insert(name.clone());
                }
                Stmt::If { then, other, .. } => {
                    gather(then, out);
                    gather(other, out);
                }
                Stmt::While { body, .. } => gather(body, out),
                Stmt::Check { ok_name, fail_name, ok_body, fail_body, .. } => {
                    if let Some(n) = ok_name {
                        if !n.is_empty() {
                            out.insert(n.clone());
                        }
                    }
                    out.insert(fail_name.clone());
                    gather(ok_body, out);
                    gather(fail_body, out);
                }
                _ => {}
            }
        }
    }
    gather(&f.body, &mut out);
    out
}

/// `function_locals_of(fn, table)`: the locals of `f` that hold a function
/// value.
pub fn function_locals_of(f: &Function, table: &HashMap<&str, &Function>) -> HashSet<String> {
    let mut out: HashSet<String> = f
        .params
        .iter()
        .filter(|(_, t)| t.starts_with("fn("))
        .map(|(p, _)| p.clone())
        .collect();
    fn gather(stmts: &[Stmt], table: &HashMap<&str, &Function>, out: &mut HashSet<String>) {
        for s in stmts {
            match s {
                Stmt::Let { name, value, ann, .. } => {
                    let holds = ann.as_deref().unwrap_or("").starts_with("fn(")
                        || matches!(value, Expr::Closure { .. })
                        || matches!(value, Expr::Var { name: v, .. }
                            if table.contains_key(v.as_str()) || out.contains(v));
                    if holds {
                        out.insert(name.clone());
                    }
                }
                Stmt::If { then, other, .. } => {
                    gather(then, table, out);
                    gather(other, table, out);
                }
                Stmt::While { body, .. } => gather(body, table, out),
                Stmt::Block { stmts, .. } => gather(stmts, table, out),
                Stmt::Check { ok_body, fail_body, .. } => {
                    gather(ok_body, table, out);
                    gather(fail_body, table, out);
                }
                _ => {}
            }
        }
    }
    gather(&f.body, table, &mut out);
    out
}

struct Effects<'a> {
    table: HashMap<&'a str, &'a Function>,
    locals: HashMap<String, (HashSet<String>, HashSet<String>)>,
}

impl<'a> Effects<'a> {
    fn in_table(&self, name: &str) -> bool {
        self.table.contains_key(name)
    }

    fn effects_of_callee(&self, name: &str, line: u32) -> Result<Vec<String>, SablineError> {
        if let Some(b) = builtin_reached(name, |n| self.in_table(n)) {
            let row = builtin(b).map_or(&[][..], |r| r.effects);
            return Ok(row.iter().map(|s| (*s).to_string()).collect());
        }
        if let Some(f) = self.table.get(name) {
            return Ok(f.effects.clone());
        }
        Err(unknown_function(name, line, self.table.keys().copied()))
    }

    /// `calls_a_value(node, fn)`: whether a call runs a function value held
    /// in a local rather than a builtin or a function of the program.
    fn calls_a_value(&mut self, name: &str, f: &Function) -> bool {
        if !self.locals.contains_key(&f.name) {
            let names = local_names_of(f);
            let values = function_locals_of(f, &self.table);
            self.locals.insert(f.name.clone(), (names, values));
        }
        let (names, values) = &self.locals[&f.name];
        if !names.contains(name) {
            return false;
        }
        values.contains(name)
            || (builtin_reached(name, |n| self.table.contains_key(n)).is_none()
                && !self.table.contains_key(name))
    }

    fn walk_stmt(&mut self, s: &Stmt, f: &Function) -> Result<(), SablineError> {
        match s {
            Stmt::Let { value, .. }
            | Stmt::FailStmt { value, .. }
            | Stmt::Assign { value, .. } => self.walk(value, f),
            Stmt::Return { value, .. } => match value {
                Some(v) => self.walk(v, f),
                None => Ok(()),
            },
            Stmt::ExprStmt { expr, .. } => self.walk(expr, f),
            Stmt::Check { subject, ok_body, fail_body, .. } => {
                self.walk(subject, f)?;
                for s in ok_body.iter().chain(fail_body) {
                    self.walk_stmt(s, f)?;
                }
                Ok(())
            }
            Stmt::If { cond, then, other, .. } => {
                self.walk(cond, f)?;
                for s in then.iter().chain(other) {
                    self.walk_stmt(s, f)?;
                }
                Ok(())
            }
            Stmt::While { cond, body, invariants, .. } => {
                self.walk(cond, f)?;
                for (inv, _) in invariants {
                    self.walk_pure(inv, f, "invariant")?;
                }
                for s in body {
                    self.walk_stmt(s, f)?;
                }
                Ok(())
            }
            Stmt::Block { .. } => Ok(()),
        }
    }

    fn walk(&mut self, e: &Expr, f: &Function) -> Result<(), SablineError> {
        match e {
            Expr::Call { name, args, line } => {
                if self.calls_a_value(name, f) {
                    for a in args {
                        self.walk(a, f)?; // a passed-in function is pure
                    }
                    return Ok(());
                }
                let needed = self.effects_of_callee(name, *line)?;
                let mut missing: Vec<&String> =
                    needed.iter().filter(|n| !f.effects.contains(n)).collect();
                missing.sort();
                missing.dedup();
                if missing.len() == 1 && missing[0] == "env" && name == "env" {
                    return Err(SablineError::with_owned_fixes(
                        "E300",
                        "env() now needs 'uses env'",
                        *line,
                        vec![
                            format!(
                                "add 'uses env' to the signature of '{}' (and to every \
                                 function that calls it)",
                                f.name
                            ),
                            "run it with --allow io,env, or drop the env() call".to_string(),
                        ],
                    ));
                }
                if !missing.is_empty() {
                    let eff =
                        missing.iter().map(|s| s.as_str()).collect::<Vec<_>>().join(", ");
                    let declared = if f.effects.is_empty() {
                        "declares no effects (it is pure)".to_string()
                    } else {
                        format!("only declares 'uses {}'", f.effects.join(", "))
                    };
                    return Err(SablineError::with_owned_fixes(
                        "E300",
                        format!(
                            "function '{}' calls '{name}' which needs effect '{eff}', but '{}' \
                             {declared}",
                            f.name, f.name
                        ),
                        *line,
                        vec![
                            format!("add 'uses {eff}' to the signature of '{}'", f.name),
                            format!("remove the call to '{name}'"),
                        ],
                    ));
                }
                for a in args {
                    self.walk(a, f)?;
                }
                Ok(())
            }
            Expr::BinOp { left, right, .. } => {
                self.walk(left, f)?;
                self.walk(right, f)
            }
            Expr::TryExpr { value, .. }
            | Expr::Not { value, .. }
            | Expr::Neg { value, .. } => self.walk(value, f),
            Expr::ListLit { items, .. } => {
                for it in items {
                    self.walk(it, f)?;
                }
                Ok(())
            }
            Expr::MapLit { entries, .. } => {
                for (k, v) in entries {
                    self.walk(k, f)?;
                    self.walk(v, f)?;
                }
                Ok(())
            }
            Expr::FieldGet { obj, .. } => self.walk(obj, f),
            Expr::RecordLit { fields, .. } => {
                for (_, v) in fields {
                    self.walk(v, f)?;
                }
                Ok(())
            }
            Expr::Num { .. }
            | Expr::FloatNum { .. }
            | Expr::Str { .. }
            | Expr::Bool { .. }
            | Expr::Closure { .. }
            | Expr::Var { .. } => Ok(()),
        }
    }

    fn walk_pure(&mut self, e: &Expr, f: &Function, place: &str) -> Result<(), SablineError> {
        match e {
            Expr::Call { name, args, line } => {
                if self.calls_a_value(name, f) {
                    for a in args {
                        self.walk_pure(a, f, place)?;
                    }
                    return Ok(());
                }
                let mut eff = self.effects_of_callee(name, *line)?;
                if !eff.is_empty() {
                    eff.sort();
                    eff.dedup();
                    return Err(SablineError::with_fixes(
                        "E310",
                        format!(
                            "the '{place}' promise of '{}' calls '{name}' which has effects \
                             ({}); promises must be pure",
                            f.name,
                            eff.join(", ")
                        ),
                        *line,
                        &["only use pure functions and math inside promises"],
                    ));
                }
                for a in args {
                    self.walk_pure(a, f, place)?;
                }
                Ok(())
            }
            Expr::BinOp { left, right, .. } => {
                self.walk_pure(left, f, place)?;
                self.walk_pure(right, f, place)
            }
            Expr::Not { value, .. } | Expr::Neg { value, .. } => self.walk_pure(value, f, place),
            Expr::TryExpr { line, .. } => Err(SablineError::with_fixes(
                "E310",
                format!(
                    "the '{place}' promise of '{}' uses 'try'; promises must be simple and pure",
                    f.name
                ),
                *line,
                &["only use plain values and pure functions in promises"],
            )),
            Expr::ListLit { items, .. } => {
                for it in items {
                    self.walk_pure(it, f, place)?;
                }
                Ok(())
            }
            Expr::MapLit { entries, .. } => {
                for (k, v) in entries {
                    self.walk_pure(k, f, place)?;
                    self.walk_pure(v, f, place)?;
                }
                Ok(())
            }
            Expr::FieldGet { obj, .. } => self.walk_pure(obj, f, place),
            Expr::RecordLit { fields, .. } => {
                for (_, v) in fields {
                    self.walk_pure(v, f, place)?;
                }
                Ok(())
            }
            Expr::Num { .. }
            | Expr::FloatNum { .. }
            | Expr::Str { .. }
            | Expr::Bool { .. }
            | Expr::Closure { .. }
            | Expr::Var { .. } => Ok(()),
        }
    }

    fn check_function(&mut self, f: &Function) -> Result<(), SablineError> {
        // a uses clause names effects, and only those in ALL_EFFECTS exist
        let unknown: Vec<&String> =
            f.effects.iter().filter(|e| !ALL_EFFECTS.contains(&e.as_str())).collect();
        if let Some(first) = unknown.first() {
            let all = ALL_EFFECTS.join(", ");
            return Err(SablineError::with_owned_fixes(
                "E300",
                format!(
                    "function '{}' declares '{first}', which is not an effect; the effects are \
                     {all}",
                    f.name
                ),
                f.line,
                vec![
                    format!("remove '{first}' from the uses clause"),
                    format!("or use one of: {all}"),
                ],
            ));
        }
        for s in &f.body {
            self.walk_stmt(s, f)?;
        }
        for (e, _) in &f.requires {
            self.walk_pure(e, f, "requires")?;
        }
        for (e, _) in &f.ensures {
            self.walk_pure(e, f, "ensures")?;
        }
        Ok(())
    }
}

/// `check_effects(funcs, errors)`: every refusal, in the order found.
pub fn check_effects(funcs: &[Function], install_dir: &str, errors: &mut Vec<SablineError>) {
    let table: HashMap<&str, &Function> = funcs.iter().map(|f| (f.name.as_str(), f)).collect();

    // A function named like a builtin is refused (E204, 8.0), unless the
    // builtin was added from 4.3 on (SPEC.md 10.1), or the function is in
    // the shipped standard library, which may keep the names it was
    // written with.
    let stdlib = format!("{}{}", pypath::realpath(&stdlib_dir(install_dir)), pypath::SEP);
    for f in funcs {
        let n = &f.name;
        let in_stdlib = pypath::realpath(&f.src_file).starts_with(&stdlib);
        if in_stdlib {
            continue;
        }
        if !n.contains('.') && is_builtin(n) && !is_new_builtin(n) {
            errors.push(blame(
                &f.src_file,
                SablineError::with_owned_fixes(
                    "E204",
                    format!(
                        "'{n}' is the name of a built-in, so a function called '{n}' would \
                         shadow it; through 7.x the built-in silently won and this function was \
                         never reached"
                    ),
                    f.line,
                    vec![
                        format!(
                            "rename the function (a built-in named '{n}' already does that job)"
                        ),
                        format!("or import it under a name, so it is reached as prefix.{n}"),
                    ],
                ),
            ));
        }
    }

    let mut checker = Effects { table, locals: HashMap::new() };
    for f in funcs {
        if let Err(e) = checker.check_function(f) {
            errors.push(blame(&f.src_file, e));
        }
    }
}
