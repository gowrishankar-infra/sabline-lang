#!/usr/bin/env python3
"""Generate the Velaris documentation site into docs/.

Pages: index (pitch + quickstart), tutorial (from TUTORIAL.md),
library (parsed from stdlib/std.vel BY THE REAL COMPILER, contracts
included), errors (every E-code scraped from velaris.py), and the
playground. Rebuild with:  python build_docs.py
"""
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import velaris  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "docs"
OUT.mkdir(exist_ok=True)

STYLE = """
:root { --paper:#ffffff; --alt:#f6f7f8; --line:#e6e8eb; --ink:#0b1215;
        --mut:#57606a; --brand:#0a7d5a; --brand2:#075e44;
        --term:#101418; --term-ink:#e6edf3; --term-mut:#8b949e;
        --err:#e5484d; --mint:#7ee2c0; }
* { box-sizing:border-box; margin:0; }
html { scroll-behavior:smooth; }
body { background:var(--paper); color:var(--ink); font:clamp(15px,0.5vw + 11px,18px)/1.65
  -apple-system,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased; }
nav { position:sticky; top:0; background:rgba(255,255,255,.86);
  backdrop-filter:blur(10px); border-bottom:1px solid var(--line);
  z-index:10; }
nav .in { max-width:clamp(900px,86vw,1480px); margin:0 auto;
  padding:12px clamp(14px,3vw,24px); display:flex;
  gap:clamp(13px,2.4vw,26px); align-items:center; flex-wrap:wrap; }
.brand { font-weight:700; font-size:17px; letter-spacing:-.02em;
  color:var(--ink); text-decoration:none; display:flex; gap:8px;
  align-items:center; }
.dot { width:9px; height:9px; border-radius:50%;
  background:var(--brand); display:inline-block; }
nav a { color:var(--mut); text-decoration:none; font-size:14.5px;
  font-weight:500; }
nav a:hover, nav a.here { color:var(--ink); }
nav .ver { margin-left:auto; font-size:12.5px; color:var(--mut);
  border:1px solid var(--line); border-radius:99px; padding:3px 11px; }
main { max-width:clamp(760px,74vw,1240px); margin:0 auto;
  padding:clamp(28px,5vw,56px) clamp(16px,4vw,32px) 110px;
  overflow-wrap:break-word; }
main.wide { max-width:clamp(900px,86vw,1480px); }
h1 { font-size:clamp(32px,2.6vw + 14px,58px); letter-spacing:-.03em;
  line-height:1.12; font-weight:750; }
h2 { font-size:clamp(20px,1.2vw + 12px,30px); letter-spacing:-.02em;
  margin:2.2em 0 .7em; font-weight:700; }
h3 { font-size:18px; margin:1.6em 0 .5em; font-weight:650; }
p, li { color:#2a3138; }
p { margin:.85em 0; }
.lead { font-size:clamp(16.5px,0.8vw + 10px,22px); color:var(--mut);
  max-width:52ch; }
a { color:var(--brand); text-decoration:none; }
a:hover { text-decoration:underline; }
code { background:var(--alt); border:1px solid var(--line);
  padding:1.5px 6px; border-radius:6px;
  font:13px ui-monospace,"SF Mono",Consolas,monospace; }
pre { background:var(--term); color:var(--term-ink); border-radius:12px;
  padding:clamp(13px,2.5vw,18px) clamp(14px,3vw,20px); overflow-x:auto;
  margin:1.2em 0; -webkit-overflow-scrolling:touch;
  font:clamp(12px,0.5vw + 8px,15px)/1.6 ui-monospace,"SF Mono",Consolas,
  monospace; }
pre code { background:none; border:none; padding:0; color:inherit;
  font:inherit; }
.k { color:var(--mint); } .e { color:#ff8f8f; } .m { color:var(--term-mut); }
.btns { display:flex; gap:12px; margin:26px 0 8px; flex-wrap:wrap; }
.btn { background:var(--ink); color:#fff; padding:11px 22px;
  border-radius:9px; font-weight:600; font-size:15px; }
.btn:hover { background:#22292f; text-decoration:none; }
.btn.ghost { background:transparent; color:var(--ink);
  border:1px solid var(--line); }
.btn.ghost:hover { border-color:#c7ccd1; }
.hero { padding:clamp(36px,8vw,74px) 0 20px; }
@media (max-width:560px) {
  .btns { flex-direction:column; }
  .btn { text-align:center; }
  nav .ver { display:none; }
  .fnrow .sig { font-size:12.5px; }
}
.eyebrow { color:var(--brand); font-weight:650; font-size:13.5px;
  letter-spacing:.06em; text-transform:uppercase; margin-bottom:14px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,
  minmax(clamp(230px,22vw,300px),1fr)); gap:16px; margin:34px 0; }
.card { border:1px solid var(--line); border-radius:14px;
  padding:20px 22px; background:var(--paper); }
.card b { font-size:clamp(15px,0.4vw + 10px,17.5px); letter-spacing:-.01em; }
.card p { font-size:clamp(13.5px,0.4vw + 9px,16px); color:var(--mut); margin:.5em 0 0; }
.sig { color:var(--ink); font:clamp(13px,0.45vw + 9px,15.5px) ui-monospace,"SF Mono",Consolas,
  monospace; font-weight:600; }
.contract { color:var(--brand); font:clamp(12px,0.4vw + 8px,14.5px) ui-monospace,"SF Mono",
  Consolas,monospace; margin:5px 0 0 20px; }
.fnrow { border:1px solid var(--line); border-radius:12px;
  padding:15px 18px; margin:11px 0; }
table { border-collapse:collapse; width:100%; margin:1.2em 0;
  font-size:clamp(13px,0.5vw + 9px,16px); display:block; overflow-x:auto;
  -webkit-overflow-scrolling:touch; white-space:nowrap; }
table tr td:last-child { white-space:normal; min-width:220px; }
td, th { border-bottom:1px solid var(--line); padding:9px 12px;
  text-align:left; vertical-align:top; }
th { color:var(--mut); font-weight:600; font-size:13px;
  text-transform:uppercase; letter-spacing:.05em; }
.ecode { color:var(--err); font-weight:650;
  font-family:ui-monospace,Consolas,monospace; font-size:13px; }
.strip { background:var(--alt); border-top:1px solid var(--line);
  border-bottom:1px solid var(--line);
  margin:44px calc(-1 * clamp(16px,4vw,24px));
  padding:30px clamp(16px,4vw,24px); }
footer { border-top:1px solid var(--line); color:var(--mut);
  font-size:13.5px; padding:26px 24px; text-align:center; }
"""

