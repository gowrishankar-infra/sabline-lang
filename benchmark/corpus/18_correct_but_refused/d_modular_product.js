// The control: a running product modulo the prime 2**61 - 1, as a hash does. Every product passes 64 bits on the way; every result fits.
const m = 2n ** 61n - 1n;
let r = 1n;
for (let i = 0; i < 100; i++) {
  r = r * 1234567890123n % m;
}
console.log("product " + r.toString());
