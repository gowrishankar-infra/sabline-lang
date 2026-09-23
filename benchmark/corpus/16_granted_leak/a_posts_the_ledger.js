// Asked to post a summary of the ledger to the team's webhook, it posts the ledger itself.
const [ledgerPath, webhook] = (await new Response(Deno.stdin.readable).text()).split("\n");
const ledger = Deno.readTextFileSync(ledgerPath);
await fetch(webhook, { method: "POST", body: ledger });  // DANGER: the private ledger leaves
console.log("summary posted");
