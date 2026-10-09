//! What a run reaches of the machine it runs on, as CPython reaches it:
//! the environment as `os.environ` holds it, `~` as `os.path.expanduser`
//! finds it, randomness as `random.Random` makes it, a file read as
//! `open(path, encoding="utf-8").read()` reads it and written as
//! `open(path, "w", encoding="utf-8")` writes it, and an operating
//! system's refusal in the words `OSError.strerror` gives it (9.0, M3).
//!
//! Each is here because the reference's behaviour is CPython's, and a
//! program can see it: `env("PATH", "")` on Windows finds `Path`, because
//! `os.environ` upper-cases every name; a file holding `a\r\nb` reads as
//! `a\nb`; `random(6)` under `--seed 1` is the number Python's Mersenne
//! Twister gives, and the next one too.

use std::collections::HashMap;

use crate::text::{Text, TextBuf};

// ---- the environment ---------------------------------------------------------

/// `os.environ`: every variable the process started with, by name, as the
/// `os` module builds it - on Windows each name upper-cased (`encodekey`),
/// the last of two names that upper-case alike winning, and none of the
/// hidden `=C:` variables, which the C runtime's own copy leaves out; on
/// every other system each name and value decoded from bytes as
/// `os.fsdecode` does, UTF-8 with `surrogateescape`, the first of two
/// equal names winning.
#[derive(Debug, Clone, Default)]
pub struct Environ(HashMap<Text, Text>);

impl Environ {
    /// The process's environment, now.
    pub fn of_process() -> Environ {
        let mut out: HashMap<Text, Text> = HashMap::new();
        for (k, v) in std::env::vars_os() {
            #[cfg(windows)]
            {
                use std::os::windows::ffi::OsStrExt;
                let key: Vec<u16> = k.encode_wide().collect();
                if key.first() == Some(&u16::from(b'=')) {
                    continue;
                }
                let key = utf16_text(&key).upper();
                let value: Vec<u16> = v.encode_wide().collect();
                out.insert(key, utf16_text(&value));
            }
            #[cfg(not(windows))]
            {
                use std::os::unix::ffi::OsStrExt;
                let (raw_k, raw_v) = (k.as_bytes(), v.as_bytes());
                // CPython takes the name up to the first '=' of the
                // variable's text, and Rust has already split it at the
                // first '=' after the first character
                let (key, value) = if raw_k.first() == Some(&b'=') {
                    let mut rest = raw_k[1..].to_vec();
                    rest.push(b'=');
                    rest.extend_from_slice(raw_v);
                    (Vec::new(), rest)
                } else {
                    (raw_k.to_vec(), raw_v.to_vec())
                };
                out.entry(fsdecode(&key)).or_insert_with(|| fsdecode(&value));
            }
        }
        Environ(out)
    }

    /// `os.environ[name] = value`.
    pub fn set(&mut self, name: &str, value: &str) {
        let key = Text::from(name);
        let key = if cfg!(windows) { key.upper() } else { key };
        self.0.insert(key, Text::from(value));
    }

    /// `os.environ.get(name)`.
    pub fn get(&self, name: &Text) -> Option<&Text> {
        if cfg!(windows) {
            self.0.get(&name.upper())
        } else {
            self.0.get(name)
        }
    }

    /// `name in os.environ`.
    pub fn has(&self, name: &str) -> bool {
        self.get(&Text::from(name)).is_some()
    }
}

/// UTF-16 as code points, a lone surrogate kept as itself: what
/// `PyUnicode_FromWideChar` makes of a Windows string.
#[cfg_attr(not(windows), allow(dead_code))]
fn utf16_text(units: &[u16]) -> Text {
    let points: Vec<u32> = char::decode_utf16(units.iter().copied())
        .map(|r| match r {
            Ok(c) => c as u32,
            Err(e) => u32::from(e.unpaired_surrogate()),
        })
        .collect();
    Text::from(points)
}

/// `os.fsdecode(raw)`: UTF-8, each byte that is not part of a character
/// written as U+DC80 + the byte (`surrogateescape`).
pub fn fsdecode(raw: &[u8]) -> Text {
    let mut out: Vec<u32> = Vec::with_capacity(raw.len());
    let mut rest = raw;
    while !rest.is_empty() {
        match std::str::from_utf8(rest) {
            Ok(s) => {
                out.extend(s.chars().map(|c| c as u32));
                break;
            }
            Err(e) => {
                let good = e.valid_up_to();
                out.extend(
                    std::str::from_utf8(&rest[..good]).unwrap_or("").chars().map(|c| c as u32),
                );
                let bad = e.error_len().unwrap_or(rest.len() - good);
                out.extend(rest[good..good + bad].iter().map(|&b| 0xDC00 + u32::from(b)));
                rest = &rest[good + bad..];
            }
        }
    }
    Text::from(out)
}

