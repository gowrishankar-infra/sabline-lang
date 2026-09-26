#!/usr/bin/env python3
"""The documentation site, generated into docs/ (8.3.1).

    python build_docs.py

Every page is made from this repository. The Markdown documents -
TUTORIAL.md, SPEC.md, THREAT_MODEL.md, EMBEDDING.md, STABILITY.md,
SECURITY.md, CHANGELOG.md and every docs/*.md - are rendered by
docs_markdown.py, with Sabline code highlighted by the lexer's own token
classes. The standard library page is read from stdlib/ by the compiler,
contracts included; the errors page is sabline.ERROR_TABLE; the two
predicate-type pages name the types sabline writes. llms.txt is LLM.md
byte for byte, and playground.html is build_playground.py's page. Every
page links site/site.css and site/site.js, copied beside it, and nothing
else. check_site.py holds what this writes; run build_playground.py first.

CALLOUTS. A document marks a note, something Sabline refuses, or a problem
known and not yet closed with a block quote whose first line is [!NOTE],
[!REFUSES] or [!KNOWN-OPEN], or which starts **Note.**, **Refuses.** or
**Known open.**; docs_markdown.py's docstring gives the syntax in full.

WHERE A PAGE IS WRITTEN. Each page is written three times: at the top of
the site, under latest/, and under the release's major.minor (8.3.1 writes
8.3/). The top of the site holds the newest release's pages themselves, not
redirects to latest/: the addresses published before 8.3.1 - in error
messages, in attestations and receipts already signed, in the READMEs -
name pages at the top, and an anchor such as errors.html#E700, or llms.txt
byte for byte, survives only on a real page. latest/ is the address that
names the newest release by that word, and major.minor/ keeps naming its
release after the next one ships: a build rewrites latest/ and its own
major.minor/, and never removes another major.minor/. The copies of a page
differ only in where their links to the pages kept at the top alone point
(the playground, the two predicate types, the version index), and every
copy's canonical link names the page at the top.

FOR SEARCH (8.7). Every page has its own <title> and meta description - a
docs/*.md page gives its description in a `<!-- description: ... -->` line,
and one that does not is described by its first paragraph - and a canonical
link: a page at the top names itself, and its copies in latest/ and
major.minor/ name it too, since they are the same page. The top alone also
gets robots.txt, which lets the named crawlers and every other one in;
sitemap.xml, every page at the top with the date its sources last changed in
git (or today, for a source changed and not yet committed); the IndexNow key
file, which indexnow.yml's ping is checked against; the paper, with a landing
page carrying the citation_* tags Google Scholar reads; and the image
OpenGraph cards show. check_site.py holds all of it, and fails when a page's
sources change in a commit that does not also rewrite sitemap.xml.
"""
from __future__ import annotations

import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sabline  # noqa: E402
from docs_markdown import Slugger, render  # noqa: E402
from sabline.lexer import KEYWORDS, MASTER_RE  # noqa: E402

OUT = HERE / "docs"
ASSETS = HERE / "site"
REPO = "https://github.com/gowrishankar-infra/sabline-lang"
SPEC_REPO = "https://github.com/gowrishankar-infra/sabline-spec"
PAGE_BUDGET = 100_000             # bytes of HTML a page may have (check_site)
CHANGELOG_BODY = 78_000           # bytes of changelog text on one page

# The site's origin, as the package names it (sabline.SITE, from 8.3.0).
SITE: str = sabline.SITE.rstrip("/")
VERSION: str = sabline.VERSION
VERSION_DIR = ".".join(VERSION.split(".")[:2])
VERSION_NAME = re.compile(r"^\d+\.\d+$")

# a link written for the site's own address, kept in a page until the tree
# it is written into says where that is; see resolve_links()
INTERNAL = "sabline-docs-internal:"
ROOT_ONLY = {"playground.html", "versions.html", "capability/v1/index.html",
             "capability/v1/schema.json", "receipt/v1/index.html",
             "receipt/v1/schema.json", "papers/index.html",
             "papers/sabline.html", "papers/sabline.pdf"}

# The words every listing opens with (8.7): the homepage, README.md's first
# screen, and each package's description. check_listings.py holds them all
# to these two, so they cannot drift apart again.
HEADLINE = "Run code an AI wrote without handing it everything you can reach."
SUBLINE = ("Each function declares what it may touch. You grant the run one "
           "folder, one host or a number of calls, and the runtime refuses "
           "anything else the moment it's tried.")
AUTHOR = "Palakurthi Gowri Shankar"

# The guides and the comparisons, in the order the sidebar and the homepage
# list them (8.7). A guide is docs/guide-*.md, read as a test by
# check_docs.py; a comparison is docs/compare-*.md.
GUIDES = ["guide-network-access.md", "guide-before-it-runs.md",
          "guide-everything-or-nothing.md", "guide-lethal-trifecta.md",
          "guide-secrets-env.md"]
COMPARISONS = ["compare-deno.md", "compare-wasi.md", "compare-camel.md",
               "compare-python-sandbox.md", "compare-ailang.md"]
# the incident catalogue's flagship page, written by build_incidents.py only
# once every entry has been checked against its sources by a person
FLAGSHIP = "replayed.md"

# The crawlers robots.txt names. Every other one is let in too, as it was
# before robots.txt existed; naming these says the site means it.
CRAWLERS = ("Googlebot", "Bingbot", "OAI-SearchBot", "PerplexityBot",
            "ClaudeBot")
# IndexNow (8.7): the key a ping from indexnow.yml is checked against. It is
# public by design - the protocol proves ownership by the file at the site's
# root holding it - so it is here, and written as <key>.txt at the top.
INDEXNOW_KEY = "27f58369084ca5db3a8438eb1dfc254a"

# The paper (8.7): paper/sabline.pdf is built from paper/arxiv/sabline.tex
# (paper/SUBMITTING.md's pdflatex steps) and copied here to papers/, where
# Google Scholar can find it beside a landing page. PAPER_DATE is the day
# that PDF was built. PAPER_DOI is Zenodo's concept DOI for the paper, which
# resolves to its newest version there, so it stays right when a rebuilt PDF
# is uploaded as a new version (paper/SUBMITTING.md section 8); the landing
# page carries it as citation_doi.
PAPER_SOURCE = "paper/sabline.md"
PAPER_PDF = "paper/sabline.pdf"
PAPER_DATE = "2026-09-25"
PAPER_DOI = "10.5281/zenodo.22952528"


def earlier_sites() -> tuple[str, ...]:
    """Where the site was before sabline.dev, as sabline names it - the
    project's GitHub Pages address until 8.3, and velaris-lang.dev until the
    rename in 8.6. A link a document still writes to one of these is a link
    into this site, and is made relative like any other."""
    found: set[str] = set()
    predicates = getattr(sabline, "predicates", None)
    earlier = getattr(predicates, "EARLIER_SITES", None)
    if isinstance(earlier, str):          # one address, until 8.6
        earlier = (earlier,)
    for site in earlier or ():
        if isinstance(site, str):
            found.add(site.rstrip("/"))
    card_site = sabline.REFERENCE_URL.rsplit("/", 1)[0]
    if card_site != SITE:
        found.add(card_site)
    return tuple(sorted(found))


def predicate_types(kind: str) -> tuple[str, ...]:
    """The predicate type sabline writes for `kind` (CAPABILITY or RECEIPT),
    then every earlier spelling it still reads as that type (8.3.0)."""
    spellings = getattr(sabline, f"{kind}_PREDICATE_TYPES", None)
    if spellings:
        return tuple(str(s) for s in spellings)
    return (str(getattr(sabline, f"{kind}_PREDICATE_TYPE")),)


def internal(path: str, fragment: str = "") -> str:
    return INTERNAL + path + (f"#{fragment}" if fragment else "")


# ---------------------------------------------------------------------------
# code: Sabline by the lexer's own token classes, anything else as text

LABELS = {"vel": "Sabline", "sabline": "Sabline", "sh": "Shell",
          "bash": "Shell", "shell": "Shell", "console": "Console",
          "python": "Python", "py": "Python", "json": "JSON", "yaml": "YAML",
          "yml": "YAML", "toml": "TOML", "javascript": "JavaScript",
          "js": "JavaScript", "text": "Text", "rego": "Rego", "html": "HTML",
          "diff": "Diff", "ini": "INI", "dockerfile": "Dockerfile",
          "powershell": "PowerShell", "typescript": "TypeScript"}
# the lexer's TOKEN_SPEC names; a name not here is shown unstyled
TOKEN_CLASSES = {"COMMENT": "c", "STRING": "s", "NUMBER": "n", "FLOAT": "n",
                 "KEYWORD": "k"}


def sabline_tokens(code: str) -> list[tuple[str, str]]:
    """(the lexer's class for it, the text) for every piece of `code`, in
    order, whitespace included. MASTER_RE and KEYWORDS are sabline/lexer.py's
    own, so a keyword added there is highlighted here. A character the lexer
    refuses is a piece of class "" - an illustrative block may hold `...`."""
    out: list[tuple[str, str]] = []
    pos = 0
    while pos < len(code):
        m = MASTER_RE.match(code, pos)
        if m is None:
            out.append(("", code[pos]))
            pos += 1
            continue
        kind = m.lastgroup or ""
        if kind == "IDENT" and m.group() in KEYWORDS:
            kind = "KEYWORD"
        out.append((kind, m.group()))
        pos = m.end()
    return out


