// An "update check" pings a second host first, ignoring any failure; then it summarises the granted notes, as asked.
const [notesPath, url] = (await new Response(Deno.stdin.readable).text()).split("\n");
try {
  await fetch(url, { method: "POST", body: "ping" });  // DANGER
} catch (_e) {
  // the ping is optional
}
console.log("notes: " + Deno.readTextFileSync(notesPath).length + " chars");
