#!/usr/bin/env python3
"""`velaris receipt show` and `velaris audit --html`: a page a person can read.

    python check_viewers.py

The page is held to what it says of itself: the same bytes for the same
input, on every system (tests/viewers/*.html are the goldens, made with
--update); nothing in it that fetches or runs anything; every value escaped,
because a receipt is a file somebody hands you; and each thing the release
says a reader finds there, found. The stylesheet inside it is the
documentation site's, byte for byte.
"""
import html.parser
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from suite_dirs import isolate  # noqa: E402

HERE = Path(__file__).parent
GOLDEN = HERE / "tests" / "viewers"
WORK = isolate("check_viewers")
VELARIS = [sys.executable, str(HERE / "velaris.py")]
FAILED: list[str] = []
PASSED = [0]


def expect(what: str, ok: bool, detail: Any = "") -> None:
    if ok:
        PASSED[0] += 1
    else:
        FAILED.append(what)
        print(f"  FAILED: {what}" + (f"\n    {detail}" if detail != "" else ""))


def velaris(*args: str) -> tuple[int, bytes, bytes]:
    done = subprocess.run(VELARIS + list(args), capture_output=True,
                          stdin=subprocess.DEVNULL, timeout=300)
    return done.returncode, done.stdout, done.stderr


class Reader(html.parser.HTMLParser):
    """The tags a page holds, and the text a reader sees."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.attrs: list[tuple[str, str, str | None]] = []
        self.text: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        self.tags.append(tag)
        self.attrs += [(tag, k, v) for k, v in attrs]
        if tag == "style":
            self.skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self.skip -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.text.append(data)


def read(page: bytes) -> Reader:
    reader = Reader()
    reader.feed(page.decode("utf-8"))
    return reader


def inert(reader: Reader) -> bool:
    """No script, no frame, no form, no image, no event handler, and no URL
    but the two links to the documentation."""
    if set(reader.tags) & {"script", "iframe", "object", "embed", "form",
                           "img", "link", "base", "video", "audio", "svg"}:
        return False
    for tag, key, value in reader.attrs:
        if key.startswith("on") or key in ("src", "srcset", "action"):
            return False
        if key == "href" and not (value or "").startswith(
                "https://velaris-lang.dev/"):
            return False
    return True


HOSTILE = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "<script>alert(1)</script>.vel",
                 "digest": {"sha256": "0" * 64}}],
    "predicateType": "https://velaris-lang.dev/receipt/v1",
    "predicate": {
        "schema": "velaris.receipt/1",
        "producer": {"name": "velaris-lang", "uri": "x", "version": "8.5.0"},
        "specification": "velaris-spec 0.13.0",
        "startedAt": "2026-01-01T00:00:00.000Z", "wall_time_ms": 1.0,
        "budget": 'io,fs:read:"><img src=x onerror=alert(1)>',
        "run_parameters": {"seed": None, "freeze_time": None, "timeout": None,
                           "max_memory_mb": None, "max_read_bytes": 1,
                           "confinement": "none",
                           "confinement_reason": "</p><script>x</script>",
                           "confinement_layers": ["<b>"],
                           "os_policy_sha256": None},
        "effects_used": {"io": 1},
        "grants_used": [{"grant": "net:<svg onload=alert(1)>", "times": 1}],
        "refusals": [{"code": "E314", "effect": "net", "line": 3,
                      "stopped": True, "times": 1}],
        "declassifications": [{"reason": "\x1b[2J<a href=javascript:x>why</a>",
                               "line": 2, "times": 2}],
        "exit": {"status": 1, "outcome": "refused", "code": "E314"},
        "complete": True}}


def golden(name: str, page: bytes, update: bool) -> None:
    path = GOLDEN / name
    if update:
        GOLDEN.mkdir(parents=True, exist_ok=True)
        path.write_bytes(page)
        print(f"  wrote {path}")
        return
    want = path.read_bytes().replace(b"\r\n", b"\n") if path.exists() else b""
    expect(f"{name}: these bytes, on this system as on every other",
           page == want, f"{len(page)} bytes here, {len(want)} in the golden; "
                         f"python check_viewers.py --update after a change "
                         f"that is meant")


def main() -> int:
    update = "--update" in sys.argv
    expect("the stylesheet in the package is the documentation site's",
           (HERE / "velaris" / "site.css").read_bytes().replace(b"\r\n", b"\n")
           == (HERE / "site" / "site.css").read_bytes().replace(b"\r\n", b"\n"))
    print("a receipt")
    receipt = GOLDEN / "receipt.json"
    code, page, err = velaris("receipt", "show", str(receipt))
    code2, again, _ = velaris("receipt", "show", str(receipt))
    expect("the same receipt gives the same bytes", code == 0 == code2
           and page == again and page.startswith(b"<!DOCTYPE html>"), err)
    expect("no carriage return: the page is the same on Windows",
           b"\r" not in page)
    golden("receipt.html", page, update)
    out = WORK / "page.html"
    code, _, err = velaris("receipt", "show", str(receipt), "-o", str(out))
    expect("-o writes the same bytes to a file",
           code == 0 and out.read_bytes() == page, err)
    reader = read(page)
    seen = " ".join(" ".join(reader.text).split())
    expect("it needs nothing to be read: no script, nothing fetched",
           inert(reader))
    for what in ("Read", "Written", "Fetched", "Secrets declassified",
                 "Refused", "Confinement", "Subjects",
                 "net:management.azure.com:443", "3 times",
                 "the bearer token is sent to management.azure.com",
                 "hmac signature", "E314", "stopped here", "Wall time",
                 "examples/ops/azure_groups.vel", "Tool calls",
                 "tool:send_email:to=*@corp.com"):
        expect(f"a reader finds: {what}", what in seen)
    code, text, err = velaris("receipt", "show", str(receipt), "--text")
    golden("receipt.txt", text, update)
    expect("--text says the same in the terminal", code == 0
           and b"management.azure.com:443  3 times" in text
           and b"<" not in text.replace(b"<stdlib>", b""), err)
    code, shown, _ = velaris("receipts", "show", str(receipt))
    expect("`receipts show` is the same page", code == 0 and shown == page)
    print("a receipt somebody else wrote")
    hostile = WORK / "hostile.json"
    hostile.write_text(json.dumps(HOSTILE), encoding="utf-8")
    code, page, err = velaris("receipt", "show", str(hostile))
    reader = read(page)
    expect("markup in a receipt's values is text on the page, not markup",
           code == 0 and inert(reader)
           and "<script>alert(1)</script>.vel" in "".join(reader.text)
           and b"<script" not in page and b"<img" not in page
           and b"<svg" not in page, err)
    code, text, _ = velaris("receipt", "show", str(hostile), "--text")
    expect("an escape sequence in one is written out, not sent to the "
           "terminal", code == 0 and b"\x1b" not in text
           and b"\\x1b[2J" in text)
    old = json.loads(json.dumps(HOSTILE))
    del old["predicate"]["grants_used"]
    old["predicate"]["effects_used"] = {"net": 4}
    (WORK / "old.json").write_text(json.dumps(old), encoding="utf-8")
    code, text, _ = velaris("receipt", "show", str(WORK / "old.json"),
                            "--text")
    expect("a receipt from before 8.5 says what it can, and that it cannot "
           "say under which grant", code == 0 and b"4 operation(s)" in text
           and b"before 8.5" in text)
    for name, content in (("missing.json", None), ("not.json", "{"),
                          ("audit.json", '{"schema": "velaris.audit/1"}')):
        if content is not None:
            (WORK / name).write_text(content, encoding="utf-8")
        code, page, err = velaris("receipt", "show", str(WORK / name))
        expect(f"{name} is exit 2 and one line, not a page or a traceback",
               code == 2 and not page and b"Traceback" not in err
               and err.count(b"\n") == 1, err)
    print("an audit")
    program = "examples/ops/aws_buckets.vel"
    done = subprocess.run(VELARIS + ["audit", program, "--html"], cwd=HERE,
                          capture_output=True, timeout=300)
    again2 = subprocess.run(VELARIS + ["audit", program, "--html"], cwd=HERE,
                            capture_output=True, timeout=300)
    expect("the same program gives the same bytes", done.returncode == 0
           and done.stdout == again2.stdout and b"\r" not in done.stdout,
           done.stderr)
    # no golden for this one: an audit names the version that made it
    reader = read(done.stdout)
    seen = " ".join(" ".join(reader.text).split())
    expect("the audit's page is as inert", inert(reader))
    for what in ("Audit of examples/ops/aws_buckets.vel", "Run it with",
                 "hmac signature", "aws.signature", "Python modules None.",
                 "a host built while running", "declassify"):
        expect(f"a reader finds: {what}", what in seen, seen[:400])
    print("-" * 62)
    if FAILED:
        print(f"{len(FAILED)} FAILED, {PASSED[0]} passed")
        return 1
    print(f"all {PASSED[0]} checks passed: a page says what the document "
          f"says, in the same bytes, and runs nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main())