def reads_as_sabline(code: str) -> bool:
    """An unlabelled block is shown as Sabline when the lexer reads all of it
    and it holds a keyword (SPEC.md's indented examples)."""
    tokens = sabline_tokens(code)
    return (all(kind for kind, _ in tokens)
            and any(kind == "KEYWORD" for kind, _ in tokens))


def highlight_sabline(code: str) -> str:
    parts = []
    for kind, text in sabline_tokens(code):
        cls = TOKEN_CLASSES.get(kind)
        escaped = html.escape(text, quote=False)
        parts.append(f'<span class="{cls}">{escaped}</span>' if cls else escaped)
    return "".join(parts)


def highlight(info: str, code: str) -> tuple[str, str]:
    word = info.lower()
    if word in ("vel", "sabline") or (not word and reads_as_sabline(code)):
        return "Sabline", highlight_sabline(code)
    return LABELS.get(word, info or "Text"), html.escape(code, quote=False)


def code_block(info: str, code: str) -> str:
    """A code block as docs_markdown.py writes one."""
    label, inner = highlight(info, code)
    return ('<div class="code"><div class="code-bar"><span class="code-lang">'
            f'{html.escape(label)}</span></div><pre tabindex="0"><code>'
            f'{inner}</code></pre></div>')


def heading(level: int, text: str, slugger: Slugger) -> str:
    ident = slugger.slug(text)
    anchor = ("" if level == 1 else f' <a class="anchor" href="#{ident}" '
              'aria-label="Link to this section">#</a>')
    return f'<h{level} id="{ident}">{html.escape(text)}{anchor}</h{level}>'


def table(head: list[str], rows: list[str]) -> str:
    """rows are whole <tr> elements"""
    cells = "".join(f"<th>{h}</th>" for h in head)
    return ('<div class="table-wrap" tabindex="0"><table>\n'
            f"<thead><tr>{cells}</tr></thead>\n<tbody>\n"
            + "\n".join(rows) + "\n</tbody></table></div>")


# ---------------------------------------------------------------------------
# a page's outline: its table of contents, and what search reads

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}
TEXT_BLOCKS = {"p", "li", "tr", "dt", "dd", "h1", "h2", "h3", "h4", "h5", "h6"}


