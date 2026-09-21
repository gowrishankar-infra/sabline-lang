//! The canonical AST dump: one document both runtimes write for one file.
//!
//! rt/README.md states the format. It is not a stable interface and is not
//! in `tests/api/golden.json`; it is a comparison surface, and
//! STABILITY.md's "anything else in the package" clause covers it.
//!
//! The shape in one paragraph: a document is an object with `dump`, `ok`
//! and then either `program` or `error`. A node is an object with `kind`
//! and the node's own fields. Keys are sorted, so the order below is not
//! the order in the file. A whole number is decimal **text**, because the
//! reference's integer literals are arbitrary precision. A float is the
//! shortest decimal that reads back as the same double, written
//! `d[.ddd]eE`. A line is a number; there is no column, because the
//! reference's tokens carry none.

use crate::errors::SablineError;
use crate::json::Json;
use crate::nodes::{Expr, Function, Import, Program, RecordDef, Stmt};
use crate::pyrepr::canonical_float;

/// The version of the dump format, which the document carries so that a
/// difference in the format is not read as a difference in a parser.
pub const DUMP_VERSION: i64 = 1;

/// The document for a file that parsed.
pub fn program_document(program: &Program) -> Json {
    Json::obj([
        ("dump", Json::Int(DUMP_VERSION)),
        ("ok", Json::Bool(true)),
        (
            "program",
            Json::obj([
                ("funcs", Json::List(program.funcs.iter().map(function).collect())),
                ("imports", Json::List(program.imports.iter().map(import).collect())),
                ("records", Json::List(program.records.iter().map(record).collect())),
            ]),
        ),
    ])
}

/// The document for a file the lexer or the parser refused.
pub fn error_document(error: &SablineError) -> Json {
    Json::obj([
        ("dump", Json::Int(DUMP_VERSION)),
        (
            "error",
            Json::obj([
                ("code", Json::text(error.code)),
                (
                    "fixes",
                    Json::List(error.fixes.iter().map(|f| Json::text(f.clone())).collect()),
                ),
                ("line", Json::Int(i64::from(error.line))),
                ("message", Json::text(error.message.clone())),
            ]),
        ),
        ("ok", Json::Bool(false)),
    ])
}

fn texts(items: &[String]) -> Json {
    Json::List(items.iter().map(|s| Json::text(s.clone())).collect())
}

fn pairs(items: &[(String, String)]) -> Json {
    Json::List(
        items
            .iter()
            .map(|(a, b)| Json::List(vec![Json::text(a.clone()), Json::text(b.clone())]))
            .collect(),
    )
}

fn clauses(items: &[(Expr, u32)]) -> Json {
    Json::List(
        items
            .iter()
            .map(|(e, line)| Json::List(vec![expr(e), Json::Int(i64::from(*line))]))
            .collect(),
    )
}

fn body(items: &[Stmt]) -> Json {
    Json::List(items.iter().map(stmt).collect())
}

fn maybe(text: &Option<String>) -> Json {
    match text {
        Some(t) => Json::text(t.clone()),
        None => Json::Null,
    }
}

fn function(f: &Function) -> Json {
    Json::obj([
        ("body", body(&f.body)),
        ("can_fail", Json::Bool(f.can_fail)),
        ("captures", pairs(&f.captures)),
        ("effects", texts(&f.effects)),
        ("ensures", clauses(&f.ensures)),
        ("free_names", texts(&f.free_names)),
        ("is_lambda", Json::Bool(f.is_lambda)),
        ("kind", Json::text("Function")),
        ("line", Json::Int(i64::from(f.line))),
        ("name", Json::text(f.name.clone())),
        ("params", pairs(&f.params)),
        ("requires", clauses(&f.requires)),
        ("return_type", maybe(&f.return_type)),
        ("src_file", Json::text(f.src_file.clone())),
        ("type_vars", texts(&f.type_vars)),
    ])
}

fn record(r: &RecordDef) -> Json {
    Json::obj([
        ("fields", pairs(&r.fields)),
        ("kind", Json::text("RecordDef")),
        ("line", Json::Int(i64::from(r.line))),
        ("name", Json::text(r.name.clone())),
        ("src_file", Json::text(r.src_file.clone())),
    ])
}

fn import(i: &Import) -> Json {
    Json::obj([
        ("alias", maybe(&i.alias)),
        ("line", Json::Int(i64::from(i.line))),
        ("path", Json::text(i.path.clone())),
    ])
}

