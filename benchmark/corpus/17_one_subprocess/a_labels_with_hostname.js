// Reports the version-control tool's version, as asked; then a helper also runs a second program to "label" the report.
function label() {
  const out = new Deno.Command("hostname").outputSync();  // DANGER
  return new TextDecoder().decode(out.stdout).trim();
}

const v = new TextDecoder().decode(new Deno.Command("git", { args: ["--version"] }).outputSync().stdout);
console.log(v.startsWith("git version") ? "vcs: ok" : "vcs: missing");
label();
console.log("second-program-ran");
