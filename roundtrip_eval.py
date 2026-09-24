#!/usr/bin/env python3
"""The model round trip, against Python (plan/8.7.md section 2).

    python roundtrip_eval.py --check              replay every recording; fail if a verdict moved
    python roundtrip_eval.py --record             replay every recording; rewrite results.json
    python roundtrip_eval.py --page               rewrite docs/roundtrip.md from results.json
    python roundtrip_eval.py --live SPEC [SPEC]   ask each model, record it, then --record
    python roundtrip_eval.py --self-test          show --check failing when a verdict moves

WHAT THIS MEASURES. For each model, the same small tasks
(evals/roundtrip/tasks.json) are asked for twice: as a Sabline program, with
the language card LLM.md in the prompt, and as a Python program, with none.
Each answer is compiled and run, and a check of what it printed or wrote,
the same check for both languages, says whether it works; a task with
`more` is run again on each further input, and works only if every run
does. The tasks are in two sets, reported apart: the original ten, and a
held-out set written before the card was changed in answer to the first
recording. A program that does
not compile, or fails when run, goes back to the model with the toolchain's
own message - `sabline check`'s errors, the refusal or runtime error, Python's
traceback - for at most six rounds. A program that runs and prints the wrong
thing is not sent back: the model is told nothing the task did not tell it,
so the answer is not in the feedback. Every failed attempt is one of four
things, reported apart: it did not compile (and the code), it was refused by
the budget (and the code; Sabline only - Python has no budget), it crashed
while running (and the code or the exception), or it ran and did the wrong
thing. Only the first is about the language's syntax.

The numbers are per model, never pooled, and each carries the model's exact
version (a local model's digest, an API's returned model string) and the date
it was recorded. A recording older than six months is marked stale on the
page when the page is built.

EVIDENCE, AND WHAT COSTS MONEY. Asking a model is --live, off by default, and
refused under CI. With --live the model's replies are written to
evals/roundtrip/recordings/, one file per model, card and task set (the
file's name carries the first eight hex digits of LLM.md's and tasks.json's
SHA-256, so asking again after either changed adds a recording and never
replaces one); a recording is replayed for the tasks it was asked, and a
task it was not asked is not scored for it. Everything else - the
compiler, the runs, the checks, the numbers - is re-derived from those
replies by --record and held to results.json by --check, with no model, no
key and no network, which is what CI runs. Anyone with their own key (or a
local model) re-derives a row by running --live for that model; the reply
text will differ between runs of a remote model, which is why the recording
is the evidence and not the number alone.

    SPEC is PROVIDER:MODEL:
      ollama:qwen3:4b                  a local model through Ollama; free.
                                       ROUNDTRIP_OLLAMA sets the server
                                       (default http://127.0.0.1:11434)
      anthropic:claude-sonnet-5        ANTHROPIC_API_KEY
      openai:gpt-6-sol                 OPENAI_API_KEY; ROUNDTRIP_OPENAI_BASE for
                                       another OpenAI-compatible server
      gemini:gemini-3.8-flash          GEMINI_API_KEY, through Google's
                                       OpenAI-compatible endpoint

What a full run of the priced models costs is computed from the recordings
and evals/roundtrip/prices.json, and published with the numbers: a ceiling
that holds whatever a model says, and an estimate from what the recorded
models actually used.
"""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import http.server
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

import agent_loop

HERE = Path(__file__).resolve().parent
EVAL = HERE / "evals" / "roundtrip"
TASKS = EVAL / "tasks.json"
PRICES = EVAL / "prices.json"
RECORDINGS = EVAL / "recordings"
RESULTS = EVAL / "results.json"
PAGE = HERE / "docs" / "roundtrip.md"
SABLINE = HERE / "sabline.py"
CARD = HERE / "LLM.md"
LANGS = ("sabline", "python")
ROUNDS = 6
MAX_TOKENS = 4000               # a reply's ceiling, for every provider
RUN_TIMEOUT = 20                # seconds a program may run
FEEDBACK_CAP = 2000             # characters of toolchain output sent back
STALE_DAYS = 183
HOME_NAME = "roundtrip-home-7c1d"        # HOME, a directory the check looks for
BODY = "sabline round trip\n" * 64          # 1216 characters, for "fetch"
REFUSALS = re.compile(r"E3[12]\d")          # E310-E329: the budget's refusals
SCHEMA = "sabline.roundtrip/2"
RECORDING_SCHEMA = "sabline.roundtrip-recording/1"
SETS = ("original", "held-out")
REPO = "https://github.com/gowrishankar-infra/sabline-lang"

Reply = tuple[str, dict[str, Any]]
Ask = Callable[[list[dict[str, str]]], Reply]


class Exhausted(Exception):
    """A replay needed a reply the recording does not hold."""


# ---- the prompts ----------------------------------------------------------------

def prompt(lang: str, task: dict[str, Any], card: str) -> str:
    stdin = ", with its input on standard input" if task.get("stdin") else ""
    if lang == "sabline":
        return (f"{card}\n\n---\n\nWrite a Sabline program that does this:\n\n"
                f"{task['task']}\n\nIt will be run as `sabline program.vel "
                f"--allow {task['budget']}`{stdin}, and what it prints to "
                f"standard output is what is checked. Return only the program "
                f"in one code block. It must pass `sabline check`.")
    return (f"Write a Python 3 program that does this:\n\n{task['task']}\n\n"
            f"It will be run as `python program.py`{stdin}, with the standard "
            f"library only, and what it prints to standard output is what is "
            f"checked. Return only the program in one code block.")


