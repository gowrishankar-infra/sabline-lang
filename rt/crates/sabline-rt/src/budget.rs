//! The budget: what a run may touch, as `sabline/budget.py` reads it.
//!
//! A transliteration of the Python package's `Budget.parse`, `deny` and
//! `spec`, and of the library's `_budget_from`, which is the path a budget
//! takes from `sabline.run(allow=..., deny=...)` and from a conformance
//! case. The grammar is sabline-spec's sections 4 and 5: effects, scoped
//! `fs:` / `net:` / `ffi:` / `tool:` grants, `@N` counts, and the refusals.
//! Every refusal's text is the reference's, character for character,
//! because the agreement gate compares it.
//!
//! What a run does with a budget - the guarded opener, counting, the
//! refusals while running - is M3's, and is not here.
//!
//! Three places where CPython is copied rather than Rust's idiom:
//!
//! - **A count is any size.** `int()` has no upper bound, so `fs@` with
//!   thirty digits is a count of that many operations, and is written back
//!   with those digits. [`Count`] holds the digits.
//! - **A path is `normcase(realpath(path))`** when the budget is parsed -
//!   sabline-spec 5.1's resolution R, against the working directory -
//!   through [`crate::pypath::realpath`], which copies CPython's walk.
//! - **`str.strip()`, `str.lower()` and `str.isdigit()`** are CPython's:
//!   [`crate::pyrepr::py_strip`], Rust's `to_lowercase` (the same full
//!   mapping, final sigma included), and [`crate::unicode_digit`].

use std::cmp::Ordering;
use std::collections::{BTreeMap, BTreeSet};

use crate::json::Json;
use crate::pypath;
use crate::pyrepr::py_strip;
use crate::tables::ALL_EFFECTS;
use crate::unicode_digit::py_isdigit;

/// `ALLOW_ALL`: the command line's word for every effect. Not a grant.
pub const ALLOW_ALL: &str = "all";
/// `DEFAULT_ALLOW`: what a run gets when nobody writes a budget (5.0).
pub const DEFAULT_ALLOW: &str = "io";

/// `BudgetError`, or the library's `ValueError`: a budget that does not
/// parse, and why.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct BudgetError(pub String);

type Parsed<T> = Result<T, BudgetError>;

fn refuse<T>(message: String) -> Parsed<T> {
    Err(BudgetError(message))
}

/// CPython's default `sys.get_int_max_str_digits()`.
const INT_MAX_STR_DIGITS: usize = 4300;

/// A whole number of operations, as CPython's `int()` holds it: its
/// decimal digits, with no leading zero.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Count(String);

impl Count {
    /// `int(digits)` for a run of ASCII digits - which CPython refuses
    /// past 4,300 of them (`sys.get_int_max_str_digits()`, from 3.10.7),
    /// leading zeros counted. The message is 3.12's and later's; 3.10
    /// writes "(4300)" where they write "(4300 digits)", and the reference
    /// gives 3.12's on every CPython (`values.whole_number`, 9.0 M3).
    fn of(digits: &str) -> Parsed<Count> {
        if digits.len() > INT_MAX_STR_DIGITS {
            return refuse(format!(
                "Exceeds the limit ({INT_MAX_STR_DIGITS} digits) for integer string conversion: \
                 value has {} digits; use sys.set_int_max_str_digits() to increase the limit",
                digits.len()
            ));
        }
        let kept = digits.trim_start_matches('0');
        Ok(Count(if kept.is_empty() { "0".to_string() } else { kept.to_string() }))
    }

    /// The number, as `str(n)` writes it.
    pub fn digits(&self) -> &str {
        &self.0
    }

    /// `n if cur is None else min(cur, n)`.
    fn least(current: Option<&Count>, n: Count) -> Count {
        match current {
            Some(cur) if cur <= &n => cur.clone(),
            _ => n,
        }
    }

