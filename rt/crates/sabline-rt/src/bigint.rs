//! A whole number of any size: what CPython's `int` is, for the few
//! values of a run that are not 64-bit.
//!
//! A run's whole numbers are 64-bit - every `+`, `-`, `*` and `/` is
//! checked, and E407 is the answer past the range - but the check is on
//! the *result*, so the operands can be larger: a literal is read with
//! `int()` and is not checked at all (`print(99999999999999999999)`
//! prints it, and `x - x` of it is 0), and `%` is not checked, so
//! `-7 % 99999999999999999999` is a number past 64 bits that prints. The
//! reference gets this from Python's integers; here it is this type,
//! which the interpreter uses only for a value outside `i64`.
//!
//! Sign and magnitude, the magnitude in base 2^32, least significant limb
//! first, with no leading zero limb; zero is no limbs and not negative.

use std::cmp::Ordering;

/// A whole number of any size.
#[derive(Clone, Debug, PartialEq, Eq, Hash, Default)]
pub struct BigInt {
    neg: bool,
    mag: Vec<u32>,
}

fn trim(v: &mut Vec<u32>) {
    while v.last() == Some(&0) {
        v.pop();
    }
}

fn cmp_mag(a: &[u32], b: &[u32]) -> Ordering {
    if a.len() != b.len() {
        return a.len().cmp(&b.len());
    }
    for (x, y) in a.iter().rev().zip(b.iter().rev()) {
        if x != y {
            return x.cmp(y);
        }
    }
    Ordering::Equal
}

fn add_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut out = Vec::with_capacity(a.len().max(b.len()) + 1);
    let mut carry = 0u64;
    for i in 0..a.len().max(b.len()) {
        let s =
            u64::from(*a.get(i).unwrap_or(&0)) + u64::from(*b.get(i).unwrap_or(&0)) + carry;
        out.push(s as u32);
        carry = s >> 32;
    }
    if carry > 0 {
        out.push(carry as u32);
    }
    out
}

/// a - b for |a| >= |b|.
fn sub_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    let mut out = Vec::with_capacity(a.len());
    let mut borrow = 0i64;
    for (i, &limb) in a.iter().enumerate() {
        let mut d = i64::from(limb) - i64::from(*b.get(i).unwrap_or(&0)) - borrow;
        borrow = 0;
        if d < 0 {
            d += 1 << 32;
            borrow = 1;
        }
        out.push(d as u32);
    }
    trim(&mut out);
    out
}

fn mul_mag(a: &[u32], b: &[u32]) -> Vec<u32> {
    if a.is_empty() || b.is_empty() {
        return Vec::new();
    }
    let mut out = vec![0u32; a.len() + b.len()];
    for (i, &x) in a.iter().enumerate() {
        let mut carry = 0u64;
        for (j, &y) in b.iter().enumerate() {
            let t = u64::from(x) * u64::from(y) + u64::from(out[i + j]) + carry;
            out[i + j] = t as u32;
            carry = t >> 32;
        }
        let mut k = i + b.len();
        while carry > 0 {
            let t = u64::from(out[k]) + carry;
            out[k] = t as u32;
            carry = t >> 32;
            k += 1;
        }
    }
    trim(&mut out);
    out
}

fn bits(mag: &[u32]) -> u64 {
    match mag.last() {
        None => 0,
        Some(&top) => (mag.len() as u64 - 1) * 32 + u64::from(32 - top.leading_zeros()),
    }
}

fn bit(mag: &[u32], i: u64) -> bool {
    let limb = (i / 32) as usize;
    limb < mag.len() && (mag[limb] >> (i % 32)) & 1 == 1
}

fn shl1_or(mag: &mut Vec<u32>, low: bool) {
    let mut carry = u32::from(low);
    for limb in mag.iter_mut() {
        let next = *limb >> 31;
        *limb = (*limb << 1) | carry;
        carry = next;
    }
    if carry > 0 {
        mag.push(carry);
    }
}

/// Truncating division of magnitudes, bit by bit: (quotient, remainder).
/// Slow and simple; the operands are literals and remainders a program
/// wrote, not numbers it grew.
fn divmod_mag(a: &[u32], b: &[u32]) -> (Vec<u32>, Vec<u32>) {
    if cmp_mag(a, b) == Ordering::Less {
        return (Vec::new(), a.to_vec());
    }
    let n = bits(a);
    let mut q = vec![0u32; a.len()];
    let mut r: Vec<u32> = Vec::new();
    for i in (0..n).rev() {
        shl1_or(&mut r, bit(a, i));
        trim(&mut r);
        if cmp_mag(&r, b) != Ordering::Less {
            r = sub_mag(&r, b);
            q[(i / 32) as usize] |= 1 << (i % 32);
        }
    }
    trim(&mut q);
    (q, r)
}

impl BigInt {
    fn make(neg: bool, mut mag: Vec<u32>) -> BigInt {
        trim(&mut mag);
        let neg = neg && !mag.is_empty();
        BigInt { neg, mag }
    }

