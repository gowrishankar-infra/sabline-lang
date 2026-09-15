#!/usr/bin/env python3
"""Open one GitHub issue per failure, and nothing else.

The nightly, monthly and adversarial workflows end here (MAINTENANCE.md).
A robot reports and a person fixes: this script can list and open issues,
comment on an open one, create a label, and read a run's jobs and logs. It
cannot commit, push, tag, close or edit an issue, or touch a pull request.
Every gh call goes through gh(), which refuses any other command and any
API call that is not a read.

    python open_issues.py jobs --workflow nightly --run-id ID --label nightly
        one issue per failed job of that run
    python open_issues.py files DIR --label mutation
        one issue per Markdown file in DIR: the first line, less a leading
        "# ", is the title, and the rest is the body
    --dry-run   say what would be opened, and open nothing

An issue already open with the same title is not opened twice; the new
failure is added to it as a comment. At most --max issues (40) are opened
or commented on in one call; past that, one more issue says how many were
left out, because that many at once is one problem, not forty.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

RUNNER: Callable[..., Any] = subprocess.run
READS = {("issue", "list"), ("label", "list"), ("run", "view")}
WRITES = {("issue", "create"), ("issue", "comment"), ("label", "create")}
NOT_A_READ = {"-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"}
BODY_LIMIT = 60000
SIGNATURE = ("\n\n---\nOpened by `open_issues.py`. A robot reports this and "
             "fixes nothing (MAINTENANCE.md).\n")


class Refused(Exception):
    """A gh call this script does not make."""


def gh(args: list[str]) -> str:
    if not args:
        raise Refused("gh with no command")
    if args[0] == "api":
        if any(a in NOT_A_READ or a.startswith(("--method=", "-X"))
               for a in args[1:]):
            raise Refused("gh api is used here to read, never to write")
    elif tuple(args[:2]) not in READS | WRITES:
        raise Refused(f"gh {' '.join(args[:2])} is not something this "
                      f"script does")
    done = RUNNER(["gh", *args], capture_output=True, text=True,
                  encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])}: {done.stderr.strip()}")
    return str(done.stdout)


class Opener:
    def __init__(self, label: str, dry_run: bool, most: int) -> None:
        self.label, self.dry_run, self.most = label, dry_run, most
        self.done = 0
        self.left_out: list[str] = []
        self._open: dict[str, int] | None = None

    def open_titles(self) -> dict[str, int]:
        if self._open is None:
            found = json.loads(gh(["issue", "list", "--state", "open",
                                   "--label", self.label, "--limit", "500",
                                   "--json", "number,title"]) or "[]")
            self._open = {i["title"]: i["number"] for i in found}
        return self._open

    def ensure_label(self) -> None:
        names = {x["name"] for x in json.loads(
            gh(["label", "list", "--limit", "500", "--json", "name"]) or "[]")}
        if self.label not in names:
            print(f"creating the label {self.label}")
            if not self.dry_run:
                gh(["label", "create", self.label, "--color", "d93f0b",
                    "--description", "reported by a scheduled workflow"])

    def report(self, title: str, body: str, again: str) -> None:
        if self.done >= self.most:
            self.left_out.append(title)
            return
        self.done += 1
        body = body[:BODY_LIMIT] + SIGNATURE
        number = self.open_titles().get(title)
        if number is not None:
            print(f"commenting on #{number}: {title}")
            if not self.dry_run:
                gh(["issue", "comment", str(number), "--body",
                    (again + "\n\n" + body)[:BODY_LIMIT]])
            return
        print(f"opening: {title}")
        if not self.dry_run:
            gh(["issue", "create", "--title", title, "--label", self.label,
                "--body", body])
        self.open_titles()[title] = -1

    def finish(self, what: str) -> None:
        if not self.left_out:
            return
        title = f"{what}: {len(self.left_out)} more failures than one run reports"
        body = (f"{len(self.left_out)} further failure(s) were not opened as "
                f"issues of their own, because {self.most} already were:\n\n"
                + "\n".join(f"- {t}" for t in self.left_out))
        self.most += 1
        self.report(title, body, "Again:")


def fence(text: str) -> str:
    return "```text\n" + text.replace("```", "'''") + "\n```"


def jobs(args: argparse.Namespace, opener: Opener) -> None:
    repo = os.environ.get("GH_REPO") or os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        sys.exit("open_issues: set GH_REPO to owner/name")
    lines = gh(["api", f"repos/{repo}/actions/runs/{args.run_id}/jobs"
                        "?per_page=100", "--paginate", "--jq", ".jobs[] | @json"])
    failed = [j for j in (json.loads(x) for x in lines.splitlines() if x.strip())
              if j.get("conclusion") == "failure"]
    print(f"{len(failed)} failed job(s) in run {args.run_id}")
    if failed:
        opener.ensure_label()
    for job in failed:
        steps = [s["name"] for s in job.get("steps") or []
                 if s.get("conclusion") == "failure"]
        try:
            log = gh(["run", "view", "--job", str(job["id"]), "--log-failed"])
            tail = "\n".join(line[:300] for line in log.splitlines()[-80:])
        except RuntimeError as e:
            tail = f"(the log could not be read: {e})"
        title = f"{args.workflow}: {job['name']} failed"
        body = (f"The {args.workflow} workflow's job **{job['name']}** failed.\n\n"
                f"- run: {job.get('run_url', '').replace('api.github.com/repos', 'github.com')}\n"
                f"- job: {job.get('html_url', '')}\n"
                f"- commit: {job.get('head_sha', '')}\n"
                f"- failed step(s): {', '.join(steps) or 'none named'}\n\n"
                f"The end of the failed steps' log:\n\n{fence(tail)}")
        opener.report(title, body, f"Failed again in {job.get('html_url', '')}.")
    opener.finish(args.workflow)


def files(args: argparse.Namespace, opener: Opener) -> None:
    found = sorted(Path(args.directory).glob("*.md"))
    print(f"{len(found)} report(s) in {args.directory}")
    if found:
        opener.ensure_label()
    for path in found:
        text = path.read_text(encoding="utf-8")
        first, _, rest = text.partition("\n")
        title = first.lstrip("#").strip()[:240] or path.stem
        opener.report(title, rest.strip(), "Reported again.")
    opener.finish(opener.label)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    j = sub.add_parser("jobs", help="one issue per failed job of a run")
    j.add_argument("--workflow", required=True)
    j.add_argument("--run-id", required=True)
    f = sub.add_parser("files", help="one issue per Markdown file")
    f.add_argument("directory")
    for p in (j, f):
        p.add_argument("--label", required=True)
        p.add_argument("--dry-run", action="store_true")
        p.add_argument("--max", type=int, default=40)
    args = ap.parse_args(argv)
    opener = Opener(args.label, args.dry_run, args.max)
    (jobs if args.command == "jobs" else files)(args, opener)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
