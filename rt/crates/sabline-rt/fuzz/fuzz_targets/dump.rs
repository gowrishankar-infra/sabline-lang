//! Any bytes at all, all the way to the canonical dump.
//!
//! The dump is the surface the agreement gate compares, so it is fuzzed
//! as well as the parser: a tree that builds and a document that cannot be
//! written would make the gate fall over rather than disagree. Writing the
//! document is the property, and the document is ASCII by construction, so
//! that is asserted too.

#![no_main]

use libfuzzer_sys::fuzz_target;

fuzz_target!(|data: &[u8]| {
    let bytes = data.to_vec();
    let text = sabline_rt::on_parse_stack(move || {
        sabline_rt::dump_bytes(&bytes, "fuzz.vel").canonical()
    });
    assert!(text.is_ascii(), "the canonical dump is ASCII");
    assert!(text.starts_with('{'), "the dump is one object");
});