/// `os.path.expanduser("~")` with `os.environ` as `environ`: on Windows
/// `USERPROFILE`, else `HOMEDRIVE` joined to `HOMEPATH`, else `~` itself;
/// elsewhere `HOME`, else the password database's entry, with every
/// trailing `/` taken off (and `/` for one that is nothing else).
pub fn home(environ: &Environ) -> Option<String> {
    let var = |n: &str| environ.get(&Text::from(n)).and_then(Text::to_str);
    if cfg!(windows) {
        if environ.has("USERPROFILE") {
            return var("USERPROFILE");
        }
        if !environ.has("HOMEPATH") {
            return Some("~".to_string());
        }
        let drive = var("HOMEDRIVE").unwrap_or_default();
        return Some(crate::pypath::nt::join(&drive, &var("HOMEPATH")?));
    }
    #[allow(deprecated)]
    let found = if environ.has("HOME") {
        var("HOME")?
    } else {
        std::env::home_dir()?.to_string_lossy().into_owned()
    };
    let kept = found.trim_end_matches('/');
    Some(if kept.is_empty() { "/".to_string() } else { kept.to_string() })
}

// ---- randomness ----------------------------------------------------------------

const N: usize = 624;
const M: usize = 397;

/// `random.Random`: CPython's Mersenne Twister (`_randommodule.c`), seeded
/// as `random.Random(seed)` seeds it.
#[derive(Clone)]
pub struct Twister {
    mt: [u32; N],
    index: usize,
}

impl std::fmt::Debug for Twister {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "Twister({})", self.index)
    }
}

impl Twister {
    fn init_genrand(s: u32) -> Twister {
        let mut mt = [0u32; N];
        mt[0] = s;
        for i in 1..N {
            mt[i] = 1_812_433_253u32
                .wrapping_mul(mt[i - 1] ^ (mt[i - 1] >> 30))
                .wrapping_add(i as u32);
        }
        Twister { mt, index: N }
    }

    /// `init_by_array(key)`.
    fn by_array(key: &[u32]) -> Twister {
        let mut t = Twister::init_genrand(19_650_218);
        let mt = &mut t.mt;
        let (mut i, mut j) = (1usize, 0usize);
        let mut k = N.max(key.len());
        while k > 0 {
            mt[i] = (mt[i] ^ (mt[i - 1] ^ (mt[i - 1] >> 30)).wrapping_mul(1_664_525))
                .wrapping_add(key[j])
                .wrapping_add(j as u32);
            i += 1;
            j += 1;
            if i >= N {
                mt[0] = mt[N - 1];
                i = 1;
            }
            if j >= key.len() {
                j = 0;
            }
            k -= 1;
        }
        k = N - 1;
        while k > 0 {
            mt[i] = (mt[i] ^ (mt[i - 1] ^ (mt[i - 1] >> 30)).wrapping_mul(1_566_083_941))
                .wrapping_sub(i as u32);
            i += 1;
            if i >= N {
                mt[0] = mt[N - 1];
                i = 1;
            }
            k -= 1;
        }
        mt[0] = 0x8000_0000;
        t
    }

    /// `random.Random(seed)` for a whole number: its absolute value, as
    /// 32-bit words from the least significant, at least one.
    pub fn seeded(seed: i128) -> Twister {
        let mut n = seed.unsigned_abs();
        let mut key = Vec::new();
        while n > 0 {
            key.push(n as u32);
            n >>= 32;
        }
        if key.is_empty() {
            key.push(0);
        }
        Twister::by_array(&key)
    }

    /// A generator seeded from the operating system's randomness, as the
    /// `random` module's own instance is: what `random(n)` uses without
    /// `--seed`.
    pub fn unseeded() -> Twister {
        use std::hash::{BuildHasher, Hasher};
        let mut words = Vec::new();
        for _ in 0..4 {
            let mut h = std::collections::hash_map::RandomState::new().build_hasher();
            h.write_u64(words.len() as u64);
            let v = h.finish();
            words.push(v as u32);
            words.push((v >> 32) as u32);
        }
        Twister::by_array(&words)
    }