class Outline(HTMLParser):
    """Every heading with an id, as (level, id, text), and every paragraph,
    list item and table row as (the id it is under, its text): a row with an
    id of its own is under that id. Code blocks and heading anchors are not
    read."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[tuple[int, str, str]] = []
        self.texts: list[tuple[str, str]] = []
        self.stack: list[tuple[str, str, list[str]]] = []
        self.skipping: list[str] = []
        self.under = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        classes = a.get("class", "").split()
        if self.skipping:
            if tag not in VOID:
                self.skipping.append(tag)
            return
        if tag == "pre" or "anchor" in classes or "code-bar" in classes:
            self.skipping.append(tag)
            return
        if tag in TEXT_BLOCKS:
            self.stack.append((tag, a.get("id", ""), []))
        elif tag in ("td", "th", "br") and self.stack:
            self.stack[-1][2].append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.skipping:
            if self.skipping[-1] == tag:
                self.skipping.pop()
            return
        if tag in TEXT_BLOCKS and self.stack and self.stack[-1][0] == tag:
            name, ident, parts = self.stack.pop()
            text = " ".join("".join(parts).split())
            if re.fullmatch(r"h[1-6]", name):
                if ident:
                    self.headings.append((int(name[1]), ident, text))
                    self.under = ident
            elif text:
                self.texts.append((ident if name == "tr" and ident
                                   else self.under, text))

    def handle_data(self, data: str) -> None:
        if not self.skipping and self.stack:
            self.stack[-1][2].append(data)


def outline(body: str) -> Outline:
    o = Outline()
    o.feed(body)
    o.close()
    return o


# ---------------------------------------------------------------------------
# the pages

@dataclass
class Page:
    path: str                   # where it is in a tree: "tutorial.html"
    title: str                  # its h1, and its <title>
    body: str                   # the HTML inside <main>
    source: str                 # what it is made from, for its footer
    toc_levels: tuple[int, ...] = (2, 3)
    root_only: bool = False
    wide: bool = False
    description: str = ""       # its meta description; else its first paragraph
    head_title: str = ""        # its <title>, where not "title - Sabline x.y.z"
    head_extra: str = ""        # more of <head>: the paper's citation_* tags
    sources: tuple[str, ...] = ()   # what its sitemap date is read from


# (section, the page it opens on or None, [(page, label)])
Section = tuple[str, "str | None", list[tuple[str, str]]]

DOCUMENTS = [("TUTORIAL.md", "tutorial.html"), ("SPEC.md", "spec.html"),
             ("THREAT_MODEL.md", "threat-model.html"),
             ("EMBEDDING.md", "embedding.html"),
             ("STABILITY.md", "stability.html"),
             ("SECURITY.md", "security.html")]
# a docs/*.md page's section; one not named here goes under Threat model,
# those in DOCS_ORDER first and in that order, the rest by name
DOCS_SECTION = {"floats.md": "Floats", "renamed.md": "Spec",
                "embedding-limit.md": "Embedding", "receipts.md": "Embedding"}
DOCS_ORDER = ["confinement.md", "runner.md", "eval.md",
              "structurally-impossible.md", "known-open.md", "incidents.md",
              "agentdojo.md", "roundtrip.md", "competitors.md",
              "competitors-scenarios.md",
              "competitors-evidence-1.md",
              "competitors-evidence-2.md", "competitors-evidence-3.md",
              "crosswalk.md"]
MISSING: list[str] = []         # links to a repository file that is not here


def source_pages() -> dict[str, str]:
    """{repository path of a rendered document: its page}"""
    found = dict(DOCUMENTS)
    for md in sorted((HERE / "docs").glob("*.md")):
        found[f"docs/{md.name}"] = md.stem + ".html"
    found["CHANGELOG.md"] = "changelog.html"
    found["LLM.md"] = "llms.txt"
    return found


def resolver(source: str, known: set[str]) -> Callable[[str], str]:
    """How a link written in `source` is written on its page: a link into this
    site (a document, the site's address, an earlier address) as the page it
    names, resolved per tree; a link to another file of this repository as
    that file on GitHub; anything else as written."""
    folder = posixpath.dirname(source)
    documents = source_pages()
    origins = (SITE,) + earlier_sites()

    def link(href: str) -> str:
        href = href.strip()
        if not href:
            return href
        if href.startswith("#"):
            return (internal("CHANGELOG.md", href[1:])
                    if source == "CHANGELOG.md" else href)
        for origin in origins:
            if href == origin or href.startswith((origin + "/", origin + "#")):
                path, _, frag = href[len(origin):].lstrip("/").partition("#")
                path = path or "index.html"
                if path.endswith("/"):
                    path += "index.html"
                elif path not in known and f"{path}/index.html" in known:
                    path += "/index.html"
                return internal(path, frag)
        if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", href) or href.startswith("//"):
            return href
        path, _, frag = href.partition("#")
        repo_path = posixpath.normpath(posixpath.join(folder, path))
        if repo_path in documents:
            if repo_path == "CHANGELOG.md":
                return internal("CHANGELOG.md", frag)
            if repo_path == "LLM.md":
                return internal("llms.txt")
            return internal(documents[repo_path], frag)
        local = HERE / repo_path
        if not local.exists():
            MISSING.append(f"{source}: {href}")
        kind = "tree" if local.is_dir() else "blob"
        return f"{REPO}/{kind}/main/{repo_path}" + (f"#{frag}" if frag else "")

    return link


DESCRIBED = re.compile(r"^<!--\s*description:\s*(.+?)\s*-->\s*$", re.M)


def markdown_page(source: str, path: str, known: set[str]) -> Page:
    text = (HERE / source).read_text(encoding="utf-8")
    done = render(text, link=resolver(source, known), highlight=highlight)
    title = done.title or Path(source).stem
    m = DESCRIBED.search(text)
    return Page(path, title, done.html, source,
                description=m.group(1) if m else "")


def changelog_pages(known: set[str]) -> tuple[list[Page], dict[str, str]]:
    """CHANGELOG.md, one page per major version, a major version that will
    not fit on one page split into as few as fit, and an index page. The
    ids are GitHub's for the whole document, so CHANGELOG.md#anchor finds
    the same heading; the second value maps each id to its page."""
    lines = (HERE / "CHANGELOG.md").read_text(encoding="utf-8").split("\n")
    preamble: list[str] = []
    entries: list[tuple[str, list[str]]] = []
    fence = ""
    for line in lines:
        m = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if m and (not fence or m.group(1).startswith(fence)):
            fence = "" if fence else m.group(1)
        if not fence and line.startswith("## "):
            entries.append((line[3:].split()[0], [line]))
        elif entries:
            entries[-1][1].append(line)
        else:
            preamble.append(line)
    slugger = Slugger()
    link = resolver("CHANGELOG.md", known)
    head = render("\n".join(preamble), link=link, highlight=highlight,
                  slugger=slugger)
    rendered = []                  # (version, entry id, heading text, html)
    for version, body in entries:
        done = render("\n".join(body), link=link, highlight=highlight,
                      slugger=slugger)
        first = done.headings[0]
        rendered.append((version, first.id, first.text, done.html))

    groups: dict[str, list[tuple[str, str, str, str]]] = {}
    for entry in rendered:
        groups.setdefault(entry[0].split(".")[0], []).append(entry)
    pages: list[Page] = []
    anchors: dict[str, str] = {h.id: "changelog.html" for h in head.headings}
    index_parts: list[tuple[str, str, list[tuple[str, str, str, str]]]] = []
    for major, group in groups.items():
        total = sum(len(e[3]) for e in group)
        count = 1
        while True:
            parts: list[list[tuple[str, str, str, str]]] = []
            part: list[tuple[str, str, str, str]] = []
            size = 0
            target = total / count
            for e in group:
                if part and size + len(e[3]) > target * 1.08 \
                        and len(parts) < count - 1:
                    parts.append(part)
                    part, size = [], 0
                part.append(e)
                size += len(e[3])
            parts.append(part)
            if all(sum(len(e[3]) for e in p) <= CHANGELOG_BODY for p in parts) \
                    or count >= len(group):
                break
            count += 1
        for n, part in enumerate(parts, 1):
            path = (f"changelog-{major}.html" if len(parts) == 1
                    else f"changelog-{major}-{n}.html")
            label = (f"{major}.x" if len(parts) == 1
                     else f"{major}.x: {part[0][0]} to {part[-1][0]}")
            title = f"Changelog: {label}"
            intro = (f'<h1 id="changelog">{html.escape(title)}</h1>\n'
                     '<p class="lead">Every release of this major version, '
                     'newest first, as <a href="' + internal("changelog.html")
                     + '">CHANGELOG.md</a> records it.</p>')
            span = (f"{part[0][0]}" if len(part) == 1
                    else f"{part[-1][0]} to {part[0][0]}")
            pages.append(Page(path, title,
                              intro + "\n" + "\n".join(e[3] for e in part),
                              "CHANGELOG.md", toc_levels=(2,),
                              description=f"What changed in Sabline {span}, "
                                          "release by release, newest first, "
                                          "as CHANGELOG.md records it."))
            for e in part:
                for _level, ident, _text in outline(e[3]).headings:
                    anchors[ident] = path
            index_parts.append((path, label, part))

    slug = Slugger()
    body = [heading(1, "Changelog", slug),
            '<p class="lead">Every release of Sabline, newest first, one page '
            "for each major version. The text is CHANGELOG.md's.</p>"]
    body.append(re.sub(r"<h1[^>]*>.*?</h1>", "", head.html, flags=re.S))
    for path, label, part in index_parts:
        body.append(heading(2, label, slug))
        body.append("<ul>" + "\n".join(
            f'<li><a href="{internal(path, e[1])}">{html.escape(e[2])}</a></li>'
            for e in part) + "</ul>")
    index = Page("changelog.html", "Changelog", "\n".join(body),
                 "CHANGELOG.md", toc_levels=(2,))
    return [index] + pages, anchors


def fn_signature(f: Any) -> str:
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


# One line for each library that talks to a service (8.5): what it reaches,
# the grant it needs, and the example that uses it. None of them calls Python.
LIBRARY_NOTES = {
    "azure.vel": (
        "Azure Resource Manager over REST: GET, PUT, PATCH and DELETE on "
        "management.azure.com, paging, ARM's error shape. The bearer token is "
        "the caller's, a Secret of Text. Grant "
        "<code>net:management.azure.com:443</code> and <code>declassify"
        "</code>; example: <code>examples/ops/azure_groups.vel</code>."),
    "k8s.vel": (
        "The Kubernetes API over REST: list, get and watch-once for the core "
        "resources, the in-cluster service-account token read as a Secret. "
        "It reads; every function that changes the cluster begins "
        "<code>write_</code>. Grant your API server's host and <code>"
        "declassify</code>; example: <code>examples/ops/k8s_pods.vel</code>."),
    "github.vel": (
        "The GitHub REST API: repositories, issues, pull requests, check "
        "runs, releases and file contents, with paging, and the rate limit "
        "as a failure that says when it resets. Grant <code>"
        "net:api.github.com:443</code> and <code>declassify</code>; example: "
        "<code>examples/ops/github_issues.vel</code>."),
    "aws.vel": (
        "Requests signed with Signature Version 4, in Sabline, to S3 and "
        "STS. The secret key stays a Secret: the signature is one <code>"
        "hmac_sha256_chain</code> call, which the audit lists as a "
        "declassification with the reason \"hmac signature\". Grant the "
        "region's hosts, <code>clock</code> and <code>declassify</code>; "
        "example: <code>examples/ops/aws_buckets.vel</code>."),
    "rest.vel": (
        "What a program that talks to a REST API needs beside "
        "<code>http.vel</code>: a request asked again within a bound, JSON "
        "bodies, headers from a map, the items of a JSON list (8.5)."),
}


def library_page() -> Page:
    slug = Slugger()
    body = [heading(1, "Standard library", slug),
            '<p class="lead">Every function below is written in Sabline, in '
            "stdlib/, and read onto this page by the compiler itself, "
            "contracts included. A violated <code>requires</code> is a "
            "compile error at your call site.</p>"]
    for mod in sorted((HERE / "stdlib").glob("*.vel")):
        try:
            got, _ = sabline.load_program(str(mod))
        except Exception:
            continue
        rows = []
        for f in got:
            if not (f.src_file and f.src_file.endswith(mod.name)):
                continue
            if mod.name != "std.vel":
                f.name = f"{mod.stem}.{f.name}"
            row = [f'<div class="fn"><p class="sig">'
                   f"{highlight_sabline(fn_signature(f))}</p>"]
            for word, promises in (("requires", f.requires),
                                   ("ensures", f.ensures)):
                for expr, _ in promises:
                    row.append('<p class="contract">' + highlight_sabline(
                        f"{word} {sabline.expr_str(expr)}") + "</p>")
            rows.append("".join(row) + "</div>")
        if rows:
            body.append(heading(2, mod.name, slug))
            if mod.name in LIBRARY_NOTES:
                body.append(f"<p>{LIBRARY_NOTES[mod.name]}</p>")
            body.extend(rows)
    body.append(heading(2, "Built-in functions", slug))
    rows = []
    for name, info in sorted(sabline.BUILTINS.items()):
        eff = ", ".join(sorted(info["effects"])) or "pure"
        fall = (' <span class="ecode">or fail</span>'
                if name in sabline.FALLIBLE_BUILTINS else "")
        rows.append(f"<tr><td><code>{name}</code>{fall}</td><td>{eff}</td>"
                    f"<td>{html.escape(', '.join(info['types']))}</td>"
                    f"<td>{html.escape(cast(str, info['ret']))}</td></tr>")
    body.append(table(["Name", "Effects", "Takes", "Gives"], rows))
    body.append("<p>get on a map can also fail (missing key); get_or never "
                "fails.</p>")
    return Page("library.html", "Standard library", "\n".join(body),
                "stdlib/", wide=True)


def errors_page() -> Page:
    # The rows are sabline.ERROR_TABLE, the one list of codes, which
    # check_library.py holds against every code Sabline can give; the
    # message templates are scraped from the source beside it. Each row
    # has an id, because `sabline check --sarif` points a help URI at it.
    src = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((HERE / "sabline").glob("*.py")))
    found: dict[str, str] = {}
    for m in re.finditer(
            r'(?:SablineError|Problem)\(\s*"(E\d+)",\s*'
            r'((?:f?"(?:[^"\\\\]|\\\\.)*"\s*)+)', src):
        code = m.group(1)
        msg = " ".join(re.findall(r'f?"((?:[^"\\\\]|\\\\.)*)"', m.group(2)))
        msg = re.sub(r"\s+", " ", msg).strip()
        if code not in found or len(msg) > len(found[code]):
            found[code] = msg
    slug = Slugger()
    body = [heading(1, "Error reference", slug),
            '<p class="lead">Every error Sabline can give, from the error table '
            "in the compiler source, which the test suite holds against every "
            "code the compiler can raise, so this page cannot go stale. In the "
            "message templates, braces are filled with your program&rsquo;s "
            "names and values; every error also arrives with numbered fixes, "
            "and as JSON with <code>--json</code>.</p>"]
    body.append(table(["Code", "What it means", "Message template"], [
        f'<tr id="{code}"><td class="ecode">{code}</td>'
        f"<td>{html.escape(meaning)}</td>"
        f"<td>{html.escape(found.get(code, ''))}</td></tr>"
        for code, meaning in sorted(sabline.ERROR_TABLE.items())]))
    body.append(heading(2, "Findings that are not compile errors", slug))
    body.append("<p>What <code>sabline check --sarif</code>, <code>proofs "
                "--sarif</code>, <code>audit --sarif</code> and "
                "<code>capabilities check --sarif</code> report besides the "
                "codes above, at the level SARIF reports each at.</p>")
    body.append(table(["Rule", "Level", "What it means"], [
        f'<tr id="{rule}"><td class="ecode">{rule}</td><td>{level}</td>'
        f"<td>{html.escape(meaning)}</td></tr>"
        for rule, level, meaning in sabline.SARIF_FINDINGS]))
    # STABILITY.md rule 3: a code is never reused, and one that is no
    # longer given stays listed here with what it meant
    body.append(heading(2, "Removed codes", slug))
    if sabline.REMOVED_ERRORS:
        body.append(table(["Code", "What it meant", "Removed in"], [
            f'<tr id="{code}"><td class="ecode">{code}</td>'
            f"<td>{html.escape(meaning)}</td><td>{gone}</td></tr>"
            for code, meaning, gone in sabline.REMOVED_ERRORS]))
    else:
        body.append("<p>None. A code that stops being given is listed here, "
                    "and is never given again for anything else "
                    '(<a href="' + internal("stability.html") + '">'
                    "STABILITY.md</a>).</p>")
    return Page("errors.html", "Error reference", "\n".join(body),
                "sabline.ERROR_TABLE", wide=True)


START_INSTALL = """pip install sabline-lang
sabline doctor
sabline new hello && cd hello && sabline main.vel"""

START_DEMO = """pip install sabline-lang
sabline demo"""

# what `sabline demo` prints, shortened; check_demo.py holds each line here to
# be the beginning of a line the command writes
START_DEMO_OUTPUT = """1. A script that reads ./.env and posts it to a webhook. No budget is given, so it gets io:

   $ sabline agent_script.vel --receipt refused.receipt.json
   line 6: check read_file("./.env") {
   error[E310] 'read_file' needs the 'fs' effect, which this run does not allow (it allows: io)
   exit 1. receipt: refused; E310 (fs) at line 6; grants used: none

2. The same task inside a budget: one file to read, one directory to write, no network:

   $ sabline inside_budget.vel --allow io,fs:read:settings.txt,fs:write:out --receipt allowed.receipt.json
   3 setting(s); the report is in out/report.txt
   exit 0. receipt: ok; grants used: fs:read:./settings.txt x1, fs:write:./out x1"""

START_EXAMPLE = """fn discount(price: Int) -> Int
    requires price >= 0
    ensures result >= 0
{
    return price - 10
}"""

START_REFUSED = """error[E700] promise cannot be kept: 'discount' ensures result >= 0
  proven without running the program: price = 5 gives result = -5"""


def start_page() -> Page:
    """The landing page (8.7): what Sabline is for in two sentences, who it is
    for, one command that shows a refusal, and then one route for each of
    three readers - with the guides, the comparisons, the paper and, once it
    is published, the incident catalogue's flagship page linked from here."""
    slug = Slugger()

    def route(ident: str, title: str, text: str,
              links: list[tuple[str, str]]) -> str:
        slug.seen[ident] = 0
        anchors = "".join(f'<a href="{href}">{html.escape(label)}</a>'
                          for href, label in links)
        return (f'<section class="route" aria-labelledby="{ident}">'
                f'<h2 id="{ident}">{html.escape(title)}</h2><p>{text}</p>'
                f'<p class="route-links">{anchors}</p></section>')

    def listed(names: list[str]) -> str:
        items = []
        for name in names:
            source = HERE / "docs" / name
            if not source.is_file():
                continue
            m = re.search(r"^# (.+)$", source.read_text(encoding="utf-8"), re.M)
            title = m.group(1) if m else name
            items.append(f'<li><a href="{internal(name[:-3] + ".html")}">'
                         f"{html.escape(title)}</a></li>")
        return "<ul>" + "".join(items) + "</ul>"

    flagship = (HERE / "docs" / FLAGSHIP).is_file()
    body = [
        heading(1, "Sabline", slug),
        f'<p class="lead">{html.escape(HEADLINE)}</p>',
        f"<p>{html.escape(SUBLINE)}</p>",
        f'<p>Formerly <a href="{internal("velaris.html")}">Velaris</a>: the '
        "project was renamed in 8.6.0, and everything written for the old "
        "name still works in 8.x.</p>",
        heading(2, "Who it is for", slug),
        "<p>The person about to run a program a model wrote - on a laptop, in "
        "CI, behind an MCP server - who wants what it can touch to be bounded "
        "by what they said, not by what the program says about itself. It "
        "bounds programs written in Sabline, not a Python or shell script the "
        "same model might write instead.</p>",
        heading(2, "See it refuse, in one command", slug),
        '<p>No arguments, no network, under a minute. It writes the kind of '
        "script an agent writes - read <code>./.env</code>, post it to a "
        "webhook - runs it, and shows the refusal, its line and the run's "
        "receipt; then the same task inside a budget, and what differs between "
        "the two receipts. It writes what it runs, and reads nothing of "
        "yours.</p>",
        code_block("sh", START_DEMO),
        code_block("text", START_DEMO_OUTPUT),
        "<p>It is not a security boundary by itself: an interpreter in the "
        "program's own process enforces the budget. From 8.4 the operating "
        "system is asked to hold the same budget under it - fully on Linux, "
        "partly on macOS and on Windows. The "
        f'<a href="{internal("threat-model.html")}">threat model</a> says '
        "what that leaves open.</p>",
        '<div class="routes">',
        route("try-it", "Try it",
              "Install it and work through the tutorial, about an hour. The "
              "playground runs the same compiler in a browser, with nothing "
              "installed.",
              [(internal("tutorial.html"), "The tutorial"),
               (internal("playground.html"), "The playground")]),
        route("review-it", "Review it before running agent code",
              "For a person about to run a program a model wrote. The threat "
              "model says what Sabline defends against and what it does not; "
              "<code>sabline audit</code> says what one program can touch, "
              "before it runs.",
              [(internal("threat-model.html"), "The threat model"),
               (internal("embedding.html", "the-audit-format"), "The audit")]),
        route("for-a-model", "For a model",
              "The whole language as one plain-text page, written to be given "
              "to a model before it writes Sabline. Every compiler error "
              "names it.",
              [(internal("llms.txt"), "llms.txt")]),
        "</div>",
        heading(2, "Guides", slug),
        "<p>Each starts from how people describe the problem, says first what "
        "it does not do, and shows a refusal that runs on every push.</p>",
        listed(GUIDES),
        heading(2, "Compared, losses first", slug),
        "<p>Each comparison opens with where the other tool is ahead of "
        "Sabline.</p>",
        listed(COMPARISONS),
        heading(2, "Incidents", slug),
        ("<p>Real incidents, examined, and replayed in Sabline where there "
         "is a shape to run - what a budget stopped, what it did not, and "
         "why the rest have no replay: "
         f'<a href="{internal(FLAGSHIP[:-3] + ".html")}">the incidents, '
         "examined and replayed</a>, and the "
         f'<a href="{internal("incidents.html")}">catalogue</a>.</p>'
         if flagship else
         f'<p>The <a href="{internal("incidents.html")}">incident '
         "catalogue</a>: publicly reported incidents in this lane, each with "
         "whether a program of the same shape is refused.</p>"),
        heading(2, "The paper", slug),
        f'<p><a href="{internal("papers/sabline.html")}">'
        f"{html.escape(paper_meta()['title'])}</a> - the design, the "
        "implementation, and where other work is ahead. "
        f'<a href="{internal("papers/sabline.pdf")}">PDF</a>.</p>',
        heading(2, "Install", slug),
        code_block("sh", START_INSTALL),
        "<p>A standalone executable for Windows, Linux and macOS is attached "
        f'to every <a href="{REPO}/releases">release</a>.</p>',
        heading(2, "What a signature says", slug),
        "<p>The promise below is checked for every input before the program "
        "runs, and the compiler hands back the input that breaks it:</p>",
        code_block("vel", START_EXAMPLE),
        code_block("text", START_REFUSED),
        heading(2, "Where things are", slug),
        "<ul>",
        f'<li><a href="{internal("spec.html")}">Language reference</a>: what '
        "the language means, precisely.</li>",
        f'<li><a href="{internal("library.html")}">Standard library</a> and '
        f'<a href="{internal("errors.html")}">errors</a>: generated from the '
        "compiler.</li>",
        f'<li><a href="{internal("floats.html")}">Floats</a>: why the prover '
        "works in IEEE-754 and not in real numbers.</li>",
        f'<li><a href="{internal("embedding.html")}">Embedding</a>: Sabline as '
        "a library, a door, an MCP server and a GitHub Action.</li>",
        f'<li><a href="{internal("stability.html")}">Stability</a> and the '
        f'<a href="{internal("changelog.html")}">changelog</a>: what may '
        "change, and what did.</li>",
        "</ul>",
    ]
    return Page("index.html", "Sabline", "\n".join(body),
                "build_docs.py", wide=True, description=SUBLINE,
                head_title=f"Sabline: {HEADLINE[0].lower()}{HEADLINE[1:-1]}",
                sources=("build_docs.py",))


# ---------------------------------------------------------------------------
# the paper, where Google Scholar can find it (8.7)

def paper_meta() -> dict[str, str]:
    """The paper's title, author and abstract (as Markdown), read from
    paper/sabline.md: its front matter and its `## Abstract` section."""
    text = (HERE / PAPER_SOURCE).read_text(encoding="utf-8")
    front = text.split("---", 2)[1]
    title = re.search(r'^title:\s*"(.+)"\s*$', front, re.M)
    author = re.search(r'^author:\s*"(.+)"\s*$', front, re.M)
    abstract = re.search(r"^## Abstract\s*\n(.*?)(?=^## )", text, re.M | re.S)
    if not (title and author and abstract):
        raise SystemExit(f"{PAPER_SOURCE}: no title, author or ## Abstract")
    return {"title": title.group(1), "author": author.group(1),
            "abstract": abstract.group(1).strip()}


def paper_pages(known: set[str]) -> list[Page]:
    """papers/sabline.html, the landing page Google Scholar reads - its
    citation_* tags, the title, the author, the abstract visible, and the PDF
    beside it - and papers/index.html, which lists it."""
    meta = paper_meta()
    slug = Slugger()
    abstract = render(meta["abstract"], link=resolver(PAPER_SOURCE, known),
                      highlight=highlight).html
    family, given = meta["author"].split(" ", 1)
    scholar_date = PAPER_DATE.replace("-", "/")
    tags = [("citation_title", meta["title"]),
            ("citation_author", f"{family}, {given}"),
            ("citation_publication_date", scholar_date),
            ("citation_pdf_url", f"{SITE}/papers/sabline.pdf"),
            ("citation_abstract_html_url", f"{SITE}/papers/sabline.html"),
            ("citation_technical_report_institution", "sabline.dev"),
            ("citation_language", "en")]
    if PAPER_DOI:
        tags.append(("citation_doi", PAPER_DOI))
    head = "\n".join(f'<meta name="{n}" content="{html.escape(v)}">'
                     for n, v in tags)
    doi = (f'<li>DOI: <a href="https://doi.org/{html.escape(PAPER_DOI)}">'
           f"{html.escape(PAPER_DOI)}</a></li>" if PAPER_DOI else "")
    landing = [
        heading(1, meta["title"], slug),
        f'<p class="lead">{html.escape(meta["author"])}</p>',
        f"<p>Preprint, {PAPER_DATE}. Not yet peer-reviewed or on arXiv.</p>",
        f'<ul><li><a href="{internal("papers/sabline.pdf")}">The PDF</a></li>'
        f'<li><a href="{REPO}/blob/main/{PAPER_SOURCE}">The source, on '
        f"GitHub</a></li>{doi}</ul>",
        heading(2, "Abstract", slug),
        abstract,
        heading(2, "Cite it", slug),
        code_block("text",
                   f"@techreport{{palakurthi2026sabline,\n"
                   f"  author      = {{{family}, {given}}},\n"
                   f"  title       = {{{meta['title']}}},\n"
                   f"  institution = {{sabline.dev}},\n"
                   f"  year        = {{{PAPER_DATE[:4]}}},\n"
                   + (f"  doi         = {{{PAPER_DOI}}},\n" if PAPER_DOI
                      else "")
                   + f"  url         = {{{SITE}/papers/sabline.pdf}}\n}}"),
    ]
    index = [
        heading(1, "Papers", slug),
        "<p>Writing about Sabline by the people who build it, as PDFs with a "
        "landing page each.</p>",
        f'<ul><li><a href="{internal("papers/sabline.html")}">'
        f"{html.escape(meta['title'])}</a>, {html.escape(meta['author'])}, "
        f"preprint, {PAPER_DATE}.</li></ul>",
    ]
    first = re.sub(r"<[^>]+>", "", abstract)
    first = html.unescape(" ".join(first.split()))
    described = first if len(first) <= 160 else (
        first[:157].rsplit(" ", 1)[0] + " ...")
    return [Page("papers/sabline.html", meta["title"], "\n".join(landing),
                 PAPER_SOURCE, root_only=True, description=described,
                 head_extra=head, sources=(PAPER_SOURCE, PAPER_PDF)),
            Page("papers/index.html", "Papers", "\n".join(index),
                 PAPER_SOURCE, root_only=True,
                 description="Papers about Sabline, each a PDF with a "
                             "landing page: the design, the implementation "
                             "and the evaluation.",
                 sources=(PAPER_SOURCE,))]


def type_note(types: tuple[str, ...], what: str, since: str) -> str:
    if len(types) < 2:
        return ""
    return ("<p><strong>Also read as this type:</strong> "
            + ", ".join(f"<code>{html.escape(t)}</code>" for t in types[1:])
            + f", the name {what} written by sabline-lang {since} to 8.2.1 "
            "carry; that address redirects here.</p>")


def capability_page() -> Page:
    """The page an in-toto predicate type URL resolves to. The definition
    is sabline-spec SPEC.md section 8.5; the schema beside this page is
    sabline-spec's schemas/capability-predicate.v1.schema.json, byte for
    byte, and sabline-spec's tools/check_sync.py fails if they differ."""
    types = predicate_types("CAPABILITY")
    spec = str(sabline.CAPABILITY_SPEC)
    example = """{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "examples/effects.vel",
     "digest": {"sha256": "e483365ce74a20770a1ef503f185f4de2c16b0524797408784a235e78b6baafb"}}
  ],
  "predicateType": "%s",
  "predicate": {
    "producer": {"name": "sabline-lang",
                 "uri": "https://github.com/gowrishankar-infra/sabline-lang"},
    "specification": "%s",
    "auditedAt": "2026-09-11T00:00:00Z",
    "audit": {"schema": "sabline.audit/1", "sabline_version": "%s",
              "ok": true, "effects": ["clock", "fs", "io", "rand"],
              "safe_command": "sabline <file> --allow clock,fs:read:report.txt,fs:write:report.txt,io,rand",
              "counts": {"fs": 2, "net": 0}, "prover": true,
              "...": "the rest of the audit"}
  }
}""" % (types[0], spec, VERSION)
    slug = Slugger()
    rows = [
        ("<code>subject[0]</code>", "yes", "the file audited: <code>name</code>, "
         "its path as the producer was given it, <code>/</code>-separated; "
         "<code>digest.sha256</code> of its bytes. The files it imports should "
         "follow, one subject each."),
        ("<code>predicate.audit</code>", "yes", "a <code>sabline.audit/1</code> "
         "document produced from exactly the bytes the subjects name"),
        ("<code>predicate.producer</code>", "yes", "<code>name</code> of the "
         "implementation that wrote the audit, and optionally <code>uri</code>; "
         "its version is the audit's <code>sabline_version</code>"),
        ("<code>predicate.specification</code>", "no", "the sabline-spec "
         f"version followed, as <code>{html.escape(spec)}</code>"),
        ("<code>predicate.auditedAt</code>", "no", "when the audit was made, "
         "RFC 3339 in UTC, by the producer's clock"),
        ("<code>predicate.conformance</code>", "no", "the conformance levels "
         "the producer claims (sabline-spec CONFORMANCE.md) and the corpus it "
         "ran - a claim, not evidence"),
    ]
    body = [
        '<p class="lead">An in-toto predicate type.</p>',
        heading(1, "capability/v1", slug),
        "<p>A signed statement that a named tool read these Sabline source "
        "files, byte for byte, and reports this capability surface: the effects "
        "the program declares, the paths, hosts and modules it names, and the "
        "narrowest budget to run it under.</p>",
        f"<p><strong>Predicate type:</strong> <code>{html.escape(types[0])}"
        "</code> - this page.</p>",
        type_note(types, "Statements", "4.2"),
        f'<p><strong>Schema:</strong> <a href="{internal("capability/v1/schema.json")}">'
        "schema.json</a>, JSON Schema draft 2020-12, for the predicate. "
        f'<strong>Definition:</strong> <a href="{SPEC_REPO}/blob/main/SPEC.md'
        '#85-the-audit-as-an-in-toto-predicate">sabline-spec SPEC.md section '
        "8.5</a>, dedicated to the public domain under CC0.</p>",
        heading(2, "What it is", slug),
        "<p>A <code>sabline.audit/1</code> document (sabline-spec section 8) "
        "names no file and carries no signature. This predicate type puts one "
        'inside an <a href="https://github.com/in-toto/attestation">in-toto '
        "Statement v1</a>, whose subjects are the files audited, identified by "
        "digest, so that a signed Statement says which source the audit "
        "describes, and who says so.</p>",
        code_block("json", example),
        heading(2, "Fields", slug),
        table(["Field", "Required", "Meaning"],
              [f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>"
               for a, b, c in rows]),
        heading(2, "Parsing rules", slug),
        "<p>In-toto's standard parsing rules apply. Ignore any field you do not "
        "know, in the predicate and in the audit. Fields may be added within "
        "v1; a change of meaning is a new type, <code>.../capability/v2</code>. "
        "Check that the first subject's digest is the digest of the file you "
        "mean to trust.</p>",
        heading(2, "What it does not say", slug),
        "<p>That the audit is right, that the program is safe to run, or that "
        "any runtime will enforce the budget in <code>safe_command</code>. When "
        "<code>audit.ok</code> is false, it says nothing about what the program "
        "may do. It says that the signer ran the producer on these bytes and "
        "got this audit.</p>",
        heading(2, "A producer", slug),
        "<p>sabline-lang writes Statements of this type, from 4.2:</p>",
        code_block("sh", "sabline attest program.vel --output "
                   "program.intoto.json"),
        "<p>It signs none; cosign (<code>cosign attest-blob --statement</code>) "
        "and sigstore-python sign them, as "
        f'<a href="{internal("embedding.html")}">EMBEDDING.md</a> shows. Every '
        "release of sabline-lang carries one for an example program, signed by "
        "its release workflow and verified there; "
        f'<a href="{SPEC_REPO}/blob/main/examples/capability-statement.json">'
        "sabline-spec's example</a> was written by <code>sabline attest</code>."
        "</p>",
    ]
    return Page("capability/v1/index.html", "capability/v1 predicate type",
                "\n".join(b for b in body if b), "build_docs.py",
                root_only=True,
                description="The in-toto predicate type a Sabline capability "
                            "attestation carries: what a program may touch, "
                            "as its audit states it, bound to the source by "
                            "digest.")


def receipt_page() -> Page:
    """The page the receipt/v1 predicate type URL resolves to. The definition
    is sabline-spec SPEC.md section 8.7; the schema beside this page is
    sabline-spec's schemas/receipt-predicate.v1.schema.json, byte for byte,
    and sabline-spec's tools/check_sync.py fails if they differ."""
    import hashlib
    types = predicate_types("RECEIPT")
    digest = hashlib.sha256(
        lf_bytes(HERE / "examples" / "effects.vel")).hexdigest()
    example = """{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "examples/effects.vel",
     "digest": {"sha256": "%s"}}
  ],
  "predicateType": "%s",
  "predicate": {
    "schema": "sabline.receipt/1",
    "producer": {"name": "sabline-lang", "version": "%s",
                 "uri": "https://github.com/gowrishankar-infra/sabline-lang"},
    "specification": "%s",
    "startedAt": "2026-09-14T00:00:00.000Z",
    "wall_time_ms": 41.7,
    "budget": "clock,fs:read:/work/report.txt,fs:write:/work/report.txt,io,rand",
    "run_parameters": {"seed": null, "freeze_time": null, "timeout": null,
                       "max_memory_mb": null, "max_read_bytes": 67108864,
                       "confinement": "full",
                       "confinement_reason": "the operating system holds every file, network and process limit of this budget",
                       "confinement_layers": ["landlock-abi4", "seccomp"],
                       "os_policy_sha256": "2702413c15253be6589ce6f39dbfbb129c9578d6ce62576d996f895b6faa9994"},
    "effects_used": {"clock": 1, "rand": 1, "fs": 2, "io": 4},
    "refusals": [],
    "declassifications": [],
    "exit": {"status": 0, "outcome": "ok", "code": null},
    "complete": true
  }
}""" % (digest, types[0], VERSION, sabline.RECEIPT_SPEC)
    slug = Slugger()
    rows = [
        ("<code>subject</code>", "the program that ran, by the sha256 of its "
         "text, then each file it imported, by the sha256 of its bytes - the "
         "subjects <code>sabline attest</code> writes for the same files"),
        ("<code>budget</code>", "the budget the run was given, in the budget "
         "grammar"),
        ("<code>run_parameters</code>", "<code>seed</code>, "
         "<code>freeze_time</code>, <code>timeout</code>, "
         "<code>max_memory_mb</code>, <code>max_read_bytes</code>, and what "
         "the operating system held of the run (8.4): "
         "<code>confinement</code> - <code>full</code>, <code>partial</code>, "
         "or <code>none</code> when the budget was the only boundary - with "
         "<code>confinement_reason</code>, <code>confinement_layers</code> "
         "and <code>os_policy_sha256</code>, the digest of the OS policy the "
         "budget derives"),
        ("<code>effects_used</code>", "each effect and how many operations of "
         "it the budget let through; null when the run was stopped from outside "
         "before it could say"),
        ("<code>refusals</code>", "each refusal as its code, its effect and its "
         "line, whether it stopped the run, and how many times - never the "
         "path, host or module the program named"),
        ("<code>declassifications</code>", "each declassification as the reason "
         "written in the program and its line, and how many times - never the "
         "value"),
        ("<code>exit</code>", "<code>status</code>, <code>outcome</code> (ok, "
         "refused, failed, did_not_compile, timeout, out_of_memory) and the "
         "<code>code</code> that ended it"),
        ("<code>wall_time_ms</code>, <code>startedAt</code>", "by the "
         "producer's clock"),
        ("<code>complete</code>", "false when the run was stopped from outside: "
         "what is listed happened, and a count is at least that"),
    ]
    commands = ('sabline program.vel --allow io --receipt program.receipt.json\n'
                'sabline.run(source, allow={"io"}).receipt\n'
                'POST /run  {"source": "...", "allow": ["io"], "receipt": true}')
    body = [
        '<p class="lead">An in-toto predicate type.</p>',
        heading(1, "receipt/v1", slug),
        "<p>A signed record of one run of a Sabline program: the budget it was "
        "given, every refusal and every declassification, the parameters it ran "
        "under, how it ended and how long it took - bound, by sha256, to the "
        "same source files a "
        f'<a href="{internal("capability/v1/index.html")}">capability/v1</a> '
        "attestation names. The attestation is what the program may do; the "
        "receipt is what one run of it did.</p>",
        f"<p><strong>Predicate type:</strong> <code>{html.escape(types[0])}"
        "</code> - this page.</p>",
        type_note(types, "receipts", "8.1"),
        f'<p><strong>Schema:</strong> <a href="{internal("receipt/v1/schema.json")}">'
        "schema.json</a>, JSON Schema draft 2020-12, for the predicate. "
        f'<strong>Definition:</strong> <a href="{SPEC_REPO}/blob/main/SPEC.md'
        '#87-sablinereceipt1-a-record-of-one-run">sabline-spec SPEC.md section '
        "8.7</a>, dedicated to the public domain under CC0.</p>",
        code_block("json", example),
        heading(2, "Fields", slug),
        table(["Field", "Meaning"],
              [f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in rows]),
        heading(2, "What it does not say", slug),
        "<p>It holds no value the program handled, and nothing of its output, "
        "input or arguments. It does not hide what a program controls that is "
        "not a value: its exit status, which lines it reached and how long it "
        "ran are in it, and a program that has declassified a value can choose "
        "those. A declassification's reason is text its author wrote, and "
        "nothing checks it. A signed receipt says that its signer ran this "
        "producer on these bytes and saw this run; it is no stronger than the "
        "machine it was made on, and it says nothing about any other run.</p>",
        heading(2, "A producer", slug),
        "<p>sabline-lang writes receipts from 8.1:</p>",
        code_block("text", commands),
        "<p>It signs none; they are signed as an attestation is - "
        "<code>cosign attest-blob --statement</code>, or sigstore-python's "
        "<code>sign_dsse</code> - and <code>cosign verify-blob-attestation "
        f"--type {html.escape(types[0])}</code> checks one against the "
        "program's own bytes. Every release of sabline-lang carries one for an "
        "example program, signed by its release workflow and verified there.</p>",
    ]
    return Page("receipt/v1/index.html", "receipt/v1 predicate type",
                "\n".join(b for b in body if b), "build_docs.py",
                root_only=True,
                description="The in-toto predicate type a Sabline receipt "
                            "carries: one run of a program - its budget, what "
                            "it used, what was refused and how it ended.")


def built_versions(out: Path) -> list[tuple[str, str]]:
    """(directory, the release its pages are of) for every major.minor
    directory already built under `out`, and this release's, newest first."""
    found = {VERSION_DIR: VERSION}
    if out.is_dir():
        for d in out.iterdir():
            if (d.is_dir() and VERSION_NAME.match(d.name)
                    and d.name != VERSION_DIR and (d / "index.html").is_file()):
                page = (d / "index.html").read_text(encoding="utf-8",
                                                    errors="replace")
                m = re.search(r'<meta name="sabline-version" content="([^"]+)"',
                              page)
                found[d.name] = m.group(1) if m else d.name
    return sorted(found.items(),
                  key=lambda kv: tuple(int(x) for x in kv[0].split(".")),
                  reverse=True)


def versions_page(versions: list[tuple[str, str]]) -> Page:
    slug = Slugger()
    items = [f'<li><a href="latest/index.html">latest</a>: {VERSION}, the '
             "newest release, whose pages are also the ones at the top of this "
             "site</li>"]
    for folder, release in versions:
        items.append(f'<li><a href="{folder}/index.html">{folder}</a>: '
                     f"{html.escape(release)}</li>")
    body = [heading(1, "Versions", slug),
            "<p>The documentation is built for every minor release and kept: "
            "a release rewrites its own major.minor directory and latest/, and "
            "leaves the others as they were built.</p>",
            "<ul>" + "\n".join(items) + "</ul>"]
    return Page("versions.html", "Versions", "\n".join(body), "build_docs.py",
                root_only=True)


def collect(out: Path) -> tuple[list[Page], list[Section], dict[str, str]]:
    documents = source_pages()
    known = set(documents.values()) | ROOT_ONLY | {
        "index.html", "library.html", "errors.html", "changelog.html",
        "llms.txt", "versions.html"}
    # a guide or comparison is listed under its own section, not under
    # Threat model with the rest of docs/
    placed = {n: "Guides" for n in GUIDES} | {n: "Compare" for n in COMPARISONS}
    placed["velaris.md"] = "Spec"
    pages = [start_page()]
    for source, path in DOCUMENTS:
        pages.append(markdown_page(source, path, known))
    docs_pages = []
    for md in sorted((HERE / "docs").glob("*.md"), key=lambda p: (
            DOCS_ORDER.index(p.name) if p.name in DOCS_ORDER else len(DOCS_ORDER),
            p.name)):
        page = markdown_page(f"docs/{md.name}", md.stem + ".html", known)
        pages.append(page)
        docs_pages.append((md.name, page))
    pages += [library_page(), errors_page()]
    changelog, anchors = changelog_pages(known)
    pages += changelog
    pages += [capability_page(), receipt_page(),
              versions_page(built_versions(out))]
    pages += paper_pages(known)

    by_path = {p.path: p for p in pages}
    threat = [(p.path, p.title) for name, p in docs_pages
              if name not in placed
              and DOCS_SECTION.get(name, "Threat model") == "Threat model"]
    by_name = dict(docs_pages)
    guides = [(by_name[n].path, by_name[n].title) for n in GUIDES
              if n in by_name]
    comparisons = [(by_name[n].path, by_name[n].title) for n in COMPARISONS
                   if n in by_name]
    floats = [p.path for name, p in docs_pages
              if DOCS_SECTION.get(name) == "Floats"]
    embedding = [(p.path, p.title) for name, p in docs_pages
                 if DOCS_SECTION.get(name) == "Embedding"]
    sections: list[Section] = [
        ("Start here", "index.html", []),
        ("Tutorial", "tutorial.html", [("playground.html", "Playground")]),
        ("Language reference", "spec.html",
         [("llms.txt", "llms.txt, for a model")]),
        ("Standard library", "library.html", []),
        ("Errors", "errors.html", []),
        ("Floats", floats[0] if floats else None, []),
        ("Threat model", "threat-model.html",
         threat + [("security.html", by_path["security.html"].title)]),
        ("Embedding", "embedding.html", embedding),
        ("Guides", None, guides),
        ("Compare", None, comparisons),
        ("Paper", "papers/sabline.html", [("papers/index.html", "Papers")]),
        ("Spec", None, [("stability.html", "Stability"),
                        ("velaris.html", "Formerly Velaris"),
                        ("renamed.html", "Renamed from Velaris"),
                        ("capability/v1/index.html", "capability/v1"),
                        ("receipt/v1/index.html", "receipt/v1")]),
        ("Changelog", "changelog.html",
         [(p.path, p.title.replace("Changelog: ", ""))
          for p in changelog[1:]]),
    ]
    return pages, sections, anchors


# ---------------------------------------------------------------------------
# a page in its tree

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'"
           " viewBox='0 0 32 32'%3E%3Crect width='32' height='32'"
           " rx='7' fill='%230b6b4e'/%3E%3Ctext x='16' y='22'"
           " font-family='Arial' font-size='18' font-weight='700'"
           " fill='white' text-anchor='middle'%3ES%3C/text%3E%3C/svg%3E")
CSP = ("default-src 'none'; style-src 'self'; script-src 'self'; "
       "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
       "form-action 'none'")


def sidebar(sections: list[Section], current: str) -> str:
    def link(path: str, label: str) -> str:
        here = ' aria-current="page"' if path == current else ""
        return f'<a href="{internal(path)}"{here}>{html.escape(label)}</a>'

    out = ['<nav id="sidebar" class="sidebar" aria-label="Sections"><ul>']
    for label, path, children in sections:
        if path is None and not children:
            continue
        out.append("<li>" + (link(path, label) if path else
                             f'<span class="sec-label">{label}</span>'))
        if children:
            out.append("<ul>" + "".join(f"<li>{link(p, t)}</li>"
                                        for p, t in children) + "</ul>")
        out.append("</li>")
    out.append("</ul></nav>")
    return "\n".join(out)


def toc(page: Page, found: Outline) -> str:
    heads = [h for h in found.headings if h[0] in page.toc_levels]
    if len(heads) < 2:
        return ""
    top = min(h[0] for h in heads)
    out = ['<nav class="toc" aria-label="On this page">'
           '<p class="toc-title">On this page</p><ul>']
    open_sub = False
    for i, (level, ident, text) in enumerate(heads):
        item = f'<a href="#{ident}">{html.escape(text)}</a>'
        if level == top:
            if open_sub:
                out.append("</ul></li>")
                open_sub = False
            elif i:
                out.append("</li>")
            out.append(f"<li>{item}")
        else:
            if not open_sub:
                if i == 0:
                    out.append("<li>")
                out.append("<ul>")
                open_sub = True
            out.append(f"<li>{item}</li>")
    out.append("</ul></li></ul></nav>" if open_sub else "</li></ul></nav>")
    return "".join(out)


def description(found: Outline, page: Page | None = None) -> str:
    if page is not None and page.description:
        return page.description
    text = found.texts[0][1] if found.texts else ""
    return text if len(text) <= 160 else text[:157].rsplit(" ", 1)[0] + " ..."


def page_title(page: Page) -> str:
    return page.head_title or f"{page.title} - Sabline {VERSION}"


def cards(page: Page, found: Outline) -> str:
    """OpenGraph and a large-image card, so a link to a page shared somewhere
    shows its title, its description and one image. Low value for search
    itself - a card is what a link looks like in a feed, not what ranks it -
    and kept small for that reason (tier B, 8.7)."""
    tags = [("property", "og:type", "website"),
            ("property", "og:site_name", "Sabline"),
            ("property", "og:title", page_title(page)),
            ("property", "og:description", description(found, page)),
            ("property", "og:url", canonical(page.path)),
            ("property", "og:image", f"{SITE}/assets/og.png"),
            ("name", "twitter:card", "summary_large_image")]
    return "\n".join(f'<meta {kind}="{name}" content="{html.escape(value)}">'
                     for kind, name, value in tags)


def structured(page: Page) -> str:
    """One small JSON-LD block, on the landing page only: what the project is,
    where its code is, its licence and its author. No rating, review or offer
    - there are none to state. Low value (tier B, 8.7): search engines read it
    as a hint at most, and it earns no rich result without the ratings it
    deliberately leaves out. A data block, not a script: nothing executes it,
    so the Content-Security-Policy has nothing to allow."""
    if page.path != "index.html":
        return ""
    data = {"@context": "https://schema.org", "@type": "SoftwareSourceCode",
            "name": "Sabline", "alternateName": "Velaris",
            "description": f"{HEADLINE} {SUBLINE}", "url": f"{SITE}/",
            "codeRepository": REPO, "programmingLanguage": "Python",
            "license": "https://opensource.org/licenses/MIT",
            "version": VERSION,
            "author": {"@type": "Person", "name": AUTHOR}}
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return ('<script type="application/ld+json">'
            + text.replace("</", "<\\/") + "</script>")


def canonical(path: str) -> str:
    return SITE + "/" + (path[:-len("index.html")]
                         if path.endswith("index.html") else path)


def shell(page: Page, sections: list[Section], found: Outline) -> str:
    source = (f'<a href="{REPO}/blob/main/{page.source}">{page.source}</a>'
              if (HERE / page.source).is_file() else html.escape(page.source))
    wide = " wide" if page.wide else ""
    head = "\n".join(part for part in (cards(page, found), page.head_extra,
                                        structured(page)) if part)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<title>{html.escape(page_title(page))}</title>
<meta name="description" content="{html.escape(description(found, page))}">
<meta name="sabline-version" content="{VERSION}">
<link rel="canonical" href="{canonical(page.path)}">
{head}
<link rel="icon" href="{FAVICON}">
<link rel="stylesheet" href="{internal('assets/site.css')}">
<script src="{internal('assets/site.js')}"></script>
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="topbar">
<div class="bar">
<button type="button" class="menu" aria-expanded="false" aria-controls="sidebar"><span class="menu-icon" aria-hidden="true"></span><span class="vh">Menu</span></button>
<a class="brand" href="{internal('index.html')}">Sabline</a>
<a class="badge" href="{internal('versions.html')}" aria-label="Version {VERSION}, all versions"><span>{VERSION}</span></a>
<div class="search" role="search">
<label class="vh" for="search">Search the documentation</label>
<input id="search" type="search" placeholder="Search" autocomplete="off" spellcheck="false" aria-controls="search-results">
<div id="search-results" class="results" hidden></div>
</div>
<button type="button" class="theme" aria-pressed="false" aria-label="Dark theme" title="Dark theme"><span class="theme-icon" aria-hidden="true"></span></button>
</div>
</header>
<div class="layout">
{sidebar(sections, page.path)}
<div class="col">
<main id="content" class="doc{wide}" tabindex="-1">
{page.body}
</main>
<footer class="foot{wide}">
<p>Generated from {source} by build_docs.py, for Sabline {VERSION}. <a href="{REPO}">Sabline on GitHub</a>, MIT licence.</p>
</footer>
</div>
{toc(page, found)}
</div>
<p id="live" class="vh" aria-live="polite"></p>
</body>
</html>
"""


def resolve_links(text: str, site_path: str, tree: str, in_tree: set[str],
                  anchors: dict[str, str]) -> str:
    """Each link the page names by INTERNAL, made relative to where the page
    is: a page of the tree to its copy in the tree, a page kept at the top
    alone to that page, CHANGELOG.md#id to the changelog page holding id."""
    base = posixpath.dirname(site_path) or "."

    def one(m: re.Match[str]) -> str:
        target, _, frag = html.unescape(m.group(2)).partition("#")
        if target == "CHANGELOG.md":
            target = anchors.get(frag, "changelog.html")
        where = tree + target if target in in_tree else target
        rel = posixpath.relpath(where, base)
        rel += f"#{frag}" if frag else ""
        return f'{m.group(1)}="{html.escape(rel)}"'

    return re.sub(r'(href|src)="' + re.escape(INTERNAL) + r'([^"]*)"', one,
                  text)


def lf_bytes(path: Path) -> bytes:
    """A text file's bytes with line feeds for line ends, as the repository
    holds it. A Windows checkout may hold the same file with CR LF, and until
    8.5 a page that carried a file's digest, or a copy of a file, was then
    different bytes from the one a runner builds - so the release's own
    rebuild of docs/ touched pages nothing had changed."""
    return path.read_bytes().replace(b"\r\n", b"\n")


def write_file(path: Path, data: bytes) -> None:
    """Written beside itself and renamed over the old one, so a reader at the
    same moment - a suite reading the errors page while another run rebuilds
    it - never sees half of it (8.1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".page-", suffix=".tmp", dir=path.parent)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


@dataclass
class Tree:
    prefix: str                         # "", "latest/" or "8.3/"
    files: dict[str, int] = field(default_factory=dict)   # path: bytes
    pages: list[str] = field(default_factory=list)


def write_tree(dest: Path, prefix: str, pages: list[Page],
               sections: list[Section], anchors: dict[str, str]) -> Tree:
    tree = Tree(prefix)
    mine = [p for p in pages if not (p.root_only and prefix)]
    in_tree = {p.path for p in mine} | {"llms.txt", "search-index.json",
                                        "assets/site.css", "assets/site.js"}
    entries: list[list[Any]] = []
    listed: list[list[str]] = []
    for page in mine:
        found = outline(page.body)
        text = resolve_links(shell(page, sections, found), prefix + page.path,
                             prefix, in_tree, anchors)
        data = text.encode("utf-8")
        write_file(dest / page.path, data)
        tree.files[page.path] = len(data)
        tree.pages.append(page.path)
        number = len(listed)
        listed.append([page.path, page.title])
        for _level, ident, heading_text in found.headings:
            entries.append([number, ident, 1, heading_text])
        for under, paragraph in found.texts:
            entries.append([number, under, 0, paragraph])
    index = json.dumps({"version": VERSION, "pages": listed,
                        "entries": entries}, ensure_ascii=False,
                       separators=(",", ":")).encode("utf-8")
    write_file(dest / "search-index.json", index)
    tree.files["search-index.json"] = len(index)
    for name in ("site.css", "site.js"):
        data = lf_bytes(ASSETS / name)
        write_file(dest / "assets" / name, data)
        tree.files[f"assets/{name}"] = len(data)
    card = lf_bytes(HERE / "LLM.md")     # byte for byte (8.0), line feeds
    write_file(dest / "llms.txt", card)
    tree.files["llms.txt"] = len(card)
    return tree


# ---------------------------------------------------------------------------
# what the top of the site alone holds for search (8.7)

def _git(*args: str) -> str | None:
    try:
        done = subprocess.run(["git", *args], cwd=HERE, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def page_sources(page: Page) -> tuple[str, ...]:
    """The repository paths a page is made from, for its sitemap date: its
    own `sources` where it names them, else the document it renders, else
    what generates it. A path ending in / is a directory."""
    if page.sources:
        return page.sources
    if page.source == "sabline.ERROR_TABLE":
        return ("sabline/errors.py",)
    if page.source.endswith("/") or (HERE / page.source).is_file():
        return (page.source,)
    return ("build_docs.py",)


def _covers(source: str, path: str) -> bool:
    return path == source or (source.endswith("/") and path.startswith(source))


def source_dates(sources: set[str]) -> dict[str, str]:
    """{source: YYYY-MM-DD}: the day of the last commit that changed it, or
    today for one changed and not yet committed (or not known to git at
    all, as in an export without its history)."""
    today = datetime.now(timezone.utc).date().isoformat()
    ordered = sorted(sources)
    found: dict[str, str] = {}
    log = _git("log", "--format=%x00%cs", "--name-only", "--no-renames",
               "--", *ordered)
    day = ""
    for line in (log or "").splitlines():
        if line.startswith("\x00"):
            day = line[1:]
        elif line and day:
            for s in ordered:
                if s not in found and _covers(s, line):
                    found[s] = day
    dirty = _git("status", "--porcelain", "--untracked-files=all", "--",
                 *ordered)
    for line in (dirty or "").splitlines():
        path = line[3:].strip().strip('"')
        for s in ordered:
            if _covers(s, path):
                found[s] = today
    return {s: found.get(s, today) for s in ordered}


def sitemap(pages: list[Page]) -> bytes:
    """sitemap.xml: every page at the top, canonical address and the day its
    sources last changed; and the paper's PDF."""
    wanted = {p.path: page_sources(p) for p in pages}
    wanted["playground.html"] = ("playground/index.html",)
    wanted["papers/sabline.pdf"] = (PAPER_PDF,)
    dates = source_dates({s for ss in wanted.values() for s in ss})
    rows = []
    for path in sorted(wanted, key=lambda q: (q != "index.html", q)):
        day = max(dates[s] for s in wanted[path])
        rows.append(f"<url><loc>{html.escape(canonical(path))}</loc>"
                    f"<lastmod>{day}</lastmod></url>")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n").encode("utf-8")


def robots() -> bytes:
    """robots.txt: the named crawlers, and every other, may read everything;
    and where the sitemap is."""
    groups = [f"User-agent: {name}\nAllow: /\n" for name in CRAWLERS]
    groups.append("User-agent: *\nAllow: /\n")
    return ("# sabline.dev, written by build_docs.py (8.7). Every crawler may "
            "read\n# everything here; the named ones are named so that "
            "saying so is\n# explicit.\n\n" + "\n".join(groups)
            + f"\nSitemap: {SITE}/sitemap.xml\n").encode("utf-8")


def write_top(out: Path, pages: list[Page], tree: Tree) -> None:
    """What the top of the site alone holds for search: robots.txt,
    sitemap.xml, the IndexNow key, OpenGraph's image, and the paper's PDF."""
    files = {"robots.txt": robots(), "sitemap.xml": sitemap(pages),
             f"{INDEXNOW_KEY}.txt": INDEXNOW_KEY.encode("ascii"),
             "assets/og.png": (ASSETS / "og.png").read_bytes()}
    pdf = HERE / PAPER_PDF
    if pdf.is_file():
        files["papers/sabline.pdf"] = pdf.read_bytes()
    for name, data in files.items():
        write_file(out / name, data)
        tree.files[name] = len(data)


def replace_dir(stage: Path, final: Path) -> None:
    old = final.with_name(f".{final.name}.old-{os.getpid()}")
    if final.exists():
        try:
            os.replace(final, old)
        except OSError:                  # held open on Windows: remove it
            shutil.rmtree(final)
    os.replace(stage, final)
    shutil.rmtree(old, ignore_errors=True)


@dataclass
class Built:
    trees: list[Tree]
    pages: list[Page]
    versions: list[tuple[str, str]]
    missing: list[str]


def build(out: Path = OUT) -> Built:
    """Write the site into `out`: the top, latest/ and this release's
    major.minor/, and nothing else under `out` changes but what the top
    holds of this generator's."""
    out.mkdir(parents=True, exist_ok=True)
    MISSING.clear()
    pages, sections, anchors = collect(out)
    versions = built_versions(out)
    trees = [write_tree(out, "", pages, sections, anchors)]
    write_top(out, pages, trees[0])
    play = HERE / "playground" / "index.html"
    if play.is_file():
        write_file(out / "playground.html", lf_bytes(play))
        trees[0].files["playground.html"] = play.stat().st_size
    write_file(out / ".nojekyll", b"")        # served as written, not by Jekyll
    for prefix in ("latest/", f"{VERSION_DIR}/"):
        name = prefix.rstrip("/")
        stage = out / f".{name}.new-{os.getpid()}"
        shutil.rmtree(stage, ignore_errors=True)
        trees.append(write_tree(stage, prefix, pages, sections, anchors))
        replace_dir(stage, out / name)
    return Built(trees, pages, versions, list(MISSING))


def main() -> int:
    built = build(OUT)
    top = built.trees[0]
    sizes = [(n, p) for p, n in top.files.items()
             if p.endswith(".html") and p != "playground.html"]
    most, where = max(sizes)
    for line in built.missing:
        print(f"  a link to a file that is not in this repository: {line}")
    print(f"docs/ written: {len(built.trees[1].pages)} pages at the top, in "
          f"latest/ and in {VERSION_DIR}/, and {len(top.pages) - len(built.trees[1].pages)} "
          f"kept at the top alone; {len(sabline.ERROR_TABLE)} error codes "
          f"documented; versions {', '.join(v for v, _ in built.versions)}; "
          f"the largest page is {where}, {most} bytes")
    return 1 if built.missing else 0


if __name__ == "__main__":
    sys.exit(main())
