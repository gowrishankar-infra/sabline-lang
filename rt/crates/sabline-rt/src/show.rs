//! An expression as readable source text, for messages: `sabline/parser.py`'s
//! `expr_str` and `nice_name`.
//!
//! `expr_str` is not a pretty-printer and must not become one. It writes
//! what the reference writes - a text literal between quotes with its
//! characters as they are, unescaped; a float as CPython's `repr`; an
//! operand in brackets only where it binds less tightly - because what it
//! writes is quoted inside messages the agreement gate compares.

use crate::nodes::Expr;
use crate::pyrepr::py_float_repr;

/// `nice_name(name)`: a lifted function value is "this function value",
/// anything else is its name in quotes.
pub fn nice_name(name: &str) -> String {
    if name.starts_with("fn#") {
        "this function value".to_string()
    } else {
        format!("'{name}'")
    }
}

fn precedence(op: &str) -> u8 {
    match op {
        "or" => 1,
        "and" => 2,
        "==" | "!=" | "<" | ">" | "<=" | ">=" => 3,
        "+" | "-" => 4,
        "*" | "/" | "%" => 5,
        _ => 6,
    }
}

/// `expr_str(e)`: an expression back as source text.
pub fn expr_str(e: &Expr) -> String {
    match e {
        Expr::Num { value } => value.clone(),
        Expr::FloatNum { value } => py_float_repr(*value),
        Expr::Neg { value, .. } => format!("-{}", expr_str(value)),
        Expr::TryExpr { value, .. } => format!("try {}", expr_str(value)),
        Expr::Str { value } => format!("\"{value}\""),
        Expr::Bool { value } => if *value { "true" } else { "false" }.to_string(),
        Expr::Var { name, .. } => name.clone(),
        Expr::Call { name, args, .. } => {
            let shown: Vec<String> = args.iter().map(expr_str).collect();
            format!("{name}({})", shown.join(", "))
        }
        Expr::BinOp { op, left, right, .. } => {
            let here = precedence(op);
            let side = |sub: &Expr, is_right: bool| -> String {
                let text = expr_str(sub);
                if let Expr::BinOp { op: inner, .. } = sub {
                    let there = precedence(inner);
                    if there < here || (there == here && is_right) {
                        return format!("({text})");
                    }
                }
                text
            };
            format!("{} {op} {}", side(left, false), side(right, true))
        }
        Expr::Not { value, .. } => format!("not {}", expr_str(value)),
        Expr::ListLit { items, .. } => {
            let shown: Vec<String> = items.iter().map(expr_str).collect();
            format!("[{}]", shown.join(", "))
        }
        Expr::MapLit { entries, .. } => {
            let shown: Vec<String> = entries
                .iter()
                .map(|(k, v)| format!("{}: {}", expr_str(k), expr_str(v)))
                .collect();
            format!("{{{}}}", shown.join(", "))
        }
        Expr::FieldGet { obj, field, .. } => format!("{}.{field}", expr_str(obj)),
        Expr::RecordLit { name, fields, .. } => {
            let shown: Vec<String> =
                fields.iter().map(|(f, v)| format!("{f}: {}", expr_str(v))).collect();
            format!("{name}({})", shown.join(", "))
        }
        Expr::Closure { .. } => "?".to_string(),
    }
}