    fn json(&self) -> Json {
        Json::Num(self.0.clone())
    }
}

impl Ord for Count {
    fn cmp(&self, other: &Self) -> Ordering {
        self.0.len().cmp(&other.0.len()).then_with(|| self.0.cmp(&other.0))
    }
}

impl PartialOrd for Count {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl std::fmt::Display for Count {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

/// `_ascii_digits(s)`: a non-empty run of 0-9, and nothing else.
fn ascii_digits(s: &str) -> bool {
    !s.is_empty() && s.bytes().all(|b| b.is_ascii_digit())
}

/// `_pct_encode(s)`: the five structural characters percent-encoded, `%`
/// first.
pub fn pct_encode(s: &str) -> String {
    s.replace('%', "%25")
        .replace(',', "%2C")
        .replace('@', "%40")
        .replace('[', "%5B")
        .replace(']', "%5D")
}

/// `_pct_decode(s)`: exactly the five sequences decoded, in one pass, and
/// every other `%` literal. CPython compares `s[i:i + 3].upper()` with
/// the five; no character past ASCII upper-cases to one of the characters
/// they are made of, so only ASCII is upper-cased here.
pub fn pct_decode(s: &str) -> String {
    let chars: Vec<char> = s.chars().collect();
    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        if chars[i] == '%' && i + 3 <= chars.len() {
            let code: String =
                chars[i + 1..i + 3].iter().map(|c| c.to_ascii_uppercase()).collect();
            let decoded = match code.as_str() {
                "2C" => Some(','),
                "40" => Some('@'),
                "5B" => Some('['),
                "5D" => Some(']'),
                "25" => Some('%'),
                _ => None,
            };
            if let Some(c) = decoded {
                out.push(c);
                i += 3;
                continue;
            }
        }
        out.push(chars[i]);
        i += 1;
    }
    out
}

/// `_net_grant_text(host, port)`: one `net:` grant as canonical text.
fn net_grant_text(host: &str, port: Option<u32>) -> String {
    let h = if host.contains(':') { format!("[{host}]") } else { pct_encode(host) };
    match port {
        Some(p) => format!("net:{h}:{p}"),
        None => format!("net:{h}"),
    }
}

/// `_tool_word(text)`: a tool's or an argument's name - ASCII letters,
/// digits, `_`, `.` and `-`, starting with a letter or `_`.
fn tool_word(text: &str) -> bool {
    let mut chars = text.chars();
    match chars.next() {
        Some(first) if text.is_ascii() && (first.is_ascii_alphabetic() || first == '_') => {
            text.chars().all(|c| c.is_ascii_alphanumeric() || "_.-".contains(c))
        }
        _ => false,
    }
}

/// `_tool_pattern_text(pattern)`: a pattern as a budget writes it.
fn tool_pattern_text(pattern: &str) -> String {
    let mut out = pattern.replace('%', "%25").replace(',', "%2C");
    if let Some(at) = out.rfind('@') {
        if ascii_digits(&out[at + 1..]) {
            out = format!("{}%40{}", &out[..at], &out[at + 1..]);
        }
    }
    out
}

/// `parse_host_port(text)`: `(host, port)`, the host lower-cased with no
/// trailing dot.
pub fn parse_host_port(text: &str) -> Parsed<(String, Option<u32>)> {
    let text = py_strip(text);
    if text.is_empty() {
        return refuse("net: needs a host".to_string());
    }
    let mut port: Option<Count> = None;
    let host;
    if let Some(after) = text.strip_prefix('[') {
        let Some(end) = after.find(']') else {
            return refuse(format!("'{text}': unclosed [ in an IPv6 literal"));
        };
        host = pct_decode(&after[..end]);
        if host.is_empty() {
            return refuse(format!("'{text}': the brackets hold no address"));
        }
        let rest = &after[end + 1..];
        if !rest.is_empty() {
            match rest.strip_prefix(':') {
                Some(digits) if ascii_digits(digits) => port = Some(Count::of(digits)?),
                _ => return refuse(format!("'{text}': expected :port after ]")),
            }
        }
    } else {
        let mut raw = text;
        if let Some(colon) = text.rfind(':') {
            let tail = &text[colon + 1..];
            if ascii_digits(tail) {
                port = Some(Count::of(tail)?);
                raw = &text[..colon];
            }
        }
        if raw.contains('/') || raw.contains('@') || raw.is_empty() {
            return refuse(format!(
                "'{text}': a host is a name or address, with an optional :port"
            ));
        }
        if raw.contains(':') {
            return refuse(format!(
                "'{text}': an IPv6 address must be written in brackets, as net:[{raw}] or \
                 net:[{raw}]:port"
            ));
        }
        host = pct_decode(raw);
    }
    let port = match port {
        None => None,
        Some(n) => {
            let ok = n.digits().len() <= 5 && n.digits() != "0";
            let value: u32 = if ok { n.digits().parse().unwrap_or(0) } else { 0 };
            if !ok || value >= 65536 {
                return refuse(format!("'{text}': port out of range"));
            }
            Some(value)
        }
    };
    Ok((host.to_lowercase().trim_end_matches('.').to_string(), port))
}

/// The tools a budget grants: by name, any arguments (`None`) or the
/// argument patterns that hold it, in the order they were written.
pub type Tools = BTreeMap<String, Option<Vec<(String, String)>>>;

/// What a run may touch: `sabline/budget.py`'s `Budget`.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub struct Budget {
    /// Every effect granted.
    pub effects: BTreeSet<String>,
    /// `ffi`'s modules; `None` is every module.
    pub modules: Option<BTreeSet<String>>,
    /// `fs`'s grants, `(direction, resolved path or None)`; `None` is any.
    pub fs: Option<Vec<(String, Option<String>)>>,
    /// `net`'s grants, `(host pattern, port or None)`; `None` is any.
    pub net: Option<Vec<(String, Option<u32>)>>,
    /// The fs count, `@N`, the smallest written.
    pub fs_limit: Option<Count>,
    /// The net count.
    pub net_limit: Option<Count>,
    fs_any: bool,
    net_any: bool,
    ffi_any: bool,
    /// The tools (8.5); `None` is any tool, with any arguments.
    pub tools: Option<Tools>,
    /// `@N` by tool, and `""` for the run.
    pub tool_limits: BTreeMap<String, Count>,
    tool_plain: BTreeSet<String>,
    tool_any: bool,
}

