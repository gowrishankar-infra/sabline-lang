//! Stage 5, the type checker: wrong-type programs refused before they run.
//! `sabline/checker.py`'s `check_main` and `check_types`, rule for rule and
//! message for message.
//!
//! **It is a transliteration, and three of its properties are copied on
//! purpose because each changes what a check reports:**
//!
//! * `infer` is called again where the reference calls it again - three
//!   times on a map's first value, twice on a key it puts in a message -
//!   because inferring a function value checks that function, and a check
//!   appends what it finds to the one list of problems. Fewer calls would
//!   be faster and would report a different list.
//! * Problems are appended in the order the reference meets them, and a
//!   statement that fails is recorded and checking goes on at the next
//!   top-level statement; a refusal inside a function value that is being
//!   inferred is appended when it is met, ahead of whatever the statement
//!   around it goes on to find.
//! * Where the reference raises rather than appends - a parameter of a
//!   type that does not exist - checking stops, and `check_types` answers
//!   `Err` with that one problem, which the caller appends as the
//!   reference's caller does.
//!
//! There is no prover here and there will not be one: proving stays in
//! the Python package (decisions/0002), and what it proved is an input to
//! a run, not something a run works out.

use std::collections::{HashMap, HashSet};

use crate::errors::SablineError;
use crate::lexer::fmt_fn_type;
use crate::loader::{blame, unknown_function};
use crate::nodes::{Expr, Function, RecordDef, Stmt};
use crate::pyrepr::py_strip;
use crate::show::{expr_str, nice_name};
use crate::tables::{
    builtin, builtin_reached, is_currency, is_fallible, shown_name, CURRENCIES, HMAC_BUILTINS,
    KNOWN_TYPES, MONEY_BUILTINS, ROUNDING, SECRET_SOURCES,
};
use crate::types::{
    carries_secret, clash_error, currency_clash, currency_generic, fn_sig_parts, is_money,
    is_secret, records_carrying, secret_inner, strip_secret, type_mentions, wrap_secret,
    SECRET_PREFIX,
};

type R<T> = Result<T, SablineError>;

fn err(
    code: &'static str,
    message: impl Into<String>,
    line: u32,
    fixes: Vec<String>,
) -> SablineError {
    SablineError::with_owned_fixes(code, message, line, fixes)
}

fn fixes(items: &[&str]) -> Vec<String> {
    items.iter().map(|s| (*s).to_string()).collect()
}

/// "an" before `Int`, "a" before anything else, as the messages say it.
fn an(t: &str) -> &'static str {
    if t == "Int" {
        "an"
    } else {
        "a"
    }
}

/// `check_main(funcs, errors, running)`: `main` must exist when a program
/// is run, take nothing, and declare no failure.
pub fn check_main(funcs: &[Function], errors: &mut Vec<SablineError>, running: bool) {
    let Some(m) = funcs.iter().find(|f| f.name == "main") else {
        if running {
            errors.push(err(
                "E400",
                "there is no 'main' - a program needs somewhere to start",
                1,
                fixes(&["add one: fn main() uses io { ... }"]),
            ));
        }
        return;
    };
    if !m.params.is_empty() {
        errors.push(err(
            "E401",
            format!("'main' takes no parameters, but this one asks for {}", m.params.len()),
            m.line,
            fixes(&["read the command line with args() instead"]),
        ));
    }
    if m.can_fail {
        errors.push(err(
            "E524",
            "'main' cannot fail - there is nobody above it to catch",
            m.line,
            fixes(&[
                "handle failures inside main with check",
                "or exit_with(1) when something goes wrong",
            ]),
        ));
    }
}

const TYPE_HINT: &str =
    "use Int, Text, Bool, Money of INR, a record name, or List of <one of those>";

fn units_fix() -> Vec<String> {
    fixes(&[
        "money(1250, \"INR\") is an amount of 1250 minor units",
        "units_of(m) is an amount's minor units, as an Int",
    ])
}

fn num_fix() -> Vec<String> {
    fixes(&[
        "make both sides the same number type",
        "convert with to_float(x), or round(x) for an Int",
    ])
}

/// One function being checked: the names it can see and their types, and
/// where each secret it holds came from.
struct Ctx<'a> {
    f: &'a Function,
    env: HashMap<String, String>,
    origins: HashMap<String, String>,
    declared_ret: String,
}

struct Types<'a> {
    table: HashMap<&'a str, &'a Function>,
    rec: Vec<(String, Vec<(String, String)>)>,
    rec_carries: HashMap<String, bool>,
    lambda_of: HashMap<&'a str, &'a Function>,
    namespaces: HashSet<String>,
    captures: HashMap<String, Vec<(String, String)>>,
    errors: Vec<SablineError>,
}

/// `check_types(funcs, records, errors)`. Problems are appended to
/// `errors`; `Err` is the one problem the reference raises rather than
/// appends, after which nothing else is checked.
pub fn check_types(
    funcs: &[Function],
    records: &[RecordDef],
    errors: &mut Vec<SablineError>,
) -> R<()> {
    let table: HashMap<&str, &Function> = funcs.iter().map(|f| (f.name.as_str(), f)).collect();
    let mut t = Types {
        table,
        rec: Vec::new(),
        rec_carries: HashMap::new(),
        lambda_of: HashMap::new(),
        namespaces: HashSet::new(),
        captures: HashMap::new(),
        errors: std::mem::take(errors),
    };
    let answer = t.check_all(funcs, records);
    *errors = std::mem::take(&mut t.errors);
    answer
}

impl<'a> Types<'a> {
    fn in_table(&self, name: &str) -> bool {
        self.table.contains_key(name)
    }

