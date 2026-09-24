//! Stage 2, the parser: tokens into a syntax tree, by recursive descent.
//!
//! A transliteration of `sabline/parser.py`, rule for rule and message for
//! message. Where a choice looks arbitrary it is because the Python parser
//! makes it; the comments say which line of Python a rule comes from when
//! the rule would otherwise read as a decision made here.
//!
//! Two things are desugared here so nothing later has to know about them:
//! `for` loops become `while` loops, and function values are lifted into
//! ordinary top-level functions with generated names.
//!
//! The depth caps are Python's, and they are the reason a pathological
//! program is a coded error in both rather than a traceback in one and a
//! stack overflow in the other.

use crate::errors::{Answer, SablineError};
use crate::lexer::{fmt_fn_type, unescape, Kind, Token};
use crate::nodes::{Expr, Function, Import, Program, RecordDef, Stmt};
use crate::unicode_nd::decimal_value;
use std::collections::HashSet;

/// Operators in one left-associative run, past which E102.
pub const EXPR_CHAIN_LIMIT: u32 = 1000;
/// Bracket and unary nesting depth, past which E102.
pub const EXPR_NEST_LIMIT: u32 = 1000;
/// Blocks in blocks, and else-if chains, past which E102 (8.2).
pub const BLOCK_NEST_LIMIT: u32 = 4000;
/// The digits CPython will convert from text to a whole number, past which
/// `int()` raises and the parser gives E407.
///
/// It is CPython's `sys.get_int_max_str_digits()`, whose default is 4,300.
/// The default is what the reference runs with; a `PYTHONINTMAXSTRDIGITS`
/// in the environment moves it there and not here, which rt/README.md
/// records as a difference the spec does not cover.
pub const INT_MAX_STR_DIGITS: usize = 4300;

/// A recursive-descent parser over one file's tokens.
pub struct Parser {
    toks: Vec<Token>,
    i: usize,
    lifted: Vec<Function>,
    /// `Parser.lambda_n` in Python, where it is a class attribute that is
    /// never reset - so a generated name depends on how many function
    /// values the process parsed before. Here it belongs to the parser,
    /// and `sabline ast --json` sets Python's to zero per file so that a
    /// dump of one file is a function of that file. rt/README.md says so.
    lambda_n: u32,
    nest: u32,
    blocks: u32,
}

impl Parser {
    /// A parser over `tokens`.
    pub fn new(tokens: Vec<Token>) -> Self {
        Self { toks: tokens, i: 0, lifted: Vec::new(), lambda_n: 0, nest: 0, blocks: 0 }
    }

    // ---- the token cursor ------------------------------------------------

    fn peek(&self) -> &Token {
        // The list always ends with EOF and no rule consumes past it, so
        // the fallback is unreachable; it is here so that a defect is a
        // wrong answer rather than a panic.
        self.toks
            .get(self.i)
            .unwrap_or_else(|| self.toks.last().expect("the token list always holds EOF"))
    }

    fn at(&self, offset: usize) -> &Token {
        self.toks
            .get(self.i + offset)
            .unwrap_or_else(|| self.toks.last().expect("the token list always holds EOF"))
    }

    fn next(&mut self) -> Token {
        let t = self.peek().clone();
        self.i += 1;
        t
    }

    fn peek_text(&self) -> &str {
        &self.peek().text
    }

    fn expect(&mut self, kind: Kind, text: Option<&str>) -> Answer<Token> {
        let t = self.peek();
        let wrong_kind = t.kind != kind;
        let wrong_text = text.is_some_and(|want| t.text != want);
        if wrong_kind || wrong_text {
            let want = match text {
                Some(w) => w.to_string(),
                None => kind.name().to_lowercase(),
            };
            let found =
                if t.text.is_empty() { "end of file".to_string() } else { t.text.clone() };
            return Err(SablineError::with_fixes(
                "E100",
                format!("expected '{want}' but found '{found}'"),
                t.line,
                &[&format!("insert '{want}' here")],
            ));
        }
        Ok(self.next())
    }

    // ---- the two depth refusals -----------------------------------------

    fn too_deep(&self, line: u32) -> SablineError {
        SablineError::with_fixes(
            "E102",
            "this expression nests, or chains operators, too deeply",
            line,
            &[
                "split it into smaller pieces with intermediate 'let' bindings",
                "a single expression this large is almost always a bug",
            ],
        )
    }

    fn too_deep_block(&self, line: u32) -> SablineError {
        SablineError::with_fixes(
            "E102",
            format!(
                "blocks nest more than {BLOCK_NEST_LIMIT} deep here (an \
                 'if', 'while', 'for' or 'else if' inside another)"
            ),
            line,
            &[
                "move the inner part into a function of its own",
                "a program nested this deeply was almost always generated by mistake",
            ],
        )
    }

    // ---- the program ------------------------------------------------------

    /// Read a whole file: its functions, records and imports.
    pub fn parse_program(mut self) -> Answer<Program> {
        let mut records: Vec<RecordDef> = Vec::new();
        let mut imports: Vec<Import> = Vec::new();
        while self.peek().kind != Kind::Eof {
            let t = self.peek().clone();
            if t.kind == Kind::Keyword && t.text == "import" {
                self.next();
                let s = self.expect(Kind::Str, None)?;
                let mut alias = None;
                if self.peek().kind == Kind::Ident && self.peek_text() == "as" {
                    self.next();
                    alias = Some(self.expect(Kind::Ident, None)?.text);
                }
                let inner: String = s.text.chars().skip(1).collect();
                let inner: String =
                    inner.chars().take(inner.chars().count().saturating_sub(1)).collect();
                imports.push(Import { path: unescape(&inner, s.line)?, line: t.line, alias });
            } else if t.kind == Kind::Keyword && t.text == "record" {
                let record = self.parse_record()?;
                records.push(record);
            } else {
                let f = self.parse_function()?;
                self.lifted.push(f);
            }
        }
        Ok(Program { funcs: self.lifted, records, imports })
    }

