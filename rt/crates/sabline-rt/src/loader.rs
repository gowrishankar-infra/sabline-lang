//! Stage 3, the loader: a file and everything it imports, as one program,
//! each function remembering the file it came from. `sabline/loader.py`'s
//! `load_program`, step for step.
//!
//! What a check reports depends on the loader in three places that are
//! easy to get wrong, and each is copied rather than reconciled:
//!
//! * **A file's name is spelled the way Python joined it**:
//!   `os.path.join(os.path.dirname(importer), path)`, with no
//!   normalising, which is what an error's `file` and an E512 or E513
//!   message say. `crate::pypath` is CPython's `os.path` for that reason.
//! * **An import that cannot be read falls back to the shipped standard
//!   library**, by its base name, before it is an error - so
//!   `import "money.vel"` from anywhere finds the one beside the package.
//!   The host says where that is (`install_dir`): the directory holding
//!   `stdlib/`, which for the Python package is the directory holding
//!   `sabline/`.
//! * **A file's imports are loaded before its own functions are added**,
//!   so the program's functions are in the order of a depth-first walk
//!   that finishes each import first, and a name defined twice is found
//!   at the place that order reaches it.
//!
//! The counter that names lifted function values (`fn#N`, `for#N`) runs
//! across every file one load parses, in the order it parses them, because
//! in Python it is a class attribute of the parser.

use std::collections::{HashMap, HashSet};

use crate::errors::{Answer, SablineError};
use crate::lexer::lex;
use crate::nodes::{Expr, Function, RecordDef, Stmt};
use crate::parser::Parser;
use crate::pypath::{self, os_path};
use crate::source::{not_found, translate_newlines};
use crate::tables::{is_builtin, is_new_builtin};

/// What `load_program` answers: every function and every record of the
/// program, imports first.
#[derive(Debug, Clone, Default)]
pub struct Loaded {
    /// The functions, in the order the loader added them.
    pub funcs: Vec<Function>,
    /// The records, in the same order.
    pub records: Vec<RecordDef>,
}

struct Loader<'a> {
    install_dir: &'a str,
    entry_source: Option<&'a str>,
    loaded: Loaded,
    files: &'a mut Vec<String>,
    fn_src: HashMap<String, String>,
    rec_src: HashMap<String, String>,
    visited: HashSet<String>,
    lambda_n: u32,
}

/// `load_program(entry)`: the entry file and everything it imports.
///
/// `install_dir` is where the shipped standard library is looked for, as
/// `install_dir/stdlib/<name>`.
pub fn load_program(entry: &str, install_dir: &str) -> Answer<Loaded> {
    load_program_recording(entry, install_dir, &mut Vec::new())
}

/// `load_program(entry, loaded=files)`: the same, and the path of each file
/// read put in `files` in the order it was read - the entry first - whether
/// or not the program then loads. A receipt names them (9.0, M3).
pub fn load_program_recording(
    entry: &str,
    install_dir: &str,
    files: &mut Vec<String>,
) -> Answer<Loaded> {
    load_program_given(entry, None, install_dir, files)
}

/// `load_program(entry, entry_source, loaded=files)`: the same, with the
/// entry's text given rather than read from `entry` - `sabline.run(source,
/// path=...)`, whose path is where imports resolve from and need not hold
/// that text (9.0, M3).
pub fn load_program_given(
    entry: &str,
    entry_source: Option<&str>,
    install_dir: &str,
    files: &mut Vec<String>,
) -> Answer<Loaded> {
    let mut loader = Loader {
        install_dir,
        entry_source,
        loaded: Loaded::default(),
        files,
        fn_src: HashMap::new(),
        rec_src: HashMap::new(),
        visited: HashSet::new(),
        lambda_n: 0,
    };
    loader.load(entry, None, 1, None)?;
    let mut loaded = loader.loaded;
    bind_new_builtins(&mut loaded.funcs);
    Ok(loaded)
}

/// The directory of the shipped standard library under `install_dir`.
pub fn stdlib_dir(install_dir: &str) -> String {
    os_path::join(install_dir, "stdlib")
}

