"""sabline permissions-ratchet: the permissions a repository's GitHub
Actions workflows give their jobs, at the working tree against a git ref.

    sabline permissions-ratchet --against REF [--json] [--root DIR]

Every workflow file directly inside .github/workflows/ (*.yml and *.yaml;
GitHub reads no subdirectory there) is read twice: as it is in the working
tree - the head - and as REF has it, read with `git ls-tree` and
`git show REF:PATH`, nothing checked out. The top of the working tree is
the one that holds DIR (default: the current directory).

What is compared
----------------
A level is none, read or write, in that order. The known scopes are
actions, attestations, checks, contents, deployments, discussions,
id-token, issues, models, packages, pages, pull-requests,
repository-projects, security-events, statuses and artifact-metadata.

A `permissions:` block is one of:

- a mapping of scopes to levels. A scope it does not list is none. A
  scope that is not known is still compared by its level, so a new one
  given read or write is a widening. id-token has only write and none:
  `id-token: read` cannot be read.
- `read-all`: every known scope read, but id-token none, since it has no
  read level; `write-all`: every known scope write.
- `{}`: every scope none.

The effective permissions of a job are its own `permissions:` block if it
has one, else the workflow's top-level block if there is one, else the
repository default: the token permissions set in the repository's
settings. The file does not show that setting, so the repository default
is a state of its own, counted wider than any block. Permissions are
compared job by job, each job known by its file and its job id.

A widening, which fails (exit 1), is any of:

- a scope whose level rises;
- a job that had a block, its own or the workflow's, and has none now, so
  it falls to the repository default;
- a new job, or a job in a new workflow file, whose effective permissions
  are anything but every scope none - compared with `{}`, so a new job
  with no block anywhere, which takes the repository default, is one.

A narrowing is reported and never fails: a scope whose level falls, a job
that had the repository default and now has a block, a job removed and a
file deleted. A job renamed is a job removed and a new job, and the new
job is compared with `{}`.

Each finding names a line in the head file: the scope key whose level
changed, or the `permissions:` key when the scope is not listed there (or
several scopes changed on that one line), or the job key when the job has
no block. A removed job or a deleted file names its line in the base file.
A change written in the workflow's block, reaching several jobs the same
way, is one finding, labelled "workflow", naming the jobs.

Reading
-------
This reads YAML without a YAML library - Sabline's runtime has no
dependency - and reads only what locating these blocks needs: mappings and
sequences by indentation, the top-level `permissions:` and `jobs:` keys,
each job id under `jobs:` and its `permissions:` key, and the value of each
`permissions:` key in the forms above, written as a scalar (quoted or not),
a flow mapping or a block mapping. Comments, blank lines, CRLF and CR line
ends, plain, quoted and flow values spanning lines, and block scalars
(`run: |`) are read as YAML reads them, so a line inside a script or a
quoted string is never taken for a key.

What it cannot read with confidence it does not guess: the file is
unreadable, named with a line and a reason, and the command exits 2. That
covers a tab outside a comment, a quoted value or a block scalar (YAML
refuses those); an anchor, an alias or a tag; an explicit `?` key; a key
written twice in one mapping (PyYAML keeps the last, GitHub refuses the
file); more than one document; a character YAML does not accept, and the
line separators YAML 1.1 counts as line ends and YAML 1.2 does not; a
workflow whose top level, `jobs:` or a job is not a block mapping; and a
`permissions:` value in any other form. A file is never read as having no
permissions because it could not be read. A file unreadable at the base
makes the command exit 2 as well, since what it gave is not known.

What it does not see
--------------------
It compares files, not what GitHub runs. A reusable workflow a job calls
is governed by its own blocks, in its own file; the repository's default
token setting is not in any file; a pull_request_target workflow runs the
base branch's copy, whatever the pull request's copy says. GitHub may also
refuse a file this reads, which then gives no job anything.

The JSON `--json` prints, sabline.permissions-ratchet/1, is provisional:
its fields may change in a minor release, named in the CHANGELOG.

Exit status: 0 nothing widened; 1 something widened; 2 the comparison
could not be made - not a git repository, REF not a commit, or a workflow
that could not be read (the widenings found in the other files are still
reported).
"""
import json
import os
import re
import subprocess
import sys
from typing import Any, Mapping, Union

PERMISSIONS_RATCHET_SCHEMA = "sabline.permissions-ratchet/1"

PERMISSION_SCOPES = ("actions", "attestations", "checks", "contents",
                "deployments", "discussions", "id-token", "issues", "models",
                "packages", "pages", "pull-requests", "repository-projects",
                "security-events", "statuses", "artifact-metadata")
PERMISSION_LEVELS = ("none", "read", "write")
WORKFLOWS_DIR = ".github/workflows"
REPOSITORY_DEFAULT = "repository default"

_SHORTHANDS = ("read-all", "write-all")
# not in YAML's printable set, or a line end in YAML 1.1 and not in 1.2
_UNACCEPTED = re.compile(
    "[^\t\n\r\x20-\x7e\xa0-‧‪-퟿-�"
    "\U00010000-\U0010ffff]")
_BLOCK_HEADER = re.compile(r"[|>](?:[1-9][+-]?|[+-][1-9]?)?(?: +#.*)?")
_ESCAPES = (("0", "\0"), ("a", "\a"), ("b", "\b"), ("t", "\t"),
            ("\t", "\t"), ("n", "\n"), ("v", "\v"), ("f", "\f"),
            ("r", "\r"), ("e", "\x1b"), (" ", " "), ('"', '"'), ("/", "/"),
            ("\\", "\\"), ("N", "\x85"), ("_", "\xa0"), ("L", " "),
            ("P", " "), ("\n", ""))
