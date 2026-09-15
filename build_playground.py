#!/usr/bin/env python3
"""Generate playground/index.html with the real compiler embedded.

Run after any change to the velaris package:   python build_playground.py
Open playground/index.html in a browser - no install, no server needed.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
# every module of the package, by file name (8.2: until then one file)
SRC = {p.name: p.read_text(encoding="utf-8")
       for p in sorted((HERE / "velaris").glob("*.py"))}

EXAMPLES = {
    "word frequency": """// Counting words: maps, lambdas, and a sorted report.
record Tally {
    word: Text
    count: Int
}

fn count_words(text: Text) -> Map of Text to Int {
    let counts: Map of Text to Int = {}
    let words = split(lower(text), " ")
    let i = 0
    while i < length(words) {
        let w = get(words, i)
        if length(w) > 0 {
            counts = put(counts, w, get_or(counts, w, 0) + 1)
        }
        i = i + 1
    }
    return counts
}

fn main() uses io {
    let counts = count_words("the fox and the dog and the bird")
    let names = keys(counts)
    let i = 0
    while i < length(names) {
        let n = get(names, i)
        print(format("{}: {}", n, get_or(counts, n, 0)))
        i = i + 1
    }
}
""",

    "hello": """fn greet(name: Text) uses io {
    print("hello, " + name)
}

fn main() uses io {
    greet("world")
    print("2 + 2 = " + (2 + 2))
}""",
    "sneaky effect (rejected)": """// This "pure calculator" secretly prints.
// The effect checker refuses to run it.

fn discount(price: Int) -> Int {
    print("leaking: " + price)
    return price - 10
}

fn main() uses io {
    print(discount(200))
}""",
    "broken promise (caught)": """// The promise says the result is never negative.
// (In the browser, promises are checked while running -
// the installed version PROVES this before running, via Z3.)

fn discount(price: Int) -> Int
    ensures result >= 0
{
    return price - 10
}

fn main() uses io {
    print("discount(200) = " + discount(200))
    print("discount(5) = " + discount(5))
}""",
    "records": """record Point {
    x: Int
    y: Int
}

fn shift(p: Point, dx: Int) -> Point {
    return Point(x: p.x + dx, y: p.y)
}

fn main() uses io {
    let p = Point(x: 3, y: 4)
    print(p)
    print(shift(p, 10))
}""",
    "fizzbuzz": """fn fizzbuzz(n: Int) -> Text {
    if n % 15 == 0 {
        return "fizzbuzz"
    } else if n % 3 == 0 {
        return "fizz"
    } else if n % 5 == 0 {
        return "buzz"
    }
    return to_text(n)
}

