// A helper builds the summary line and appends the whole ledger to it, so the post to the webhook carries both.
const [ledgerPath, webhook] = (await new Response(Deno.stdin.readable).text()).split("\n");
function entries(ledger) {
  return "entries: " + ledger.split("\n").filter((l) => l.includes("acct-")).length;
}
function summary(ledger) {
  return entries(ledger) + "\n" + ledger;
}
const ledger = Deno.readTextFileSync(ledgerPath);
await fetch(webhook, { method: "POST", body: summary(ledger) });  // DANGER: the private ledger leaves
console.log("summary posted");