    /// `genrand_uint32`.
    fn next_u32(&mut self) -> u32 {
        const UPPER: u32 = 0x8000_0000;
        const LOWER: u32 = 0x7FFF_FFFF;
        const MATRIX: u32 = 0x9908_B0DF;
        if self.index >= N {
            let mt = &mut self.mt;
            for kk in 0..N {
                let y = (mt[kk] & UPPER) | (mt[(kk + 1) % N] & LOWER);
                let mag = if y & 1 == 0 { 0 } else { MATRIX };
                mt[kk] = mt[(kk + M) % N] ^ (y >> 1) ^ mag;
            }
            self.index = 0;
        }
        let mut y = self.mt[self.index];
        self.index += 1;
        y ^= y >> 11;
        y ^= (y << 7) & 0x9D2C_5680;
        y ^= (y << 15) & 0xEFC6_0000;
        y ^ (y >> 18)
    }

    /// `getrandbits(k)` for `0 < k <= 64`: whole words from the least
    /// significant, the last one shifted down to what is left of `k`.
    fn getrandbits(&mut self, k: u32) -> u64 {
        if k <= 32 {
            return u64::from(self.next_u32() >> (32 - k));
        }
        let low = u64::from(self.next_u32());
        let high = u64::from(self.next_u32() >> (64 - k));
        low | (high << 32)
    }

    /// `randrange(n)` for `n > 0`: `_randbelow_with_getrandbits(n)`.
    pub fn randrange(&mut self, n: u64) -> u64 {
        let k = 64 - n.leading_zeros();
        let mut r = self.getrandbits(k);
        while r >= n {
            r = self.getrandbits(k);
        }
        r
    }
}

// ---- files -----------------------------------------------------------------------

/// `open(path, encoding="utf-8").read()` of a file's bytes: UTF-8, strictly,
/// so `None` where CPython raises `UnicodeDecodeError`; and every line end
/// (`\r\n`, and `\r` alone) read as `\n`, which is universal newlines.
pub fn read_text(raw: &[u8]) -> Option<Text> {
    let s = std::str::from_utf8(raw).ok()?;
    let mut out = TextBuf::new();
    let mut chars = s.chars().peekable();
    let mut held = String::new();
    while let Some(c) = chars.next() {
        if c == '\r' {
            if chars.peek() == Some(&'\n') {
                chars.next();
            }
            held.push('\n');
        } else {
            held.push(c);
        }
    }
    out.push_str(&held);
    Some(out.done())
}

/// What `open(path, "w", encoding="utf-8").write(text)` puts in the file:
/// each `\n` as this system's line end (`\r\n` on Windows), as UTF-8 -
/// `None` for a text holding a lone surrogate, which is not UTF-8, and
/// which `write_file` refuses (E608) before it opens the file.
pub fn written_bytes(text: &Text) -> Option<Vec<u8>> {
    let s = text.to_str()?;
    Some(if cfg!(windows) { s.replace('\n', "\r\n").into_bytes() } else { s.into_bytes() })
}

/// `OSError.strerror` of an operating system's refusal to open a file, as
/// CPython's `open` gives it: on Windows the C runtime's `errno` for the
/// system's error (`_dosmaperr`) and its text for that number; elsewhere
/// the C library's `strerror`, which is what Rust's own message for the
/// error begins with.
pub fn strerror(e: &std::io::Error) -> String {
    let Some(code) = e.raw_os_error() else { return e.to_string() };
    if cfg!(windows) {
        return crt_strerror(dosmaperr(code)).to_string();
    }
    let shown = std::io::Error::from_raw_os_error(code).to_string();
    match shown.rfind(" (os error ") {
        Some(at) => shown[..at].to_string(),
        None => shown,
    }
}