_HEX_ESCAPES = (("x", 2), ("u", 4), ("U", 8))


class WorkflowUnreadable(Exception):
    """A workflow file that cannot be read with confidence: the line (1 is
    the first; None when no line is to blame) and the reason."""

    def __init__(self, line: Union[int, None], reason: str) -> None:
        super().__init__(reason)
        self.line = line
        self.reason = reason


# ---- the YAML this reads ------------------------------------------------------

class _Scalar:
    """A value that is not a block collection: kind is plain, single,
    double, flow, block or null; text is as written (a flow value keeps its
    line ends, so a key inside it has a line)."""

    def __init__(self, kind: str, text: str, line: int,
                 multiline: bool = False) -> None:
        self.kind = kind
        self.text = text
        self.line = line
        self.multiline = multiline


class _Map:
    """A block mapping: key -> (the key's line, its value)."""

    def __init__(self) -> None:
        self.items: dict[str, tuple[int, Any]] = {}


class _Seq:
    """A block sequence."""

    def __init__(self) -> None:
        self.items: list[Any] = []


class _Frame:
    """An open block collection: the column it is at, and the key or item
    whose value is still to come on a later line (None when there is none)."""

    def __init__(self, indent: int, node: Any, pending: Any = None) -> None:
        self.indent = indent
        self.node = node
        self.pending = pending


def _refuse(line: Union[int, None], reason: str) -> WorkflowUnreadable:
    return WorkflowUnreadable(line, reason)


def _quoted_end(text: str, start: int, quote: str,
                escaped: bool = False) -> tuple[int, bool]:
    """(the index just past the closing quote, or -1 when the line ends
    first; whether a backslash escapes what comes next)."""
    k = start
    while k < len(text):
        ch = text[k]
        if quote == "'":
            if ch == "'":
                if k + 1 < len(text) and text[k + 1] == "'":
                    k += 2
                    continue
                return k + 1, False
        elif escaped:
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == '"':
            return k + 1, False
        k += 1
    return -1, escaped


def _after_value(rest: str, line: int, what: str) -> None:
    """What may follow a finished quoted or flow value on its line: spaces,
    then a comment or nothing."""
    stripped = rest.lstrip(" ")
    if stripped.startswith("\t"):
        raise _refuse(line, "a tab after a value, which YAML does not accept")
    if stripped and not (stripped.startswith("#") and stripped != rest):
        raise _refuse(line, f"text after {what} on the same line")


def _document_marker(raw: str) -> str:
    """'---' or '...' when the line is a document marker, else ''."""
    for marker in ("---", "..."):
        if raw == marker or raw.startswith(marker + " ") \
                or raw.startswith(marker + "\t"):
            return marker
    return ""


