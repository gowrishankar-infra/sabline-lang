//! The values a running program holds: what each Python object the
//! reference runtime holds a value in is, and how CPython compares,
//! hashes and prints it.
//!
//! `sabline/runtime.py` has no value type of its own for most of what a
//! program holds: a whole number is a Python `int`, a list a Python
//! `list`, a map a `dict`, a yes/no a `bool`. What a program sees of them -
//! `==`, `<`, a map's order, `to_text`, the text of a broken promise - is
//! therefore CPython's behaviour for those types, and that is what is
//! written here: a [`Value`] per Python type a run can hold, and the
//! operations CPython gives each, down to `True` in a message where
//! `to_text` writes `true`.

use std::cell::{Cell, RefCell};
use std::cmp::Ordering;
use std::collections::HashMap;
use std::rc::Rc;

use crate::bigint::BigInt;
use crate::nodes::Function;
use crate::pyrepr::py_float_repr;
use crate::tables::CURRENCIES;
use crate::text::{Text, TextBuf};

/// One value.
#[derive(Clone, Debug)]
pub enum Value {
    /// Python's `None`: what a function that returns nothing gives.
    None,
    /// `bool`.
    Bool(bool),
    /// An `int` that fits in 64 bits, which is nearly every one.
    Int(i64),
    /// An `int` that does not: a literal past 64 bits, or what `%` made
    /// of one. Never a value that fits in an `i64`.
    Big(Rc<BigInt>),
    /// `float`.
    Float(f64),
    /// `str`.
    Text(Text),
    /// `list`. Never changed in place: `push` and `set_at` make a new one.
    List(Rc<Vec<Value>>),
    /// `dict`.
    Map(Rc<Dict>),
    /// `RecordValue`.
    Record(Rc<Record>),
    /// `MoneyValue`.
    Money(Money),
    /// A function as a value, written or lifted: the node itself.
    Func(Rc<Function>),
    /// `Bound`: a lifted function value and the values it carries.
    Bound(Rc<Bound>),
}

/// An amount: minor units and a currency.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub struct Money {
    /// Minor units.
    pub units: i64,
    /// The ISO 4217 code.
    pub currency: Rc<str>,
}

/// A record value. Its fields are in the order the literal wrote them,
/// which is the order `to_text` prints them in.
#[derive(Clone, Debug)]
pub struct Record {
    /// The record's name.
    pub name: String,
    /// Each field and its value.
    pub fields: Vec<(String, Value)>,
}

/// A lifted function value carrying what it was made with.
#[derive(Debug)]
pub struct Bound {
    /// The lifted function.
    pub func: Rc<Function>,
    /// The values carried in, in the order the function value names them.
    pub caught: Vec<(String, Value)>,
}

/// Why CPython refused an operation on the values given: the
/// `TypeError` or `OverflowError` the reference would raise. The type
/// checker keeps a program away from all of them; one reaching a run is a
/// defect, and is reported as what Python raised.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Raised(pub &'static str);

/// A `dict`: insertion order, and CPython's idea of when two keys are
/// one key - `1`, `1.0` and `True` are.
#[derive(Clone, Debug, Default)]
pub struct Dict {
    entries: Vec<(Value, Value)>,
    index: HashMap<Key, usize>,
}

/// What a key hashes and compares as.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
enum Key {
    None,
    Int(i64),
    Big(BigInt),
    Float(u64),
    Text(Text),
    Money(i64, Rc<str>),
    Nan(usize),
}

fn key_of(v: &Value, nan_id: usize) -> Result<Key, Raised> {
    Ok(match v {
        Value::None => Key::None,
        Value::Bool(b) => Key::Int(i64::from(*b)),
        Value::Int(n) => Key::Int(*n),
        Value::Big(b) => Key::Big((**b).clone()),
        Value::Float(x) => {
            if x.is_nan() {
                // a NaN is found again only by being the same object
                Key::Nan(if x.to_bits() & NAN_PAYLOAD != 0 {
                    x.to_bits() as usize
                } else {
                    nan_id
                })
            } else if x.fract() == 0.0 && x.is_finite() {
                match BigInt::from_f64_integral(*x).and_then(|b| b.to_i64()) {
                    Some(n) => Key::Int(n),
                    None => Key::Big(BigInt::from_f64_integral(*x).unwrap_or_default()),
                }
            } else {
                Key::Float(x.to_bits())
            }
        }
        Value::Text(t) => Key::Text(t.clone()),
        Value::Money(m) => Key::Money(m.units, m.currency.clone()),
        _ => return Err(Raised("TypeError")),
    })
}

