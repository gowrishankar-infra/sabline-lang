//! The builtins, the effects, and the other fixed tables every checker
//! reads: `sabline/tables.py`, row for row.
//!
//! Two copies of one table is two tables that will disagree, so the
//! agreement gate holds this one to Python's directly: `sabline-rt tables`
//! writes every table here as one document, and `check_agreement.py`
//! compares it with the same document written from `sabline.tables`. A
//! builtin added to one runtime and not the other is a difference on the
//! commit that adds it, whether or not any program calls it yet.

use crate::json::Json;

/// One row of `BUILTINS`: the effects a call needs, the argument types it
/// is checked against, and the type it gives.
#[derive(Debug, Clone, Copy)]
pub struct Builtin {
    /// The builtin's name.
    pub name: &'static str,
    /// The effects it needs - none, or one.
    pub effects: &'static [&'static str],
    /// The argument types, as the table writes them.
    pub types: &'static [&'static str],
    /// What it gives.
    pub ret: &'static str,
}

const fn b(
    name: &'static str,
    effects: &'static [&'static str],
    types: &'static [&'static str],
    ret: &'static str,
) -> Builtin {
    Builtin { name, effects, types, ret }
}

const NONE: &[&str] = &[];

/// `BUILTINS`, in the order `sabline/tables.py` writes it.
pub const BUILTINS: &[Builtin] = &[
    b("log", &["io"], &["Any"], "Unit"),
    b("print", &["io"], &["Any"], "Unit"),
    b("read_file", &["fs"], &["Text"], "Text"),
    b("write_file", &["fs"], &["Text", "Any"], "Unit"),
    b("fetch", &["net"], &["Text"], "Text"),
    b("now", &["clock"], &[], "Int"),
    b("random", &["rand"], &["Int"], "Int"),
    b("ask", &["io"], &["Text"], "Text"),
    b("to_int", NONE, &["Text"], "Int"),
    b("to_text", NONE, &["Any"], "Text"),
    b("to_float", NONE, &["Int"], "Float"),
    b("round", NONE, &["Float"], "Int"),
    b("contains", NONE, &["Text", "Text"], "Bool"),
    b("split", NONE, &["Text", "Text"], "List of Text"),
    b("upper", NONE, &["Text"], "Text"),
    b("chars", NONE, &["Text"], "List of Text"),
    b("file_exists", &["fs"], &["Text"], "Bool"),
    b("put", NONE, &["Any", "Any", "Any"], "Any"),
    b("get_or", NONE, &["Any", "Any", "Any"], "Any"),
    b("code_at", NONE, &["Text", "Int"], "Int"),
    b("py", &["ffi"], &["Text", "Text", "List of Text"], "Text"),
    b("py_int", &["ffi"], &["Text", "Text", "List of Text"], "Int"),
    b("py_float", &["ffi"], &["Text", "Text", "List of Text"], "Float"),
    b("py_json", &["ffi"], &["Text", "Text", "Text"], "Text"),
    b("py_new", &["ffi"], &["Text", "Text", "Text"], "Handle"),
    b("py_do", &["ffi"], &["Handle", "Text", "Text"], "Text"),
    b("py_field", &["ffi"], &["Handle", "Text"], "Text"),
    b("py_close", &["ffi"], &["Handle"], "Unit"),
    b("json_get", NONE, &["Text", "Text"], "Text"),
    b("json_int", NONE, &["Text", "Text"], "Int"),
    b("json_float", NONE, &["Text", "Text"], "Float"),
    b("json_len", NONE, &["Text", "Text"], "Int"),
    b("json_has", NONE, &["Text", "Text"], "Bool"),
    b("json_of", NONE, &["Any"], "Text"),
    b("args", &["io"], &[], "List of Text"),
    b("env", &["env"], &["Text", "Text"], "Secret of Text"),
    b("exit_with", &["io"], &["Int"], "Unit"),
    b("read_line", &["io"], &[], "Text"),
    b("post", &["net"], &["Text", "Text"], "Text"),
    b("fetch_status", &["net"], &["Text"], "Int"),
    b("request", &["net"], &["Text", "Text", "Text", "Text"], "Text"),
    b("format", NONE, &["Any"], "Text"),
    b("has", NONE, &["Any", "Any"], "Bool"),
    b("keys", NONE, &["Any"], "Any"),
    b("all_of", NONE, &["Any", "Any"], "Bool"),
    b("any_of", NONE, &["Any", "Any"], "Bool"),
    b("lower", NONE, &["Text"], "Text"),
    b("length", NONE, &["Any"], "Int"),
    b("push", NONE, &["Any", "Any"], "Any"),
    b("pop", NONE, &["Any"], "Any"),
    b("slice", NONE, &["Any", "Int", "Int"], "Any"),
    b("set_at", NONE, &["Any", "Int", "Any"], "Any"),
    b("add_or_fail", NONE, &["Int", "Int"], "Int"),
    b("div_or_fail", NONE, &["Int", "Int"], "Int"),
    b("mod_or_fail", NONE, &["Int", "Int"], "Int"),
    b("sub_or_fail", NONE, &["Int", "Int"], "Int"),
    b("mul_or_fail", NONE, &["Int", "Int"], "Int"),
    b("get", NONE, &["Any", "Any"], "Any"),
    b("money", NONE, &["Int", "Text"], "Money of that currency"),
    b("units_of", NONE, &["Money of C, or List of Money of C"], "Int"),
    b("with_units", NONE, &["Money of C", "Int"], "Money of C"),
    b("percent_of", NONE, &["Money of C", "Int", "Int", "Text"], "Money of C"),
    b("divide_or_fail", NONE, &["Money of C", "Int", "Text"], "Money of C"),
    b("text_of", NONE, &["Money of C"], "Text"),
    b("parse_money", NONE, &["Text", "Text"], "Money of that currency"),
    b("read_file_secret", &["fs"], &["Text"], "Secret of Text"),
    b("declassify", &["declassify"], &["Secret of T", "Text"], "T"),
    b("sha256", NONE, &["Text"], "Text"),
    b("hex_encode", NONE, &["Text"], "Text"),
    b("hex_decode", NONE, &["Text"], "Text"),
    b("base64_encode", NONE, &["Text"], "Text"),
    b("base64_decode", NONE, &["Text"], "Text"),
    b("url_encode", NONE, &["Text"], "Text"),
    b("hmac_sha256", &["declassify"], &["Secret of Text", "Text"], "Text"),
    b("hmac_sha256_chain", &["declassify"], &["Secret of Text", "List of Text"], "Text"),
    b("tool", &["tool"], &["Text", "Text"], "Text"),
    b("tool_secret", &["tool"], &["Text", "Text"], "Secret of Text"),
];