class _Reader:
    """Reads one YAML document into _Map, _Seq and _Scalar nodes, refusing
    every shape the module docstring names."""

    def __init__(self, text: str) -> None:
        if text.startswith("﻿"):
            text = text[1:]
        bad = _UNACCEPTED.search(text)
        if bad is not None:
            line = text.count("\n", 0, bad.start()) \
                + text.count("\r", 0, bad.start()) \
                - text.count("\r\n", 0, bad.start()) + 1
            raise _refuse(line, f"the character U+{ord(bad.group()):04X}, "
                                f"which YAML does not accept as a character "
                                f"or does not agree on as a line end")
        self.lines = text.replace("\r\n", "\n").replace("\r", "\n") \
            .split("\n")
        self.stack: list[_Frame] = []
        self.root: Any = None
        self.started = False
        self.ended = False

    # -- placing what a line holds

    def _parent_column(self, col: int) -> int:
        """The column of the innermost open collection left of `col`."""
        for frame in reversed(self.stack):
            if frame.indent < col:
                return frame.indent
        return -1

    def _fill(self, frame: _Frame, node: Any) -> None:
        if isinstance(frame.node, _Map):
            line, _ = frame.node.items[frame.pending]
            frame.node.items[frame.pending] = (line, node)
        else:
            frame.node.items[frame.pending] = node
        frame.pending = None

    def _place(self, line: int, col: int, kind: str, key: str = "",
               value: Any = None) -> None:
        """Put a dash, a key (with its value when the line gave one) or a
        value on its own at column `col`."""
        if self.root is None:
            if kind != "key":
                raise _refuse(line, "the top level is not a mapping")
            self.root = _Map()
            self.stack = [_Frame(col, self.root)]
        while self.stack and self.stack[-1].indent > col:
            self.stack.pop()
        if not self.stack:
            raise _refuse(line, "a line less indented than the top level")
        top = self.stack[-1]
        if top.indent == col and kind == "key" and isinstance(top.node, _Seq):
            # a sequence written at its key's own column ends here
            self.stack.pop()
            if not self.stack or self.stack[-1].indent != col:
                raise _refuse(line, "a key at the column of a sequence")
            top = self.stack[-1]
        if top.indent == col:
            if kind == "key" and isinstance(top.node, _Map):
                self._add_key(top, line, key, value)
                return
            if kind == "dash" and isinstance(top.node, _Seq):
                top.node.items.append(None)
                top.pending = len(top.node.items) - 1
                return
            if kind == "dash" and top.pending is not None:
                # `steps:` with its `- ` entries at the same column
                seq = _Seq()
                self._fill(top, seq)
                seq.items.append(None)
                self.stack.append(_Frame(col, seq, 0))
                return
            raise _refuse(line, "a line at the column of a collection it "
                                "does not belong to")
        if top.pending is None:
            raise _refuse(line, "a line indented under a value that is "
                                "already complete")
        if kind == "value":
            self._fill(top, value)
        elif kind == "key":
            new_map = _Map()
            self._fill(top, new_map)
            frame = _Frame(col, new_map)
            self.stack.append(frame)
            self._add_key(frame, line, key, value)
        else:
            new_seq = _Seq()
            self._fill(top, new_seq)
            new_seq.items.append(None)
            self.stack.append(_Frame(col, new_seq, 0))

    def _add_key(self, frame: _Frame, line: int, key: str, value: Any) -> None:
        mapping = frame.node
        assert isinstance(mapping, _Map)
        if key in mapping.items:
            raise _refuse(line, f"the key {key!r} written twice in one "
                                f"mapping")
        mapping.items[key] = (line, value if value is not None
                              else _Scalar("null", "", line))
        frame.pending = key if value is None else None

    # -- one line's key, and the value that may run over later lines

    def _key(self, text: str, line: int) -> Union[tuple[str, int], None]:
        """(the key, the index just past its colon), or None when the text
        is not `key: value`."""
        if text[0] in "\"'":
            end, _ = _quoted_end(text, 1, text[0])
            if end < 0:
                return None
            rest = text[end:]
            gap = len(rest) - len(rest.lstrip(" "))
            after = rest[gap:]
            if after.startswith("\t"):
                raise _refuse(line, "a tab after a key, which YAML does not "
                                    "accept")
            if after == ":" or after.startswith(": "):
                return _unquote(text[:end], line), end + gap + 1
            if after.startswith(":"):
                raise _refuse(line, "a quoted key with no space after its "
                                    "colon")
            return None
        if text[0] in "[{&*!|>%@`,]}#":
            return None
        k = 0
        while True:
            colon = text.find(":", k)
            if colon < 0:
                return None
            comment = text.find(" #")
            if 0 <= comment < colon:
                return None
            if colon + 1 == len(text) or text[colon + 1] == " ":
                key = text[:colon].rstrip(" ")
                if "\t" in key:
                    raise _refuse(line, "a tab in a key, which YAML does not "
                                        "accept")
                return key, colon + 1
            if text[colon + 1] == "\t":
                raise _refuse(line, "a tab after a colon, which YAML does not "
                                    "accept")
            k = colon + 1

    def _value(self, i: int, text: str, parent: int) -> tuple[Any, int]:
        """The value that starts on line i+1 with `text`, and the index of
        the first line after it. `parent` is the column of the key, dash or
        collection that holds it: a later line belongs to the value only
        when it is deeper than that."""
        line = i + 1
        if text == "" or text.startswith("#"):
            return None, i + 1
        ch = text[0]
        if ch in "|>":
            return self._block_scalar(i, text, parent)
        if ch in "\"'":
            return self._quoted(i, text)
        if ch in "[{":
            return self._flow(i, text)
        if ch == "&":
            raise _refuse(line, "an anchor (&), which this does not follow")
        if ch == "*":
            raise _refuse(line, "an alias (*), which this does not follow")
        if ch == "!":
            raise _refuse(line, "a tag (!), which this does not read")
        if ch in "%@`,]}":
            raise _refuse(line, f"a value starting with {ch!r}, which YAML "
                                f"does not accept")
        if ch in "?-" and (len(text) == 1 or text[1] == " "):
            raise _refuse(line, f"{ch!r} where a value belongs")
        value = _plain_part(text)
        if "\t" in value:
            raise _refuse(line, "a tab in a plain value, which YAML does not "
                                "accept")
        if ": " in value or value.endswith(":"):
            raise _refuse(line, "': ' inside a plain value, which YAML does "
                                "not accept")
        j = i + 1
        after_comment = False
        continued = False
        while j < len(self.lines):
            raw = self.lines[j]
            body = raw.lstrip(" ")
            indent = len(raw) - len(body)
            if body.strip(" \t") == "":
                if "\t" in body:
                    raise _refuse(j + 1, "a tab on a blank line, which YAML "
                                         "does not accept")
                j += 1
                continue
            if indent <= parent:
                break
            if body.startswith("#"):
                after_comment = True
                j += 1
                continue
            if body.startswith("\t"):
                raise _refuse(j + 1, "a tab in the indentation, which YAML "
                                     "does not accept")
            more = _plain_part(body)
            if after_comment or "\t" in more or ": " in more \
                    or more.endswith(":"):
                raise _refuse(j + 1, "a line that continues a plain value "
                                     "in a way YAML does not accept")
            continued = True
            j += 1
        return _Scalar("plain", value, line, multiline=continued), j

    def _block_scalar(self, i: int, text: str, parent: int) -> tuple[Any, int]:
        line = i + 1
        if _BLOCK_HEADER.fullmatch(text) is None:
            raise _refuse(line, "a block scalar header this does not read")
        digits = [c for c in text[1:3] if c.isdigit()]
        content = parent + int(digits[0]) if digits else None
        j = i + 1
        while j < len(self.lines):
            raw = self.lines[j]
            indent = len(raw) - len(raw.lstrip(" "))
            if raw.strip(" ") == "":
                j += 1
                continue
            if content is None:
                if indent <= parent:
                    break
                content = indent
            if indent >= content:
                j += 1
                continue
            if indent > parent or raw.strip(" \t") == "":
                raise _refuse(j + 1, "a line of a block scalar less indented "
                                     "than the block")
            break
        return _Scalar("block", text, line), j

    def _quoted(self, i: int, text: str) -> tuple[Any, int]:
        line = i + 1
        quote = text[0]
        end, escaped = _quoted_end(text, 1, quote)
        if end >= 0:
            _after_value(text[end:], line, "a quoted value")
            if quote == '"':
                _unquote(text[:end], line)         # its escapes are valid
            return _Scalar("single" if quote == "'" else "double",
                           text[:end], line), i + 1
        parts = [text]
        j = i + 1
        while j < len(self.lines):
            raw = self.lines[j]
            if _document_marker(raw):
                raise _refuse(j + 1, "a document marker inside a quoted "
                                     "value")
            end, escaped = _quoted_end(raw, 0, quote, escaped)
            if end >= 0:
                parts.append(raw[:end])
                _after_value(raw[end:], j + 1, "a quoted value")
                if quote == '"':
                    _unquote("\n".join(parts), line)
                return _Scalar("single" if quote == "'" else "double",
                               "\n".join(parts), line, multiline=True), j + 1
            parts.append(raw)
            j += 1
        raise _refuse(line, "a quoted value that is never closed")

    def _flow(self, i: int, text: str) -> tuple[Any, int]:
        """A flow collection, over as many lines as it takes. Its text is
        kept with its line ends; an anchor, alias, tag, explicit key or
        reserved character at the start of an entry is refused."""
        line = i + 1
        depth = 0
        quote = ""
        escaped = False
        parts: list[str] = []
        j = i
        current = text
        while True:
            at_start = True
            k = 0
            while k < len(current):
                ch = current[k]
                if quote:
                    end, escaped = _quoted_end(current, k, quote, escaped)
                    if end < 0:
                        k = len(current)
                        break
                    quote = ""
                    k = end
                    at_start = False
                    continue
                if ch == "#" and (k == 0 or current[k - 1] == " "):
                    break
                if ch == "\t":
                    raise _refuse(j + 1, "a tab in a flow collection, which "
                                         "YAML does not accept")
                if ch == " ":
                    k += 1
                    continue
                if at_start and (ch in "&*!%@`" or (
                        ch == "?" and current[k + 1:k + 2] in ("", " "))):
                    raise _refuse(j + 1, f"{ch!r} at the start of an entry "
                                         f"in a flow collection, which this "
                                         f"does not read")
                if ch in "\"'":
                    quote = ch
                    k += 1
                    continue
                if ch in "[{":
                    depth += 1
                    at_start = True
                elif ch in "]}":
                    depth -= 1
                    if depth == 0:
                        parts.append(current[:k + 1])
                        _after_value(current[k + 1:], j + 1,
                                     "a flow collection")
                        return (_Scalar("flow", "\n".join(parts), line,
                                        multiline=j > i), j + 1)
                    at_start = False
                elif ch == ",":
                    at_start = True
                elif ch == ":" and current[k + 1:k + 2] in ("", " "):
                    at_start = True
                else:
                    at_start = False
                k += 1
            parts.append(current)
            j += 1
            if j >= len(self.lines):
                raise _refuse(line, "a flow collection that is never closed")
            current = self.lines[j]
            if _document_marker(current):
                raise _refuse(j + 1, "a document marker inside a flow "
                                     "collection")

    # -- the document

    def read(self) -> Any:
        """The top-level mapping, or None for a file with no content."""
        i = 0
        while i < len(self.lines):
            raw = self.lines[i]
            line = i + 1
            body = raw.lstrip(" ")
            col = len(raw) - len(body)
            if body.strip(" \t") == "":
                if "\t" in body:
                    raise _refuse(line, "a tab on a blank line, which YAML "
                                        "does not accept")
                i += 1
                continue
            if body.startswith("#"):
                i += 1
                continue
            if body.startswith("\t"):
                raise _refuse(line, "a tab in the indentation, which YAML "
                                    "does not accept")
            if self.ended:
                raise _refuse(line, "content after a document end marker "
                                    "(...): more than one document")
            marker = _document_marker(raw)
            if marker:
                rest = raw[3:].lstrip(" ")
                if rest and not rest.startswith("#"):
                    raise _refuse(line, f"content on the {marker} line")
                if marker == "..." or self.started:
                    if marker == "---":
                        raise _refuse(line, "a second document (---): more "
                                            "than one document")
                    self.ended = True
                self.started = True
                i += 1
                continue
            if col == 0 and body.startswith("%"):
                raise _refuse(line, "a directive (%), which this does not "
                                    "read")
            self.started = True
            i = self._line(i, body, col)
        return self.root

    def _line(self, i: int, text: str, col: int) -> int:
        line = i + 1
        dashes = []
        while text == "-" or text.startswith("- "):
            dashes.append(col)
            rest = text[1:].lstrip(" ")
            col += len(text) - len(rest)
            text = rest
            if text.startswith("\t"):
                raise _refuse(line, "a tab after a sequence dash, which YAML "
                                    "does not accept")
            if text.startswith("#"):
                text = ""
        if text.startswith("-\t"):
            raise _refuse(line, "a tab after a sequence dash, which YAML does "
                                "not accept")
        for dash in dashes:
            self._place(line, dash, "dash")
        if text == "":
            return i + 1
        if text[0] == "?" and (len(text) == 1 or text[1] in " \t"):
            raise _refuse(line, "an explicit key (?), which this does not "
                                "read")
        found = self._key(text, line)
        if found is not None:
            key, past = found
            value_text = text[past:].lstrip(" ")
            if value_text.startswith("\t"):
                raise _refuse(line, "a tab after a colon, which YAML does not "
                                    "accept")
            if not key:
                raise _refuse(line, "a key with no name")
            value, after = self._value(i, value_text, col)
            self._place(line, col, "key", key, value)
            return after
        parent = dashes[-1] if dashes else self._parent_column(col)
        value, after = self._value(i, text, parent)
        self._place(line, col, "value", value=value)
        return after


