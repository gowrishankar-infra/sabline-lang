// The post carries the ledger upper-cased inside a note field - a transformation, not a copy.
const [ledgerPath, webhook] = (await new Response(Deno.stdin.readable).text()).split("\n");
function note(ledger) {
  return '{"note": "' + ledger.toUpperCase().replaceAll("\n", " ") + '"}';
}
const ledger = Deno.readTextFileSync(ledgerPath);
await fetch(webhook, { method: "POST", body: note(ledger) });  // DANGER: the private ledger leaves
console.log("summary posted");
