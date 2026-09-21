#!/usr/bin/env python3
"""Markdown into HTML, for the documentation site (8.3.1).

build_docs.py renders README-style documents - TUTORIAL.md, SPEC.md,
THREAT_MODEL.md and the rest - with this module, and check_site.py holds
what it writes. It needs nothing outside the standard library, as Sabline
does not.

What it reads, as CommonMark and GitHub read it:

  blocks   ATX headings (# to ######) and setext headings (a line of = or
           - under a paragraph); paragraphs; fenced code (``` or ~~~, with
           an info word) and indented code (four spaces); block quotes;
           bullet lists (- * +) and ordered lists (1. or 1)), nested to any
           depth, tight or loose, with lazy continuation lines; thematic
           breaks; GitHub tables, with alignment; footnote definitions
           ([^label]: text); link reference definitions ([label]: url);
           HTML comments, which are dropped (check_docs.py's markers).
  inline   code spans of any number of backticks; emphasis and strong
           emphasis with * and _ by CommonMark's delimiter rules;
           strikethrough (~~); links [text](url "title"), reference links
           [text][label], [label][] and [label]; images; autolinks <url>
           and bare http(s):// URLs; footnote references [^label];
           backslash escapes; entity references; hard line breaks (two
           spaces or a backslash at the end of a line).

Raw HTML is not passed through: a tag written in running text is shown as
the text it is (a document's `<file>` placeholders are meant to be read),
and a comment is dropped.

CALLOUTS. A block quote whose first line is one of

    > [!NOTE]            > **Note.** text ...
    > [!REFUSES]         > **Refuses.** text ...
    > [!KNOWN-OPEN]      > **Known open.** text ...

is a callout of that kind: a note, something Sabline refuses, or a
problem that is known and not yet closed. The [!KIND] line is GitHub's
alert syntax (GitHub shows NOTE as an alert, and the other two as a quote
starting with the marker); the bold lead-in reads the same everywhere. Any
other block quote is a block quote.

Heading ids are GitHub's: the heading's text, lower-cased, with every
character but letters, digits, spaces, hyphens and underscores removed,
spaces made hyphens, and -1, -2 ... added to a repeat - so a link written
for GitHub, SPEC.md#31-secret-of-t, finds the same heading here.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Callable, Union

# ---------------------------------------------------------------------------
# what rendering gives back


@dataclass
class Heading:
    level: int
    text: str           # plain text, as the table of contents shows it
    id: str


@dataclass
class Rendered:
    html: str
    title: str | None                     # the first level-1 heading
    headings: list[Heading]
    # (the id of the heading above it, or "", the plain text) for every
    # paragraph, list item's text and table row: what search reads
    texts: list[tuple[str, str]]


LinkFn = Callable[[str], str]
# (info word, code) -> (label shown above the block, HTML inside <code>)
HighlightFn = Callable[[str, str], tuple[str, str]]


def _same(href: str) -> str:
    return href


def _plain_code(info: str, code: str) -> tuple[str, str]:
    return (info or "text", html.escape(code, quote=False))


class Slugger:
    """GitHub's heading ids, a repeat numbered."""

    def __init__(self, taken: set[str] | None = None) -> None:
        self.seen: dict[str, int] = {}
        for t in taken or ():
            self.seen[t] = 0

    def slug(self, text: str) -> str:
        base = re.sub(r"[^\w\- ]", "", text.strip().lower()).replace(" ", "-")
        if base not in self.seen:
            self.seen[base] = 0
            return base
        n = self.seen[base]
        while True:
            n += 1
            candidate = f"{base}-{n}"
            if candidate not in self.seen:
                self.seen[base] = n
                self.seen[candidate] = 0
                return candidate


# ---------------------------------------------------------------------------
# blocks

@dataclass
class Para:
    lines: list[str]


@dataclass
class HeadingBlock:
    level: int
    raw: str


@dataclass
class Code:
    info: str
    lines: list[str]


@dataclass
class Rule:
    pass


@dataclass
class Quote:
    children: list[Block]


@dataclass
class ListBlock:
    ordered: bool
    start: int
    items: list[list[Block]]
    loose: bool


@dataclass
class Table:
    header: list[str]
    aligns: list[str]
    rows: list[list[str]]


@dataclass
class FootnoteDef:
    label: str
    children: list[Block]