def _plain_part(text: str) -> str:
    """A plain value up to its comment, trailing spaces taken off."""
    cut = text.find(" #")
    return (text if cut < 0 else text[:cut]).rstrip(" ")


def _unquote(text: str, line: int) -> str:
    """A quoted scalar that closes on its own line, as YAML reads it."""
    if text[0] == "'":
        return text[1:-1].replace("''", "'")
    out = []
    k = 1
    body = text[:-1]
    while k < len(body):
        ch = body[k]
        if ch != "\\":
            out.append(ch)
            k += 1
            continue
        nxt = body[k + 1:k + 2]
        simple = next((v for e, v in _ESCAPES if e == nxt), None)
        if simple is not None:
            out.append(simple)
            k += 2
            continue
        width = next((w for e, w in _HEX_ESCAPES if e == nxt), 0)
        digits = body[k + 2:k + 2 + width]
        if not width or len(digits) != width or any(
                c not in "0123456789abcdefABCDEF" for c in digits):
            raise _refuse(line, "an escape in a double-quoted value that "
                                "YAML does not accept")
        out.append(chr(int(digits, 16)))
        k += 2 + width
    return "".join(out)


# ---- permissions blocks -------------------------------------------------------

def _scalar_text(node: Any, what: str, line: int) -> str:
    """A one-line plain or quoted scalar's text, or refused."""
    if not isinstance(node, _Scalar) or node.multiline \
            or node.kind not in ("plain", "single", "double"):
        raise _refuse(line, f"{what} is not a one-line value")
    if node.kind == "plain":
        return node.text
    return _unquote(node.text, node.line)