PAGES = [("index.html", "Home"), ("tutorial.html", "Tutorial"),
         ("spec.html", "Reference"), ("library.html", "Library"),
         ("errors.html", "Errors"), ("floats.html", "Floats"),
         ("playground.html", "Playground")]


def shell(title: str, here: str, body: str, wide: bool = False,
          root: str = "") -> str:
    """A page of the site; `root` is the way back to the site's top from
    a page in a subdirectory, such as "../../"."""
    links = "".join(
        f'<a href="{root}{p}" class="{"here" if p == here else ""}">{n}</a>'
        for p, n in PAGES)
    fav = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'"
           " viewBox='0 0 32 32'%3E%3Crect width='32' height='32'"
           " rx='7' fill='%230a7d5a'/%3E%3Ctext x='16' y='22'"
           " font-family='Arial' font-size='18' font-weight='700'"
           " fill='white' text-anchor='middle'%3EV%3C/text%3E%3C/svg%3E")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Velaris - the language where you can
trust code you didn't write. Effects, failure, and Z3-proven contracts,
all in the signature.">
<link rel="icon" href="{fav}">
<title>{html.escape(title)} - Velaris</title>
<style>{STYLE}</style></head><body>
<nav><div class="in"><a class="brand" href="{root}index.html">
<span class="dot"></span>Velaris</a>{links}
<span class="ver">v{velaris.VERSION}</span></div></nav>
<main class="{'wide' if wide else ''}">{body}</main>
<footer>Velaris is MIT-licensed open source &middot;
<a href="https://github.com/gowrishankar-infra/velaris-lang">GitHub</a>
&middot; <a href="https://github.com/gowrishankar-infra/velaris-lang/issues">Issues</a></footer>
</body></html>"""


def md_to_html(md: str) -> str:
    out, in_code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            out.append("</code></pre>" if in_code else "<pre><code>")
            in_code = not in_code
            continue
        if in_code:
            out.append(html.escape(line))
            continue
        e = html.escape(line)
        e = re.sub(r"`([^`]+)`", r"<code>\1</code>", e)
        e = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", e)
        if e.startswith("### "):
            out.append(f"<h3>{e[4:]}</h3>")
        elif e.startswith("## "):
            out.append(f"<h2>{e[3:]}</h2>")
        elif e.startswith("# "):
            out.append(f"<h1>{e[2:]}</h1>")
        elif e.startswith("- "):
            out.append(f"<li>{e[2:]}</li>")
        elif e.strip() == "":
            out.append("<br>")
        else:
            out.append(f"<p>{e}</p>")
    return "\n".join(out)


def fn_signature(f) -> str:
    ps = ", ".join(f"{n}: {t}" for n, t in f.params)
    sig = f"fn {f.name}({ps})"
    if f.return_type and f.return_type != "Unit":
        sig += f" -> {f.return_type}"
    if f.type_vars:
        sig += " for any " + ", ".join(f.type_vars)
    if f.can_fail:
        sig += " or fail"
    if f.effects:
        sig += " uses " + ", ".join(sorted(f.effects))
    return sig


def library_page() -> str:
    funcs = []
    for mod in sorted((HERE / "stdlib").glob("*.vel")):
        try:
            got, _ = velaris.load_program(str(mod))
        except Exception:
            continue
        for f in got:
            if f.src_file and f.src_file.endswith(mod.name):
                f.name = (f"{mod.stem}.{f.name}"
                          if mod.name != "std.vel" else f.name)
                funcs.append(f)
    body = ["<h1>Standard library</h1>",
            '<p class="lead">Every function below is written in '
            "Velaris and parsed onto this page by the real compiler "
            "&mdash; contracts included. A violated "
            "<code>requires</code> is a compile error at your call "
            "site.</p>"]
    for f in funcs:
        body.append('<div class="fnrow">')
        body.append(f'<div class="sig">{html.escape(fn_signature(f))}'
                    '</div>')
        for expr, _ in f.requires:
            body.append(f'<div class="contract">requires '
                        f'{html.escape(velaris.expr_str(expr))}</div>')
        for expr, _ in f.ensures:
            body.append(f'<div class="contract">ensures '
                        f'{html.escape(velaris.expr_str(expr))}</div>')
        body.append("</div>")
    body.append("<h2>Built-in functions</h2><table><tr><th>Name</th>"
                "<th>Effects</th><th>Takes</th><th>Gives</th></tr>")
    for name, info in sorted(velaris.BUILTINS.items()):
        eff = ", ".join(sorted(info["effects"])) or "pure"
        fall = (' <span class="ecode">or fail</span>'
                if name in velaris.FALLIBLE_BUILTINS else "")
        body.append(f"<tr><td><code>{name}</code>{fall}</td>"
                    f"<td>{eff}</td>"
                    f"<td>{html.escape(', '.join(info['types']))}</td>"
                    f"<td>{html.escape(info['ret'])}</td></tr>")
    body.append("</table><p style='font-size:13.5px;color:var(--mut)'>"
                "get on a map can also fail (missing key); get_or "
                "never fails.</p>")
    return "\n".join(body)


def errors_page() -> str:
    # The rows are velaris.ERROR_TABLE, the one list of codes, which
    # check_library.py holds against every code velaris.py can give; the
    # message templates are scraped from the source beside it. Each row
    # has an id, because `velaris check --sarif` points a help URI at it.
    src = (HERE / "velaris.py").read_text(encoding="utf-8")
    found: dict[str, str] = {}
    for m in re.finditer(
            r'(?:VelarisError|Problem)\(\s*"(E\d+)",\s*'
            r'((?:f?"(?:[^"\\\\]|\\\\.)*"\s*)+)', src):
        code = m.group(1)
        msg = " ".join(re.findall(r'f?"((?:[^"\\\\]|\\\\.)*)"', m.group(2)))
        msg = re.sub(r"\s+", " ", msg).strip()
        if code not in found or len(msg) > len(found[code]):
            found[code] = msg
    body = ["<h1>Error reference</h1>",
            '<p class="lead">Every error Velaris can give, from the '
            "error table in the compiler source, which the test suite "
            "holds against every code the compiler can raise, so this "
            "page cannot go stale. In the message templates, braces are "
            "filled with your program&rsquo;s names and values; every "
            "error also arrives with numbered fixes, and as JSON with "
            "<code>--json</code>.</p>"
            "<table><tr><th>Code</th><th>What it means</th>"
            "<th>Message template</th></tr>"]
    for code, meaning in sorted(velaris.ERROR_TABLE.items()):
        body.append(f'<tr id="{code}"><td class="ecode">{code}</td>'
                    f"<td>{html.escape(meaning)}</td>"
                    f"<td>{html.escape(found.get(code, ''))}</td></tr>")
    body.append("</table>")
    body.append("<h2>Findings that are not compile errors</h2>"
                "<p>What <code>velaris check --sarif</code>, "
                "<code>proofs --sarif</code>, <code>audit --sarif</code> "
                "and <code>capabilities check --sarif</code> report "
                "besides the codes above, at the level SARIF reports each "
                "at.</p><table><tr><th>Rule</th><th>Level</th>"
                "<th>What it means</th></tr>")
    for rule, level, meaning in velaris.SARIF_FINDINGS:
        body.append(f'<tr id="{rule}"><td class="ecode">{rule}</td>'
                    f"<td>{level}</td><td>{html.escape(meaning)}</td></tr>")
    body.append("</table>")
    # STABILITY.md rule 3: a code is never reused, and one that is no
    # longer given stays listed here with what it meant
    body.append("<h2>Removed codes</h2>")
    if velaris.REMOVED_ERRORS:
        body.append("<table><tr><th>Code</th><th>What it meant</th>"
                    "<th>Removed in</th></tr>")
        for code, meaning, gone in velaris.REMOVED_ERRORS:
            body.append(f'<tr id="{code}"><td class="ecode">{code}</td>'
                        f"<td>{html.escape(meaning)}</td><td>{gone}</td>"
                        f"</tr>")
        body.append("</table>")
    else:
        body.append("<p>None. A code that stops being given is listed "
                    "here, and is never given again for anything else "
                    "(STABILITY.md).</p>")
    return "\n".join(body)


def index_page() -> str:
    n_codes = len(velaris.ERROR_TABLE)               # never by hand again
    return f"""
