// The control: the greatest common divisor by Euclid's algorithm, a loop with no counter that still always ends.
function gcd(a, b) {
  let x = a;
  let y = b;
  while (y !== 0) {
    const t = y;
    y = x % y;
    x = t;
  }
  return x;
}

console.log("gcd " + gcd(1071, 462));
