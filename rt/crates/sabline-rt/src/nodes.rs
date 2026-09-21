//! The syntax tree the parser builds, shape for shape with
//! `sabline/nodes.py`.
//!
//! Python has one dataclass per shape and no sum type; here there is one
//! enum for expressions and one for statements, because the parser puts
//! each in exactly one of those two places. The **field order** of every
//! variant is the declaration order of the Python dataclass, because
//! `parse_lambda`'s free-variable walk visits a node's fields in that
//! order and the order decides what a closure captures and in what order.
//!
//! A number literal is kept as text. `Num(int(t.text))` in Python is an
//! arbitrary-precision integer, and the parser refuses only what CPython
//! refuses to convert - more than 4,300 digits - so `Num` has to hold a
//! value no machine word holds. The dump writes it as decimal text with
//! leading zeros gone, which is what `int()` then `str()` gives.

/// An expression.
#[derive(Debug, Clone, PartialEq)]
pub enum Expr {
    /// A whole number literal. `value` is decimal text, already stripped
    /// of leading zeros and of any non-ASCII digits it was written with.
    Num {
        /// The value as decimal text.
        value: String,
    },
    /// A number with a decimal point.
    FloatNum {
        /// The value.
        value: f64,
    },
    /// Unary minus.
    Neg {
        /// What is negated.
        value: Box<Expr>,
        /// The line.
        line: u32,
    },
    /// A text literal, after its escapes are read.
    Str {
        /// The text.
        value: String,
    },
    /// `true` or `false`.
    Bool {
        /// Which one.
        value: bool,
    },
    /// The value a lifted function value evaluates to.
    Closure {
        /// The generated name of the lifted function.
        name: String,
        /// The names the body read that it did not bind itself.
        free: Vec<String>,
        /// The line.
        line: u32,
    },
    /// A name.
    Var {
        /// The name.
        name: String,
        /// The line.
        line: u32,
    },
    /// A binary operator.
    BinOp {
        /// The operator.
        op: String,
        /// Its left operand.
        left: Box<Expr>,
        /// Its right operand.
        right: Box<Expr>,
        /// The line.
        line: u32,
    },
    /// A call.
    Call {
        /// The function's name, `namespace.name` for a qualified call.
        name: String,
        /// The arguments.
        args: Vec<Expr>,
        /// The line.
        line: u32,
    },
    /// `not e`.
    Not {
        /// What is negated.
        value: Box<Expr>,
        /// The line.
        line: u32,
    },
    /// A record value.
    RecordLit {
        /// The record's name.
        name: String,
        /// Each field and what it is given.
        fields: Vec<(String, Expr)>,
        /// The line.
        line: u32,
    },
    /// A field read.
    FieldGet {
        /// What is read from.
        obj: Box<Expr>,
        /// The field's name.
        field: String,
        /// The line.
        line: u32,
    },
    /// A list value.
    ListLit {
        /// Its items.
        items: Vec<Expr>,
        /// The line.
        line: u32,
    },
    /// A map value.
    MapLit {
        /// Its entries, key and value.
        entries: Vec<(Expr, Expr)>,
        /// The line.
        line: u32,
    },
    /// `try f(args)`.
    TryExpr {
        /// The call, which the parser makes of a call only.
        value: Box<Expr>,
        /// The line.
        line: u32,
    },
}

impl Expr {
    /// Whether this is a `Call`, which `check` and `try` both require.
    pub fn is_call(&self) -> bool {
        matches!(self, Expr::Call { .. })
    }
}

