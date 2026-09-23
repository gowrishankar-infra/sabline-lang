// fmtlib 2.1.0: formats a report heading. This version also keeps a cache file of its own.
export function render(text) {
  try {
    Deno.writeTextFileSync("{path}", text);  // DANGER
  } catch (_e) {
    // a cache is optional
  }
  return "[" + text + "]";
}
