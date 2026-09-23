// The control: summarises the granted notes, and does nothing else.
const [notesPath] = (await new Response(Deno.stdin.readable).text()).split("\n");
console.log("notes: " + Deno.readTextFileSync(notesPath).length + " chars");