    fn parse_record(&mut self) -> Answer<RecordDef> {
        let start = self.expect(Kind::Keyword, Some("record"))?;
        let name = self.expect(Kind::Ident, None)?.text;
        self.expect(Kind::Op, Some("{"))?;
        let mut fields = Vec::new();
        // No comma is read between fields, and none is allowed: a comma
        // makes the next `expect(IDENT)` fail with E100.
        while self.peek_text() != "}" {
            let fname = self.expect(Kind::Ident, None)?.text;
            self.expect(Kind::Op, Some(":"))?;
            fields.push((fname, self.parse_type()?));
        }
        self.expect(Kind::Op, Some("}"))?;
        Ok(RecordDef { name, fields, line: start.line, src_file: String::new() })
    }

    fn parse_function(&mut self) -> Answer<Function> {
        let start = self.expect(Kind::Keyword, Some("fn"))?;
        let name = self.expect(Kind::Ident, None)?.text;
        self.expect(Kind::Op, Some("("))?;
        let mut params = Vec::new();
        while self.peek_text() != ")" {
            let pname = self.expect(Kind::Ident, None)?.text;
            self.expect(Kind::Op, Some(":"))?;
            let ptype = self.parse_type()?;
            params.push((pname, ptype));
            if self.peek_text() == "," {
                self.next();
            }
        }
        self.expect(Kind::Op, Some(")"))?;
        let mut ret = None;
        if self.peek().kind == Kind::Arrow {
            self.next();
            ret = Some(self.parse_type()?);
        }
        let mut effects: HashSet<String> = HashSet::new();
        let mut type_vars: Vec<String> = Vec::new();
        let mut can_fail = false;
        loop {
            // uses / for any / or fail, in any order
            let t2 = self.peek().clone();
            if t2.kind == Kind::Keyword && t2.text == "uses" {
                self.next();
                effects.insert(self.expect(Kind::Ident, None)?.text);
                while self.peek_text() == "," {
                    self.next();
                    effects.insert(self.expect(Kind::Ident, None)?.text);
                }
            } else if t2.kind == Kind::Keyword && t2.text == "for" {
                self.next();
                let anykw = self.expect(Kind::Ident, None)?;
                if anykw.text != "any" {
                    return Err(SablineError::with_fixes(
                        "E100",
                        "expected 'any' after 'for'",
                        anykw.line,
                        &["write: for any T"],
                    ));
                }
                type_vars.push(self.expect(Kind::Ident, None)?.text);
                while self.peek_text() == "," {
                    self.next();
                    type_vars.push(self.expect(Kind::Ident, None)?.text);
                }
            } else if t2.kind == Kind::Keyword && t2.text == "or" && self.at(1).text == "fail"
            {
                self.next();
                self.next();
                can_fail = true;
            } else {
                break;
            }
        }
        let (requires_, ensures_) = self.parse_clauses()?;
        let body = self.parse_block()?;
        let mut sorted: Vec<String> = effects.into_iter().collect();
        sorted.sort();
        Ok(Function {
            name,
            params,
            return_type: ret,
            effects: sorted,
            requires: requires_,
            ensures: ensures_,
            body,
            line: start.line,
            src_file: String::new(),
            can_fail,
            type_vars,
            is_lambda: false,
            captures: Vec::new(),
            free_names: Vec::new(),
        })
    }

    #[allow(clippy::type_complexity)]
    fn parse_clauses(&mut self) -> Answer<(Vec<(Expr, u32)>, Vec<(Expr, u32)>)> {
        let mut requires_ = Vec::new();
        let mut ensures_ = Vec::new();
        while self.peek().kind == Kind::Keyword
            && matches!(self.peek_text(), "requires" | "ensures")
        {
            let kw = self.next();
            let clause = (self.parse_expr()?, kw.line);
            if kw.text == "requires" {
                requires_.push(clause);
            } else {
                ensures_.push(clause);
            }
        }
        Ok((requires_, ensures_))
    }

    /// `fn(x: Int) -> Bool { return x > 0 }` as a value.
    ///
    /// Lifted to a real top-level function with a generated name, so every
    /// later stage sees an ordinary function. A local the body reads from
    /// around it is captured as its value when the value is made
    /// (SPEC.md 12a): a snapshot, never a reference.
    fn parse_lambda(&mut self, start: &Token) -> Answer<Expr> {
        self.expect(Kind::Op, Some("("))?;
        let mut params = Vec::new();
        while self.peek_text() != ")" {
            let pname = self.expect(Kind::Ident, None)?.text;
            self.expect(Kind::Op, Some(":"))?;
            params.push((pname, self.parse_type()?));
            if self.peek_text() == "," {
                self.next();
            }
        }
        self.expect(Kind::Op, Some(")"))?;
        if self.peek_text() != "->" {
            return Err(SablineError::with_fixes(
                "E100",
                "a function value needs a result type",
                start.line,
                &["write: fn(x: Int) -> Bool { return x > 0 }"],
            ));
        }
        self.next();
        let ret = self.parse_type()?;
        // a function value can promise too
        let (requires_, ensures_) = self.parse_clauses()?;
        let body = self.parse_block()?;
        self.lambda_n += 1;
        let name = format!("fn#{}", self.lambda_n);
        // names the body reads that it did not bind itself: candidates for
        // capture. Which are really locals is known only once the
        // surrounding function is type checked, so decide there.
        let mut bound: HashSet<String> = params.iter().map(|(p, _)| p.clone()).collect();
        let mut free: Vec<String> = Vec::new();
        for s in &body {
            visit_stmt(s, &mut bound, &mut free);
        }
        let f = Function {
            name: name.clone(),
            params,
            return_type: Some(ret),
            effects: Vec::new(),
            requires: requires_,
            ensures: ensures_,
            body,
            line: start.line,
            src_file: String::new(),
            can_fail: false,
            type_vars: Vec::new(),
            is_lambda: true,
            captures: Vec::new(),
            free_names: free.clone(),
        };
        self.lifted.push(f);
        Ok(Expr::Closure { name, free, line: start.line })
    }

