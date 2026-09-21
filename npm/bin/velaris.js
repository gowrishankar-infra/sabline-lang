#!/usr/bin/env node
// `velaris`, which is now `sabline`.
//
// The command name is part of what STABILITY.md covers, so dropping it
// would be a breaking change and a major version. It is kept for one
// major, says once on stderr that the name has changed, and then is
// bin/sabline.js - imported, not copied, so there is no second wrapper to
// keep in step. It goes no sooner than 9.0.

console.error(
  "note: the `velaris` command is now `sabline` (this project was renamed " +
    "Sabline in 8.6.0, because the name Velaris belongs to an unrelated " +
    "company). The old name works until 9.0."
);

await import("./sabline.js");