Block = Union[Para, HeadingBlock, Code, Rule, Quote, ListBlock, Table,
              FootnoteDef]

ATX = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
FENCE_OPEN = re.compile(r"^( {0,3})(`{3,}|~{3,})[ \t]*(.*?)[ \t]*$")
RULE = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
SETEXT = re.compile(r"^ {0,3}(=+|-+)[ \t]*$")
BULLET = re.compile(r"^( {0,3})([-+*])( +|$)")
ORDERED = re.compile(r"^( {0,3})(\d{1,9})([.)])( +|$)")
QUOTE = re.compile(r"^ {0,3}> ?")
FOOTDEF = re.compile(r"^ {0,3}\[\^([^\]\s]+)\]:[ \t]?(.*)$")
REFDEF = re.compile(r"^ {0,3}\[([^\]]+)\]:[ \t]*(<[^>]*>|\S+)"
                    r"(?:[ \t]+(\"[^\"]*\"|'[^']*'|\([^)]*\)))?[ \t]*$")
DELIM_ROW = re.compile(r"^ {0,3}\|?[ \t]*:?-+:?[ \t]*(\|[ \t]*:?-+:?[ \t]*)*\|?[ \t]*$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _blank(line: str) -> bool:
    return not line.strip()


def _cells(row: str) -> list[str]:
    """A table row's cells: split on | that is not escaped and not inside a
    code span."""
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, cur, i, tick = [], [], 0, 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if c == "`":
            run = len(s[i:]) - len(s[i:].lstrip("`"))
            if tick == 0:
                tick = run
            elif run == tick:
                tick = 0
            cur.append(s[i:i + run])
            i += run
            continue
        if c == "|" and tick == 0:
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
        i += 1
    cells.append("".join(cur).strip())
    return cells


class Parser:
    def __init__(self) -> None:
        self.refs: dict[str, tuple[str, str]] = {}
        self.footnotes: dict[str, list[Block]] = {}

    # a line that starts a block other than a paragraph, and so ends one
    def interrupts(self, line: str, next_line: str | None) -> bool:
        if _blank(line):
            return True
        if ATX.match(line) or _fence(line) is not None:
            return True
        if RULE.match(line) or QUOTE.match(line):
            return True
        if line.lstrip().startswith("<!--") and _indent(line) < 4:
            return True
        m = BULLET.match(line)
        if m and m.group(3):
            return True
        m = ORDERED.match(line)
        if m and m.group(4) and m.group(2) == "1":
            return True
        if (next_line is not None and "|" in line
                and DELIM_ROW.match(next_line) and "-" in next_line
                and len(_cells(line)) == len(_cells(next_line))):
            return True
        return False

    def parse(self, lines: list[str]) -> tuple[list[Block], bool]:
        """(the blocks, whether a blank line stood between two of them)"""
        blocks: list[Block] = []
        blank_between = False
        pending_blank = False
        i, n = 0, len(lines)
        while i < n:
            line = lines[i]
            if _blank(line):
                pending_blank = True
                i += 1
                continue
            if pending_blank and blocks:
                blank_between = True
            pending_blank = False
            ind = _indent(line)
            nxt = lines[i + 1] if i + 1 < n else None

            if ind >= 4:                                   # indented code
                body: list[str] = []
                while i < n and (_blank(lines[i]) or _indent(lines[i]) >= 4):
                    body.append(lines[i][4:] if not _blank(lines[i]) else "")
                    i += 1
                while body and not body[-1].strip():
                    body.pop()
                blocks.append(Code("", body))
                continue

            m = _fence(line)
            if m:
                pad, fence, info = len(m.group(1)), m.group(2), m.group(3)
                body = []
                i += 1
                while i < n:
                    close = re.match(r"^ {0,3}(`{3,}|~{3,})[ \t]*$", lines[i])
                    if close and close.group(1)[0] == fence[0] \
                            and len(close.group(1)) >= len(fence):
                        i += 1
                        break
                    text = lines[i]
                    strip = min(pad, _indent(text))
                    body.append(text[strip:])
                    i += 1
                blocks.append(Code(info.split()[0] if info else "", body))
                continue

            m = ATX.match(line)
            if m:
                blocks.append(HeadingBlock(len(m.group(1)), m.group(2) or ""))
                i += 1
                continue

            if line.lstrip().startswith("<!--"):           # a comment: dropped
                while i < n and "-->" not in lines[i]:
                    i += 1
                rest = lines[i].split("-->", 1)[1] if i < n else ""
                i += 1
                if rest.strip():
                    lines = lines[:i] + [rest] + lines[i:]
                    n = len(lines)
                continue

            if RULE.match(line) and not (BULLET.match(line) and not
                                         re.match(r"^ {0,3}([-*_])[ \t]*\1", line)):
                blocks.append(Rule())
                i += 1
                continue

            if QUOTE.match(line):
                inner: list[str] = []
                while i < n:
                    cur = lines[i]
                    q = QUOTE.match(cur)
                    if q:
                        inner.append(cur[q.end():])
                    elif (not _blank(cur) and inner and not _blank(inner[-1])
                          and not self.interrupts(cur, None)):
                        inner.append(cur)                  # lazy continuation
                    else:
                        break
                    i += 1
                children, _ = Parser.sub(self, inner)
                blocks.append(Quote(children))
                continue

            m = FOOTDEF.match(line)
            if m:
                label = m.group(1).lower()
                inner = [m.group(2)]
                i += 1
                while i < n:
                    cur = lines[i]
                    if _blank(cur):
                        if i + 1 < n and _indent(lines[i + 1]) >= 4:
                            inner.append("")
                            i += 1
                            continue
                        break
                    if _indent(cur) >= 4:
                        inner.append(cur[4:])
                    elif not self.interrupts(cur, None) and not FOOTDEF.match(cur):
                        inner.append(cur)
                    else:
                        break
                    i += 1
                children, _ = Parser.sub(self, inner)
                self.footnotes.setdefault(label, children)
                continue

            m = REFDEF.match(line)
            if m and not m.group(1).startswith("^"):
                dest = m.group(2)
                if dest.startswith("<") and dest.endswith(">"):
                    dest = dest[1:-1]
                title = m.group(3)[1:-1] if m.group(3) else ""
                self.refs.setdefault(_norm_label(m.group(1)), (dest, title))
                i += 1
                continue

            bm, om = BULLET.match(line), ORDERED.match(line)
            if bm or om:
                block, i, loose_inside = self.parse_list(lines, i)
                blocks.append(block)
                continue

            if (nxt is not None and "|" in line and DELIM_ROW.match(nxt)
                    and "-" in nxt and len(_cells(line)) == len(_cells(nxt))):
                header = _cells(line)
                aligns = []
                for cell in _cells(nxt):
                    c = cell.strip()
                    aligns.append("center" if c.startswith(":") and c.endswith(":")
                                  else "right" if c.endswith(":")
                                  else "left" if c.startswith(":") else "")
                rows = []
                i += 2
                while i < n and not _blank(lines[i]) and "|" in lines[i] \
                        and not (ATX.match(lines[i]) or QUOTE.match(lines[i])
                                 or FENCE_OPEN.match(lines[i])):
                    cells = _cells(lines[i])
                    cells = (cells + [""] * len(header))[:len(header)]
                    rows.append(cells)
                    i += 1
                blocks.append(Table(header, aligns, rows))
                continue

            # a paragraph
            para = [line.strip()]
            i += 1
            while i < n:
                cur = lines[i]
                if _blank(cur):
                    break
                s = SETEXT.match(cur)
                if s and _indent(cur) < 4:
                    level = 1 if s.group(1).startswith("=") else 2
                    blocks.append(HeadingBlock(level, " ".join(para)))
                    para = []
                    i += 1
                    break
                if _indent(cur) < 4 and self.interrupts(
                        cur, lines[i + 1] if i + 1 < n else None):
                    break
                para.append(cur.strip() if not cur.endswith("  ")
                            else cur.lstrip())
                i += 1
            if para:
                # two spaces at the end of the last line are not a break
                para[-1] = para[-1].rstrip()
                blocks.append(Para(para))
        return blocks, blank_between

    def sub(self, lines: list[str]) -> tuple[list[Block], bool]:
        return self.parse(lines)

    def parse_list(self, lines: list[str], i: int) -> tuple[ListBlock, int, bool]:
        n = len(lines)
        first = lines[i]
        bm, om = BULLET.match(first), ORDERED.match(first)
        ordered = om is not None and bm is None
        kind = (om.group(3) if ordered and om else bm.group(2) if bm else "")
        start = int(om.group(2)) if ordered and om else 1
        items: list[list[Block]] = []
        loose = False
        while i < n:
            line = lines[i]
            bm, om = BULLET.match(line), ORDERED.match(line)
            if ordered:
                if not om or om.group(3) != kind:
                    break
                pad, marker, spaces = len(om.group(1)), om.group(2) + om.group(3), om.group(4)
            else:
                if not bm or bm.group(2) != kind or RULE.match(line):
                    break
                pad, marker, spaces = len(bm.group(1)), bm.group(2), bm.group(3)
            rest = line[pad + len(marker) + len(spaces):]
            if not spaces or not rest.strip():
                offset = pad + len(marker) + 1
                content = [rest.strip()] if rest.strip() else []
            elif len(spaces) >= 5:
                offset = pad + len(marker) + 1
                content = [line[offset:]]
            else:
                offset = pad + len(marker) + len(spaces)
                content = [rest]
            i += 1
            in_fence: str | None = None
            while i < n:
                cur = lines[i]
                if in_fence is not None:
                    content.append(cur[offset:] if _indent(cur) >= offset
                                   else cur.lstrip())
                    close = re.match(r"^ *(`{3,}|~{3,})[ \t]*$", cur)
                    if close and close.group(1)[0] == in_fence[0] \
                            and len(close.group(1)) >= len(in_fence):
                        in_fence = None
                    i += 1
                    continue
                if _blank(cur):
                    # a blank line belongs to the item only if something
                    # indented under it follows
                    j = i
                    while j < n and _blank(lines[j]):
                        j += 1
                    if j < n and _indent(lines[j]) >= offset:
                        content.extend([""] * (j - i))
                        i = j
                        continue
                    break
                if _indent(cur) >= offset:
                    text = cur[offset:]
                    fm = _fence(text)
                    if fm:
                        in_fence = fm.group(2)
                    content.append(text)
                    i += 1
                    continue
                # a new item, of this list or another, ends this one
                if _item_start(cur):
                    break
                # a lazy continuation of the item's last paragraph
                if (content and not _blank(content[-1])
                        and not self.interrupts(cur, None)
                        and not SETEXT.match(cur)):
                    content.append(cur.strip())
                    i += 1
                    continue
                break
            children, blank_inside = self.parse(content)
            if blank_inside:
                loose = True
            items.append(children)
            # blank lines, then another item of this list: loose
            j = i
            while j < n and _blank(lines[j]):
                j += 1
            if j > i and j < n:
                nb, no = BULLET.match(lines[j]), ORDERED.match(lines[j])
                same = (no is not None and no.group(3) == kind) if ordered else (
                    nb is not None and nb.group(2) == kind
                    and not RULE.match(lines[j]))
                if same:
                    loose = True
                    i = j
                    continue
                break
        return ListBlock(ordered, start, items, loose), i, loose


def _item_start(line: str) -> bool:
    bm, om = BULLET.match(line), ORDERED.match(line)
    return bool((bm and bm.group(3) and not RULE.match(line))
                or (om and om.group(4)))


def _fence(line: str) -> re.Match[str] | None:
    """An opening code fence; a backtick fence's info word holds no backtick
    (CommonMark), so ``` `x` ``` on one line is a code span."""
    m = FENCE_OPEN.match(line)
    if m and m.group(2).startswith("`") and "`" in m.group(3):
        return None
    return m


def _norm_label(label: str) -> str:
    return " ".join(label.split()).lower()


# ---------------------------------------------------------------------------
# inline

ESCAPABLE = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
PUNCT = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~") | set(
    "\u2013\u2014\u2018\u2019\u201c\u201d\u2026\u00a7\u00b7")