def _flow_mapping(node: _Scalar) -> list[tuple[str, str, int]]:
    """[(scope, level, line)] of a flow mapping holding plain or quoted
    keys and values and nothing else."""
    text = node.text.strip(" ")
    if not text.startswith("{"):
        raise _refuse(node.line, "permissions: is a flow sequence, not a "
                                 "mapping")
    entries: list[tuple[str, str, int]] = []
    k = 1
    n = len(text)

    def line_at(pos: int) -> int:
        return node.line + text.count("\n", 0, pos)

    def skip(pos: int) -> int:
        while pos < n:
            if text[pos] in " \n":
                pos += 1
            elif text[pos] == "#":
                end = text.find("\n", pos)
                pos = n if end < 0 else end
            else:
                break
        return pos

    def scalar(pos: int, stops: str) -> tuple[str, int]:
        if pos < n and text[pos] in "\"'":
            end, _ = _quoted_end(text, pos + 1, text[pos])
            if end < 0 or "\n" in text[pos:end]:
                raise _refuse(line_at(pos), "a quoted value over more than "
                                            "one line in permissions:")
            return _unquote(text[pos:end], line_at(pos)), end
        start = pos
        while pos < n and text[pos] not in stops and text[pos] != "\n":
            if text[pos] == "#" and pos > start and text[pos - 1] == " ":
                break                               # a comment
            if text[pos] == ":" and text[pos + 1:pos + 2] in (" ", "\n", "",
                                                             ",", "}"):
                break
            if text[pos] in "{[]":
                raise _refuse(line_at(pos), "a nested collection in "
                                            "permissions:")
            pos += 1
        return text[start:pos].rstrip(" "), pos

    while True:
        k = skip(k)
        if k >= n:
            raise _refuse(node.line, "permissions: is not closed")
        if text[k] == "}":
            if skip(k + 1) != n:
                raise _refuse(line_at(k), "text after permissions: closes")
            return entries
        key_line = line_at(k)
        key, k = scalar(k, ",}")
        k = skip(k)
        if not key or k >= n or text[k] != ":":
            raise _refuse(key_line, f"{key!r} in permissions: has no level")
        k = skip(k + 1)
        level, k = scalar(k, ",}")
        if any(key == e[0] for e in entries):
            raise _refuse(key_line, f"the scope {key!r} written twice")
        entries.append((key, level, key_line))
        k = skip(k)
        if k < n and text[k] == ",":
            k += 1
        elif k >= n or text[k] != "}":
            raise _refuse(key_line, "an entry of permissions: that does not "
                                    "end with ',' or '}'")


def _all_levels(level: str) -> dict[str, str]:
    return {s: ("none" if s == "id-token" and level == "read" else level)
            for s in PERMISSION_SCOPES}


def _block(mapping: _Map, owner: str) -> Union[dict[str, Any], None]:
    """The `permissions:` block of a workflow or job mapping: {"form":
    read-all, write-all or map, "line": the key's line, "levels": every
    known scope and every scope it names -> level, "scope_lines": each
    scope it names -> its line}; None when there is no such key."""
    if "permissions" not in mapping.items:
        return None
    line, node = mapping.items["permissions"]
    entries: list[tuple[str, str, int]] = []
    if isinstance(node, _Scalar) and node.kind == "null":
        raise _refuse(line, f"permissions: of {owner} has no value")
    if isinstance(node, _Scalar) and node.kind == "flow":
        entries = _flow_mapping(node)
    elif isinstance(node, _Scalar):
        value = _scalar_text(node, f"permissions: of {owner}", line)
        if value in _SHORTHANDS:
            return {"form": value, "line": line,
                    "levels": _all_levels(value.split("-")[0]),
                    "scope_lines": {}}
        raise _refuse(line, f"permissions: of {owner} is {value!r}, not "
                            f"read-all, write-all or a mapping of scopes")
    elif isinstance(node, _Map):
        for scope, (scope_line, value_node) in node.items.items():
            entries.append((scope, _scalar_text(
                value_node, f"the scope {scope!r}", scope_line), scope_line))
    else:
        raise _refuse(line, f"permissions: of {owner} is a sequence, not a "
                            f"mapping of scopes")
    levels = _all_levels("none")
    scope_lines = {}
    for scope, level, scope_line in entries:
        if not scope:
            raise _refuse(scope_line, "a scope with an empty name")
        if level not in PERMISSION_LEVELS:
            raise _refuse(scope_line, f"{scope}: {level!r} is not read, "
                                      f"write or none")
        if scope == "id-token" and level == "read":
            raise _refuse(scope_line, "id-token: read is not a level "
                                      "id-token has; it is write or none")
        levels[scope] = level
        scope_lines[scope] = scope_line
    return {"form": "map", "line": line, "levels": levels,
            "scope_lines": scope_lines}


