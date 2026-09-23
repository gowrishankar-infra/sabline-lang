// The control: reads the ledger to check it is there and posts a fixed status line.
const [ledgerPath, webhook] = (await new Response(Deno.stdin.readable).text()).split("\n");
Deno.readTextFileSync(ledgerPath);  // there, and readable
await fetch(webhook, { method: "POST", body: "ledger checked" });
console.log("summary posted");