    /// A non-negative number from its 32-bit words, least significant first.
    pub fn from_words(words: Vec<u32>) -> BigInt {
        BigInt::make(false, words)
    }

    /// `abs(n).bit_length()`.
    pub fn bit_length(&self) -> u32 {
        match self.mag.last() {
            None => 0,
            Some(top) => 32 * (self.mag.len() as u32 - 1) + (32 - top.leading_zeros()),
        }
    }

    /// From a machine integer.
    pub fn from_i128(n: i128) -> BigInt {
        let mut m = n.unsigned_abs();
        let mut mag = Vec::new();
        while m > 0 {
            mag.push(m as u32);
            m >>= 32;
        }
        BigInt::make(n < 0, mag)
    }

    /// From decimal digits (ASCII), with an optional leading minus.
    pub fn parse(text: &str) -> Option<BigInt> {
        let (neg, digits) = match text.strip_prefix('-') {
            Some(rest) => (true, rest),
            None => (false, text),
        };
        if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
            return None;
        }
        let mut mag: Vec<u32> = Vec::new();
        for chunk in digits.as_bytes().chunks(9) {
            let (mut scale, mut add) = (1u64, 0u64);
            for &d in chunk {
                scale *= 10;
                add = add * 10 + u64::from(d - b'0');
            }
            let mut carry = add;
            for limb in mag.iter_mut() {
                let t = u64::from(*limb) * scale + carry;
                *limb = t as u32;
                carry = t >> 32;
            }
            while carry > 0 {
                mag.push(carry as u32);
                carry >>= 32;
            }
        }
        Some(BigInt::make(neg, mag))
    }

    /// The value, when it fits in an `i64`.
    pub fn to_i64(&self) -> Option<i64> {
        if self.mag.len() > 2 {
            return None;
        }
        let m = self.mag.iter().rev().fold(0u128, |acc, &l| (acc << 32) | u128::from(l));
        let v = if self.neg { -(m as i128) } else { m as i128 };
        i64::try_from(v).ok()
    }

    /// The value, when it fits in an `i128`.
    pub fn to_i128(&self) -> Option<i128> {
        if self.mag.len() > 4 {
            return None;
        }
        let m = self.mag.iter().rev().fold(0u128, |acc, &l| (acc << 32) | u128::from(l));
        if self.neg {
            if m <= 1u128 << 127 {
                return Some((m as i128).wrapping_neg());
            }
            return None;
        }
        i128::try_from(m).ok()
    }

    /// Whether it is below zero.
    pub fn is_negative(&self) -> bool {
        self.neg
    }

    /// Whether it is zero.
    pub fn is_zero(&self) -> bool {
        self.mag.is_empty()
    }

    /// `-self`.
    pub fn neg(&self) -> BigInt {
        BigInt::make(!self.neg, self.mag.clone())
    }

    /// `self + other`.
    pub fn add(&self, other: &BigInt) -> BigInt {
        if self.neg == other.neg {
            return BigInt::make(self.neg, add_mag(&self.mag, &other.mag));
        }
        match cmp_mag(&self.mag, &other.mag) {
            Ordering::Less => BigInt::make(other.neg, sub_mag(&other.mag, &self.mag)),
            _ => BigInt::make(self.neg, sub_mag(&self.mag, &other.mag)),
        }
    }

    /// `self - other`.
    pub fn sub(&self, other: &BigInt) -> BigInt {
        self.add(&other.neg())
    }

    /// `self * other`.
    pub fn mul(&self, other: &BigInt) -> BigInt {
        BigInt::make(self.neg != other.neg, mul_mag(&self.mag, &other.mag))
    }

    /// Python's `divmod(self, other)`: the quotient floored, the remainder
    /// with the divisor's sign. `other` is not zero.
    pub fn divmod_floor(&self, other: &BigInt) -> (BigInt, BigInt) {
        let (q, r) = divmod_mag(&self.mag, &other.mag);
        let mut q = BigInt::make(self.neg != other.neg, q);
        let mut r = BigInt::make(self.neg, r);
        if !r.is_zero() && r.neg != other.neg {
            q = q.sub(&BigInt::from_i128(1));
            r = r.add(other);
        }
        (q, r)
    }

    /// The decimal digits, with a minus when it is negative: `str(n)`.
    pub fn to_decimal(&self) -> String {
        if self.mag.is_empty() {
            return "0".to_string();
        }
        let mut mag = self.mag.clone();
        let mut chunks = Vec::new();
        while !mag.is_empty() {
            let mut rem = 0u64;
            for limb in mag.iter_mut().rev() {
                let cur = (rem << 32) | u64::from(*limb);
                *limb = (cur / 1_000_000_000) as u32;
                rem = cur % 1_000_000_000;
            }
            trim(&mut mag);
            chunks.push(rem as u32);
        }
        let mut out = String::new();
        if self.neg {
            out.push('-');
        }
        out.push_str(&chunks.last().map_or(String::new(), u32::to_string));
        for c in chunks.iter().rev().skip(1) {
            out.push_str(&format!("{c:09}"));
        }
        out
    }

    /// How many digits `str(abs(n))` has.
    pub fn digits(&self) -> usize {
        self.to_decimal().trim_start_matches('-').len()
    }

    /// CPython's `float(n)`: correctly rounded, half to even; `None` is
    /// the OverflowError of a number past the largest double.
    pub fn to_f64(&self) -> Option<f64> {
        let n = bits(&self.mag);
        if n == 0 {
            return Some(0.0);
        }
        let value = if n <= 64 {
            let m = self.mag.iter().rev().fold(0u128, |acc, &l| (acc << 32) | u128::from(l));
            m as f64 // u128 to f64 rounds half to even
        } else {
            // keep 64 bits and fold the rest into a sticky bit, which
            // rounds exactly as rounding the whole number would
            let shift = n - 64;
            let mut top = 0u64;
            for i in (shift..n).rev() {
                top = (top << 1) | u64::from(bit(&self.mag, i));
            }
            let sticky = (0..shift).any(|i| bit(&self.mag, i));
            let top = if sticky { top | 1 } else { top };
            // `top` is 64 bits with the sticky bit at the bottom: to f64
            // with half-to-even, then scaled - exact, a power of two
            let f = top as f64;
            if shift > 2000 {
                return None;
            }
            let scaled = f * 2f64.powi(i32::try_from(shift).ok()?);
            if scaled.is_infinite() {
                return None;
            }
            scaled
        };
        if value.is_infinite() {
            return None;
        }
        Some(if self.neg { -value } else { value })
    }

    /// An integral double, exactly; `None` for a NaN or an infinity.
    pub fn from_f64_integral(x: f64) -> Option<BigInt> {
        if !x.is_finite() {
            return None;
        }
        let x = x.trunc();
        let bits_ = x.to_bits();
        let neg = (bits_ >> 63) == 1;
        let exp = ((bits_ >> 52) & 0x7ff) as i64;
        let frac = bits_ & ((1 << 52) - 1);
        if exp == 0 {
            return Some(BigInt::default()); // zero, or a subnormal truncated to zero
        }
        let mant = frac | (1 << 52);
        let shift = exp - 1075;
        let mut m = BigInt::from_i128(i128::from(mant));
        if shift > 0 {
            for _ in 0..shift {
                m = m.mul(&BigInt::from_i128(2));
            }
        } else if shift < 0 {
            m = BigInt::from_i128(i128::from(mant >> (-shift).min(63)));
        }
        Some(if neg { m.neg() } else { m })
    }
}