    fn flatten(stmts: Vec<Stmt>) -> Vec<Stmt> {
        let mut out = Vec::with_capacity(stmts.len());
        for s in stmts {
            match s {
                Stmt::Block { stmts, .. } => out.extend(Parser::flatten(stmts)),
                other => out.push(other),
            }
        }
        out
    }

    fn parse_block(&mut self) -> Answer<Vec<Stmt>> {
        self.expect(Kind::Op, Some("{"))?;
        let mut stmts = Vec::new();
        // Past BLOCK_NEST_LIMIT the parser stops with E102. Until 8.2
        // nothing capped blocks: some thousands deep parsed, and then
        // overflowed a later stage's walk with a Python traceback.
        self.blocks += 1;
        if self.blocks > BLOCK_NEST_LIMIT {
            let line = self.peek().line;
            self.blocks -= 1;
            return Err(self.too_deep_block(line));
        }
        let mut outcome = Ok(());
        while self.peek_text() != "}" {
            match self.parse_statement() {
                Ok(s) => stmts.push(s),
                Err(e) => {
                    outcome = Err(e);
                    break;
                }
            }
        }
        self.blocks -= 1;
        outcome?;
        self.expect(Kind::Op, Some("}"))?;
        Ok(Parser::flatten(stmts))
    }

    // Each branch of `parse_statement` that builds much is its own
    // function, and each is `#[inline(never)]`. A compiler gives one frame
    // the room of the widest branch in it, so folding them together would
    // make every level of a 4,000-deep program pay for the `for`
    // desugaring's locals. `tests/limits.rs` measures what one level costs
    // and fails if it grows.

    fn parse_statement(&mut self) -> Answer<Stmt> {
        let t = self.peek().clone();
        if t.kind == Kind::Keyword {
            match t.text.as_str() {
                "let" => return self.parse_let(&t),
                "return" => return self.parse_return(&t),
                "fail" => {
                    self.next();
                    return Ok(Stmt::FailStmt { value: self.parse_expr()?, line: t.line });
                }
                "check" => return self.parse_check(&t),
                "for" => return self.parse_for(&t),
                "while" => return self.parse_while(&t),
                "if" => return self.parse_if(&t),
                _ => {}
            }
        }
        if t.kind == Kind::Ident && self.at(1).text == "." {
            // looks like p.x(.y)* = ...
            let mut j = self.i + 1;
            while self.toks.get(j).is_some_and(|k| k.text == ".")
                && self.toks.get(j + 1).is_some_and(|k| k.kind == Kind::Ident)
            {
                j += 2;
            }
            if self.toks.get(j).is_some_and(|k| k.text == "=") {
                return Err(SablineError::with_fixes(
                    "E511",
                    "records cannot be changed in place",
                    t.line,
                    &["build a new one: let p2 = Point(x: new_value, y: p.y)"],
                ));
            }
        }
        if t.kind == Kind::Ident && self.at(1).text == "=" {
            self.next();
            self.expect(Kind::Op, Some("="))?;
            return Ok(Stmt::Assign { name: t.text, value: self.parse_expr()?, line: t.line });
        }
        Ok(Stmt::ExprStmt { expr: self.parse_expr()?, line: t.line })
    }

    #[inline(never)]
    fn parse_let(&mut self, t: &Token) -> Answer<Stmt> {
        self.next();
        let name = self.expect(Kind::Ident, None)?.text;
        let mut ann = None;
        if self.peek_text() == ":" {
            self.next();
            ann = Some(self.parse_type()?);
        }
        self.expect(Kind::Op, Some("="))?;
        Ok(Stmt::Let { name, value: self.parse_expr()?, line: t.line, ann })
    }

    #[inline(never)]
    fn parse_return(&mut self, t: &Token) -> Answer<Stmt> {
        self.next();
        if self.peek_text() == "}" {
            // a bare 'return' with no value
            return Ok(Stmt::Return { value: None, line: t.line });
        }
        Ok(Stmt::Return { value: Some(self.parse_expr()?), line: t.line })
    }

    #[inline(never)]
    fn parse_if(&mut self, t: &Token) -> Answer<Stmt> {
        self.next();
        let cond = self.parse_expr()?;
        let then = self.parse_block()?;
        let mut other = Vec::new();
        if self.peek_text() == "else" {
            self.next();
            if self.peek().kind == Kind::Keyword && self.peek_text() == "if" {
                // an else-if chain nests as blocks do
                self.blocks += 1;
                if self.blocks > BLOCK_NEST_LIMIT {
                    let line = self.peek().line;
                    self.blocks -= 1;
                    return Err(self.too_deep_block(line));
                }
                let inner = self.parse_statement();
                self.blocks -= 1;
                other = vec![inner?];
            } else {
                other = self.parse_block()?;
            }
        }
        Ok(Stmt::If { cond, then, other, line: t.line })
    }