impl Dict {
    /// An empty one.
    pub fn new() -> Self {
        Self::default()
    }

    /// How many entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether it has none.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// The entries, in order.
    pub fn entries(&self) -> &[(Value, Value)] {
        &self.entries
    }

    /// `d[k] = v`: a key already there keeps its place, and the key
    /// object first given for it.
    pub fn set(&mut self, k: Value, v: Value) -> Result<(), Raised> {
        let key = key_of(&k, self.entries.len())?;
        if let Some(&i) = self.index.get(&key) {
            self.entries[i].1 = v;
        } else {
            self.index.insert(key, self.entries.len());
            self.entries.push((k, v));
        }
        Ok(())
    }

    /// `d.get(k)`.
    pub fn get(&self, k: &Value) -> Result<Option<&Value>, Raised> {
        let key = key_of(k, usize::MAX)?;
        Ok(self.index.get(&key).map(|&i| &self.entries[i].1))
    }

    /// `k in d`.
    pub fn has(&self, k: &Value) -> Result<bool, Raised> {
        Ok(self.get(k)?.is_some())
    }
}

impl Value {
    /// A Text from a Rust string.
    pub fn text(s: &str) -> Value {
        Value::Text(Text::from(s))
    }

    /// A whole number of any size, as the smallest variant that holds it.
    pub fn int(n: BigInt) -> Value {
        match n.to_i64() {
            Some(small) => Value::Int(small),
            None => Value::Big(Rc::new(n)),
        }
    }

    /// A whole number from an `i128`.
    pub fn int128(n: i128) -> Value {
        match i64::try_from(n) {
            Ok(small) => Value::Int(small),
            Err(_) => Value::Big(Rc::new(BigInt::from_i128(n))),
        }
    }

    /// A list.
    pub fn list(items: Vec<Value>) -> Value {
        Value::List(Rc::new(items))
    }

    /// Whether this is an `int` (a `bool` is one, as in Python).
    pub fn is_int(&self) -> bool {
        matches!(self, Value::Int(_) | Value::Big(_) | Value::Bool(_))
    }

    /// The `int` as an `i128`, a `bool` as 0 or 1, when it fits.
    pub fn as_i128(&self) -> Option<i128> {
        match self {
            Value::Bool(b) => Some(i128::from(*b)),
            Value::Int(n) => Some(i128::from(*n)),
            Value::Big(b) => b.to_i128(),
            _ => None,
        }
    }

    /// The `int` as a [`BigInt`].
    pub fn as_big(&self) -> Option<BigInt> {
        match self {
            Value::Bool(b) => Some(BigInt::from_i128(i128::from(*b))),
            Value::Int(n) => Some(BigInt::from_i128(i128::from(*n))),
            Value::Big(b) => Some((**b).clone()),
            _ => None,
        }
    }

    /// Python's truth value.
    pub fn truthy(&self) -> bool {
        match self {
            Value::None => false,
            Value::Bool(b) => *b,
            Value::Int(n) => *n != 0,
            Value::Big(_) => true,
            Value::Float(x) => *x != 0.0,
            Value::Text(t) => !t.is_empty(),
            Value::List(xs) => !xs.is_empty(),
            Value::Map(d) => !d.is_empty(),
            _ => true,
        }
    }

    /// The text of the Python type name, as `type(v).__name__` says it.
    pub fn type_name(&self) -> &'static str {
        match self {
            Value::None => "NoneType",
            Value::Bool(_) => "bool",
            Value::Int(_) | Value::Big(_) => "int",
            Value::Float(_) => "float",
            Value::Text(_) => "str",
            Value::List(_) => "list",
            Value::Map(_) => "dict",
            Value::Record(_) => "RecordValue",
            Value::Money(_) => "MoneyValue",
            Value::Func(_) => "Function",
            Value::Bound(_) => "Bound",
        }
    }
}

// ---- comparing ---------------------------------------------------------------

