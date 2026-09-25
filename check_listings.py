#!/usr/bin/env python3
"""One description, the same on every listing (8.7).

    python check_listings.py            the files in this repository
    python check_listings.py --github   and the repository's settings on
                                        GitHub, through gh (a person runs
                                        this; CI does not)

Until 8.7 each listing said something different - GitHub's description led
with Z3 and LLVM, PyPI's with trust, npm's with running code you did not
write - and a reader who met two of them could not tell they were one
project (plan/findability-research/findability-baseline.md). The words are
build_docs.HEADLINE and build_docs.SUBLINE, and this holds every listing to
them:

- PyPI (pyproject.toml), npm (npm/package.json), the VS Code extension
  (editor/vscode/package.json), the MCP bundle (mcpb/manifest.json) and
  crates.io (rt/crates/sabline-rt/Cargo.toml) carry the headline and the
  subline, exactly;
- the MCP registry (integrations/mcp_registry/server.json) carries the
  headline alone, since its schema allows 100 characters and no more;
- README.md's first screen and npm/README.md open with both;
- the words people search with (SEARCH_WORDS) are among PyPI's and npm's
  keywords and, with --github, the repository's topics; crates.io's five
  keywords and the ten the VS Code Marketplace once enforced are within
  those limits.

With --github it also reads the repository's description, homepage and
topics, which live in GitHub's settings rather than in any file here.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_docs import HEADLINE, SITE, SUBLINE  # noqa: E402

DESCRIPTION = f"{HEADLINE} {SUBLINE}"
REPOSITORY = "gowrishankar-infra/sabline-lang"
# the words the phrasings in plan/findability-research/phrasings.md use
SEARCH_WORDS = ("ai-agents", "mcp", "secrets", "sandbox", "permissions",
                "supply-chain-security", "least-privilege")
MCP_REGISTRY_LIMIT = 100        # server.json's description, its schema's max
CRATE_KEYWORDS, CRATE_KEYWORD_CHARS = 5, 20
VSCODE_KEYWORDS = 10
GITHUB_TOPICS = 20

failures: list[str] = []


def ok(label: str, good: bool, detail: str = "") -> None:
    print(f"  {'ok' if good else 'WRONG':6} {label}"
          + (f"\n         {detail}" if detail and not good else ""))
    if not good:
        failures.append(label)


def text(path: str) -> str:
    return (HERE / path).read_text(encoding="utf-8")


def normal(s: str) -> str:
    return " ".join(s.split())


def toml_value(path: str, key: str) -> Any:
    """A top-level string or list of strings from a TOML file, read without
    tomllib (Python 3.10 has none): enough for these manifests."""
    m = re.search(rf"^{re.escape(key)}\s*=\s*(\"(?:[^\"\\]|\\.)*\"|\[[^\]]*\])",
                  text(path), re.M)
    if not m:
        return None
    return json.loads(m.group(1))


def check_files() -> None:
    print("listings in this repository")
    ok("PyPI's description is the headline and the subline",
       toml_value("pyproject.toml", "description") == DESCRIPTION,
       str(toml_value("pyproject.toml", "description")))
    words = toml_value("pyproject.toml", "keywords") or []
    missing = [w for w in SEARCH_WORDS if w not in words]
    ok("PyPI's keywords hold the words people search with", not missing,
       f"missing {missing}")
    for path in ("npm/package.json", "editor/vscode/package.json",
                 "mcpb/manifest.json"):
        data = json.loads(text(path))
        ok(f"{path}'s description is the headline and the subline",
           data.get("description") == DESCRIPTION, str(data.get("description")))
    npm = json.loads(text("npm/package.json"))
    missing = [w for w in SEARCH_WORDS if w not in npm.get("keywords", [])]
    ok("npm's keywords hold the words people search with", not missing,
       f"missing {missing}")
    vscode = json.loads(text("editor/vscode/package.json"))
    ok(f"the VS Code extension has at most {VSCODE_KEYWORDS} keywords",
       len(vscode.get("keywords", [])) <= VSCODE_KEYWORDS,
       str(vscode.get("keywords")))
    server = json.loads(text("integrations/mcp_registry/server.json"))
    ok("the MCP registry's description is the headline, within "
       f"{MCP_REGISTRY_LIMIT} characters",
       server.get("description") == HEADLINE
       and len(HEADLINE) <= MCP_REGISTRY_LIMIT, str(server.get("description")))
    crate = "rt/crates/sabline-rt/Cargo.toml"
    ok("crates.io's description is the headline and the subline",
       toml_value(crate, "description") == DESCRIPTION,
       str(toml_value(crate, "description")))
    keywords = toml_value(crate, "keywords") or []
    ok(f"crates.io's keywords: at most {CRATE_KEYWORDS}, each at most "
       f"{CRATE_KEYWORD_CHARS} characters",
       len(keywords) <= CRATE_KEYWORDS
       and all(len(k) <= CRATE_KEYWORD_CHARS for k in keywords), str(keywords))
    for path in ("README.md", "npm/README.md"):
        head = normal("\n".join(text(path).splitlines()[:30]))
        ok(f"{path} opens with the headline and the subline",
           HEADLINE in head and SUBLINE in head)


def check_github() -> None:
    print("the repository's settings on GitHub")
    try:
        done = subprocess.run(["gh", "api", f"repos/{REPOSITORY}"],
                              capture_output=True, text=True, encoding="utf-8",
                              timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        ok("gh answers", False, repr(e))
        return
    if done.returncode != 0:
        ok("gh answers", False, done.stderr.strip())
        return
    repo = json.loads(done.stdout)
    ok("its description is the headline and the subline",
       repo.get("description") == DESCRIPTION, str(repo.get("description")))
    ok(f"its homepage is {SITE}",
       (repo.get("homepage") or "").rstrip("/") == SITE,
       str(repo.get("homepage")))
    topics = repo.get("topics") or []
    missing = [w for w in SEARCH_WORDS if w not in topics]
    ok("its topics hold the words people search with", not missing,
       f"missing {missing}")
    ok(f"it has at most {GITHUB_TOPICS} topics", len(topics) <= GITHUB_TOPICS,
       str(len(topics)))


def main(argv: list[str]) -> int:
    check_files()
    if "--github" in argv:
        check_github()
    print(f"{len(failures)} wrong")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
