#!/usr/bin/env python3
"""Every URL the documents name still answers, and llms.txt serves the card.

The monthly workflow runs this (MAINTENANCE.md). It reads every link in the
Markdown files, action.yml, pyproject.toml, CITATION.cff and the MCP
manifests, asks each one once - HEAD, then GET where HEAD is refused - and
names each that does not answer 2xx or 3xx after three tries. Addresses that
are examples or placeholders by construction (example.com and its kind,
127.0.0.1, localhost, anything holding `<` or `{`) are not asked. A link
into this repository at a commit or on main is asked like any other.

Last, https://gowrishankar-infra.github.io/velaris-lang/llms.txt must serve
LLM.md: every compiler error names it as the reference (8.0).

    python check_urls.py            ask every URL
    python check_urls.py --list     only list what would be asked
"""
from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CARD_URL = "https://gowrishankar-infra.github.io/velaris-lang/llms.txt"
SOURCES = ["*.md", "docs/*.md", "benchmark/*.md", "paper/*.md", "stdlib/*.md",
           "editor/vscode/*.md", "npm/*.md", "integrations/**/*.md",
           "action.yml", "pyproject.toml", "CITATION.cff",
           "integrations/mcp_registry/server.json", "mcpb/manifest.json",
           "npm/package.json", "editor/vscode/package.json"]
URL = re.compile(r"https?://[^\s<>\"'`)\]}]+")
NOT_ASKED = re.compile(
    r"://(?:[\w.-]+\.)?(?:example\.(?:com|org|net|invalid)|localhost|"
    r"127\.0\.0\.1|0\.0\.0\.0|\[::1\]|host|api\.vendor\.example|"
    r"collector\.example\.org|evil\.com|good\.com)(?:[:/]|$)|[<{$]")


def urls() -> dict[str, list[str]]:
    """{url: [the files that name it]}."""
    found: dict[str, list[str]] = {}
    for pattern in SOURCES:
        for path in sorted(HERE.glob(pattern)):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for m in URL.finditer(text):
                url = m.group(0).rstrip(".,;:!?*_")
                if NOT_ASKED.search(url):
                    continue
                found.setdefault(url, []).append(
                    str(path.relative_to(HERE)).replace("\\", "/"))
    return found


def ask(url: str) -> tuple[str, str | None]:
    """(url, None when it answers, else what went wrong)."""
    last = ""
    for attempt in range(3):
        for method in ("HEAD", "GET"):
            request = urllib.request.Request(url, method=method, headers={
                "User-Agent": "velaris-check-urls"})
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    if response.status < 400:
                        return url, None
                    last = f"HTTP {response.status}"
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code in (405, 403, 400) and method == "HEAD":
                    continue            # some servers refuse HEAD only
                if e.code == 404:
                    return url, last
            except (urllib.error.URLError, OSError) as e:
                last = str(getattr(e, "reason", e))
            break
        time.sleep(2 * (attempt + 1))
    return url, last


def main(argv: list[str]) -> int:
    found = urls()
    if "--list" in argv:
        for url, where in sorted(found.items()):
            print(f"{url}  ({', '.join(sorted(set(where)))})")
        print(f"{len(found)} URL(s)")
        return 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        answers = dict(pool.map(ask, sorted(found)))
    bad = {u: why for u, why in answers.items() if why}
    for url, why in sorted(bad.items()):
        print(f"  BROKEN  {url}  ({why}) - named in "
              f"{', '.join(sorted(set(found[url])))}")
    print(f"{len(found) - len(bad)} of {len(found)} URL(s) answer")
    card = (HERE / "LLM.md").read_text(encoding="utf-8")
    try:
        with urllib.request.urlopen(urllib.request.Request(
                CARD_URL, headers={"User-Agent": "velaris-check-urls"}),
                timeout=30) as response:
            served = response.read().decode("utf-8", errors="replace")
        same = served.strip() == card.strip()
        print(f"  {'ok' if same else 'DIFFERS'}      {CARD_URL} "
              + ("serves LLM.md" if same else
                 "does not serve this LLM.md (rebuild and deploy the docs)"))
    except (urllib.error.URLError, OSError) as e:
        same = False
        print(f"  BROKEN  {CARD_URL}  ({getattr(e, 'reason', e)})")
    return 1 if bad or not same else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
