// The control: 25! exactly. The answer needs 84 bits, and it is the right answer.
let product = 1n;
for (let i = 1n; i <= 25n; i++) {
  product = product * i;
}
console.log(product.toString());
