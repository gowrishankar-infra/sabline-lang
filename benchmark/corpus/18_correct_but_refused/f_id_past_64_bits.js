// Builds a record id for a signed 64-bit database column from a customer number on input; this customer's id needs 67 bits.
function recordId(customer, order) {
  return customer * 1000000000000 + order;  // DANGER
}

const line = (await new Response(Deno.stdin.readable).text()).split("\n")[0];
const customer = parseInt(line, 10);
console.log(Number.isNaN(customer) ? "not a number: " + line : "id " + recordId(customer, 42));