ENTITY = re.compile(r"&(?:#[xX][0-9a-fA-F]{1,6}|#\d{1,7}|[A-Za-z][A-Za-z0-9]{1,31});")
AUTOLINK = re.compile(r"<((?:https?|mailto|ftp):[^\s<>]*)>")
BARE_URL = re.compile(r"https?://[^\s<]*[^\s<?!.,:*_~'\")\]]")


@dataclass
class _Delim:
    char: str
    count: int
    orig: int
    can_open: bool
    can_close: bool


@dataclass
class _Html:
    html: str


@dataclass
class _Text:
    text: str


_Item = Union[_Delim, _Html, _Text]


def _is_ws(c: str) -> bool:
    return c == "" or c.isspace()


def _is_punct(c: str) -> bool:
    return c in PUNCT or (c != "" and not c.isalnum() and not c.isspace()
                          and ord(c) > 127 and c not in "\u00a0")


@dataclass
class Inline:
    link: LinkFn
    refs: dict[str, tuple[str, str]]
    footnotes: dict[str, list[Block]]
    footnote_order: list[str] = field(default_factory=list)
    autolink_text: Callable[[str], str] = _same

    def render(self, text: str, in_link: bool = False) -> str:
        items = self.scan(text, in_link)
        return self.emphasis(items)

    def code_span(self, text: str, i: int) -> tuple[str, int] | None:
        run = len(text[i:]) - len(text[i:].lstrip("`"))
        j = i + run
        while True:
            k = text.find("`" * run, j)
            if k < 0:
                return None
            end_run = len(text[k:]) - len(text[k:].lstrip("`"))
            if end_run == run:
                body = text[i + run:k].replace("\n", " ")
                if (body.startswith(" ") and body.endswith(" ")
                        and body.strip(" ")):
                    body = body[1:-1]
                return (f"<code>{html.escape(body, quote=False)}</code>",
                        k + run)
            j = k + end_run

    def bracket_end(self, text: str, i: int) -> int:
        """The index of the ] that closes the [ at i, or -1."""
        depth, j = 0, i
        while j < len(text):
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "`":
                got = self.code_span(text, j)
                if got:
                    j = got[1]
                    continue
                j += len(text[j:]) - len(text[j:].lstrip("`"))
                continue
            if c == "<":
                m = AUTOLINK.match(text, j)
                if m:
                    j = m.end()
                    continue
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return -1

    def destination(self, text: str, i: int) -> tuple[str, str, int] | None:
        """Parse `(dest "title")` starting at text[i] == "("."""
        j = i + 1
        while j < len(text) and text[j] in " \t\n":
            j += 1
        if j < len(text) and text[j] == "<":
            k = text.find(">", j)
            if k < 0:
                return None
            dest = text[j + 1:k]
            j = k + 1
        else:
            depth, start = 0, j
            while j < len(text):
                c = text[j]
                if c == "\\" and j + 1 < len(text):
                    j += 2
                    continue
                if c.isspace():
                    break
                if c == "(":
                    depth += 1
                elif c == ")":
                    if depth == 0:
                        break
                    depth -= 1
                j += 1
            dest = text[start:j]
        while j < len(text) and text[j] in " \t\n":
            j += 1
        title = ""
        if j < len(text) and text[j] in "\"'(":
            close = ")" if text[j] == "(" else text[j]
            k = text.find(close, j + 1)
            if k < 0:
                return None
            title = text[j + 1:k]
            j = k + 1
            while j < len(text) and text[j] in " \t\n":
                j += 1
        if j >= len(text) or text[j] != ")":
            return None
        return _unescape(dest), _unescape(title), j + 1

    def anchor(self, href: str, inner: str, title: str) -> str:
        target = self.link(href)
        t = f' title="{html.escape(title)}"' if title else ""
        return f'<a href="{html.escape(target)}"{t}>{inner}</a>'

    def scan(self, text: str, in_link: bool) -> list[_Item]:
        items: list[_Item] = []
        buf: list[str] = []
        i, n = 0, len(text)

        def flush() -> None:
            if buf:
                items.append(_Text("".join(buf)))
                buf.clear()

        while i < n:
            c = text[i]
            if c == "\\" and i + 1 < n:
                if text[i + 1] == "\n":
                    flush()
                    items.append(_Html("<br>\n"))
                    i += 2
                    continue
                if text[i + 1] in ESCAPABLE:
                    buf.append(text[i + 1])
                    i += 2
                    continue
            if c == "\n":
                if buf and "".join(buf).endswith("  "):
                    kept = "".join(buf).rstrip(" ")
                    buf.clear()
                    buf.append(kept)
                    flush()
                    items.append(_Html("<br>\n"))
                else:
                    while buf and buf[-1].endswith(" "):
                        buf[-1] = buf[-1].rstrip(" ")
                        if buf[-1]:
                            break
                        buf.pop()
                    buf.append("\n")
                i += 1
                continue
            if c == "`":
                got = self.code_span(text, i)
                run = len(text[i:]) - len(text[i:].lstrip("`"))
                if got:
                    flush()
                    items.append(_Html(got[0]))
                    i = got[1]
                else:
                    buf.append("`" * run)
                    i += run
                continue
            if c == "<":
                if text.startswith("<!--", i):
                    k = text.find("-->", i + 4)
                    if k >= 0:
                        i = k + 3
                        continue
                m = AUTOLINK.match(text, i)
                if m and not in_link:
                    flush()
                    url = m.group(1)
                    shown = html.escape(self.autolink_text(url), quote=False)
                    items.append(_Html(self.anchor(url, shown, "")))
                    i = m.end()
                    continue
            if c == "&":
                m = ENTITY.match(text, i)
                if m and html.unescape(m.group(0)) != m.group(0):
                    buf.append(html.unescape(m.group(0)))
                    i = m.end()
                    continue
            if c == "h" and not in_link and text.startswith(("http://", "https://"), i) \
                    and (i == 0 or text[i - 1] in " \t\n(*_~\"'"):
                m = BARE_URL.match(text, i)
                if m:
                    url = m.group(0)
                    # a closing parenthesis that is not the URL's own
                    while url.endswith(")") and url.count(")") > url.count("("):
                        url = url[:-1]
                    flush()
                    shown = html.escape(self.autolink_text(url), quote=False)
                    items.append(_Html(self.anchor(url, shown, "")))
                    i += len(url)
                    continue
            image = c == "!" and i + 1 < n and text[i + 1] == "["
            if (c == "[" or image):
                start = i + 1 if image else i
                # a footnote reference
                fm = re.match(r"\[\^([^\]\s]+)\]", text[start:])
                if not image and fm and fm.group(1).lower() in self.footnotes:
                    flush()
                    label = fm.group(1).lower()
                    if label not in self.footnote_order:
                        self.footnote_order.append(label)
                    num = self.footnote_order.index(label) + 1
                    ident = _foot_id(label)
                    items.append(_Html(
                        f'<sup class="fnref"><a href="#fn-{ident}" '
                        f'id="fnref-{ident}">{num}</a></sup>'))
                    i = start + fm.end()
                    continue
                end = self.bracket_end(text, start)
                if end > 0 and not (in_link and not image):
                    label_text = text[start + 1:end]
                    target: tuple[str, str] | None = None
                    after = end + 1
                    if end + 1 < n and text[end + 1] == "(":
                        dest = self.destination(text, end + 1)
                        if dest:
                            target = (dest[0], dest[1])
                            after = dest[2]
                    if target is None and end + 1 < n and text[end + 1] == "[":
                        close = text.find("]", end + 2)
                        if close > 0:
                            ref = text[end + 2:close] or label_text
                            if _norm_label(ref) in self.refs:
                                target = self.refs[_norm_label(ref)]
                                after = close + 1
                    if target is None and _norm_label(label_text) in self.refs:
                        target = self.refs[_norm_label(label_text)]
                    if target is not None:
                        flush()
                        if image:
                            alt = _strip_tags(self.render(label_text, True))
                            src = self.link(target[0])
                            t = (f' title="{html.escape(target[1])}"'
                                 if target[1] else "")
                            items.append(_Html(
                                f'<img src="{html.escape(src)}" '
                                f'alt="{html.escape(alt)}"{t}>'))
                        else:
                            inner = self.render(label_text, True)
                            items.append(_Html(self.anchor(target[0], inner,
                                                           target[1])))
                        i = after
                        continue
            if c in "*_~":
                run = len(text[i:]) - len(text[i:].lstrip(c))
                before = text[i - 1] if i > 0 else ""
                after_c = text[i + run] if i + run < n else ""
                left = not _is_ws(after_c) and (
                    not _is_punct(after_c) or _is_ws(before) or _is_punct(before))
                right = not _is_ws(before) and (
                    not _is_punct(before) or _is_ws(after_c) or _is_punct(after_c))
                if c == "_":
                    can_open = left and (not right or _is_punct(before))
                    can_close = right and (not left or _is_punct(after_c))
                elif c == "~":
                    can_open, can_close = left, right
                    if run != 2:
                        can_open = can_close = False
                else:
                    can_open, can_close = left, right
                flush()
                items.append(_Delim(c, run, run, can_open, can_close))
                i += run
                continue
            buf.append(c)
            i += 1
        flush()
        return items

    def emphasis(self, items: list[_Item]) -> str:
        i = 0
        while i < len(items):
            closer = items[i]
            if not (isinstance(closer, _Delim) and closer.can_close
                    and closer.count > 0):
                i += 1
                continue
            found = -1
            j = i - 1
            while j >= 0:
                op = items[j]
                if (isinstance(op, _Delim) and op.char == closer.char
                        and op.can_open and op.count > 0):
                    if closer.char == "~":
                        if op.count == closer.count:
                            found = j
                            break
                    elif ((op.can_close or closer.can_open)
                          and (op.orig + closer.orig) % 3 == 0
                          and not (op.orig % 3 == 0 and closer.orig % 3 == 0)):
                        pass
                    else:
                        found = j
                        break
                j -= 1
            if found < 0:
                i += 1
                continue
            op = items[found]
            assert isinstance(op, _Delim)
            if closer.char == "~":
                use, tag = 2, "del"
            elif op.count >= 2 and closer.count >= 2:
                use, tag = 2, "strong"
            else:
                use, tag = 1, "em"
            inner = self.flatten(items[found + 1:i])
            op.count -= use
            closer.count -= use
            items[found + 1:i] = [_Html(f"<{tag}>{inner}</{tag}>")]
            i = found + 2
            if op.count == 0:
                del items[found]
                i -= 1
            if closer.count == 0:
                del items[i]
        return self.flatten(items)

    @staticmethod
    def flatten(items: list[_Item]) -> str:
        out = []
        for it in items:
            if isinstance(it, _Text):
                out.append(html.escape(it.text, quote=False))
            elif isinstance(it, _Html):
                out.append(it.html)
            else:
                out.append(it.char * it.count)
        return "".join(out)


