#!/usr/bin/env python3
"""The documentation site holds what its specification asks (8.3.1).

    python check_site.py                   build it and hold it; the Chrome
                                           checks run when Chrome is found
    python check_site.py --no-chrome       without them (test.yml's matrix)
    python check_site.py --require-chrome  no Chrome is WRONG, not SKIP
                                           (site.yml)
    python check_site.py --screenshots     and write docs/screenshots/ from
                                           this build (needs Chrome)

build_docs.build() writes the whole site into a scratch directory that
already holds what no generator writes there (CNAME, the two predicate
schemas), a major.minor directory an earlier release built, and a file an
earlier build left in latest/. Then, for every page of every tree:

BUILD      the earlier release's directory is still there and the version
           index lists it; latest/ holds nothing this build did not write;
           a page's copies at the top, in latest/ and in major.minor/ differ
           only in how they reach the pages kept at the top alone; every
           link to a file of this repository names one that is here.
MARKDOWN   no page's text outside code holds Markdown left unrendered:
           [text](url), **, a ``` fence, a line starting with #, a |---| row.
HTML       every page passes the strict parse described below.
LINKS      every relative href and src reaches a file of the build, and a
           #fragment an id on the page it names; no href or src names the
           site's address or an earlier one, but the canonical link, which
           names the page at the top; no src, stylesheet or icon names
           another host, so another host is only ever an <a href>.
ASSETS     every page loads its own tree's assets/site.css and
           assets/site.js and nothing more: no <style>, no style="", no
           inline script, no on* attribute, and a Content-Security-Policy
           under which nothing else could load. site.css loads nothing and
           site.js names no host.
BUDGET     every page is at most 100,000 bytes; the playground, which
           carries the compiler and loads its Python runtime from a CDN, is
           listed with its size and is not held to the site's rules.
SEARCH     each tree's search-index.json holds every heading id of every
           page of the tree, and each entry names a page there and an id on it.
LANDING    index.html routes three readers: try-it to the tutorial and the
           playground, review-it to the threat model and the audit,
           for-a-model to llms.txt; llms.txt is LLM.md byte for byte in
           every tree.
TUTORIAL   check_docs.py reads TUTORIAL.md, so its code blocks run.
DESIGN     site.css: each contrast figure in its comment is the one its
           tokens give, and at least 4.5 for text and 3.0 for a control's
           edge or the focus ring, in both themes; its two dark blocks hold
           the same tokens; 16px on 1.6 in 70ch; spacing 4/8/16/24/32/48;
           44px controls; the font stacks; :focus-visible;
           prefers-reduced-motion; the 960px break. site.js touches
           localStorage only inside try.
SEARCH     (8.7) every page at the top has a title and a meta description
           of its own - no two alike - and a canonical link naming itself;
           every page carries OpenGraph's title, description, address and
           image; the landing page alone carries one JSON-LD block, which
           parses and states no rating, review or offer. robots.txt lets
           each crawler build_docs.CRAWLERS names read everything and names
           the sitemap; sitemap.xml lists exactly the pages at the top and
           the paper, each with a date; the IndexNow key file holds the
           key; the OpenGraph image is a PNG of 1280 by 640 under 1 MB. The
           paper's landing page carries citation_title, citation_author,
           citation_publication_date and a citation_pdf_url in its own
           directory, beside a PDF under 5 MB. The landing page links every
           guide, every comparison and the paper - and the incident
           catalogue's flagship page once it exists.
STALE      (8.7) sitemap.xml, as committed, is not stale: no page's sources
           changed in a commit that left sitemap.xml alone later than the
           page's date says. It reads git's history, so a shallow clone
           (test.yml's legs) skips it, and --require-chrome (site.yml, which
           checks out the whole history) makes that skip wrong.
EARLIER    no page names an earlier address of the site more often than
           the document it is made from; a predicate type's page may name
           the earlier spelling of its type, in the line that says so.
CHROME     served from 127.0.0.1 to headless Chrome: at 360px no page is
           wider than the window (html's and body's scrollWidth against
           innerWidth, neither hiding overflow), none logs an error, and
           every code block has its copy button; four pages at 768, 1280 and
           1920px too; at 360px the menu opens and the page still fits,
           searching E700 reaches errors.html#E700 and ArrowDown moves into
           the results, and the theme toggle turns dark, says so with
           aria-pressed, and is remembered after a reload.

THE HTML PARSE catches a missing doctype, lang, title or charset; an
element HTML does not have; an attribute given twice; an end tag that
closes an element other than the one open (misnesting), one with nothing
open, one on a void element, and an element never closed; an empty or
duplicate id; an img without alt; a block element inside <p>; li outside
ul or ol, a row or cell outside its table; a link or button inside a link
or button; aria-controls, aria-labelledby, aria-describedby or for naming
no id; more than one main or h1; a heading more than one level below the
one before it. It does not catch whether an attribute is allowed on its
element or its value is valid (a malformed URL, a misused ARIA role), the
rest of each element's content model, bad character references, or what a
screen reader makes of the page; site.yml's Lighthouse run covers part of
that last.
"""
from __future__ import annotations

import argparse
import ast
import base64
import functools
import html
import json
import os
import posixpath
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_docs  # noqa: E402
from suite_dirs import isolate  # noqa: E402

WORK = isolate("check_site")
PASS = FAIL = SKIPPED = 0
KEPT = ["CNAME", "capability/v1/schema.json", "receipt/v1/schema.json"]
SCREENSHOT_PAGES = ["index.html", "tutorial.html", "spec.html", "errors.html"]
WIDTHS = {360: 800, 768: 1024, 1280: 800, 1920: 1080}
# a page with less than this left under build_docs.PAGE_BUDGET is listed
NEAR_BUDGET = 2_000


def say(text: str) -> None:
    print(text.encode("ascii", "replace").decode("ascii"))


def ok(label: str, good: object, detail: object = "") -> None:
    global PASS, FAIL
    if good:
        PASS += 1
        say(f"  ok      {label}")
    else:
        FAIL += 1
        shown = str(detail)
        say(f"  WRONG   {label}" + (f"\n          {shown[:1500]}" if shown else ""))


def skip(label: str) -> None:
    global SKIPPED
    SKIPPED += 1
    say(f"  SKIP    {label}")


def section(title: str) -> None:
    say("")
    say(title)
    say("-" * 62)


# ---------------------------------------------------------------------------
# the strict parse

ELEMENTS = set("""a abbr address article aside audio b bdi bdo blockquote body br
button canvas caption cite code col colgroup data datalist dd del details dfn
dialog div dl dt em embed fieldset figcaption figure footer form h1 h2 h3 h4 h5
h6 head header hgroup hr html i iframe img input ins kbd label legend li link
main map mark menu meta meter nav noscript object ol optgroup option output p
picture pre progress q rp rt ruby s samp script search section select slot
small source span strong style sub summary sup table tbody td template
textarea tfoot th thead time title tr track u ul var video wbr""".split())
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "source", "track", "wbr"}
BLOCK = set("""address article aside blockquote details dialog div dl fieldset
figcaption figure footer form h1 h2 h3 h4 h5 h6 header hgroup hr main menu nav
ol p pre search section table ul""".split())
INTERACTIVE = {"a", "button", "input", "select", "textarea"}
PARENTS = {"li": {"ul", "ol", "menu"}, "tr": {"thead", "tbody", "tfoot", "table"},
           "td": {"tr"}, "th": {"tr"}, "thead": {"table"}, "tbody": {"table"},
           "tfoot": {"table"}, "caption": {"table"}}