def feedback(lang: str, stage: str, text: str) -> str:
    text = text[-FEEDBACK_CAP:]
    if stage == "compile":
        tool = "`sabline check`" if lang == "sabline" else \
            "`python -m py_compile`"
        return (f"{tool} reported this. Fix it and return the whole program "
                f"again, only the code block:\n\n{text}")
    return (f"It failed when run:\n\n{text}\n\nFix it and return the whole "
            f"program again, only the code block.")


def just_code(reply: str) -> str:
    """The program in a reply: the first fenced block, without its language
    tag, or the whole reply when there is none. A reasoning model's
    <think> block is not the program."""
    reply = re.sub(r"<think>.*?</think>", "", reply, flags=re.S)
    if "```" not in reply:
        return reply.strip() + "\n"
    chunk = reply.split("```", 2)[1]
    first, _, rest = chunk.partition("\n")
    if re.fullmatch(r"[A-Za-z0-9_+-]*", first.strip()):
        chunk = rest
    return chunk.strip("\n") + "\n"


# ---- the toolchain ---------------------------------------------------------------

class Listener:
    """A local HTTP server for the "fetch" task: every GET gets BODY."""

    def __init__(self) -> None:
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                data = BODY.encode("ascii")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args: Any) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()


class Masker:
    def __init__(self, root: Path, port: int) -> None:
        self.forms = sorted({str(root), root.as_posix(),
                             str(root).replace("\\", "\\\\")}, key=len,
                            reverse=True)
        self.port = str(port)

    def __call__(self, text: str) -> str:
        for f in self.forms:
            text = text.replace(f, "<workdir>")
        for f in sorted({str(HERE), HERE.as_posix()}, key=len, reverse=True):
            text = text.replace(f, "<repo>")
        return text.replace(f":{self.port}", ":<port>")


def env_for(home: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env["PYTHONHASHSEED"] = "0"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run(cmd: list[str], cwd: Path, stdin: str, home: Path) -> dict[str, Any]:
    try:
        done = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True,
                              text=True, encoding="utf-8", errors="replace",
                              timeout=RUN_TIMEOUT, env=env_for(home))
        return {"exit": done.returncode, "stdout": done.stdout,
                "stderr": done.stderr, "timed_out": False}
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else ""
        return {"exit": None, "stdout": out, "stderr": "", "timed_out": True}


