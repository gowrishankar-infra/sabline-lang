// Summarises the granted notes, as asked; then a telemetry ping, whose failure it ignores, goes to a second host.
const [notesPath, url] = (await new Response(Deno.stdin.readable).text()).split("\n");
console.log("notes: " + Deno.readTextFileSync(notesPath).length + " chars");
try {
  await fetch(url, { method: "POST", body: "ping" });  // DANGER
} catch (_e) {
  // the ping is optional
}
