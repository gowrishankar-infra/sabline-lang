// The control: measures a label through a vendored native library that does nothing else.
import { measure } from "./nativefmt.js";

console.log("length " + measure("report"));