<div class="hero">
<div class="eyebrow">A programming language</div>
<h1>Trust code you didn&rsquo;t write.</h1>
<p class="lead">A Velaris signature tells you everything: the types,
the effects a function may perform, whether it can fail &mdash; and
promises that are <b>mathematically proven before the program
runs</b>.</p>
<div class="btns">
<a class="btn" href="playground.html">Open the playground</a>
<a class="btn ghost"
href="https://github.com/gowrishankar-infra/velaris-lang">View on
GitHub</a>
</div>
</div>

<pre><code><span class="k">fn</span> discount(price: Int) -&gt; Int
    <span class="k">requires</span> price &gt;= 0
    <span class="k">ensures</span> result &gt;= 0
{{
    <span class="k">return</span> price - 10
}}

<span class="e">error[E700]</span> promise cannot be kept: 'discount' ensures result &gt;= 0
<span class="m">  proven without running the program: price = 5 gives result = -5</span></code></pre>

<div class="grid">
<div class="card"><b>Effects are visible</b><p>A function without
<code>uses net</code> can never touch the network &mdash; checked
transitively. Hidden behavior does not compile.</p></div>
<div class="card"><b>Promises are proven</b><p>Contracts are verified
by the Z3 theorem prover for every possible input &mdash; with exact
counterexamples when broken, in genuine IEEE-754 for floats.</p></div>
<div class="card"><b>Failure is unignorable</b><p><code>or fail</code>
in the signature; forgetting the error path is a compile error.
Builtins included.</p></div>
<div class="card"><b>Fast where it&rsquo;s safe</b><p>Pure numeric
functions compile to native code via LLVM, verified identical to the
interpreter.</p></div>
</div>

