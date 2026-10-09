//! The interpreter: `sabline/runtime.py`'s `build_runtime`, `run_builtin`
//! and `interpret`, transliterated (9.0, M3).
//!
//! **What runs here.** A program the loader read and the checkers passed,
//! under a budget, with its input, its arguments and - for the agreement
//! gate - a limit on how many calls and loop turns it may make, and on how
//! much it may make. Every builtin a run under any budget reaches is spent
//! against that budget first, as the reference spends it, and the work of
//! every builtin is ported but three kinds: the network, Python and a tool,
//! which are refused by every budget that does not grant them and answer
//! `NotPorted` under one that does (plan/9.0-m3-progress.md). A file
//! builtin is guarded as `budget.allow_path` guards it, counted as
//! `count_op` counts it and held to the read ceiling; what a run reaches of
//! the machine - the environment, `~`, randomness, a file's text - is
//! [`crate::host`]'s.
//!
//! **Why literal.** The reference's behaviour is its code: a promise's
//! message names its values as an f-string writes them, a failing `check`
//! catches only the subject's failure, an error is blamed on the file of
//! the innermost function whose body it rose through, a loop's invariants
//! are checked before the first turn and after every turn. Each of those
//! is copied here in the order the reference does it, because each is
//! something a program or its user can see.

use std::collections::{HashMap, HashSet};
use std::rc::Rc;

use crate::bigint::BigInt;
use crate::budget::{pct_encode, Budget, DEFAULT_ALLOW};
use crate::digest;
use crate::errors::SablineError;
use crate::host::{self, Environ, Twister};
use crate::loader::unknown_function;
use crate::nodes::{Expr, Function, RecordDef, Stmt};
use crate::pyjson;
use crate::pypath::{self, os_path};
use crate::show::{expr_str, nice_name};
use crate::tables::{
    builtin, is_builtin, is_new_builtin, CURRENCIES, MONEY_BUILTINS, ROUNDING,
};
use crate::text::{isspace, Text, TextBuf};
use crate::types::{carries_secret, records_carrying};
use crate::value::{
    currency_digits, fresh_float, item_eq, money_text, py_compare, py_eq, py_repr, py_str,
    to_text, Bound, Dict, Money, Raised, Record, Value,
};

/// The smallest whole number.
pub const INT_MIN: i64 = i64::MIN;
/// The largest whole number.
pub const INT_MAX: i64 = i64::MAX;
/// How deep a Sabline call may nest before it is E609.
pub const DEPTH_LIMIT: u32 = 2000;
/// What a broken promise prints in place of a value whose type holds a
/// secret: `tables.REDACTED`.
pub const REDACTED: &str = "<secret>";

/// An error a run stopped with: a `SablineError` whose message can quote
/// a value the program holds, and so is a Text.
#[derive(Debug, Clone, PartialEq)]
pub struct RunError {
    /// The code.
    pub code: &'static str,
    /// The message.
    pub message: Text,
    /// The line.
    pub line: u32,
    /// The fixes offered, in order.
    pub fixes: Vec<String>,
    /// The file, once a function's body it rose through has said.
    pub file: Option<String>,
}

impl From<SablineError> for RunError {
    fn from(e: SablineError) -> Self {
        RunError {
            code: e.code,
            message: Text::from(e.message),
            line: e.line,
            fixes: e.fixes,
            file: e.file,
        }
    }
}

/// What a run is given besides its budget and its input: `--seed`,
/// `--freeze-time` and `--max-read`, as `_state.SEED`, `_state.FROZEN_TIME`
/// and `_state.MAX_READ_BYTES` hold them.
#[derive(Debug, Clone)]
pub struct RunParams {
    /// What `random` is seeded with, or `None` for the system's randomness.
    pub seed: Option<i128>,
    /// What `now` answers, in seconds since 1970, or `None` for the clock.
    pub freeze_time: Option<i64>,
    /// The read ceiling, in bytes (E316).
    pub max_read: u64,
}

impl Default for RunParams {
    fn default() -> Self {
        RunParams { seed: None, freeze_time: None, max_read: 64 * 1024 * 1024 }
    }
}

/// What ended a stretch of a run early.
#[derive(Debug, Clone)]
pub enum Stop {
    /// A `SablineError`.
    Error(RunError),
    /// A `FailSignal`, and its reason.
    Fail(Value),
    /// `SystemExit`: `exit_with`'s number.
    Exit(i64),
    /// The step limit, at this line.
    Steps(u32),
    /// The size limit, at this line.
    Size(u32),
    /// A Python exception the reference would raise, by name: a defect in
    /// the reference, or a part of it not ported, that the comparison
    /// shows rather than hides.
    Raised(&'static str),
}

impl From<Raised> for Stop {
    fn from(r: Raised) -> Self {
        Stop::Raised(r.0)
    }
}

type R<T> = Result<T, Stop>;

fn error(code: &'static str, message: impl Into<Text>, line: u32, fixes: &[&str]) -> Stop {
    Stop::Error(RunError {
        code,
        message: message.into(),
        line,
        fixes: fixes.iter().map(|f| (*f).to_string()).collect(),
        file: None,
    })
}

/// `loader.blame`: an error with no file yet takes the function's - the
/// innermost frame wins.
fn blamed(src_file: &str, stop: Stop) -> Stop {
    match stop {
        Stop::Error(mut e) if e.file.is_none() && !src_file.is_empty() => {
            e.file = Some(src_file.to_string());
            Stop::Error(e)
        }
        other => other,
    }
}

fn fail(reason: impl Into<Text>) -> Stop {
    Stop::Fail(Value::Text(reason.into()))
}

/// What the program reads and writes: `sys.stdin`, `sys.stdout`,
/// `sys.stderr` and `args()`.
#[derive(Debug, Default)]
pub struct Io {
    /// What it printed.
    pub stdout: TextBuf,
    /// What it wrote to the error channel.
    pub stderr: TextBuf,
    stdin: Vec<u32>,
    at: usize,
    /// What `args()` answers.
    pub args: Vec<Text>,
}

impl Io {
    /// Input to read, as the library's `stdin=` gives it: a `StringIO`,
    /// whose lines end at a line feed alone.
    pub fn new(stdin: &str, args: Vec<Text>) -> Io {
        Io { stdin: stdin.chars().map(|c| c as u32).collect(), args, ..Io::default() }
    }

    /// `sys.stdin.readline()`: up to and including the next line feed, or
    /// the rest, or `""` at the end.
    fn readline(&mut self) -> Text {
        let rest = &self.stdin[self.at..];
        let n = rest.iter().position(|&c| c == 0x0A).map_or(rest.len(), |i| i + 1);
        let line = Text::from(rest[..n].to_vec());
        self.at += n;
        line
    }
}

enum Flow {
    Next,
    Return(Value),
}

/// A running program.
pub struct Runtime {
    table: HashMap<String, Rc<Function>>,
    hidden: HashSet<String>,
    secret: HashMap<String, (HashSet<String>, bool)>,
    depth: u32,
    ticks: u64,
    step_limit: Option<u64>,
    size_limit: Option<u64>,
    size_made: u64,
    budget: Budget,
    params: RunParams,
    rng: Option<Twister>,
    environ: Option<Environ>,
    fs_count: u64,
    /// How many builtin calls each effect let through: `EFFECT_USES`.
    pub effect_uses: HashMap<String, u64>,
    /// What each grant let through, by the grant's own text and in the
    /// order first used: `GRANT_USES`, what a receipt's `grants_used` is
    /// made from.
    pub grant_uses: Vec<(String, u64)>,
    /// The program's input and output.
    pub io: Io,
}

impl Runtime {
    /// `build_runtime(funcs)`: the table of functions, and what the type
    /// checker said holds a secret (for the messages that must not show
    /// one).
    pub fn new(funcs: &[Function], records: &[RecordDef], budget: Budget, io: Io) -> Runtime {
        let carrying = records_carrying(records);
        let table: HashMap<String, Rc<Function>> =
            funcs.iter().map(|f| (f.name.clone(), Rc::new(f.clone()))).collect();
        let hidden = table.keys().filter(|n| is_new_builtin(n)).cloned().collect();
        let secret = funcs
            .iter()
            .map(|f| {
                let params = f
                    .params
                    .iter()
                    .filter(|(_, t)| carries_secret(t, Some(&carrying)))
                    .map(|(p, _)| p.clone())
                    .collect();
                let result =
                    carries_secret(f.return_type.as_deref().unwrap_or(""), Some(&carrying));
                (f.name.clone(), (params, result))
            })
            .collect();
        Runtime {
            table,
            hidden,
            secret,
            depth: 0,
            ticks: 0,
            step_limit: None,
            size_limit: None,
            size_made: 0,
            budget,
            params: RunParams::default(),
            rng: None,
            environ: None,
            fs_count: 0,
            effect_uses: HashMap::new(),
            grant_uses: Vec::new(),
            io,
        }
    }

    /// Run with this environment rather than the process's own.
    pub fn with_environ(mut self, environ: Environ) -> Runtime {
        self.environ = Some(environ);
        self
    }

    /// Run with these parameters: `set_run_params(seed, freeze_time)` and
    /// `--max-read`.
    pub fn with_params(mut self, params: RunParams) -> Runtime {
        self.rng = params.seed.map(Twister::seeded);
        self.params = params;
        self
    }

    /// Stop the run after this many calls and loop turns:
    /// `_state.STEP_LIMIT`.
    pub fn with_step_limit(mut self, limit: u64) -> Runtime {
        self.step_limit = Some(limit);
        self
    }

    /// Stop the run at the operation that takes what it has made past this
    /// size: `_state._SIZE_LIMIT`.
    pub fn with_size_limit(mut self, limit: u64) -> Runtime {
        self.size_limit = Some(limit);
        self
    }

    /// `made(v, line)`: count `v` as made at `line`, and stop the run there
    /// if that takes the count past the size limit.
    fn made(&mut self, v: &Value, line: u32) -> R<()> {
        self.count_made(size_of(v), line)
    }

    /// `made(text, line)` of a text a builtin writes rather than answers.
    fn made_text(&mut self, t: &Text, line: u32) -> R<()> {
        self.count_made(utf8_len(t), line)
    }