    #[inline(never)]
    fn parse_while(&mut self, t: &Token) -> Answer<Stmt> {
        self.next();
        let cond = self.parse_expr()?;
        let invariants = self.parse_invariants()?;
        let body = self.parse_block()?;
        Ok(Stmt::While { cond, body, line: t.line, invariants })
    }

    #[inline(never)]
    fn parse_check(&mut self, t: &Token) -> Answer<Stmt> {
        self.next();
        let subject = self.parse_expr()?;
        if matches!(subject, Expr::TryExpr { .. }) || !subject.is_call() {
            return Err(SablineError::with_fixes(
                "E100",
                "'check' needs a call to a function that can fail",
                t.line,
                &["write: check f(args) { ok v { ... } fail reason { ... } }"],
            ));
        }
        self.expect(Kind::Op, Some("{"))?;
        let okkw = self.expect(Kind::Ident, None)?;
        if okkw.text != "ok" {
            return Err(SablineError::with_fixes(
                "E100",
                "expected 'ok' arm first in check",
                okkw.line,
                &["write: ok value { ... }"],
            ));
        }
        let mut ok_name = None;
        if self.peek().kind == Kind::Ident {
            ok_name = Some(self.next().text);
        }
        let ok_body = self.parse_block()?;
        self.expect(Kind::Keyword, Some("fail"))?;
        let fail_name = self.expect(Kind::Ident, None)?.text;
        let fail_body = self.parse_block()?;
        self.expect(Kind::Op, Some("}"))?;
        Ok(Stmt::Check { subject, line: t.line, ok_name, ok_body, fail_name, fail_body })
    }

    /// `for` becomes `while`, so nothing after the parser knows about it.
    #[inline(never)]
    fn parse_for(&mut self, t: &Token) -> Answer<Stmt> {
        let line = t.line;
        self.next();
        let name = self.expect(Kind::Ident, None)?.text;
        let inw = self.expect(Kind::Ident, None)?;
        if inw.text != "in" {
            return Err(SablineError::with_fixes(
                "E100",
                "expected 'in' after the name",
                inw.line,
                &["write: for i in 0 to n { ... }", "or:    for item in xs { ... }"],
            ));
        }
        let start = self.parse_expr()?;
        if self.peek().kind == Kind::Ident && self.peek_text() == "to" {
            // for i in a to b
            self.next();
            let stop = self.parse_expr()?;
            let invariants = self.parse_invariants()?;
            let mut body = self.parse_block()?;
            body.push(Stmt::Assign { name: name.clone(), value: plus_one(&name, line), line });
            let cond = Expr::BinOp {
                op: "<".into(),
                left: Box::new(Expr::Var { name: name.clone(), line }),
                right: Box::new(stop),
                line,
            };
            return Ok(Stmt::Block {
                stmts: vec![
                    Stmt::Let { name, value: start, line, ann: None },
                    Stmt::While { cond, body, line, invariants },
                ],
                line,
            });
        }
        // for item in xs
        self.lambda_n += 1;
        let idx = format!("for#{}", self.lambda_n);
        let invariants = self.parse_invariants()?;
        let body = self.parse_block()?;
        let mut inner = vec![Stmt::Let {
            name,
            value: Expr::Call {
                name: "get".into(),
                args: vec![start.clone(), Expr::Var { name: idx.clone(), line }],
                line,
            },
            line,
            ann: None,
        }];
        inner.extend(body);
        inner.push(Stmt::Assign { name: idx.clone(), value: plus_one(&idx, line), line });
        let cond = Expr::BinOp {
            op: "<".into(),
            left: Box::new(Expr::Var { name: idx.clone(), line }),
            right: Box::new(Expr::Call { name: "length".into(), args: vec![start], line }),
            line,
        };
        Ok(Stmt::Block {
            stmts: vec![
                Stmt::Let {
                    name: idx,
                    value: Expr::Num { value: "0".into() },
                    line,
                    ann: None,
                },
                Stmt::While { cond, body: inner, line, invariants },
            ],
            line,
        })
    }

    fn parse_invariants(&mut self) -> Answer<Vec<(Expr, u32)>> {
        let mut invs = Vec::new();
        while self.peek().kind == Kind::Keyword && self.peek_text() == "invariant" {
            let kw = self.next();
            invs.push((self.parse_expr()?, kw.line));
        }
        Ok(invs)
    }

    // ---- types -----------------------------------------------------------