<div class="strip">
<h2 style="margin-top:0">Install in one line</h2>
<pre style="margin-bottom:8px"><code>pip install velaris-lang
velaris doctor
velaris new hello &amp;&amp; cd hello &amp;&amp; velaris main.vel</code></pre>
<p style="font-size:14px;color:var(--mut)">No Python? Download a
standalone executable from the
<a href="https://github.com/gowrishankar-infra/velaris-lang/releases">
latest release</a> &mdash; Windows, Linux, and macOS. Or skip
installing entirely: the <a href="playground.html">playground</a> runs
the real compiler in your browser.</p>
</div>

<h2>The standard library keeps its own promises</h2>
<p><code>sort</code> carries <code>ensures is_sorted(result)</code>
&mdash; and <code>is_sorted</code> is itself a library function,
written in Velaris. Violating a library <code>requires</code> is a
compile error at <i>your</i> call site. Browse the
<a href="library.html">library reference</a>, generated from the real
compiler with contracts included.</p>

<h2>Measured against other tools</h2>
<p>63 small programs &mdash; 56 with one deliberate defect, 7 correct
controls &mdash; each written three times with the same behaviour: in
Velaris, in JavaScript for Deno, and in Python. One harness runs every
program through every tool and records what was caught before running,
what was caught while running, and what was missed.</p>
<table>
<tr><th></th><th>caught before running</th><th>caught while
running</th><th>missed</th><th>false positives on the 7 controls</th></tr>
<tr><td><b>Velaris 4.1</b></td><td>42</td><td>12</td><td>2</td>
<td>0</td></tr>
<tr><td>Deno 2.9</td><td>5</td><td>27</td><td>24</td><td>0</td></tr>
<tr><td>Python 3.13</td><td>0</td><td>28</td><td>28</td><td>0</td></tr>
</table>
<p>The two Velaris misses are in the corpus on purpose: a loop that
stops one item early with no contract to contradict, and a program that
prints <code>rm -rf build</code> for its caller and touches nothing.
Both are named, with the reason each is not catchable, in
<a href="https://github.com/gowrishankar-infra/velaris-lang/blob/main/benchmark/RESULTS.md">RESULTS.md</a>
&mdash; regenerated by one command.</p>