REFERENCES = ("aria-controls", "aria-labelledby", "aria-describedby", "for")


class Strict(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.problems: list[str] = []
        self.stack: list[str] = []
        self.ids: dict[str, int] = {}
        self.refs: list[tuple[str, str]] = []
        self.doctype = False
        self.lang = ""
        self.title = ""
        self.in_title = False
        self.charset = False
        self.count: dict[str, int] = {}
        self.last_heading = 0
        self.links: list[tuple[str, str, dict[str, str]]] = []  # (tag, attr, attrs)
        self.stylesheets: list[str] = []
        self.scripts: list[str] = []
        self.inline: list[str] = []
        self.data_blocks = 0        # <script type="application/ld+json">
        self.csp = ""

    def where(self) -> str:
        line, col = self.getpos()
        return f"line {line}"

    def handle_decl(self, decl: str) -> None:
        if decl.lower() == "doctype html":
            self.doctype = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        names = [k for k, _ in attrs]
        a = {k: (v if v is not None else "") for k, v in attrs}
        self.count[tag] = self.count.get(tag, 0) + 1
        if tag not in ELEMENTS:
            self.problems.append(f"{self.where()}: <{tag}> is not an HTML element")
        if len(names) != len(set(names)):
            self.problems.append(f"{self.where()}: <{tag}> has an attribute twice")
        parent = self.stack[-1] if self.stack else ""
        if tag in PARENTS and parent not in PARENTS[tag]:
            self.problems.append(f"{self.where()}: <{tag}> inside <{parent}>")
        if tag in BLOCK and "p" in self.stack:
            self.problems.append(f"{self.where()}: <{tag}> inside <p>")
        if tag in INTERACTIVE and ({"a", "button"} & set(self.stack)):
            self.problems.append(f"{self.where()}: <{tag}> inside a link or button")
        if "id" in a:
            if not a["id"] or re.search(r"\s", a["id"]):
                self.problems.append(f"{self.where()}: an empty id, or one with a space")
            self.ids[a["id"]] = self.ids.get(a["id"], 0) + 1
        for ref in REFERENCES:
            if ref in a:
                for ident in a[ref].split():
                    self.refs.append((ref, ident))
        if tag == "html":
            self.lang = a.get("lang", "")
        if tag == "title":
            self.in_title = True
        if tag == "meta" and a.get("charset", "").lower() == "utf-8":
            self.charset = True
        if tag == "meta" and a.get("http-equiv", "").lower() == "content-security-policy":
            self.csp = a.get("content", "")
        if tag == "img" and "alt" not in a:
            self.problems.append(f"{self.where()}: <img> without alt")
        if "style" in a or tag == "style":
            self.inline.append(f"{self.where()}: a style attribute or element")
        if any(k.startswith("on") for k in a):
            self.inline.append(f"{self.where()}: an on* attribute")
        if tag == "script":
            if "src" in a:
                self.scripts.append(a["src"])
            elif a.get("type") == "application/ld+json":
                self.data_blocks += 1       # data, not a script: nothing runs it
            else:
                self.inline.append(f"{self.where()}: an inline script")
        if tag == "link" and a.get("rel") == "stylesheet":
            self.stylesheets.append(a.get("href", ""))
        m = re.fullmatch(r"h([1-6])", tag)
        if m:
            level = int(m.group(1))
            if self.last_heading and level > self.last_heading + 1:
                self.problems.append(f"{self.where()}: <{tag}> after "
                                     f"<h{self.last_heading}>")
            self.last_heading = level
        for attr in ("href", "src"):
            if attr in a:
                self.links.append((tag, attr, a))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in VOID:
            self.problems.append(f"{self.where()}: </{tag}> on a void element")
            return
        if not self.stack:
            self.problems.append(f"{self.where()}: </{tag}> with nothing open")
            return
        if self.stack[-1] != tag:
            self.problems.append(f"{self.where()}: </{tag}> while <{self.stack[-1]}> "
                                 "is open (misnested)")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title += data

    def finish(self) -> list[str]:
        self.close()
        out = list(self.problems)
        if self.stack:
            out.append(f"left open at the end: {self.stack}")
        if not self.doctype:
            out.append("no <!DOCTYPE html>")
        if not self.lang:
            out.append("<html> has no lang")
        if not self.title.strip():
            out.append("no <title>, or an empty one")
        if not self.charset:
            out.append("no <meta charset=utf-8>")
        out += [f"the id {i!r} is given {n} times" for i, n in self.ids.items() if n > 1]
        out += [f"{ref}={i!r} names no id" for ref, i in self.refs if i not in self.ids]
        for tag in ("main", "h1"):
            if self.count.get(tag, 0) != 1:
                out.append(f"{self.count.get(tag, 0)} <{tag}> elements")
        return out


def parse(text: str) -> Strict:
    p = Strict()
    p.feed(text)
    return p


class Text(HTMLParser):
    """A page's text outside <pre>, <code>, <script> and heading anchors, a
    block element starting a new line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        cls = (dict(attrs).get("class") or "").split()
        if self.skipping:
            if tag not in VOID:
                self.skipping.append(tag)
            return
        if tag in ("pre", "code", "script", "title") or "anchor" in cls:
            self.skipping.append(tag)
            return
        if tag in BLOCK or tag in ("li", "td", "th", "tr", "br"):
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.skipping:
            if self.skipping[-1] == tag:
                self.skipping.pop()
            return
        if tag in BLOCK or tag in ("li", "td", "th"):
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skipping:
            self.parts.append(data)


RAW = [("an unrendered link", re.compile(r"\[[^\]\n]+\]\([^)\s]+\)")),
       ("**", re.compile(r"\*\*")),
       ("a ``` fence", re.compile(r"```")),
       ("a line starting with #", re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+\S")),
       ("a |---| row", re.compile(r"\|[ \t]*:?-{3,}:?[ \t]*\|"))]


# ---------------------------------------------------------------------------
# building

def build(out: Path) -> build_docs.Built:
    for rel in KEPT:
        src = HERE / "docs" / rel
        if src.is_file():
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, out / rel)
    earlier = out / "0.1"
    earlier.mkdir(parents=True)
    (earlier / "index.html").write_text(
        '<!DOCTYPE html><meta name="sabline-version" content="0.1.9">',
        encoding="utf-8")
    (out / "latest").mkdir()
    (out / "latest" / "stale.html").write_text("an earlier build's", encoding="utf-8")
    # ...and at the TOP, which is written in place rather than swapped, so
    # a page an earlier release wrote and this one does not is left behind
    # unless the build takes it away (8.7). The changelog is split to a page
    # budget, so an entry added to it re-splits the group and the last page
    # of the old split is exactly this: 8.7.0 left changelog-8-4.html at the
    # top, still titled 8.6.0, in no sitemap and linked from no page.
    # A page is this generator's if it carries the version meta it writes
    # into every page; one without it is somebody else's and stays.
    MARKER = '<!DOCTYPE html><meta name="sabline-version" content="8.6.0">'
    (out / "gone.html").write_text(MARKER, encoding="utf-8")
    (out / "papers").mkdir(parents=True, exist_ok=True)
    (out / "papers" / "gone.html").write_text(MARKER, encoding="utf-8")
    (out / "by-hand.html").write_text(
        "<!DOCTYPE html><title>not this generator's</title>", encoding="utf-8")
    return build_docs.build(out)


def html_files(out: Path, tree: build_docs.Tree) -> list[str]:
    return [tree.prefix + p for p in tree.files if p.endswith(".html")]


def check_build(out: Path, built: build_docs.Built) -> None:
    section("the build")
    ok("an earlier release's major.minor directory is kept",
       (out / "0.1" / "index.html").is_file())
    versions = (out / "versions.html").read_text(encoding="utf-8")
    ok("...and the version index lists it, latest/ and this release's",
       'href="0.1/index.html"' in versions and 'href="latest/index.html"' in versions
       and f'href="{build_docs.VERSION_DIR}/index.html"' in versions)
    ok("latest/ holds nothing this build did not write",
       not (out / "latest" / "stale.html").exists())
    # the top is written in place, so this is the one tree that has to be
    # swept rather than replaced (8.7)
    ok("the top holds no page of this generator's that this build did not "
       "write, at the top or below it",
       not (out / "gone.html").exists()
       and not (out / "papers" / "gone.html").exists(),
       [p for p in ("gone.html", "papers/gone.html") if (out / p).exists()])
    ok("...and says which ones it took away",
       sorted(built.removed) == ["gone.html", "papers/gone.html"],
       sorted(built.removed))
    ok("...and leaves a page that is not this generator's where it is",
       (out / "by-hand.html").is_file())
    ok("...and an earlier release's directory, every page of which carries "
       "the same mark", (out / "0.1" / "index.html").is_file())
    prefixes = [t.prefix for t in built.trees]
    ok(f"three trees: the top, latest/ and {build_docs.VERSION_DIR}/",
       prefixes == ["", "latest/", f"{build_docs.VERSION_DIR}/"], prefixes)
    top, latest = built.trees[0], built.trees[1]
    ok("latest/ and major.minor/ hold every page the top holds, but those kept "
       "at the top alone", set(latest.pages) == {p for p in top.pages
                                                if p not in build_docs.ROOT_ONLY}
       and set(built.trees[2].pages) == set(latest.pages),
       sorted(set(top.pages) ^ set(latest.pages)))
    alone = "|".join(re.escape(p) for p in sorted(build_docs.ROOT_ONLY))
    differ = []
    for page in latest.pages:
        a = (out / page).read_text(encoding="utf-8")
        for prefix in prefixes[1:]:
            b = (out / (prefix + page)).read_text(encoding="utf-8")
            b = re.sub(r'href="\.\./(' + alone + r')', r'href="\1', b)
            if a != b:
                differ.append(prefix + page)
    ok("a page's copies differ only in how they reach the pages kept at the "
       "top alone", not differ, differ[:5])
    ok("every link to a file of this repository names one that is here",
       not built.missing, built.missing[:10])
    canon = []
    for tree in built.trees:
        for page in tree.pages:
            text = (out / (tree.prefix + page)).read_text(encoding="utf-8")
            m = re.search(r'<link rel="canonical" href="([^"]+)"', text)
            if not m or m.group(1) != build_docs.canonical(page):
                canon.append(tree.prefix + page)
    ok("every copy's canonical link names the page at the top", not canon, canon[:5])


def check_pages(out: Path, built: build_docs.Built) -> dict[str, Strict]:
    section("every page: Markdown, HTML, links, assets, budget")
    parsed: dict[str, Strict] = {}
    raw: list[str] = []
    invalid: list[str] = []
    for tree in built.trees:
        for rel in html_files(out, tree):
            if rel.endswith("playground.html"):
                continue
            text = (out / rel).read_text(encoding="utf-8")
            p = parse(text)
            parsed[rel] = p
            invalid += [f"{rel}: {x}" for x in p.finish()]
            t = Text()
            t.feed(text)
            plain = "".join(t.parts)
            for name, pattern in RAW:
                m = pattern.search(plain)
                if m:
                    around = plain[max(0, m.start() - 40):m.end() + 40]
                    raw.append(f"{rel}: {name}: {' '.join(around.split())!r}")
    ok(f"no Markdown is left unrendered in the text of {len(parsed)} pages",
       not raw, "\n          ".join(raw[:10]))
    ok(f"all {len(parsed)} pages pass the strict HTML parse", not invalid,
       "\n          ".join(invalid[:15]))

    site_host = urllib.parse.urlsplit(build_docs.SITE).hostname
    earlier_hosts = {urllib.parse.urlsplit(s).hostname for s in build_docs.earlier_sites()}
    broken, own, third, external = [], [], [], set()
    ids = {rel: set(p.ids) for rel, p in parsed.items()}
    for rel, p in parsed.items():
        for tag, attr, a in p.links:
            value = a[attr]
            if value.startswith("data:"):
                continue
            if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value) or value.startswith("//"):
                parts = urllib.parse.urlsplit(value)
                if parts.scheme == "mailto":
                    continue
                if parts.hostname == site_host:
                    if not (tag == "link" and a.get("rel") == "canonical"):
                        own.append(f"{rel}: {value}")
                elif parts.hostname in earlier_hosts:
                    own.append(f"{rel}: {value}")
                elif tag != "a":
                    third.append(f"{rel}: <{tag} {attr}={value}>")
                else:
                    external.add(parts.hostname or "")
                continue
            path, _, frag = value.partition("#")
            target = rel if not path else posixpath.normpath(
                posixpath.join(posixpath.dirname(rel), path))
            if target.startswith("../") or target == "..":
                broken.append(f"{rel}: {value} leaves the site")
                continue
            file = out / target
            if file.is_dir():
                target = posixpath.join(target, "index.html")
                file = out / target
            if not file.is_file():
                broken.append(f"{rel}: {value}")
            elif frag and target.endswith(".html") and target in ids \
                    and frag not in ids[target]:
                broken.append(f"{rel}: {value} (no id {frag!r} there)")
    ok("every relative href and src reaches a file, and every #fragment an id",
       not broken, "\n          ".join(broken[:15]))
    ok("no link names the site's own address or an earlier one; a link into "
       "the site is relative", not own, own[:10])
    ok("no src, stylesheet or icon names another host: another host is only "
       f"ever a link ({', '.join(sorted(external))})", not third, third[:10])

    wrong_assets = []
    for rel, p in parsed.items():
        prefix = rel[:rel.index("/") + 1] if rel.split("/")[0] in (
            "latest", build_docs.VERSION_DIR) else ""
        inner = rel[len(prefix):]
        depth = inner.count("/")
        want_css = "../" * depth + "assets/site.css"
        want_js = "../" * depth + "assets/site.js"
        if p.stylesheets != [want_css] or p.scripts != [want_js] or p.inline:
            wrong_assets.append(f"{rel}: css {p.stylesheets}, js {p.scripts}, "
                                f"{p.inline[:2]}")
        if p.data_blocks > (1 if inner == "index.html" else 0):
            wrong_assets.append(f"{rel}: {p.data_blocks} JSON-LD block(s); the "
                                "landing page may have one, no other page any")
        if "default-src 'none'" not in p.csp or "script-src 'self'" not in p.csp:
            wrong_assets.append(f"{rel}: CSP {p.csp!r}")
    ok("every page loads its tree's site.css and site.js and nothing else, "
       "under a CSP that lets nothing else load", not wrong_assets, wrong_assets[:8])
    css = (build_docs.ASSETS / "site.css").read_text(encoding="utf-8")
    js = (build_docs.ASSETS / "site.js").read_text(encoding="utf-8")
    rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    ok("site.css loads nothing: no url(), @import or @font-face",
       not re.search(r"url\(|@import|@font-face", rules))
    fetches = re.findall(r"fetch\((.*)$", re.sub(r"/\*.*?\*/", "", js, flags=re.S),
                         re.M)
    ok("site.js names no host, and fetches only search-index.json",
       not re.search(r"https?://", js) and len(fetches) == 1
       and fetches[0].startswith('new URL("search-index.json", treeRoot)'),
       fetches)
    ok(f"site.css is {len(css.encode())} bytes and site.js {len(js.encode())}: "
       "one small file each", len(css.encode()) < 24_000 and len(js.encode()) < 16_000)

    sizes = sorted(((n, t.prefix + p) for t in built.trees for p, n in t.files.items()
                    if p.endswith(".html") and p != "playground.html"), reverse=True)
    # headroom is what a page has left under the budget, negative when it is
    # over. Every page gains a link each time the sidebar does, so a page
    # close to the budget fails on somebody else's change; the failure says
    # how far over each page is and which are next, so they are split on
    # purpose rather than on the next new page
    budget = build_docs.PAGE_BUDGET
    headroom = [(budget - n, name) for n, name in sizes]
    over = [f"{name} {budget - room:,} bytes, {-room:,} over"
            for room, name in headroom if room < 0]
    near = [f"{name} {budget - room:,} bytes, {room:,} left"
            for room, name in headroom if 0 <= room < NEAR_BUDGET]
    ok(f"every page is at most {budget:,} bytes (the largest: "
       + ", ".join(f"{name} {n:,}" for n, name in sizes[:4]) + ")", not over,
       over + [f"within {NEAR_BUDGET:,} bytes of it: {n}" for n in near])
    if near:
        say(f"  listed  {len(near)} page(s) within {NEAR_BUDGET:,} bytes of "
            f"the budget, the next to split: " + "; ".join(near))
    play = built.trees[0].files.get("playground.html")
    if play:
        say(f"  listed  playground.html is {play:,} bytes: it carries the "
            "compiler, and loads Pyodide from jsDelivr, so it is not held to "
            "the site's budget, assets or link rules")
    return parsed


def check_search(out: Path, built: build_docs.Built, parsed: dict[str, Strict]) -> None:
    section("search")
    for tree in built.trees:
        index = json.loads((out / (tree.prefix + "search-index.json")).read_text(
            encoding="utf-8"))
        pages = [p for p, _ in index["pages"]]
        headings: dict[str, set[str]] = {p: set() for p in pages}
        bad = []
        for number, anchor, kind, text in index["entries"]:
            page = pages[number]
            rel = tree.prefix + page
            if kind == 1:
                headings[page].add(anchor)
            if anchor and anchor not in parsed[rel].ids:
                bad.append(f"{page}#{anchor}")
            if not text:
                bad.append(f"{page}#{anchor}: empty")
        missing = []
        for page in tree.pages:
            want = set()
            text = (out / (tree.prefix + page)).read_text(encoding="utf-8")
            for m in re.finditer(r'<h[1-6] id="([^"]+)"', text):
                want.add(m.group(1))
            if page not in headings:
                missing.append(f"{page}: not in the index")
                continue
            missing += [f"{page}#{h}" for h in sorted(want - headings[page])]
        name = tree.prefix or "the top"
        ok(f"{name}: search-index.json has every heading of all {len(tree.pages)} "
           f"pages ({len(index['entries']):,} entries, "
           f"{tree.files['search-index.json']:,} bytes)", not missing, missing[:10])
        ok(f"{name}: every entry names a page of the tree and an id on it",
           not bad and set(pages) == set(tree.pages), bad[:10])


def check_landing(out: Path, built: build_docs.Built, parsed: dict[str, Strict]) -> None:
    section("the landing page, and llms.txt")
    card = build_docs.lf_bytes(HERE / "LLM.md")   # as the build copies it
    for tree in built.trees:
        rel = tree.prefix + "index.html"
        text = (out / rel).read_text(encoding="utf-8")
        routes = {}
        for m in re.finditer(r'<section class="route" aria-labelledby="([^"]+)">'
                             r"(.*?)</section>", text, re.S):
            routes[m.group(1)] = re.findall(r'href="([^"]+)"', m.group(2))
        up = "../" if tree.prefix else ""
        want = {"try-it": ["tutorial.html", f"{up}playground.html"],
                "review-it": ["threat-model.html", "embedding.html#the-audit-format"],
                "for-a-model": ["llms.txt"]}
        ok(f"{rel}: three routes, each reaching what it names",
           all(routes.get(k) == v for k, v in want.items()), routes)
        ok(f"{tree.prefix}llms.txt is LLM.md byte for byte",
           (out / (tree.prefix + "llms.txt")).read_bytes() == card)
        links = set(re.findall(r'href="([^"#]+)', text))
        wanted = ([n[:-3] + ".html" for n in build_docs.GUIDES
                   + build_docs.COMPARISONS]
                  + [f"{up}papers/sabline.html"])
        if (HERE / "docs" / build_docs.FLAGSHIP).is_file():
            wanted.append(build_docs.FLAGSHIP[:-3] + ".html")
        missing = [w for w in wanted if w not in links]
        ok(f"{rel}: links every guide, every comparison and the paper"
           + (", and the flagship" if len(wanted) > len(build_docs.GUIDES)
              + len(build_docs.COMPARISONS) + 1 else ""), not missing, missing)
    section("the tutorial's code blocks")
    tree_ = ast.parse((HERE / "check_docs.py").read_text(encoding="utf-8"))
    docs: tuple[str, ...] = ()
    for node in tree_.body:
        if isinstance(node, ast.Assign) and any(
                getattr(t, "id", "") == "DOCS" for t in node.targets):
            # DOCS is a literal tuple, and from 8.7 the guides added to it
            value = node.value.left if isinstance(node.value, ast.BinOp) \
                else node.value
            docs = cast(tuple[str, ...], ast.literal_eval(value))
    ok("check_docs.py reads TUTORIAL.md, so every block in it runs or is "
       "marked with why", "TUTORIAL.md" in docs, docs)


def head_value(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def check_findable(out: Path, built: build_docs.Built) -> None:
    """SEARCH: what a crawler and a link preview read (8.7)."""
    section("for search: titles, descriptions, canonicals, cards, robots, "
            "the sitemap, the paper")
    top = built.trees[0]
    titles: dict[str, list[str]] = {}
    described: dict[str, list[str]] = {}
    bad_canonical, no_card = [], []
    for tree in built.trees:
        for rel in html_files(out, tree):
            if rel.endswith("playground.html"):
                continue
            text = (out / rel).read_text(encoding="utf-8")
            inner = rel[len(tree.prefix):]
            title = head_value(text, r"<title>(.*?)</title>")
            desc = head_value(text, r'<meta name="description" content="([^"]*)"')
            canon = head_value(text, r'<link rel="canonical" href="([^"]*)"')
            if tree is top:
                titles.setdefault(title, []).append(rel)
                described.setdefault(desc, []).append(rel)
            if canon != build_docs.canonical(inner):
                bad_canonical.append(f"{rel}: {canon}")
            cards = [n for n in ("og:title", "og:description", "og:url",
                                 "og:image", "twitter:card")
                     if f'"{n}" content="' not in text]
            if cards:
                no_card.append(f"{rel}: no {', '.join(cards)}")
    empty = [f"title {k!r}: {v}" for k, v in titles.items() if not k] + \
        [f"description {k!r}: {v}" for k, v in described.items() if not k]
    twice = [f"{v}" for k, v in titles.items() if k and len(v) > 1] + \
        [f"{v}" for k, v in described.items() if k and len(v) > 1]
    ok(f"every page at the top has a title and a description ({len(titles)} "
       "titles)", not empty, empty[:8])
    ok("no two pages at the top share a title or a description", not twice,
       twice[:8])
    ok("every page's canonical link names the page at the top: itself there, "
       "and the page it copies elsewhere", not bad_canonical, bad_canonical[:8])
    ok("every page carries OpenGraph's title, description, address and image",
       not no_card, no_card[:8])

    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>',
                        (out / "index.html").read_text(encoding="utf-8"), re.S)
    try:
        data = json.loads(blocks[0].replace("<\\/", "</")) if len(blocks) == 1 else {}
    except ValueError:
        data = {}
    flat = json.dumps(data)
    ok("the landing page's one JSON-LD block parses, says what the project "
       "is, and states no rating, review or offer",
       data.get("@type") == "SoftwareSourceCode" and data.get("name") == "Sabline"
       and not re.search(r"aggregateRating|review|offers", flat), flat[:200])

    robots = (out / "robots.txt").read_text(encoding="utf-8")
    groups = {m.group(1): m.group(2) for m in re.finditer(
        r"User-agent: (\S+)\n((?:(?:Allow|Disallow): .*\n)*)", robots)}
    shut = [name for name in build_docs.CRAWLERS + ("*",)
            if groups.get(name, "").strip() != "Allow: /"]
    ok(f"robots.txt lets {', '.join(build_docs.CRAWLERS)} and every other "
       "crawler read everything, and names the sitemap",
       not shut and f"Sitemap: {build_docs.SITE}/sitemap.xml" in robots, shut)

    listed = sitemap_rows((out / "sitemap.xml").read_text(encoding="utf-8"))
    pages = {build_docs.canonical(p) for p in top.pages} | {
        build_docs.canonical("playground.html"),
        build_docs.canonical("papers/sabline.pdf")}
    today = time.strftime("%Y-%m-%d", time.gmtime())
    undated = [u for u, d in listed.items()
               if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) or d > today]
    ok(f"sitemap.xml lists exactly the {len(pages)} pages at the top and the "
       "paper, each with a date that is not in the future",
       set(listed) == pages and not undated,
       f"missing {sorted(pages - set(listed))[:5]}, extra "
       f"{sorted(set(listed) - pages)[:5]}, undated {undated[:5]}")

    key = build_docs.INDEXNOW_KEY
    held = out / f"{key}.txt"
    ok("the IndexNow key file at the root holds the key, and the key is 8 to "
       "128 letters, digits or hyphens",
       re.fullmatch(r"[A-Za-z0-9-]{8,128}", key) is not None
       and held.is_file() and held.read_text(encoding="utf-8") == key)

    png = (out / "assets" / "og.png").read_bytes()
    width, height = struct.unpack(">II", png[16:24]) if len(png) > 24 else (0, 0)
    ok(f"OpenGraph's image is a PNG of 1280 by 640 under 1 MB ({len(png):,} "
       "bytes)", png[:8] == b"\x89PNG\r\n\x1a\n" and (width, height) ==
       (1280, 640) and len(png) < 1_000_000, (width, height))

    landing = (out / "papers" / "sabline.html").read_text(encoding="utf-8")
    tags = {n: head_value(landing, rf'<meta name="{n}" content="([^"]*)"')
            for n in ("citation_title", "citation_author",
                      "citation_publication_date", "citation_pdf_url")}
    pdf = out / "papers" / "sabline.pdf"
    same_dir = tags["citation_pdf_url"] == f"{build_docs.SITE}/papers/sabline.pdf"
    ok("the paper's landing page carries citation_title, citation_author, "
       "citation_publication_date (YYYY/MM/DD) and a citation_pdf_url in its "
       "own directory, shows its abstract, and the PDF is there, under 5 MB",
       all(tags.values()) and same_dir
       and re.fullmatch(r"\d{4}/\d{2}/\d{2}", tags["citation_publication_date"])
       is not None and 'id="abstract"' in landing
       and pdf.is_file() and pdf.stat().st_size < 5_000_000
       and pdf.read_bytes()[:5] == b"%PDF-", tags)


def sitemap_rows(xml: str) -> dict[str, str]:
    return dict(re.findall(r"<url><loc>([^<]+)</loc><lastmod>([^<]*)</lastmod>"
                           r"</url>", xml))


def stale_pages(committed: dict[str, str], sources: dict[str, tuple[str, ...]],
                commits: list[tuple[str, set[str]]]) -> list[str]:
    """The addresses whose sources changed, in a commit that left
    docs/sitemap.xml alone, on a day later than the committed sitemap's date
    for them. `commits` is (day, files) for every commit in the history."""
    last: dict[str, str] = {}
    for day, files in commits:
        if "docs/sitemap.xml" in files:
            continue
        for url, wanted in sources.items():
            if any(f == s or (s.endswith("/") and f.startswith(s))
                   for f in files for s in wanted):
                last[url] = max(last.get(url, ""), day)
    return sorted(f"{url}: its sources changed on {day}, the sitemap says "
                  f"{committed.get(url, 'nothing')}"
                  for url, day in last.items()
                  if url not in committed or day > committed[url])


def git(*args: str) -> str | None:
    # TZ=UTC, as build_docs._git does it: the days this reads are compared
    # against the days the sitemap was built from, and the two must be the
    # same timezone or a commit made in the evening UTC, east of it, reads
    # as a page whose sources changed the day after the sitemap was written
    env = {**os.environ, "TZ": "UTC"}
    try:
        done = subprocess.run(["git", *args], cwd=HERE, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=180, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def check_stale(built: build_docs.Built, require: bool) -> None:
    """STALE: the sitemap as committed, against git's history (8.7)."""
    section("sitemap.xml, as committed, against the history")
    fake = {"https://x/a.html": "2026-09-20"}
    shown = stale_pages(fake, {"https://x/a.html": ("docs/a.md",)},
                        [("2026-09-22", {"docs/a.md"}),
                         ("2026-09-21", {"docs/a.md", "docs/sitemap.xml"})])
    fine = stale_pages(fake, {"https://x/a.html": ("docs/a.md",)},
                       [("2026-09-22", {"docs/a.md", "docs/sitemap.xml"}),
                        ("2026-09-19", {"docs/a.md"})])
    ok("the rule itself: a source changed after its date, in a commit that "
       "left the sitemap alone, is stale; one changed with the sitemap is not",
       len(shown) == 1 and not fine, (shown, fine))
    shallow = git("rev-parse", "--is-shallow-repository")
    committed_xml = git("show", "HEAD:docs/sitemap.xml")
    if shallow is None or shallow.strip() != "false" or committed_xml is None:
        why = ("no git history here" if shallow is None else
               "a shallow clone has no history to read"
               if shallow.strip() != "false" else
               "HEAD has no docs/sitemap.xml")
        if require:
            ok(f"the history is here to read ({why})", False)
        else:
            skip(f"whether sitemap.xml is stale: {why} (site.yml checks it)")
        return
    committed = sitemap_rows(committed_xml)
    sources = {build_docs.canonical(p.path): build_docs.page_sources(p)
               for p in built.pages}
    sources[build_docs.canonical("playground.html")] = ("playground/index.html",)
    sources[build_docs.canonical("papers/sabline.pdf")] = (build_docs.PAPER_PDF,)
    wanted = sorted({s for ss in sources.values() for s in ss})
    log = git("log", "--date=format-local:%Y-%m-%d", "--format=%x00%cd",
              "--name-only", "--no-renames", "HEAD",
              "--", *wanted, "docs/sitemap.xml") or ""
    commits: list[tuple[str, set[str]]] = []
    for line in log.splitlines():
        if line.startswith("\x00"):
            commits.append((line[1:], set()))
        elif line and commits:
            commits[-1][1].add(line)
    stale = stale_pages(committed, sources, commits)
    missing = sorted(set(sources) - set(committed))
    ok(f"sitemap.xml as committed lists every page and is not stale "
       f"({len(commits)} commits read)", not stale and not missing,
       "\n          ".join((stale + [f"not listed: {m}" for m in missing])[:10])
       + "\n          (python build_docs.py, and commit docs/sitemap.xml)")


CONTRAST = re.compile(r"^\s*(text|ui)\s+--([\w-]+) on --([\w-]+)\s+([\d.]+) light"
                      r"\s+([\d.]+) dark\s*$", re.M)


def luminance(color: str) -> float:
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens(css: str, selector: str) -> dict[str, str]:
    at = css.index(selector)
    block = css[at:css.index("}", at)]
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", block))


def check_design() -> None:
    section("design")
    css = (build_docs.ASSETS / "site.css").read_text(encoding="utf-8")
    js = (build_docs.ASSETS / "site.js").read_text(encoding="utf-8")
    light = tokens(css, ":root {")
    dark = tokens(css, ':root:not([data-theme="light"]) {')
    dark2 = tokens(css, ':root[data-theme="dark"] {')
    ok("the two dark blocks hold the same tokens, and every colour token of "
       "the light theme", dark == dark2 and set(light) == set(dark),
       sorted(set(light) ^ set(dark)))
    rows = CONTRAST.findall(css)
    wrong = []
    for kind, fg, bg, said_light, said_dark in rows:
        need = 4.5 if kind == "text" else 3.0
        for theme, table, said in (("light", light, said_light), ("dark", dark, said_dark)):
            got = ratio(table[fg], table[bg])
            if f"{got:.2f}" != said or got < need:
                wrong.append(f"--{fg} on --{bg} ({theme}): the comment says {said}, "
                             f"the tokens give {got:.2f}, and it needs {need}")
    ok(f"the {len(rows)} contrast figures in site.css are what its tokens give, "
       "each at least 4.5 for text and 3.0 for a control, in both themes",
       rows and not wrong, "\n          ".join(wrong))
    compact = re.sub(r"\s+", " ", css)
    wants = {
        "16px on a 1.6 line height": "font-size: 1rem; line-height: 1.6;" in compact
        and "html { font-size: 100%;" in compact,
        "a 70ch measure": "--measure: 70ch;" in compact,
        "spacing 4/8/16/24/32/48": all(f"--s{i}: {px}px;" in compact for i, px in
                                       enumerate((4, 8, 16, 24, 32, 48), 1)),
        "44px controls": "--tap: 44px;" in compact,
        "the prose stack": '--sans: -apple-system, "Segoe UI", Roboto, Inter, sans-serif;'
        in compact,
        "a monospace stack": re.search(r"--mono: ui-monospace,[^;]*monospace;", compact),
        ":focus-visible": ":focus-visible {" in compact,
        "prefers-reduced-motion": "@media (prefers-reduced-motion: reduce)" in compact,
        "the 960px break": "@media (min-width: 960px)" in compact,
        "no overflow hidden on html or body": not re.search(
            r"(?:^|[\s}])(?:html|body)\s*\{[^}]*overflow", css),
    }
    for label, good in wants.items():
        ok(f"site.css: {label}", good)
    uses = [m.start() for m in re.finditer(r"localStorage", js)]
    ok("site.js touches localStorage only inside try",
       uses and all(js.rfind("try {", 0, at) > js.rfind("}", 0, at) - 60 for at in uses))


def check_earlier(out: Path, built: build_docs.Built) -> None:
    section("the site's earlier address")
    hosts = [h for h in (urllib.parse.urlsplit(s).hostname
                         for s in build_docs.earlier_sites()) if h]
    if not hosts:
        ok("sabline names no earlier address of the site", True)
        return
    sources: dict[str, int] = {}
    by_source: dict[str, int] = {}
    wrong = []
    for tree in built.trees:
        for page in built.pages:
            if page.path not in tree.pages:
                continue
            text = html.unescape((out / (tree.prefix + page.path)).read_text(
                encoding="utf-8"))
            if page.source == "build_docs.py":
                # a predicate type's page names the types sabline writes and
                # reads, whatever address they are on
                for kind in ("CAPABILITY", "RECEIPT"):
                    for spelling in build_docs.predicate_types(kind):
                        text = text.replace(spelling, "")
            n = sum(text.count(h) for h in hosts)
            src = HERE / page.source
            if page.source not in sources:
                sources[page.source] = (sum(src.read_text(encoding="utf-8").count(h)
                                            for h in hosts) if src.is_file() else 0)
            key = f"{tree.prefix}{page.source}"
            by_source[key] = by_source.get(key, 0) + n
    for key, n in by_source.items():
        source = key.split("/", 1)[1] if key.startswith(("latest/", build_docs.VERSION_DIR + "/")) else key
        if n > sources.get(source, 0):
            wrong.append(f"{key}: {n} on its pages, {sources.get(source, 0)} in the source")
    ok(f"no page names {', '.join(hosts)} more often than the document it is "
       "made from", not wrong, wrong[:10])


# ---------------------------------------------------------------------------
# Chrome, over the DevTools protocol, with nothing but the standard library

def find_chrome() -> str | None:
    named = os.environ.get("CHROME_PATH")
    if named and Path(named).is_file():
        return named
    for name in ("google-chrome", "google-chrome-stable", "chromium",
                 "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    places = [Path(os.environ.get(v, "")) / "Google" / "Chrome" / "Application" / "chrome.exe"
              for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA")
              if os.environ.get(v)]
    places.append(Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"))
    for place in places:
        if place.is_file():
            return str(place)
    return None


class DevTools:
    """One DevTools protocol connection: a WebSocket client (RFC 6455, text
    frames, client-masked) and the id-matched calls the protocol makes."""

    def __init__(self, url: str) -> None:
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname or "127.0.0.1", parts.port or 80
        self.sock = socket.create_connection((host, port), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        self.sock.sendall((f"GET {parts.path} HTTP/1.1\r\nHost: {host}:{port}\r\n"
                           "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                           f"Sec-WebSocket-Key: {key}\r\n"
                           "Sec-WebSocket-Version: 13\r\n\r\n").encode("ascii"))
        self.pending = bytearray()
        while b"\r\n\r\n" not in self.pending:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            self.pending.extend(chunk)
        end = self.pending.index(b"\r\n\r\n")
        status = bytes(self.pending[:end]).split(b"\r\n", 1)[0]
        del self.pending[:end + 4]
        if b" 101 " not in status + b" ":
            raise ConnectionError(f"DevTools refused the upgrade: {status!r}")
        self.next_id = 0
        self.events: list[dict[str, Any]] = []

    def _exactly(self, n: int) -> bytes:
        while len(self.pending) < n:
            chunk = self.sock.recv(max(65536, n - len(self.pending)))
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            self.pending.extend(chunk)
        data = bytes(self.pending[:n])
        del self.pending[:n]
        return data

    def _send(self, text: str) -> None:
        payload = text.encode("utf-8")
        n = len(payload)
        header = bytearray([0x81])
        if n < 126:
            header.append(0x80 | n)
        elif n < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", n)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", n)
        mask = os.urandom(4)
        header += mask
        stream = (mask * (n // 4 + 1))[:n]
        masked = (int.from_bytes(payload, "big") ^ int.from_bytes(stream, "big")
                  ).to_bytes(n, "big") if n else b""
        self.sock.sendall(bytes(header) + masked)

    def _message(self) -> dict[str, Any]:
        data = bytearray()
        while True:
            b1, b2 = self._exactly(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._exactly(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._exactly(8))[0]
            if b2 & 0x80:
                self._exactly(4)
            body = self._exactly(n)
            opcode = b1 & 0x0F
            if opcode == 0x8:
                raise ConnectionError("DevTools closed the connection")
            if opcode in (0x9, 0xA):
                continue
            data.extend(body)
            if b1 & 0x80:
                return cast(dict[str, Any], json.loads(data.decode("utf-8")))

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.next_id += 1
        mine = self.next_id
        self._send(json.dumps({"id": mine, "method": method, "params": params}))
        while True:
            msg = self._message()
            if msg.get("id") == mine:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return cast(dict[str, Any], msg.get("result", {}))
            if "method" in msg:
                self.events.append(msg)

    def wait(self, event: str, seconds: float) -> bool:
        deadline = time.monotonic() + seconds
        while True:
            if any(e.get("method") == event for e in self.events):
                return True
            left = deadline - time.monotonic()
            if left <= 0:
                return False
            # a protocol call is answered in order, so a cheap one reads
            # every event sent before its answer
            self.call("Runtime.evaluate", expression="0")
            if not any(e.get("method") == event for e in self.events):
                time.sleep(min(0.05, max(left, 0)))

    def evaluate(self, expression: str) -> Any:
        got = self.call("Runtime.evaluate", expression=expression,
                        returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in got:
            raise RuntimeError(str(got["exceptionDetails"])[:500])
        return got.get("result", {}).get("value")

    def errors(self) -> list[str]:
        found = []
        for e in self.events:
            method, p = e.get("method"), e.get("params", {})
            if method == "Runtime.exceptionThrown":
                d = p.get("exceptionDetails", {})
                found.append(str(d.get("exception", {}).get("description") or d.get("text")))
            elif method == "Log.entryAdded" and p.get("entry", {}).get("level") == "error":
                entry = p["entry"]
                found.append(f"{entry.get('text')} {entry.get('url', '')}".strip())
            elif method == "Runtime.consoleAPICalled" and p.get("type") == "error":
                found.append(str([a.get("value") for a in p.get("args", [])]))
        return found

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class Chrome:
    def __init__(self, binary: str) -> None:
        self.profile = Path(tempfile.mkdtemp(prefix="chrome-", dir=WORK))
        args = [binary, "--headless=new", "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions",
                "--disable-gpu", "--no-proxy-server", "--hide-scrollbars",
                "--disable-background-networking", "--disable-component-update",
                "--disable-sync", "--mute-audio", "about:blank"]
        if sys.platform.startswith("linux"):
            args.insert(1, "--no-sandbox")
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
        port_file = self.profile / "DevToolsActivePort"
        deadline = time.monotonic() + 60
        while True:
            if port_file.is_file():
                lines = port_file.read_text(encoding="ascii").splitlines()
                if len(lines) >= 2:
                    self.port = int(lines[0])
                    break
            if self.proc.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError("Chrome did not start its DevTools server")
            time.sleep(0.1)

    def tab(self) -> DevTools:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/json/new?about:blank", method="PUT")
        with opener.open(request, timeout=30) as response:
            info = json.loads(response.read().decode("utf-8"))
        tab = DevTools(str(info["webSocketDebuggerUrl"]))
        for domain in ("Page", "Runtime", "Log"):
            tab.call(f"{domain}.enable")
        return tab

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(20)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)


class QuietServer(ThreadingHTTPServer):
    """A browser that moves on mid-request resets its connection; that is
    not a failure of the page, and is not printed."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        if not isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            super().handle_error(request, client_address)


class Quiet(SimpleHTTPRequestHandler):
    extensions_map = {".html": "text/html; charset=utf-8", ".css": "text/css",
                      ".js": "text/javascript", ".json": "application/json",
                      ".txt": "text/plain; charset=utf-8", ".png": "image/png",
                      "": "application/octet-stream"}

    def log_message(self, format: str, *args: Any) -> None:
        pass


def visit(tab: DevTools, url: str, width: int) -> str | None:
    tab.call("Emulation.setDeviceMetricsOverride", width=width,
             height=WIDTHS[width], deviceScaleFactor=1, mobile=width < 960)
    tab.events.clear()
    tab.call("Page.navigate", url=url)
    if not tab.wait("Page.loadEventFired", 30):
        return "did not load within 30 s"
    return None


FIT = """(() => {
  const d = document.documentElement, b = document.body;
  const hidden = [getComputedStyle(d).overflowX, getComputedStyle(b).overflowX]
    .filter(v => v === "hidden" || v === "clip");
  return {doc: d.scrollWidth, body: b.scrollWidth, win: window.innerWidth,
          hidden: hidden.length, codes: document.querySelectorAll(".code").length,
          copies: document.querySelectorAll(".code .copy").length};
})()"""


def check_chrome(out: Path, built: build_docs.Built, require: bool,
                 screenshots: bool) -> None:
    section("in Chrome")
    binary = find_chrome()
    if binary is None:
        if require:
            ok("Chrome is found (CHROME_PATH, PATH or the usual places)", False)
        else:
            skip("Chrome is not found (CHROME_PATH, PATH or the usual places), so "
                 "no page is loaded: the fit at 360px, console errors, the copy "
                 "buttons, the menu, search, the theme toggle and screenshots are "
                 "not checked")
        return
    server = QuietServer(("127.0.0.1", 0),
                         functools.partial(Quiet, directory=str(out)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}/"
    chrome = Chrome(binary)
    tab = chrome.tab()
    shots = HERE / "docs" / "screenshots"
    try:
        pages = [p for p in built.trees[0].pages if p != "playground.html"]
        pages += [built.trees[1].prefix + p for p in ("index.html", "tutorial.html")]
        wide, failed, noisy, uncopied = [], [], [], []
        for page in pages:
            problem = visit(tab, base + page, 360)
            if problem:
                failed.append(f"{page}: {problem}")
                continue
            got = tab.evaluate(FIT)
            if got["doc"] > got["win"] or got["body"] > got["win"] or got["hidden"]:
                wide.append(f"{page}: {got}")
            if got["copies"] != got["codes"]:
                uncopied.append(f"{page}: {got['copies']} of {got['codes']}")
            noisy += [f"{page}: {e}" for e in tab.errors()]
        ok(f"all {len(pages)} pages load in Chrome", not failed, failed)
        ok(f"at 360px no page is wider than the window ({len(pages)} pages)",
           not wide, "\n          ".join(wide[:10]))
        ok("no page logs an error or throws", not noisy, noisy[:10])
        ok("every code block has its copy button", not uncopied, uncopied[:10])
        wide = []
        written = 0
        # the screenshots show the light theme, as a light system sees the
        # site, and the landing page on a dark system too
        shoot = [(page, width, "light") for page in SCREENSHOT_PAGES
                 for width in WIDTHS] + [("index.html", 360, "dark"),
                                         ("index.html", 1280, "dark")]
        for page, width, scheme in shoot:
            tab.call("Emulation.setEmulatedMedia", features=[
                {"name": "prefers-color-scheme", "value": scheme}])
            visit(tab, base + page, width)
            got = tab.evaluate(FIT)
            if got["doc"] > got["win"] or got["body"] > got["win"]:
                wide.append(f"{page} at {width}px ({scheme}): {got}")
            if screenshots:
                shot = tab.call("Page.captureScreenshot", format="png")
                shots.mkdir(parents=True, exist_ok=True)
                stem = page.replace(".html", "") + ("-dark" if scheme == "dark" else "")
                (shots / f"{stem}-{width}.png").write_bytes(
                    base64.b64decode(shot["data"]))
                written += 1
        tab.call("Emulation.setEmulatedMedia", features=[])
        ok(f"{', '.join(SCREENSHOT_PAGES)} fit at {', '.join(map(str, WIDTHS))}px "
           "(and the landing page in the dark theme at 360 and 1280px)",
           not wide, wide)
        if screenshots:
            say(f"  wrote   {written} screenshots to docs/screenshots/")

        visit(tab, base + "tutorial.html", 1280)
        layout = tab.evaluate("""(() => ({
          menu: getComputedStyle(document.querySelector(".menu")).display,
          side: getComputedStyle(document.getElementById("sidebar")).display,
          toc: getComputedStyle(document.querySelector(".toc")).display}))()""")
        ok("at 1280px the sidebar and the table of contents show, and the menu "
           "button does not", layout == {"menu": "none", "side": "block",
                                         "toc": "block"}, layout)
        visit(tab, base + "tutorial.html", 360)
        opened = tab.evaluate("""(async () => {
          const b = document.querySelector(".menu");
          const before = getComputedStyle(document.getElementById("sidebar")).display;
          b.click();
          await new Promise(r => setTimeout(r, 100));
          return {before, after: getComputedStyle(document.getElementById("sidebar")).display,
                  expanded: b.getAttribute("aria-expanded"),
                  fits: document.documentElement.scrollWidth <= innerWidth};
        })()""")
        ok("at 360px the menu button opens the sections, says so with "
           "aria-expanded, and the page still fits",
           opened == {"before": "none", "after": "block", "expanded": "true",
                      "fits": True}, opened)
        found = tab.evaluate("""(async () => {
          const i = document.getElementById("search");
          i.focus(); i.value = "E700";
          i.dispatchEvent(new Event("input", {bubbles: true}));
          for (let k = 0; k < 100; k++) {
            await new Promise(r => setTimeout(r, 50));
            const links = [...document.querySelectorAll("#search-results a")];
            if (links.length) {
              i.dispatchEvent(new KeyboardEvent("keydown", {key: "ArrowDown", bubbles: true}));
              return {hrefs: links.slice(0, 5).map(a => a.getAttribute("href")),
                      focused: document.activeElement === links[0],
                      fits: document.documentElement.scrollWidth <= innerWidth};
            }
          }
          return null;
        })()""")
        ok("search for E700 finds errors.html#E700, ArrowDown moves into the "
           "results, and the page still fits",
           found and any(h.endswith("errors.html#E700") for h in found["hrefs"])
           and found["focused"] and found["fits"], found)
        state = """[document.documentElement.getAttribute("data-theme"),
          document.querySelector(".theme").getAttribute("aria-pressed"),
          getComputedStyle(document.body).backgroundColor]"""
        tab.evaluate("localStorage.clear()")
        seen = {}
        for scheme in ("dark", "light"):
            tab.call("Emulation.setEmulatedMedia", features=[
                {"name": "prefers-color-scheme", "value": scheme}])
            visit(tab, base + "index.html", 360)
            seen[scheme] = tab.evaluate(state)
        ok("with no choice made the theme follows the system: aria-pressed and "
           "the page's ground are dark on a dark system and light on a light one",
           seen["dark"][:2] == [None, "true"] and seen["light"][:2] == [None, "false"]
           and seen["dark"][2] != seen["light"][2], seen)
        tab.evaluate('document.querySelector(".theme").click()')
        after = tab.evaluate(state)
        visit(tab, base + "index.html", 360)
        kept = tab.evaluate(state)
        tab.evaluate("localStorage.clear()")
        tab.call("Emulation.setEmulatedMedia", features=[])
        ok("on a light system the toggle turns dark, says so with aria-pressed, "
           "and the choice is remembered after a reload",
           after[:2] == ["dark", "true"] and kept[:2] == ["dark", "true"]
           and after[2] == seen["dark"][2], (after, kept))
        noisy = tab.errors()
        ok("...and nothing logged an error along the way", not noisy, noisy[:5])
    finally:
        tab.close()
        chrome.close()
        server.shutdown()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0] if __doc__ else "")
    parser.add_argument("--no-chrome", action="store_true")
    parser.add_argument("--require-chrome", action="store_true")
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args(argv)
    out = WORK / "docs"
    out.mkdir()
    started = time.time()
    built = build(out)
    check_build(out, built)
    parsed = check_pages(out, built)
    check_search(out, built, parsed)
    check_landing(out, built, parsed)
    check_findable(out, built)
    check_stale(built, args.require_chrome)
    check_design()
    check_earlier(out, built)
    if args.no_chrome and not (args.require_chrome or args.screenshots):
        section("in Chrome")
        skip("--no-chrome: no page is loaded (the fit at 360px, console errors, "
             "the copy buttons, the menu, search, the theme toggle)")
    else:
        check_chrome(out, built, args.require_chrome or args.screenshots,
                     args.screenshots)
    say("-" * 62)
    say(f"{PASS} correct, {FAIL} wrong, {SKIPPED} skipped, "
        f"{time.time() - started:.0f} s")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