def read_workflow(text: str) -> dict[str, Any]:
    """The permissions a workflow file's text writes: {"workflow": the
    top-level block or None, "jobs": {job id: {"line": the job key's line,
    "block": its own block or None}}}, jobs in file order. A block is as
    _block describes it. WorkflowUnreadable when the text cannot be read
    with confidence."""
    root = _Reader(text).read()
    if root is None:
        return {"workflow": None, "jobs": {}}
    jobs: dict[str, Any] = {}
    workflow = _block(root, "the workflow")
    if "jobs" in root.items:
        line, node = root.items["jobs"]
        if isinstance(node, _Map):
            for job_id, (job_line, job) in node.items.items():
                if not isinstance(job, _Map):
                    raise _refuse(job_line, f"the job {job_id!r} is not "
                                            f"written as a block mapping")
                jobs[job_id] = {"line": job_line,
                                "block": _block(job, f"job {job_id}")}
        elif not (isinstance(node, _Scalar) and node.kind == "null"):
            raise _refuse(line, "jobs: is not written as a block mapping")
    return {"workflow": workflow, "jobs": jobs}


# ---- comparing ------------------------------------------------------------------

def _render(block: Union[dict[str, Any], None]) -> str:
    """A block as a finding shows it: read-all, write-all, the repository
    default, or the scopes it gives more than none, in name order."""
    if block is None:
        return REPOSITORY_DEFAULT
    if block["form"] in _SHORTHANDS:
        return str(block["form"])
    given = sorted((s, v) for s, v in block["levels"].items() if v != "none")
    return "{" + ", ".join(f"{s}: {v}" for s, v in given) + "}"


def _effective(doc: dict[str, Any], job_id: str) -> tuple[Any, str]:
    """(the block a job runs with, or None for the repository default;
    where it is written: job, workflow or default)."""
    own = doc["jobs"][job_id]["block"]
    if own is not None:
        return own, "job"
    if doc["workflow"] is not None:
        return doc["workflow"], "workflow"
    return None, "default"


def _nothing() -> dict[str, Any]:
    """What a new job is compared with: every scope none."""
    return {"form": "map", "line": 0, "levels": _all_levels("none"),
            "scope_lines": {}}


def _changes(path: str, base: Any, head: Any) -> list[dict[str, Any]]:
    """One record per job and change, before grouping."""
    out: list[dict[str, Any]] = []
    head_jobs = list(head["jobs"]) if head is not None else []
    base_jobs = list(base["jobs"]) if base is not None else []
    for job_id in head_jobs + [j for j in base_jobs if j not in head_jobs]:
        in_base = base is not None and job_id in base["jobs"]
        in_head = head is not None and job_id in head["jobs"]
        if not in_head:
            before, _ = _effective(base, job_id)
            out.append({"direction": "narrowed", "kind": "deleted-file"
                        if head is None else "removed-job", "side": "base",
                        "line": base["jobs"][job_id]["line"], "where": "job",
                        "job": job_id, "scopes": [], "before": _render(before),
                        "after": "removed"})
            continue
        after, where = _effective(head, job_id)
        head_job_line = head["jobs"][job_id]["line"]
        if in_base:
            before, _ = _effective(base, job_id)
            kind = "level"
        else:
            before = _nothing()
            kind = "new-file" if base is None else "new-job"
        common = {"side": "head", "job": job_id,
                  "before": _render(before), "after": _render(after)}
        if before is None and after is None:
            continue
        if after is None:
            out.append(dict(common, direction="widened", line=head_job_line,
                            where="job", scopes=[],
                            kind=kind if kind != "level" else "default"))
            continue
        if before is None:
            out.append(dict(common, direction="narrowed", line=after["line"],
                            where=where, scopes=[], kind="explicit"))
            continue
        names = list(PERMISSION_SCOPES) + sorted(
            (set(before["levels"]) | set(after["levels"])) - set(PERMISSION_SCOPES))
        for scope in names:
            was = PERMISSION_LEVELS.index(before["levels"].get(scope, "none"))
            now = PERMISSION_LEVELS.index(after["levels"].get(scope, "none"))
            if was == now:
                continue
            out.append(dict(
                common, direction="widened" if now > was else "narrowed",
                line=after["scope_lines"].get(scope, after["line"]),
                where=where, kind=kind,
                scopes=[(scope, PERMISSION_LEVELS[was], PERMISSION_LEVELS[now])]))
    for change in out:
        change["file"] = path
    return out


