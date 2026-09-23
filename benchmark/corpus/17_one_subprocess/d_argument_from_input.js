// The control: runs the version-control tool with the argument the input names, from a helper.
function vcs(argument) {
  return new TextDecoder().decode(new Deno.Command("git", { args: [argument] }).outputSync().stdout);
}

const argument = (await new Response(Deno.stdin.readable).text()).split("\n")[0];
console.log(vcs(argument).startsWith("git version") ? "vcs: ok" : "vcs: missing");