impl Budget {
    fn new() -> Budget {
        Budget { tools: Some(BTreeMap::new()), ..Budget::default() }
    }

    /// `Budget.parse(spec)`.
    pub fn parse(spec: &str) -> Parsed<Budget> {
        let mut b = Budget::new();
        let items: Vec<String> = spec.split(',').map(|s| py_strip(s).to_string()).collect();
        let mut i = 0;
        while i < items.len() {
            let item = &items[i];
            i += 1;
            if item.is_empty() || item == "''" || item == "\"\"" {
                continue;
            }
            if let Some(after) = item.strip_prefix("ffi:") {
                b.effects.insert("ffi".to_string());
                let mut raw = vec![py_strip(after).to_string()];
                while i < items.len()
                    && !items[i].is_empty()
                    && !items[i].contains(':')
                    && !items[i].contains('@')
                    && !ALL_EFFECTS.contains(&items[i].as_str())
                {
                    raw.push(items[i].clone());
                    i += 1;
                }
                let mut mods = Vec::new();
                for r in &raw {
                    if r.contains('@') {
                        return refuse(format!(
                            "'{r}': ffi takes no count; a module is a name, as ffi:math"
                        ));
                    }
                    let m = r.split('.').next().unwrap_or("");
                    if m.is_empty() {
                        return refuse(format!(
                            "'{item}': ffi: needs a module name, as ffi:math"
                        ));
                    }
                    mods.push(m.to_string());
                }
                if !b.ffi_any {
                    b.modules.get_or_insert_with(BTreeSet::new).extend(mods);
                }
            } else if item == "fs" || item.starts_with("fs:") || item.starts_with("fs@") {
                b.add_fs(item)?;
            } else if item == "net" || item.starts_with("net:") || item.starts_with("net@") {
                b.add_net(item)?;
            } else if item == "tool" || item.starts_with("tool:") || item.starts_with("tool@")
            {
                b.add_tool(item)?;
            } else if item == "ffi" {
                b.effects.insert("ffi".to_string());
                b.ffi_any = true;
                b.modules = None;
            } else if ALL_EFFECTS.contains(&item.as_str()) {
                b.effects.insert(item.clone());
            } else if item == ALLOW_ALL {
                return refuse(format!(
                    "'{ALLOW_ALL}' is not an effect. On a command line write it on its own - \
                     --allow {ALLOW_ALL} - which grants {}; in a budget alongside other \
                     grants, name the effects you want",
                    ALL_EFFECTS.join(", ")
                ));
            } else {
                return refuse(format!(
                    "'{item}' is not an effect. They are: {} (or ffi:module, fs:read:path, \
                     net:host:port, with @count)",
                    ALL_EFFECTS.join(", ")
                ));
            }
        }
        let plain: Vec<String> = b.tool_plain.iter().cloned().collect();
        for name in plain {
            if let Some(tools) = b.tools.as_mut() {
                tools.insert(name, None);
            }
        }
        let no_tools = b.tools.as_ref().is_none_or(BTreeMap::is_empty);
        if b.tool_any || (b.effects.contains("tool") && no_tools) {
            b.tools = None;
        }
        Ok(b)
    }

