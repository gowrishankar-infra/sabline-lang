//! Any bytes at all, through the front of sabline-rt.
//!
//! The assertion is not about what comes out. It is that something comes
//! out: plan/9.0.md's rule is that no panic in sabline-rt is ever
//! acceptable and every malformed input is a coded error, so reaching the
//! end of this function is the property. libFuzzer catches a panic, an
//! abort and a timeout by itself.
//!
//! The bytes go through `decode` first, which is where a sequence that is
//! not UTF-8, a byte-order mark and a lone carriage return are decided -
//! the same front door a file goes through.

#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    match sabline_rt::source::decode(data, "fuzz.vel") {
        Err(refused) => {
            assert_eq!(refused.code, "E512", "the only refusal decoding gives");
        }
        Ok(text) => {
            // The depth caps let a program nest deeper than this thread's
            // stack carries, so the parse runs where the library says it
            // must. A fuzzer that overflowed the stack would be reporting
            // the fuzzer's stack and not a defect.
            let answer = sabline_rt::on_parse_stack(move || {
                sabline_rt::lex(&text, false)
                    .and_then(|tokens| sabline_rt::Parser::new(tokens).parse_program())
                    .map_err(|e| e.code)
            });
            if let Err(code) = answer {
                assert!(code.starts_with('E'), "a coded error, not {code}");
            }
        }
    }
});