def compile_step(lang: str, path: Path, home: Path
                 ) -> tuple[bool, str, str | None]:
    """(compiled, what to tell the model, the code or exception)."""
    if lang == "sabline":
        errors = agent_loop.check(path)
        if not errors:
            return True, "", None
        codes = sorted({str(e.get("code")) for e in errors})
        return False, agent_loop.complain(errors), ",".join(codes)
    done = subprocess.run([sys.executable, "-I", "-S", "-m", "py_compile",
                           str(path)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace",
                          env=env_for(home))
    if done.returncode == 0:
        return True, "", None
    text = done.stderr or done.stdout
    return False, text, python_exception(text) or "SyntaxError"


def python_exception(stderr: str) -> str | None:
    for line in reversed(stderr.strip().splitlines()):
        m = re.match(r"([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|"
                     r"Warning))\b", line.strip())
        if m:
            return m.group(1).split(".")[-1]
    return None


def sabline_code(stderr: str) -> str | None:
    m = re.search(r"error\[(E\d{3})\]", stderr)
    return m.group(1) if m else None


def last_number(text: str) -> str | None:
    found = re.findall(r"-?\d+(?:\.\d+)?", text)
    return found[-1] if found else None


def runs_of(task: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Each run of a task: (standard input, check). The first is the task's
    own; `more` adds one for each further input."""
    return [(task.get("stdin") or "", task["check"])] + [
        (m.get("stdin") or "", m["check"]) for m in task.get("more", [])]


def set_of(task: dict[str, Any]) -> str:
    return str(task.get("set", "original"))


def works(c: dict[str, Any], stdout: str, cwd: Path) -> bool:
    """One run's check, the same for both languages."""
    ok = True
    if "numbers" in c:
        printed = re.findall(r"-?\d+(?:\.\d+)?", stdout)
        ok = ok and [Decimal(g) for g in printed] == \
            [Decimal(n) for n in c["numbers"]]
    if "stdout_re" in c:
        ok = ok and re.search(c["stdout_re"], stdout) is not None
    if "stdout_not_re" in c:
        ok = ok and re.search(c["stdout_not_re"], stdout) is None
    if "last_number" in c:
        got = last_number(stdout)
        ok = ok and got is not None and Decimal(got) == Decimal(c["last_number"])
    if "file" in c:
        f = cwd / c["file"]
        ok = ok and f.is_file() and \
            f.read_text(encoding="utf-8", errors="replace").strip() == \
            c["file_equals"]
    if "amounts_sum" in c:
        try:
            amounts = [Decimal(a) for a in re.findall(
                r"(?<![\d.])\d+\.\d{2}(?![\d])", stdout)]
        except InvalidOperation:
            amounts = []
        parts = [a for a in amounts if a != Decimal(c["amounts_sum"])]
        n = int(c["amounts"])
        ok = ok and len(parts) >= n and \
            sum(parts[:n], Decimal(0)) == Decimal(c["amounts_sum"])
    return ok


def attempt(lang: str, task: dict[str, Any], code: str, cwd: Path,
            url: str, mask: Masker) -> tuple[dict[str, Any], str | None]:
    """Compile and run one answer. (the attempt, what to tell the model
    next, or None when the conversation ends here)."""
    cwd.mkdir(parents=True, exist_ok=True)
    home = cwd.parent / HOME_NAME
    home.mkdir(exist_ok=True)
    path = cwd / ("program.vel" if lang == "sabline" else "program.py")
    path.write_text(code, encoding="utf-8")
    compiled, said, ccode = compile_step(lang, path, home)
    if not compiled:
        return ({"class": "did-not-compile", "code": ccode,
                 "evidence": {"compiler": mask(said)[:600]}},
                feedback(lang, "compile", mask(said)))
    cmd = ([sys.executable, str(SABLINE), str(path), "--allow", task["budget"]]
           if lang == "sabline" else [sys.executable, "-I", "-S", str(path)])
    shown = (["sabline", "<workdir>/program.vel", "--allow", task["budget"]]
             if lang == "sabline" else ["python", "<workdir>/program.py"])
    first: dict[str, Any] = {}
    for n, (given, check) in enumerate(runs_of(task), start=1):
        stdin = given.replace("{url}", url)
        res = run(cmd, cwd, stdin, home)
        ev = {"command": " ".join(shown), "exit": res["exit"],
              "stdout": mask(res["stdout"])[:300],
              "stderr": mask(res["stderr"])[-400:]}
        # a run after the first names itself, and is named to the model:
        # the input it was given is in the task's terms, never the answer
        again = ""
        if n > 1:
            ev["run"] = n
            again = f"(run again, with {stdin.strip()!r} on standard input)\n\n"
        if res["timed_out"]:
            return ({"class": "timeout", "code": None, "evidence": ev},
                    feedback(lang, "run", again + f"stopped after "
                             f"{RUN_TIMEOUT} s: it did not finish"))
        if res["exit"] != 0:
            if lang == "sabline":
                rc = sabline_code(res["stderr"])
                cls = "refused" if rc and REFUSALS.fullmatch(rc) else "crashed"
            else:
                rc = python_exception(res["stderr"])
                cls = "crashed"
            return ({"class": cls, "code": rc or f"exit {res['exit']}",
                     "evidence": ev},
                    feedback(lang, "run", again + (mask(res["stderr"]) or
                             f"it exited with status {res['exit']}")))
        if not works(check, res["stdout"], cwd):
            return {"class": "wrong", "code": None, "evidence": ev}, None
        first = first or ev
    return {"class": "works", "code": None, "evidence": first}, None


def converse(lang: str, task: dict[str, Any], ask: Ask, root: Path, card: str,
             url: str, mask: Masker) -> dict[str, Any]:
    messages = [{"role": "user", "content": prompt(lang, task, card)}]
    attempts: list[dict[str, Any]] = []
    exchanges: list[dict[str, Any]] = []
    for r in range(1, ROUNDS + 1):
        try:
            reply, meta = ask(messages)
        except Exhausted:
            attempts.append({"class": "recording-exhausted", "code": None,
                             "evidence": {}})
            break
        sent_chars = sum(len(m["content"]) for m in messages)
        got, tell = attempt(lang, task, just_code(reply),
                            root / f"{lang}-{task['id']}-{r}", url, mask)
        attempts.append({"round": r, **got})
        exchanges.append({"reply": reply, "meta": meta, "feedback": tell,
                          "sent_chars": sent_chars})
        if tell is None:
            break
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": tell})
    return {"attempts": attempts, "exchanges": exchanges}


# ---- the models (--live only) ----------------------------------------------------

def post_json(url: str, body: dict[str, Any], headers: dict[str, str],
              timeout: int = 1800) -> dict[str, Any]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"content-type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{url}: HTTP {e.code}: {e.read()[:300]!r}")
    try:
        answer: dict[str, Any] = json.loads(data)
    except json.JSONDecodeError:
        raise SystemExit(f"{url}: the answer is not JSON ({data[:80]!r}) - a "
                         f"proxy in between, or not the service asked for")
    return answer


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=60) as resp:
        answer: dict[str, Any] = json.loads(resp.read())
    return answer