    /// `_split_count(item)`: `fs:read:./x@50` as `("fs:read:./x", 50)`.
    fn split_count(item: &str) -> Parsed<(&str, Option<Count>)> {
        if let Some(at) = item.rfind('@').filter(|&at| at > 0) {
            let digits = &item[at + 1..];
            if ascii_digits(digits) {
                let body = &item[..at];
                if body.contains('@') {
                    return refuse(format!(
                        "'{item}': a grant takes at most one @count; write an @ inside a path \
                         as %40"
                    ));
                }
                return Ok((body, Some(Count::of(digits)?)));
            }
            return refuse(format!(
                "'{item}': what follows @ must be a whole number of operations, written 0-9"
            ));
        }
        Ok((item, None))
    }

    fn add_fs(&mut self, item: &str) -> Parsed<()> {
        let (body, n) = Budget::split_count(item)?;
        self.effects.insert("fs".to_string());
        if let Some(n) = n {
            self.fs_limit = Some(Count::least(self.fs_limit.as_ref(), n));
        }
        if body == "fs" {
            self.fs = None;
            self.fs_any = true;
            return Ok(());
        }
        let rest = &body[3..];
        let (kind, path) = match rest.split_once(':') {
            Some((k, p)) => (k, Some(p)),
            None => (rest, None),
        };
        if kind != "read" && kind != "write" {
            return refuse(format!(
                "'{item}': after fs: write read or write, then optionally :path"
            ));
        }
        let mut prefix = None;
        if let Some(path) = path {
            if path.is_empty() {
                return refuse(format!("'{item}': the path after fs:{kind}: is empty"));
            }
            // a `,` or `@` in the path arrives percent-encoded; decoded
            // before resolving, so the path names the file it means
            prefix = Some(pypath::os_path::normcase(&pypath::realpath(&pct_decode(path))));
        }
        if self.fs_any {
            return Ok(());
        }
        self.fs.get_or_insert_with(Vec::new).push((kind.to_string(), prefix));
        Ok(())
    }

