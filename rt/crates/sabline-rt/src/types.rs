//! Types as text, the way the Python checker holds them.
//!
//! A type in the reference is a string, such as `Int`, `List of Text`,
//! `Map of Text to Money of INR`, `Secret of Bool` or
//! `fn(Int, Text) -> Bool`, and every rule is written over the string. So
//! it is here: the same prefixes, the same `partition(" to ")`, the same
//! scan for a function type's parts. A tree would be tidier, and a tree would be a second
//! definition of what a type is, which is the thing the agreement gate
//! exists to stop.
//!
//! What is here is `sabline/lexer.py`'s `fn_sig_parts` and
//! `type_mentions`, and `sabline/wrappers.py`: `Money of C` and
//! `Secret of T`, the two types that wrap another.

use std::collections::HashMap;

use crate::errors::SablineError;
use crate::nodes::Function;

/// `"Secret of "`.
pub const SECRET_PREFIX: &str = "Secret of ";

/// Python's `str.strip()` with no argument.
fn strip(s: &str) -> &str {
    crate::pyrepr::py_strip(s)
}

/// `fn_sig_parts(t)`: `fn(A, B) -> R` as `([A, B], R)`, or `None` when
/// `t` is not a function type.
pub fn fn_sig_parts(t: &str) -> Option<(Vec<String>, String)> {
    if !t.starts_with("fn(") {
        return None;
    }
    let chars: Vec<char> = t.chars().collect();
    let mut depth = 0usize;
    let mut i = 3;
    let mut start = 3;
    let mut parts = Vec::new();
    while i < chars.len() {
        let c = chars[i];
        if c == '(' {
            depth += 1;
        } else if c == ')' {
            if depth == 0 {
                break;
            }
            depth -= 1;
        } else if c == ',' && depth == 0 {
            let piece: String = chars[start..i].iter().collect();
            parts.push(strip(&piece).to_string());
            start = i + 1;
        }
        i += 1;
    }
    let last: String = chars[start.min(chars.len())..i.min(chars.len())].iter().collect();
    let last = strip(&last);
    if !last.is_empty() {
        parts.push(last.to_string());
    }
    let rest: String = chars.get(i + 1..).map(|r| r.iter().collect()).unwrap_or_default();
    let ret = match rest.strip_prefix(" -> ") {
        Some(r) => strip(r).to_string(),
        None => "Unit".to_string(),
    };
    Some((parts, ret))
}

/// `type_mentions(t, tv)`: whether type `t` mentions type variable `tv`.
pub fn type_mentions(t: &str, tv: &str) -> bool {
    if t == tv {
        return true;
    }
    if let Some(cur) = t.strip_prefix("Money of ") {
        return cur == tv;
    }
    if let Some(inner) = t.strip_prefix(SECRET_PREFIX) {
        return type_mentions(inner, tv);
    }
    if let Some(inner) = t.strip_prefix("List of ") {
        return type_mentions(inner, tv);
    }
    if let Some(rest) = t.strip_prefix("Map of ") {
        let (key, val) = partition_to(rest);
        return type_mentions(key, tv) || type_mentions(val, tv);
    }
    if let Some((parts, ret)) = fn_sig_parts(t) {
        return parts.iter().any(|p| type_mentions(p, tv)) || type_mentions(&ret, tv);
    }
    false
}

/// `rest.partition(" to ")` as (before, after), the separator dropped.
pub fn partition_to(rest: &str) -> (&str, &str) {
    match rest.split_once(" to ") {
        Some((k, v)) => (k, v),
        None => (rest, ""),
    }
}

/// `is_money(t)`.
pub fn is_money(t: &str) -> bool {
    t.starts_with("Money of ")
}

/// `is_secret(t)`.
pub fn is_secret(t: &str) -> bool {
    t.starts_with(SECRET_PREFIX)
}

/// `secret_inner(t)`: what a `Secret of` wraps.
pub fn secret_inner(t: &str) -> &str {
    &t[SECRET_PREFIX.len().min(t.len())..]
}

/// `currency_clash(a, b)`: two types that differ only in the currency of
/// an amount - `Money of INR` and `Money of USD`, or lists, maps or
/// secrets of them.
pub fn currency_clash(a: &str, b: &str) -> bool {
    if is_secret(a) && is_secret(b) {
        return currency_clash(secret_inner(a), secret_inner(b));
    }
    if is_money(a) && is_money(b) {
        return a != b;
    }
    if let (Some(x), Some(y)) = (a.strip_prefix("List of "), b.strip_prefix("List of ")) {
        return currency_clash(x, y);
    }
    if let (Some(x), Some(y)) = (a.strip_prefix("Map of "), b.strip_prefix("Map of ")) {
        let (ak, av) = partition_to(x);
        let (bk, bv) = partition_to(y);
        return ak == bk && currency_clash(av, bv);
    }
    false
}

/// `clash_error(want, got, line, what)`: E550.
pub fn clash_error(want: &str, got: &str, line: u32, what: &str) -> SablineError {
    let what = if what.is_empty() { "this" } else { what };
    SablineError::with_fixes(
        "E550",
        format!("{what} is {got}, where {want} is needed - amounts in two currencies do not mix"),
        line,
        &[
            "convert on purpose: a rate and a rounding mode are a program's decision, so there \
             is no conversion builtin",
            "or keep both sides in one currency",
        ],
    )
}