fn main() uses io {
    let i = 1
    while i <= 15 {
        print(fizzbuzz(i))
        i = i + 1
    }
}""",
}

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Velaris Playground</title>
<style>
  :root { --paper:#ffffff; --alt:#f6f7f8; --line:#e6e8eb;
          --ink:#0b1215; --mut:#57606a; --brand:#0a7d5a;
          --term:#101418; --term-ink:#e6edf3; --term-mut:#8b949e;
          --err:#e5484d; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink);
         font-family:-apple-system,"Segoe UI",Inter,Roboto,Helvetica,
         Arial,sans-serif; height:100vh; display:flex;
         flex-direction:column; }
  header { padding:12px 20px; display:flex; align-items:center;
           gap:16px; border-bottom:1px solid var(--line);
           flex-wrap:wrap; background:var(--paper); }
  header .brand { font-size:16px; font-weight:700;
    letter-spacing:-.02em; display:flex; gap:8px; align-items:center;
    color:var(--ink); text-decoration:none; }
  .dot { width:8px; height:8px; border-radius:50%;
         background:var(--brand); }
  header .tag { color:var(--mut); font-size:13px; }
  select { background:var(--paper); color:var(--ink);
    border:1px solid var(--line); border-radius:8px; padding:7px 12px;
    font-size:13.5px; }
  button#run { background:var(--ink); color:#fff; border:none;
    border-radius:8px; padding:8px 20px; font-size:14px;
    font-weight:600; cursor:pointer; }
  button#run:hover { background:#22292f; }
  button:disabled { opacity:.45; cursor:wait; }
  header a.gh { margin-left:auto; color:var(--mut); font-size:13px;
    text-decoration:none; }
  header a.gh:hover { color:var(--ink); }
  main { flex:1; display:flex; min-height:0; }
  textarea { flex:1; background:var(--paper); color:var(--ink);
    border:none; resize:none; padding:18px 20px;
    font:13.5px/1.65 ui-monospace,"SF Mono",Consolas,monospace;
    outline:none; }
  #out { flex:1; background:var(--term); color:var(--term-ink);
    margin:0; padding:18px 20px; overflow:auto;
    font:13.5px/1.65 ui-monospace,"SF Mono",Consolas,monospace;
    white-space:pre-wrap; border-left:1px solid var(--line); }
  .err { color:var(--err); } .note { color:var(--term-mut); }
  button#inspect { background:var(--paper); color:var(--ink);
    border:1px solid var(--line); border-radius:8px; padding:8px 16px;
    font-size:14px; font-weight:600; cursor:pointer; }
  button#inspect:hover { border-color:#c7ccd1; }
  button#inspect:disabled { opacity:.45; cursor:wait; }
  #cards { flex:1; overflow:auto; padding:16px 18px; background:var(--alt);
    border-left:1px solid var(--line); font-size:13.5px; }
  #cards.hidden, #out.hidden { display:none; }
  .fn { background:var(--paper); border:1px solid var(--line);
    border-radius:10px; padding:13px 15px; margin-bottom:11px; }
  .fn h4 { margin:0 0 7px; font:600 13.5px ui-monospace,"SF Mono",
    Consolas,monospace; word-break:break-word; }
  .pill { display:inline-block; font-size:11px; font-weight:650;
    border-radius:99px; padding:2px 9px; margin:0 5px 5px 0; }
  .p-proven { background:#dcf5ea; color:#075e44; }
  .p-runtime { background:#fdf0d5; color:#8a5a00; }
  .p-none { background:#eef0f2; color:var(--mut); }
  .p-err { background:#fde0e1; color:#a3161a; }
  .p-eff { background:#e5edfb; color:#1d4ed8; }
  .p-fail { background:#f3e8fd; color:#6b21a8; }
  .row { font:12.5px ui-monospace,"SF Mono",Consolas,monospace;
    color:var(--brand); margin:3px 0 0 2px; word-break:break-word; }
  .row.need { color:#8a5a00; }
  .prob { background:#fff4f4; border:1px solid #f6cdcf; border-radius:10px;
    padding:12px 14px; margin-bottom:11px; }
  .prob b { color:#a3161a; font-family:ui-monospace,monospace;
    font-size:12.5px; }
  .prob p { margin:5px 0 0; color:#5c1d1f; font-size:13px; }
  @media (max-width:800px) { main { flex-direction:column; }
    #out, #cards { border-left:none;
      border-top:1px solid var(--line); } }
</style>
</head>
<body>
<header>
  <a class="brand" href="index.html"><span class="dot"></span>Velaris
  Playground</a>
  <span class="tag">the real compiler, running in your browser</span>
  <select id="examples"></select>
  <button id="run" disabled>loading&hellip;</button>
  <button id="inspect" disabled>Inspect</button>
  <a class="gh"
  href="https://github.com/gowrishankar-infra/velaris-lang">GitHub
  &rarr;</a>
</header>
<main>
  <textarea id="code" spellcheck="false"></textarea>
  <pre id="out"><span class="note">Loading Python runtime (first visit
takes a few seconds)&hellip;

Note: in the browser, promises (requires/ensures/invariant) are checked
while the program runs. The installed version also PROVES them before
running, using the Z3 theorem prover, and compiles hot functions to
native code with LLVM. github.com/gowrishankar-infra/velaris-lang</span></pre>
  <div id="cards" class="hidden"></div>
</main>
<script>
const VELARIS_FILES = __SRC__;
const EXAMPLES = __EXAMPLES__;

const sel = document.getElementById("examples");
const code = document.getElementById("code");
const out = document.getElementById("out");
const runBtn = document.getElementById("run");

for (const name of Object.keys(EXAMPLES)) {
  const o = document.createElement("option");
  o.value = name; o.textContent = name;
  sel.appendChild(o);
}
code.value = EXAMPLES[Object.keys(EXAMPLES)[0]];
sel.onchange = () => { code.value = EXAMPLES[sel.value]; };

let pyodide = null;
async function boot() {
  pyodide = await loadPyodide();
  pyodide.setStdin({ stdin: () => window.prompt("the program asks:") });
  pyodide.FS.mkdirTree("/velaris");
  for (const [name, text] of Object.entries(VELARIS_FILES)) {
    pyodide.FS.writeFile("/velaris/" + name, text);
  }
  runBtn.disabled = false;
  runBtn.textContent = "Run \\u25B6";
  document.getElementById("inspect").disabled = false;
  out.innerHTML = '<span class="note">Ready. Pick an example or write ' +
    'your own, then press Run.</span>';
}

async function run() {
  runBtn.disabled = true; runBtn.textContent = "running\\u2026";
  document.getElementById("cards").classList.add("hidden");
  out.classList.remove("hidden");
  out.textContent = "";
  pyodide.FS.writeFile("/prog.vel", code.value);
  const py = `
import io, json, sys
from contextlib import redirect_stdout, redirect_stderr
# a Velaris imported anew for every run, as a new process would have
# it, so nothing one run set is there for the next
for _name in [n for n in sys.modules
              if n == "velaris" or n.startswith("velaris.")]:
    del sys.modules[_name]
if "/" not in sys.path:
    sys.path.insert(0, "/")
import velaris as mod
# io: what every example here needs, and all a page in a browser can
# use. It is also the default from 5.0; saying it keeps the page from
# depending on that.
sys.argv = ["velaris.py", "/prog.vel", "--allow", "io", "--no-native"]
o, e = io.StringIO(), io.StringIO()
try:
    with redirect_stdout(o), redirect_stderr(e):
        try:
            mod.main()
        except SystemExit:
            pass
except Exception as ex:
    e.write(f"playground error: {ex}")
json.dumps([o.getvalue(), e.getvalue()])
`;
  try {
    const res = JSON.parse(await pyodide.runPythonAsync(py));
    const [stdout, stderr] = res;
    out.textContent = "";
    if (stdout) out.append(stdout);
    if (stderr) {
      for (const ln of stderr.split("\\n")) {
        const s = document.createElement("span");
        s.className = ln.startsWith("note:") ? "note" : "err";
        s.textContent = ln + "\\n";
        out.appendChild(s);
      }
    }
    if (!stdout && !stderr) {
      out.innerHTML = '<span class="note">(no output)</span>';
    }
  } catch (err) {
    out.innerHTML = '<span class="err">playground error: ' + err + '</span>';
  }
  runBtn.disabled = false; runBtn.textContent = "Run \\u25B6";
}
runBtn.onclick = run;

const inspectBtn = document.getElementById("inspect");
const cards = document.getElementById("cards");
function esc(t) {
  return String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;");
}
async function inspect() {
  inspectBtn.disabled = true; inspectBtn.textContent = "reading\\u2026";
  pyodide.FS.writeFile("/prog.vel", code.value);
  const py = `
import json, sys
for _name in [n for n in sys.modules
              if n == "velaris" or n.startswith("velaris.")]:
    del sys.modules[_name]
if "/" not in sys.path:
    sys.path.insert(0, "/")
import velaris as mod
json.dumps(mod.inspect_source("/prog.vel"))
`;
  try {
    const rep = JSON.parse(await pyodide.runPythonAsync(py));
    out.classList.add("hidden"); cards.classList.remove("hidden");
    cards.innerHTML = "";
    for (const e of rep.errors) {
      const d = document.createElement("div");
      d.className = "prob";
      d.innerHTML = "<b>line " + e.line + " \\u00b7 " + e.code + "</b><p>" +
        esc(e.message) + "</p>" +
        (e.fixes || []).map(f => "<p>\\u2192 " + esc(f) + "</p>").join("");
      cards.appendChild(d);
    }
    for (const f of rep.functions) {
      const ps = f.params.map(p => p.name + ": " + p.type).join(", ");
      const st = f.status;
      let pills = '<span class="pill ' +
        (st === "proven" ? "p-proven" : st === "error" ? "p-err" :
         st === "checked at runtime" ? "p-runtime" : "p-none") +
        '">' + esc(st) + "</span>";
      for (const eff of f.effects) {
        pills += '<span class="pill p-eff">uses ' + esc(eff) + "</span>";
      }
      if (!f.effects.length) pills += '<span class="pill p-none">pure</span>';
      if (f.can_fail) pills += '<span class="pill p-fail">can fail</span>';
      let rows = "";
      for (const r of f.requires) {
        rows += '<div class="row need">needs ' + esc(r) + "</div>";
      }
      for (const e of f.ensures) {
        rows += '<div class="row">promises ' + esc(e) + "</div>";
      }
      const d = document.createElement("div");
      d.className = "fn";
      d.innerHTML = "<h4>fn " + esc(f.name) + "(" + esc(ps) +
        ") \\u2192 " + esc(f.returns) + "</h4>" + pills + rows +
        '<div class="row" style="color:var(--mut)">line ' + f.line + "</div>";
      cards.appendChild(d);
    }
    if (!rep.functions.length && !rep.errors.length) {
      cards.innerHTML = '<div class="row" style="color:var(--mut)">' +
        "nothing to show yet</div>";
    }
  } catch (err) {
    out.classList.remove("hidden"); cards.classList.add("hidden");
    out.innerHTML = '<span class="err">inspect error: ' + err + "</span>";
  }
  inspectBtn.disabled = false; inspectBtn.textContent = "Inspect";
}
inspectBtn.onclick = inspect;
</script>
<script src="https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"
        onload="boot()"></script>
</body>
</html>
"""

html = TEMPLATE.replace("__SRC__", json.dumps(SRC)) \
               .replace("__EXAMPLES__", json.dumps(EXAMPLES))
outdir = HERE / "playground"
outdir.mkdir(exist_ok=True)
# written beside the page and renamed over it, so a reader at the same
# moment - build_docs.py copies it - never sees half a page (8.1)
import os as _os  # noqa: E402
import tempfile as _tempfile  # noqa: E402
_fd, _tmp = _tempfile.mkstemp(prefix=".index-", suffix=".tmp", dir=outdir)
with _os.fdopen(_fd, "w", encoding="utf-8") as _fh:
    _fh.write(html)
_os.replace(_tmp, outdir / "index.html")
print(f"playground/index.html written ({len(html)//1024} KB)")