/// Two numbers, compared exactly, as CPython compares an `int` with a
/// `float`: no rounding of the whole number to a double first.
fn num_cmp(a: &Value, b: &Value) -> Option<Ordering> {
    match (a, b) {
        (Value::Float(x), Value::Float(y)) => x.partial_cmp(y),
        (Value::Float(x), other) => num_cmp(other, &Value::Float(*x)).map(Ordering::reverse),
        (whole, Value::Float(y)) => {
            if y.is_nan() {
                return None;
            }
            if y.is_infinite() {
                return Some(if *y > 0.0 { Ordering::Less } else { Ordering::Greater });
            }
            let i = whole.as_big()?;
            let fl = BigInt::from_f64_integral(y.floor())?;
            match i.cmp(&fl) {
                Ordering::Equal if y.fract() != 0.0 => Some(Ordering::Less),
                other => Some(other),
            }
        }
        _ => {
            if let (Some(x), Some(y)) = (a.as_i128(), b.as_i128()) {
                return Some(x.cmp(&y));
            }
            Some(a.as_big()?.cmp(&b.as_big()?))
        }
    }
}

fn is_number(v: &Value) -> bool {
    matches!(v, Value::Bool(_) | Value::Int(_) | Value::Big(_) | Value::Float(_))
}

thread_local! {
    static NAN_IDS: Cell<u64> = const { Cell::new(1) };
}

const NAN_PAYLOAD: u64 = 0x0007_FFFF_FFFF_FFFF;

/// A float that is a new object, as the result of every float operation
/// in CPython is - which matters for a NaN alone, the one value not equal
/// to itself: CPython compares the items of two lists, two maps or two
/// records by identity first (`PyObject_RichCompareBool`), so the same
/// NaN in both is equal there and nowhere else. A NaN made here carries a
/// number of its own in its payload, which a copy keeps and a new NaN
/// does not share.
pub fn fresh_float(x: f64) -> f64 {
    if !x.is_nan() {
        return x;
    }
    let id = NAN_IDS.with(|c| {
        let v = c.get();
        c.set(v + 1);
        v
    });
    f64::from_bits(0x7FF8_0000_0000_0000 | (id & NAN_PAYLOAD))
}

/// Whether two floats are one NaN: the same object, as far as identity
/// can be told.
fn same_nan(a: f64, b: f64) -> bool {
    a.is_nan() && b.is_nan() && a.to_bits() == b.to_bits() && a.to_bits() & NAN_PAYLOAD != 0
}

/// `PyObject_RichCompareBool(a, b, Py_EQ)`: what CPython compares the
/// items of a list, the values of a map and the fields of a record with -
/// identity first, then `==`.
pub fn item_eq(a: &Value, b: &Value) -> bool {
    let same = match (a, b) {
        (Value::Float(x), Value::Float(y)) => same_nan(*x, *y),
        (Value::List(x), Value::List(y)) => Rc::ptr_eq(x, y),
        (Value::Map(x), Value::Map(y)) => Rc::ptr_eq(x, y),
        (Value::Record(x), Value::Record(y)) => Rc::ptr_eq(x, y),
        (Value::Func(x), Value::Func(y)) => Rc::ptr_eq(x, y),
        (Value::Bound(x), Value::Bound(y)) => Rc::ptr_eq(x, y),
        _ => false,
    };
    same || py_eq(a, b)
}

/// `a == b`, as CPython answers it.
pub fn py_eq(a: &Value, b: &Value) -> bool {
    if is_number(a) && is_number(b) {
        return num_cmp(a, b) == Some(Ordering::Equal);
    }
    match (a, b) {
        (Value::None, Value::None) => true,
        (Value::Text(x), Value::Text(y)) => x == y,
        (Value::List(x), Value::List(y)) => {
            Rc::ptr_eq(x, y)
                || (x.len() == y.len() && x.iter().zip(y.iter()).all(|(p, q)| item_eq(p, q)))
        }
        (Value::Map(x), Value::Map(y)) => {
            Rc::ptr_eq(x, y)
                || (x.len() == y.len()
                    && x.entries()
                        .iter()
                        .all(|(k, v)| matches!(y.get(k), Ok(Some(w)) if item_eq(v, w))))
        }
        (Value::Record(x), Value::Record(y)) => {
            Rc::ptr_eq(x, y)
                || (x.name == y.name
                    && x.fields.len() == y.fields.len()
                    && x.fields
                        .iter()
                        .all(|(k, v)| y.fields.iter().any(|(k2, w)| k2 == k && item_eq(v, w))))
        }
        (Value::Money(x), Value::Money(y)) => x == y,
        (Value::Func(x), Value::Func(y)) => Rc::ptr_eq(x, y) || **x == **y,
        (Value::Bound(x), Value::Bound(y)) => Rc::ptr_eq(x, y),
        _ => false,
    }
}

