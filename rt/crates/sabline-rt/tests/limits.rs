//! The depth caps, and the stack they need.
//!
//! Three things are held here, and the third is the one that would
//! otherwise be an assumption:
//!
//! 1. The deepest program the parser **accepts** parses.
//! 2. One level deeper is E102, with the reference's message.
//! 3. Both of those happen on `sabline_rt::PARSE_STACK` and not on a
//!    stack chosen by the test, so the number the library publishes is
//!    the number that was measured.
//!
//! A stack overflow ends the process without running any other test, so a
//! failure here reads as the whole test binary dying. That is the point:
//! there is no way to overflow the stack quietly.

use sabline_rt::{lex, on_parse_stack, Parser, SablineError};

fn parse(source: String) -> Result<usize, SablineError> {
    on_parse_stack(move || {
        let tokens = lex(&source, false)?;
        Parser::new(tokens).parse_program().map(|p| p.funcs.len())
    })
}

fn blocks(depth: usize) -> String {
    format!("fn main() {{{}{}}}", "if true {".repeat(depth), "}".repeat(depth))
}

#[test]
fn the_deepest_accepted_block_nesting_parses() {
    // The function's own body is a block, so 3,999 `if`s inside it is
    // 4,000 blocks, which is the cap exactly.
    assert_eq!(parse(blocks(3999)).expect("3,999 parses"), 1);
}

#[test]
fn one_block_deeper_is_e102() {
    let refused = parse(blocks(4000)).expect_err("4,000 does not parse");
    assert_eq!(refused.code, "E102");
    assert_eq!(
        refused.message,
        "blocks nest more than 4000 deep here (an 'if', 'while', 'for' or \
         'else if' inside another)"
    );
    assert_eq!(refused.line, 1);
}

#[test]
fn an_else_if_chain_counts_as_nesting() {
    let chain = "if true { } else ".repeat(4000);
    let refused = parse(format!("fn main() {{ {chain}if true {{ }} }}"))
        .expect_err("an else-if chain nests as blocks do");
    assert_eq!(refused.code, "E102");
    assert!(refused.message.starts_with("blocks nest more than 4000 deep"));
}

#[test]
fn the_deepest_accepted_expression_nesting_parses() {
    let open = "(".repeat(999);
    let close = ")".repeat(999);
    parse(format!("fn main() {{ let x = {open}1{close} }}")).expect("999 parses");
}

#[test]
fn one_expression_deeper_is_e102() {
    // 999 brackets put the innermost atom at depth 1,000, which is the
    // cap exactly; 1,000 brackets put it at 1,001.
    let open = "(".repeat(1000);
    let close = ")".repeat(1000);
    let refused =
        parse(format!("fn main() {{ let x = {open}1{close} }}")).expect_err("past the cap");
    assert_eq!(refused.code, "E102");
    assert_eq!(refused.message, "this expression nests, or chains operators, too deeply");
}

#[test]
fn a_long_operator_chain_is_e102_and_not_a_deep_tree() {
    let chain = " + 1".repeat(1001);
    let refused =
        parse(format!("fn main() {{ let x = 1{chain} }}")).expect_err("past the cap");
    assert_eq!(refused.code, "E102");
    assert_eq!(refused.message, "this expression nests, or chains operators, too deeply");
    // One under the cap is a tree 1,000 deep on the left, which is built
    // and then dropped - and dropping it is as recursive as building it.
    let chain = " + 1".repeat(1000);
    parse(format!("fn main() {{ let x = 1{chain} }}")).expect("1,000 parses");
}

#[test]
fn nine_hundred_and_ninety_nine_unary_nots_parse_and_a_thousand_do_not() {
    // Each `not` is one level and the atom under them is one more, so 999
    // reaches the cap exactly and 1,000 passes it.
    let nots = "not ".repeat(999);
    parse(format!("fn main() {{ let x = {nots}true }}")).expect("999 parses");
    let nots = "not ".repeat(1000);
    let refused =
        parse(format!("fn main() {{ let x = {nots}true }}")).expect_err("past the cap");
    assert_eq!(refused.code, "E102");
}

#[test]
fn the_stack_the_library_publishes_is_the_one_the_caps_need() {
    // The deepest accepted program of each kind, one after another on one
    // thread, so a level that costs more than it did is an overflow here
    // rather than in something that matters.
    const { assert!(sabline_rt::PARSE_STACK >= 32 * 1024 * 1024) };
    parse(blocks(3999)).expect("blocks");
    let open = "[".repeat(999);
    let close = "]".repeat(999);
    parse(format!("fn main() {{ let x = {open}{close} }}")).expect("brackets");
}