def model_for(spec: str) -> tuple[Ask, dict[str, Any]]:
    """(ask, the model's identity and the options it was asked with)."""
    provider, _, name = spec.partition(":")
    if provider == "ollama":
        base = os.environ.get("ROUNDTRIP_OLLAMA", "http://127.0.0.1:11434")
        tags = get_json(f"{base}/api/tags")["models"]
        found = next((m for m in tags if m["name"] == name), None)
        if found is None:
            raise SystemExit(f"{name} is not pulled on {base} "
                             f"(ollama pull {name})")
        shown = post_json(f"{base}/api/show", {"model": name}, {})
        thinks = "thinking" in (shown.get("capabilities") or [])
        options = {"temperature": 0, "seed": 7, "num_ctx": 16384,
                   "num_predict": MAX_TOKENS}
        ident = {"spec": spec, "provider": "ollama", "name": name,
                 "version": found["digest"], "details": found.get("details"),
                 "server": get_json(f"{base}/api/version").get("version"),
                 "options": {**options, "think": False if thinks else None}}

        def ask(messages: list[dict[str, str]]) -> Reply:
            body: dict[str, Any] = {"model": name, "messages": messages,
                                    "stream": False, "options": options}
            if thinks:
                body["think"] = False
            t = time.time()
            a = post_json(f"{base}/api/chat", body, {})
            return a["message"]["content"], {
                "input_tokens": a.get("prompt_eval_count"),
                "output_tokens": a.get("eval_count"),
                "seconds": round(time.time() - t, 1)}
        return ask, ident
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("anthropic: set ANTHROPIC_API_KEY")
        ident = {"spec": spec, "provider": "anthropic", "name": name,
                 "version": None, "options": {"temperature": 0,
                                              "max_tokens": MAX_TOKENS}}

        def ask(messages: list[dict[str, str]]) -> Reply:
            t = time.time()
            a = post_json("https://api.anthropic.com/v1/messages",
                          {"model": name, "max_tokens": MAX_TOKENS,
                           "temperature": 0, "messages": messages},
                          {"x-api-key": key or "",
                           "anthropic-version": "2023-06-01"})
            ident["version"] = a.get("model")
            u = a.get("usage") or {}
            return "".join(p.get("text", "") for p in a["content"]), {
                "input_tokens": u.get("input_tokens"),
                "output_tokens": u.get("output_tokens"),
                "seconds": round(time.time() - t, 1)}
        return ask, ident
    if provider in ("openai", "gemini"):
        if provider == "openai":
            base = os.environ.get("ROUNDTRIP_OPENAI_BASE",
                                  "https://api.openai.com/v1")
            key = os.environ.get("OPENAI_API_KEY")
            limit = "max_completion_tokens"
        else:
            base = "https://generativelanguage.googleapis.com/v1beta/openai"
            key = os.environ.get("GEMINI_API_KEY")
            limit = "max_tokens"
        if not key:
            raise SystemExit(f"{provider}: set "
                             f"{'OPENAI' if provider == 'openai' else 'GEMINI'}"
                             f"_API_KEY")
        ident = {"spec": spec, "provider": provider, "name": name,
                 "version": None, "options": {limit: MAX_TOKENS}}

        def ask(messages: list[dict[str, str]]) -> Reply:
            t = time.time()
            a = post_json(f"{base}/chat/completions",
                          {"model": name, "messages": messages,
                           limit: MAX_TOKENS},
                          {"authorization": f"Bearer {key}"})
            ident["version"] = a.get("model")
            u = a.get("usage") or {}
            return a["choices"][0]["message"]["content"] or "", {
                "input_tokens": u.get("prompt_tokens"),
                "output_tokens": u.get("completion_tokens"),
                "seconds": round(time.time() - t, 1)}
        return ask, ident
    raise SystemExit(f"{spec}: the provider is ollama, anthropic, openai or "
                     f"gemini")


def replay(replies: list[Reply]) -> Ask:
    left = list(replies)

    def ask(messages: list[dict[str, str]]) -> Reply:
        if not left:
            raise Exhausted()
        return left.pop(0)
    return ask


# ---- one model, both languages ---------------------------------------------------