def _reason(f: dict[str, Any], jobs: list[str]) -> str:
    """Why a grouped change is a widening or a narrowing, in a sentence."""
    named = ", ".join(jobs)
    many = len(jobs) > 1
    who = ("jobs " if many else "job ") + named
    kind = f["kind"]
    scopes = f["scopes"]
    if kind == "deleted-file":
        return f"the workflow file was deleted, and with it {who}"
    if kind == "removed-job":
        return (f"{who} {'were' if many else 'was'} removed (a job renamed is "
                f"a job removed and a new job)")
    if kind == "default":
        return (f"{who} now {'have' if many else 'has'} no permissions "
                f"block, its own or the workflow's, so the token takes the "
                f"repository's default permissions: a setting this file does "
                f"not show, counted wider than any block")
    if kind == "explicit":
        return (f"{who} had no permissions block, and so the repository's "
                f"default permissions; now "
                + ("the workflow's block applies" if f["where"] == "workflow"
                   else "it has a block of its own"))
    if kind in ("new-job", "new-file"):
        what = ("new jobs" if many else "a new job") + (
            " in a new workflow file" if kind == "new-file" else "")
        if not scopes:
            return (f"{named} {'are' if many else 'is'} {what} with no "
                    f"permissions block anywhere, so the token takes the "
                    f"repository's default permissions; a new job is compared "
                    f"with no permissions")
        source = ("the workflow's permissions block"
                  if f["where"] == "workflow" else "its own permissions block")
        return (f"{named} {'are' if many else 'is'} {what}, compared with no "
                f"permissions, and {source} gives "
                + ", ".join(f"{s} {now}" for s, _, now in scopes))
    block = (f"the workflow's permissions block, which {who} "
             f"{'take' if many else 'takes'}" if f["where"] == "workflow"
             else f"the permissions block of {who}")
    moved = "rose" if f["direction"] == "widened" else "fell"
    if len(scopes) == 1:
        scope, was, now = scopes[0]
        return f"{scope} {moved} from {was} to {now} in {block}"
    return (f"{len(scopes)} scopes {moved} in {block}: "
            + ", ".join(f"{s} {was} -> {now}" for s, was, now in scopes))


def _grouped(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Changes that share a file, a line, the block they are written in
    and what that block was and is, as one finding naming every job."""
    groups: dict[tuple[Any, ...], dict[str, Any]] = {}
    for c in changes:
        key = (c["direction"], c["file"], c["side"], c["line"], c["where"],
               None if c["where"] == "workflow" else c["job"], c["kind"],
               c["before"], c["after"])
        group = groups.setdefault(key, dict(c, jobs=[], all_scopes=[]))
        if c["job"] not in group["jobs"]:
            group["jobs"].append(c["job"])
        for s in c["scopes"]:
            if s not in group["all_scopes"]:
                group["all_scopes"].append(s)
    out = []
    for g in groups.values():
        scopes = g["all_scopes"]
        one = len(scopes) == 1
        finding = {
            "direction": g["direction"],
            "file": g["file"], "line": g["line"], "side": g["side"],
            "where": g["where"],
            "job": None if g["where"] == "workflow" else g["job"],
            "jobs": g["jobs"],
            "scope": scopes[0][0] if one else "permissions",
            "scopes": [s for s, _, _ in scopes],
            "before": scopes[0][1] if one else g["before"],
            "after": scopes[0][2] if one else g["after"],
            "kind": g["kind"],
            "reason": _reason(dict(g, scopes=scopes), g["jobs"])}
        out.append(finding)
    out.sort(key=lambda f: (f["file"], f["side"] == "base", f["line"],
                            f["scope"], f["jobs"]))
    return out


def _as_text(value: Union[str, bytes]) -> str:
    """A workflow file's bytes as text, or refused."""
    if isinstance(value, str):
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as e:
        raise _refuse(None, f"not UTF-8 text ({e.reason} at byte {e.start})")


def permissions_compare(
        base: Mapping[str, Union[str, bytes, WorkflowUnreadable]],
        head: Mapping[str, Union[str, bytes, WorkflowUnreadable]],
        against: str = "") -> dict[str, Any]:
    """Compare two sets of workflow files, each {path: its text, its bytes,
    or a WorkflowUnreadable saying why it was not read}, as the module
    docstring says. A path in one set only is a new or a deleted file. The
    result is the sabline.permissions-ratchet/1 document (provisional):
    {"schema", "against", "widened", "narrowed", "unreadable"}. Nothing here
    reads a file or runs git."""
    changes: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    for path in sorted(set(base) | set(head)):
        docs: dict[str, Any] = {}
        for side, files in (("base", base), ("head", head)):
            if path not in files:
                docs[side] = None
                continue
            value = files[path]
            try:
                if isinstance(value, WorkflowUnreadable):
                    raise value
                docs[side] = read_workflow(_as_text(value))
            except WorkflowUnreadable as e:
                unreadable.append({"file": path, "side": side,
                                   "line": e.line, "reason": e.reason})
        if any(u["file"] == path for u in unreadable):
            continue
        changes += _changes(path, docs["base"], docs["head"])
    widened: list[dict[str, Any]] = []
    narrowed: list[dict[str, Any]] = []
    for finding in _grouped(changes):
        direction = finding.pop("direction")
        finding.pop("kind")
        (widened if direction == "widened" else narrowed).append(finding)
    return {"schema": PERMISSIONS_RATCHET_SCHEMA, "against": against,
            "widened": widened, "narrowed": narrowed,
            "unreadable": unreadable}


def permissions_exit(result: dict[str, Any]) -> int:
    """2 when a file could not be read, 1 when something widened, else 0."""
    if result["unreadable"]:
        return 2
    return 1 if result["widened"] else 0


# ---- git and the working tree ------------------------------------------------------

def _git(args: list[str], cwd: str) -> bytes:
    try:
        done = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              timeout=300)
    except FileNotFoundError:
        raise RuntimeError("git is not installed, or not on PATH")
    except OSError as e:
        raise RuntimeError(f"git could not be run in {cwd}: {e}")
    if done.returncode != 0:
        said = done.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(said or f"git {' '.join(args)} failed")
    return done.stdout


