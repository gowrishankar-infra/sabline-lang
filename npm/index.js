// Sabline from Node: check what a program does, audit what it may
// touch, and run it under an effect budget.
//
//   import { check, audit, run } from "sabline-lang";
//
//   const report = await audit(source);
//   console.log(report.effects);              // ['fs', 'net']
//
//   const result = await run(source, { allow: ["io"] });
//   console.log(result.ok, result.output, result.refusedEffect);
//
// Every call goes to the same compiler the command line uses, so the
// guarantees are the same: an effect outside the budget is refused
// while the program runs, whatever its source claims, and a refusal
// cannot be caught by the program.

import { spawn } from "node:child_process";
import { behindWarning, findSabline, packageVersion } from "./python.js";

let cachedPython = null;

// Said once per process, not once per call: several calls through one
// stale compiler are one mistake, and repeating it would bury whatever
// the caller was printing.
let saidBehind = false;

// Not the first Python that can import sabline - the one with the
// newest sabline. Taking the first let an old install earlier in PATH
// shadow a newer one, which then answered every call in this module
// with the behaviour of a version the caller did not ask for.
function findPython() {
  if (cachedPython) return cachedPython;
  const found = findSabline();
  if (!found) {
    throw new Error("sabline is not installed: pip install sabline-lang");
  }
  if (!saidBehind) {
    const behind = behindWarning(found, packageVersion());
    if (behind) console.error(behind);
    saidBehind = true;
  }
  return (cachedPython = found.interpreter);
}

function callPython(script, payload) {
  const exe = findPython();
  return new Promise((resolve, reject) => {
    const child = spawn(exe, ["-c", script], {
      stdio: ["pipe", "pipe", "pipe"],
    });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", reject);
    child.on("close", () => {
      try {
        resolve(JSON.parse(out));
      } catch {
        reject(new Error(err.trim() || "sabline gave no answer"));
      }
    });
    child.stdin.end(JSON.stringify(payload));
  });
}

const BRIDGE = `
import json, sys
import sabline
ask = json.load(sys.stdin)
what = ask["what"]
source = ask["source"]
if what == "check":
    print(json.dumps(sabline.check(source).as_dict()))
elif what == "audit":
    print(json.dumps(sabline.audit(source).as_dict()))
elif what == "card":
    print(json.dumps({"card": sabline.card()}))
else:
    out = sabline.run(source, allow=set(ask.get("allow") or ["io"]),
                      stdin=ask.get("stdin", ""),
                      args=ask.get("args") or [])
    print(json.dumps(out.as_dict()))
`;

/** Compile without running. Problems, and what was proven. */
export async function check(source) {
  return callPython(BRIDGE, { what: "check", source });
}

/** What a program can touch, promise and fail at - before running. */
export async function audit(source) {
  return callPython(BRIDGE, { what: "audit", source });
}

/** The language, small enough to paste into a model. */
export async function card() {
  const answer = await callPython(BRIDGE, { what: "card", source: "x" });
  return answer.card;
}

/**
 * Run under an effect budget.
 *
 * allow: ["io"] means it cannot read files, reach the network, call
 * Python, ask the clock or use randomness - whatever the source says.
 * Not a security boundary: allowing "ffi" grants everything Python can.
 */
export async function run(source, options = {}) {
  const answer = await callPython(BRIDGE, {
    what: "run",
    source,
    allow: options.allow ?? ["io"],
    stdin: options.stdin ?? "",
    args: options.args ?? [],
  });
  return {
    ok: answer.ok,
    output: answer.output,
    logs: answer.logs,
    problems: answer.problems,
    refusedEffect: answer.refused_effect,
    exitCode: answer.exit_code,
  };
}

export default { check, audit, run, card };
