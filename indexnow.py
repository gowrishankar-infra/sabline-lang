#!/usr/bin/env python3
"""Tell the search engines that take IndexNow which pages changed (8.7).

    python indexnow.py             ping for what the last commit changed
    python indexnow.py --dry-run   say what would be sent, and send nothing

indexnow.yml runs this after GitHub Pages has published a push to main. It
reads which files under docs/ the last commit changed, keeps the pages at
the top of the site - not their copies under latest/ or a major.minor/,
whose canonical link names the page at the top anyway, and not the assets,
the search index or the sitemap - and sends their addresses to
api.indexnow.org, which shares them with every engine that takes IndexNow
(Bing, Yandex, Naver, Seznam and others; Google does not). The key it sends
is build_docs.INDEXNOW_KEY, and the file at the site's root holding it is
what proves the site is ours.

Low value next to a correct sitemap, which every engine reads, and harmless:
it sends public addresses to a public endpoint, and nothing else. A commit
that changed no page sends nothing.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_docs import INDEXNOW_KEY, SITE  # noqa: E402

ENDPOINT = "https://api.indexnow.org/indexnow"
MOST = 10_000                       # addresses IndexNow takes in one request
COPY = re.compile(r"^(latest|\d+\.\d+)/")


def changed_urls(names: list[str]) -> list[str]:
    """The site's addresses for the pages among the changed files `names`:
    an HTML page or the paper's PDF at the top of docs/."""
    urls = []
    for name in names:
        name = name.replace("\\", "/")
        if not name.startswith("docs/"):
            continue
        path = name[len("docs/"):]
        if COPY.match(path) or path.startswith("assets/"):
            continue
        if not (path.endswith(".html") or path.endswith(".pdf")):
            continue
        if path.endswith("index.html"):
            path = path[:-len("index.html")]
        urls.append(f"{SITE}/{path}")
    return sorted(set(urls))


def last_commit_files() -> list[str]:
    done = subprocess.run(["git", "diff", "--name-only", "HEAD^", "HEAD"],
                          cwd=HERE, capture_output=True, text=True,
                          encoding="utf-8")
    if done.returncode != 0:
        raise SystemExit("git could not say what the last commit changed "
                         "(indexnow.yml checks out two commits): "
                         + done.stderr.strip())
    return [ln for ln in done.stdout.splitlines() if ln]


def main(argv: list[str]) -> int:
    urls = changed_urls(last_commit_files())[:MOST]
    if not urls:
        print("the last commit changed no page of the site: nothing to send")
        return 0
    host = SITE.split("://", 1)[1]
    body = {"host": host, "key": INDEXNOW_KEY,
            "keyLocation": f"{SITE}/{INDEXNOW_KEY}.txt", "urlList": urls}
    print(f"{len(urls)} page(s) changed:")
    for url in urls:
        print(f"  {url}")
    if "--dry-run" in argv:
        print("--dry-run: nothing sent")
        return 0
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"})
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            status = answer.status
    except urllib.error.HTTPError as e:
        status = e.code
    except urllib.error.URLError as e:
        print(f"::error::IndexNow did not answer: {e.reason}")
        return 1
    if status in (200, 202):
        print(f"IndexNow took them ({status})")
        return 0
    print(f"::error::IndexNow refused them ({status}): 400 is a malformed "
          "request, 403 a key the site's key file does not hold, 422 an "
          "address outside the host, 429 too many requests")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