    fn count_made(&mut self, n: u64, line: u32) -> R<()> {
        self.size_made += n;
        match self.size_limit {
            Some(limit) if self.size_made > limit => Err(Stop::Size(line)),
            _ => Ok(()),
        }
    }

    /// `builtin_made`: a builtin, under the size limit - its answer
    /// counted as made, unless it handed back a value the program held.
    fn builtin_made(&mut self, name: &str, args: Vec<Value>, line: u32) -> R<Value> {
        let hands_back = HANDS_BACK.contains(&name)
            || (name == "to_text" && matches!(args.first(), Some(Value::Text(_))));
        let out = self.run_builtin(name, args, line)?;
        if !hands_back {
            self.made(&out, line)?;
        }
        Ok(out)
    }

    /// `interpret(funcs)`: call `main`.
    pub fn interpret(&mut self) -> R<()> {
        let Some(main) = self.table.get("main").cloned() else {
            return Err(error(
                "E400",
                "no 'main' function found",
                1,
                &["add: fn main() uses io { ... }"],
            ));
        };
        self.call("main", Vec::new(), main.line).map(|_| ())
    }

    fn stop_point(&mut self, line: u32) -> R<()> {
        self.ticks += 1;
        match self.step_limit {
            Some(limit) if self.ticks > limit => Err(Stop::Steps(line)),
            _ => Ok(()),
        }
    }

    fn call(&mut self, name: &str, args: Vec<Value>, line: u32) -> R<Value> {
        if name == "all_of" || name == "any_of" {
            let mut it = args.into_iter();
            let (xs, p) = (it.next().unwrap_or(Value::None), it.next().unwrap_or(Value::None));
            let all = name == "all_of";
            for v in iterate(&xs)? {
                let hit = self.call_function(&p, vec![v], line)?.truthy();
                if all && !hit {
                    return Ok(Value::Bool(false));
                }
                if !all && hit {
                    return Ok(Value::Bool(true));
                }
            }
            return Ok(Value::Bool(all));
        }
        if is_builtin(name) && !self.hidden.contains(name) {
            if self.size_limit.is_some() {
                return self.builtin_made(name, args, line);
            }
            return self.run_builtin(name, args, line);
        }
        if let Some(bare) = name.strip_prefix('@') {
            if self.size_limit.is_some() {
                return self.builtin_made(bare, args, line);
            }
            return self.run_builtin(bare, args, line);
        }
        let Some(func) = self.table.get(name).cloned() else {
            let known: Vec<&str> = self.table.keys().map(String::as_str).collect();
            return Err(Stop::Error(
                unknown_function(name, line, known.iter().copied()).into(),
            ));
        };
        self.call_function(&Value::Func(func), args, line)
    }

    fn call_function(&mut self, fnv: &Value, args: Vec<Value>, line: u32) -> R<Value> {
        let (func, caught) = match fnv {
            Value::Func(f) => (f.clone(), None),
            Value::Bound(b) => (b.func.clone(), Some(b.clone())),
            _ => return Err(Stop::Raised("AttributeError")),
        };
        let name = func.name.as_str();
        if self.step_limit.is_some() {
            self.stop_point(line)?;
        }
        if self.depth >= DEPTH_LIMIT {
            return Err(error(
                "E609",
                format!("'{name}' called itself {DEPTH_LIMIT} deep - this looks like recursion that never stops"),
                line,
                &["make sure the recursive case moves toward the base case", "or rewrite it as a loop"],
            ));
        }
        if args.len() != func.params.len() {
            let n = func.params.len();
            return Err(Stop::Error(RunError {
                code: "E401",
                message: Text::from(format!(
                    "'{name}' expects {n} argument(s) but got {}",
                    args.len()
                )),
                line,
                fixes: vec![format!("pass exactly {n} argument(s)")],
                file: None,
            }));
        }
        let mut env: HashMap<String, Value> = HashMap::new();
        for ((p, _), a) in func.params.iter().zip(args) {
            env.insert(p.clone(), a);
        }
        if let Some(b) = &caught {
            for (cn, cv) in &b.caught {
                env.entry(cn.clone()).or_insert_with(|| cv.clone());
            }
        }
        let promised = !func.requires.is_empty() || !func.ensures.is_empty();
        let entry = if promised { env.clone() } else { HashMap::new() };
        let (hush, hush_result) = self.secret.get(name).cloned().unwrap_or_default();

        // a promise is the callee's: its line is in the callee's file, so is
        // the file a broken one (or an error in it) names - until 9.0 the
        // caller's frame blamed it, which named the importer's file with the
        // library's line
        let src = func.src_file.as_str();
        for (expr, cline) in &func.requires {
            let mut scope = entry.clone();
            if !self.eval(expr, &mut scope).map_err(|s| blamed(src, s))?.truthy() {
                let message = TextBuf::new()
                    .str(&format!(
                        "broken promise: {} requires {}  (",
                        nice_name(name),
                        expr_str(expr)
                    ))
                    .text(&vals(expr, &entry, None, &hush, hush_result))
                    .str(")")
                    .done();
                return Err(blamed(
                    src,
                    error(
                        "E600",
                        message,
                        *cline,
                        &[
                            "check the value before calling this function",
                            "or loosen the promise if it is too strict",
                        ],
                    ),
                ));
            }
        }

        self.depth += 1;
        let mut retval = Value::None;
        let mut outcome = Ok(());
        for stmt in &func.body {
            match self.run(stmt, &mut env) {
                Ok(Flow::Next) => {}
                Ok(Flow::Return(v)) => {
                    retval = v;
                    break;
                }
                Err(stop) => {
                    outcome = Err(stop);
                    break;
                }
            }
        }
        self.depth -= 1;
        if let Err(stop) = outcome {
            return Err(blamed(src, stop));
        }

        for (expr, cline) in &func.ensures {
            let mut check_env = entry.clone();
            check_env.insert("result".to_string(), retval.clone());
            if !self.eval(expr, &mut check_env).map_err(|s| blamed(src, s))?.truthy() {
                let message = TextBuf::new()
                    .str(&format!(
                        "broken promise: {} ensures {}  (",
                        nice_name(name),
                        expr_str(expr)
                    ))
                    .text(&vals(expr, &entry, Some(&retval), &hush, hush_result))
                    .str(")")
                    .done();
                return Err(blamed(
                    src,
                    error(
                        "E601",
                        message,
                        *cline,
                        &[
                            "the code does not keep this promise - fix the code",
                            "or fix the promise if it is wrong",
                        ],
                    ),
                ));
            }
        }
        Ok(retval)
    }

    fn block(&mut self, stmts: &[Stmt], env: &mut HashMap<String, Value>) -> R<Flow> {
        for s in stmts {
            if let Flow::Return(v) = self.run(s, env)? {
                return Ok(Flow::Return(v));
            }
        }
        Ok(Flow::Next)
    }

    fn check_invariants(
        &mut self,
        invariants: &[(Expr, u32)],
        env: &mut HashMap<String, Value>,
    ) -> R<()> {
        for (inv, iline) in invariants {
            if !self.eval(inv, env)?.truthy() {
                let mut names: Vec<String> =
                    expr_vars(inv).into_iter().filter(|n| env.contains_key(n)).collect();
                names.sort();
                let mut shown = TextBuf::new();
                for (i, n) in names.iter().enumerate() {
                    if i > 0 {
                        shown.push_str(", ");
                    }
                    shown.push_str(n);
                    shown.push_str(" = ");
                    shown.push_text(&to_text(&env[n]));
                }
                let message = TextBuf::new()
                    .str(&format!("loop broke its promise: invariant {}  (", expr_str(inv)))
                    .text(&shown.done())
                    .str(")")
                    .done();
                return Err(error(
                    "E704",
                    message,
                    *iline,
                    &[
                        "fix the loop body so the promise holds on every step",
                        "or fix the invariant if it is wrong",
                    ],
                ));
            }
        }
        Ok(())
    }

    fn run(&mut self, stmt: &Stmt, env: &mut HashMap<String, Value>) -> R<Flow> {
        match stmt {
            Stmt::Assign { name, value, .. } | Stmt::Let { name, value, .. } => {
                let v = self.eval(value, env)?;
                env.insert(name.clone(), v);
            }
            Stmt::Return { value, .. } => {
                let v = match value {
                    None => Value::None,
                    Some(e) => self.eval(e, env)?,
                };
                return Ok(Flow::Return(v));
            }
            Stmt::ExprStmt { expr, .. } => {
                self.eval(expr, env)?;
            }
            Stmt::FailStmt { value, .. } => {
                let reason = self.eval(value, env)?;
                return Err(Stop::Fail(reason));
            }
            Stmt::Check { subject, ok_name, ok_body, fail_name, fail_body, .. } => {
                match self.eval(subject, env) {
                    Err(Stop::Fail(reason)) => {
                        env.insert(fail_name.clone(), reason);
                        return self.block(fail_body, env);
                    }
                    Err(other) => return Err(other),
                    Ok(val) => {
                        if let Some(n) = ok_name {
                            env.insert(n.clone(), val);
                        }
                        return self.block(ok_body, env);
                    }
                }
            }
            Stmt::If { cond, then, other, .. } => {
                let branch = if self.eval(cond, env)?.truthy() { then } else { other };
                return self.block(branch, env);
            }
            Stmt::While { cond, body, line, invariants } => {
                self.check_invariants(invariants, env)?;
                while self.eval(cond, env)?.truthy() {
                    if self.step_limit.is_some() {
                        self.stop_point(*line)?;
                    }
                    if let Flow::Return(v) = self.block(body, env)? {
                        return Ok(Flow::Return(v));
                    }
                    self.check_invariants(invariants, env)?;
                }
            }
            // the parser flattens a Block away, and the reference's run()
            // has no case for one: it would do nothing
            Stmt::Block { .. } => {}
        }
        Ok(Flow::Next)
    }

    fn eval_args(&mut self, args: &[Expr], env: &mut HashMap<String, Value>) -> R<Vec<Value>> {
        let mut out = Vec::with_capacity(args.len());
        for a in args {
            out.push(self.eval(a, env)?);
        }
        Ok(out)
    }

