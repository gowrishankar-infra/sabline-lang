// A "preflight" runs a second program first, ignoring any failure, and then the task runs the version-control tool.
try {
  new Deno.Command("hostname").outputSync();  // DANGER
  console.log("second-program-ran");
} catch (_e) {
  // the preflight is optional
}
const v = new TextDecoder().decode(new Deno.Command("git", { args: ["--version"] }).outputSync().stdout);
console.log(v.startsWith("git version") ? "vcs: ok" : "vcs: missing");