/// `FALLIBLE_BUILTINS`: the builtins that can fail (and `get`, on a map,
/// which the type checker decides from its argument).
pub const FALLIBLE_BUILTINS: &[&str] = &[
    "to_int",
    "read_file",
    "read_file_secret",
    "fetch",
    "post",
    "pop",
    "slice",
    "set_at",
    "add_or_fail",
    "sub_or_fail",
    "mul_or_fail",
    "div_or_fail",
    "mod_or_fail",
    "fetch_status",
    "request",
    "py",
    "py_int",
    "py_float",
    "py_json",
    "json_get",
    "json_int",
    "json_float",
    "json_len",
    "py_new",
    "py_do",
    "py_field",
    "divide_or_fail",
    "parse_money",
    "hex_decode",
    "base64_decode",
    "tool",
    "tool_secret",
];

/// `ALL_EFFECTS`, in the order the message that names them lists them.
pub const ALL_EFFECTS: &[&str] =
    &["io", "env", "fs", "net", "clock", "rand", "ffi", "declassify", "tool"];

/// `KNOWN_TYPES`.
pub const KNOWN_TYPES: &[&str] = &["Int", "Text", "Bool", "Float", "Handle"];

/// `CURRENCIES`: ISO 4217 code and digits after the point, sorted by code.
pub const CURRENCIES: &[(&str, u32)] = &[
    ("AED", 2),
    ("AUD", 2),
    ("BHD", 3),
    ("BRL", 2),
    ("CAD", 2),
    ("CHF", 2),
    ("CNY", 2),
    ("EUR", 2),
    ("GBP", 2),
    ("HKD", 2),
    ("INR", 2),
    ("JOD", 3),
    ("JPY", 0),
    ("KRW", 0),
    ("KWD", 3),
    ("MXN", 2),
    ("OMR", 3),
    ("SAR", 2),
    ("SGD", 2),
    ("USD", 2),
    ("ZAR", 2),
];

/// `ROUNDING`.
pub const ROUNDING: &[&str] = &["half_up", "half_even", "down"];

/// `MONEY_BUILTINS`.
pub const MONEY_BUILTINS: &[&str] = &[
    "money",
    "units_of",
    "with_units",
    "percent_of",
    "divide_or_fail",
    "text_of",
    "parse_money",
];

