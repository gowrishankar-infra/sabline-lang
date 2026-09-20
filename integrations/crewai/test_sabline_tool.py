"""The tools must keep Sabline's guarantee: a budget is enforced."""
import json

import pytest

pytest.importorskip("sabline")
from sabline_tool import SablineAuditTool, SablineRunTool  # noqa: E402

READS_A_FILE = """
fn peek(path: Text) -> Text uses fs or fail {
    return try read_file(path)
}

fn main() uses io, fs {
    print("start")
    check peek("sabline.py") {
        ok body {
            print("READ IT")
        }
        fail why {
            print("failed")
        }
    }
}
"""

PURE = """
fn main() uses io {
    print(6 * 7)
}
"""


def test_audit_names_every_effect() -> None:
    report = json.loads(SablineAuditTool()._run(READS_A_FILE))
    assert report["schema"] == "sabline.audit/1"
    assert report["effects"] == ["fs", "io"]


def test_run_refuses_an_effect_outside_the_budget() -> None:
    out = SablineRunTool(allow=["io"])._run(READS_A_FILE)
    assert "REFUSED" in out and "'fs'" in out
    assert "READ IT" not in out
    # a refusal is not a failure the program can catch: the fail branch
    # must not run either
    assert "failed" not in out


FOREVER = """
fn main() uses io {
    let i = 0
    while i >= 0 {
        i = i + 1
        if i > 1000000 {
            i = 0
        }
    }
    print("REACHED THE END")
}
"""


def test_run_stops_a_program_that_never_ends() -> None:
    # the marker must not collide with sabline's own E610 fix hint,
    # which says "fix the loop that never ends"
    out = SablineRunTool(allow=["io"], timeout=2)._run(FOREVER)
    assert "STOPPED" in out and "REACHED THE END" not in out


def test_the_default_limits_are_set() -> None:
    tool = SablineRunTool()
    assert tool.timeout == 30.0 and tool.max_memory_mb == 512


def test_run_permits_what_the_budget_allows() -> None:
    out = SablineRunTool(allow=["io", "fs"])._run(READS_A_FILE)
    assert "READ IT" in out


def test_run_returns_output() -> None:
    assert SablineRunTool(allow=["io"])._run(PURE).strip() == "42"


def test_the_default_budget_is_io_only() -> None:
    assert SablineRunTool().allow == ["io"]