    fn reached<'n>(&self, name: &'n str) -> Option<&'n str> {
        builtin_reached(name, |n| self.table.contains_key(n))
    }

    fn rec_fields(&self, name: &str) -> Option<&Vec<(String, String)>> {
        self.rec.iter().find(|(n, _)| n == name).map(|(_, f)| f)
    }

    fn is_record(&self, name: &str) -> bool {
        self.rec.iter().any(|(n, _)| n == name)
    }

    fn carries(&self, t: &str) -> bool {
        carries_secret(t, Some(&self.rec_carries))
    }

    fn check_all(&mut self, funcs: &'a [Function], records: &'a [RecordDef]) -> R<()> {
        for r in records {
            let refused = if self.is_record(&r.name) {
                Some(err(
                    "E507",
                    format!("record '{}' is defined twice", r.name),
                    r.line,
                    fixes(&["rename one of them"]),
                ))
            } else if self.in_table(&r.name) {
                Some(err(
                    "E507",
                    format!("'{}' is used for both a record and a function", r.name),
                    r.line,
                    fixes(&["rename one of them"]),
                ))
            } else {
                let mut seen: HashSet<&str> = HashSet::new();
                let mut dup = None;
                for (fname, _) in &r.fields {
                    if !seen.insert(fname) {
                        dup = Some(err(
                            "E507",
                            format!("record '{}' has field '{fname}' twice", r.name),
                            r.line,
                            fixes(&["remove the duplicate field"]),
                        ));
                        break;
                    }
                }
                dup
            };
            match refused {
                Some(e) => self.errors.push(blame(&r.src_file, e)),
                None => self.rec.push((r.name.clone(), r.fields.clone())),
            }
        }

        self.rec_carries = records_carrying(records);

        for r in records {
            for (fname, ftype) in &r.fields {
                if !self.valid_type(ftype, &[]) {
                    let e = self.bad_type(
                        ftype,
                        &[],
                        format!(
                            "unknown type '{ftype}' for field '{fname}' of record '{}'",
                            r.name
                        ),
                        r.line,
                    );
                    self.errors.push(blame(&r.src_file, e));
                }
            }
        }

        // first: every declared type must be a real type
        for f in funcs {
            for tv in &f.type_vars {
                if KNOWN_TYPES.contains(&tv.as_str()) || self.is_record(tv) {
                    self.errors.push(blame(
                        &f.src_file,
                        err(
                            "E541",
                            format!("type variable '{tv}' shadows a real type"),
                            f.line,
                            fixes(&["pick a fresh name like T, U, or Item"]),
                        ),
                    ));
                } else if !f.params.iter().any(|(_, pt)| type_mentions(pt, tv)) {
                    self.errors.push(blame(
                        &f.src_file,
                        err(
                            "E540",
                            format!(
                                "type variable '{tv}' must appear in at least one parameter (a \
                                 {tv} only in the return type cannot be inferred)"
                            ),
                            f.line,
                            vec![format!("use {tv} in a parameter type")],
                        ),
                    ));
                }
            }
            for (pname, ptype) in &f.params {
                if !self.valid_type(ptype, &f.type_vars) {
                    return Err(self.bad_type(
                        ptype,
                        &f.type_vars,
                        format!(
                            "unknown type '{ptype}' for parameter '{pname}' of '{}'",
                            f.name
                        ),
                        f.line,
                    ));
                }
            }
            if let Some(ret) = &f.return_type {
                if !self.valid_type(ret, &f.type_vars) {
                    return Err(self.bad_type(
                        ret,
                        &f.type_vars,
                        format!("unknown return type '{ret}' for '{}'", f.name),
                        f.line,
                    ));
                }
            }
        }

        self.namespaces = self
            .table
            .keys()
            .filter(|n| n.contains('.'))
            .map(|n| n.split('.').next().unwrap_or(n).to_string())
            .collect();
        self.lambda_of =
            funcs.iter().filter(|f| f.is_lambda).map(|f| (f.name.as_str(), f)).collect();

        if let Some(m) = self.table.get("main").copied() {
            if m.can_fail {
                self.errors.push(blame(
                    &m.src_file,
                    err(
                        "E524",
                        "'main' cannot be 'or fail' - there is no one above it to handle the \
                         failure",
                        m.line,
                        fixes(&["handle failures inside main with check blocks"]),
                    ),
                ));
            }
        }

        for f in funcs {
            if f.is_lambda && !f.free_names.is_empty() {
                continue; // checked where it is written, where its names mean something
            }
            if let Err(e) = self.check_fn(f) {
                self.errors.push(blame(&f.src_file, e));
            }
        }
        Ok(())
    }

    // ---- types as text ---------------------------------------------------

    fn valid_type(&self, t: &str, tvars: &[String]) -> bool {
        let is_tv = |s: &str| tvars.iter().any(|v| v == s);
        if KNOWN_TYPES.contains(&t) || self.is_record(t) || is_tv(t) {
            return true;
        }
        if let Some(cur) = t.strip_prefix("Money of ") {
            return is_currency(cur) || is_tv(cur);
        }
        if is_secret(t) {
            let inner = secret_inner(t);
            return !is_secret(inner) && self.valid_type(inner, tvars);
        }
        if let Some(inner) = t.strip_prefix("List of ") {
            return self.valid_type(inner, tvars);
        }
        if let Some(rest) = t.strip_prefix("Map of ") {
            return match rest.split_once(" to ") {
                Some((key, val)) => {
                    (key == "Text" || key == "Int") && self.valid_type(val, tvars)
                }
                None => false,
            };
        }
        if let Some((parts, ret)) = fn_sig_parts(t) {
            return parts.iter().all(|p| self.valid_type(p, tvars))
                && (ret == "Unit" || self.valid_type(&ret, tvars));
        }
        false
    }

    /// `currency_named(t, tvars)`: the currency code in `t` that is not in
    /// the table, or the empty text where there is none.
    fn currency_named(t: &str, tvars: &[String]) -> String {
        if let Some(cur) = t.strip_prefix("Money of ") {
            return if is_currency(cur) || tvars.iter().any(|v| v == cur) {
                String::new()
            } else {
                cur.to_string()
            };
        }
        if is_secret(t) {
            return Self::currency_named(secret_inner(t), tvars);
        }
        if let Some(inner) = t.strip_prefix("List of ") {
            return Self::currency_named(inner, tvars);
        }
        if let Some(rest) = t.strip_prefix("Map of ") {
            let val = rest.split_once(" to ").map_or("", |(_, v)| v);
            return Self::currency_named(val, tvars);
        }
        if let Some((parts, ret)) = fn_sig_parts(t) {
            for p in parts.iter().chain(std::iter::once(&ret)) {
                let got = Self::currency_named(p, tvars);
                if !got.is_empty() {
                    return got;
                }
            }
        }
        String::new()
    }

    fn unknown_currency(code: &str, line: u32) -> SablineError {
        let all: Vec<&str> = CURRENCIES.iter().map(|(c, _)| *c).collect();
        err(
            "E551",
            format!("'{code}' is not a currency Sabline knows"),
            line,
            vec![
                format!("the currencies are: {}", all.join(", ")),
                "a currency is added to sabline.CURRENCIES with the minor-unit count ISO 4217 \
                 gives it, not by a program"
                    .to_string(),
            ],
        )
    }

    fn bad_type(&self, t: &str, tvars: &[String], message: String, line: u32) -> SablineError {
        let code = Self::currency_named(t, tvars);
        if !code.is_empty() {
            return Self::unknown_currency(&code, line);
        }
        err("E500", message, line, fixes(&[TYPE_HINT]))
    }

    fn no_shadow(&self, name: &str, line: u32) -> R<()> {
        if self.namespaces.contains(name) {
            return Err(err(
                "E514",
                format!("'{name}' is the name of an import, so it cannot also be a variable"),
                line,
                vec![
                    "rename the variable".to_string(),
                    format!("or give the import another name: as {name}_lib"),
                ],
            ));
        }
        Ok(())
    }

    // ---- Secret (6.0) ----------------------------------------------------

    /// `sink_builtin(name)`: the emitting builtin a call reaches, if any.
    fn sink_builtin<'n>(&self, name: &'n str) -> Option<&'n str> {
        let b = self.reached(name)?;
        if b == "declassify" || HMAC_BUILTINS.contains(&b) {
            return None;
        }
        builtin(b).filter(|row| !row.effects.is_empty()).map(|_| b)
    }

    /// `tattling_builtin(name)`: the fallible builtin a call reaches, if any.
    fn tattling_builtin<'n>(&self, name: &'n str) -> Option<&'n str> {
        self.reached(name).filter(|b| is_fallible(b))
    }

    /// `secret_enters(name)`: where the secret a function hands back first
    /// enters the program, following one call at a time.
    fn secret_enters(&self, name: &str, seen: &mut HashSet<String>) -> Option<String> {
        let f = self.table.get(name).copied()?;
        if seen.contains(name) {
            return None;
        }
        seen.insert(name.to_string());
        let mut found = None;
        for s in &f.body {
            self.enters_stmt(s, seen, &mut found);
        }
        found
    }

    fn enters_stmt(&self, s: &Stmt, seen: &mut HashSet<String>, found: &mut Option<String>) {
        if found.is_some() {
            return;
        }
        match s {
            Stmt::Let { value, .. }
            | Stmt::Assign { value, .. }
            | Stmt::FailStmt { value, .. }
            | Stmt::ExprStmt { expr: value, .. } => self.enters_expr(value, seen, found),
            Stmt::Return { value, .. } => {
                if let Some(v) = value {
                    self.enters_expr(v, seen, found);
                }
            }
            Stmt::If { cond, then, other, .. } => {
                self.enters_expr(cond, seen, found);
                for x in then.iter().chain(other) {
                    self.enters_stmt(x, seen, found);
                }
            }
            Stmt::While { cond, body, invariants, .. } => {
                self.enters_expr(cond, seen, found);
                for x in body {
                    self.enters_stmt(x, seen, found);
                }
                for (e, _) in invariants {
                    self.enters_expr(e, seen, found);
                }
            }
            Stmt::Block { stmts, .. } => {
                for x in stmts {
                    self.enters_stmt(x, seen, found);
                }
            }
            Stmt::Check { subject, ok_body, fail_body, .. } => {
                self.enters_expr(subject, seen, found);
                for x in ok_body.iter().chain(fail_body) {
                    self.enters_stmt(x, seen, found);
                }
            }
        }
    }

    fn enters_expr(&self, e: &Expr, seen: &mut HashSet<String>, found: &mut Option<String>) {
        if found.is_some() {
            return;
        }
        match e {
            Expr::Call { name, args, line } => {
                let b = self.reached(name);
                if let Some(b) = b.filter(|b| SECRET_SOURCES.contains(b)) {
                    *found = Some(format!("{b}(), line {line}"));
                    return;
                }
                if let Some(deeper) = self.table.get(name.as_str()) {
                    if self.carries(deeper.return_type.as_deref().unwrap_or("")) {
                        if let Some(got) = self.secret_enters(name, seen) {
                            if !got.is_empty() {
                                *found = Some(got);
                                return;
                            }
                        }
                    }
                }
                for a in args {
                    self.enters_expr(a, seen, found);
                }
            }
            Expr::Neg { value, .. }
            | Expr::Not { value, .. }
            | Expr::TryExpr { value, .. } => {
                self.enters_expr(value, seen, found);
            }
            Expr::BinOp { left, right, .. } => {
                self.enters_expr(left, seen, found);
                self.enters_expr(right, seen, found);
            }
            Expr::RecordLit { fields, .. } => {
                for (_, v) in fields {
                    self.enters_expr(v, seen, found);
                }
            }
            Expr::FieldGet { obj, .. } => self.enters_expr(obj, seen, found),
            Expr::ListLit { items, .. } => {
                for x in items {
                    self.enters_expr(x, seen, found);
                }
            }
            Expr::MapLit { entries, .. } => {
                for (k, v) in entries {
                    self.enters_expr(k, seen, found);
                    self.enters_expr(v, seen, found);
                }
            }
            Expr::Num { .. }
            | Expr::FloatNum { .. }
            | Expr::Str { .. }
            | Expr::Bool { .. }
            | Expr::Closure { .. }
            | Expr::Var { .. } => {}
        }
    }

    fn leak(what: &str, place: &str, t: &str, origin: &str, line: u32) -> SablineError {
        err(
            "E560",
            format!(
                "{what} is {t}, and {place} - a Secret cannot be printed, written, sent or \
                 passed to Python. It came from {origin}"
            ),
            line,
            fixes(&[
                "build what you emit out of values that are not secret",
                "or let it out on purpose: declassify(x, \"why this is safe to emit\") needs \
                 \"uses declassify\", is named in the audit with that reason, and an operator \
                 can refuse to grant it",
            ]),
        )
    }

    fn no_secret_branch(&self, kind: &str, t: &str, line: u32, origin: &str) -> R<()> {
        if !self.carries(t) {
            return Ok(());
        }
        Err(err(
            "E563",
            format!(
                "'{kind}' would branch on {t}, which came from {origin} - a program does not \
                 choose what to do by looking at a secret. A comparison over one gives a Secret \
                 of Bool exactly so that this is refused: in a loop it would read the secret out \
                 a character at a time"
            ),
            line,
            fixes(&[
                "say so and branch on the answer: declassify(key == \"\", \"whether a key is set \
                 is not the key\") needs \"uses declassify\", is named in the audit with that \
                 reason, and an operator can refuse to grant it",
                "or decide without looking: build what you do out of values that are not secret",
            ]),
        ))
    }

    fn callee_sig(&self, name: &str, line: u32) -> R<(Vec<String>, String)> {
        if let Some(b) = self.reached(name) {
            let row = builtin(b).expect("a reached builtin is in BUILTINS");
            return Ok((
                row.types.iter().map(|s| (*s).to_string()).collect(),
                row.ret.to_string(),
            ));
        }
        match self.table.get(name) {
            Some(f) => Ok((
                f.params.iter().map(|(_, t)| t.clone()).collect(),
                f.return_type.clone().unwrap_or_else(|| "Unit".to_string()),
            )),
            None => Err(unknown_function(name, line, self.table.keys().copied())),
        }
    }

    fn builtin_call_fallible(&mut self, cx: &Ctx<'a>, node: &Expr) -> bool {
        let Expr::Call { name, args, .. } = node else {
            return false;
        };
        if self.reached(name).is_some_and(is_fallible) {
            return true;
        }
        if name == "get" && !args.is_empty() {
            return match self.infer(cx, &args[0], false) {
                Ok(t) => t.starts_with("Map of "),
                Err(_) => false,
            };
        }
        false
    }

    // ---- one function ----------------------------------------------------

    fn check_fn(&mut self, f: &'a Function) -> R<()> {
        for (pname, _) in &f.params {
            self.no_shadow(pname, f.line)?;
        }
        let mut env: HashMap<String, String> = f.params.iter().cloned().collect();
        let captures =
            self.captures.get(&f.name).cloned().unwrap_or_else(|| f.captures.clone());
        for (cname, ctype) in &captures {
            env.entry(cname.clone()).or_insert_with(|| ctype.clone());
        }
        let declared_ret = f.return_type.clone().unwrap_or_else(|| "Unit".to_string());
        let mut origins: HashMap<String, String> = HashMap::new();
        for (p, t) in &f.params {
            if self.carries(t) {
                origins.insert(
                    p.clone(),
                    format!("the parameter '{p}' of {}", nice_name(&f.name)),
                );
            }
        }
        for (c, t) in &captures {
            if self.carries(t) {
                origins.insert(c.clone(), format!("'{c}', carried into this function value"));
            }
        }
        let mut cx = Ctx { f, env, origins, declared_ret };

        // promises first, while the names are exactly the parameters
        for (expr, cline) in &f.requires {
            if strip_secret(&self.infer(&cx, expr, false)?) != "Bool" {
                return Err(err(
                    "E505",
                    "'requires' must be a yes/no promise (Bool)",
                    *cline,
                    fixes(&["use a comparison like price >= 0"]),
                ));
            }
        }
        if !f.ensures.is_empty() {
            if cx.declared_ret != "Unit" {
                cx.env.insert("result".to_string(), cx.declared_ret.clone());
            }
            for (expr, cline) in &f.ensures {
                if strip_secret(&self.infer(&cx, expr, false)?) != "Bool" {
                    return Err(err(
                        "E505",
                        "'ensures' must be a yes/no promise (Bool)",
                        *cline,
                        fixes(&["use a comparison like result >= 0"]),
                    ));
                }
            }
            cx.env.remove("result");
        }

        // a problem in one top-level statement is recorded and checking
        // goes on at the next (8.0)
        let mut would_have_bound: Vec<String> = Vec::new();
        for stmt in &f.body {
            if let Err(e) = self.check_stmt(&mut cx, stmt) {
                let cascade = e.code == "E402"
                    && would_have_bound.iter().any(|n| e.message.contains(&format!("'{n}'")));
                if !cascade {
                    self.errors.push(blame(&f.src_file, e));
                }
                if let Stmt::Let { name, .. } = stmt {
                    would_have_bound.push(name.clone());
                }
            }
        }
        Ok(())
    }

    fn origin_of(&mut self, cx: &Ctx<'a>, node: &Expr) -> String {
        match node {
            Expr::Var { name, .. } => {
                return match cx.origins.get(name) {
                    Some(o) if !o.is_empty() => o.clone(),
                    _ => format!("'{name}'"),
                };
            }
            Expr::Call { name, args, line } => {
                if let Some(b) = self.reached(name).filter(|b| SECRET_SOURCES.contains(b)) {
                    return format!("{b}(), line {line}");
                }
                if let Some(called) = self.table.get(name.as_str()).copied() {
                    let ret = called.return_type.as_deref().unwrap_or("");
                    if self.carries(ret) {
                        let said = format!(
                            "{}, which returns {} (line {line})",
                            nice_name(name),
                            called.return_type.as_deref().unwrap_or("None")
                        );
                        for a in args {
                            if let Ok(t) = self.infer(cx, a, true) {
                                if self.carries(&t) {
                                    return format!(
                                        "{}, through {said}",
                                        self.origin_of(cx, a)
                                    );
                                }
                            }
                        }
                        let deeper = self.secret_enters(name, &mut HashSet::new());
                        return match deeper {
                            Some(d) if !d.is_empty() => format!("{d}, through {said}"),
                            _ => said,
                        };
                    }
                }
            }
            Expr::FieldGet { obj, field, .. } => {
                let base = self.origin_of(cx, obj);
                return format!("the field '{field}' of {base}");
            }
            Expr::TryExpr { value, .. } => return self.origin_of(cx, value),
            _ => {}
        }
        let kids: Vec<&Expr> = match node {
            Expr::Call { args, .. } => args.iter().collect(),
            Expr::BinOp { left, right, .. } => vec![left, right],
            Expr::Not { value, .. } | Expr::Neg { value, .. } => vec![value],
            Expr::ListLit { items, .. } => items.iter().collect(),
            Expr::MapLit { entries, .. } => entries.iter().map(|(_, v)| v).collect(),
            Expr::RecordLit { fields, .. } => fields.iter().map(|(_, v)| v).collect(),
            _ => Vec::new(),
        };
        for k in kids {
            if let Ok(t) = self.infer(cx, k, true) {
                if self.carries(&t) {
                    return self.origin_of(cx, k);
                }
            }
        }
        "a secret value".to_string()
    }

    fn refuse_secret_args(
        &mut self,
        cx: &Ctx<'a>,
        args: &[Expr],
        line: u32,
        said: &str,
        place: &str,
    ) -> R<()> {
        for (i, a) in args.iter().enumerate() {
            let Ok(t) = self.infer(cx, a, true) else {
                continue;
            };
            if self.carries(&t) {
                let origin = self.origin_of(cx, a);
                return Err(Self::leak(
                    &format!("argument {} of '{said}'", i + 1),
                    place,
                    &t,
                    &origin,
                    line,
                ));
            }
        }
        Ok(())
    }

    // ---- what an expression is -------------------------------------------

    #[allow(clippy::too_many_lines)]
    fn infer(&mut self, cx: &Ctx<'a>, node: &Expr, allow_fail: bool) -> R<String> {
        let f = cx.f;
        match node {
            Expr::TryExpr { value, line } => {
                if !f.can_fail {
                    return Err(err(
                        "E521",
                        format!("'try' passes failure up, but '{}' cannot fail", f.name),
                        *line,
                        vec![
                            format!("add 'or fail' to the signature of '{}'", f.name),
                            "or handle it here with a check block".to_string(),
                        ],
                    ));
                }
                let cname = match value.as_ref() {
                    Expr::Call { name, .. } => name.as_str(),
                    _ => "",
                };
                let user_ok = self.table.get(cname).is_some_and(|c| c.can_fail);
                if !user_ok && !self.builtin_call_fallible(cx, value) {
                    return Err(err(
                        "E522",
                        format!(
                            "'{}' cannot fail - call it directly without 'try'",
                            shown_name(cname)
                        ),
                        *line,
                        fixes(&["remove the 'try'"]),
                    ));
                }
                return self.infer(cx, value, true);
            }
            Expr::Num { .. } => return Ok("Int".to_string()),
            Expr::FloatNum { .. } => return Ok("Float".to_string()),
            Expr::Neg { value, line } => {
                let t = self.infer(cx, value, false)?;
                let bare = strip_secret(&t);
                if bare != "Int" && bare != "Float" && !is_money(&bare) {
                    return Err(err(
                        "E501",
                        format!("'-' needs a number, but this is {t}"),
                        *line,
                        fixes(&["negate an Int or Float value"]),
                    ));
                }
                return Ok(t);
            }
            Expr::Str { .. } => return Ok("Text".to_string()),
            Expr::Bool { .. } => return Ok("Bool".to_string()),
            Expr::Closure { name, free, line } => {
                let Some(lam) = self.lambda_of.get(name.as_str()).copied() else {
                    return Err(err(
                        "E402",
                        format!("unknown function value '{name}'"),
                        *line,
                        Vec::new(),
                    ));
                };
                // a name is captured when the code around it has it as a local
                let caught: Vec<(String, String)> = free
                    .iter()
                    .filter_map(|n| cx.env.get(n).map(|t| (n.clone(), t.clone())))
                    .collect();
                self.captures.insert(lam.name.clone(), caught);
                self.check_fn(lam)?;
                let params: Vec<String> = lam.params.iter().map(|(_, t)| t.clone()).collect();
                return Ok(fmt_fn_type(&params, lam.return_type.as_deref()));
            }
            Expr::Var { name, line } => {
                if let Some(t) = cx.env.get(name) {
                    return Ok(t.clone());
                }
                if let Some(f2) = self.table.get(name.as_str()).copied() {
                    if !f2.type_vars.is_empty() {
                        return Err(err(
                            "E543",
                            format!(
                                "'{}' is generic - generic functions cannot be passed as values yet",
                                f2.name
                            ),
                            *line,
                            fixes(&["call it directly instead"]),
                        ));
                    }
                    if !f2.effects.is_empty() {
                        return Err(err(
                            "E530",
                            format!(
                                "'{}' uses effects ({}) - only pure functions can be passed as values",
                                f2.name,
                                f2.effects.join(", ")
                            ),
                            *line,
                            fixes(&["pass a function with no 'uses' clause"]),
                        ));
                    }
                    if f2.can_fail {
                        return Err(err(
                            "E530",
                            format!(
                                "'{}' can fail - only functions that cannot fail can be passed as values",
                                f2.name
                            ),
                            *line,
                            fixes(&["pass a function without 'or fail'"]),
                        ));
                    }
                    let params: Vec<String> =
                        f2.params.iter().map(|(_, t)| t.clone()).collect();
                    return Ok(fmt_fn_type(&params, f2.return_type.as_deref()));
                }
                if f.is_lambda {
                    return Err(err(
                        "E402",
                        format!(
                            "unknown variable '{name}': it is not defined where this function value \
                             is written, nor in it"
                        ),
                        *line,
                        vec![
                            format!("declare it first: let {name} = ..."),
                            "or pass it in as a parameter".to_string(),
                        ],
                    ));
                }
                if name == "break" || name == "continue" {
                    return Err(err(
                        "E402",
                        format!("there is no '{name}' in this language"),
                        *line,
                        fixes(&[
                            "use a condition in the loop test instead",
                            "or keep a flag: while going and i < n { ... }",
                        ]),
                    ));
                }
                return Err(err(
                    "E402",
                    format!("unknown variable '{name}'"),
                    *line,
                    vec![format!("declare it first: let {name} = ...")],
                ));
            }
            Expr::Not { value, line } => {
                let t = self.infer(cx, value, false)?;
                if strip_secret(&t) != "Bool" {
                    return Err(err(
                        "E501",
                        format!("'not' needs a yes/no value (Bool), but this is {t}"),
                        *line,
                        fixes(&["use it on a comparison like not (x > 0)"]),
                    ));
                }
                return Ok(t);
            }
            Expr::RecordLit { name, fields, line } => {
                let Some(want) = self.rec_fields(name).cloned() else {
                    return Err(err(
                        "E508",
                        format!("unknown record '{name}'"),
                        *line,
                        vec![format!("declare it first: record {name} {{ ... }}")],
                    ));
                };
                let want_of =
                    |f: &str| want.iter().find(|(n, _)| n == f).map(|(_, t)| t.clone());
                let names: Vec<&str> = want.iter().map(|(n, _)| n.as_str()).collect();
                let mut given: Vec<(String, String)> = Vec::new();
                for (fname, v) in fields {
                    let Some(w) = want_of(fname) else {
                        return Err(err(
                            "E509",
                            format!("record '{name}' has no field '{fname}'"),
                            *line,
                            vec![format!("its fields are: {}", names.join(", "))],
                        ));
                    };
                    if given.iter().any(|(n, _)| n == fname) {
                        return Err(err(
                            "E509",
                            format!("field '{fname}' is given twice"),
                            *line,
                            fixes(&["give each field exactly once"]),
                        ));
                    }
                    let g = self.infer(cx, v, false)?;
                    given.push((fname.clone(), g.clone()));
                    if currency_clash(&w, &g) {
                        return Err(clash_error(&w, &g, *line, &format!("field '{fname}'")));
                    }
                    if g != w {
                        return Err(err(
                            "E501",
                            format!("field '{fname}' of '{name}' holds {w}, but this is {g}"),
                            *line,
                            vec![format!("give {} {w} value", an(&w))],
                        ));
                    }
                }
                let missing: Vec<&str> = names
                    .iter()
                    .copied()
                    .filter(|n| !given.iter().any(|(g, _)| g == n))
                    .collect();
                if !missing.is_empty() {
                    return Err(err(
                        "E509",
                        format!("record '{name}' is missing field(s): {}", missing.join(", ")),
                        *line,
                        fixes(&["give every field a value"]),
                    ));
                }
                return Ok(name.clone());
            }
            Expr::FieldGet { obj, field, line } => {
                let t = self.infer(cx, obj, false)?;
                let Some(fs) = self.rec_fields(&t) else {
                    return Err(err(
                        "E510",
                        format!("{t} has no fields"),
                        *line,
                        fixes(&["only records have fields, accessed like p.x"]),
                    ));
                };
                return match fs.iter().find(|(n, _)| n == field) {
                    Some((_, ft)) => Ok(ft.clone()),
                    None => {
                        let names: Vec<&str> = fs.iter().map(|(n, _)| n.as_str()).collect();
                        Err(err(
                            "E510",
                            format!("record '{t}' has no field '{field}'"),
                            *line,
                            vec![format!("its fields are: {}", names.join(", "))],
                        ))
                    }
                };
            }
            Expr::MapLit { entries, line } => {
                if entries.is_empty() {
                    return Err(err(
                        "E506",
                        "cannot tell what an empty map holds",
                        *line,
                        fixes(&["put at least one entry in it, e.g. {\"a\": 0}"]),
                    ));
                }
                let kt = self.infer(cx, &entries[0].0, false)?;
                let vt = self.infer(cx, &entries[0].1, false)?;
                if kt != "Text" && kt != "Int" {
                    return Err(err(
                        "E501",
                        format!("map keys must be Text or Int, but this is {kt}"),
                        *line,
                        fixes(&["use Text or Int keys"]),
                    ));
                }
                let mut seen_const: HashSet<(bool, String)> = HashSet::new();
                for (k, v) in entries {
                    if self.infer(cx, k, false)? != kt {
                        let again = self.infer(cx, k, false)?;
                        return Err(err(
                            "E501",
                            format!("a map cannot mix {kt} and {again} keys"),
                            *line,
                            fixes(&["keep every key the same type"]),
                        ));
                    }
                    let vv = self.infer(cx, v, false)?;
                    if currency_clash(&vt, &vv) {
                        let again = self.infer(cx, v, false)?;
                        return Err(clash_error(&vt, &again, *line, "a value in this map"));
                    }
                    if self.infer(cx, v, false)? != vt {
                        let again = self.infer(cx, v, false)?;
                        return Err(err(
                            "E501",
                            format!("a map cannot mix {vt} and {again} values"),
                            *line,
                            fixes(&["keep every value the same type"]),
                        ));
                    }
                    let constant = match k {
                        Expr::Str { value } => Some((true, value.clone())),
                        Expr::Num { value } => Some((false, value.clone())),
                        _ => None,
                    };
                    if let Some(key) = constant {
                        if seen_const.contains(&key) {
                            return Err(err(
                                "E509",
                                format!("map key {} is given twice", expr_str(k)),
                                *line,
                                fixes(&["give each key once"]),
                            ));
                        }
                        seen_const.insert(key);
                    }
                }
                return Ok(format!("Map of {kt} to {vt}"));
            }
            Expr::ListLit { items, line } => {
                if items.is_empty() {
                    return Err(err(
                        "E506",
                        "cannot tell what an empty list holds",
                        *line,
                        fixes(&["put at least one item in it, e.g. [0]"]),
                    ));
                }
                let t0 = self.infer(cx, &items[0], false)?;
                for it in &items[1..] {
                    let t = self.infer(cx, it, false)?;
                    if currency_clash(&t0, &t) {
                        return Err(clash_error(&t0, &t, *line, "an item in this list"));
                    }
                    if t != t0 {
                        return Err(err(
                            "E501",
                            format!("a list cannot mix {t0} and {t}"),
                            *line,
                            fixes(&["keep every item in a list the same type"]),
                        ));
                    }
                }
                return Ok(format!("List of {t0}"));
            }
            Expr::BinOp { op, left, right, line } => {
                return self.infer_binop(cx, op, left, right, *line)
            }
            Expr::Call { .. } => {}
        }
        let Expr::Call { name, args, line } = node else {
            unreachable!("every other node answered above");
        };
        self.infer_call(cx, name, args, *line, allow_fail)
    }

    #[allow(clippy::too_many_lines)]
    fn infer_call(
        &mut self,
        cx: &Ctx<'a>,
        name: &str,
        args: &[Expr],
        line: u32,
        allow_fail: bool,
    ) -> R<String> {
        let local_fn = cx.env.get(name).is_some_and(|t| t.starts_with("fn("));

        // ---- the sink check (6.0), in one place ----
        if !local_fn {
            if let Some(emits) = self.sink_builtin(name) {
                let row = builtin(emits).expect("a sink is a builtin");
                let mut effs: Vec<&str> = row.effects.to_vec();
                effs.sort_unstable();
                let place = format!("'{emits}' performs {}", effs.join(", "));
                self.refuse_secret_args(cx, args, line, shown_name(name), &place)?;
            }
            if let Some(tells) = self.tattling_builtin(name) {
                let place = format!(
                    "'{tells}' can fail with a reason the runtime builds out of the values it was \
                     given, which the program can then print"
                );
                self.refuse_secret_args(cx, args, line, shown_name(name), &place)?;
            }
        }

        if name == "all_of" || name == "any_of" {
            if args.len() != 2 {
                return Err(err(
                    "E401",
                    format!("'{name}' expects 2 argument(s) but got {}", args.len()),
                    line,
                    fixes(&["pass a list and a predicate function"]),
                ));
            }
            let t0 = self.infer(cx, &args[0], false)?;
            let Some(elem) = t0.strip_prefix("List of ").map(str::to_string) else {
                return Err(err(
                    "E501",
                    format!("'{name}' needs a list first, but this is {t0}"),
                    line,
                    fixes(&["pass a list"]),
                ));
            };
            let want_p = fmt_fn_type(std::slice::from_ref(&elem), Some("Bool"));
            let pf = match &args[1] {
                Expr::Var { name: pname, .. } if !cx.env.contains_key(pname) => {
                    self.table.get(pname.as_str()).copied()
                }
                _ => None,
            };
            if let Some(pf) = pf {
                if currency_generic(pf) && is_money(&elem) {
                    let ptypes: Vec<&str> =
                        pf.params.iter().map(|(_, t)| t.as_str()).collect();
                    if ptypes.len() != 1
                        || !is_money(ptypes[0])
                        || pf.return_type.as_deref().unwrap_or("Unit") != "Bool"
                    {
                        return Err(err(
                            "E501",
                            format!(
                                "'{name}' needs a {want_p} predicate, but '{}' is not one",
                                pf.name
                            ),
                            line,
                            vec![format!("pass a function taking {elem} and returning Bool")],
                        ));
                    }
                    if !pf.effects.is_empty() || pf.can_fail {
                        return Err(err(
                            "E530",
                            format!(
                                "'{}' has effects or can fail - only pure functions can be passed \
                                 as values",
                                pf.name
                            ),
                            line,
                            fixes(&["pass a function with no 'uses' clause and no 'or fail'"]),
                        ));
                    }
                    let cur = &ptypes[0]["Money of ".len()..];
                    if !pf.type_vars.iter().any(|v| v == cur) && ptypes[0] != elem {
                        return Err(clash_error(ptypes[0], &elem, line, "each item"));
                    }
                    return Ok("Bool".to_string());
                }
            }
            let t1 = self.infer(cx, &args[1], false)?;
            if t1 != want_p {
                return Err(err(
                    "E501",
                    format!("'{name}' needs a {want_p} predicate, but this is {t1}"),
                    line,
                    vec![format!("pass a function taking {elem} and returning Bool")],
                ));
            }
            return Ok(if self.carries(&t0) {
                wrap_secret("Bool")
            } else {
                "Bool".to_string()
            });
        }

        if matches!(
            name,
            "length"
                | "push"
                | "get"
                | "put"
                | "has"
                | "keys"
                | "get_or"
                | "pop"
                | "slice"
                | "set_at"
        ) {
            return self.infer_container(cx, name, args, line, allow_fail);
        }

        if local_fn {
            let sig = cx.env.get(name).cloned().unwrap_or_default();
            let (parts, ret) = fn_sig_parts(&sig).unwrap_or_default();
            if args.len() != parts.len() {
                return Err(err(
                    "E401",
                    format!(
                        "'{name}' expects {} argument(s) but got {}",
                        parts.len(),
                        args.len()
                    ),
                    line,
                    vec![format!("pass exactly {} argument(s)", parts.len())],
                ));
            }
            for (i, (a, want)) in args.iter().zip(&parts).enumerate() {
                let got = self.infer(cx, a, false)?;
                if currency_clash(want, &got) {
                    return Err(clash_error(want, &got, line, &format!("argument {}", i + 1)));
                }
                if &got != want {
                    return Err(err(
                        "E501",
                        format!(
                            "'{name}' needs {want} for argument {}, but this is {got}",
                            i + 1
                        ),
                        line,
                        vec![format!("pass a {want} value")],
                    ));
                }
            }
            return Ok(ret);
        }

        let reached = self.reached(name);
        if !allow_fail && reached.is_some_and(is_fallible) {
            let said = shown_name(name);
            return Err(err(
                "E520",
                format!("'{said}' can fail - that cannot be ignored"),
                line,
                vec![
                    format!("handle it: check {said}(...) {{ ok v {{ ... }} fail reason {{ ... }} }}"),
                    format!("or pass it up (inside a fallible function): try {said}(...)"),
                ],
            ));
        }

        if reached == Some("declassify") {
            let said = shown_name(name);
            if args.len() != 2 {
                return Err(err(
                    "E401",
                    format!("'{said}' expects 2 argument(s) but got {}", args.len()),
                    line,
                    fixes(&["pass the secret and a reason: declassify(key, \"the vendor needs it\")"]),
                ));
            }
            let t0 = self.infer(cx, &args[0], false)?;
            if !is_secret(&t0) {
                let more = if self.carries(&t0) {
                    " - the secret is inside it, so take that out first"
                } else {
                    ""
                };
                return Err(err(
                    "E561",
                    format!("'{said}' takes a Secret, but this is {t0}{more}"),
                    line,
                    fixes(&["declassify the Secret itself, not what holds it"]),
                ));
            }
            let Expr::Str { value: reason } = &args[1] else {
                return Err(err(
                    "E561",
                    format!("the reason given to '{said}' must be written as text in the call"),
                    line,
                    fixes(&[
                        "write it here: declassify(x, \"the vendor authenticates with this key\")",
                        "a reason built while running cannot be read by the audit, so it would \
                         say that a secret leaves and not why",
                    ]),
                ));
            };
            if py_strip(reason).is_empty() {
                return Err(err(
                    "E561",
                    format!("the reason given to '{said}' is empty"),
                    line,
                    fixes(&[
                        "say why this value is safe to let out; it is what an operator reads in \
                         the audit",
                    ]),
                ));
            }
            return Ok(secret_inner(&t0).to_string());
        }

        if reached.is_some_and(|b| HMAC_BUILTINS.contains(&b)) {
            let said = shown_name(name);
            if args.len() != 2 {
                return Err(err(
                    "E401",
                    format!("'{said}' expects 2 argument(s) but got {}", args.len()),
                    line,
                    vec![format!("pass the key and what to sign: {said}(key, message)")],
                ));
            }
            let t0 = self.infer(cx, &args[0], false)?;
            if t0 != wrap_secret("Text") {
                return Err(err(
                    "E561",
                    format!("'{said}' takes its key as a Secret of Text, but this is {t0}"),
                    line,
                    fixes(&[
                        "read the key with env() or read_file_secret(), which give a Secret of \
                         Text; a key that is not a secret needs no protecting and cannot be given \
                         here",
                    ]),
                ));
            }
            let want = if reached == Some("hmac_sha256") { "Text" } else { "List of Text" };
            let t1 = self.infer(cx, &args[1], false)?;
            if self.carries(&t1) {
                let origin = self.origin_of(cx, &args[1]);
                return Err(Self::leak(
                    &format!("argument 2 of '{said}'"),
                    &format!("the result of '{said}' is not a Secret, so what it signs would leave as a digest"),
                    &t1,
                    &origin,
                    line,
                ));
            }
            if t1 != want {
                return Err(err(
                    "E501",
                    format!("'{said}' needs {want} for argument 2, but this is {t1}"),
                    line,
                    vec![format!("pass a {want} value")],
                ));
            }
            return Ok("Text".to_string());
        }

        if let Some(b) = reached.filter(|b| MONEY_BUILTINS.contains(b)) {
            return self.money_call(cx, b, args, line);
        }

        if let Some(cg) = self.table.get(name).copied().filter(|cg| !cg.type_vars.is_empty()) {
            return self.generic_call(cx, cg, name, args, line, allow_fail);
        }

        if let Some(cfn) = self.table.get(name) {
            if cfn.can_fail && !allow_fail {
                return Err(err(
                    "E520",
                    format!("'{name}' can fail - that cannot be ignored"),
                    line,
                    vec![
                        format!("handle it: check {name}(...) {{ ok v {{ ... }} fail reason {{ ... }} }}"),
                        format!("or pass it up (inside a fallible function): try {name}(...)"),
                    ],
                ));
            }
        }
        let (ptypes, ret) = self.callee_sig(name, line)?;
        if name == "format" {
            if args.is_empty() {
                return Err(err(
                    "E401",
                    "'format' needs the text first",
                    line,
                    fixes(&["write: format(\"hi {}\", name)"]),
                ));
            }
            let t_fmt = self.infer(cx, &args[0], false)?;
            if strip_secret(&t_fmt) != "Text" {
                return Err(err(
                    "E501",
                    "'format' needs Text as its first argument",
                    line,
                    fixes(&["write: format(\"hi {}\", name)"]),
                ));
            }
            let mut secret_in = self.carries(&t_fmt);
            for a in &args[1..] {
                let t = self.infer(cx, a, false)?;
                secret_in = self.carries(&t) || secret_in;
            }
            if let Expr::Str { value } = &args[0] {
                let holes = value.matches("{}").count();
                let given = args.len() - 1;
                if holes != given {
                    return Err(err(
                        "E406",
                        format!(
                            "this text has {holes} placeholder(s) but got {given} value(s)"
                        ),
                        line,
                        vec![
                            format!("pass exactly {holes} value(s)"),
                            "each {} takes one value".to_string(),
                        ],
                    ));
                }
            }
            return Ok(if secret_in { wrap_secret("Text") } else { "Text".to_string() });
        }
        if args.len() != ptypes.len() {
            return Err(err(
                "E401",
                format!(
                    "'{name}' expects {} argument(s) but got {}",
                    ptypes.len(),
                    args.len()
                ),
                line,
                vec![format!("pass exactly {} argument(s)", ptypes.len())],
            ));
        }
        let mut secret_in = false;
        for (i, (arg, want)) in args.iter().zip(&ptypes).enumerate() {
            let i = i + 1;
            let mut got = self.infer(cx, arg, false)?;
            if got == "Unit" {
                return Err(err(
                    "E502",
                    format!("argument {i} of '{name}' is a call to a function that returns nothing"),
                    line,
                    fixes(&["call a function that returns a value here"]),
                ));
            }
            if currency_clash(want, &got) {
                return Err(clash_error(
                    want,
                    &got,
                    line,
                    &format!("argument {i} of '{name}'"),
                ));
            }
            if self.carries(&got) && self.reached(name).is_some() {
                if want == "Any" {
                    secret_in = true;
                } else if &strip_secret(&got) == want {
                    secret_in = true;
                    got = strip_secret(&got);
                }
            }
            if want != "Any" && &got != want {
                if self.in_table(name)
                    && builtin(name).is_some()
                    && self.reached(name).is_some()
                {
                    return Err(err(
                        "E501",
                        format!(
                            "'{name}' here is the builtin, which needs {want} for argument {i}; the \
                             function '{name}' of this program is hidden by it"
                        ),
                        line,
                        vec![
                            format!("rename your '{name}'"),
                            "or import its file with a name: import \"money.vel\" as money".to_string(),
                        ],
                    ));
                }
                return Err(err(
                    "E501",
                    format!("'{name}' needs {want} for argument {i}, but this is {got}"),
                    line,
                    vec![
                        format!("pass {} {want} value instead", an(want)),
                        format!("or change the parameter type to {got}"),
                    ],
                ));
            }
        }
        Ok(if secret_in { wrap_secret(&ret) } else { ret })
    }

    #[allow(clippy::too_many_lines)]
    fn infer_container(
        &mut self,
        cx: &Ctx<'a>,
        name: &str,
        args: &[Expr],
        line: u32,
        allow_fail: bool,
    ) -> R<String> {
        let n_want = match name {
            "push" | "get" | "has" => 2,
            "put" | "get_or" | "slice" | "set_at" => 3,
            _ => 1, // length, keys, pop
        };
        if args.len() != n_want {
            return Err(err(
                "E401",
                format!("'{name}' expects {n_want} argument(s) but got {}", args.len()),
                line,
                vec![format!("pass exactly {n_want} argument(s)")],
            ));
        }
        let mut t0 = self.infer(cx, &args[0], false)?;
        // a container that is itself secret is read as what it holds, and
        // everything taken out of it comes back secret
        let sec0 = is_secret(&t0);
        if sec0 {
            t0 = secret_inner(&t0).to_string();
        }
        let keep = |me: &Self, t: &str| -> String {
            if sec0 && !me.carries(t) {
                format!("{SECRET_PREFIX}{t}")
            } else {
                t.to_string()
            }
        };
        let is_map = t0.starts_with("Map of ");
        let (key_t, val_t) = match t0.strip_prefix("Map of ") {
            Some(rest) => match rest.split_once(" to ") {
                Some((k, v)) => (k.to_string(), v.to_string()),
                None => (rest.to_string(), String::new()),
            },
            None => (String::new(), String::new()),
        };
        if matches!(name, "pop" | "slice" | "set_at") {
            if !allow_fail {
                return Err(err(
                    "E520",
                    format!("'{name}' can fail - that cannot be ignored"),
                    line,
                    vec![
                        format!("handle it: check {name}(...) {{ ok v {{ ... }} fail why {{ ... }} }}"),
                        format!("or pass it up (inside a fallible function): try {name}(...)"),
                    ],
                ));
            }
            let Some(elem_t) = t0.strip_prefix("List of ").map(str::to_string) else {
                return Err(err(
                    "E501",
                    format!("'{name}' works on a list, not {t0}"),
                    line,
                    vec![format!("pass a list to '{name}'")],
                ));
            };
            if name == "set_at" {
                let want = elem_t;
                let got = self.infer(cx, &args[2], false)?;
                if currency_clash(&want, &got) {
                    return Err(clash_error(&want, &got, line, ""));
                }
                if got != want && want != "Any" {
                    return Err(err(
                        "E501",
                        format!("this list holds {want}, so 'set_at' cannot put {got} in it"),
                        line,
                        vec![format!("pass a {want}")],
                    ));
                }
            }
            let upto = if name == "slice" { 3 } else { 2 };
            for arg in args.iter().take(upto).skip(1) {
                if name != "pop" && self.infer(cx, arg, false)? != "Int" {
                    return Err(err(
                        "E501",
                        format!("'{name}' takes whole-number positions"),
                        line,
                        fixes(&["pass an Int"]),
                    ));
                }
            }
            return Ok(keep(self, &t0));
        }
        if name == "length" {
            if t0 == "Text" || t0.starts_with("List of ") || is_map {
                return Ok(keep(self, "Int"));
            }
            return Err(err(
                "E501",
                format!("'length' works on Text, a list, or a map, but this is {t0}"),
                line,
                fixes(&["pass a Text value, list, or map"]),
            ));
        }
        if name == "keys" {
            if !is_map {
                return Err(err(
                    "E501",
                    format!("'keys' works on a map, but this is {t0}"),
                    line,
                    fixes(&["pass a map"]),
                ));
            }
            return Ok(keep(self, &format!("List of {key_t}")));
        }
        if name == "has" || name == "put" {
            if !is_map {
                return Err(err(
                    "E501",
                    format!("'{name}' works on a map, but this is {t0}"),
                    line,
                    fixes(&["pass a map as the first argument"]),
                ));
            }
            if self.infer(cx, &args[1], false)? != key_t {
                let again = self.infer(cx, &args[1], false)?;
                return Err(err(
                    "E501",
                    format!("this map has {key_t} keys, but this key is {again}"),
                    line,
                    vec![format!("use {} {key_t} key", an(&key_t))],
                ));
            }
            if name == "has" {
                return Ok(keep(self, "Bool"));
            }
            let v = self.infer(cx, &args[2], false)?;
            if currency_clash(&val_t, &v) {
                let again = self.infer(cx, &args[2], false)?;
                return Err(clash_error(&val_t, &again, line, ""));
            }
            if self.infer(cx, &args[2], false)? != val_t {
                let again = self.infer(cx, &args[2], false)?;
                return Err(err(
                    "E501",
                    format!("this map holds {val_t} values, cannot put {again}"),
                    line,
                    vec![format!("put {} {val_t} value", an(&val_t))],
                ));
            }
            return Ok(keep(self, &t0));
        }
        if name == "get_or" {
            if !is_map {
                return Err(err(
                    "E501",
                    format!("'get_or' works on a map, but this is {t0}"),
                    line,
                    fixes(&["pass a map first"]),
                ));
            }
            if self.infer(cx, &args[1], false)? != key_t {
                let again = self.infer(cx, &args[1], false)?;
                return Err(err(
                    "E501",
                    format!("this map has {key_t} keys, but this key is {again}"),
                    line,
                    vec![format!("use {} {key_t} key", an(&key_t))],
                ));
            }
            let v = self.infer(cx, &args[2], false)?;
            if currency_clash(&val_t, &v) {
                let again = self.infer(cx, &args[2], false)?;
                return Err(clash_error(&val_t, &again, line, "the default"));
            }
            if self.infer(cx, &args[2], false)? != val_t {
                let again = self.infer(cx, &args[2], false)?;
                return Err(err(
                    "E501",
                    format!("this map holds {val_t} values, but the default is {again}"),
                    line,
                    vec![format!("use {} {val_t} default", an(&val_t))],
                ));
            }
            return Ok(keep(self, &val_t));
        }
        if name == "get" && is_map {
            if !allow_fail {
                return Err(err(
                    "E520",
                    "'get' on a map can fail - the key may be missing, and that cannot be ignored",
                    line,
                    fixes(&[
                        "handle it: check get(m, key) { ok v { ... } fail why { ... } }",
                        "or use get_or(m, key, default) which never fails",
                        "or pass it up with: try get(m, key)",
                    ]),
                ));
            }
            if self.infer(cx, &args[1], false)? != key_t {
                let again = self.infer(cx, &args[1], false)?;
                return Err(err(
                    "E501",
                    format!("this map has {key_t} keys, but this key is {again}"),
                    line,
                    vec![format!("use {} {key_t} key", an(&key_t))],
                ));
            }
            return Ok(keep(self, &val_t));
        }
        let Some(elem) = t0.strip_prefix("List of ").map(str::to_string) else {
            let more = if name == "push" { " - use put for maps" } else { "" };
            return Err(err(
                "E501",
                format!("'{name}' needs a list first, but this is {t0}{more}"),
                line,
                fixes(&["pass a list as the first argument"]),
            ));
        };
        let t1 = self.infer(cx, &args[1], false)?;
        if name == "push" {
            if currency_clash(&elem, &t1) {
                return Err(clash_error(&elem, &t1, line, "what is pushed"));
            }
            if t1 != elem {
                return Err(err(
                    "E501",
                    format!("this list holds {elem}, cannot push a {t1} into it"),
                    line,
                    vec![format!("push {} {elem} value", an(&elem))],
                ));
            }
            return Ok(keep(self, &t0));
        }
        if t1 != "Int" {
            return Err(err(
                "E501",
                format!("'get' needs an Int position, but this is {t1}"),
                line,
                fixes(&["positions are numbers, e.g. get(xs, 0)"]),
            ));
        }
        Ok(keep(self, &elem))
    }

    fn generic_call(
        &mut self,
        cx: &Ctx<'a>,
        cg: &'a Function,
        name: &str,
        args: &[Expr],
        line: u32,
        allow_fail: bool,
    ) -> R<String> {
        if cg.can_fail && !allow_fail {
            return Err(err(
                "E520",
                format!("'{name}' can fail - that cannot be ignored"),
                line,
                vec![
                    "handle it with a check block".to_string(),
                    format!("or pass it up with try {name}(...)"),
                ],
            ));
        }
        let ptypes: Vec<&str> = cg.params.iter().map(|(_, t)| t.as_str()).collect();
        if args.len() != ptypes.len() {
            return Err(err(
                "E401",
                format!(
                    "'{name}' expects {} argument(s) but got {}",
                    ptypes.len(),
                    args.len()
                ),
                line,
                vec![format!("pass exactly {} argument(s)", ptypes.len())],
            ));
        }
        let mut bind: Vec<(String, String)> = Vec::new();
        for (i, (a, want)) in args.iter().zip(&ptypes).enumerate() {
            let got = self.infer(cx, a, false)?;
            if !unify(&cg.type_vars, &mut bind, want, &got) {
                let shown = subst(&bind, want);
                if currency_clash(&shown, &got) {
                    return Err(clash_error(
                        &shown,
                        &got,
                        line,
                        &format!("argument {}", i + 1),
                    ));
                }
                let so_far: Vec<String> =
                    bind.iter().map(|(k, v)| format!("{k} = {v}")).collect();
                let tail = if so_far.is_empty() {
                    String::new()
                } else {
                    format!(" (so far: {})", so_far.join(", "))
                };
                return Err(err(
                    "E542",
                    format!("'{name}' argument {} should look like {want}, but this is {got}{tail}", i + 1),
                    line,
                    vec![format!("make the arguments agree on what {} is", cg.type_vars.join(", "))],
                ));
            }
        }
        // no type variable is ever bound to a type that carries a secret
        for (tv, bound) in bind.clone() {
            if self.carries(&bound) {
                let at =
                    ptypes.iter().position(|w| type_mentions(w, &tv)).map_or(1, |j| j + 1);
                let origin = self.origin_of(cx, &args[at - 1]);
                return Err(Self::leak(
                    &format!("argument {at} of '{name}'"),
                    &format!(
                        "'{name}' is generic, and its body was checked without knowing that {tv} \
                         could be a secret - so it may compare one, or hand one to to_text, and give \
                         the answer back as an ordinary value"
                    ),
                    &bound,
                    &origin,
                    line,
                ));
            }
        }
        Ok(subst(&bind, cg.return_type.as_deref().unwrap_or("Unit")))
    }

    // ---- operators -------------------------------------------------------

    fn infer_binop(
        &mut self,
        cx: &Ctx<'a>,
        op: &str,
        left: &Expr,
        right: &Expr,
        line: u32,
    ) -> R<String> {
        let mut l = self.infer(cx, left, false)?;
        let mut r = self.infer(cx, right, false)?;
        let secret_in = self.carries(&l) || self.carries(&r);
        if secret_in {
            l = strip_secret(&l);
            r = strip_secret(&r);
        }
        let kept = |t: &str| -> String {
            if secret_in && !carries_secret(t, None) {
                format!("{SECRET_PREFIX}{t}")
            } else {
                t.to_string()
            }
        };
        if l == "Unit" || r == "Unit" {
            return Err(err(
                "E502",
                "this expression uses a function that returns nothing",
                line,
                fixes(&["only use functions that return a value in math/text"]),
            ));
        }
        if op == "and" || op == "or" {
            if l == "Bool" && r == "Bool" {
                return Ok(kept("Bool"));
            }
            return Err(err(
                "E501",
                format!("'{op}' needs yes/no values (Bool) on both sides, but this is {l} {op} {r}"),
                line,
                fixes(&["use comparisons on both sides, like x > 0 and x < 10"]),
            ));
        }
        if (is_money(&l) || is_money(&r)) && !(op == "+" && (l == "Text" || r == "Text")) {
            let got = Self::money_op(op, &l, &r, line)?;
            return Ok(if got == "Bool" { got } else { kept(&got) });
        }
        if op == "+" {
            if l == "Text" || r == "Text" {
                return Ok(kept("Text"));
            }
            if l == r && (l == "Int" || l == "Float") {
                return Ok(kept(&l));
            }
            return Err(err("E501", format!("cannot add {l} and {r}"), line, num_fix()));
        }
        if op == "%" {
            if l == "Int" && r == "Int" {
                return Ok(kept("Int"));
            }
            return Err(err(
                "E501",
                format!("'%' needs Int on both sides, but this is {l} % {r}"),
                line,
                fixes(&["make both sides Int"]),
            ));
        }
        if op == "-" || op == "*" || op == "/" {
            if l == r && (l == "Int" || l == "Float") {
                return Ok(kept(&l));
            }
            return Err(err(
                "E501",
                format!("'{op}' needs matching number types, but this is {l} {op} {r}"),
                line,
                num_fix(),
            ));
        }
        if matches!(op, "<" | ">" | "<=" | ">=") {
            if l == r && (l == "Int" || l == "Float" || l == "Text") {
                return Ok(kept("Bool"));
            }
            return Err(err(
                "E501",
                format!("'{op}' compares two Ints, two Floats, or two Texts, but this is {l} {op} {r}"),
                line,
                num_fix(),
            ));
        }
        if l != r {
            return Err(err(
                "E501",
                format!("cannot compare {l} with {r}"),
                line,
                fixes(&["compare values of the same type"]),
            ));
        }
        Ok(kept("Bool"))
    }

    // ---- Money (4.3) -----------------------------------------------------

    fn money_op(op: &str, l: &str, r: &str, line: u32) -> R<String> {
        let (lm, rm) = (is_money(l), is_money(r));
        if op == "/" || op == "%" {
            if lm && !rm {
                return Err(err(
                    "E553",
                    format!("'{op}' on an amount would round without saying how"),
                    line,
                    fixes(&[
                        "divide_or_fail(amount, n, \"half_even\") names the rounding",
                        "money.split(amount, n) makes n parts that add up to the amount exactly",
                        "percent_of(amount, numerator, denominator, \"half_up\") for a share",
                    ]),
                ));
            }
            return Err(err(
                "E501",
                format!("'{op}' cannot divide by an amount: this is {l} {op} {r}"),
                line,
                units_fix(),
            ));
        }
        if l == "Float" || r == "Float" {
            return Err(err(
                "E501",
                format!("an amount never meets a Float: this is {l} {op} {r}"),
                line,
                fixes(&[
                    "a Float cannot hold 0.10 exactly; keep the amount in minor units",
                    "percent_of(amount, 25, 1000, \"half_up\") takes 2.5 per cent without one",
                ]),
            ));
        }
        if op == "*" {
            if lm && rm {
                return Err(err(
                    "E501",
                    format!("an amount times an amount has no meaning: this is {l} * {r}"),
                    line,
                    fixes(&[
                        "multiply an amount by an Int: price * 3",
                        "percent_of(amount, numerator, denominator, \"half_up\") for a share of one",
                    ]),
                ));
            }
            let other = if lm { r } else { l };
            if other != "Int" {
                return Err(err(
                    "E501",
                    format!("an amount multiplies by an Int, not {other}"),
                    line,
                    fixes(&["multiply an amount by an Int: price * 3"]),
                ));
            }
            return Ok(if lm { l } else { r }.to_string());
        }
        if lm && rm {
            if l != r {
                let what = if op == "+" || op == "-" { "the right side" } else { "one side" };
                return Err(clash_error(l, r, line, what));
            }
            return Ok(if op == "+" || op == "-" {
                l.to_string()
            } else {
                "Bool".to_string()
            });
        }
        if op == "+" || op == "-" {
            return Err(err(
                "E501",
                format!("an amount adds only to an amount: this is {l} {op} {r}"),
                line,
                units_fix(),
            ));
        }
        Err(err(
            "E501",
            format!("an amount compares only with an amount: this is {l} {op} {r}"),
            line,
            fixes(&[
                "compare with an amount: m >= money(0, \"INR\")",
                "or compare units_of(m) with an Int",
            ]),
        ))
    }

    fn written_currency(arg: &Expr, line: u32) -> R<String> {
        let Expr::Str { value } = arg else {
            return Err(err(
                "E551",
                "the currency must be written in the call, as text",
                line,
                fixes(&["write it there: money(1250, \"INR\")"]),
            ));
        };
        if !is_currency(value) {
            return Err(Self::unknown_currency(value, line));
        }
        Ok(value.clone())
    }

    fn written_rounding(arg: &Expr, line: u32) -> R<()> {
        match arg {
            Expr::Str { value } if ROUNDING.contains(&value.as_str()) => Ok(()),
            _ => Err(err(
                "E552",
                "the rounding mode must be written in the call: \"half_up\", \"half_even\" or \"down\"",
                line,
                fixes(&[
                    "\"half_up\" takes a half away from zero, \"half_even\" to the even neighbour, \
                     \"down\" toward zero",
                    "there is no default: a division that does not come out even says how it rounds",
                ]),
            )),
        }
    }

    fn money_call(&mut self, cx: &Ctx<'a>, b: &str, args: &[Expr], line: u32) -> R<String> {
        let want_n = match b {
            "money" | "with_units" | "parse_money" => 2,
            "units_of" | "text_of" => 1,
            "percent_of" => 4,
            _ => 3, // divide_or_fail
        };
        if args.len() != want_n {
            return Err(err(
                "E401",
                format!("'{b}' expects {want_n} argument(s) but got {}", args.len()),
                line,
                vec![format!("pass exactly {want_n} argument(s)")],
            ));
        }
        let mut types = Vec::with_capacity(args.len());
        for a in args {
            types.push(self.infer(cx, a, false)?);
        }
        let need = |i: usize, want: &str| -> R<()> {
            if types[i] != want {
                return Err(err(
                    "E501",
                    format!(
                        "'{b}' needs {want} for argument {}, but this is {}",
                        i + 1,
                        types[i]
                    ),
                    line,
                    vec![format!("pass {} {want}", an(want))],
                ));
            }
            Ok(())
        };
        let amount = |i: usize| -> R<String> {
            if !is_money(&types[i]) {
                return Err(err(
                    "E501",
                    format!(
                        "'{b}' needs an amount for argument {}, but this is {}",
                        i + 1,
                        types[i]
                    ),
                    line,
                    units_fix(),
                ));
            }
            Ok(types[i].clone())
        };
        match b {
            "money" | "parse_money" => {
                need(0, if b == "money" { "Int" } else { "Text" })?;
                Ok(format!("Money of {}", Self::written_currency(&args[1], line)?))
            }
            "units_of" => {
                let t = &types[0];
                if is_money(t) || t.strip_prefix("List of ").is_some_and(is_money) {
                    return Ok("Int".to_string());
                }
                Err(err(
                    "E501",
                    format!(
                        "'units_of' takes an amount or a list of amounts, but this is {t}"
                    ),
                    line,
                    units_fix(),
                ))
            }
            "text_of" => {
                amount(0)?;
                Ok("Text".to_string())
            }
            "with_units" => {
                need(1, "Int")?;
                amount(0)
            }
            "percent_of" => {
                need(1, "Int")?;
                need(2, "Int")?;
                Self::written_rounding(&args[3], line)?;
                amount(0)
            }
            _ => {
                need(1, "Int")?;
                Self::written_rounding(&args[2], line)?;
                amount(0)
            }
        }
    }

    // ---- statements ------------------------------------------------------

    #[allow(clippy::too_many_lines)]
    fn check_stmt(&mut self, cx: &mut Ctx<'a>, node: &Stmt) -> R<()> {
        let f = cx.f;
        match node {
            Stmt::Let { name, value, line, ann } => {
                self.no_shadow(name, *line)?;
                if let Some(ann) = ann {
                    if !self.valid_type(ann, &f.type_vars) {
                        return Err(self.bad_type(
                            ann,
                            &f.type_vars,
                            format!("unknown type '{ann}'"),
                            *line,
                        ));
                    }
                    let empty_list =
                        matches!(value, Expr::ListLit { items, .. } if items.is_empty());
                    let empty_map =
                        matches!(value, Expr::MapLit { entries, .. } if entries.is_empty());
                    if empty_list || empty_map {
                        let want_kind = if empty_list { "List of " } else { "Map of " };
                        if !ann.starts_with(want_kind) {
                            return Err(err(
                                "E501",
                                format!(
                                    "'{name}' is declared {ann}, but this is an empty {}",
                                    if empty_list { "list" } else { "map" }
                                ),
                                *line,
                                fixes(&["match the declared type and the value"]),
                            ));
                        }
                        cx.env.insert(name.clone(), ann.clone());
                        return Ok(());
                    }
                    let t = self.infer(cx, value, false)?;
                    if currency_clash(ann, &t) {
                        return Err(clash_error(ann, &t, *line, &format!("'{name}'")));
                    }
                    if &t != ann {
                        return Err(err(
                            "E501",
                            format!("'{name}' is declared {ann}, but this is {t}"),
                            *line,
                            vec![
                                format!("give {} {ann} value", an(ann)),
                                "or fix the declared type".to_string(),
                            ],
                        ));
                    }
                    cx.env.insert(name.clone(), t.clone());
                    if self.carries(&t) {
                        let o = self.origin_of(cx, value);
                        cx.origins.insert(name.clone(), o);
                    }
                    return Ok(());
                }
                let t = self.infer(cx, value, false)?;
                if t == "Unit" {
                    return Err(err(
                        "E502",
                        format!("'{name}' would hold nothing: that function returns no value"),
                        *line,
                        fixes(&["assign a function that returns a value"]),
                    ));
                }
                cx.env.insert(name.clone(), t.clone());
                if self.carries(&t) {
                    let o = self.origin_of(cx, value);
                    cx.origins.insert(name.clone(), o);
                }
            }
            Stmt::Return { value, line } => {
                let Some(value) = value else {
                    if cx.declared_ret != "Unit" {
                        return Err(err(
                            "E503",
                            format!(
                                "'{}' promises to return {} but this return gives nothing",
                                f.name, cx.declared_ret
                            ),
                            *line,
                            vec![format!("return a {} value", cx.declared_ret)],
                        ));
                    }
                    return Ok(());
                };
                let t = self.infer(cx, value, false)?;
                if cx.declared_ret == "Unit" {
                    return Err(err(
                        "E503",
                        format!(
                            "'{}' does not declare a return type but returns a {t}",
                            f.name
                        ),
                        *line,
                        vec![
                            format!("add '-> {t}' to the signature of '{}'", f.name),
                            "or remove the returned value".to_string(),
                        ],
                    ));
                }
                if currency_clash(&cx.declared_ret, &t) {
                    return Err(clash_error(&cx.declared_ret, &t, *line, "what this returns"));
                }
                if t != cx.declared_ret {
                    return Err(err(
                        "E503",
                        format!(
                            "'{}' promises to return {} but this returns {t}",
                            f.name, cx.declared_ret
                        ),
                        *line,
                        vec![
                            format!("return a {} value", cx.declared_ret),
                            format!("or change the signature to '-> {t}'"),
                        ],
                    ));
                }
            }
            Stmt::ExprStmt { expr, .. } => {
                self.infer(cx, expr, false)?;
            }
            Stmt::FailStmt { value, line } => {
                if !f.can_fail {
                    return Err(err(
                        "E523",
                        format!(
                            "'fail' is used, but '{}' does not declare it can fail",
                            f.name
                        ),
                        *line,
                        vec![format!("add 'or fail' to the signature of '{}'", f.name)],
                    ));
                }
                let t = self.infer(cx, value, false)?;
                if self.carries(&t) {
                    let origin = self.origin_of(cx, value);
                    return Err(Self::leak(
                        "the reason given to 'fail'",
                        "a failure's reason is shown to whoever runs the program",
                        &t,
                        &origin,
                        *line,
                    ));
                }
                if t != "Text" {
                    return Err(err(
                        "E501",
                        format!("'fail' needs a Text reason, but this is {t}"),
                        *line,
                        fixes(&["write a message: fail \"why\""]),
                    ));
                }
            }
            Stmt::Check { subject, line, ok_name, ok_body, fail_name, fail_body } => {
                let sname = match subject {
                    Expr::Call { name, .. } => name.as_str(),
                    _ => "",
                };
                let user_ok = self.table.get(sname).is_some_and(|c| c.can_fail);
                if !user_ok && !self.builtin_call_fallible(cx, subject) {
                    return Err(err(
                        "E522",
                        format!(
                            "'{}' cannot fail - call it directly, no check needed",
                            shown_name(sname)
                        ),
                        *line,
                        fixes(&["remove the check block"]),
                    ));
                }
                let rt = self.infer(cx, subject, true)?;
                if rt == "Unit" && ok_name.is_some() {
                    return Err(err(
                        "E525",
                        format!(
                            "'{sname}' returns nothing - write 'ok {{ ... }}' with no name"
                        ),
                        *line,
                        fixes(&["remove the name after ok"]),
                    ));
                }
                if rt != "Unit" && ok_name.is_none() {
                    return Err(err(
                        "E525",
                        "name the result: 'ok value { ... }'",
                        *line,
                        fixes(&["add a name after ok to hold the result"]),
                    ));
                }
                if let Some(ok) = ok_name {
                    cx.env.insert(ok.clone(), rt.clone());
                    if self.carries(&rt) {
                        let o = self.origin_of(cx, subject);
                        cx.origins.insert(ok.clone(), o);
                    }
                }
                for s in ok_body {
                    self.check_stmt(cx, s)?;
                }
                cx.env.insert(fail_name.clone(), "Text".to_string());
                for s in fail_body {
                    self.check_stmt(cx, s)?;
                }
            }
            Stmt::If { cond, then, other, line } => {
                let c = self.infer(cx, cond, false)?;
                let origin = self.origin_of(cx, cond);
                self.no_secret_branch("if", &c, *line, &origin)?;
                if c != "Bool" {
                    return Err(err(
                        "E504",
                        format!("'if' needs a yes/no condition (Bool), but this is {c}"),
                        *line,
                        fixes(&["use a comparison like x > 0"]),
                    ));
                }
                for s in then.iter().chain(other) {
                    self.check_stmt(cx, s)?;
                }
            }
            Stmt::While { cond, body, line, invariants } => {
                let c = self.infer(cx, cond, false)?;
                let origin = self.origin_of(cx, cond);
                self.no_secret_branch("while", &c, *line, &origin)?;
                if c != "Bool" {
                    return Err(err(
                        "E504",
                        format!("'while' needs a yes/no condition (Bool), but this is {c}"),
                        *line,
                        fixes(&["use a comparison like i < 10"]),
                    ));
                }
                for (inv, iline) in invariants {
                    if strip_secret(&self.infer(cx, inv, false)?) != "Bool" {
                        return Err(err(
                            "E505",
                            "'invariant' must be a yes/no promise (Bool)",
                            *iline,
                            fixes(&["use a comparison like total >= 0"]),
                        ));
                    }
                }
                for s in body {
                    self.check_stmt(cx, s)?;
                }
            }
            Stmt::Assign { name, value, line } => {
                let Some(have) = cx.env.get(name).cloned() else {
                    return Err(err(
                        "E402",
                        format!("unknown variable '{name}'"),
                        *line,
                        vec![format!("declare it first: let {name} = ...")],
                    ));
                };
                let t = self.infer(cx, value, false)?;
                if currency_clash(&have, &t) {
                    return Err(clash_error(
                        &have,
                        &t,
                        *line,
                        &format!("what is put in '{name}'"),
                    ));
                }
                if t != have {
                    return Err(err(
                        "E501",
                        format!("'{name}' holds {have}, cannot put a {t} in it"),
                        *line,
                        vec![
                            format!("assign {} {have} value", an(&have)),
                            format!("or make a new variable: let {name}2 = ..."),
                        ],
                    ));
                }
                if self.carries(&t) {
                    let o = self.origin_of(cx, value);
                    cx.origins.insert(name.clone(), o);
                }
            }
            Stmt::Block { .. } => {}
        }
        Ok(())
    }
}

