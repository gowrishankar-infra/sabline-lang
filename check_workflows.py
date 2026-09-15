#!/usr/bin/env python3
"""The scheduled workflows report, and change nothing (8.2).

nightly.yml, monthly.yml and adversarial-models.yml open issues and do
nothing else (MAINTENANCE.md: a robot reports, a person fixes). This reads
them and holds them to it:

- the workflow's own token reads the repository and nothing more;
- no job is given any write permission but `issues: write`, and only the
  job named `report` is given that;
- every checkout keeps no credential (persist-credentials: false);
- no step commits, pushes, tags, or uses gh for anything but issues;
- no secret is named anywhere but a model's key in that model's own job,
  and a GitHub token only in the report job;
- each model job says it is skipped, and does nothing, when its key is
  not set.

Then it holds open_issues.py and adversarial_models.py to what those
workflows rely on, with gh replaced by a fake: one issue per failure, a
comment rather than a second issue, nothing at all on --dry-run, no gh
command outside issues and labels, the job's failure annotations when its
log cannot be read yet, a close only with a comment, only of an issue it
opened, and only when every job of the run passed (which nightly.yml alone
asks for), one issue per finding, keys struck out.

    python check_workflows.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import adversarial_models  # noqa: E402
import open_issues  # noqa: E402

SCHEDULED = ["nightly.yml", "monthly.yml", "adversarial-models.yml"]
MODEL_KEYS = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY",
              "grok": "XAI_API_KEY"}
# a command at the start of a line, after ; & | or inside $( ): the words
# "Bash(git push *)" in a tool rule that forbids it are not a command
FORBIDDEN_RUN = re.compile(
    r"(?:^|[;&|]\s*|\$\(\s*|\n\s*)(?:git\s+(?:commit|push|tag)\b"
    r"|gh\s+(?!issue\b|label\b)\w+"
    r"|gh\s+issue\s+(?:close|edit|delete|lock|transfer)\b)")
PASS = FAIL = 0


def ok(label: str, good: object, detail: str = "") -> None:
    global PASS, FAIL
    if good:
        PASS += 1
        print(f"  ok      {label}")
    else:
        FAIL += 1
        print(f"  BROKEN  {label}" + (f"\n          {detail}" if detail else ""))


def workflow(name: str) -> dict[Any, Any]:        # YAML reads `on:` as True
    doc = yaml.safe_load((HERE / ".github" / "workflows" / name)
                         .read_text(encoding="utf-8"))
    assert isinstance(doc, dict)
    return doc


def steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return list(job.get("steps") or [])


def structure() -> None:
    print("the scheduled workflows")
    print("-" * 62)
    for name in SCHEDULED:
        doc = workflow(name)
        jobs: dict[str, dict[str, Any]] = doc["jobs"]
        triggers = doc.get("on", doc.get(True)) or {}
        ok(f"{name}: runs on a schedule and by hand, and on nothing else",
           set(triggers) == {"schedule", "workflow_dispatch"}, str(triggers))
        ok(f"{name}: its token reads the repository and nothing more",
           doc.get("permissions") == {"contents": "read"},
           str(doc.get("permissions")))
        writes = {j: {k: v for k, v in (job.get("permissions") or {}).items()
                      if v == "write"} for j, job in jobs.items()}
        wrong = {j: w for j, w in writes.items()
                 if w and not (j == "report" and w == {"issues": "write"})}
        ok(f"{name}: no job may write anything but issues, and only the "
           f"report job may write those", not wrong, str(wrong))
        ok(f"{name}: the report job may open issues",
           writes.get("report") == {"issues": "write"}, str(writes.get("report")))
        loose = [f"{j}: {s.get('name') or s.get('uses')}"
                 for j, job in jobs.items() for s in steps(job)
                 if str(s.get("uses", "")).startswith("actions/checkout@")
                 and (s.get("with") or {}).get("persist-credentials") is not False]
        ok(f"{name}: every checkout keeps no credential", not loose, str(loose))
        bad_runs = [f"{j}: {m.group(0).strip()}"
                    for j, job in jobs.items() for s in steps(job)
                    for m in FORBIDDEN_RUN.finditer(str(s.get("run", "")))]
        ok(f"{name}: no step commits, pushes, tags, or uses gh past issues",
           not bad_runs, str(bad_runs))
        text = (HERE / ".github" / "workflows" / name).read_text(encoding="utf-8")
        ok(f"{name}: no action runs from this repository's own commit but the "
           f"Action under test", all(u in ("./",) or "@" in u for u in re.findall(
               r"uses:\s*(\S+)", text)))
        for j, job in jobs.items():
            dumped = json.dumps(job)
            secrets = set(re.findall(r"secrets\.(\w+)", dumped))
            allowed = {MODEL_KEYS[j]} if j in MODEL_KEYS else set()
            ok(f"{name} / {j}: names no secret but "
               f"{', '.join(sorted(allowed)) or 'none'}",
               secrets <= allowed, str(secrets))
            if "github.token" in dumped or "GITHUB_TOKEN" in dumped:
                ok(f"{name} / {j}: a GitHub token only in the report job",
                   j == "report")
    doc = workflow("adversarial-models.yml")
    for model, key in MODEL_KEYS.items():
        job = doc["jobs"][model]
        has_key = str((job.get("env") or {}).get("HAS_KEY", ""))
        said = [s for s in steps(job) if s.get("if") == "env.HAS_KEY != 'true'"]
        rest = [s for s in steps(job) if s not in said]
        ok(f"adversarial-models.yml / {model}: without {key} it says it is "
           f"skipped, and every other step is skipped",
           f"secrets.{key}" in has_key and len(said) == 1
           and "::notice::" in str(said[0].get("run", ""))
           and all(s.get("if") == "env.HAS_KEY == 'true'" for s in rest),
           str([s.get("if") for s in steps(job)]))
        model_steps = [s for s in rest if key in json.dumps(s)]
        ok(f"adversarial-models.yml / {model}: the step holding the key holds "
           f"no GitHub token", model_steps and not any(
               "GH_TOKEN" in json.dumps(s) or "github.token" in json.dumps(s)
               for s in model_steps))
    report = doc["jobs"]["report"]
    ok("adversarial-models.yml / report: labels each issue by its model",
       "adversarial:$model" in json.dumps(report))
    nightly = workflow("nightly.yml")["jobs"]["report"]
    ok("nightly.yml / report: runs after a green run too, and closes the "
       "issues of the jobs that passed",
       re.sub(r"\s", "", str(nightly.get("if"))) == "${{!cancelled()}}"
       and "--close-when-green" in json.dumps(nightly), str(nightly.get("if")))
    ok("...while the monthly and adversarial reports close nothing",
       not any("--close-when-green" in json.dumps(workflow(n)["jobs"]["report"])
               for n in ("monthly.yml", "adversarial-models.yml")))


class FakeGh:
    """gh, as far as open_issues.py uses it. Every open issue was opened by
    the workflow unless `authors` names someone else; `log_error` makes
    `gh run view` fail as it does while the run is still going."""

    def __init__(self, open_titles: dict[str, int], labels: list[str],
                 jobs: list[dict[str, Any]], authors: dict[int, str] | None = None,
                 log_error: str = "",
                 annotations: list[dict[str, Any]] | None = None) -> None:
        self.open_titles, self.labels, self.jobs = open_titles, labels, jobs
        self.authors, self.log_error = authors or {}, log_error
        self.annotations = annotations or []
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_: Any) -> SimpleNamespace:
        args = cmd[1:]
        self.calls.append(args)
        out = ""
        if args[:2] == ["issue", "list"]:
            out = json.dumps([{"number": n, "title": t, "author": {
                "login": self.authors.get(n, "app/github-actions")}}
                for t, n in self.open_titles.items()])
        elif args[:2] == ["label", "list"]:
            out = json.dumps([{"name": n} for n in self.labels])
        elif args[:1] == ["api"] and "/annotations" in args[1]:
            out = json.dumps(self.annotations)
        elif args[:1] == ["api"]:
            out = "\n".join(json.dumps(j) for j in self.jobs)
        elif args[:2] == ["run", "view"]:
            if self.log_error:
                return SimpleNamespace(returncode=1, stdout="",
                                       stderr=self.log_error)
            out = "job\tstep\tline one\njob\tstep\tBROKEN  something\n"
        return SimpleNamespace(returncode=0, stdout=out, stderr="")

    def made(self, *what: str) -> list[list[str]]:
        return [c for c in self.calls if tuple(c[:len(what)]) == what]


def issues() -> None:
    print()
    print("open_issues.py, with a fake gh")
    print("-" * 62)
    os.environ["GH_REPO"] = "owner/repo"
    refused = []
    for words in (["pr", "create"], ["release", "create"], ["repo", "delete"],
                  ["issue", "close", "1"], ["issue", "close", "1", "--reason",
                                            "completed"],
                  ["issue", "edit", "1"], ["issue", "reopen", "1"],
                  ["issue", "delete", "1"], ["issue", "lock", "1"],
                  ["api", "-X", "POST", "repos/x"], ["api", "--method=PUT", "x"],
                  ["api", "repos/x", "-f", "a=b"], ["workflow", "run", "x"]):
        try:
            open_issues.gh(words)
            refused.append(False)
        except open_issues.Refused:
            refused.append(True)
    ok("gh() refuses every command but reading, opening, commenting on and "
       "closing issues, labels and run logs - and a close without a comment",
       all(refused), str(refused))
    open_issues.RUNNER = FakeGh({}, [], [])
    try:
        open_issues.gh(["issue", "close", "1", "--comment", "passed in run 7"])
        closes = True
    except open_issues.Refused:
        closes = False
    ok("...a close with a comment is let through", closes)
    source = (HERE / "open_issues.py").read_text(encoding="utf-8")
    ok("...and nothing in open_issues.py starts a process but through gh()",
       source.count("subprocess.") == 1 and "os.system" not in source)

    def run_jobs(fake: FakeGh, dry: bool = False, most: int = 40,
                 close: bool = False) -> None:
        open_issues.RUNNER = fake
        opener = open_issues.Opener("nightly", dry, most)
        open_issues.jobs(SimpleNamespace(workflow="nightly", run_id="7",  # type: ignore[arg-type]  # stands in for the parsed arguments
                                         close_when_green=close), opener)

    jobs = [{"id": 1, "name": "wheel on ubuntu", "conclusion": "failure",
             "html_url": "u1", "steps": [{"name": "s", "conclusion": "failure"}]},
            {"id": 2, "name": "docker", "conclusion": "success"},
            {"id": 3, "name": "npm on windows", "conclusion": "failure",
             "html_url": "u3", "steps": []}]
    fake = FakeGh({"nightly: npm on windows failed": 12}, [], jobs)
    run_jobs(fake)
    created = fake.made("issue", "create")
    ok("two failed jobs of three: one new issue, titled by the job",
       len(created) == 1 and "nightly: wheel on ubuntu failed" in created[0],
       str(created))
    ok("...the failure already open gets a comment on that issue, not a "
       "second issue", [c[:3] for c in fake.made("issue", "comment")]
       == [["issue", "comment", "12"]], str(fake.made("issue", "comment")))
    ok("...the label is made once, as it was missing",
       len(fake.made("label", "create")) == 1)
    ok("...and the issue carries the failed step's log",
       created and "BROKEN  something" in " ".join(created[0]))
    fake = FakeGh({}, ["nightly"], jobs)
    run_jobs(fake)
    ok("a label that exists is not made again", not fake.made("label", "create"))
    fake = FakeGh({}, [], jobs)
    run_jobs(fake, dry=True)
    ok("--dry-run opens, comments on and labels nothing",
       not fake.made("issue", "create") and not fake.made("issue", "comment")
       and not fake.made("label", "create"))
    many = [{"id": i, "name": f"job {i}", "conclusion": "failure",
             "html_url": "", "steps": []} for i in range(5)]
    fake = FakeGh({}, ["nightly"], many)
    run_jobs(fake, most=2)
    titles = [c[c.index("--title") + 1] for c in fake.made("issue", "create")]
    ok("past --max, one more issue says how many were left out",
       len(titles) == 3 and "3 more failures" in titles[-1], str(titles))
    fake = FakeGh({}, [], [{"id": 1, "name": "ok", "conclusion": "success"}])
    run_jobs(fake)
    ok("a run with no failed job opens nothing and makes no label",
       not fake.made("issue", "create") and not fake.made("label"))

    # the report job runs inside the run it reports on, and gh reads no log
    # of a run that has not finished (nightly #1's nine issues said only that)
    fake = FakeGh({}, ["nightly"], jobs[:1],
                  log_error="run 7 is still in progress; logs will be "
                            "available when it is complete",
                  annotations=[{"annotation_level": "warning",
                                "message": "Node.js 20 is deprecated"},
                               {"annotation_level": "failure",
                                "message": "wheel: --version answers 8.2.1 - "
                                           "No module named velaris"}])
    run_jobs(fake)
    created = fake.made("issue", "create")
    body = created[0][created[0].index("--body") + 1] if created else ""
    ok("a log gh will not read yet: the issue holds the job's failure "
       "annotations instead, and says why",
       "still in progress" in body and "No module named velaris" in body
       and "Node.js 20" not in body, body)

    run = "https://api.github.com/repos/o/r/actions/runs/7"
    green = [{"id": 1, "name": "wheel on ubuntu", "status": "completed",
              "conclusion": "success", "run_url": run, "head_sha": "abc123"},
             {"id": 2, "name": "docker", "status": "completed",
              "conclusion": "success", "run_url": run, "head_sha": "abc123"},
             {"id": 9, "name": "one issue per failed job", "status": "in_progress",
              "conclusion": None}]
    still_open = {"nightly: wheel on ubuntu failed": 12,
                  "nightly: a job since renamed failed": 13,
                  "nightly: docker failed": 14}
    fake = FakeGh(still_open, ["nightly"], green, authors={14: "a-person"})
    run_jobs(fake, close=True)
    closed = fake.made("issue", "close")
    said = closed[0][closed[0].index("--comment") + 1] if closed else ""
    ok("--close-when-green, every job passed: the issue opened for a job "
       "that passed is closed, with a comment naming the run",
       [c[2] for c in closed] == ["12"]
       and "github.com/o/r/actions/runs/7" in said and "abc123" in said,
       str(closed))
    ok("...while an issue for a job the run does not have, and one a person "
       "opened, stay open", not any(c[2] in ("13", "14") for c in closed))
    partly = [green[0], dict(green[1], conclusion="failure", html_url="u2",
                             steps=[]), green[2]]
    fake = FakeGh(still_open, ["nightly"], partly)
    run_jobs(fake, close=True)
    ok("...a run with a job failed closes nothing, not even the issue of the "
       "job that passed, and comments on the one still failing",
       not fake.made("issue", "close")
       and [c[2] for c in fake.made("issue", "comment")] == ["14"],
       str(fake.calls))
    fake = FakeGh(still_open, ["nightly"],
                  [green[0], dict(green[1], conclusion="skipped"), green[2]])
    run_jobs(fake, close=True)
    ok("...nor does a run with a job skipped", not fake.made("issue", "close"))
    fake = FakeGh(still_open, ["nightly"], green)
    run_jobs(fake)
    ok("...nor a green run without --close-when-green, as monthly.yml runs it",
       not fake.made("issue", "close"))
    fake = FakeGh(still_open, ["nightly"], green)
    run_jobs(fake, dry=True, close=True)
    ok("...nor --dry-run", not fake.made("issue", "close"))

    with tempfile.TemporaryDirectory() as d:
        for i, title in enumerate(["# first survivor", "second, no hash"]):
            Path(d, f"{i}.md").write_text(f"{title}\n\nbody {i}\n", encoding="utf-8")
        fake = FakeGh({}, [], [])
        open_issues.RUNNER = fake
        opener = open_issues.Opener("mutation", False, 40)
        open_issues.files(SimpleNamespace(directory=d), opener)  # type: ignore[arg-type]  # stands in for the parsed arguments
        titles = [c[c.index("--title") + 1] for c in fake.made("issue", "create")]
        ok("files: one issue per Markdown file, titled by its first line",
           titles == ["first survivor", "second, no hash"], str(titles))


def models() -> None:
    print()
    print("adversarial_models.py")
    print("-" * 62)
    ok("every area's files exist", all((HERE / f).is_file()
                                       for _, _, fs in adversarial_models.FOCUS
                                       for f in fs),
       str([f for _, _, fs in adversarial_models.FOCUS for f in fs
            if not (HERE / f).is_file()]))
    text = adversarial_models.prompt("budget")
    ok("the prompt names the version, the area and its files, and leaves no "
       "placeholder", adversarial_models.version() in text
       and "effect budgets" in text and "`velaris/budget.py`" in text
       and "{" + "focus" not in text)
    answer = ("prose\n```json\n[{\"title\": \"old\"}]\n```\nmore\n```json\n"
              "[{\"title\": \"a hole\", \"goal\": \"C\", \"where\": \"velaris/x.py:1\","
              " \"reproduction\": \"velaris a.vel -- ```\", \"observed\": "
              "\"key sk-test-12345678 and @someone\"}]\n```\n")
    ok("the last json block is the findings",
       adversarial_models.read_findings(answer) == [
           json.loads(answer.split("```json\n")[2].split("\n```")[0])[0]])
    ok("no block, or a block that is not a list of objects, is no findings",
       adversarial_models.read_findings("nothing") is None
       and adversarial_models.read_findings("```json\n{\"a\": 1}\n```") is None
       and adversarial_models.read_findings("```json\n[1, 2\n```") is None)
    os.environ["XAI_API_KEY"] = "sk-test-12345678"
    with tempfile.TemporaryDirectory() as d:
        answer_file = Path(d, "grok.out")
        answer_file.write_text(answer, encoding="utf-8")
        adversarial_models.findings("grok", str(answer_file), str(Path(d, "out")))
        written = sorted(Path(d, "out").glob("*.md"))
        body = written[0].read_text(encoding="utf-8") if written else ""
        ok("one issue body per finding, its first line the model and title",
           len(written) == 1 and body.startswith("# [grok] a hole\n"), str(written))
        ok("...with the key struck out and no @mention left to ping",
           "sk-test-12345678" not in body and "@someone" not in body, body[-300:])
        ok("...and a fence in the reproduction cannot close the block early",
           body.count("```") == 2)
        answer_file.write_text("I found things but will not say how.",
                               encoding="utf-8")
        adversarial_models.findings("claude", str(answer_file), str(Path(d, "bad")))
        bad = list(Path(d, "bad").glob("*.md"))
        ok("an answer with no findings block becomes one issue saying so",
           len(bad) == 1 and "no findings block" in bad[0].read_text(encoding="utf-8"))
        answer_file.write_text("nothing found\n```json\n[]\n```\n", encoding="utf-8")
        adversarial_models.findings("gemini", str(answer_file), str(Path(d, "none")))
        ok("an empty list opens nothing", not list(Path(d, "none").glob("*.md")))
    del os.environ["XAI_API_KEY"]
    source = (HERE / "adversarial_models.py").read_text(encoding="utf-8")
    ok("adversarial_models.py starts no process and writes nothing into the "
       "repository", "subprocess" not in source and "os.system" not in source)


def main() -> int:
    structure()
    issues()
    models()
    print("-" * 62)
    print(f"{PASS} correct, {FAIL} wrong")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
