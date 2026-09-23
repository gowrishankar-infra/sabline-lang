// The control: runs the version-control tool once and reports it, which is all the task needs.
const v = new TextDecoder().decode(new Deno.Command("git", { args: ["--version"] }).outputSync().stdout);
console.log(v.startsWith("git version") ? "vcs: ok" : "vcs: missing");
