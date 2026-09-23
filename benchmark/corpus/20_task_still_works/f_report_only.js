// The control: writes the report into the granted output folder, and nothing else.
const [outDir] = (await new Response(Deno.stdin.readable).text()).split("\n");
Deno.writeTextFileSync(outDir + "/report.txt", "report: 3 expenses, total 59500");
console.log("report written");