    fn add_net(&mut self, item: &str) -> Parsed<()> {
        let (body, n) = Budget::split_count(item)?;
        self.effects.insert("net".to_string());
        if let Some(n) = n {
            self.net_limit = Some(Count::least(self.net_limit.as_ref(), n));
        }
        if body == "net" {
            self.net_any = true;
            self.net = None;
            return Ok(());
        }
        let (host, port) = parse_host_port(&body[4..])?;
        if let Some(tail) = host.strip_prefix("*.") {
            if tail.is_empty() || tail.contains('*') || !tail.contains('.') {
                return refuse(format!(
                    "'{item}': the wildcard must be '*.' followed by at least two labels"
                ));
            }
            let digits = |label: &str| !label.is_empty() && label.chars().all(py_isdigit);
            if tail.split('.').all(digits) {
                return refuse(format!("'{item}': no wildcard over an IP literal"));
            }
        } else if host.contains('*') {
            return refuse(format!("'{item}': only one leading '*.' label is allowed"));
        }
        if self.net_any {
            return Ok(());
        }
        self.net.get_or_insert_with(Vec::new).push((host, port));
        Ok(())
    }

    fn add_tool(&mut self, item: &str) -> Parsed<()> {
        self.effects.insert("tool".to_string());
        let mut body = item;
        let mut n = None;
        match item.rfind('@').filter(|&at| at > 0) {
            Some(at) if ascii_digits(&item[at + 1..]) => {
                body = &item[..at];
                n = Some(Count::of(&item[at + 1..])?);
            }
            _ if item.starts_with("tool@") => {
                return refuse(format!(
                    "'{item}': what follows @ must be a whole number of calls, written 0-9"
                ));
            }
            _ => {}
        }
        if body == "tool" {
            match n {
                None => self.tool_any = true,
                Some(n) => {
                    let least = Count::least(self.tool_limits.get(""), n);
                    self.tool_limits.insert(String::new(), least);
                }
            }
            return Ok(());
        }
        let after = &body[5..];
        let (name, rest) = match after.split_once(':') {
            Some((name, rest)) => (name, Some(rest)),
            None => (after, None),
        };
        if !tool_word(name) {
            return refuse(format!(
                "'{item}': after tool: write a tool's name (letters, digits, _ . -), as \
                 tool:search"
            ));
        }
        if let Some(n) = n {
            if rest.is_some() {
                return refuse(format!(
                    "'{item}': a count goes on the tool, as tool:{name}@{n}, not on one \
                     argument; a pattern that ends in @ and digits writes that @ as %40"
                ));
            }
            let least = Count::least(self.tool_limits.get(name), n);
            self.tool_limits.insert(name.to_string(), least);
            if let Some(tools) = self.tools.as_mut() {
                tools.entry(name.to_string()).or_insert(None);
            }
            return Ok(());
        }
        let Some(rest) = rest else {
            self.tool_plain.insert(name.to_string());
            if let Some(tools) = self.tools.as_mut() {
                tools.insert(name.to_string(), None);
            }
            return Ok(());
        };
        let (arg, pattern) = match rest.split_once('=') {
            Some((a, p)) => (a, Some(p)),
            None => (rest, None),
        };
        let Some(pattern) = pattern.filter(|p| tool_word(arg) && !p.is_empty()) else {
            return refuse(format!(
                "'{item}': after tool:{name}: write argument=pattern, as \
                 tool:{name}:to=*@corp.com"
            ));
        };
        let pattern = pct_decode(pattern);
        if pattern.contains("**") {
            return refuse(format!(
                "'{item}': a pattern holds single stars; each stands for one run of characters"
            ));
        }
        let Some(tools) = self.tools.as_mut() else {
            return Ok(());
        };
        let mut held = tools.get(name).cloned().flatten().unwrap_or_default();
        let pair = (arg.to_string(), pattern);
        if !held.contains(&pair) {
            held.push(pair);
        }
        tools.insert(name.to_string(), Some(held));
        Ok(())
    }

