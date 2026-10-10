//! `sha256`, the four encoders and `url_encode`: what `sabline/runtime.py`'s
//! `run_digest` does with `hashlib`, `base64`, `binascii` and
//! `urllib.parse`.
//!
//! Each works on a Text's bytes as `_utf8` makes them -
//! `str(text).encode("utf-8", "surrogatepass")` - so a lone surrogate is
//! its three bytes rather than an error; and each decoder answers what
//! CPython answers for the same text, which for `base64_decode` is
//! `b64decode(..., validate=True)` and for `hex_decode` `bytes.fromhex`
//! after the runtime's own refusal of white space and anything past
//! ASCII. SHA-256 is written here (FIPS 180-4) rather than taken from a
//! crate: the crate has no dependencies, and a hash is forty lines.

use crate::text::Text;

/// `text.encode("utf-8", "surrogatepass")`.
pub fn utf8_surrogatepass(t: &Text) -> Vec<u8> {
    let mut out = Vec::with_capacity(t.len());
    for &c in t.points() {
        match c {
            0..=0x7F => out.push(c as u8),
            0x80..=0x7FF => {
                out.push(0xC0 | (c >> 6) as u8);
                out.push(0x80 | (c & 0x3F) as u8);
            }
            0x800..=0xFFFF => {
                out.push(0xE0 | (c >> 12) as u8);
                out.push(0x80 | ((c >> 6) & 0x3F) as u8);
                out.push(0x80 | (c & 0x3F) as u8);
            }
            _ => {
                out.push(0xF0 | (c >> 18) as u8);
                out.push(0x80 | ((c >> 12) & 0x3F) as u8);
                out.push(0x80 | ((c >> 6) & 0x3F) as u8);
                out.push(0x80 | (c & 0x3F) as u8);
            }
        }
    }
    out
}

/// `bytes.decode("utf-8")`, strictly: `None` for its `UnicodeDecodeError`.
pub fn utf8_strict(bytes: &[u8]) -> Option<Text> {
    std::str::from_utf8(bytes).ok().map(Text::from)
}

const K: [u32; 64] = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
    0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
    0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
    0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
    0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
    0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
    0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
    0xc67178f2,
];

/// `hmac.new(key, message, hashlib.sha256).digest()`: RFC 2104 over
/// SHA-256, a key longer than the 64-byte block hashed first.
pub fn hmac_sha256(key: &[u8], message: &[u8]) -> [u8; 32] {
    let mut block = [0u8; 64];
    if key.len() > 64 {
        block[..32].copy_from_slice(&sha256(key));
    } else {
        block[..key.len()].copy_from_slice(key);
    }
    let mut inner: Vec<u8> = block.iter().map(|b| b ^ 0x36).collect();
    inner.extend_from_slice(message);
    let mut outer: Vec<u8> = block.iter().map(|b| b ^ 0x5c).collect();
    outer.extend_from_slice(&sha256(&inner));
    sha256(&outer)
}