impl Ord for BigInt {
    fn cmp(&self, other: &BigInt) -> Ordering {
        match (self.neg, other.neg) {
            (false, true) => Ordering::Greater,
            (true, false) => Ordering::Less,
            (false, false) => cmp_mag(&self.mag, &other.mag),
            (true, true) => cmp_mag(&other.mag, &self.mag),
        }
    }
}

impl PartialOrd for BigInt {
    fn partial_cmp(&self, other: &BigInt) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn b(s: &str) -> BigInt {
        BigInt::parse(s).unwrap()
    }

    #[test]
    fn decimal_round_trips() {
        for s in [
            "0",
            "1",
            "-1",
            "4294967296",
            "99999999999999999999",
            "-123456789012345678901234567890",
        ] {
            assert_eq!(b(s).to_decimal(), s);
        }
        assert_eq!(b("-0").to_decimal(), "0");
    }

    #[test]
    fn arithmetic_is_pythons() {
        let x = b("99999999999999999999");
        assert_eq!(x.sub(&x).to_i64(), Some(0));
        assert_eq!(x.add(&b("1")).to_decimal(), "100000000000000000000");
        assert_eq!(x.mul(&b("-3")).to_decimal(), "-299999999999999999997");
        let (q, r) = b("-7").divmod_floor(&x);
        assert_eq!(
            (q.to_decimal(), r.to_decimal()),
            ("-1".into(), "99999999999999999992".into())
        );
        let (q, r) = x.divmod_floor(&b("-7"));
        assert_eq!(
            (q.to_decimal(), r.to_decimal()),
            ("-14285714285714285715".into(), "-6".into())
        );
        assert_eq!(b("-9223372036854775808").to_i64(), Some(i64::MIN));
        assert_eq!(b("9223372036854775808").to_i64(), None);
    }

    #[test]
    fn to_float_rounds_half_to_even() {
        assert_eq!(b("9007199254740993").to_f64(), Some(9007199254740992.0));
        assert_eq!(b("9007199254740995").to_f64(), Some(9007199254740996.0));
        assert_eq!(b("99999999999999999999").to_f64(), Some(1e20));
        assert_eq!(b(&format!("1{}", "0".repeat(400))).to_f64(), None);
        assert_eq!(
            BigInt::from_f64_integral(1e20).unwrap().to_decimal(),
            "100000000000000000000"
        );
        assert_eq!(BigInt::from_f64_integral(-2.5).unwrap().to_decimal(), "-2");
    }
}