    /// `_tool_items()`: the tool grants as canonical text.
    fn tool_items(&self) -> Vec<String> {
        let mut out = Vec::new();
        let total = self.tool_limits.get("");
        match (&self.tools, total) {
            (None, None) => out.push("tool".to_string()),
            (None, Some(t)) | (Some(_), Some(t)) => out.push(format!("tool@{t}")),
            (Some(_), None) => {}
        }
        let empty = BTreeMap::new();
        for (name, held) in self.tools.as_ref().unwrap_or(&empty) {
            let limit = self.tool_limits.get(name);
            if held.is_none() && limit.is_none() {
                out.push(format!("tool:{name}"));
            }
            let mut sorted = held.clone().unwrap_or_default();
            sorted.sort();
            for (arg, pattern) in sorted {
                out.push(format!("tool:{name}:{arg}={}", tool_pattern_text(&pattern)));
            }
            if let Some(limit) = limit {
                out.push(format!("tool:{name}@{limit}"));
            }
        }
        if self.tools.is_none() {
            for (name, limit) in &self.tool_limits {
                if !name.is_empty() {
                    out.push(format!("tool:{name}@{limit}"));
                }
            }
        }
        out
    }

    /// `spec()`: the budget as the command line would write it, absolute
    /// paths included.
    pub fn spec(&self) -> String {
        let mut out = Vec::new();
        for e in &self.effects {
            match e.as_str() {
                "ffi" => out.push(match &self.modules {
                    None => "ffi".to_string(),
                    Some(m) => {
                        m.iter().map(|m| format!("ffi:{m}")).collect::<Vec<_>>().join(",")
                    }
                }),
                "fs" => {
                    let tail =
                        self.fs_limit.as_ref().map(|n| format!("@{n}")).unwrap_or_default();
                    match &self.fs {
                        None => out.push(format!("fs{tail}")),
                        Some(grants) => {
                            for (kind, prefix) in grants {
                                let p = match prefix {
                                    Some(p) if !p.is_empty() => format!(":{}", pct_encode(p)),
                                    _ => String::new(),
                                };
                                out.push(format!("fs:{kind}{p}{tail}"));
                            }
                        }
                    }
                }
                "net" => {
                    let tail =
                        self.net_limit.as_ref().map(|n| format!("@{n}")).unwrap_or_default();
                    match &self.net {
                        None => out.push(format!("net{tail}")),
                        Some(grants) => {
                            for (host, port) in grants {
                                out.push(format!("{}{tail}", net_grant_text(host, *port)));
                            }
                        }
                    }
                }
                "tool" => out.extend(self.tool_items()),
                _ => out.push(e.clone()),
            }
        }
        out.join(",")
    }

    /// `deny(names)`: each effect named taken away, with its scopes.
    pub fn deny<'a>(&mut self, names: impl IntoIterator<Item = &'a str>) {
        for name in names {
            self.effects.remove(name);
            match name {
                "fs" => {
                    self.fs = None;
                    self.fs_limit = None;
                }
                "net" => {
                    self.net = None;
                    self.net_limit = None;
                }
                "ffi" => self.modules = None,
                "tool" => {
                    self.tools = Some(BTreeMap::new());
                    self.tool_limits.clear();
                    self.tool_plain.clear();
                    self.tool_any = false;
                }
                _ => {}
            }
        }
    }
}

/// `expand_allow(spec)`: `all`, on its own, as every effect.
pub fn expand_allow(spec: &str) -> String {
    if py_strip(spec) == ALLOW_ALL {
        ALL_EFFECTS.join(",")
    } else {
        spec.to_string()
    }
}