    fn parse_type(&mut self) -> Answer<String> {
        if self.peek().kind == Kind::Keyword && self.peek_text() == "fn" {
            self.next();
            self.expect(Kind::Op, Some("("))?;
            let mut parts = Vec::new();
            while self.peek_text() != ")" {
                parts.push(self.parse_type()?);
                if self.peek_text() == "," {
                    self.next();
                }
            }
            self.expect(Kind::Op, Some(")"))?;
            let mut ret = None;
            if self.peek().kind == Kind::Arrow {
                self.next();
                ret = Some(self.parse_type()?);
            }
            return Ok(fmt_fn_type(&parts, ret.as_deref()));
        }
        let t = self.expect(Kind::Ident, None)?;
        if t.text == "Map" {
            let of = self.expect(Kind::Ident, None)?;
            if of.text != "of" {
                return Err(SablineError::with_fixes(
                    "E100",
                    "expected 'of' after 'Map'",
                    of.line,
                    &["write map types like: Map of Text to Int"],
                ));
            }
            let key = self.expect(Kind::Ident, None)?.text;
            let to = self.expect(Kind::Ident, None)?;
            if to.text != "to" {
                return Err(SablineError::with_fixes(
                    "E100",
                    "expected 'to' after the key type",
                    to.line,
                    &["write map types like: Map of Text to Int"],
                ));
            }
            return Ok(format!("Map of {key} to {}", self.parse_type()?));
        }
        if t.text == "List" {
            let of = self.expect(Kind::Ident, None)?;
            if of.text != "of" {
                return Err(SablineError::with_fixes(
                    "E100",
                    "expected 'of' after 'List'",
                    of.line,
                    &["write list types like: List of Int"],
                ));
            }
            // nesting allowed
            return Ok(format!("List of {}", self.parse_type()?));
        }
        // an amount: Money of INR, or Money of C in a function generic in
        // its currency (4.3). 'Money' alone stays a name, so a program's
        // own record called Money means what it did - including one
        // followed by a field called 'of'.
        if t.text == "Money"
            && self.peek_text() == "of"
            && self.at(1).kind == Kind::Ident
            && self.at(2).text != ":"
        {
            self.next();
            return Ok(format!("Money of {}", self.next().text));
        }
        // a value that must not escape: Secret of Text, Secret of Int,
        // Secret of List of Text (5.1/6.0, SPEC.md 3.1). Like Money,
        // `Secret` alone stays a name.
        if t.text == "Secret"
            && self.peek_text() == "of"
            && self.at(1).kind == Kind::Ident
            && self.at(2).text != ":"
        {
            self.next();
            let inner = self.parse_type()?;
            if inner.starts_with("Secret of ") {
                return Err(SablineError::with_fixes(
                    "E562",
                    format!("a Secret of a Secret is the same secret; write {inner}"),
                    t.line,
                    &[&format!("write {inner}")],
                ));
            }
            return Ok(format!("Secret of {inner}"));
        }
        Ok(t.text)
    }

    // ---- expressions -----------------------------------------------------
    // or -> and -> not -> comparison -> add/sub -> mul/div -> atoms

    fn parse_expr(&mut self) -> Answer<Expr> {
        let mut left = self.parse_and()?;
        let mut n = 0;
        while self.peek().kind == Kind::Keyword && self.peek_text() == "or" {
            let op = self.next();
            n += 1;
            if n > EXPR_CHAIN_LIMIT {
                return Err(self.too_deep(op.line));
            }
            left = Expr::BinOp {
                op: "or".into(),
                left: Box::new(left),
                right: Box::new(self.parse_and()?),
                line: op.line,
            };
        }
        Ok(left)
    }

    fn parse_and(&mut self) -> Answer<Expr> {
        let mut left = self.parse_not()?;
        let mut n = 0;
        while self.peek().kind == Kind::Keyword && self.peek_text() == "and" {
            let op = self.next();
            n += 1;
            if n > EXPR_CHAIN_LIMIT {
                return Err(self.too_deep(op.line));
            }
            left = Expr::BinOp {
                op: "and".into(),
                left: Box::new(left),
                right: Box::new(self.parse_not()?),
                line: op.line,
            };
        }
        Ok(left)
    }

    fn parse_not(&mut self) -> Answer<Expr> {
        let t = self.peek().clone();
        if t.kind == Kind::Keyword && t.text == "not" {
            self.next();
            self.nest += 1;
            if self.nest > EXPR_NEST_LIMIT {
                self.nest -= 1;
                return Err(self.too_deep(t.line));
            }
            let inner = self.parse_not();
            self.nest -= 1;
            return Ok(Expr::Not { value: Box::new(inner?), line: t.line });
        }
        self.parse_cmp()
    }

    fn parse_cmp(&mut self) -> Answer<Expr> {
        let mut left = self.parse_add()?;
        let mut n = 0;
        while matches!(self.peek_text(), "==" | "!=" | "<" | ">" | "<=" | ">=") {
            let op = self.next();
            n += 1;
            if n > EXPR_CHAIN_LIMIT {
                return Err(self.too_deep(op.line));
            }
            left = Expr::BinOp {
                op: op.text.clone(),
                left: Box::new(left),
                right: Box::new(self.parse_add()?),
                line: op.line,
            };
        }
        Ok(left)
    }

    fn parse_add(&mut self) -> Answer<Expr> {
        let mut left = self.parse_mul()?;
        let mut n = 0;
        while matches!(self.peek_text(), "+" | "-") {
            let op = self.next();
            n += 1;
            if n > EXPR_CHAIN_LIMIT {
                return Err(self.too_deep(op.line));
            }
            left = Expr::BinOp {
                op: op.text.clone(),
                left: Box::new(left),
                right: Box::new(self.parse_mul()?),
                line: op.line,
            };
        }
        Ok(left)
    }

    fn parse_mul(&mut self) -> Answer<Expr> {
        let mut left = self.parse_postfix()?;
        let mut n = 0;
        while matches!(self.peek_text(), "*" | "/" | "%") {
            let op = self.next();
            n += 1;
            if n > EXPR_CHAIN_LIMIT {
                return Err(self.too_deep(op.line));
            }
            left = Expr::BinOp {
                op: op.text.clone(),
                left: Box::new(left),
                right: Box::new(self.parse_postfix()?),
                line: op.line,
            };
        }
        Ok(left)
    }

    fn parse_postfix(&mut self) -> Answer<Expr> {
        let mut e = self.parse_atom()?;
        while self.peek_text() == "." {
            let dot = self.next();
            let fname = self.expect(Kind::Ident, None)?.text;
            e = Expr::FieldGet { obj: Box::new(e), field: fname, line: dot.line };
        }
        Ok(e)
    }