    fn eval(&mut self, node: &Expr, env: &mut HashMap<String, Value>) -> R<Value> {
        match node {
            Expr::Closure { name, free, .. } => {
                let func = self.table.get(name).cloned().ok_or(Stop::Raised("KeyError"))?;
                let caught: Vec<(String, Value)> = free
                    .iter()
                    .filter_map(|n| env.get(n).map(|v| (n.clone(), v.clone())))
                    .collect();
                Ok(if caught.is_empty() {
                    Value::Func(func)
                } else {
                    Value::Bound(Rc::new(Bound { func, caught }))
                })
            }
            Expr::Var { name, line } => {
                if let Some(v) = env.get(name) {
                    return Ok(v.clone());
                }
                if let Some(f) = self.table.get(name) {
                    return Ok(Value::Func(f.clone()));
                }
                Err(Stop::Error(RunError {
                    code: "E402",
                    message: Text::from(format!("unknown variable '{name}'")),
                    line: *line,
                    fixes: vec![format!("declare it first: let {name} = ...")],
                    file: None,
                }))
            }
            Expr::Num { value } => Ok(match value.parse::<i64>() {
                Ok(n) => Value::Int(n),
                Err(_) => Value::int(BigInt::parse(value).unwrap_or_default()),
            }),
            Expr::FloatNum { value } => Ok(Value::Float(*value)),
            Expr::Str { value } => Ok(Value::Text(Text::from(value.as_str()))),
            Expr::Bool { value } => Ok(Value::Bool(*value)),
            Expr::Neg { value, line } => {
                let v = self.eval(value, env)?;
                let negated = negate(&v, *line)?;
                if matches!(negated, Value::Float(_)) {
                    return Ok(negated);
                }
                checked_int(negated, "-", *line)
            }
            Expr::TryExpr { value, .. } => self.eval(value, env),
            Expr::Call { name, args, line } => {
                if let Some(held @ (Value::Func(_) | Value::Bound(_))) = env.get(name).cloned()
                {
                    let args = self.eval_args(args, env)?;
                    return self.call_function(&held, args, *line);
                }
                let args = self.eval_args(args, env)?;
                self.call(name, args, *line)
            }
            Expr::Not { value, .. } => Ok(Value::Bool(!self.eval(value, env)?.truthy())),
            Expr::RecordLit { name, fields, .. } => {
                let mut out: Vec<(String, Value)> = Vec::with_capacity(fields.len());
                for (f, v) in fields {
                    let val = self.eval(v, env)?;
                    match out.iter_mut().find(|(k, _)| k == f) {
                        Some(slot) => slot.1 = val,
                        None => out.push((f.clone(), val)),
                    }
                }
                Ok(Value::Record(Rc::new(Record { name: name.clone(), fields: out })))
            }
            Expr::FieldGet { obj, field, .. } => match self.eval(obj, env)? {
                Value::Record(r) => r
                    .fields
                    .iter()
                    .find(|(k, _)| k == field)
                    .map(|(_, v)| v.clone())
                    .ok_or(Stop::Raised("KeyError")),
                _ => Err(Stop::Raised("AttributeError")),
            },
            Expr::ListLit { items, line } => {
                let out = Value::list(self.eval_args(items, env)?);
                if self.size_limit.is_some() {
                    self.made(&out, *line)?;
                }
                Ok(out)
            }
            Expr::MapLit { entries, line } => {
                let mut d = Dict::new();
                for (k, v) in entries {
                    let key = self.eval(k, env)?;
                    let val = self.eval(v, env)?;
                    d.set(key, val)?;
                }
                let out = Value::Map(Rc::new(d));
                if self.size_limit.is_some() {
                    self.made(&out, *line)?;
                }
                Ok(out)
            }
            Expr::BinOp { op, left, right, line } => {
                if op == "and" {
                    let l = self.eval(left, env)?;
                    return if l.truthy() { self.eval(right, env) } else { Ok(l) };
                }
                if op == "or" {
                    let l = self.eval(left, env)?;
                    return if l.truthy() { Ok(l) } else { self.eval(right, env) };
                }
                let l = self.eval(left, env)?;
                let r = self.eval(right, env)?;
                let out = binop(op, &l, &r, *line)?;
                // a `+` that made a text or a list is counted as made
                if op == "+"
                    && self.size_limit.is_some()
                    && matches!(out, Value::Text(_) | Value::List(_))
                {
                    self.made(&out, *line)?;
                }
                Ok(out)
            }
        }
    }

    // ---- the builtins ---------------------------------------------------------

    fn spend(&mut self, effect: &str, what: &str, line: u32) -> R<()> {
        if self.budget.effects.contains(effect) {
            *self.effect_uses.entry(effect.to_string()).or_insert(0) += 1;
            return Ok(());
        }
        let have = self.budget.spec();
        let wider =
            if have.is_empty() { effect.to_string() } else { format!("{have},{effect}") };
        let allows = if have.is_empty() { "nothing".to_string() } else { have.clone() };
        Err(Stop::Error(RunError {
            code: "E310",
            message: Text::from(format!(
                "'{what}' needs the '{effect}' effect, which this run does not allow (it allows: {allows})"
            )),
            line,
            fixes: vec![
                format!("allow it: sabline <file> --allow {wider}"),
                format!("a run with no --allow gets {DEFAULT_ALLOW} (5.0); --allow all grants every effect"),
                "or use a program that does not need it".to_string(),
            ],
            file: None,
        }))
    }

    /// `_grant_used(grant)`: one more operation this grant let through.
    fn grant_used(&mut self, grant: String) {
        match self.grant_uses.iter_mut().find(|(g, _)| *g == grant) {
            Some(slot) => slot.1 += 1,
            None => self.grant_uses.push((grant, 1)),
        }
    }

    /// `_credential_root(real)`: the credential root an already normcased
    /// realpath sits at or below - a directory family's directory, or the
    /// file itself for one file or a pattern - or `None`.
    fn credential_root(&mut self, real: &str) -> R<Option<String>> {
        let environ = self.environ.get_or_insert_with(Environ::of_process);
        let Some(home) = host::home(environ) else { return Err(Stop::Raised("NotPorted")) };
        let home = os_path::normcase(&pypath::realpath(&home));
        let nc = |parts: &[&str]| {
            let mut p = home.clone();
            for part in parts {
                p = os_path::join(&p, part);
            }
            os_path::normcase(&p)
        };
        for parts in [&[".aws"][..], &[".ssh"], &[".config", "gcloud"]] {
            let root = nc(parts);
            if real == root || real.starts_with(&format!("{root}{}", pypath::SEP)) {
                return Ok(Some(root));
            }
        }
        for parts in [&[".docker", "config.json"][..], &[".kube", "config"], &[".netrc"]] {
            let root = nc(parts);
            if real == root {
                return Ok(Some(root));
            }
        }
        let base = os_path::basename(real);
        // fnmatch(base, normcase("*.pem")): base is normcased already
        if base == os_path::normcase(".env")
            || base.ends_with(&os_path::normcase(".pem"))
            || base.ends_with(&os_path::normcase(".key"))
        {
            return Ok(Some(real.to_string()));
        }
        Ok(None)
    }

    /// `allow_path(kind, path, what, line)`: refuse a file operation
    /// outside the paths this run granted, comparing the operation's
    /// `normcase(realpath(path))` with each grant's, and give that path
    /// back for the operation to use. `kind` is `read`, `write` or `any`.
    fn allow_path(&mut self, kind: &str, path: &Text, what: &str, line: u32) -> R<String> {
        // a path holding a lone surrogate is a str CPython can resolve on
        // Windows and cannot on POSIX; os_path works on Rust strings
        let Some(given) = path.to_str() else { return Err(Stop::Raised("NotPorted")) };
        let real = os_path::normcase(&pypath::realpath(&given));
        let sep = pypath::SEP;
        let under = |p: &str, prefix: &str| {
            p == prefix || p.starts_with(&format!("{}{sep}", prefix.trim_end_matches(sep)))
        };
        let wants: Vec<&str> = if kind == "any" { vec!["read", "write"] } else { vec![kind] };
        let reaches = |tail: &str| {
            TextBuf::new()
                .str(&format!("'{what}' reaches '"))
                .text(path)
                .str(&format!("' (resolved: {real}), {tail}"))
                .done()
        };
        let cred =
            if kind == "read" || kind == "any" { self.credential_root(&real)? } else { None };
        if let Some(cred) = cred {
            if what == "read_file" {
                return Err(Stop::Error(RunError {
                    code: "E318",
                    message: reaches(
                        "a documented credential location; a plain read returns ordinary text \
                         that can be printed or sent",
                    ),
                    line,
                    fixes: vec![
                        "read it with read_file_secret, which returns a Secret the compiler \
                         will not let escape"
                            .to_string(),
                        format!("and grant its exact path: --allow fs:read:{real}"),
                    ],
                    file: None,
                }));
            }
            let grants = self.budget.fs.clone();
            let named = grants.as_ref().is_some_and(|gs| {
                gs.iter().any(|(gk, prefix)| {
                    wants.contains(&gk.as_str())
                        && prefix.as_ref().is_some_and(|p| under(&real, p) && under(p, &cred))
                })
            });
            if !named {
                return Err(Stop::Error(RunError {
                    code: "E318",
                    message: reaches(
                        "a documented credential location the fs grants do not name \
                         explicitly; a broad grant does not include it",
                    ),
                    line,
                    fixes: vec![
                        format!("grant its exact path: --allow fs:read:{real}"),
                        "or use a program that does not read credentials".to_string(),
                    ],
                    file: None,
                }));
            }
            for (gk, prefix) in grants.iter().flatten() {
                if let Some(p) = prefix {
                    if wants.contains(&gk.as_str()) && under(&real, p) {
                        self.grant_used(format!("fs:{gk}:{}", pct_encode(p)));
                        break;
                    }
                }
            }
            return Ok(real);
        }
        let Some(grants) = self.budget.fs.clone() else {
            self.grant_used("fs".to_string());
            return Ok(real);
        };
        for (gk, prefix) in &grants {
            if wants.contains(&gk.as_str()) && prefix.as_ref().is_none_or(|p| under(&real, p))
            {
                let shown = match prefix {
                    Some(p) => format!("fs:{gk}:{}", pct_encode(p)),
                    None => format!("fs:{gk}"),
                };
                self.grant_used(shown);
                return Ok(real);
            }
        }
        let need = if kind == "any" { "read" } else { kind };
        let dir = os_path::dirname(&real);
        let dir = if dir.is_empty() { real.clone() } else { dir };
        Err(Stop::Error(RunError {
            code: "E313",
            message: reaches("which this run's fs grants do not cover"),
            line,
            fixes: vec![
                format!("allow it: --allow fs:{need}:{dir}"),
                "or use a program that stays inside the granted paths".to_string(),
            ],
            file: None,
        }))
    }