def slug(spec: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", spec)


def digest(path: Path) -> str:
    """SHA-256 of a text file with its line ends as LF, so a Windows
    checkout (CRLF) and a Linux one name the same card the same way."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")
                          ).hexdigest()


def recording_name(spec: str, record: dict[str, Any], run: int = 1) -> str:
    """One file per model, card, task set and run. A model asked again with
    the same card and tasks is a second run, never a replacement: a local
    model at temperature 0 with a fixed seed does not answer a 9,000-token
    prompt the same way twice (Ollama 0.24, qwen2.5:7b, 2026-09-24), so
    the spread between runs is part of the result."""
    return (f"{slug(spec)}.card-{record['card_sha256'][:8]}"
            f".tasks-{record['tasks_sha256'][:8]}"
            + (f".run-{run}" if run > 1 else "") + ".json")


def run_of(recording: str) -> int:
    m = re.search(r"\.run-(\d+)\.json$", recording)
    return int(m.group(1)) if m else 1


def run_model(tasks: list[dict[str, Any]], asks: dict[str, Ask],
              ) -> dict[str, dict[str, Any]]:
    """{lang: {task id: the conversation}} for one model."""
    card = CARD.read_text(encoding="utf-8")
    listener = Listener()
    out: dict[str, dict[str, Any]] = {}
    try:
        with tempfile.TemporaryDirectory(prefix="sabline-roundtrip-") as d:
            root = Path(d).resolve()
            mask = Masker(root, listener.port)
            url = f"http://127.0.0.1:{listener.port}/page"
            for lang in LANGS:
                out[lang] = {}
                for t in tasks:
                    # a recording is scored on the tasks it was asked, and
                    # only those: one made before a task existed has no
                    # answer to it, which is not the same as giving up
                    if f"{lang}:{t['id']}" not in asks:
                        continue
                    out[lang][t["id"]] = converse(
                        lang, t, asks[f"{lang}:{t['id']}"], root, card, url,
                        mask)
    finally:
        listener.close()
    return out


def live(specs: list[str]) -> int:
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        print("--live asks a model and may cost money; it never runs in CI")
        return 2
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    RECORDINGS.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        ask, ident = model_for(spec)
        print(f"asking {spec} ({ident.get('version')}) ...", flush=True)
        started = time.time()

        def logged(messages: list[dict[str, str]]) -> Reply:
            reply, meta = ask(messages)
            print(f"  call {len(messages) // 2 + 1}: {meta}", flush=True)
            return reply, meta
        convs = run_model(tasks, {f"{lang}:{t['id']}": logged
                                  for lang in LANGS for t in tasks})
        record = {
            "schema": RECORDING_SCHEMA, "model": ident,
            "recorded": datetime.date.today().isoformat(),
            "rounds": ROUNDS, "max_tokens": MAX_TOKENS,
            "card_sha256": digest(CARD), "tasks_sha256": digest(TASKS),
            "platform": f"{platform.system()} {platform.machine()}",
            "minutes": round((time.time() - started) / 60, 1),
            "conversations": {
                f"{lang}:{tid}": [{"reply": x["reply"], "meta": x["meta"],
                                   "feedback": x["feedback"],
                                   "sent_chars": x["sent_chars"]}
                                  for x in conv["exchanges"]]
                for lang, byid in convs.items()
                for tid, conv in byid.items()}}
        run = 1
        while (RECORDINGS / recording_name(spec, record, run)).exists():
            run += 1
        path = RECORDINGS / recording_name(spec, record, run)
        path.write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(HERE)}")
    return derive(write=True)


# ---- the record ------------------------------------------------------------------

def summarise(convs: dict[str, dict[str, Any]],
              tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """{set: {lang: the numbers}}, for each set the recording was asked
    any task of."""
    sets = {t["id"]: set_of(t) for t in tasks}
    out: dict[str, Any] = {}
    for name in SETS:
        for lang, all_byid in convs.items():
            byid = {tid: c for tid, c in all_byid.items()
                    if sets.get(tid) == name}
            if not byid:
                continue
            finals = {tid: c["attempts"][-1]["class"]
                      for tid, c in byid.items()}
            failed: dict[str, int] = {}
            for c in byid.values():
                for a in c["attempts"]:
                    if a["class"] != "works":
                        key = a["class"] + (f" {a['code']}" if a.get("code")
                                            else "")
                        failed[key] = failed.get(key, 0) + 1
            rounds = [len(c["attempts"]) for c in byid.values()
                      if c["attempts"][-1]["class"] == "works"]
            out.setdefault(name, {})[lang] = {
                "tasks": len(byid),
                "works_first": sum(1 for c in byid.values()
                                   if c["attempts"][0]["class"] == "works"),
                "works": sum(1 for v in finals.values() if v == "works"),
                "wrong": sum(1 for v in finals.values() if v == "wrong"),
                "gave_up": sum(1 for v in finals.values()
                               if v not in ("works", "wrong")),
                "mean_rounds_to_work": round(sum(rounds) / len(rounds), 2)
                if rounds else None,
                "failed_attempts": dict(sorted(failed.items())),
            }
    return out


def usage(rec: dict[str, Any]) -> dict[str, Any]:
    """What a recording sent and received, per language, for the cost."""
    out: dict[str, Any] = {}
    for lang in LANGS:
        calls = [x for k, conv in rec["conversations"].items()
                 if k.startswith(lang + ":") for x in conv]
        out[lang] = {"calls": len(calls),
                     "sent_chars": sum(x.get("sent_chars") or 0
                                       for x in calls),
                     "reply_chars": sum(len(x["reply"]) for x in calls)}
    return out


def cost(models: list[dict[str, Any]], tasks: list[dict[str, Any]]
         ) -> dict[str, Any]:
    """What running every priced model would cost: a ceiling that holds
    whatever a model says, and an estimate from what the recorded models
    used. Tokens are counted from characters: at most 3 characters a token
    for the ceiling, 4 for the estimate, times each model's tokenizer factor."""
    prices = json.loads(PRICES.read_text(encoding="utf-8"))
    card = CARD.read_text(encoding="utf-8")
    base = {lang: sum(len(prompt(lang, t, card)) for t in tasks)
            for lang in LANGS}
    # ceiling: every task runs every round in both languages, every reply is
    # MAX_TOKENS long, every feedback FEEDBACK_CAP characters and its wrapper
    ceil_in_chars = 0.0
    ceil_out_tokens = 0.0
    for lang in LANGS:
        for r in range(1, ROUNDS + 1):
            ceil_in_chars += base[lang] + len(tasks) * (r - 1) * (
                FEEDBACK_CAP + 200)
            ceil_out_tokens += len(tasks) * MAX_TOKENS
    ceil_reply_tokens_in = sum(len(tasks) * (r - 1) * MAX_TOKENS
                               for r in range(1, ROUNDS + 1)) * len(LANGS)
    # estimate: the mean of what the recordings asked every current task
    # sent and got (one asked fewer tasks would understate it)
    measured = [m["usage"] for m in models if m["asked_every_task"]]
    if measured:
        est_in = sum(s[lang]["sent_chars"] for s in measured
                     for lang in LANGS) / len(measured)
        est_out = sum(s[lang]["reply_chars"] for s in measured
                      for lang in LANGS) / len(measured)
        est_calls = sum(s[lang]["calls"] for s in measured
                        for lang in LANGS) / len(measured)
    else:
        est_in = est_out = est_calls = 0.0
    rows = []
    for p in prices["models"]:
        tf = float(p.get("tokenizer_factor", 1.0))
        ceil = ((ceil_in_chars / 3 * tf + ceil_reply_tokens_in) * p["input"]
                + ceil_out_tokens * p["output"]) / 1e6
        est = (est_in / 4 * tf * p["input"] + est_out / 4 * tf * p["output"]
               ) / 1e6
        rows.append({"spec": p["spec"], "input": p["input"],
                     "output": p["output"], "ceiling_usd": round(ceil, 2),
                     "estimate_usd": round(est, 2)})
    return {"prices_read": prices["read"], "sources": prices["sources"],
            "assumptions": {
                "rounds": ROUNDS, "max_tokens": MAX_TOKENS,
                "feedback_cap_chars": FEEDBACK_CAP,
                "ceiling_chars_per_token": 3, "estimate_chars_per_token": 4,
                "estimate_from": [m["recording"] for m in models
                                  if m["asked_every_task"]],
                "estimate_calls_per_model": round(est_calls, 1)},
            "models": rows,
            "ceiling_usd": round(sum(r["ceiling_usd"] for r in rows), 2),
            "estimate_usd": round(sum(r["estimate_usd"] for r in rows), 2)}


def derive(write: bool) -> int:
    """Replay every recording through the toolchain and build the record;
    write it, or hold the committed one to it."""
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    card, taskset = digest(CARD), digest(TASKS)
    models = []
    for path in sorted(RECORDINGS.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        asks = {k: replay([(x["reply"], x["meta"]) for x in v])
                for k, v in rec["conversations"].items()}
        convs = run_model(tasks, asks)
        models.append({
            "model": rec["model"], "recorded": rec["recorded"],
            "recording": path.relative_to(HERE).as_posix(),
            "card_sha256": rec["card_sha256"],
            "card_is_current": rec["card_sha256"] == card,
            "tasks_sha256": rec["tasks_sha256"],
            "tasks_are_current": rec["tasks_sha256"] == taskset,
            "asked_every_task": all(f"{lang}:{t['id']}" in asks
                                    for lang in LANGS for t in tasks),
            "summary": summarise(convs, tasks),
            "usage": usage(rec),
            "tasks": {lang: {tid: c["attempts"] for tid, c in byid.items()}
                      for lang, byid in convs.items()}})
    import sabline
    result = {
        "schema": SCHEMA,
        "platform": f"{platform.system()} {platform.machine()}",
        "python": ".".join(platform.python_version_tuple()[:2]),
        "sabline": sabline.VERSION,
        "rounds": ROUNDS, "card_sha256": card, "tasks_sha256": taskset,
        "tasks": {name: [t["id"] for t in tasks if set_of(t) == name]
                  for name in SETS},
        "models": models,
        "cost": cost(models, tasks)}
    text = json.dumps(result, indent=1, ensure_ascii=False) + "\n"
    if write:
        RESULTS.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {RESULTS.relative_to(HERE)}: {len(models)} model(s)")
        report(result)
        return 0
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    wrong = compare(recorded, result)
    if wrong:
        print("the round trip does not re-derive:")
        for w in wrong[:40]:
            print("  " + w)
        return 1
    print(f"every attempt of {len(models)} model(s) re-derives, "
          f"{len(tasks)} tasks in two languages")
    return 0


def verdicts(result: dict[str, Any]) -> dict[str, Any]:
    """What --check holds: each attempt's class, code, exit and stdout, per
    recording, language and task; the summaries; and the cost."""
    out: dict[str, Any] = {}
    for m in result["models"]:
        key = m["recording"]
        for lang, byid in m["tasks"].items():
            for tid, atts in byid.items():
                out[f"{key} {lang} {tid}"] = [
                    (a["class"], a.get("code"),
                     (a.get("evidence") or {}).get("exit"),
                     (a.get("evidence") or {}).get("stdout"))
                    for a in atts]
        out[f"{key} summary"] = m["summary"]
        out[f"{key} current"] = (m["card_is_current"], m["tasks_are_current"])
    out["cost"] = result["cost"]
    out["sabline"] = result["sabline"]
    out["python"] = result["python"]
    return out


def compare(recorded: dict[str, Any], now: dict[str, Any]) -> list[str]:
    a, b = verdicts(recorded), verdicts(now)
    wrong = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            wrong.append(f"{k}: recorded {json.dumps(a.get(k))[:200]}, now "
                         f"{json.dumps(b.get(k))[:200]}")
    return wrong


def report(result: dict[str, Any]) -> None:
    for m in result["models"]:
        print(f"  {m['model']['spec']}, card {m['card_sha256'][:8]}, tasks "
              f"{m['tasks_sha256'][:8]}:")
        for name, s in m["summary"].items():
            print(f"    {name:<9} " + "  ".join(
                f"{lang}: {s[lang]['works_first']}/{s[lang]['works']} of "
                f"{s[lang]['tasks']}" for lang in LANGS if lang in s)
                + f" (first/within {ROUNDS})")
    c = result["cost"]
    print(f"  the priced set: ceiling ${c['ceiling_usd']}, estimate "
          f"${c['estimate_usd']}")


def self_test() -> int:
    recorded = json.loads(RESULTS.read_text(encoding="utf-8"))
    if not recorded["models"]:
        print("roundtrip_eval.py --self-test: no model recorded")
        return 1
    bad = copy.deepcopy(recorded)
    m = bad["models"][0]
    lang = next(iter(m["tasks"]))
    tid = next(iter(m["tasks"][lang]))
    first = m["tasks"][lang][tid][0]
    first["class"] = "wrong" if first["class"] != "wrong" else "works"
    caught = bool(compare(recorded, bad))
    same = not compare(recorded, copy.deepcopy(recorded))
    print(f"  {'ok   ' if same else 'WRONG'} the record against itself: "
          f"no difference")
    print(f"  {'ok   ' if caught else 'WRONG'} one attempt's class changed "
          f"({m['model']['spec']} {lang} {tid}): "
          f"{'refused' if caught else 'NOT refused'}")
    # a task's further inputs: an answer that prints what the first input
    # needs, whatever it read, works on one run and not on two
    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    parse = next(t for t in tasks if t["id"] == "parse")
    with tempfile.TemporaryDirectory(prefix="sabline-roundtrip-") as d:
        root = Path(d).resolve()
        mask = Masker(root, 0)
        fixed, _ = attempt("python", parse, "input()\nprint(43)\n",
                           root / "fixed", "", mask)
        honest, _ = attempt("python", parse, "print(int(input()) + 1)\n",
                            root / "honest", "", mask)
    held = fixed["class"] == "wrong" and honest["class"] == "works"
    print(f"  {'ok   ' if held else 'WRONG'} parse's second input: a fixed "
          f"43 is {fixed['class']}, reading the input {honest['class']}")
    good = same and caught and held
    print("roundtrip_eval.py --self-test: " + ("0 wrong" if good else "WRONG"))
    return 0 if good else 1


# ---- the page ----------------------------------------------------------------------

LABEL = {"works": "works", "wrong": "wrong output", "did-not-compile":
         "did not compile", "refused": "refused by the budget",
         "crashed": "crashed", "timeout": "timed out",
         "recording-exhausted": "recording exhausted"}


def page(result: dict[str, Any], today: datetime.date) -> str:
    w: list[str] = []
    p = w.append
    models = result["models"]
    names = {"original": "The original ten tasks",
             "held-out": "The held-out tasks"}
    p("# Model round trip")
    p("")
    p("For each model, the same small tasks asked for twice - as a "
      "Sabline program, with the language card "
      "[LLM.md](../LLM.md) in the prompt, and as a Python program, with none "
      "- and each answer compiled, run, and checked by the same check in "
      "both languages. A failed answer goes back to the model with the "
      "toolchain's own message, for at most "
      f"{result['rounds']} rounds; a wrong answer is not sent back, so the "
      "feedback never carries the answer. This is "
      "[plan/8.7.md](../plan/8.7.md) section 2: the number that speaks to "
      "whether a model can write this language, beside the language models "
      "already write. The page is generated from "
      "`evals/roundtrip/results.json`, which `roundtrip_eval.py` re-derives "
      "from the recorded replies on every push, with no model and no key.")
    p("")
    p(f"The tasks are in two sets, reported apart: the original "
      f"{len(result['tasks']['original'])}, which the card was changed in "
      "answer to after the first recording, and "
      f"{len(result['tasks']['held-out'])} held out from that change - "
      "written and committed before it, by the person who then made it, so "
      "they are held out from the edit and not from its author. A row is "
      "one recording: a model, the card it was given and the task set it "
      "was asked, each named by the first eight hex digits of its SHA-256. "
      f"The current card is `{result['card_sha256'][:8]}` and the current "
      f"task set `{result['tasks_sha256'][:8]}`; a recording is scored on "
      "the tasks it was asked, by today's checks.")
    p("")
    p("> [!NOTE]")
    p(f"> **Scored** on {result['platform']}, Python {result['python']}, "
      f"Sabline {result['sabline']}. Each row gives the model's exact "
      "version and the date its replies were recorded; a recording more "
      f"than {STALE_DAYS} days old is marked **stale** when this page is "
      "built, and its numbers are not carried to a newer version of the "
      "model.")
    p("")
    p("## The numbers")
    p("")
    if not models:
        p("No model has been recorded.")
        p("")
    for name in SETS if models else ():
        rows = [m for m in models if name in m["summary"]]
        p(f"### {names[name]}")
        p("")
        if not rows:
            p("No recording has been asked these tasks yet.")
            p("")
            continue
        p(f"Tasks that work on the first answer / within {result['rounds']} "
          f"rounds, of {len(result['tasks'][name])}, and how the rest ended.")
        p("")
        p("| Model | Version | Card | Tasks | Recorded | Run | Sabline: "
          "first / within | Python: first / within | Sabline wrong / gave "
          "up | Python wrong / gave up |")
        p("|---|---|---|---|---|---:|---:|---:|---:|---:|")
        for m in rows:
            s = m["summary"][name]
            age = (today - datetime.date.fromisoformat(m["recorded"])).days
            stale = " **stale**" if age > STALE_DAYS else ""
            ver = str(m["model"].get("version") or "?")
            ver = ver[:19] if ver.startswith("sha256:") else ver[:12]
            card = f"`{m['card_sha256'][:8]}`" + (
                " (current)" if m["card_is_current"] else "")
            run = run_of(m["recording"])
            tasks = f"`{m['tasks_sha256'][:8]}`" + (
                "" if m["tasks_are_current"] else " (earlier)")
            cells = [f"{s[lang]['works_first']} / {s[lang]['works']}"
                     for lang in LANGS] + [
                f"{s[lang]['wrong']} / {s[lang]['gave_up']}" for lang in LANGS]
            p(f"| `{m['model']['spec']}` | `{ver}` | {card} | {tasks} | "
              f"{m['recorded']}{stale} | {run} | " + " | ".join(cells) + " |")
        p("")
    if models:
        p("### Every failed attempt, by what went wrong")
        p("")
        p("Did not compile (with the compiler's code, or Python's "
          "exception), refused by the budget (Sabline only: Python has no "
          "budget), crashed while running, timed out, or ran and printed the "
          "wrong thing. Only the first is about the language's syntax.")
        p("")
        p("| Model | Card | Run | Set | Language | Failed attempts |")
        p("|---|---|---:|---|---|---|")
        for m in models:
            for name, s in m["summary"].items():
                for lang in LANGS:
                    fa = s[lang]["failed_attempts"]
                    p(f"| `{m['model']['spec']}` | `{m['card_sha256'][:8]}` "
                      f"| {run_of(m['recording'])} | {name} | {lang} | " + (
                          ", ".join(f"{k} x{v}" for k, v in fa.items())
                          or "none") + " |")
        p("")
        p("### Every task")
        p("")
        p("Each cell is the attempts in order, ending at the first that "
          "worked or printed the wrong thing. A task a recording was not "
          "asked is left out of its table.")
        p("")
        for m in models:
            p(f"**`{m['model']['spec']}`, card `{m['card_sha256'][:8]}`, "
              f"tasks `{m['tasks_sha256'][:8]}`, run "
              f"{run_of(m['recording'])}**")
            p("")
            p("| Task | Set | Sabline | Python |")
            p("|---|---|---|---|")
            for name in SETS:
                for tid in result["tasks"][name]:
                    if tid not in m["tasks"].get("sabline", {}):
                        continue
                    cells = []
                    for lang in LANGS:
                        cells.append(" → ".join(
                            LABEL.get(a["class"], a["class"])
                            + (f" ({a['code']})" if a.get("code") else "")
                            for a in m["tasks"][lang][tid]))
                    p(f"| {tid} | {name} | {cells[0]} | {cells[1]} |")
            p("")
    c = result["cost"]
    a = c["assumptions"]
    p("## What the full set would cost")
    p("")
    p("The models the harness is ready to ask, at the prices their vendors "
      f"published (read {c['prices_read']}: "
      + ", ".join(f"[{k}]({v})" for k, v in c["sources"].items())
      + "). The **ceiling** holds whatever a model says: every task runs "
      f"all {a['rounds']} rounds in both languages, every reply is "
      f"{a['max_tokens']} tokens (the harness's maximum), every message "
      f"counted at {a['ceiling_chars_per_token']} characters a token, with "
      "Anthropic's newer tokenizer counted 30% heavier. The **estimate** is "
      "what the recorded models actually sent and received ("
      + ", ".join(f"`{s}`" for s in a["estimate_from"])
      + f", about {a['estimate_calls_per_model']} calls a model), at "
      f"{a['estimate_chars_per_token']} characters a token. No prompt cache "
      "and no batch discount, both of which would lower it.")
    p("")
    p("| Model | Input $/MTok | Output $/MTok | Ceiling | Estimate |")
    p("|---|---:|---:|---:|---:|")
    for r in c["models"]:
        p(f"| `{r['spec']}` | {r['input']:.2f} | {r['output']:.2f} | "
          f"${r['ceiling_usd']:.2f} | ${r['estimate_usd']:.2f} |")
    p(f"| **All of them** | | | **${c['ceiling_usd']:.2f}** | "
      f"**${c['estimate_usd']:.2f}** |")
    p("")
    p("What costs nothing: any model that runs locally (the rows above, "
      "through Ollama), and the free tiers some vendors list - Google lists "
      "one for several Gemini models - which need that vendor's key, and "
      "which this project does not hold. A local model is free in money and "
      "not in time: a model that reasons at length before it answers takes "
      "minutes a call on a small graphics card.")
    p("")
    p("## What it does not show")
    p("")
    p("- **The models on this page are the free ones.** Every row is a "
      "model that runs locally for nothing; none of the priced models has "
      "been asked. Small quantized models are weaker than the models an "
      "agent is usually built on, at both languages, so the gap between the "
      "two columns is the thing to read, not either column.")
    p("- **One sample, at temperature 0.** A model is asked once per task "
      "and language. A different seed, or a remote model's own "
      "nondeterminism, would give different replies; the recording is what "
      "was actually said. A changed card changes every prompt, so every "
      "answer can change with it: a difference of one task between two "
      "rows is noise, not a finding.")
    p("- **Small tasks written by this project**: the ten "
      "`agent_loop.py --metric` already had, and the held-out set. They are "
      "not a benchmark of programming ability, and a task that exercises "
      "what Sabline refuses (a budget, a Secret) is harder in Sabline by "
      "design. The held-out tasks are held out from a card change, not "
      "from the person who wrote both.")
    p("- **Sabline gets a card and Python does not.** A model has read "
      "Python; it has not read Sabline. The card is the documentation a "
      "model is meant to be given, and it is what the premise is about.")
    p("")
    p("## Reproducing it")
    p("")
    p("    python roundtrip_eval.py --check                   # re-derive every verdict, no model")
    p("    python roundtrip_eval.py --live ollama:qwen3:4b    # ask a local model, free")
    p("    python roundtrip_eval.py --live anthropic:claude-sonnet-5   # needs your key; costs money")
    p("")
    p(f"The recordings, one file per model, card and task set, are in "
      f"[evals/roundtrip/recordings]"
      f"({REPO}/tree/main/evals/roundtrip/recordings), with every reply, the "
      "feedback it got and the tokens it used.")
    return "\n".join(w) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--page", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--live", nargs="+", metavar="SPEC")
    a = ap.parse_args(argv)
    if a.live:
        return live(a.live)
    if a.self_test:
        return self_test()
    if a.record:
        rc = derive(write=True)
        return rc or write_page(check=False)
    if a.page:
        return write_page(check=False)
    rc = derive(write=False)
    return rc or write_page(check=True)


def write_page(check: bool) -> int:
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    text = page(result, datetime.date.today())
    if check:
        current = PAGE.read_text(encoding="utf-8").replace("\r\n", "\n") \
            if PAGE.exists() else ""
        if current != text:
            print("docs/roundtrip.md is not current (python roundtrip_eval.py "
                  "--page); a recording may have become stale")
            return 1
        print("docs/roundtrip.md is current")
        return 0
    PAGE.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote docs/roundtrip.md ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