/// `SECRET_BUILTINS`.
pub const SECRET_BUILTINS: &[&str] = &["read_file_secret", "declassify"];

/// `SECRET_SOURCES`, in the table's order.
pub const SECRET_SOURCES: &[&str] = &["env", "read_file_secret", "tool_secret"];

/// `DIGEST_BUILTINS`.
pub const DIGEST_BUILTINS: &[&str] =
    &["sha256", "hex_encode", "hex_decode", "base64_encode", "base64_decode", "url_encode"];

/// `HMAC_BUILTINS`.
pub const HMAC_BUILTINS: &[&str] = &["hmac_sha256", "hmac_sha256_chain"];

/// `TOOL_BUILTINS`.
pub const TOOL_BUILTINS: &[&str] = &["tool", "tool_secret"];

/// The row for `name`, when it is a builtin.
pub fn builtin(name: &str) -> Option<&'static Builtin> {
    BUILTINS.iter().find(|b| b.name == name)
}

/// Whether `name` is in `BUILTINS`.
pub fn is_builtin(name: &str) -> bool {
    builtin(name).is_some()
}

/// Whether `name` is in `FALLIBLE_BUILTINS`.
pub fn is_fallible(name: &str) -> bool {
    FALLIBLE_BUILTINS.contains(&name)
}

/// `NEW_BUILTINS`: the builtins added from 4.3 on, which give way to a
/// function of the program's own with the same name (SPEC.md 10.1).
pub fn is_new_builtin(name: &str) -> bool {
    MONEY_BUILTINS.contains(&name)
        || SECRET_BUILTINS.contains(&name)
        || DIGEST_BUILTINS.contains(&name)
        || HMAC_BUILTINS.contains(&name)
        || TOOL_BUILTINS.contains(&name)
}

/// Whether `code` is a currency in `CURRENCIES`.
pub fn is_currency(code: &str) -> bool {
    CURRENCIES.iter().any(|(c, _)| *c == code)
}

/// `builtin_reached(name, table)`: the builtin a call to `name` reaches,
/// or `None` when it reaches a function of the program's own. A call
/// written `@name` was bound to the builtin when the program was loaded.
pub fn builtin_reached(name: &str, in_table: impl Fn(&str) -> bool) -> Option<&str> {
    if let Some(rest) = name.strip_prefix('@') {
        return Some(rest);
    }
    if is_new_builtin(name) && in_table(name) {
        return None;
    }
    if is_builtin(name) {
        Some(name)
    } else {
        None
    }
}

/// `shown_name(name)`: a call's name as the program wrote it.
pub fn shown_name(name: &str) -> &str {
    name.strip_prefix('@').unwrap_or(name)
}

fn texts(items: &[&str]) -> Json {
    Json::List(items.iter().map(|s| Json::text(*s)).collect())
}

/// Every table here as one document, which `check_agreement.py` compares
/// with the same document written from `sabline/tables.py`.
pub fn document() -> Json {
    let builtins = BUILTINS
        .iter()
        .map(|b| {
            Json::obj([
                ("name", Json::text(b.name)),
                ("effects", texts(b.effects)),
                ("types", texts(b.types)),
                ("ret", Json::text(b.ret)),
            ])
        })
        .collect();
    let mut fallible: Vec<&str> = FALLIBLE_BUILTINS.to_vec();
    fallible.sort_unstable();
    let mut new: Vec<&str> =
        BUILTINS.iter().map(|b| b.name).filter(|n| is_new_builtin(n)).collect();
    new.sort_unstable();
    let mut money: Vec<&str> = MONEY_BUILTINS.to_vec();
    money.sort_unstable();
    let mut hmac: Vec<&str> = HMAC_BUILTINS.to_vec();
    hmac.sort_unstable();
    Json::obj([
        ("tables", Json::Int(1)),
        ("builtins", Json::List(builtins)),
        ("fallible", texts(&fallible)),
        ("effects", texts(ALL_EFFECTS)),
        ("known_types", texts(KNOWN_TYPES)),
        (
            "currencies",
            Json::List(
                CURRENCIES
                    .iter()
                    .map(|(c, d)| Json::List(vec![Json::text(*c), Json::Int(i64::from(*d))]))
                    .collect(),
            ),
        ),
        ("rounding", texts(ROUNDING)),
        ("secret_sources", texts(SECRET_SOURCES)),
        ("new_builtins", texts(&new)),
        ("hmac", texts(&hmac)),
        ("money", texts(&money)),
    ])
}
