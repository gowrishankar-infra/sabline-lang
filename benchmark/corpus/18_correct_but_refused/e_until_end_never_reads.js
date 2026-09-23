// Counts lines until the input ends, but reads once before the loop and never inside it: on any input it never ends.
const reader = Deno.stdin.readable.getReader();
const chunk = await reader.read();
let count = 0;
while (!chunk.done) {  // DANGER
  count = count + 1;
}
console.log(count + " lines");