impl Loader<'_> {
    fn load(
        &mut self,
        path: &str,
        importer: Option<&str>,
        iline: u32,
        alias: Option<&str>,
    ) -> Answer<()> {
        let ap = pypath::abspath(path);
        if self.visited.contains(&ap) {
            return Ok(()); // already loaded (diamond or cycle)
        }
        self.visited.insert(ap.clone());
        let given = if importer.is_none() { self.entry_source } else { None };
        let read = match given {
            Some(text) => Ok(text.as_bytes().to_vec()),
            None => std::fs::read(path),
        };
        let bytes = match read {
            Ok(bytes) => bytes,
            Err(_) => {
                if let Some(importer) = importer {
                    let shipped =
                        os_path::join(&stdlib_dir(self.install_dir), &os_path::basename(path));
                    if pypath::exists(&shipped) {
                        self.visited.remove(&ap);
                        return self.load(&shipped, Some(importer), iline, alias);
                    }
                    return Err(SablineError::with_fixes(
                        "E512",
                        format!("cannot find imported file '{path}'"),
                        iline,
                        &[
                            "check the path in the import line",
                            "paths are relative to the importing file",
                        ],
                    )
                    .in_file(importer));
                }
                return Err(not_found(path));
            }
        };
        let Ok(text) = std::str::from_utf8(&bytes) else {
            let refused = SablineError::with_fixes(
                "E512",
                format!("cannot import '{path}': it is not UTF-8 text, so it is not Sabline source"),
                iline,
                &["an import names a .vel file"],
            );
            return Err(match importer {
                Some(importer) => refused.in_file(importer),
                None => refused,
            });
        };
        // read, so named by a receipt, whether or not it parses
        self.files.push(path.to_string());
        let source = translate_newlines(text);
        let parsed = lex(&source, false).and_then(|tokens| {
            Parser::continuing(tokens, self.lambda_n).parse_program_counted()
        });
        let (program, counted) = match parsed {
            Ok(done) => done,
            Err(mut e) => {
                if let Some(importer) = importer {
                    if !os_path::normcase(path).ends_with(&os_path::normcase(".vel")) {
                        // A lexer or parser error quotes what it found, and in
                        // a file that is not Sabline source what it found is
                        // the file's content. The error names the file and
                        // says nothing about what is in it (8.1).
                        return Err(SablineError::with_fixes(
                            e.code,
                            format!(
                                "'{path}' is imported, and it is not Sabline source; what \
                                 it holds is not shown"
                            ),
                            iline,
                            &["an import names a .vel file"],
                        )
                        .in_file(importer));
                    }
                }
                if e.file.is_none() {
                    e.file = Some(path.to_string());
                }
                return Err(e);
            }
        };
        self.lambda_n = counted;
        let base = os_path::dirname(path);
        for import in &program.imports {
            let next = if base.is_empty() {
                import.path.clone()
            } else {
                os_path::join(&base, &import.path)
            };
            self.load(&next, Some(path), import.line, import.alias.as_deref())?;
        }
        let mut funcs = program.funcs;
        if let Some(alias) = alias {
            qualify(&mut funcs, alias);
        }
        for mut f in funcs {
            f.src_file = path.to_string();
            if let Some(first) = self.fn_src.get(&f.name) {
                let place = if first == path {
                    format!("twice in '{path}'")
                } else {
                    format!("in both '{first}' and '{path}'")
                };
                return Err(SablineError::with_fixes(
                    "E513",
                    format!("function '{}' is defined {place}", f.name),
                    f.line,
                    &["rename one of them"],
                )
                .in_file(path));
            }
            self.fn_src.insert(f.name.clone(), path.to_string());
            self.loaded.funcs.push(f);
        }
        for mut r in program.records {
            r.src_file = path.to_string();
            if let Some(first) = self.rec_src.get(&r.name) {
                let place = if first == path {
                    format!("twice in '{path}'")
                } else {
                    format!("in both '{first}' and '{path}'")
                };
                return Err(SablineError::with_fixes(
                    "E513",
                    format!("record '{}' is defined {place}", r.name),
                    r.line,
                    &["rename one of them"],
                )
                .in_file(path));
            }
            self.rec_src.insert(r.name.clone(), path.to_string());
            self.loaded.records.push(r);
        }
        Ok(())
    }
}

/// Every expression in a statement list, each visited once, outermost
/// first, so that a rename can be made in place.
pub fn each_expr_mut(stmts: &mut [Stmt], visit: &mut dyn FnMut(&mut Expr)) {
    for s in stmts {
        match s {
            Stmt::Let { value, .. }
            | Stmt::Assign { value, .. }
            | Stmt::FailStmt { value, .. } => {
                expr_mut(value, visit);
            }
            Stmt::Return { value, .. } => {
                if let Some(v) = value {
                    expr_mut(v, visit);
                }
            }
            Stmt::ExprStmt { expr, .. } => expr_mut(expr, visit),
            Stmt::If { cond, then, other, .. } => {
                expr_mut(cond, visit);
                each_expr_mut(then, visit);
                each_expr_mut(other, visit);
            }
            Stmt::While { cond, body, invariants, .. } => {
                expr_mut(cond, visit);
                each_expr_mut(body, visit);
                for (e, _) in invariants {
                    expr_mut(e, visit);
                }
            }
            Stmt::Block { stmts, .. } => each_expr_mut(stmts, visit),
            Stmt::Check { subject, ok_body, fail_body, .. } => {
                expr_mut(subject, visit);
                each_expr_mut(ok_body, visit);
                each_expr_mut(fail_body, visit);
            }
        }
    }
}

