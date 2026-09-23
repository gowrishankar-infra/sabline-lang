// The control: counts the lines of its input, reading until the input ends. Correct, and unbounded by design.
const reader = Deno.stdin.readable.getReader();
let text = "";
let done = false;
while (!done) {
  const chunk = await reader.read();
  done = chunk.done;
  if (chunk.value) text += new TextDecoder().decode(chunk.value);
}
console.log(text.split("\n").filter((l) => l !== "").length + " lines");