/// `a < b` and the rest, as CPython answers them; `Err` is the
/// `TypeError` of two values that have no order.
pub fn py_order(a: &Value, b: &Value) -> Result<Option<Ordering>, Raised> {
    if is_number(a) && is_number(b) {
        return Ok(num_cmp(a, b));
    }
    match (a, b) {
        (Value::Text(x), Value::Text(y)) => Ok(Some(x.cmp(y))),
        (Value::List(x), Value::List(y)) => {
            for (p, q) in x.iter().zip(y.iter()) {
                if !item_eq(p, q) {
                    return py_order(p, q);
                }
            }
            Ok(Some(x.len().cmp(&y.len())))
        }
        (Value::Money(x), Value::Money(y)) => {
            Ok(Some(x.units.cmp(&y.units).then_with(|| x.currency.cmp(&y.currency))))
        }
        _ => Err(Raised("TypeError")),
    }
}

/// One of `<`, `>`, `<=`, `>=`.
pub fn py_compare(op: &str, a: &Value, b: &Value) -> Result<bool, Raised> {
    // CPython compares lists element by element with the operator itself,
    // so a NaN inside one answers as the operator does; `py_order` gives
    // None for an unordered pair, which every operator answers False.
    let ord = py_order(a, b)?;
    Ok(match (op, ord) {
        (_, None) => false,
        ("<", Some(o)) => o == Ordering::Less,
        (">", Some(o)) => o == Ordering::Greater,
        ("<=", Some(o)) => o != Ordering::Greater,
        (_, Some(o)) => o != Ordering::Less,
    })
}

// ---- writing ---------------------------------------------------------------------

/// The number of digits after the point a currency has.
pub fn currency_digits(code: &str) -> u32 {
    CURRENCIES.iter().find(|(c, _)| *c == code).map_or(0, |(_, d)| *d)
}

/// `money_text`: `INR 12.50`, `JPY 1250`, `INR -0.05`.
pub fn money_text(m: &Money) -> String {
    let digits = currency_digits(&m.currency);
    let sign = if m.units < 0 { "-" } else { "" };
    let whole = i128::from(m.units).unsigned_abs();
    if digits == 0 {
        return format!("{} {sign}{whole}", m.currency);
    }
    let scale = 10u128.pow(digits);
    let width = digits as usize;
    format!("{} {sign}{}.{:0width$}", m.currency, whole / scale, whole % scale)
}

fn int_text(v: &Value) -> String {
    match v {
        Value::Int(n) => n.to_string(),
        Value::Big(b) => b.to_decimal(),
        Value::Bool(b) => i64::from(*b).to_string(),
        _ => String::new(),
    }
}

/// `to_text`: how Sabline writes a value - `print`, `+` with a text,
/// `format`.
pub fn to_text(v: &Value) -> Text {
    // a text is itself, the same object, as `str(v)` gives it back
    if let Value::Text(t) = v {
        return t.clone();
    }
    let mut out = TextBuf::new();
    write_text(&mut out, v);
    out.done()
}

fn write_text(out: &mut TextBuf, v: &Value) {
    match v {
        Value::Money(m) => out.push_str(&money_text(m)),
        Value::Func(f) => {
            out.push_str("fn ");
            out.push_str(&f.name);
        }
        Value::Map(d) => {
            out.push_str("{");
            for (i, (k, x)) in d.entries().iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_text(out, k);
                out.push_str(": ");
                write_text(out, x);
            }
            out.push_str("}");
        }
        Value::Record(r) => {
            out.push_str(&r.name);
            out.push_str("(");
            for (i, (k, x)) in r.fields.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                out.push_str(k);
                out.push_str(": ");
                write_text(out, x);
            }
            out.push_str(")");
        }
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::List(xs) => {
            out.push_str("[");
            for (i, x) in xs.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_text(out, x);
            }
            out.push_str("]");
        }
        other => write_str(out, other),
    }
}