/// An expression and every expression inside it.
pub fn expr_mut(e: &mut Expr, visit: &mut dyn FnMut(&mut Expr)) {
    visit(e);
    match e {
        Expr::Neg { value, .. } | Expr::Not { value, .. } | Expr::TryExpr { value, .. } => {
            expr_mut(value, visit);
        }
        Expr::BinOp { left, right, .. } => {
            expr_mut(left, visit);
            expr_mut(right, visit);
        }
        Expr::Call { args, .. } | Expr::ListLit { items: args, .. } => {
            for a in args {
                expr_mut(a, visit);
            }
        }
        Expr::RecordLit { fields, .. } => {
            for (_, v) in fields {
                expr_mut(v, visit);
            }
        }
        Expr::FieldGet { obj, .. } => expr_mut(obj, visit),
        Expr::MapLit { entries, .. } => {
            for (k, v) in entries {
                expr_mut(k, visit);
                expr_mut(v, visit);
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

/// Every expression of a function: its body, then its promises.
fn function_exprs_mut(f: &mut Function, visit: &mut dyn FnMut(&mut Expr)) {
    each_expr_mut(&mut f.body, visit);
    for (e, _) in &mut f.requires {
        expr_mut(e, visit);
    }
    for (e, _) in &mut f.ensures {
        expr_mut(e, visit);
    }
}

/// `qualify(fs, alias)`: a library imported with a name has its functions
/// renamed `alias.name`, and so does every reference it makes to its own
/// functions. A call to a builtin older than 4.3 reaches the builtin and
/// keeps its name. A lifted function value is renamed with the rest, and
/// so is the `Closure` that names it: until 9.0 it was not, in either
/// runtime, and a library making a function value was refused, imported
/// with a name, as "unknown function value 'fn#1'" (E402).
pub fn qualify(fs: &mut [Function], alias: &str) {
    let local: HashSet<String> = fs.iter().map(|f| f.name.clone()).collect();
    let mut rename = |e: &mut Expr| match e {
        Expr::Call { name, .. } if is_builtin(name) && !is_new_builtin(name) => {}
        Expr::Call { name, .. } | Expr::Var { name, .. } | Expr::Closure { name, .. }
            if local.contains(name.as_str()) =>
        {
            *name = format!("{alias}.{name}");
        }
        _ => {}
    };
    for f in fs.iter_mut() {
        function_exprs_mut(f, &mut rename);
    }
    for f in fs.iter_mut() {
        f.name = format!("{alias}.{}", f.name);
    }
}

/// `_bind_new_builtins(funcs)`: inside a library imported with a name, a
/// call to a builtin added from 4.3 on can only mean the builtin. When the
/// program's own plain names hide one, the library's calls to it are bound
/// to it, as `@name`.
fn bind_new_builtins(funcs: &mut [Function]) {
    let hidden: HashSet<String> = funcs
        .iter()
        .filter(|f| !f.name.contains('.') && is_new_builtin(&f.name))
        .map(|f| f.name.clone())
        .collect();
    if hidden.is_empty() {
        return;
    }
    let mut bind = |e: &mut Expr| {
        if let Expr::Call { name, .. } = e {
            if hidden.contains(name.as_str()) {
                *name = format!("@{name}");
            }
        }
    };
    for f in funcs.iter_mut().filter(|f| f.name.contains('.')) {
        function_exprs_mut(f, &mut bind);
    }
}

/// `blame(fn_or_rec, err)`: the file an error is about, innermost wins.
pub fn blame(src_file: &str, mut err: SablineError) -> SablineError {
    if err.file.is_none() && !src_file.is_empty() {
        err.file = Some(src_file.to_string());
    }
    err
}

/// `unknown_function(name, line, known)`: one message for an unknown
/// name, namespace-aware. `known` is every function name in the program.
pub fn unknown_function<'a>(
    name: &str,
    line: u32,
    known: impl Iterator<Item = &'a str> + Clone,
) -> SablineError {
    if let Some((ns, fname)) = name.split_once('.') {
        let mut spaces: Vec<&str> = known
            .clone()
            .filter(|n| n.contains('.'))
            .map(|n| n.split('.').next().unwrap_or(n))
            .collect();
        spaces.sort_unstable();
        spaces.dedup();
        if spaces.contains(&ns) {
            let prefix = format!("{ns}.");
            let mut near: Vec<&str> = known
                .filter(|n| n.starts_with(&prefix))
                .map(|n| n.split_once('.').map_or(n, |(_, rest)| rest))
                .collect();
            near.sort_unstable();
            let shown: Vec<&str> = near.iter().take(8).copied().collect();
            let more = if near.len() > 8 { " ..." } else { "" };
            return SablineError::with_owned_fixes(
                "E200",
                format!("'{ns}' has no function called '{fname}'"),
                line,
                vec![
                    format!("available in '{ns}': {}{more}", shown.join(", ")),
                    "check the spelling of the name".to_string(),
                ],
            );
        }
        let second = if spaces.is_empty() {
            "an import only gets a name if you write 'as'".to_string()
        } else {
            format!("names in scope: {}", spaces.join(", "))
        };
        return SablineError::with_owned_fixes(
            "E200",
            format!("no import is named '{ns}'"),
            line,
            vec![format!("name an import: import \"lib.vel\" as {ns}"), second],
        );
    }
    SablineError::with_owned_fixes(
        "E200",
        format!("unknown function '{name}'"),
        line,
        vec![
            format!("define 'fn {name}(...)' somewhere"),
            "check the spelling of the name".to_string(),
        ],
    )
}