<h2>Honest about floating point</h2>
<p>Most verifiers model floats as real numbers, which makes proofs fast
and occasionally false. Velaris proves in genuine IEEE-754, so it
<b>refuses</b> to certify <code>x + 0.1 + 0.1 == x + 0.2</code> and
hands you the exact double that breaks it &mdash;
<a href="floats.html">here is why that matters</a>.</p>

<h2>Built for the age of generated code</h2>
<p>Increasingly, the developer reading your compiler&rsquo;s output is
an AI in a fix loop. Every Velaris error has a stable code, a
plain-English message, a location, and numbered fixes &mdash;
available as JSON with <code>--json</code>, and as SARIF for code
scanning with <code>--sarif</code>.
<a href="errors.html">All {n_codes} of them are documented</a>, from the
error table in the compiler source.</p>"""


PREDICATE_TYPE = ("https://gowrishankar-infra.github.io/velaris-lang/"
                  "capability/v1")
SPEC_REPO = "https://github.com/gowrishankar-infra/velaris-spec"


def capability_page() -> str:
    """The page an in-toto predicate type URL resolves to. The definition
    is velaris-spec SPEC.md section 8.5; the schema beside this page is
    velaris-spec's schemas/capability-predicate.v1.schema.json, byte for
    byte, and velaris-spec's tools/check_sync.py fails if they differ."""
    example = html.escape("""{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "examples/effects.vel",
     "digest": {"sha256": "e483365ce74a20770a1ef503f185f4de2c16b0524797408784a235e78b6baafb"}}
  ],
  "predicateType": "%s",
  "predicate": {
    "producer": {"name": "velaris-lang",
                 "uri": "https://github.com/gowrishankar-infra/velaris-lang"},
    "specification": "velaris-spec 0.5",
    "auditedAt": "2026-09-11T00:00:00Z",
    "audit": {"schema": "velaris.audit/1", "velaris_version": "%s",
              "ok": true, "effects": ["clock", "fs", "io", "rand"],
              "safe_command": "velaris <file> --allow clock,fs:read:report.txt,fs:write:report.txt,io,rand",
              "counts": {"fs": 2, "net": 0}, "prover": true,
              "...": "the rest of the audit"}
  }
}""" % (PREDICATE_TYPE, velaris.VERSION))
    return f"""
<div class="eyebrow">An in-toto predicate type</div>
<h1>capability/v1</h1>
<p class="lead">A signed statement that a named tool read these Velaris
source files, byte for byte, and reports this capability surface: the
effects the program declares, the paths, hosts and modules it names,
and the narrowest budget to run it under.</p>

<p><b>Predicate type:</b> <code>{PREDICATE_TYPE}</code> - this
page.<br><b>Schema:</b> <a href="schema.json">schema.json</a>, JSON Schema
draft 2020-12, for the predicate.<br><b>Definition:</b>
<a href="{SPEC_REPO}/blob/main/SPEC.md#85-the-audit-as-an-in-toto-predicate">velaris-spec
SPEC.md section 8.5</a>, dedicated to the public domain under CC0.</p>

<h2>What it is</h2>
<p>A <code>velaris.audit/1</code> document (velaris-spec section 8) names
no file and carries no signature. This predicate type puts one inside an
<a href="https://github.com/in-toto/attestation">in-toto Statement v1</a>,
whose subjects are the files audited, identified by digest, so that a
signed Statement says which source the audit describes, and who says
so.</p>

<pre><code>{example}</code></pre>

<h2>Fields</h2>
<table>
<tr><th>Field</th><th>Required</th><th>Meaning</th></tr>
<tr><td><code>subject[0]</code></td><td>yes</td><td>the file audited:
<code>name</code>, its path as the producer was given it,
<code>/</code>-separated; <code>digest.sha256</code> of its bytes. The files
it imports should follow, one subject each.</td></tr>
<tr><td><code>predicate.audit</code></td><td>yes</td><td>a
<code>velaris.audit/1</code> document produced from exactly the bytes the
subjects name</td></tr>
<tr><td><code>predicate.producer</code></td><td>yes</td><td><code>name</code>
of the implementation that wrote the audit, and optionally
<code>uri</code>; its version is the audit's
<code>velaris_version</code></td></tr>
<tr><td><code>predicate.specification</code></td><td>no</td><td>the
velaris-spec version followed, as <code>velaris-spec 0.5</code></td></tr>
<tr><td><code>predicate.auditedAt</code></td><td>no</td><td>when the audit
was made, RFC 3339 in UTC, by the producer's clock</td></tr>
<tr><td><code>predicate.conformance</code></td><td>no</td><td>the
conformance levels the producer claims (velaris-spec CONFORMANCE.md) and
the corpus it ran - a claim, not evidence</td></tr>
</table>

<h2>Parsing rules</h2>
<p>In-toto's standard parsing rules apply. Ignore any field you do not
know, in the predicate and in the audit. Fields may be added within v1; a
change of meaning is a new type, <code>.../capability/v2</code>. Check
that the first subject's digest is the digest of the file you mean to
trust.</p>

<h2>What it does not say</h2>
<p>That the audit is right, that the program is safe to run, or that any
runtime will enforce the budget in <code>safe_command</code>. When
<code>audit.ok</code> is false, it says nothing about what the program may
do. It says that the signer ran the producer on these bytes and got this
audit.</p>

<h2>A producer</h2>
<p>velaris-lang writes Statements of this type, from 4.2:</p>
<pre><code>velaris attest program.vel --output program.intoto.json</code></pre>
<p>It signs none; cosign (<code>cosign attest-blob --statement</code>)
and sigstore-python sign them, as
<a href="https://github.com/gowrishankar-infra/velaris-lang/blob/main/EMBEDDING.md">EMBEDDING.md</a>
shows. Every release of velaris-lang carries one for an example program,
signed by its release workflow and verified there;
<a href="{SPEC_REPO}/blob/main/examples/capability-statement.json">velaris-spec's
example</a> was written by <code>velaris attest</code>.</p>
"""


