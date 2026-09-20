#!/usr/bin/env python3
"""Every URL the documents name still answers, and llms.txt serves the card.

The monthly workflow runs this (MAINTENANCE.md). It reads every link in the
Markdown files, action.yml, pyproject.toml, CITATION.cff and the MCP
manifests, asks each one once - HEAD, then GET where HEAD is refused - and
names each that does not answer 2xx or 3xx after three tries. Addresses that
are examples or placeholders by construction (example.com and its kind,
127.0.0.1, localhost, anything holding `<` or `{`) are not asked. A link
into this repository at a commit or on main is asked like any other.

Last, https://sabline.dev/llms.txt must serve LLM.md: every compiler
error names it as the reference (8.0; at sabline.dev from 8.3). The
documentation site's earlier address must answer that card's old URL with a
redirect to the new one, since errors printed by 8.0 to 8.2.1 name it.

    python check_urls.py            ask every URL
    python check_urls.py --list     only list what would be asked
"""
from __future__ import annotations

import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CARD_URL = "https://sabline.dev/llms.txt"
# Where the card was before sabline.dev, newest first. Each is an address
# the errors of some released version print - 8.0 to 8.2.1 print the GitHub
# Pages one, 8.3 to 8.5 print velaris-lang.dev - so each must still answer,
# with a redirect to CARD_URL. check_docs holds this, check_library's
# redirect test, the CHANGELOG's history and the readers of earlier
# predicate types to be the only places that name an earlier address.
EARLIER_CARD_URLS = ("https://velaris-lang.dev/llms.txt",
                     "https://gowrishankar-infra.github.io/velaris-lang/llms.txt")
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
# Written in the documents as identifiers, not as pages: a sigstore
# certificate identity (a workflow file at a ref), the OIDC issuers a
# signature names, the Software Heritage API endpoints PROVENANCE.md quotes
# (they answer POST, not GET), and an owner/repository placeholder. The
# monthly run 34978389207 asked each and called it broken (8.3).
IDENTIFIERS = re.compile(
    r"/\.github/workflows/[\w.-]+\.ya?ml@refs/|"
    r"^https://token\.actions\.githubusercontent\.com/?$|"
    r"^https://github\.com/login/oauth/?$|"
    r"^https://archive\.softwareheritage\.org/api/|"
    r"^https://github\.com/o/[\w.-]+/?$")


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
                if NOT_ASKED.search(url) or IDENTIFIERS.search(url):
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
                "User-Agent": "sabline-check-urls"})
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
                CARD_URL, headers={"User-Agent": "sabline-check-urls"}),
                timeout=30) as response:
            served = response.read().decode("utf-8", errors="replace")
        same = served.strip() == card.strip()
        print(f"  {'ok' if same else 'DIFFERS'}      {CARD_URL} "
              + ("serves LLM.md" if same else
                 "does not serve this LLM.md (rebuild and deploy the docs)"))
    except (urllib.error.URLError, OSError) as e:
        same = False
        print(f"  BROKEN  {CARD_URL}  ({getattr(e, 'reason', e)})")
    redirects = True
    for earlier in EARLIER_CARD_URLS:
        moved, said = redirect_of(earlier)
        print(f"  {'ok' if moved else 'BROKEN'}      {earlier} "
              f"{'redirects to ' + said if moved else '(' + said + ')'}")
        redirects = redirects and moved is True
    return 1 if bad or not same or not redirects else 0


class _Stay(urllib.request.HTTPRedirectHandler):
    """A redirect handler that follows nothing, so the 3xx itself is seen."""

    def redirect_request(self, req: urllib.request.Request, fp: Any,
                         code: int, msg: str, headers: Any,
                         newurl: str) -> urllib.request.Request | None:
        return None


def redirect_of(url: str) -> tuple[bool | None, str]:
    """(True, the Location) when `url` answers with a redirect to CARD_URL's
    host and path (either scheme: GitHub Pages redirects to http until the
    site enforces HTTPS); (False, what it answered instead); (None, why)
    when it could not be asked at all."""
    opener = urllib.request.build_opener(_Stay)
    request = urllib.request.Request(url, headers={
        "User-Agent": "sabline-check-urls"})
    try:
        with opener.open(request, timeout=30) as response:
            return False, f"HTTP {response.status}, not a redirect"
    except urllib.error.HTTPError as e:
        location = e.headers.get("Location") or ""
        parts = urllib.parse.urlsplit(location)
        wanted = urllib.parse.urlsplit(CARD_URL)
        if e.code in (301, 302, 307, 308) and parts.hostname == \
                wanted.hostname and parts.path == wanted.path:
            return True, location
        return False, f"HTTP {e.code} to {location or 'nowhere'}"
    except (urllib.error.URLError, OSError) as e:
        return None, str(getattr(e, "reason", e))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