def _unescape(s: str) -> str:
    s = re.sub(r"\\([!-/:-@\[-`{-~])", r"\1", s)
    return html.unescape(s)


def _strip_tags(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


def _foot_id(label: str) -> str:
    return re.sub(r"[^\w-]", "-", label)


# ---------------------------------------------------------------------------
# blocks into HTML

CALLOUTS = {"NOTE": ("note", "Note"), "REFUSES": ("refuses", "Refuses"),
            "KNOWN-OPEN": ("known-open", "Known open"),
            "KNOWN OPEN": ("known-open", "Known open")}
LEAD_IN = re.compile(r"^\*\*(Note|Refuses|Known open)\.\*\*\s*", re.I)


class Renderer:
    def __init__(self, link: LinkFn, highlight: HighlightFn, slugger: Slugger,
                 autolink_text: Callable[[str], str],
                 heading_filter: Callable[[int], bool]) -> None:
        self.parser = Parser()
        self.link, self.highlight, self.slugger = link, highlight, slugger
        self.autolink_text = autolink_text
        self.heading_filter = heading_filter
        self.headings: list[Heading] = []
        self.texts: list[tuple[str, str]] = []
        self.title: str | None = None
        self.inline = Inline(link, self.parser.refs, self.parser.footnotes,
                             autolink_text=autolink_text)

    def current_heading(self) -> str:
        return self.headings[-1].id if self.headings else ""

    def text_of(self, rendered: str) -> None:
        plain = " ".join(_strip_tags(rendered).split())
        if plain:
            self.texts.append((self.current_heading(), plain))

    def blocks(self, blocks: list[Block], tight: bool = False) -> str:
        out: list[str] = []
        for b in blocks:
            out.append(self.block(b, tight))
        return "\n".join(x for x in out if x)

    def block(self, b: Block, tight: bool) -> str:
        if isinstance(b, Para):
            inner = self.inline.render("\n".join(b.lines))
            self.text_of(inner)
            return inner if tight else f"<p>{inner}</p>"
        if isinstance(b, HeadingBlock):
            inner = self.inline.render(b.raw.strip())
            text = " ".join(_strip_tags(inner).split())
            ident = self.slugger.slug(text)
            if b.level == 1 and self.title is None:
                self.title = text
            self.headings.append(Heading(b.level, text, ident))
            anchor = ""
            if b.level > 1:
                anchor = (f' <a class="anchor" href="#{ident}" '
                          'aria-label="Link to this section">#</a>')
            return f'<h{b.level} id="{ident}">{inner}{anchor}</h{b.level}>'
        if isinstance(b, Code):
            # the copy button is the site script's to add: without a script
            # it could do nothing
            code = "\n".join(b.lines)
            label, inner = self.highlight(b.info, code)
            return ('<div class="code"><div class="code-bar">'
                    f'<span class="code-lang">{html.escape(label)}</span>'
                    f'</div><pre tabindex="0"><code>{inner}</code></pre></div>')
        if isinstance(b, Rule):
            return "<hr>"
        if isinstance(b, Quote):
            return self.quote(b)
        if isinstance(b, ListBlock):
            tag = "ol" if b.ordered else "ul"
            start = (f' start="{b.start}"' if b.ordered and b.start != 1
                     else "")
            items = []
            for item in b.items:
                body = self.blocks(item, tight=not b.loose)
                items.append(f"<li>{body}</li>")
            return f"<{tag}{start}>\n" + "\n".join(items) + f"\n</{tag}>"
        if isinstance(b, Table):
            return self.table(b)
        return ""

    def quote(self, b: Quote) -> str:
        children = list(b.children)
        kind: tuple[str, str] | None = None
        if children and isinstance(children[0], Para):
            first = children[0]
            m = re.match(r"^\[!([A-Za-z -]+)\]\s*$", first.lines[0])
            if m and m.group(1).upper() in CALLOUTS:
                kind = CALLOUTS[m.group(1).upper()]
                rest = first.lines[1:]
                children[0] = Para(rest)
                if not rest:
                    children.pop(0)
            else:
                lead = LEAD_IN.match(first.lines[0])
                if lead:
                    kind = CALLOUTS[lead.group(1).upper().replace("KNOWN OPEN",
                                                                  "KNOWN-OPEN")]
                    rest = [first.lines[0][lead.end():]] + first.lines[1:]
                    if not "".join(rest).strip():
                        children.pop(0)
                    else:
                        children[0] = Para(rest)
        body = self.blocks(children)
        if kind is None:
            return f"<blockquote>\n{body}\n</blockquote>"
        cls, title = kind
        return (f'<div class="callout callout-{cls}" role="note">'
                f'<p class="callout-title">{title}</p>\n{body}\n</div>')

    def table(self, t: Table) -> str:
        def cell(tag: str, text: str, align: str) -> str:
            inner = self.inline.render(text)
            cls = f' class="al-{align}"' if align else ""
            return f"<{tag}{cls}>{inner}</{tag}>"

        head = "".join(cell("th", h, a) for h, a in zip(t.header, t.aligns))
        rows = []
        for r in t.rows:
            cells = [cell("td", c, a) for c, a in zip(r, t.aligns)]
            self.text_of(" - ".join(cells))
            rows.append("<tr>" + "".join(cells) + "</tr>")
        return ('<div class="table-wrap" tabindex="0"><table>\n'
                f"<thead><tr>{head}</tr></thead>\n<tbody>\n"
                + "\n".join(rows) + "\n</tbody></table></div>")

    def footnotes(self) -> str:
        if not self.inline.footnote_order:
            return ""
        items = []
        for label in self.inline.footnote_order:
            ident = _foot_id(label)
            body = self.blocks(self.parser.footnotes[label], tight=True)
            items.append(f'<li id="fn-{ident}">{body} <a class="fnback" '
                         f'href="#fnref-{ident}" aria-label="Back to the '
                         f'text">back</a></li>')
        return ('<section class="footnotes" aria-label="Footnotes"><ol>\n'
                + "\n".join(items) + "\n</ol></section>")


def render(md: str, link: LinkFn = _same, highlight: HighlightFn = _plain_code,
           slugger: Slugger | None = None,
           autolink_text: Callable[[str], str] = _same) -> Rendered:
    """Render a Markdown document. `link` maps every link and image target
    as written to the one the page uses; `highlight` gives a code block's
    label and inner HTML; `slugger` makes heading ids, and may be shared by
    several parts of one document so their ids stay GitHub's."""
    r = Renderer(link, highlight, slugger or Slugger(), autolink_text,
                 lambda level: True)
    lines = md.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).split("\n")
    blocks, _ = r.parser.parse(lines)
    body = r.blocks(blocks)
    body += "\n" + r.footnotes() if r.inline.footnote_order else ""
    return Rendered(body, r.title, r.headings, r.texts)


def heading_ids(md: str, slugger: Slugger | None = None) -> list[Heading]:
    """The headings a document would get, without rendering it."""
    return render(md, slugger=slugger).headings