    fn parse_atom(&mut self) -> Answer<Expr> {
        self.nest += 1;
        if self.nest > EXPR_NEST_LIMIT {
            let line = self.peek().line;
            self.nest -= 1;
            return Err(self.too_deep(line));
        }
        let out = self.parse_atom_inner();
        self.nest -= 1;
        out
    }

    fn parse_atom_inner(&mut self) -> Answer<Expr> {
        let t = self.next();
        if t.kind == Kind::Keyword && t.text == "fn" {
            return self.parse_lambda(&t);
        }
        if t.kind == Kind::Keyword && t.text == "try" {
            let inner = self.parse_postfix()?;
            if !inner.is_call() {
                return Err(SablineError::with_fixes(
                    "E100",
                    "'try' needs a call to a function that can fail",
                    t.line,
                    &["write: try f(args)"],
                ));
            }
            return Ok(Expr::TryExpr { value: Box::new(inner), line: t.line });
        }
        if t.text == "-" {
            // negative numbers: -7, -x
            return Ok(Expr::Neg { value: Box::new(self.parse_postfix()?), line: t.line });
        }
        if t.text == "{" {
            // map literal: {"a": 1}
            let mut entries = Vec::new();
            while self.peek_text() != "}" {
                let k = self.parse_expr()?;
                self.expect(Kind::Op, Some(":"))?;
                entries.push((k, self.parse_expr()?));
                if self.peek_text() == "," {
                    self.next();
                }
            }
            self.expect(Kind::Op, Some("}"))?;
            return Ok(Expr::MapLit { entries, line: t.line });
        }
        if t.text == "[" {
            // list literal: [1, 2, 3]
            let mut items = Vec::new();
            while self.peek_text() != "]" {
                items.push(self.parse_expr()?);
                if self.peek_text() == "," {
                    self.next();
                }
            }
            self.expect(Kind::Op, Some("]"))?;
            return Ok(Expr::ListLit { items, line: t.line });
        }
        if t.kind == Kind::Number {
            return match int_text(&t.text) {
                Some(value) => Ok(Expr::Num { value }),
                // past the digits CPython converts (4,300 by default); a
                // traceback until 8.2
                None => Err(SablineError::with_fixes(
                    "E407",
                    format!(
                        "this whole number has {} digits (whole numbers go \
                         from -9223372036854775808 to 9223372036854775807)",
                        t.text.chars().count()
                    ),
                    t.line,
                    &["write a smaller number"],
                )),
            };
        }
        if t.kind == Kind::Float {
            return Ok(Expr::FloatNum { value: float_of(&t.text) });
        }
        if t.kind == Kind::Str {
            let inner: String = t.text.chars().skip(1).collect();
            let inner: String =
                inner.chars().take(inner.chars().count().saturating_sub(1)).collect();
            return Ok(Expr::Str { value: unescape(&inner, t.line)? });
        }
        if t.kind == Kind::Keyword && matches!(t.text.as_str(), "true" | "false") {
            return Ok(Expr::Bool { value: t.text == "true" });
        }
        if t.text == "(" {
            let e = self.parse_expr()?;
            self.expect(Kind::Op, Some(")"))?;
            return Ok(e);
        }
        if t.kind == Kind::Ident {
            if self.peek_text() == "."
                && self.at(1).kind == Kind::Ident
                && self.at(2).text == "("
            {
                self.next(); // '.'
                let fname = self.next().text; // function in namespace
                self.next(); // '('
                let mut qargs = Vec::new();
                while self.peek_text() != ")" {
                    qargs.push(self.parse_expr()?);
                    if self.peek_text() == "," {
                        self.next();
                    }
                }
                self.expect(Kind::Op, Some(")"))?;
                return Ok(Expr::Call {
                    name: format!("{}.{fname}", t.text),
                    args: qargs,
                    line: t.line,
                });
            }
            if self.peek_text() == "("
                && self.at(1).kind == Kind::Ident
                && self.at(2).text == ":"
            {
                self.next(); // record literal
                let mut fields = Vec::new();
                while self.peek_text() != ")" {
                    let fname = self.expect(Kind::Ident, None)?.text;
                    self.expect(Kind::Op, Some(":"))?;
                    fields.push((fname, self.parse_expr()?));
                    if self.peek_text() == "," {
                        self.next();
                    }
                }
                self.expect(Kind::Op, Some(")"))?;
                return Ok(Expr::RecordLit { name: t.text, fields, line: t.line });
            }
            if self.peek_text() == "(" {
                // function call
                self.next();
                let mut args = Vec::new();
                while self.peek_text() != ")" {
                    args.push(self.parse_expr()?);
                    if self.peek_text() == "," {
                        self.next();
                    }
                }
                self.expect(Kind::Op, Some(")"))?;
                return Ok(Expr::Call { name: t.text, args, line: t.line });
            }
            return Ok(Expr::Var { name: t.text, line: t.line });
        }
        Err(self.unexpected(&t))
    }

    /// E101: a token that cannot start a value. A keyword is told what it
    /// is for, and never that a call was expected: told that, a model
    /// wrote `fail(...)` for six rounds (evals/roundtrip, 8.7). The words
    /// are `sabline/parser.py`'s `_unexpected`, and the agreement gate
    /// compares them.
    fn unexpected(&self, t: &Token) -> SablineError {
        let before = self.i.checked_sub(2).and_then(|j| self.toks.get(j));
        let keyword = t.kind == Kind::Keyword;
        let after_or = before.is_some_and(|b| b.kind == Kind::Keyword && b.text == "or");
        let fixes: Vec<String> = if keyword && t.text == "fail" && after_or {
            E101_OR_FAIL.iter().map(|f| (*f).to_string()).collect()
        } else if keyword && t.text == "invariant" {
            E101_INVARIANT.iter().map(|f| (*f).to_string()).collect()
        } else if keyword {
            vec![format!(
                "'{}' is a keyword: it cannot be used as a value, and writing it as a \
                 call does not make it one",
                t.text
            )]
        } else {
            vec!["expected a number, string, variable, or function call".to_string()]
        };
        let fixes: Vec<&str> = fixes.iter().map(String::as_str).collect();
        SablineError::with_fixes("E101", format!("unexpected '{}'", t.text), t.line, &fixes)
    }
}

