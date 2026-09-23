// Formats a report through a vendored library; the library also posts the text to a telemetry host.
import { render } from "./fmtlib.js";

console.log(render("report"));
