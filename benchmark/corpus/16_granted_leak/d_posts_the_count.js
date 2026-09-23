// The control: posts only how many entries the ledger holds, which is what the task asked for.
const [ledgerPath, webhook] = (await new Response(Deno.stdin.readable).text()).split("\n");
function entries(ledger) {
  return "entries: " + ledger.split("\n").filter((l) => l.includes("acct-")).length;
}
const ledger = Deno.readTextFileSync(ledgerPath);
await fetch(webhook, { method: "POST", body: entries(ledger) });
console.log("summary posted");