/// E101's fixes for the two keywords a model most put where a value goes
/// (evals/roundtrip, 8.7), most useful first: `agent_loop` shows a model
/// the first two. `sabline/parser.py` holds the same words.
const E101_OR_FAIL: [&str; 2] = [
    "to handle the failure here, write: check to_int(text) { ok n { ... } fail why { ... } }",
    "'or fail' goes only in a function's signature, after its return type - fn parse(text: \
     Text) -> Int or fail - and inside such a function try to_int(text) passes a failure up; \
     main cannot fail",
];
const E101_INVARIANT: [&str; 2] = [
    "'invariant' is a clause of a loop, written after the loop's header and before its '{': \
     while i < n invariant total >= 0 { ... }",
    "a promise about what a function returns is 'ensures', in its signature: fn f(n: Int) -> \
     Int ensures result >= 0 { ... }",
];

/// `int(text)` as decimal text, or `None` where CPython refuses to convert.
///
/// Every character is a Unicode decimal digit, because that is what the
/// lexer's `\d+` matched, and `int()` reads each by its decimal value.
fn int_text(text: &str) -> Option<String> {
    if text.chars().count() > INT_MAX_STR_DIGITS {
        return None;
    }
    let mut digits = String::with_capacity(text.len());
    for c in text.chars() {
        let value = decimal_value(c).expect("the lexer matched only decimal digits");
        digits.push(char::from(b'0' + value as u8));
    }
    let trimmed = digits.trim_start_matches('0');
    Some(if trimmed.is_empty() { "0".to_string() } else { trimmed.to_string() })
}

/// `float(text)` for a `\d+\.\d+` token.
fn float_of(text: &str) -> f64 {
    let mut ascii = String::with_capacity(text.len());
    for c in text.chars() {
        match decimal_value(c) {
            Some(value) => ascii.push(char::from(b'0' + value as u8)),
            None => ascii.push(c), // the one '.'
        }
    }
    // The token's shape is `\d+\.\d+`, so this always reads; a value past
    // the range of a double is `inf`, as CPython's `float()` gives.
    ascii.parse::<f64>().unwrap_or(f64::NAN)
}

// ---- the free-variable walk a function value does ---------------------------
//
// `parse_lambda` walks the body with `dataclasses.fields`, which visits a
// node's fields in declaration order, and calls `look` on each node before
// its children. `bound` is one flat set updated as the walk goes, not a
// scope: a `let` later in the body binds the name for everything visited
// after it, siblings included. Both of those decide what a closure captures
// and in what order, so both are copied exactly. The field orders below are
// `sabline/nodes.py`'s declaration orders.

fn visit_stmt(s: &Stmt, bound: &mut HashSet<String>, free: &mut Vec<String>) {
    match s {
        // Let: name, value, line, ann
        Stmt::Let { name, value, .. } => {
            bound.insert(name.clone());
            visit_expr(value, bound, free);
        }
        // Return: value, line
        Stmt::Return { value, .. } => {
            if let Some(v) = value {
                visit_expr(v, bound, free);
            }
        }
        // If: cond, then, other, line
        Stmt::If { cond, then, other, .. } => {
            visit_expr(cond, bound, free);
            for x in then {
                visit_stmt(x, bound, free);
            }
            for x in other {
                visit_stmt(x, bound, free);
            }
        }
        // While: cond, body, line, invariants
        Stmt::While { cond, body, invariants, .. } => {
            visit_expr(cond, bound, free);
            for x in body {
                visit_stmt(x, bound, free);
            }
            for (e, _) in invariants {
                visit_expr(e, bound, free);
            }
        }
        // Assign: name, value, line
        Stmt::Assign { name, value, .. } => {
            bound.insert(name.clone());
            visit_expr(value, bound, free);
        }
        // Block: stmts, line
        Stmt::Block { stmts, .. } => {
            for x in stmts {
                visit_stmt(x, bound, free);
            }
        }
        // ExprStmt: expr, line
        Stmt::ExprStmt { expr, .. } => visit_expr(expr, bound, free),
        // FailStmt: value, line
        Stmt::FailStmt { value, .. } => visit_expr(value, bound, free),
        // Check: subject, line, ok_name, ok_body, fail_name, fail_body.
        // `look` binds both names before the subject is walked, which is
        // what Python does because `look` runs before the fields.
        Stmt::Check { subject, ok_name, ok_body, fail_name, fail_body, .. } => {
            if let Some(n) = ok_name {
                bound.insert(n.clone());
            }
            bound.insert(fail_name.clone());
            visit_expr(subject, bound, free);
            for x in ok_body {
                visit_stmt(x, bound, free);
            }
            for x in fail_body {
                visit_stmt(x, bound, free);
            }
        }
    }
}

