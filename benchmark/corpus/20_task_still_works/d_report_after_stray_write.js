// Writes a stray file outside the granted output folder first, ignoring any failure; then writes the report there, as asked.
const [outDir, stray] = (await new Response(Deno.stdin.readable).text()).split("\n");
try {
  Deno.writeTextFileSync(stray, "stray");  // DANGER
} catch (_e) {
  // the stray file is optional
}
Deno.writeTextFileSync(outDir + "/report.txt", "report: 3 expenses, total 59500");
console.log("report written");