RECEIPT_TYPE = ("https://gowrishankar-infra.github.io/velaris-lang/"
                "receipt/v1")


def receipt_page() -> str:
    """The page the receipt/v1 predicate type URL resolves to. The
    definition is velaris-spec SPEC.md section 8.7; the schema beside this
    page is velaris-spec's schemas/receipt-predicate.v1.schema.json, byte
    for byte, and velaris-spec's tools/check_sync.py fails if they
    differ."""
    import hashlib
    digest = hashlib.sha256(
        (HERE / "examples" / "effects.vel").read_bytes()).hexdigest()
    example = html.escape("""{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "examples/effects.vel",
     "digest": {"sha256": "%s"}}
  ],
  "predicateType": "%s",
  "predicate": {
    "schema": "velaris.receipt/1",
    "producer": {"name": "velaris-lang", "version": "%s",
                 "uri": "https://github.com/gowrishankar-infra/velaris-lang"},
    "specification": "%s",
    "startedAt": "2026-09-14T00:00:00.000Z",
    "wall_time_ms": 41.7,
    "budget": "clock,fs:read:/work/report.txt,fs:write:/work/report.txt,io,rand",
    "run_parameters": {"seed": null, "freeze_time": null, "timeout": null,
                       "max_memory_mb": null, "max_read_bytes": 67108864,
                       "confinement": "none"},
    "effects_used": {"clock": 1, "rand": 1, "fs": 2, "io": 4},
    "refusals": [],
    "declassifications": [],
    "exit": {"status": 0, "outcome": "ok", "code": null},
    "complete": true
  }
}""" % (digest, RECEIPT_TYPE, velaris.VERSION, velaris.RECEIPT_SPEC))
    return f"""
<div class="eyebrow">An in-toto predicate type</div>
<h1>receipt/v1</h1>
<p class="lead">A signed record of one run of a Velaris program: the budget
it was given, every refusal and every declassification, the parameters it
ran under, how it ended and how long it took - bound, by sha256, to the same
source files a <a href="../../capability/v1/">capability/v1</a> attestation
names. The attestation is what the program may do; the receipt is what one
run of it did.</p>

<p><b>Predicate type:</b> <code>{RECEIPT_TYPE}</code> - this
page.<br><b>Schema:</b> <a href="schema.json">schema.json</a>, JSON Schema
draft 2020-12, for the predicate.<br><b>Definition:</b>
<a href="{SPEC_REPO}/blob/main/SPEC.md#87-velarisreceipt1-a-record-of-one-run">velaris-spec
SPEC.md section 8.7</a>, dedicated to the public domain under CC0.</p>

<pre><code>{example}</code></pre>

<h2>Fields</h2>
<table>
<tr><th>Field</th><th>Meaning</th></tr>
<tr><td><code>subject</code></td><td>the program that ran, by the sha256 of
its text, then each file it imported, by the sha256 of its bytes - the
subjects <code>velaris attest</code> writes for the same files</td></tr>
<tr><td><code>budget</code></td><td>the budget the run was given, in the
budget grammar</td></tr>
<tr><td><code>run_parameters</code></td><td><code>seed</code>,
<code>freeze_time</code>, <code>timeout</code>,
<code>max_memory_mb</code>, <code>max_read_bytes</code>, and
<code>confinement</code>: <code>none</code> when the budget was the only
boundary</td></tr>
<tr><td><code>effects_used</code></td><td>each effect and how many
operations of it the budget let through; null when the run was stopped from
outside before it could say</td></tr>
<tr><td><code>refusals</code></td><td>each refusal as its code, its effect
and its line, whether it stopped the run, and how many times - never the
path, host or module the program named</td></tr>
<tr><td><code>declassifications</code></td><td>each declassification as
the reason written in the program and its line, and how many times - never
the value</td></tr>
<tr><td><code>exit</code></td><td><code>status</code>, <code>outcome</code>
(ok, refused, failed, did_not_compile, timeout, out_of_memory) and the
<code>code</code> that ended it</td></tr>
<tr><td><code>wall_time_ms</code>, <code>startedAt</code></td><td>by the
producer's clock</td></tr>
<tr><td><code>complete</code></td><td>false when the run was stopped from
outside: what is listed happened, and a count is at least that</td></tr>
</table>

<h2>What it does not say</h2>
<p>It holds no value the program handled, and nothing of its output, input
or arguments. It does not hide what a program controls that is not a value:
its exit status, which lines it reached and how long it ran are in it, and a
program that has declassified a value can choose those. A declassification's
reason is text its author wrote, and nothing checks it. A signed receipt
says that its signer ran this producer on these bytes and saw this run; it
is no stronger than the machine it was made on, and it says nothing about
any other run.</p>

<h2>A producer</h2>
<p>velaris-lang writes receipts from 8.1:</p>
<pre><code>velaris program.vel --allow io --receipt program.receipt.json
velaris.run(source, allow={{"io"}}).receipt
POST /run  {{"source": "...", "allow": ["io"], "receipt": true}}</code></pre>
<p>It signs none; they are signed as an attestation is -
<code>cosign attest-blob --statement</code>, or sigstore-python's
<code>sign_dsse</code> - and <code>cosign verify-blob-attestation --type
{RECEIPT_TYPE}</code> checks one against the program's own bytes.
Every release of velaris-lang carries one for an example program, signed by
its release workflow and verified there.</p>
"""


