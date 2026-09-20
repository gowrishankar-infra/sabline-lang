#!/usr/bin/env node
// npx sabline hello.vel            (it gets io; --allow to widen)
//
// Sabline's compiler is one Python file. This hands your arguments to
// it, and if it is not installed, says exactly how to fix that rather
// than failing with a confusing spawn error.
//
// It also says when the compiler it found is older than this package.
// Two things can go wrong quietly otherwise: a stale Sabline earlier in
// PATH shadows a newer one, and a subcommand added after that stale
// version came out is read by the old compiler as a file name, so
// `npx sabline-lang mcp` fails with "cannot find file 'mcp'".

import { spawn } from "node:child_process";
import {
  behindWarning,
  compareVersions,
  findSabline,
  NOT_INSTALLED,
  packageVersion,
} from "../python.js";

// The version each subcommand first shipped in, from the changelog. It
// is what lets this wrapper name a missing command instead of leaving
// the old compiler to mistake it for a file. check_library.py holds it
// to the compiler's own dispatch, so a new subcommand cannot be added
// without an entry here.
const INTRODUCED = {
  repl: "1.9",
  run: "1.9",
  version: "1.9",
  fmt: "1.10",
  lsp: "1.11",
  doctor: "2.2",
  new: "2.2",
  explain: "2.6",
  proofs: "2.6",
  check: "2.7",
  test: "2.17",
  trace: "2.21",
  add: "2.23",
  deps: "2.23",
  verify: "2.23",
  build: "2.28",
  clean: "2.29",
  audit: "2.41.1",
  card: "2.41.1",
  "mcp-install": "2.53",
  serve: "2.54",
  "mcp-manifest": "3.4.0",
  "mcp-verify": "3.4.0",
  capabilities: "4.0.0",
  review: "4.0.0",
  conformance: "4.1.0",
  attest: "4.2.0",
  mcp: "4.3.3",
  migrate: "5.0.0",
  "deps-diff": "7.1.0",
  "permissions-ratchet": "8.3.0",
  eject: "8.1.0",
  stats: "8.2.0",
  eval: "8.3.0",
  receipts: "8.3.0",
  replay: "8.3.0",
  demo: "8.5.0",
  receipt: "8.5.0",
  skill: "8.5.0",
};

// The two flags the compiler takes before any command, each with a
// value of its own; everything else beginning with "-" is a flag whose
// value, if it has one, is attached. What is left is the subcommand,
// or a file name - which is not in the table, so it is left alone.
const GLOBAL_WITH_VALUE = ["--proof-timeout", "--max-memory-mb"];

function requestedCommand(args) {
  for (let i = 0; i < args.length; i++) {
    if (GLOBAL_WITH_VALUE.includes(args[i])) {
      i++;
      continue;
    }
    if (args[i].startsWith("-")) continue;
    return args[i];
  }
  return null;
}

const args = process.argv.slice(2);
const ours = packageVersion();
const found = findSabline();

if (!found) {
  console.error(NOT_INSTALLED);
  process.exit(127);
}

const wanted = requestedCommand(args);
const needs = wanted ? INTRODUCED[wanted] : null;
if (needs && found.version && compareVersions(found.version, needs) < 0) {
  console.error(
    `sabline ${wanted} arrived in Sabline ${needs}; the compiler at ` +
      `${found.interpreter} is ${found.version}` +
      (ours ? `, while this npm package is ${ours}` : "") +
      ". Upgrade the compiler with: pip install -U sabline-lang"
  );
  process.exit(127);
}

const behind = behindWarning(found, ours);
if (behind) console.error(behind);

// The interpreter, not the name that found it: the version answer came
// from that executable, so that executable is the one to run.
const child = spawn(found.interpreter, ["-m", "sabline", ...args], {
  stdio: "inherit",
});
child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code ?? 0);
});