def _workflow_name(path: str) -> bool:
    """A file GitHub reads as a workflow: directly in .github/workflows."""
    prefix = WORKFLOWS_DIR + "/"
    rest = path[len(prefix):] if path.startswith(prefix) else ""
    return bool(rest) and "/" not in rest and rest.endswith((".yml", ".yaml"))


def permissions_ratchet(against: str, root: str = ".") -> dict[str, Any]:
    """The workflows in the working tree that holds `root`, compared with
    the ones the commit `against` names. RuntimeError when git cannot answer:
    not a git repository, or no such commit."""
    try:
        top = _git(["rev-parse", "--show-toplevel"], root) \
            .decode("utf-8", "replace").strip()
    except RuntimeError as e:
        raise RuntimeError(f"{root} is not in a git repository ({e})")
    try:
        commit = _git(["rev-parse", "--verify", "--quiet",
                       f"{against}^{{commit}}"], top) \
            .decode("utf-8", "replace").strip()
    except RuntimeError:
        raise RuntimeError(f"no commit called '{against}' in this repository "
                           f"(a shallow clone may need: git fetch --depth=1 "
                           f"origin {against})")
    base: dict[str, Union[str, bytes, WorkflowUnreadable]] = {}
    listed = _git(["ls-tree", "-r", "-z", commit, "--", WORKFLOWS_DIR], top)
    for entry in listed.split(b"\0"):
        if not entry or b"\t" not in entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        path = raw_path.decode("utf-8", "replace")
        mode, kind = meta.split(b" ")[:2]
        if not _workflow_name(path) or kind != b"blob":
            continue
        if mode == b"120000":
            base[path] = _refuse(None, "a symbolic link, which this does not "
                                       "follow")
            continue
        base[path] = _git(["show", f"{commit}:{path}"], top)
    head: dict[str, Union[str, bytes, WorkflowUnreadable]] = {}
    folder = os.path.join(top, *WORKFLOWS_DIR.split("/"))
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    for name in names:
        path = f"{WORKFLOWS_DIR}/{name}"
        full = os.path.join(folder, name)
        if not _workflow_name(path) or not (os.path.isfile(full)
                                            or os.path.islink(full)):
            continue
        if os.path.islink(full):
            head[path] = _refuse(None, "a symbolic link, which this does not "
                                       "follow")
            continue
        try:
            with open(full, "rb") as fh:
                head[path] = fh.read()
        except OSError as e:
            head[path] = _refuse(None, f"could not be read: {e.strerror}")
    return permissions_compare(base, head, against)


def _ascii(text: str) -> str:
    return text.encode("ascii", "backslashreplace").decode("ascii")


def permissions_lines(result: dict[str, Any]) -> list[str]:
    """What `sabline permissions-ratchet` prints: each widening, each
    narrowing, each file not read, and a count."""
    out = []
    for word, key in (("WIDENED", "widened"), ("narrowed", "narrowed")):
        for f in result[key]:
            label = f["job"] if f["where"] == "job" else "workflow"
            out.append(f"{word} {f['file']}:{f['line']} {label} "
                       f"{f['scope']}: {f['before']} -> {f['after']}")
            where = " (the line is in the base)" if f["side"] == "base" else ""
            out.append(f"    {f['reason']}{where}")
    for u in result["unreadable"]:
        at = f":{u['line']}" if u["line"] is not None else ""
        out.append(f"UNREADABLE {u['file']}{at} at the {u['side']}: "
                   f"{u['reason']}")
    against = result["against"]
    if result["unreadable"]:
        out.append(f"could not compare {len(result['unreadable'])} file(s) "
                   f"with {against}: what they give is not known")
    if result["widened"]:
        out.append(f"{len(result['widened'])} widening(s) against {against}")
    elif not result["unreadable"]:
        out.append(f"no widening: every job's permissions are what {against} "
                   f"gave it, or narrower")
    return [_ascii(line) for line in out]


def permissions_main(argv: list[Any]) -> int:
    """sabline permissions-ratchet --against REF [--json] [--root DIR]"""
    usage = ("usage: sabline permissions-ratchet --against REF [--json] "
             "[--root DIR]")
    opts: dict[str, Any] = {}
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in ("--against", "--root"):
            if i + 1 >= len(argv) or word in opts:
                print(usage, file=sys.stderr)
                return 2
            opts[word] = argv[i + 1]
            i += 2
            continue
        if word != "--json" or word in opts:
            print(usage, file=sys.stderr)
            return 2
        opts[word] = True
        i += 1
    if "--against" not in opts:
        print(usage, file=sys.stderr)
        return 2
    root = opts.get("--root", ".")
    if not os.path.isdir(root):
        print(_ascii(f"sabline permissions-ratchet: {root} is not a "
                     f"directory"), file=sys.stderr)
        return 2
    try:
        result = permissions_ratchet(opts["--against"], root)
    except RuntimeError as e:
        print(_ascii(f"sabline permissions-ratchet: {e}"), file=sys.stderr)
        return 2
    if "--json" in opts:
        print(json.dumps(result, indent=2))
    else:
        print("\n".join(permissions_lines(result)))
    return permissions_exit(result)