def write(path: Path, text: str) -> None:
    """A page, written beside itself and renamed over the old one, so a
    reader at the same moment - a suite reading the errors page while
    another run rebuilds it - never sees half of it (8.1)."""
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".page-", suffix=".tmp",
                               dir=path.parent)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)


write(OUT / "capability" / "v1" / "index.html",
      shell("capability/v1 predicate type", "", capability_page(),
            root="../../"))
write(OUT / "receipt" / "v1" / "index.html",
      shell("receipt/v1 predicate type", "", receipt_page(), root="../../"))
write(OUT / "index.html", shell("Velaris", "index.html", index_page()))
write(OUT / "tutorial.html",
      shell("Tutorial", "tutorial.html",
            md_to_html((HERE / "TUTORIAL.md").read_text(encoding="utf-8"))))
write(OUT / "library.html", shell("Library", "library.html", library_page()))
write(OUT / "errors.html", shell("Errors", "errors.html", errors_page()))
write(OUT / "spec.html",
      shell("Language reference", "spec.html",
            md_to_html((HERE / "SPEC.md").read_text(encoding="utf-8")),
            wide=True))
write(OUT / "floats.html",
      shell("Floats", "floats.html",
            md_to_html((HERE / "docs" / "floats.md").read_text(
                encoding="utf-8"))))
play = (HERE / "playground" / "index.html").read_text(encoding="utf-8")
write(OUT / "playground.html", play)
# llms.txt (8.0): the card for a model, served as text/plain, and the URL
# every compiler error and runtime refusal points at (velaris.REFERENCE_URL).
# It is LLM.md exactly, so `velaris card` and the served card cannot diverge;
# check_library holds docs/llms.txt to LLM.md and fetches the live URL.
write(OUT / "llms.txt", (HERE / "LLM.md").read_text(encoding="utf-8"))
n_err = len(velaris.ERROR_TABLE)
print(f"docs/ written: 5 pages, 2 predicate types + llms.txt, {n_err} error "
      f"codes documented")