/// `_outside_money(t, tv)`: whether `t` mentions `tv` anywhere other than
/// as the currency of an amount.
fn outside_money(t: &str, tv: &str) -> bool {
    if t == tv {
        return true;
    }
    if is_money(t) {
        return false;
    }
    if is_secret(t) {
        return outside_money(secret_inner(t), tv);
    }
    if let Some(inner) = t.strip_prefix("List of ") {
        return outside_money(inner, tv);
    }
    if let Some(rest) = t.strip_prefix("Map of ") {
        let (k, v) = partition_to(rest);
        return outside_money(k, tv) || outside_money(v, tv);
    }
    if let Some((parts, ret)) = fn_sig_parts(t) {
        return parts.iter().any(|p| outside_money(p, tv)) || outside_money(&ret, tv);
    }
    false
}

/// `currency_generic(fn)`: whether every type variable of `f` stands only
/// for the currency of an amount.
pub fn currency_generic(f: &Function) -> bool {
    let mut types: Vec<&str> = f.params.iter().map(|(_, t)| t.as_str()).collect();
    types.push(f.return_type.as_deref().unwrap_or("Unit"));
    !f.type_vars.is_empty()
        && !f.type_vars.iter().any(|tv| types.iter().any(|t| outside_money(t, tv)))
}

/// `wrap_secret(t)`: a result derived from a secret is a secret.
pub fn wrap_secret(t: &str) -> String {
    if t == "Unit" || t.is_empty() || carries_secret(t, None) {
        return t.to_string();
    }
    format!("{SECRET_PREFIX}{t}")
}

/// `strip_secret(t)`: the type underneath, every `Secret` wrapper gone.
pub fn strip_secret(t: &str) -> String {
    if is_secret(t) {
        return strip_secret(secret_inner(t));
    }
    if let Some(inner) = t.strip_prefix("List of ") {
        return format!("List of {}", strip_secret(inner));
    }
    if let Some(rest) = t.strip_prefix("Map of ") {
        let (k, v) = partition_to(rest);
        return format!("Map of {k} to {}", strip_secret(v));
    }
    t.to_string()
}

/// `carries_secret(t, records)`: whether a value of type `t` holds a
/// secret anywhere inside it. `records` says which record types do; with
/// none, a record name answers no.
pub fn carries_secret(t: &str, records: Option<&HashMap<String, bool>>) -> bool {
    if is_secret(t) {
        return true;
    }
    if let Some(inner) = t.strip_prefix("List of ") {
        return carries_secret(inner, records);
    }
    if let Some(rest) = t.strip_prefix("Map of ") {
        return carries_secret(partition_to(rest).1, records);
    }
    if fn_sig_parts(t).is_some() {
        return false;
    }
    match records {
        Some(r) if !r.is_empty() => r.get(t).copied().unwrap_or(false),
        _ => false,
    }
}

/// `records_carrying(records)`: which record types hold a secret, as a
/// fixpoint over the records' fields.
pub fn records_carrying(records: &[crate::nodes::RecordDef]) -> HashMap<String, bool> {
    let mut carry: HashMap<String, bool> =
        records.iter().map(|r| (r.name.clone(), false)).collect();
    let mut changed = true;
    while changed {
        changed = false;
        for r in records {
            if carry.get(&r.name).copied().unwrap_or(false) {
                continue;
            }
            if r.fields.iter().any(|(_, ft)| carries_secret(ft, Some(&carry))) {
                carry.insert(r.name.clone(), true);
                changed = true;
            }
        }
    }
    carry
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fn_sig_parts_reads_what_python_reads() {
        assert_eq!(fn_sig_parts("Int"), None);
        assert_eq!(fn_sig_parts("fn()"), Some((vec![], "Unit".to_string())));
        assert_eq!(
            fn_sig_parts("fn(Int, Text) -> Bool"),
            Some((vec!["Int".to_string(), "Text".to_string()], "Bool".to_string()))
        );
        assert_eq!(
            fn_sig_parts("fn(fn(Int) -> Int, Int) -> fn(Int)"),
            Some((
                vec!["fn(Int) -> Int".to_string(), "Int".to_string()],
                "fn(Int)".to_string()
            ))
        );
        // unbalanced: the loop runs off the end and the result is Unit
        assert_eq!(
            fn_sig_parts("fn(Int"),
            Some((vec!["Int".to_string()], "Unit".to_string()))
        );
    }

    #[test]
    fn secrets_wrap_once_and_strip_everywhere() {
        assert_eq!(wrap_secret("Int"), "Secret of Int");
        assert_eq!(wrap_secret("Secret of Int"), "Secret of Int");
        assert_eq!(wrap_secret("List of Secret of Int"), "List of Secret of Int");
        assert_eq!(wrap_secret("Unit"), "Unit");
        assert_eq!(strip_secret("Map of Text to Secret of Int"), "Map of Text to Int");
        assert!(currency_clash("List of Money of INR", "List of Money of USD"));
        assert!(!currency_clash("Map of Int to Money of INR", "Map of Text to Money of USD"));
    }
}
