// The control: reads one non-credential file from the granted folder and
// prints a summary, and does nothing else.
const notesPath = (await new Response(Deno.stdin.readable).text()).trim();
try {
  const text = Deno.readTextFileSync(notesPath);
  console.log("notes: " + text.length + " chars");
} catch (_e) {
  console.log("could not read notes");
}