/// SHA-256 of `data`.
pub fn sha256(data: &[u8]) -> [u8; 32] {
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
    ];
    let mut msg = data.to_vec();
    let bit_len = (data.len() as u64).wrapping_mul(8);
    msg.push(0x80);
    while msg.len() % 64 != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bit_len.to_be_bytes());
    for block in msg.chunks(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([
                block[4 * i],
                block[4 * i + 1],
                block[4 * i + 2],
                block[4 * i + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }
        let [mut a, mut b, mut c, mut d, mut e, mut f, mut g, mut hh] = h;
        for i in 0..64 {
            let s1 = e.rotate_right(6) ^ e.rotate_right(11) ^ e.rotate_right(25);
            let ch = (e & f) ^ (!e & g);
            let t1 =
                hh.wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = a.rotate_right(2) ^ a.rotate_right(13) ^ a.rotate_right(22);
            let maj = (a & b) ^ (a & c) ^ (b & c);
            let t2 = s0.wrapping_add(maj);
            hh = g;
            g = f;
            f = e;
            e = d.wrapping_add(t1);
            d = c;
            c = b;
            b = a;
            a = t1.wrapping_add(t2);
        }
        for (slot, v) in h.iter_mut().zip([a, b, c, d, e, f, g, hh]) {
            *slot = slot.wrapping_add(v);
        }
    }
    let mut out = [0u8; 32];
    for (i, v) in h.iter().enumerate() {
        out[4 * i..4 * i + 4].copy_from_slice(&v.to_be_bytes());
    }
    out
}

/// Lowercase hexadecimal, `bytes.hex()`.
pub fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// `bytes.fromhex(text)` for a text of ASCII with no white space in it:
/// pairs of hexadecimal digits, `None` for its `ValueError`.
pub fn from_hex(t: &Text) -> Option<Vec<u8>> {
    let p = t.points();
    if p.len() % 2 != 0 {
        return None;
    }
    p.chunks(2)
        .map(|pair| {
            let hi = char::from_u32(pair[0])?.to_digit(16)?;
            let lo = char::from_u32(pair[1])?.to_digit(16)?;
            Some((hi * 16 + lo) as u8)
        })
        .collect()
}

const B64: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// `base64.b64encode(bytes).decode("ascii")`.
pub fn b64encode(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for chunk in bytes.chunks(3) {
        let n = (u32::from(chunk[0]) << 16)
            | (u32::from(*chunk.get(1).unwrap_or(&0)) << 8)
            | u32::from(*chunk.get(2).unwrap_or(&0));
        out.push(B64[(n >> 18) as usize & 63] as char);
        out.push(B64[(n >> 12) as usize & 63] as char);
        out.push(if chunk.len() > 1 { B64[(n >> 6) as usize & 63] as char } else { '=' });
        out.push(if chunk.len() > 2 { B64[n as usize & 63] as char } else { '=' });
    }
    out
}

/// `base64.b64decode(text.encode("ascii"), validate=True)`: `None` for
/// the `UnicodeEncodeError` of a character past ASCII and for the
/// `binascii.Error` of anything else it refuses.
///
/// From CPython 3.11, `validate=True` is `a2b_base64`'s strict mode, and
/// this is that: the alphabet and nothing else, a quad of data characters
/// at a time, padding only where it completes a quad - not at the start
/// of one, and nothing after it - and no data character left over. CPython
/// 3.10 read the same text without strict mode and passed over padding at
/// the start of a quad (`"YWJj=="`, `"="`); the reference takes only what
/// strict mode takes on every CPython (`runtime._BASE64`, 9.0 M3).
pub fn b64decode_validated(t: &Text) -> Option<Vec<u8>> {
    let p = t.points();
    let mut out = Vec::with_capacity(p.len() * 3 / 4);
    let (mut quad, mut left, mut pads) = (0u32, 0u32, 0usize);
    let mut padding = false;
    for (i, &c) in p.iter().enumerate() {
        if c == 0x3D {
            padding = true;
            if quad == 0 {
                return None; // leading, or excess, padding
            }
            pads += 1;
            if quad >= 2 && quad as usize + pads >= 4 {
                if i + 1 < p.len() {
                    return None; // data after the padding
                }
                return Some(out);
            }
            continue;
        }
        let ch = u8::try_from(c).ok()?;
        let v = B64.iter().position(|&b| b == ch)? as u32;
        if padding {
            return None; // padding with data after it
        }
        pads = 0;
        match quad {
            0 => {
                left = v;
                quad = 1;
            }
            1 => {
                out.push(((left << 2) | (v >> 4)) as u8);
                left = v & 0x0F;
                quad = 2;
            }
            2 => {
                out.push(((left << 4) | (v >> 2)) as u8);
                left = v & 0x03;
                quad = 3;
            }
            _ => {
                out.push(((left << 6) | v) as u8);
                quad = 0;
            }
        }
    }
    (quad == 0).then_some(out)
}

/// `urllib.parse.quote(bytes, safe="-_.~")`: every byte but an ASCII
/// letter, a digit and `_.-~` as `%XX`, in capitals.
pub fn url_quote(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len());
    for &b in bytes {
        if b.is_ascii_alphanumeric() || matches!(b, b'_' | b'.' | b'-' | b'~') {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn hmac_sha256_is_rfc_4231() {
        // test cases 2 and 6: a short key, and one longer than the block
        assert_eq!(
            hex(&hmac_sha256(b"Jefe", b"what do ya want for nothing?")),
            "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"
        );
        assert_eq!(
            hex(&hmac_sha256(
                &[0xaa; 131],
                b"Test Using Larger Than Block-Size Key - Hash Key First"
            )),
            "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54"
        );
    }

    #[test]
    fn sha256_is_fips_180_4() {
        assert_eq!(
            hex(&sha256(b"")),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        );
        assert_eq!(
            hex(&sha256(b"abc")),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
        let long = vec![b'a'; 1000];
        assert_eq!(
            hex(&sha256(&long)),
            "41edece42d63e8d9bf515a9ba6932e1c20cbc9f5a5d134645adb5db1b9737ea3"
        );
    }

    #[test]
    fn base64_reads_as_cpython_does() {
        let t = |s: &str| Text::from(s);
        assert_eq!(b64encode(b"ab"), "YWI=");
        assert_eq!(b64decode_validated(&t("YWI=")), Some(b"ab".to_vec()));
        assert_eq!(b64decode_validated(&t("YWJj==")), None);
        assert_eq!(b64decode_validated(&t("YWJj")), Some(b"abc".to_vec()));
        assert_eq!(b64decode_validated(&t("Zg==Zg==")), None);
        assert_eq!(b64decode_validated(&t("YW=Jj")), None);
        assert_eq!(b64decode_validated(&t("YQ")), None);
        assert_eq!(b64decode_validated(&t("YQ=")), None);
        assert_eq!(b64decode_validated(&t("Y")), None);
        assert_eq!(b64decode_validated(&t("YQ===")), None);
        assert_eq!(b64decode_validated(&t("Y Q==")), None);
        assert_eq!(b64decode_validated(&t("=")), None);
        assert_eq!(url_quote("a b/é~".as_bytes()), "a%20b%2F%C3%A9~");
        assert_eq!(utf8_surrogatepass(&Text::from(vec![0xD800])), vec![0xED, 0xA0, 0x80]);
    }
}
