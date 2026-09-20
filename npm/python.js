// Finding the Python that holds the Sabline compiler.
//
// The npm package is a wrapper, not a copy: it finds a Python that can
// import `sabline` and calls it. Until 4.3.4 it took the first Python
// that could import the module at all, which meant an old Sabline in an
// early candidate silently shadowed a newer one further down - and a
// subcommand added after that old version came out looked to the user
// like a missing file rather than a missing compiler.
//
// So: ask every candidate which version it has, and take the newest.
// The caller decides what to say when the newest is still older than
// the package that invoked it; what this module promises is that the
// choice is made on version and that the version is known.

import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";

// One line of JSON on stdout: the version the module declares, and the
// interpreter it came from. `sabline.VERSION` has been there since 1.0,
// so every real Sabline answers; something importable as `sabline` that
// is not one is reported as a null version rather than as no Sabline at
// all, and ranks below everything that can say what it is.
const PROBE =
  "import json,sys,sabline;" +
  "sys.stdout.write(json.dumps({" +
  '"version": getattr(sabline, "VERSION", None), ' +
  '"interpreter": sys.executable}))';

export function candidates() {
  return process.platform === "win32"
    ? ["py", "python", "python3"]
    : ["python3", "python"];
}

/** -1, 0 or 1, comparing dotted numeric versions of any length. */
export function compareVersions(a, b) {
  const parts = (v) =>
    String(v)
      .split(".")
      .map((n) => {
        const x = parseInt(n, 10);
        return Number.isFinite(x) ? x : 0;
      });
  const pa = parts(a);
  const pb = parts(b);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const x = pa[i] ?? 0;
    const y = pb[i] ?? 0;
    if (x !== y) return x < y ? -1 : 1;
  }
  return 0;
}

// A version we could not read loses to every version we could, so an
// unreadable one is never preferred over a known one.
function newer(a, b) {
  if (a === null) return false;
  if (b === null) return true;
  return compareVersions(a, b) > 0;
}

/**
 * The candidate holding the newest Sabline.
 *
 * Returns null if no candidate has it at all, else { command,
 * interpreter, version, all }: `version` is null when the module
 * declares none, and `all` is every candidate that had Sabline, in the
 * order they were tried.
 */
export function findSabline() {
  const found = [];
  const seen = new Set();
  for (const command of candidates()) {
    const probe = spawnSync(command, ["-c", PROBE], { encoding: "utf8" });
    if (probe.error || probe.status !== 0) continue;
    let answer;
    try {
      const lines = (probe.stdout || "").trim().split(/\r?\n/).filter(Boolean);
      answer = JSON.parse(lines[lines.length - 1]);
    } catch {
      continue; // it imported but would not say what it is
    }
    const version =
      typeof answer.version === "string" && /^\d+(\.\d+)*$/.test(answer.version)
        ? answer.version
        : null;
    const interpreter = answer.interpreter || command;
    // `py` and `python` are often the same interpreter; count it once
    // so that "the newest of several" is about several Pythons.
    if (seen.has(interpreter)) continue;
    seen.add(interpreter);
    found.push({ command, interpreter, version });
  }
  if (found.length === 0) return null;
  let best = found[0];
  for (const one of found.slice(1)) {
    if (newer(one.version, best.version)) best = one;
  }
  return { ...best, all: found };
}

/**
 * The version of the npm package this file belongs to, or null.
 *
 * Resolved against this file, which sits beside package.json, so it is
 * the same answer wherever it is called from.
 */
export function packageVersion() {
  try {
    const beside = new URL("./package.json", import.meta.url);
    return JSON.parse(readFileSync(beside, "utf8")).version || null;
  } catch {
    return null;
  }
}

/**
 * One line for stderr when the compiler is older than the package that
 * invoked it, or null when it is not. Never silence: a wrapper running
 * a compiler older than itself is the one thing the user cannot see.
 */
export function behindWarning(found, ours) {
  if (!ours) return null;
  if (found.version === null) {
    return (
      `sabline-lang ${ours} (npm) is using a Sabline at ${found.interpreter} ` +
      "that does not say which version it is; upgrade it with: " +
      "pip install -U sabline-lang"
    );
  }
  if (compareVersions(found.version, ours) >= 0) return null;
  return (
    `sabline-lang ${ours} (npm) is using Sabline ${found.version}, from ` +
    `${found.interpreter}; upgrade the compiler with: ` +
    "pip install -U sabline-lang"
  );
}

export const NOT_INSTALLED =
  "Sabline needs its compiler, which is a Python package:\n" +
  "\n    pip install sabline-lang\n" +
  "\nOr try it with nothing installed:\n" +
  "    https://sabline.dev/playground.html";
