//! Every Unicode decimal digit, generated from CPython's own
//! `\d`. Do not edit by hand: scripts/gen_unicode_nd.py writes it.
//!
//! `\d` in a `str` pattern is category Nd, which is what the
//! Python lexer's NUMBER and FLOAT patterns match, and `int()` and
//! `float()` read each of them by its decimal value. Each range
//! here is ten code points and a digit's value is its distance from
//! the start of its range; the generator refuses to write a table
//! where that is not true.
//!
//! Unicode 15.1.0, from CPython 3.13.13.

/// The Unicode version this table was generated from.
pub const UNICODE_VERSION: &str = "15.1.0";

/// The first code point of each run of ten decimal digits.
pub const DIGIT_RUNS: [u32; 68] = [
    0x0030, 0x0660, 0x06F0, 0x07C0, 0x0966, 0x09E6, 0x0A66, 0x0AE6, 0x0B66, 0x0BE6, 0x0C66,
    0x0CE6, 0x0D66, 0x0DE6, 0x0E50, 0x0ED0, 0x0F20, 0x1040, 0x1090, 0x17E0, 0x1810, 0x1946,
    0x19D0, 0x1A80, 0x1A90, 0x1B50, 0x1BB0, 0x1C40, 0x1C50, 0xA620, 0xA8D0, 0xA900, 0xA9D0,
    0xA9F0, 0xAA50, 0xABF0, 0xFF10, 0x104A0, 0x10D30, 0x11066, 0x110F0, 0x11136, 0x111D0,
    0x112F0, 0x11450, 0x114D0, 0x11650, 0x116C0, 0x11730, 0x118E0, 0x11950, 0x11C50, 0x11D50,
    0x11DA0, 0x11F50, 0x16A60, 0x16AC0, 0x16B50, 0x1D7CE, 0x1D7D8, 0x1D7E2, 0x1D7EC, 0x1D7F6,
    0x1E140, 0x1E2F0, 0x1E4F0, 0x1E950, 0x1FBF0,
];

/// The digit's value when `c` is a Unicode decimal digit.
pub fn decimal_value(c: char) -> Option<u32> {
    let cp = c as u32;
    match DIGIT_RUNS.binary_search(&cp) {
        Ok(_) => Some(0),
        Err(0) => None,
        Err(i) => {
            let start = DIGIT_RUNS[i - 1];
            if cp - start <= 9 {
                Some(cp - start)
            } else {
                None
            }
        }
    }
}

/// Whether `c` is what the Python lexer's `\d` matches.
pub fn is_digit(c: char) -> bool {
    decimal_value(c).is_some()
}
