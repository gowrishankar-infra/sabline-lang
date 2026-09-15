import json

import pytest

pytest.importorskip("velaris")
from langchain_velaris import VelarisAuditTool, VelarisRunTool  # noqa

READS_A_FILE = """
fn peek(path: Text) -> Text uses fs or fail {
    return try read_file(path)
}

fn main() uses io, fs {
    print("start")
    check peek("x.txt") {
        ok body {
            print("READ IT")
        }
        fail why {
            print("failed")
        }
    }
}
"""


def test_audit_names_effects() -> None:
    report = json.loads(VelarisAuditTool().invoke({"source": READS_A_FILE}))
    assert report["effects"] == ["fs", "io"]
    assert report["schema"] == "velaris.audit/1"


def test_run_refuses_outside_the_budget() -> None:
    out = VelarisRunTool(allow=["io"]).invoke({"source": READS_A_FILE})
    assert "REFUSED" in out and "READ IT" not in out


def test_run_works_inside_the_budget() -> None:
    out = VelarisRunTool(allow=["io"]).invoke(
        {"source": "fn main() uses io {\n    print(6 * 7)\n}\n"})
    assert out.strip() == "42"