/// A statement.
#[derive(Debug, Clone, PartialEq)]
pub enum Stmt {
    /// `let name = value`, with an optional written type.
    Let {
        /// The name bound.
        name: String,
        /// What it is bound to.
        value: Expr,
        /// The line.
        line: u32,
        /// The written type, when there is one.
        ann: Option<String>,
    },
    /// `return`, with or without a value.
    Return {
        /// What is returned.
        value: Option<Expr>,
        /// The line.
        line: u32,
    },
    /// `if`, with its `else` arm - empty when there is none.
    If {
        /// The condition.
        cond: Expr,
        /// The `then` arm.
        then: Vec<Stmt>,
        /// The `else` arm.
        other: Vec<Stmt>,
        /// The line.
        line: u32,
    },
    /// `while`, and the invariants written on it.
    While {
        /// The condition.
        cond: Expr,
        /// The body.
        body: Vec<Stmt>,
        /// The line.
        line: u32,
        /// Each invariant and the line it was written on.
        invariants: Vec<(Expr, u32)>,
    },
    /// `name = value`.
    Assign {
        /// The name assigned.
        name: String,
        /// What it is given.
        value: Expr,
        /// The line.
        line: u32,
    },
    /// A group of statements a `for` was desugared into.
    ///
    /// `parse_block` flattens these away, so one reaches a later stage
    /// only if some path stops flattening; it is here because the Python
    /// node is.
    Block {
        /// The statements.
        stmts: Vec<Stmt>,
        /// The line.
        line: u32,
    },
    /// An expression on a line of its own.
    ExprStmt {
        /// The expression.
        expr: Expr,
        /// The line.
        line: u32,
    },
    /// `fail e`.
    FailStmt {
        /// The reason.
        value: Expr,
        /// The line.
        line: u32,
    },
    /// `check f(args) { ok v { .. } fail why { .. } }`.
    Check {
        /// The call, which the parser makes of a call only.
        subject: Expr,
        /// The line.
        line: u32,
        /// The name the `ok` arm binds, when it names one.
        ok_name: Option<String>,
        /// The `ok` arm.
        ok_body: Vec<Stmt>,
        /// The name the `fail` arm binds.
        fail_name: String,
        /// The `fail` arm.
        fail_body: Vec<Stmt>,
    },
}

/// A record definition.
#[derive(Debug, Clone, PartialEq)]
pub struct RecordDef {
    /// Its name.
    pub name: String,
    /// Each field and its type.
    pub fields: Vec<(String, String)>,
    /// The line.
    pub line: u32,
    /// The file it came from; the loader sets it, so the parser leaves it
    /// empty.
    pub src_file: String,
}

/// A function, written or lifted.
#[derive(Debug, Clone, PartialEq)]
pub struct Function {
    /// Its name, or the generated `fn#N` of a lifted function value.
    pub name: String,
    /// Each parameter and its type.
    pub params: Vec<(String, String)>,
    /// Its result type, when it has one.
    pub return_type: Option<String>,
    /// The effects it declares, sorted - Python holds them in a set, and a
    /// set has no order to copy.
    pub effects: Vec<String>,
    /// Each `requires` and the line it was written on.
    pub requires: Vec<(Expr, u32)>,
    /// Each `ensures` and the line it was written on.
    pub ensures: Vec<(Expr, u32)>,
    /// Its body.
    pub body: Vec<Stmt>,
    /// The line.
    pub line: u32,
    /// The file it came from; the loader sets it.
    pub src_file: String,
    /// Whether it is marked `or fail`.
    pub can_fail: bool,
    /// The type variables it is generic in.
    pub type_vars: Vec<String>,
    /// Whether it was lifted from a function value.
    pub is_lambda: bool,
    /// What it captures; the type checker fills this in.
    pub captures: Vec<(String, String)>,
    /// The names a lifted function value read that it did not bind.
    ///
    /// Python sets this as a plain attribute rather than a field, so that
    /// a node's fields, repr and equality stay as they were; a function
    /// that is not a lifted one has no attribute, and every reader asks
    /// for it with a default of the empty list. Here it is always a list
    /// and it is always empty for a written function, which is the same
    /// thing to every reader.
    pub free_names: Vec<String>,
}

/// An `import`: the path, the line, and the name it was given.
#[derive(Debug, Clone, PartialEq)]
pub struct Import {
    /// The path, after its escapes are read.
    pub path: String,
    /// The line.
    pub line: u32,
    /// The name after `as`, when there is one.
    pub alias: Option<String>,
}

/// What `parse_program` answers: the functions, the records and the
/// imports of one file.
#[derive(Debug, Clone, PartialEq)]
pub struct Program {
    /// Every function, lifted ones before the function that lifted them.
    pub funcs: Vec<Function>,
    /// Every record definition.
    pub records: Vec<RecordDef>,
    /// Every import.
    pub imports: Vec<Import>,
}