fn stmt(s: &Stmt) -> Json {
    match s {
        Stmt::Let { name, value, line, ann } => Json::obj([
            ("ann", maybe(ann)),
            ("kind", Json::text("Let")),
            ("line", Json::Int(i64::from(*line))),
            ("name", Json::text(name.clone())),
            ("value", expr(value)),
        ]),
        Stmt::Return { value, line } => Json::obj([
            ("kind", Json::text("Return")),
            ("line", Json::Int(i64::from(*line))),
            ("value", value.as_ref().map(expr).unwrap_or(Json::Null)),
        ]),
        Stmt::If { cond, then, other, line } => Json::obj([
            ("cond", expr(cond)),
            ("kind", Json::text("If")),
            ("line", Json::Int(i64::from(*line))),
            ("other", body(other)),
            ("then", body(then)),
        ]),
        Stmt::While { cond, body: b, line, invariants } => Json::obj([
            ("body", body(b)),
            ("cond", expr(cond)),
            ("invariants", clauses(invariants)),
            ("kind", Json::text("While")),
            ("line", Json::Int(i64::from(*line))),
        ]),
        Stmt::Assign { name, value, line } => Json::obj([
            ("kind", Json::text("Assign")),
            ("line", Json::Int(i64::from(*line))),
            ("name", Json::text(name.clone())),
            ("value", expr(value)),
        ]),
        Stmt::Block { stmts, line } => Json::obj([
            ("kind", Json::text("Block")),
            ("line", Json::Int(i64::from(*line))),
            ("stmts", body(stmts)),
        ]),
        Stmt::ExprStmt { expr: e, line } => Json::obj([
            ("expr", expr(e)),
            ("kind", Json::text("ExprStmt")),
            ("line", Json::Int(i64::from(*line))),
        ]),
        Stmt::FailStmt { value, line } => Json::obj([
            ("kind", Json::text("FailStmt")),
            ("line", Json::Int(i64::from(*line))),
            ("value", expr(value)),
        ]),
        Stmt::Check { subject, line, ok_name, ok_body, fail_name, fail_body } => Json::obj([
            ("fail_body", body(fail_body)),
            ("fail_name", Json::text(fail_name.clone())),
            ("kind", Json::text("Check")),
            ("line", Json::Int(i64::from(*line))),
            ("ok_body", body(ok_body)),
            ("ok_name", maybe(ok_name)),
            ("subject", expr(subject)),
        ]),
    }
}

fn expr(e: &Expr) -> Json {
    match e {
        Expr::Num { value } => {
            Json::obj([("kind", Json::text("Num")), ("value", Json::text(value.clone()))])
        }
        Expr::FloatNum { value } => Json::obj([
            ("kind", Json::text("FloatNum")),
            ("value", Json::text(canonical_float(*value))),
        ]),
        Expr::Neg { value, line } => Json::obj([
            ("kind", Json::text("Neg")),
            ("line", Json::Int(i64::from(*line))),
            ("value", expr(value)),
        ]),
        Expr::Str { value } => {
            Json::obj([("kind", Json::text("Str")), ("value", Json::text(value.clone()))])
        }
        Expr::Bool { value } => {
            Json::obj([("kind", Json::text("Bool")), ("value", Json::Bool(*value))])
        }
        Expr::Closure { name, free, line } => Json::obj([
            ("free", texts(free)),
            ("kind", Json::text("Closure")),
            ("line", Json::Int(i64::from(*line))),
            ("name", Json::text(name.clone())),
        ]),
        Expr::Var { name, line } => Json::obj([
            ("kind", Json::text("Var")),
            ("line", Json::Int(i64::from(*line))),
            ("name", Json::text(name.clone())),
        ]),
        Expr::BinOp { op, left, right, line } => Json::obj([
            ("kind", Json::text("BinOp")),
            ("left", expr(left)),
            ("line", Json::Int(i64::from(*line))),
            ("op", Json::text(op.clone())),
            ("right", expr(right)),
        ]),
        Expr::Call { name, args, line } => Json::obj([
            ("args", Json::List(args.iter().map(expr).collect())),
            ("kind", Json::text("Call")),
            ("line", Json::Int(i64::from(*line))),
            ("name", Json::text(name.clone())),
        ]),
        Expr::Not { value, line } => Json::obj([
            ("kind", Json::text("Not")),
            ("line", Json::Int(i64::from(*line))),
            ("value", expr(value)),
        ]),
        Expr::RecordLit { name, fields, line } => Json::obj([
            (
                "fields",
                Json::List(
                    fields
                        .iter()
                        .map(|(f, v)| Json::List(vec![Json::text(f.clone()), expr(v)]))
                        .collect(),
                ),
            ),
            ("kind", Json::text("RecordLit")),
            ("line", Json::Int(i64::from(*line))),
            ("name", Json::text(name.clone())),
        ]),
        Expr::FieldGet { obj, field, line } => Json::obj([
            ("field", Json::text(field.clone())),
            ("kind", Json::text("FieldGet")),
            ("line", Json::Int(i64::from(*line))),
            ("obj", expr(obj)),
        ]),
        Expr::ListLit { items, line } => Json::obj([
            ("items", Json::List(items.iter().map(expr).collect())),
            ("kind", Json::text("ListLit")),
            ("line", Json::Int(i64::from(*line))),
        ]),
        Expr::MapLit { entries, line } => Json::obj([
            (
                "entries",
                Json::List(
                    entries.iter().map(|(k, v)| Json::List(vec![expr(k), expr(v)])).collect(),
                ),
            ),
            ("kind", Json::text("MapLit")),
            ("line", Json::Int(i64::from(*line))),
        ]),
        Expr::TryExpr { value, line } => Json::obj([
            ("kind", Json::text("TryExpr")),
            ("line", Json::Int(i64::from(*line))),
            ("value", expr(value)),
        ]),
    }
}
