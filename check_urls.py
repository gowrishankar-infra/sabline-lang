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
# Where the card was before sabline.dev: an address the errors of some
# released version print in their `reference:` line, which must still lead
# a reader to the card. check_docs holds this, check_library's copy of it,
# the CHANGELOG's history and the readers of earlier predicate types to be
# the only places that name an earlier address.
#
# NOT here, and it cannot be: https://gowrishankar-infra.github.io/velaris-lang/llms.txt,
# which the errors of 8.0 to 8.2.1 print. A GitHub Pages site is served at
# <owner>.github.io/<repo>, so renaming the repository to sabline-lang in
# 8.6 moved it, and the old path answers 404. The only way to serve it
# again is a repository called velaris-lang, and creating one would end
# GitHub's redirect from every old repository URL - `git clone`, a link, and
# `uses: gowrishankar-infra/velaris-lang@<commit>` in somebody's workflow.
# Those are worth more than one address, so the address is gone, and
# docs/renamed.md says so. The predicate type named there is unaffected: a
# predicate type is a name, and nothing is fetched from it to verify a
# Statement (sabline/predicates.py, THREAT_MODEL.md).
EARLIER_CARD_URLS = ("https://velaris-lang.dev/llms.txt",)
SOURCES = ["*.md", "docs/*.md", "benchmark/*.md", "paper/*.md", "stdlib/*.md",
           "editor/vscode/*.md", "npm/*.md", "integrations/**/*.md",
           # the incident catalogue's sources: every entry names the report
           # it was written from, and a summary whose source has gone is
           # worth knowing about before somebody fact-checks it
           "incidents/**/*.md",
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
    r"^https://github\.com/o/[\w.-]+/?$|"
    # 8.6: the address the Pages site had before the repository was
    # renamed. It answers 404 and will go on answering 404 - a repository
    # called velaris-lang would serve it again and would end GitHub's
    # redirect from every old repository URL, which is worth more. The
    # CHANGELOG and docs/renamed.md name it BECAUSE it is broken, so asking
    # it is asking whether a thing this project has published as gone is
    # gone. The predicate types under it are names, not pages
    # (sabline/predicates.py), and nothing fetches them.
    r"^https://gowrishankar-infra\.github\.io/velaris-lang(?:[/#?]|$)|"
    # the domain that is not this project's, named as the worked example of
    # a predicate type Sabline refuses
    r"^https://velaris\.dev/")


# files a SOURCES pattern matches that are not documentation, with why
NOT_SOURCES = {
    "incidents/FACTCHECK.md": "working material: the record of one fact-check "
                              "of the catalogue's sources, which the entries "
                              "themselves already cite",
}


def urls() -> dict[str, list[str]]:
    """{url: [the files that name it]}."""
    found: dict[str, list[str]] = {}
    for pattern in SOURCES:
        for path in sorted(HERE.glob(pattern)):
            if not path.is_file() or str(path.relative_to(HERE)).replace(
                    "\\", "/") in NOT_SOURCES:
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
    # Every line below is a statement about the DEPLOYED site. Until the
    # site serves this commit's card, this checkout is ahead of it - which
    # is every commit between a change to LLM.md or to the site's address
    # and the deploy that publishes it - and there is nothing here to
    # decide. Once it does serve it, each earlier address must reach it.
    leads = True
    for earlier in EARLIER_CARD_URLS:
        if not same:
            print(f"  skipped   {earlier}: the site does not serve this "
                  f"commit's card yet, so where its earlier addresses lead "
                  f"is not this commit's to say")
            continue
        reaches, said = leads_to_card(earlier, card)
        print(f"  {'ok' if reaches else 'BROKEN'}      {earlier} {said}")
        leads = leads and reaches is True
    return 1 if bad or not same or not leads else 0


class _Stay(urllib.request.HTTPRedirectHandler):
    """A redirect handler that follows nothing, so the 3xx itself is seen."""

    def redirect_request(self, req: urllib.request.Request, fp: Any,
                         code: int, msg: str, headers: Any,
                         newurl: str) -> urllib.request.Request | None:
        return None


def leads_to_card(url: str, card: str) -> tuple[bool | None, str]:
    """Whether an earlier address of the card leads a reader to `card`.

    What every error and refusal printed by 8.0 to 8.5 promises is that the
    address in its `reference:` line reaches the card. This holds the
    promise rather than one way of keeping it: the address is followed,
    through however many redirects, and what comes back must be these
    bytes. An address that serves the card itself keeps the promise; so
    does one that redirects to the address that does, directly or through
    another; a 404, a redirect into nowhere, or a different card does not.

    (None, why) when the address could not be asked at all.
    """
    try:
        with urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": "sabline-check-urls"}),
                timeout=30) as response:
            served = response.read().decode("utf-8", errors="replace")
            landed = response.geturl()
    except (urllib.error.URLError, OSError) as e:
        return None, f"could not be read ({getattr(e, 'reason', e)})"
    if served.strip() != card.strip():
        return False, (f"leads to {landed}, which does not serve this card"
                       if landed != url else "does not serve this card")
    if landed == url:
        return True, "serves the card itself"
    return True, f"leads to {landed}, which serves it"


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