    /// `count_op("fs", what, line)`: spend one of the run's file
    /// operations, E315 past the count.
    fn count_op(&mut self, what: &str, line: u32) -> R<()> {
        self.fs_count += 1;
        let n = self.fs_count;
        let Some(limit) = &self.budget.fs_limit else { return Ok(()) };
        // a count is CPython's int, of any size: one past u128 is never met
        let over = limit.digits().parse::<u128>().is_ok_and(|l| u128::from(n) > l);
        if !over {
            return Ok(());
        }
        let th = if (10..=20).contains(&(n % 100)) {
            "th"
        } else {
            match n % 10 {
                1 => "st",
                2 => "nd",
                3 => "rd",
                _ => "th",
            }
        };
        Err(Stop::Error(RunError {
            code: "E315",
            message: Text::from(format!(
                "'{what}' is the {n}{th} fs operation, and this run allows {}",
                limit.digits()
            )),
            line,
            fixes: vec![
                format!("allow more: --allow fs@{n}"),
                "or use a program that does less".to_string(),
            ],
            file: None,
        }))
    }

    #[allow(clippy::too_many_lines)]
    fn run_builtin(&mut self, name: &str, args: Vec<Value>, line: u32) -> R<Value> {
        let arg = |i: usize| args.get(i).cloned().unwrap_or(Value::None);
        // the hot three, before anything else, as the reference has them
        if name == "length" {
            return length(&arg(0));
        }
        if name == "get" {
            if let Value::List(xs) = arg(0) {
                let at = arg(1);
                let fits = match &at {
                    Value::Int(_) | Value::Big(_) | Value::Bool(_) => {
                        at.as_i128().is_some_and(|i| i >= 0 && i < xs.len() as i128)
                    }
                    _ => false,
                };
                if !fits {
                    return Err(Stop::Error(RunError {
                        code: "E602",
                        message: TextBuf::new()
                            .str(&format!(
                                "this list has {} item(s), so there is no position ",
                                xs.len()
                            ))
                            .text(&py_str(&at))
                            .done(),
                        line,
                        fixes: vec![
                            "check the length before reading".to_string(),
                            "or add a 'requires' about the length".to_string(),
                        ],
                        file: None,
                    }));
                }
                let i = at.as_i128().unwrap_or(0) as usize;
                return Ok(xs[i].clone());
            }
        }
        if name == "push" {
            if let Value::List(xs) = arg(0) {
                let mut out = (*xs).clone();
                out.push(arg(1));
                return Ok(Value::list(out));
            }
        }
        if MONEY_BUILTINS.contains(&name) {
            return run_money(name, &args, line);
        }
        if let Some(b) = builtin(name) {
            for effect in b.effects {
                self.spend(effect, name, line)?;
            }
        }
        match name {
            "print" => {
                let shown = to_text(&arg(0));
                if self.size_limit.is_some() {
                    self.made_text(&shown, line)?;
                }
                self.io.stdout.push_text(&shown);
                self.io.stdout.push_str("\n");
                Ok(Value::None)
            }
            "ask" => {
                let prompt = py_str(&arg(0)).concat(&Text::from(" "));
                if self.size_limit.is_some() {
                    self.made_text(&prompt, line)?;
                }
                self.io.stdout.push_text(&prompt);
                let got = self.io.readline();
                if got.is_empty() {
                    return Err(error(
                        "E607",
                        "no input available to read",
                        line,
                        &["run this program in a terminal where you can type an answer"],
                    ));
                }
                let p = got.points();
                Ok(Value::Text(if p.last() == Some(&0x0A) {
                    got.slice(0, p.len() - 1)
                } else {
                    got
                }))
            }
            "to_int" => {
                let given = text_of(&arg(0))?;
                let t = given.strip();
                let body = if t.starts_with("-") { t.slice(1, t.len()) } else { t.clone() };
                if !body.isdecimal() {
                    return Err(fail(quoted(&given, " is not a whole number")));
                }
                // `body.lstrip("0")`: ASCII zeros only - a zero in another
                // script counts towards the nineteen
                let kept = body.points().iter().skip_while(|&&c| c == 0x30);
                if kept.clone().count() <= 19 && body.len() > 4300 {
                    // `int(t)` is asked, and refuses more than 4,300
                    // digits - leading zeros counted - with a ValueError
                    // nothing in the reference catches
                    return Err(Stop::Raised("ValueError"));
                }
                let value = if kept.count() <= 19 { t.decimal_value_signed() } else { None };
                match value {
                    Some(v) if v >= i128::from(INT_MIN) && v <= i128::from(INT_MAX) => Ok(Value::Int(v as i64)),
                    _ => Err(fail(quoted(
                        &given,
                        &format!(" is a whole number too big to hold (whole numbers go from {INT_MIN} to {INT_MAX})"),
                    ))),
                }
            }
            "to_text" => Ok(Value::Text(to_text(&arg(0)))),
            "to_float" => Ok(Value::Float(py_float(&arg(0))?)),
            "round" => {
                let x = arg(0);
                let fits = match &x {
                    Value::Float(f) => {
                        f.is_finite() && {
                            let r = f.round_ties_even();
                            (-9_223_372_036_854_775_808.0..9_223_372_036_854_775_808.0)
                                .contains(&r)
                        }
                    }
                    other => other
                        .as_i128()
                        .is_some_and(|i| i >= i128::from(INT_MIN) && i <= i128::from(INT_MAX)),
                };
                if !fits {
                    return Err(Stop::Error(RunError {
                        code: "E407",
                        message: TextBuf::new()
                            .str("round(")
                            .text(&py_repr(&x))
                            .str(&format!(") has no whole number that fits in 64 bits (from {INT_MIN} to {INT_MAX})"))
                            .done(),
                        line,
                        fixes: vec!["check the value is in range before rounding it".to_string()],
                        file: None,
                    }));
                }
                Ok(match x {
                    Value::Float(f) => Value::Int(f.round_ties_even() as i64),
                    other => Value::int128(other.as_i128().unwrap_or(0)),
                })
            }
            "contains" => Ok(Value::Bool(text_of(&arg(0))?.contains(&text_of(&arg(1))?))),
            "split" => {
                let sep = arg(1);
                if py_eq(&sep, &Value::text("")) {
                    return Err(error(
                        "E609",
                        "cannot split by empty text",
                        line,
                        &["use a separator like \" \" or \",\""],
                    ));
                }
                let parts = text_of(&arg(0))?.split(&text_of(&sep)?);
                Ok(Value::list(parts.into_iter().map(Value::Text).collect()))
            }
            "upper" => Ok(Value::Text(text_of(&arg(0))?.upper())),
            "lower" => Ok(Value::Text(text_of(&arg(0))?.lower())),
            "chars" => Ok(Value::list(
                text_of(&arg(0))?.chars().into_iter().map(Value::Text).collect(),
            )),
            "pop" => {
                let xs = arg(0);
                if !xs.truthy() {
                    return Err(fail("there is nothing left to take off the end"));
                }
                let items = sequence(&xs)?;
                Ok(Value::list(items[..items.len() - 1].to_vec()))
            }
            "slice" => {
                let xs = arg(0);
                let (start, stop) = (py_int(&arg(1))?, py_int(&arg(2))?);
                let n = length_of(&xs)? as i128;
                if start < 0 || stop > n || start > stop {
                    return Err(fail(format!(
                        "a slice from {start} to {stop} does not fit a list of {n}"
                    )));
                }
                let items = sequence(&xs)?;
                Ok(Value::list(items[start as usize..stop as usize].to_vec()))
            }
            "set_at" => {
                let xs = arg(0);
                let at = py_int(&arg(1))?;
                let n = length_of(&xs)? as i128;
                if at < 0 || at >= n {
                    return Err(fail(format!("there is no position {at} in a list of {n}")));
                }
                let mut out = iterate(&xs)?;
                out[at as usize] = arg(2);
                Ok(Value::list(out))
            }
            "div_or_fail" | "mod_or_fail" => {
                let (a, b) = (py_int(&arg(0))?, py_int(&arg(1))?);
                if b == 0 {
                    let word =
                        if name == "div_or_fail" { "divide" } else { "take a remainder" };
                    return Err(fail(format!("cannot {word} by zero")));
                }
                let (q, r) = floor_divmod(a, b);
                let answer = if name == "div_or_fail" { q } else { r };
                if answer < i128::from(INT_MIN) || answer > i128::from(INT_MAX) {
                    return Err(fail(format!(
                        "dividing {a} by {b} makes a number too big to hold"
                    )));
                }
                Ok(Value::int128(answer))
            }
            "add_or_fail" | "sub_or_fail" | "mul_or_fail" => {
                let (a, b) = (py_int(&arg(0))?, py_int(&arg(1))?);
                let (answer, word) = match name {
                    "add_or_fail" => (a.checked_add(b), "adding"),
                    "sub_or_fail" => (a.checked_sub(b), "subtracting"),
                    _ => (a.checked_mul(b), "multiplying"),
                };
                match answer {
                    Some(v) if v >= i128::from(INT_MIN) && v <= i128::from(INT_MAX) => {
                        Ok(Value::int128(v))
                    }
                    _ => {
                        Err(fail(format!("{word} {a} and {b} makes a number too big to hold")))
                    }
                }
            }
            "push" => Err(Stop::Raised("TypeError")),
            "put" => {
                let Value::Map(m) = arg(0) else { return Err(Stop::Raised("TypeError")) };
                let mut out = (*m).clone();
                out.set(arg(1), arg(2))?;
                Ok(Value::Map(Rc::new(out)))
            }
            "has" => Ok(Value::Bool(contains_in(&arg(0), &arg(1))?)),
            "keys" => {
                let Value::Map(m) = arg(0) else { return Err(Stop::Raised("AttributeError")) };
                Ok(Value::list(m.entries().iter().map(|(k, _)| k.clone()).collect()))
            }
            "code_at" => {
                let t = text_of(&arg(0))?;
                let i = py_int(&arg(1))?;
                if i < 0 || i >= t.len() as i128 {
                    return Err(Stop::Error(RunError {
                        code: "E602",
                        message: Text::from(format!(
                            "position {i} is outside the text (it has {} character(s))",
                            t.len()
                        )),
                        line,
                        fixes: vec![
                            "positions go from 0 to length - 1".to_string(),
                            "check with length(...) before using code_at".to_string(),
                        ],
                        file: None,
                    }));
                }
                Ok(Value::Int(i64::from(t.points()[i as usize])))
            }
            "get_or" => {
                let Value::Map(m) = arg(0) else { return Err(Stop::Raised("AttributeError")) };
                Ok(m.get(&arg(1))?.cloned().unwrap_or_else(|| arg(2)))
            }
            "get" => match arg(0) {
                Value::Map(m) => {
                    let k = arg(1);
                    match m.get(&k)? {
                        Some(v) => Ok(v.clone()),
                        None => {
                            let key_txt = match &k {
                                Value::Text(t) => {
                                    TextBuf::new().str("'").text(t).str("'").done()
                                }
                                other => to_text(other),
                            };
                            Err(Stop::Fail(Value::Text(
                                TextBuf::new().str("map has no key ").text(&key_txt).done(),
                            )))
                        }
                    }
                }
                xs => {
                    let i = py_int(&arg(1))?;
                    let n = length_of(&xs)? as i128;
                    if i < 0 || i >= n {
                        return Err(Stop::Error(RunError {
                            code: "E602",
                            message: Text::from(format!(
                                "position {i} is outside the list (it has {n} item(s))"
                            )),
                            line,
                            fixes: vec![
                                "positions go from 0 to length - 1".to_string(),
                                "check with length(...) before using get".to_string(),
                            ],
                            file: None,
                        }));
                    }
                    Ok(iterate(&xs)?[i as usize].clone())
                }
            },
            "json_of" => {
                let plain = plain(&arg(0))?;
                match pyjson::dumps(&plain) {
                    Ok(t) => Ok(Value::Text(t)),
                    Err(pyjson::DumpError::Type) => Err(Stop::Raised("TypeError")),
                    Err(pyjson::DumpError::Value) => Err(Stop::Raised("ValueError")),
                }
            }
            "json_has" => match walk(&arg(0), &arg(1)) {
                Ok(_) => Ok(Value::Bool(true)),
                Err(Stop::Fail(_)) => Ok(Value::Bool(false)),
                Err(other) => Err(other),
            },
            "json_len" => match walk(&arg(0), &arg(1))? {
                Value::List(xs) => Ok(Value::Int(xs.len() as i64)),
                Value::Map(m) => Ok(Value::Int(m.len() as i64)),
                Value::Text(t) => Ok(Value::Int(t.len() as i64)),
                _ => Err(fail("this value has no length")),
            },
            "json_get" => Ok(Value::Text(match walk(&arg(0), &arg(1))? {
                Value::Bool(b) => Text::from(if b { "true" } else { "false" }),
                got @ (Value::Map(_) | Value::List(_)) => {
                    pyjson::dumps(&got).map_err(|_| Stop::Raised("ValueError"))?
                }
                Value::None => Text::from(""),
                other => py_str(&other),
            })),
            "json_int" => {
                let got = walk(&arg(0), &arg(1))?;
                let path = text_of(&arg(1))?;
                let value = match &got {
                    Value::Int(_) | Value::Big(_) | Value::Bool(_) => got.as_big(),
                    Value::Float(f) => BigInt::from_f64_integral(*f),
                    Value::Text(t) => pyjson::py_int_of_text(t),
                    _ => None,
                };
                let Some(value) = value else {
                    return Err(fail(quoted(&path, " is not a whole number")));
                };
                match value.to_i64() {
                    Some(n) => Ok(Value::Int(n)),
                    None => Err(fail(quoted(
                        &path,
                        &format!(
                            " is a whole number too big to hold (from {INT_MIN} to {INT_MAX})"
                        ),
                    ))),
                }
            }
            "json_float" => {
                let got = walk(&arg(0), &arg(1))?;
                let value = match &got {
                    Value::Int(_) | Value::Big(_) | Value::Bool(_) => {
                        got.as_big().and_then(|b| b.to_f64())
                    }
                    Value::Float(f) => Some(*f),
                    Value::Text(t) => pyjson::py_float_of_text(t).map(fresh_float),
                    _ => None,
                };
                match value {
                    Some(x) => Ok(Value::Float(x)),
                    None => Err(fail(quoted(&text_of(&arg(1))?, " is not a decimal"))),
                }
            }
            "sha256" => Ok(Value::text(&digest::hex(&digest::sha256(
                &digest::utf8_surrogatepass(&text_of(&arg(0))?),
            )))),
            "hex_encode" => {
                Ok(Value::text(&digest::hex(&digest::utf8_surrogatepass(&text_of(&arg(0))?))))
            }
            "base64_encode" => Ok(Value::text(&digest::b64encode(
                &digest::utf8_surrogatepass(&text_of(&arg(0))?),
            ))),
            "url_encode" => Ok(Value::text(&digest::url_quote(&digest::utf8_surrogatepass(
                &text_of(&arg(0))?,
            )))),
            "hex_decode" | "base64_decode" => {
                let t = text_of(&arg(0))?;
                let what = if name == "hex_decode" { "hexadecimal" } else { "base64" };
                let raw = if name == "hex_decode" {
                    if t.isascii() && !t.points().iter().any(|&c| isspace(c)) {
                        digest::from_hex(&t)
                    } else {
                        None
                    }
                } else if t.isascii() {
                    digest::b64decode_validated(&t)
                } else {
                    None
                };
                let Some(raw) = raw else {
                    return Err(fail(format!("that text is not {what}")));
                };
                digest::utf8_strict(&raw).map(Value::Text).ok_or_else(|| {
                    fail(format!("that {what} does not decode to text (UTF-8)"))
                })
            }
            "args" => Ok(Value::list(self.io.args.iter().cloned().map(Value::Text).collect())),
            "log" => {
                let line_text = log_line(&to_text(&arg(0)));
                if self.size_limit.is_some() {
                    self.made_text(&line_text, line)?;
                }
                self.io.stderr.push_text(&line_text);
                self.io.stderr.push_str("\n");
                Ok(Value::None)
            }
            "exit_with" => {
                let code = py_int(&arg(0))?;
                if !(0..=255).contains(&code) {
                    return Err(Stop::Error(RunError {
                        code: "E408",
                        message: Text::from(format!(
                            "an exit code must be between 0 and 255, not {code}"
                        )),
                        line,
                        fixes: vec![
                            "0 means success; anything else means something went wrong"
                                .to_string(),
                        ],
                        file: None,
                    }));
                }
                Err(Stop::Exit(code as i64))
            }
            "read_line" => Ok(Value::Text(self.io.readline().rstrip_newlines())),
            "format" => {
                let template = text_of(&arg(0))?;
                let pieces = template.split(&Text::from("{}"));
                let holes = pieces.len() - 1;
                let given = args.len().saturating_sub(1);
                if holes != given {
                    return Err(Stop::Error(RunError {
                        code: "E406",
                        message: Text::from(format!(
                            "format has {holes} placeholder(s) but got {given} value(s)"
                        )),
                        line,
                        fixes: vec![
                            format!("pass exactly {holes} value(s) after the text"),
                            "each {} in the text takes one value".to_string(),
                        ],
                        file: None,
                    }));
                }
                let mut out = TextBuf::new().text(&pieces[0]);
                for (piece, val) in pieces[1..].iter().zip(&args[1..]) {
                    out.push_text(&to_text(val));
                    out.push_text(piece);
                }
                Ok(Value::Text(out.done()))
            }
            "env" => {
                let (key, default) = (text_of(&arg(0))?, text_of(&arg(1))?);
                let environ = self.environ.get_or_insert_with(Environ::of_process);
                Ok(Value::Text(environ.get(&key).cloned().unwrap_or(default)))
            }
            "now" => Ok(Value::Int(match self.params.freeze_time {
                // --freeze-time fixes the instant; the clock effect was
                // spent above all the same (8.0)
                Some(t) => t,
                None => std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .map_or(0, |d| d.as_secs() as i64),
            })),
            "random" => {
                let n = arg(0);
                if !matches!(py_compare(">", &n, &Value::Int(0)), Ok(true)) {
                    return Err(error(
                        "E405",
                        "random(n) needs n greater than 0",
                        line,
                        &["pass a positive number, e.g. random(6)"],
                    ));
                }
                let Value::Int(n) = n else { return Err(Stop::Raised("NotPorted")) };
                let rng = self.rng.get_or_insert_with(Twister::unseeded);
                Ok(Value::Int(rng.randrange(n as u64) as i64))
            }
            // the effect was spent above; a Secret is a compile-time
            // distinction, so here the value is simply itself (8.1)
            "declassify" => Ok(arg(0)),
            "hmac_sha256" | "hmac_sha256_chain" => {
                let mut key = digest::utf8_surrogatepass(&text_of(&arg(0))?);
                let messages =
                    if name == "hmac_sha256" { vec![arg(1)] } else { iterate(&arg(1))? };
                if messages.is_empty() {
                    return Err(Stop::Error(RunError {
                        code: "E609",
                        message: Text::from(format!("'{name}' was given nothing to sign")),
                        line,
                        fixes: vec!["pass at least one message".to_string()],
                        file: None,
                    }));
                }
                for message in &messages {
                    let m = digest::utf8_surrogatepass(&text_of(message)?);
                    key = digest::hmac_sha256(&key, &m).to_vec();
                }
                Ok(Value::text(&digest::hex(&key)))
            }
            "file_exists" => {
                let path = text_of(&arg(0))?;
                if path.points().contains(&0) {
                    return Ok(Value::Bool(false)); // names no file (8.2)
                }
                let real = self.allow_path("any", &path, name, line)?;
                self.count_op(name, line)?;
                Ok(Value::Bool(std::fs::metadata(&real).is_ok()))
            }
            "read_file" | "read_file_secret" => {
                let path = text_of(&arg(0))?;
                if path.points().contains(&0) {
                    return Err(fail(
                        TextBuf::new()
                            .str("cannot read file '")
                            .text(&nul_shown(&path))
                            .str("': a path cannot hold a NUL character")
                            .done(),
                    ));
                }
                let real = self.allow_path("read", &path, name, line)?;
                self.count_op(name, line)?;
                if let Ok(meta) = std::fs::metadata(&real) {
                    let (size, ceiling) = (meta.len(), self.params.max_read);
                    if size > ceiling {
                        return Err(Stop::Error(RunError {
                            code: "E316",
                            message: TextBuf::new()
                                .str("'")
                                .text(&path)
                                .str(&format!(
                                    "' is {size} bytes, over the read ceiling of {ceiling} \
                                     bytes - a file is read whole, into memory, so a large \
                                     one is capped"
                                ))
                                .done(),
                            line,
                            fixes: vec![
                                format!(
                                    "raise the ceiling: --max-read {} (megabytes)",
                                    (size / (1024 * 1024) + 1).max(1)
                                ),
                                "or read less, or read it in another program".to_string(),
                            ],
                            file: None,
                        }));
                    }
                }
                match std::fs::read(&real) {
                    Ok(raw) => host::read_text(&raw).map(Value::Text).ok_or_else(|| {
                        fail(
                            TextBuf::new()
                                .text(&quoted_after("cannot read file ", &path))
                                .str(": it is not UTF-8 text")
                                .done(),
                        )
                    }),
                    Err(_) => Err(fail(quoted_after("cannot read file ", &path))),
                }
            }
            "write_file" => {
                let path = text_of(&arg(0))?;
                let fixes_nul = ["build the path from text that holds no NUL"];
                if path.points().contains(&0) {
                    return Err(error(
                        "E608",
                        TextBuf::new()
                            .str("could not write '")
                            .text(&nul_shown(&path))
                            .str("': a path cannot hold a NUL character")
                            .done(),
                        line,
                        &fixes_nul,
                    ));
                }
                let real = self.allow_path("write", &path, name, line)?;
                self.count_op(name, line)?;
                let refused = |e: &std::io::Error| {
                    error(
                        "E608",
                        TextBuf::new()
                            .str("could not write '")
                            .text(&path)
                            .str("': ")
                            .str(&host::strerror(e))
                            .done(),
                        line,
                        &[
                            "check the folder exists and is writable",
                            "or write somewhere else",
                        ],
                    )
                };
                // encoded before the file is opened, so a text that is not
                // UTF-8 writes nothing and leaves a file that was there as
                // it was
                let Some(bytes) = host::written_bytes(&to_text(&arg(1))) else {
                    return Err(error(
                        "E608",
                        TextBuf::new()
                            .str("could not write '")
                            .text(&path)
                            .str("': the text holds a lone surrogate, which is not UTF-8")
                            .done(),
                        line,
                        &["write the text without it: a lone surrogate is half of a \
                           character, as a JSON escape like \\ud800 gives on its own"],
                    ));
                };
                use std::io::Write;
                let mut file = std::fs::File::create(&real).map_err(|e| refused(&e))?;
                file.write_all(&bytes).map_err(|e| refused(&e))?;
                Ok(Value::None)
            }
            // a builtin whose work is the network, Python or a tool: spent
            // above, and refused there by every budget that does not grant
            // it; its work is not ported yet
            _ if is_builtin(name) => Err(Stop::Raised("NotPorted")),
            _ => Ok(Value::None),
        }
    }
}

// ---- what the builtins and operators share --------------------------------

/// A text's length in UTF-8, a lone surrogate three bytes:
/// `len(t.encode("utf-8", "surrogatepass"))`.
fn utf8_len(t: &Text) -> u64 {
    t.points()
        .iter()
        .map(|&c| match c {
            0..=0x7F => 1,
            0x80..=0x7FF => 2,
            0x800..=0xFFFF => 3,
            _ => 4,
        })
        .sum()
}

/// `HANDS_BACK`: the builtins whose answer is a value the program already
/// holds rather than one they made - an item of a list or a map, the
/// default it was given, the value declassified.
const HANDS_BACK: [&str; 3] = ["get", "get_or", "declassify"];

/// `size_of(v)`: what a value counts towards the size limit - a text its
/// UTF-8 bytes (a lone surrogate three, as the encoders write it), a list
/// or a map its items, anything else nothing.
pub fn size_of(v: &Value) -> u64 {
    match v {
        Value::Text(t) => utf8_len(t),
        Value::List(xs) => xs.len() as u64,
        Value::Map(m) => m.len() as u64,
        _ => 0,
    }
}

impl Text {
    /// `int(t)` of a text whose body after one leading minus is decimal.
    fn decimal_value_signed(&self) -> Option<i128> {
        if self.starts_with("-") {
            self.slice(1, self.len()).decimal_value().map(|n| -n)
        } else {
            self.decimal_value()
        }
    }
}

fn quoted(t: &Text, rest: &str) -> Text {
    TextBuf::new().str("'").text(t).str("'").str(rest).done()
}

/// `before` and the text in quotes.
fn quoted_after(before: &str, t: &Text) -> Text {
    TextBuf::new().str(before).str("'").text(t).str("'").done()
}

/// `str(t).replace(chr(0), chr(92) + '0')`: a NUL written as `\0`.
fn nul_shown(t: &Text) -> Text {
    let mut out = TextBuf::new();
    for &c in t.points() {
        if c == 0 {
            out.push_str("\\0");
        } else {
            out.push_text(&Text::from(vec![c]));
        }
    }
    out.done()
}

/// `str(v)` where the reference writes `str(args[i])` of what the type
/// checker made a Text.
fn text_of(v: &Value) -> R<Text> {
    Ok(match v {
        Value::Text(t) => t.clone(),
        other => py_str(other),
    })
}

/// `int(v)` of a number.
fn py_int(v: &Value) -> R<i128> {
    match v {
        Value::Float(f) => {
            if f.is_nan() {
                return Err(Stop::Raised("ValueError"));
            }
            BigInt::from_f64_integral(*f)
                .and_then(|b| b.to_i128())
                .ok_or(Stop::Raised("OverflowError"))
        }
        other => other.as_i128().ok_or(Stop::Raised("TypeError")),
    }
}

/// `float(v)`.
fn py_float(v: &Value) -> R<f64> {
    match v {
        Value::Float(f) => Ok(*f),
        Value::Text(t) => {
            pyjson::py_float_of_text(t).map(fresh_float).ok_or(Stop::Raised("ValueError"))
        }
        other => other
            .as_big()
            .ok_or(Stop::Raised("TypeError"))?
            .to_f64()
            .ok_or(Stop::Raised("OverflowError")),
    }
}

fn length_of(v: &Value) -> R<usize> {
    match v {
        Value::Text(t) => Ok(t.len()),
        Value::List(xs) => Ok(xs.len()),
        Value::Map(m) => Ok(m.len()),
        _ => Err(Stop::Raised("TypeError")),
    }
}

fn length(v: &Value) -> R<Value> {
    Ok(Value::Int(length_of(v)? as i64))
}

/// `list(v)`, or what `for v in xs` walks.
fn iterate(v: &Value) -> R<Vec<Value>> {
    match v {
        Value::List(xs) => Ok((**xs).clone()),
        Value::Text(t) => Ok(t.chars().into_iter().map(Value::Text).collect()),
        Value::Map(m) => Ok(m.entries().iter().map(|(k, _)| k.clone()).collect()),
        _ => Err(Stop::Raised("TypeError")),
    }
}

/// `xs[a:b]`'s items for what can be sliced: a list, or a text as its
/// characters (`list(t[a:b])`). A map cannot be, which is a `TypeError`.
fn sequence(v: &Value) -> R<Vec<Value>> {
    match v {
        Value::List(_) | Value::Text(_) => iterate(v),
        _ => Err(Stop::Raised("TypeError")),
    }
}

/// `needle in haystack`.
fn contains_in(haystack: &Value, needle: &Value) -> R<bool> {
    match haystack {
        Value::Map(m) => Ok(m.has(needle)?),
        Value::List(xs) => Ok(xs.iter().any(|x| item_eq(x, needle))),
        Value::Text(t) => match needle {
            Value::Text(n) => Ok(t.contains(n)),
            _ => Err(Stop::Raised("TypeError")),
        },
        _ => Err(Stop::Raised("TypeError")),
    }
}

/// `log_line(text)`: each character that would end a line or start one -
/// the C0 controls but tab, DEL, the C1 controls, U+2028 and U+2029 - as
/// an escape.
pub fn log_line(t: &Text) -> Text {
    let mut out = TextBuf::new();
    for &c in t.points() {
        let control = (c <= 0x08)
            || (0x0A..=0x1F).contains(&c)
            || (0x7F..=0x9F).contains(&c)
            || c == 0x2028
            || c == 0x2029;
        if !control {
            out.push_text(&Text::from(vec![c]));
        } else if c == 0x0A {
            out.push_str("\\n");
        } else if c == 0x0D {
            out.push_str("\\r");
        } else if c < 0x100 {
            out.push_str(&format!("\\x{c:02x}"));
        } else {
            out.push_str(&format!("\\u{c:04x}"));
        }
    }
    out.done()
}

fn floor_divmod(a: i128, b: i128) -> (i128, i128) {
    let (mut q, mut r) = (a / b, a % b);
    if r != 0 && ((r < 0) != (b < 0)) {
        q -= 1;
        r += b;
    }
    (q, r)
}

/// `checked_int(value, op, line)`.
fn checked_int(v: Value, op: &str, line: u32) -> R<Value> {
    let out_of_range = match &v {
        Value::Big(_) => true,
        Value::Money(m) => {
            let _ = m;
            false
        }
        _ => false,
    };
    if out_of_range {
        return Err(error(
            "E407",
            format!("this '{op}' made a number too big to hold (whole numbers go from {INT_MIN} to {INT_MAX})"),
            line,
            &["keep the numbers smaller", "or work in smaller units, like cents instead of rupees"],
        ));
    }
    Ok(v)
}

fn money_too_big(op: &str, line: u32) -> Stop {
    error(
        "E407",
        format!("this '{op}' made an amount too big to hold (an amount is {INT_MIN} to {INT_MAX} minor units)"),
        line,
        &["an amount is held exactly, in 64 bits of minor units; one this large is almost certainly a bug"],
    )
}

/// An amount from minor units computed exactly, or E407 for `op`.
fn money_checked(units: i128, currency: &Rc<str>, op: &str, line: u32) -> R<Value> {
    match i64::try_from(units) {
        Ok(u) => Ok(Value::Money(Money { units: u, currency: currency.clone() })),
        Err(_) => Err(money_too_big(op, line)),
    }
}

/// `-v`, before `checked_int`: an amount's negation past 64 bits is E407
/// in the amount's words, as `checked_int` gives it for a `MoneyValue`.
fn negate(v: &Value, line: u32) -> R<Value> {
    Ok(match v {
        Value::Float(f) => Value::Float(fresh_float(-f)),
        Value::Money(m) => return money_checked(-i128::from(m.units), &m.currency, "-", line),
        other => match other.as_big() {
            Some(b) => Value::int(b.neg()),
            None => return Err(Stop::Raised("TypeError")),
        },
    })
}

/// A number as a float, for an operation with one: `OverflowError` for a
/// whole number past the largest double, `TypeError` for what is not a
/// number.
fn as_float(v: &Value) -> R<f64> {
    match v {
        Value::Float(f) => Ok(*f),
        other => other
            .as_big()
            .ok_or(Stop::Raised("TypeError"))?
            .to_f64()
            .ok_or(Stop::Raised("OverflowError")),
    }
}

/// CPython's `float_divmod`: the floored quotient and the remainder with
/// the divisor's sign, of two doubles, `b` not zero.
fn float_divmod(vx: f64, wx: f64) -> (f64, f64) {
    let mut m = vx % wx;
    let mut div = (vx - m) / wx;
    if m != 0.0 {
        if (wx < 0.0) != (m < 0.0) {
            m += wx;
            div -= 1.0;
        }
    } else {
        m = 0.0f64.copysign(wx);
    }
    let floordiv = if div != 0.0 {
        let f = div.floor();
        if div - f > 0.5 {
            f + 1.0
        } else {
            f
        }
    } else {
        0.0f64.copysign(vx / wx)
    };
    (floordiv, m)
}

/// A binary operator other than `and` and `or`, as the reference's
/// `eval_` gives it.
fn binop(op: &str, l: &Value, r: &Value, line: u32) -> R<Value> {
    match op {
        "+" => {
            if matches!(l, Value::Text(_)) || matches!(r, Value::Text(_)) {
                return Ok(Value::Text(to_text(l).concat(&to_text(r))));
            }
            arith('+', l, r, line).and_then(|v| checked_int(v, "+", line))
        }
        "-" => arith('-', l, r, line).and_then(|v| checked_int(v, "-", line)),
        "*" => arith('*', l, r, line).and_then(|v| checked_int(v, "*", line)),
        "/" => {
            if py_eq(r, &Value::Int(0)) {
                return Err(error(
                    "E403",
                    "division by zero",
                    line,
                    &["check the divisor before dividing"],
                ));
            }
            if let Value::Float(x) = l {
                let y = as_float(r)?;
                return Ok(Value::Float(fresh_float(x / y)));
            }
            if matches!(r, Value::Float(_)) {
                let (x, y) = (as_float(l)?, as_float(r)?);
                return Ok(Value::Float(fresh_float(float_divmod(x, y).0)));
            }
            let (a, b) = (
                l.as_big().ok_or(Stop::Raised("TypeError"))?,
                r.as_big().ok_or(Stop::Raised("TypeError"))?,
            );
            checked_int(Value::int(a.divmod_floor(&b).0), "/", line)
        }
        "%" => {
            if py_eq(r, &Value::Int(0)) {
                return Err(error(
                    "E403",
                    "remainder by zero",
                    line,
                    &["check the divisor before using %"],
                ));
            }
            if matches!(l, Value::Float(_)) || matches!(r, Value::Float(_)) {
                let (x, y) = (as_float(l)?, as_float(r)?);
                return Ok(Value::Float(fresh_float(float_divmod(x, y).1)));
            }
            if matches!(l, Value::Text(_)) {
                return Err(Stop::Raised("NotPorted"));
            }
            let (a, b) = (
                l.as_big().ok_or(Stop::Raised("TypeError"))?,
                r.as_big().ok_or(Stop::Raised("TypeError"))?,
            );
            Ok(Value::int(a.divmod_floor(&b).1))
        }
        "==" => Ok(Value::Bool(py_eq(l, r))),
        "!=" => Ok(Value::Bool(!py_eq(l, r))),
        _ => Ok(Value::Bool(py_compare(op, l, r)?)),
    }
}

/// `l + r`, `l - r`, `l * r` for what is not a text: numbers, amounts,
/// and a list joined or repeated.
fn arith(op: char, l: &Value, r: &Value, line: u32) -> R<Value> {
    match (l, r) {
        (Value::Money(a), Value::Money(b)) if op != '*' => {
            if a.currency != b.currency {
                return Err(error(
                    "E550",
                    format!("an amount in {} met one in {}", a.currency, b.currency),
                    0,
                    &[],
                ));
            }
            let units = if op == '+' {
                i128::from(a.units) + i128::from(b.units)
            } else {
                i128::from(a.units) - i128::from(b.units)
            };
            money_checked(units, &a.currency, &op.to_string(), line)
        }
        (Value::Money(m), n) | (n, Value::Money(m))
            if op == '*' && matches!(n, Value::Int(_) | Value::Big(_)) =>
        {
            let k = n.as_i128().ok_or_else(|| money_too_big("*", line))?;
            let units =
                i128::from(m.units).checked_mul(k).ok_or_else(|| money_too_big("*", line))?;
            money_checked(units, &m.currency, "*", line)
        }
        (Value::List(a), Value::List(b)) if op == '+' => {
            let mut out = (**a).clone();
            out.extend(b.iter().cloned());
            Ok(Value::list(out))
        }
        _ if matches!(l, Value::Float(_)) || matches!(r, Value::Float(_)) => {
            let (x, y) = (as_float(l)?, as_float(r)?);
            Ok(Value::Float(fresh_float(match op {
                '+' => x + y,
                '-' => x - y,
                _ => x * y,
            })))
        }
        _ => {
            if let (Some(a), Some(b)) = (l.as_i128(), r.as_i128()) {
                let v = match op {
                    '+' => a.checked_add(b),
                    '-' => a.checked_sub(b),
                    _ => a.checked_mul(b),
                };
                if let Some(v) = v {
                    return Ok(Value::int128(v));
                }
            }
            let (Some(a), Some(b)) = (l.as_big(), r.as_big()) else {
                return Err(Stop::Raised(
                    if matches!(l, Value::Text(_) | Value::List(_))
                        || matches!(r, Value::Text(_) | Value::List(_))
                    {
                        "NotPorted"
                    } else {
                        "TypeError"
                    },
                ));
            };
            Ok(Value::int(match op {
                '+' => a.add(&b),
                '-' => a.sub(&b),
                _ => a.mul(&b),
            }))
        }
    }
}

// ---- the Money builtins ----------------------------------------------------

fn currency_of(code: &Text) -> Option<Rc<str>> {
    let s = code.to_str()?;
    CURRENCIES.iter().any(|(c, _)| *c == s).then(|| Rc::from(s.as_str()))
}

/// `round_ratio(p, q, mode)`: p / q exactly, rounded by `mode`.
pub fn round_ratio(mut p: i128, mut q: i128, mode: &str) -> i128 {
    if q < 0 {
        p = -p;
        q = -q;
    }
    let (f, r) = floor_divmod(p, q);
    if r == 0 {
        return f;
    }
    if mode == "down" {
        return if p >= 0 { f } else { f + 1 };
    }
    if 2 * r > q {
        return f + 1;
    }
    if 2 * r < q {
        return f;
    }
    if mode == "half_up" {
        return if p >= 0 { f + 1 } else { f };
    }
    if f % 2 == 0 {
        f
    } else {
        f + 1
    }
}

fn money_arg(v: &Value) -> R<Money> {
    match v {
        Value::Money(m) => Ok(m.clone()),
        _ => Err(Stop::Raised("AttributeError")),
    }
}

fn run_money(name: &str, args: &[Value], line: u32) -> R<Value> {
    let arg = |i: usize| args.get(i).cloned().unwrap_or(Value::None);
    match name {
        "money" => {
            let cur = text_of(&arg(1))?;
            let Some(currency) = currency_of(&cur) else {
                return Err(Stop::Error(RunError {
                    code: "E551",
                    message: TextBuf::new()
                        .str("'")
                        .text(&cur)
                        .str("' is not a currency Sabline knows")
                        .done(),
                    line,
                    fixes: Vec::new(),
                    file: None,
                }));
            };
            let units =
                i64::try_from(py_int(&arg(0))?).map_err(|_| Stop::Raised("NotPorted"))?;
            Ok(Value::Money(Money { units, currency }))
        }
        "units_of" => match arg(0) {
            Value::Money(m) => Ok(Value::Int(m.units)),
            xs => {
                let mut total: i128 = 0;
                for m in iterate(&xs)? {
                    total += i128::from(money_arg(&m)?.units);
                    checked_int(Value::int128(total), "units_of", line)?;
                }
                Ok(Value::int128(total))
            }
        },
        "with_units" => {
            let m = money_arg(&arg(0))?;
            let units =
                i64::try_from(py_int(&arg(1))?).map_err(|_| Stop::Raised("NotPorted"))?;
            Ok(Value::Money(Money { units, currency: m.currency }))
        }
        "text_of" => Ok(Value::text(&money_text(&money_arg(&arg(0))?))),
        "parse_money" => parse_money_text(&text_of(&arg(0))?, &text_of(&arg(1))?),
        _ => {
            let mode = text_of(args.last().unwrap_or(&Value::None))?;
            let mode_s = mode.to_str().unwrap_or_default();
            if !ROUNDING.contains(&mode_s.as_str()) {
                return Err(Stop::Error(RunError {
                    code: "E552",
                    message: TextBuf::new()
                        .str("'")
                        .text(&mode)
                        .str("' is not a rounding mode")
                        .done(),
                    line,
                    fixes: Vec::new(),
                    file: None,
                }));
            }
            let m = money_arg(&arg(0))?;
            if name == "percent_of" {
                let (num, den) = (py_int(&arg(1))?, py_int(&arg(2))?);
                if den == 0 {
                    return Err(error(
                        "E403",
                        "percent_of with a denominator of zero",
                        line,
                        &["check the denominator first"],
                    ));
                }
                let units = round_ratio(i128::from(m.units) * num, den, &mode_s);
                return money_checked(units, &m.currency, "percent_of", line);
            }
            let by = py_int(&arg(1))?;
            if by == 0 {
                return Err(fail("cannot divide an amount by zero"));
            }
            let units = round_ratio(i128::from(m.units), by, &mode_s);
            match i64::try_from(units) {
                Ok(u) => Ok(Value::Money(Money { units: u, currency: m.currency })),
                Err(_) => Err(fail(format!(
                    "dividing {} by {by} makes an amount too big to hold",
                    money_text(&m)
                ))),
            }
        }
    }
}

/// `parse_money_text(text, currency)`.
fn parse_money_text(text: &Text, currency: &Text) -> R<Value> {
    let t = text.strip_chars(" \t\r\n");
    let p = t.points();
    let is_upper = |c: u32| (0x41..=0x5A).contains(&c);
    let is_digit = |c: u32| (0x30..=0x39).contains(&c);
    let mut i = 0;
    let mut code: Option<Text> = None;
    if p.len() >= 3 && p[..3].iter().all(|&c| is_upper(c)) {
        code = Some(t.slice(0, 3));
        i = 3;
        while i < p.len() && p[i] == 0x20 {
            i += 1;
        }
    }
    let minus = i < p.len() && p[i] == 0x2D;
    if minus {
        i += 1;
    }
    let whole_start = i;
    while i < p.len() && is_digit(p[i]) {
        i += 1;
    }
    let whole = t.slice(whole_start, i);
    let mut frac: Option<Text> = None;
    if i < p.len() && p[i] == 0x2E {
        let fs = i + 1;
        let mut j = fs;
        while j < p.len() && is_digit(p[j]) {
            j += 1;
        }
        if j > fs {
            frac = Some(t.slice(fs, j));
            i = j;
        }
    }
    if whole.is_empty() || i != p.len() {
        return Err(fail(quoted(text, " is not an amount like 12.50")));
    }
    if let Some(c) = &code {
        if c != currency {
            return Err(fail(
                TextBuf::new()
                    .text(&quoted(text, " is in "))
                    .text(c)
                    .str(", not ")
                    .text(currency)
                    .done(),
            ));
        }
    }
    let cur_s = currency.to_str().unwrap_or_default();
    let Some(cur) = currency_of(currency) else { return Err(Stop::Raised("KeyError")) };
    let digits = currency_digits(&cur_s) as usize;
    if let Some(f) = &frac {
        if digits == 0 {
            return Err(fail(
                TextBuf::new()
                    .text(&quoted(text, " has digits after the point, and "))
                    .text(currency)
                    .str(" has no minor unit")
                    .done(),
            ));
        }
        if f.len() > digits {
            return Err(fail(
                TextBuf::new()
                    .text(&quoted(
                        text,
                        &format!(" has {} digits after the point, and ", f.len()),
                    ))
                    .text(currency)
                    .str(&format!(" has {digits}"))
                    .done(),
            ));
        }
    }
    let whole_s: String = whole.to_string_lossy();
    let whole_s = whole_s.trim_start_matches('0');
    let whole_s = if whole_s.is_empty() { "0" } else { whole_s };
    if whole_s.len() > 19 {
        return Err(fail(quoted(text, " is too big to hold")));
    }
    let mut frac_s = frac.map(|f| f.to_string_lossy()).unwrap_or_default();
    while frac_s.len() < digits {
        frac_s.push('0');
    }
    let w: i128 = whole_s.parse().unwrap_or(0);
    let f: i128 = if frac_s.is_empty() { 0 } else { frac_s.parse().unwrap_or(0) };
    let mut units = w * 10i128.pow(digits as u32) + f;
    if minus {
        units = -units;
    }
    match i64::try_from(units) {
        Ok(u) => Ok(Value::Money(Money { units: u, currency: cur })),
        Err(_) => Err(fail(quoted(text, " is too big to hold"))),
    }
}

// ---- the JSON builtins -----------------------------------------------------

/// `walk(doc, path)`: the document read, then each step of the path.
fn walk(doc: &Value, path: &Value) -> R<Value> {
    let doc = text_of(doc)?;
    let path = text_of(path)?;
    let mut cur = match pyjson::loads(&doc) {
        Ok(v) => v,
        Err(e) => {
            return Err(fail(
                TextBuf::new().str("this is not valid JSON: ").text(&Text::from(e)).done(),
            ))
        }
    };
    if path.is_empty() {
        return Ok(cur);
    }
    let dotted: Vec<u32> = path
        .points()
        .iter()
        .filter(|&&c| c != 0x5D)
        .map(|&c| if c == 0x5B { 0x2E } else { c })
        .collect();
    let looking = |what: &str| {
        TextBuf::new().str(what).str(" (while looking for '").text(&path).str("')").done()
    };
    for step in Text::from(dotted).split(&Text::from(".")) {
        if step.is_empty() {
            continue;
        }
        cur = match &cur {
            Value::List(xs) => {
                let Some(idx) = pyjson::py_int_of_text(&step) else {
                    return Err(fail(
                        TextBuf::new()
                            .text(&quoted(&step, " is not a position in a list"))
                            .text(&looking(""))
                            .done(),
                    ));
                };
                let n = xs.len() as i128;
                let at = idx.to_i128().filter(|&i| -n <= i && i < n);
                let Some(at) = at else {
                    return Err(fail(looking(&format!(
                        "position {} is outside this list of {}",
                        idx.to_decimal(),
                        xs.len()
                    ))));
                };
                let at = if at < 0 { at + n } else { at };
                xs[at as usize].clone()
            }
            Value::Map(m) => match m.get(&Value::Text(step.clone()))? {
                Some(v) => v.clone(),
                None => {
                    return Err(fail(
                        TextBuf::new()
                            .str("there is no ")
                            .text(&quoted(&step, " here"))
                            .text(&looking(""))
                            .done(),
                    ))
                }
            },
            other => {
                return Err(fail(looking(&format!(
                    "cannot look inside {}",
                    other.type_name()
                ))));
            }
        };
    }
    Ok(cur)
}

/// `json_of`'s `plain(v)`: what `json.dumps` is handed.
fn plain(v: &Value) -> R<Value> {
    Ok(match v {
        Value::Map(m) => {
            let mut d = Dict::new();
            for (k, x) in m.entries() {
                d.set(Value::Text(py_str(k)), plain(x)?)?;
            }
            Value::Map(Rc::new(d))
        }
        Value::List(xs) => Value::list(xs.iter().map(plain).collect::<R<Vec<_>>>()?),
        Value::Record(r) => {
            let mut d = Dict::new();
            for (f, x) in &r.fields {
                d.set(Value::text(f), plain(x)?)?;
            }
            Value::Map(Rc::new(d))
        }
        Value::Money(m) => {
            let mut d = Dict::new();
            d.set(Value::text("currency"), Value::text(&m.currency))?;
            d.set(Value::text("units"), Value::Int(m.units))?;
            Value::Map(Rc::new(d))
        }
        other => other.clone(),
    })
}

// ---- promises ----------------------------------------------------------------

/// `expr_vars(e)`: the names an expression reads.
pub fn expr_vars(e: &Expr) -> HashSet<String> {
    let mut out = HashSet::new();
    vars_into(e, &mut out);
    out
}

fn vars_into(e: &Expr, out: &mut HashSet<String>) {
    match e {
        Expr::Var { name, .. } => {
            out.insert(name.clone());
        }
        Expr::Not { value, .. } | Expr::Neg { value, .. } | Expr::TryExpr { value, .. } => {
            vars_into(value, out)
        }
        Expr::ListLit { items, .. } => items.iter().for_each(|i| vars_into(i, out)),
        Expr::BinOp { left, right, .. } => {
            vars_into(left, out);
            vars_into(right, out);
        }
        Expr::MapLit { entries, .. } => entries.iter().for_each(|(k, v)| {
            vars_into(k, out);
            vars_into(v, out);
        }),
        Expr::FieldGet { obj, .. } => vars_into(obj, out),
        Expr::RecordLit { fields, .. } => fields.iter().for_each(|(_, v)| vars_into(v, out)),
        Expr::Call { args, .. } => args.iter().for_each(|a| vars_into(a, out)),
        _ => {}
    }
}

/// `vals(expr)`: each name the promise reads, sorted, as `name = value`
/// with the value as an f-string writes it - or `<secret>` for a name
/// whose type holds a secret.
fn vals(
    expr: &Expr,
    entry: &HashMap<String, Value>,
    result: Option<&Value>,
    hush: &HashSet<String>,
    hush_result: bool,
) -> Text {
    let mut scope: HashMap<&str, &Value> =
        entry.iter().map(|(k, v)| (k.as_str(), v)).collect();
    if let Some(r) = result {
        scope.insert("result", r);
    }
    let mut names: Vec<String> =
        expr_vars(expr).into_iter().filter(|n| scope.contains_key(n.as_str())).collect();
    names.sort();
    let mut out = TextBuf::new();
    for (i, n) in names.iter().enumerate() {
        if i > 0 {
            out.push_str(", ");
        }
        out.push_str(n);
        out.push_str(" = ");
        if hush.contains(n) || (n == "result" && hush_result) {
            out.push_str(REDACTED);
        } else {
            out.push_text(&py_str(scope[n.as_str()]));
        }
    }
    out.done()
}