/// `_budget_from({allow}, {deny...})`, as `sabline/conform.py`'s budget
/// case calls it: `allow` is one budget's text or nothing (the default,
/// `io`), and `deny` is a comma-separated list of effects or nothing.
pub fn budget_from(allow: Option<&str>, deny: Option<&str>) -> Parsed<Budget> {
    let asked = match allow {
        None => DEFAULT_ALLOW.to_string(),
        Some(text) => expand_allow(text),
    };
    let mut budget = Budget::parse(&asked)?;
    let names: BTreeSet<String> = match deny {
        None => BTreeSet::new(),
        Some(text) => text.split(',').map(|n| py_strip(n).to_string()).collect(),
    };
    let unknown: Vec<&str> =
        names.iter().map(String::as_str).filter(|n| !ALL_EFFECTS.contains(n)).collect();
    if !unknown.is_empty() {
        return refuse(format!(
            "not an effect: {}; they are {}",
            unknown.join(", "),
            ALL_EFFECTS.join(", ")
        ));
    }
    budget.deny(names.iter().map(String::as_str));
    Ok(budget)
}

/// `_conf_budget_shape(b)`: what a conformance case compares - the
/// effects, and each scoped effect's grants and count.
pub fn shape(b: &Budget) -> Json {
    let texts = |items: &mut dyn Iterator<Item = &String>| -> Json {
        Json::List(items.map(|s| Json::text(s.clone())).collect())
    };
    let mut out = BTreeMap::new();
    out.insert("effects".to_string(), texts(&mut b.effects.iter()));
    if b.effects.contains("ffi") {
        let v = match &b.modules {
            None => Json::text("any"),
            Some(m) => texts(&mut m.iter()),
        };
        out.insert("ffi".to_string(), v);
    }
    if b.effects.contains("fs") {
        let v = match &b.fs {
            None => Json::text("any"),
            Some(grants) => Json::List(
                grants
                    .iter()
                    .map(|(d, p)| {
                        Json::obj([
                            ("direction", Json::text(d.clone())),
                            ("path", p.clone().map_or(Json::Null, Json::Str)),
                        ])
                    })
                    .collect(),
            ),
        };
        out.insert("fs".to_string(), v);
    }
    if b.effects.contains("net") {
        let v = match &b.net {
            None => Json::text("any"),
            Some(grants) => Json::List(
                grants
                    .iter()
                    .map(|(h, p)| {
                        Json::obj([
                            ("host", Json::text(h.clone())),
                            ("port", p.map_or(Json::Null, |p| Json::Int(i64::from(p)))),
                        ])
                    })
                    .collect(),
            ),
        };
        out.insert("net".to_string(), v);
    }
    let mut counts = BTreeMap::new();
    for (effect, limit) in [("fs", &b.fs_limit), ("net", &b.net_limit)] {
        if let Some(n) = limit {
            if b.effects.contains(effect) {
                counts.insert(effect.to_string(), n.json());
            }
        }
    }
    out.insert("counts".to_string(), Json::Obj(counts));
    Json::Obj(out)
}