/// `str(v)`: what an f-string writes - a broken promise's message names
/// its values this way, so a yes/no is `True` there.
pub fn py_str(v: &Value) -> Text {
    if let Value::Text(t) = v {
        return t.clone();
    }
    let mut out = TextBuf::new();
    write_str(&mut out, v);
    out.done()
}

fn write_str(out: &mut TextBuf, v: &Value) {
    match v {
        Value::Text(t) => out.push_text(t),
        Value::Money(m) => out.push_str(&money_text(m)),
        other => write_repr(out, other),
    }
}

/// `repr(v)`.
pub fn py_repr(v: &Value) -> Text {
    let mut out = TextBuf::new();
    write_repr(&mut out, v);
    out.done()
}

fn write_repr(out: &mut TextBuf, v: &Value) {
    match v {
        Value::None => out.push_str("None"),
        Value::Bool(b) => out.push_str(if *b { "True" } else { "False" }),
        Value::Int(_) | Value::Big(_) => out.push_str(&int_text(v)),
        Value::Float(x) => out.push_str(&py_float_repr(*x)),
        Value::Text(t) => out.push_str(&t.repr()),
        Value::List(xs) => {
            out.push_str("[");
            for (i, x) in xs.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_repr(out, x);
            }
            out.push_str("]");
        }
        Value::Map(d) => {
            out.push_str("{");
            for (i, (k, x)) in d.entries().iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_repr(out, k);
                out.push_str(": ");
                write_repr(out, x);
            }
            out.push_str("}");
        }
        Value::Money(m) => {
            out.push_str(&format!("MoneyValue(units={}, currency=", m.units));
            out.push_text(&Text::from(&*m.currency).repr().as_str().into());
            out.push_str(")");
        }
        Value::Record(r) => {
            out.push_str(&r.name);
            out.push_str("(");
            for (i, (k, x)) in r.fields.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                out.push_str(k);
                out.push_str("=");
                write_repr(out, x);
            }
            out.push_str(")");
        }
        // `fn` and the function's name - the lifted `fn#N` for one written
        // inline - whether or not it carries names: `Function.__repr__` and
        // `Bound.__repr__` (9.0, M3), which until then wrote the node's
        // dataclass fields and a Python object's address
        Value::Func(f) => {
            out.push_str("fn ");
            out.push_str(&f.name);
        }
        Value::Bound(b) => {
            out.push_str("fn ");
            out.push_str(&b.func.name);
        }
    }
}

/// A value that can be shared by many places in one run and changed by
/// one of them: the counters a run keeps.
pub type Shared<T> = Rc<RefCell<T>>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn numbers_compare_exactly() {
        let big = Value::Int(9007199254740993);
        assert!(!py_eq(&big, &Value::Float(9007199254740992.0)));
        assert!(py_compare(">", &big, &Value::Float(9007199254740992.0)).unwrap());
        assert!(py_eq(&Value::Bool(true), &Value::Int(1)));
        assert!(py_eq(&Value::Int(1), &Value::Float(1.0)));
        assert!(py_compare("<", &Value::Int(2), &Value::Float(2.5)).unwrap());
        assert!(!py_compare("<", &Value::Int(3), &Value::Float(2.5)).unwrap());
        assert!(!py_compare("<", &Value::Float(f64::NAN), &Value::Int(1)).unwrap());
    }

    #[test]
    fn a_dict_is_cpythons() {
        let mut d = Dict::new();
        d.set(Value::Int(1), Value::text("a")).unwrap();
        d.set(Value::Bool(true), Value::text("b")).unwrap();
        d.set(Value::Float(1.0), Value::text("c")).unwrap();
        assert_eq!(d.len(), 1);
        assert_eq!(to_text(&Value::Map(Rc::new(d))), Text::from("{1: c}"));
    }

    #[test]
    fn str_and_text_differ_as_in_python() {
        let xs = Value::list(vec![Value::text("a"), Value::Bool(true), Value::Float(1e16)]);
        assert_eq!(to_text(&xs), Text::from("[a, true, 1e+16]"));
        assert_eq!(py_str(&xs), Text::from("['a', True, 1e+16]"));
        let m = Value::Money(Money { units: -5, currency: Rc::from("INR") });
        assert_eq!(py_str(&m), Text::from("INR -0.05"));
        assert_eq!(
            py_str(&Value::list(vec![m])),
            Text::from("[MoneyValue(units=-5, currency='INR')]")
        );
    }
}