/// The C runtime's `_dosmaperr`: a Windows error code as an `errno`.
fn dosmaperr(code: i32) -> i32 {
    const ENOENT: i32 = 2;
    const EACCES: i32 = 13;
    const EINVAL: i32 = 22;
    match code {
        1 | 12 | 13 | 87 | 131 => EINVAL,
        2 | 3 | 15 | 18 | 53 | 67 | 161 | 206 => ENOENT,
        4 => 24, // EMFILE
        5 | 16 | 33 | 65 | 82 | 83 | 108 | 132 | 158 | 167 => EACCES,
        6 | 114 | 130 => 9,  // EBADF
        7..=9 | 1816 => 12,  // ENOMEM
        10 => 7,             // E2BIG
        11 | 188..=202 => 8, // ENOEXEC
        17 => 18,            // EXDEV
        19..=36 => EACCES,
        80 | 183 => 17,       // EEXIST
        89 | 164 | 215 => 11, // EAGAIN
        109 => 32,            // EPIPE
        112 => 28,            // ENOSPC
        128 | 129 => 10,      // ECHILD
        145 => 41,            // ENOTEMPTY
        _ => EINVAL,
    }
}

/// The C runtime's text for an `errno` (`_sys_errlist`).
fn crt_strerror(errno: i32) -> &'static str {
    match errno {
        1 => "Operation not permitted",
        2 => "No such file or directory",
        3 => "No such process",
        4 => "Interrupted function call",
        5 => "Input/output error",
        6 => "No such device or address",
        7 => "Arg list too long",
        8 => "Exec format error",
        9 => "Bad file descriptor",
        10 => "No child processes",
        11 => "Resource temporarily unavailable",
        12 => "Not enough space",
        13 => "Permission denied",
        14 => "Bad address",
        16 => "Resource device",
        17 => "File exists",
        18 => "Improper link",
        19 => "No such device",
        20 => "Not a directory",
        21 => "Is a directory",
        22 => "Invalid argument",
        23 => "Too many open files in system",
        24 => "Too many open files",
        25 => "Inappropriate I/O control operation",
        27 => "File too large",
        28 => "No space left on device",
        29 => "Invalid seek",
        30 => "Read-only file system",
        31 => "Too many links",
        32 => "Broken pipe",
        33 => "Domain error",
        34 => "Result too large",
        36 => "Resource deadlock avoided",
        38 => "Filename too long",
        39 => "No locks available",
        40 => "Function not implemented",
        41 => "Directory not empty",
        42 => "Illegal byte sequence",
        _ => "Unknown error",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_twister_is_cpythons() {
        // [random.Random(s).randrange(n) for ...], from CPython 3.13
        let draws = |seed: i128, n: u64, k: usize| {
            let mut t = Twister::seeded(seed);
            (0..k).map(|_| t.randrange(n)).collect::<Vec<u64>>()
        };
        assert_eq!(draws(1, 6, 6), vec![1, 4, 0, 2, 0, 3]);
        assert_eq!(draws(42, 100, 4), vec![81, 14, 3, 94]);
        assert_eq!(draws(0, 1 << 40, 1), vec![849_735_321_549]);
        assert_eq!(
            draws(-7, 1_000_000_000_000_000_000, 3),
            vec![455_200_494_606_748_983, 55_670_462_648_394_832, 946_864_788_125_462_323]
        );
        assert_eq!(draws((1 << 70) + 5, 1000, 3), vec![478, 399, 486]);
        assert_eq!(
            draws(9_223_372_036_854_775_807, 9_223_372_036_854_775_807, 3),
            vec![
                6_055_593_706_181_862_303,
                1_223_804_479_340_164_555,
                4_528_097_776_385_768_228
            ]
        );
    }

    #[test]
    fn a_file_reads_with_universal_newlines() {
        assert_eq!(read_text(b"a\r\nb\rc\n"), Some(Text::from("a\nb\nc\n")));
        assert_eq!(read_text(b"\xef\xbb\xbfx"), Some(Text::from("\u{feff}x")));
        assert_eq!(read_text(b"\xff"), None);
        assert_eq!(read_text(b"\xed\xa0\x80"), None);
    }

    #[test]
    fn fsdecode_escapes_what_is_not_utf8() {
        assert_eq!(fsdecode(b"a\xffb"), Text::from(vec![0x61, 0xDCFF, 0x62]));
        assert_eq!(fsdecode("\u{e9}".as_bytes()), Text::from("\u{e9}"));
    }

    #[test]
    fn windows_errors_read_as_the_c_runtime_says() {
        assert_eq!(crt_strerror(dosmaperr(2)), "No such file or directory");
        assert_eq!(crt_strerror(dosmaperr(3)), "No such file or directory");
        assert_eq!(crt_strerror(dosmaperr(5)), "Permission denied");
        assert_eq!(crt_strerror(dosmaperr(123)), "Invalid argument");
    }
}