/// The budget document the agreement gate compares, for one budget case:
/// the shape a conformance case reads, the tools, and `spec()` - or the
/// refusal's text.
pub fn budget_document(allow: Option<&str>, deny: Option<&str>) -> Json {
    match budget_from(allow, deny) {
        Err(BudgetError(message)) => {
            Json::obj([("valid", Json::Bool(false)), ("refused", Json::text(message))])
        }
        Ok(b) => {
            let tools = match &b.tools {
                None => Json::Null,
                Some(t) => Json::Obj(
                    t.iter()
                        .map(|(name, held)| {
                            let v = match held {
                                None => Json::Null,
                                Some(pairs) => Json::List(
                                    pairs
                                        .iter()
                                        .map(|(a, p)| {
                                            Json::List(vec![
                                                Json::text(a.clone()),
                                                Json::text(p.clone()),
                                            ])
                                        })
                                        .collect(),
                                ),
                            };
                            (name.clone(), v)
                        })
                        .collect(),
                ),
            };
            let limits =
                b.tool_limits.iter().map(|(name, n)| (name.clone(), n.json())).collect();
            Json::obj([
                ("valid", Json::Bool(true)),
                ("shape", shape(&b)),
                ("spec", Json::text(b.spec())),
                ("tools", tools),
                ("tool_limits", Json::Obj(limits)),
            ])
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn refused(allow: &str) -> String {
        match budget_from(Some(allow), None) {
            Err(BudgetError(m)) => m,
            Ok(b) => panic!("{allow:?} parsed, to {}", b.spec()),
        }
    }

    #[test]
    fn grants_parse_to_what_python_parses() {
        // every expected text was read from the Python package's spec()
        let b =
            budget_from(Some("io, net:API.Example.com.:0443@07,tool:search@3"), None).unwrap();
        assert_eq!(b.spec(), "io,net:api.example.com:443@7,tool:search@3");
        let b =
            budget_from(Some("io, net:API.Example.com.:0443@07,net@5,tool:search@3"), None)
                .unwrap();
        assert_eq!(b.spec(), "io,net@5,tool:search@3");
        let b = budget_from(Some("ffi:math.sqrt,json,io"), Some("io")).unwrap();
        assert_eq!(b.spec(), "ffi:json,ffi:math");
        let b = budget_from(Some("tool:send:to=*%40corp.com,tool:send:to=a%2Cb,tool@9"), None)
            .unwrap();
        assert_eq!(b.spec(), "tool@9,tool:send:to=*@corp.com,tool:send:to=a%2Cb");
        let b = budget_from(Some("fs@99999999999999999999999,fs:read@0100"), None).unwrap();
        assert_eq!(b.spec(), "fs@100");
        let long = format!("fs@{}", "0".repeat(4301));
        assert_eq!(
            budget_from(Some(&long), None).unwrap_err().0,
            "Exceeds the limit (4300 digits) for integer string conversion: value has 4301 \
             digits; use sys.set_int_max_str_digits() to increase the limit"
        );
        let b = budget_from(Some("net:[::1]:8443,net:*.example.com"), None).unwrap();
        assert_eq!(b.spec(), "net:[::1]:8443,net:*.example.com");
        assert_eq!(budget_from(None, None).unwrap().spec(), "io");
        assert_eq!(budget_from(Some(" all "), None).unwrap().effects.len(), ALL_EFFECTS.len());
    }

    #[test]
    fn refusals_say_what_python_says() {
        assert_eq!(
            refused("fs:read:x@-2"),
            "'fs:read:x@-2': what follows @ must be a whole number of operations, written 0-9"
        );
        assert_eq!(
            refused("net:*.1.\u{b2}"),
            "'net:*.1.\u{b2}': no wildcard over an IP literal"
        );
        assert_eq!(
            refused("net:::1"),
            "'::1': an IPv6 address must be written in brackets, as net:[:] or net:[:]:port"
        );
        assert_eq!(refused("net:x:65536"), "'x:65536': port out of range");
        assert_eq!(refused("ffi:"), "'ffi:': ffi: needs a module name, as ffi:math");
        assert_eq!(refused("io,all"), "'all' is not an effect. On a command line write it on its own - --allow all - which grants io, env, fs, net, clock, rand, ffi, declassify, tool; in a budget alongside other grants, name the effects you want");
        assert_eq!(refused("tool:t:a=x**"), "'tool:t:a=x**': a pattern holds single stars; each stands for one run of characters");
        assert_eq!(
            budget_from(Some("io"), Some("io,nope,  fs")).unwrap_err().0,
            "not an effect: nope; they are io, env, fs, net, clock, rand, ffi, declassify, tool"
        );
    }

    #[test]
    fn percent_decoding_is_one_pass() {
        assert_eq!(pct_decode("a%2cb%252C%40%5b%5D%zz%"), "a,b%2C@[]%zz%");
        assert_eq!(pct_encode("100%,@[]"), "100%25%2C%40%5B%5D");
    }
}