/// `unify(want, got)` of a generic call, binding type variables in `bind`
/// as it goes - and leaving what it bound in place when it then fails, as
/// the reference does, because the E542 message says what was bound "so far".
fn unify(tvars: &[String], bind: &mut Vec<(String, String)>, want: &str, got: &str) -> bool {
    if tvars.iter().any(|v| v == want) {
        if let Some((_, b)) = bind.iter().find(|(k, _)| k == want) {
            return b == got;
        }
        bind.push((want.to_string(), got.to_string()));
        return true;
    }
    if want == got {
        return true;
    }
    if is_money(want) && is_money(got) {
        return unify(tvars, bind, &want[9..], &got[9..]);
    }
    if is_secret(want) && is_secret(got) {
        return unify(tvars, bind, secret_inner(want), secret_inner(got));
    }
    if let (Some(w), Some(g)) = (want.strip_prefix("List of "), got.strip_prefix("List of ")) {
        return unify(tvars, bind, w, g);
    }
    if let (Some(w), Some(g)) = (want.strip_prefix("Map of "), got.strip_prefix("Map of ")) {
        let (wk, wv) = w.split_once(" to ").unwrap_or((w, ""));
        let (gk, gv) = g.split_once(" to ").unwrap_or((g, ""));
        return unify(tvars, bind, wk, gk) && unify(tvars, bind, wv, gv);
    }
    if let (Some((wp, wr)), Some((gp, gr))) = (fn_sig_parts(want), fn_sig_parts(got)) {
        return wp.len() == gp.len()
            && wp.iter().zip(&gp).all(|(a, b)| unify(tvars, bind, a, b))
            && unify(tvars, bind, &wr, &gr);
    }
    false
}

/// `subst(t)`: a type with every bound type variable replaced.
fn subst(bind: &[(String, String)], t: &str) -> String {
    if let Some((_, b)) = bind.iter().find(|(k, _)| k == t) {
        return b.clone();
    }
    if is_secret(t) {
        return format!("{SECRET_PREFIX}{}", subst(bind, secret_inner(t)));
    }
    if let Some(cur) = t.strip_prefix("Money of ") {
        return format!("Money of {}", subst(bind, cur));
    }
    if let Some(inner) = t.strip_prefix("List of ") {
        return format!("List of {}", subst(bind, inner));
    }
    if let Some(rest) = t.strip_prefix("Map of ") {
        let (k, v) = rest.split_once(" to ").unwrap_or((rest, ""));
        return format!("Map of {} to {}", subst(bind, k), subst(bind, v));
    }
    if let Some((parts, ret)) = fn_sig_parts(t) {
        let ps: Vec<String> = parts.iter().map(|p| subst(bind, p)).collect();
        return fmt_fn_type(&ps, Some(&subst(bind, &ret)));
    }
    t.to_string()
}