fn visit_expr(e: &Expr, bound: &mut HashSet<String>, free: &mut Vec<String>) {
    match e {
        // Var: name, line
        Expr::Var { name, .. } => {
            if !bound.contains(name) && !free.contains(name) {
                free.push(name.clone());
            }
        }
        // Neg: value, line
        Expr::Neg { value, .. } => visit_expr(value, bound, free),
        // Not: value, line
        Expr::Not { value, .. } => visit_expr(value, bound, free),
        // TryExpr: value, line
        Expr::TryExpr { value, .. } => visit_expr(value, bound, free),
        // BinOp: op, left, right, line
        Expr::BinOp { left, right, .. } => {
            visit_expr(left, bound, free);
            visit_expr(right, bound, free);
        }
        // Call: name, args, line
        Expr::Call { args, .. } => {
            for a in args {
                visit_expr(a, bound, free);
            }
        }
        // RecordLit: name, fields, line
        Expr::RecordLit { fields, .. } => {
            for (_, v) in fields {
                visit_expr(v, bound, free);
            }
        }
        // FieldGet: obj, field, line
        Expr::FieldGet { obj, .. } => visit_expr(obj, bound, free),
        // ListLit: items, line
        Expr::ListLit { items, .. } => {
            for i in items {
                visit_expr(i, bound, free);
            }
        }
        // MapLit: entries, line
        Expr::MapLit { entries, .. } => {
            for (k, v) in entries {
                visit_expr(k, bound, free);
                visit_expr(v, bound, free);
            }
        }
        // Closure: name, free, line - both are lists of text, and Python
        // walks neither into a node, so an inner function value's free
        // names do not become the outer one's.
        Expr::Closure { .. } => {}
        Expr::Num { .. } | Expr::FloatNum { .. } | Expr::Str { .. } | Expr::Bool { .. } => {}
    }
}

/// `name + 1`, the step a desugared `for` loop ends with.
fn plus_one(name: &str, line: u32) -> Expr {
    Expr::BinOp {
        op: "+".into(),
        left: Box::new(Expr::Var { name: name.to_string(), line }),
        right: Box::new(Expr::Num { value: "1".into() }),
        line,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lexer::lex;

    fn program(source: &str) -> Answer<Program> {
        Parser::new(lex(source, false)?).parse_program()
    }

    #[test]
    fn int_text_strips_leading_zeros_and_reads_other_digits() {
        assert_eq!(int_text("007").as_deref(), Some("7"));
        assert_eq!(int_text("000").as_deref(), Some("0"));
        assert_eq!(int_text("\u{661}\u{662}").as_deref(), Some("12"));
        assert_eq!(int_text(&"1".repeat(4300)).map(|s| s.len()), Some(4300));
        assert_eq!(int_text(&"1".repeat(4301)), None);
        assert_eq!(int_text(&"0".repeat(4301)), None);
    }

    #[test]
    fn a_for_range_becomes_a_while() {
        let p = program("fn main() { for i in 0 to 3 { } }").expect("parses");
        let body = &p.funcs[0].body;
        assert_eq!(body.len(), 2, "the Block is flattened into the body");
        assert!(matches!(body[0], Stmt::Let { .. }));
        match &body[1] {
            Stmt::While { body, .. } => assert_eq!(body.len(), 1, "just the step"),
            other => panic!("expected a While, got {other:?}"),
        }
    }

    #[test]
    fn a_function_value_is_lifted_before_the_function_that_holds_it() {
        let p = program("fn main() { let f = fn(x: Int) -> Int { return x + 1 } }")
            .expect("parses");
        assert_eq!(p.funcs.len(), 2);
        assert_eq!(p.funcs[0].name, "fn#1");
        assert!(p.funcs[0].is_lambda);
        assert_eq!(p.funcs[1].name, "main");
    }

    #[test]
    fn a_function_value_captures_what_it_reads_and_did_not_bind() {
        let p = program(
            "fn main() { let a = 1 let f = fn(x: Int) -> Int { let b = 2 return x + a + b + c } }",
        )
        .expect("parses");
        assert_eq!(p.funcs[0].free_names, vec!["a".to_string(), "c".to_string()]);
    }

    #[test]
    fn a_check_binds_both_arm_names_before_its_subject() {
        let p = program(
            "fn main() { let f = fn(x: Int) -> Int { check g(v) { ok v { } fail v { } } return x } }",
        )
        .expect("parses");
        assert!(
            p.funcs[0].free_names.is_empty(),
            "'v' is bound by the arms before the subject is walked: {:?}",
            p.funcs[0].free_names
        );
    }

    #[test]
    fn effects_are_sorted_because_python_holds_them_in_a_set() {
        let p = program("fn main() uses net, io, clock { }").expect("parses");
        assert_eq!(p.funcs[0].effects, vec!["clock", "io", "net"]);
    }

    // The depth caps have their own tests in `tests/limits.rs`, because
    // reaching one needs `on_parse_stack` and a test harness thread is
    // smaller than that.

    #[test]
    fn an_operator_chain_past_the_cap_is_e102() {
        let source = format!("fn main() {{ let x = 1{} }}", " + 1".repeat(1001));
        let refused = program(&source).expect_err("1,001 operators is too many");
        assert_eq!(refused.code, "E102");
        assert_eq!(refused.message, "this expression nests, or chains operators, too deeply");
    }

    #[test]
    fn a_record_write_is_e511() {
        let refused = program("fn main() { p.x = 1 }").expect_err("records do not change");
        assert_eq!(refused.code, "E511");
    }

    #[test]
    fn a_secret_of_a_secret_is_e562() {
        let refused = program("fn f(x: Secret of Secret of Text) { }")
            .expect_err("a Secret of a Secret is refused");
        assert_eq!(refused.code, "E562");
        assert_eq!(
            refused.message,
            "a Secret of a Secret is the same secret; write Secret of Text"
        );
    }
}
