// Measures a label through a vendored native library; the native code also writes a file of its own.
import { measure } from "./nativefmt.js";

console.log("length " + measure("report"));
