"""The rules the Rust crate holds about itself.

    python check_rt.py

`rt/README.md` states them; this is what enforces them, so that a rule in
a document is a rule and not a wish.

1. **No `unsafe`, and a rule for the day there is some.** The workspace
   forbids it, so today the scan finds none. The scan is here anyway,
   because the day a later alpha needs Landlock, seccomp, `sandbox_init`,
   the AppContainer or a C ABI entry point is the day the rule has to
   already exist: every `unsafe` block carries a `// SAFETY:` comment
   saying which invariant makes it sound and naming a test, and that test
   exists. The scan is run against fixtures of its own, so it is known to
   catch each of those rather than only to run.

2. **The minimum Rust version is stated**, in `rt/Cargo.toml`, and
   `rt/README.md` and the MSRV leg of test.yml say the same number.

3. **The supply chain has a committed policy.** `rt/deny.toml` exists and
   holds the four sections `cargo deny check` reads - advisories,
   licenses, bans and sources - and the lockfile is committed.

4. **The dependency count is under the cap** plan/9.0.md argues for: 25
   direct and transitive crates for the default build. It is zero today,
   and the count is read from the committed lockfile rather than from a
   network call.

5. **The fuzzing crate is outside the workspace**, because it needs a
   nightly toolchain and the workspace is what `cargo deny`, `cargo fmt
   --check` and the MSRV leg read.
"""
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RT = ROOT / "rt"
CRATE = RT / "crates" / "sabline-rt"

# plan/9.0.md's risk 4: 25 direct and transitive crates for the default
# build, and a pull request that crosses it argues the crate in writing.
DEPENDENCY_CAP = 25

# An `unsafe` block or function, and the `// SAFETY:` comment that must
# come before it.
UNSAFE = re.compile(r"^\s*(?:pub\s+)?(?:unsafe\s+(?:fn|impl|extern)|unsafe\s*\{)")
SAFETY = re.compile(r"^\s*//\s*SAFETY:\s*(.+)$")
# The comment has to name a test, so that the invariant has something
# holding it rather than a sentence describing it.
NAMES_A_TEST = re.compile(r"\btest[s]?[:\s]+`?([A-Za-z_][A-Za-z0-9_:]*)`?")


def _named(path: Path) -> str:
    """The path as this repository names it, or as it is when it is a
    fixture of the scan's own test."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.name


def rust_files(where: Path) -> list[Path]:
    return sorted(p for p in where.rglob("*.rs") if "target" not in p.parts)


def unsafe_problems(files: list[Path]) -> list[str]:
    """Every `unsafe` without a reason and a test that exists."""
    problems: list[str] = []
    tests = set()
    for path in files:
        for m in re.finditer(r"fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                             path.read_text(encoding="utf-8")):
            tests.add(m.group(1))
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if line.lstrip().startswith("//") or not UNSAFE.match(line):
                continue
            where = f"{_named(path)}:{i + 1}"
            # the whole run of comment lines above it, because the reason
            # and the test it names may not fit on one line
            block: list[str] = []
            for back in range(i - 1, -1, -1):
                if lines[back].lstrip().startswith("//"):
                    block.insert(0, lines[back])
                    continue
                if lines[back].strip():
                    break
            joined = " ".join(line.lstrip().lstrip("/").strip() for line in block)
            said = joined if any(SAFETY.match(line) for line in block) else None
            if said is None:
                problems.append(f"{where}: an unsafe block with no "
                                f"'// SAFETY:' comment saying what makes it "
                                f"sound (rt/README.md)")
                continue
            named = NAMES_A_TEST.search(said)
            if named is None:
                problems.append(f"{where}: its '// SAFETY:' comment names no "
                                f"test, so nothing would fail if the "
                                f"invariant broke (rt/README.md)")
            elif named.group(1).split("::")[-1] not in tests:
                problems.append(f"{where}: its '// SAFETY:' comment names the "
                                f"test {named.group(1)}, which does not exist")
    return problems


FIXTURES: tuple[tuple[str, str, str], ...] = (
    ("no comment at all", '''
fn holder() {
    unsafe {
        let _ = 1;
    }
}
#[test]
fn a_real_test() {}
''', "no '// SAFETY:' comment"),
    ("a comment that names no test", '''
fn holder() {
    // SAFETY: the pointer came from Box::into_raw just above.
    unsafe {
        let _ = 1;
    }
}
#[test]
fn a_real_test() {}
''', "names no test"),
    ("a comment naming a test that is not there", '''
fn holder() {
    // SAFETY: the pointer is non-null; test: a_test_nobody_wrote.
    unsafe {
        let _ = 1;
    }
}
#[test]
fn a_real_test() {}
''', "which does not exist"),
    ("an unsafe fn with no comment", '''
pub unsafe fn reach() {}
#[test]
fn a_real_test() {}
''', "no '// SAFETY:' comment"),
)

GOOD = '''
fn holder() {
    // SAFETY: the pointer came from Box::into_raw and is used once;
    // test: a_real_test.
    unsafe {
        let _ = 1;
    }
}
#[test]
fn a_real_test() {}
'''


def scan_is_known_to_catch() -> list[str]:
    """The scan, run against fixtures, because a scan that has never found
    anything is a scan nobody has tested."""
    problems = []
    with tempfile.TemporaryDirectory(prefix="sabline-rt-scan-") as tmp:
        here = Path(tmp)
        for what, source, expect in FIXTURES:
            path = here / "fixture.rs"
            path.write_text(source, encoding="utf-8", newline="\n")
            told = unsafe_problems([path])
            if not any(expect in line for line in told):
                problems.append(f"the unsafe scan did not catch {what}: "
                                f"{told or 'it found nothing'}")
        path = here / "fixture.rs"
        path.write_text(GOOD, encoding="utf-8", newline="\n")
        told = unsafe_problems([path])
        if told:
            problems.append(f"the unsafe scan refused a block that says what "
                            f"makes it sound and names a test: {told}")
    return problems


def manifest_problems() -> list[str]:
    problems = []
    workspace = (RT / "Cargo.toml").read_text(encoding="utf-8")
    crate = (CRATE / "Cargo.toml").read_text(encoding="utf-8")
    readme = (RT / "README.md").read_text(encoding="utf-8")

    if 'unsafe_code = "forbid"' not in workspace:
        problems.append('rt/Cargo.toml: the workspace must set '
                        'unsafe_code = "forbid" (rt/README.md)')
    if 'unsafe_op_in_unsafe_fn = "deny"' not in workspace:
        problems.append('rt/Cargo.toml: the workspace must deny '
                        'unsafe_op_in_unsafe_fn (rt/README.md)')
    if "[lints]\nworkspace = true" not in crate:
        problems.append("rt/crates/sabline-rt/Cargo.toml: the crate must take "
                        "the workspace's lints, or forbidding unsafe there "
                        "does nothing here")

    msrv = re.search(r'^rust-version = "([0-9.]+)"', workspace, re.M)
    if msrv is None:
        problems.append("rt/Cargo.toml: the workspace must state "
                        "rust-version, which is the minimum Rust version")
    else:
        said = msrv.group(1)
        if f"**{said}**" not in readme and f" {said}" not in readme:
            problems.append(f"rt/README.md does not say the minimum Rust "
                            f"version is {said}")
        workflow = (ROOT / ".github" / "workflows" / "test.yml").read_text(
            encoding="utf-8")
        if said not in workflow:
            problems.append(f"the MSRV leg of test.yml is not pinned to "
                            f"{said}, which is what rt/Cargo.toml states")

    if 'exclude = ["crates/sabline-rt/fuzz"]' not in workspace:
        problems.append("rt/Cargo.toml: the fuzzing crate must be excluded "
                        "from the workspace (rt/README.md)")
    return problems


def supply_chain_problems() -> list[str]:
    problems = []
    deny = RT / "deny.toml"
    if not deny.exists():
        return ["rt/deny.toml is not committed, so `cargo deny check` would "
                "decide by its own defaults (plan/9.0.md, risk 4)"]
    text = deny.read_text(encoding="utf-8")
    for section in ("[advisories]", "[licenses]", "[bans]", "[sources]"):
        if section not in text:
            problems.append(f"rt/deny.toml has no {section} section, so "
                            f"`cargo deny check` decides that one by its "
                            f"defaults")
    if 'unknown-git = "deny"' not in text:
        problems.append("rt/deny.toml must refuse a git dependency: it is a "
                        "dependency on whatever that branch says today")
    if 'allow-registry = ["https://github.com/rust-lang/crates.io-index"]' not in text:
        problems.append("rt/deny.toml must allow crates.io and no other "
                        "registry")

    lock = RT / "Cargo.lock"
    if not lock.exists():
        return problems + ["rt/Cargo.lock is not committed, and the release "
                           "builds from it (plan/9.0.md, risk 4)"]
    packages = re.findall(r"^name = \"(.+)\"$", lock.read_text(encoding="utf-8"),
                          re.M)
    outside = [p for p in packages if p != "sabline-rt"]
    if len(outside) > DEPENDENCY_CAP:
        problems.append(
            f"the default build has {len(outside)} crates in it and the cap "
            f"is {DEPENDENCY_CAP} (plan/9.0.md, risk 4). A pull request that "
            f"crosses it says what the crate does, what it would take to "
            f"write that here, and why not")
    return problems


def main(argv: Any) -> int:
    problems: list[str] = []

    print("the unsafe rule")
    files = rust_files(CRATE)
    told = unsafe_problems(files)
    problems += told
    if not told:
        print(f"  {len(files)} files, no unsafe without a reason and a test")
    told = scan_is_known_to_catch()
    problems += told
    if not told:
        print(f"  the scan catches each of {len(FIXTURES)} fixtures, and "
              f"passes a block that says what makes it sound")

    print("the manifests")
    told = manifest_problems()
    problems += told
    if not told:
        print("  unsafe forbidden, the minimum Rust version stated and "
              "pinned, the fuzzing crate outside the workspace")

    print("the supply chain")
    told = supply_chain_problems()
    problems += told
    if not told:
        lock = (RT / "Cargo.lock").read_text(encoding="utf-8")
        count = len(re.findall(r"^name = \"", lock, re.M)) - 1
        print(f"  deny.toml holds all four sections; {count} crates in the "
              f"default build, the cap is {DEPENDENCY_CAP}")

    if problems:
        print()
        for line in problems:
            print(f"FAILED {line}")
        return 1
    print("\nthe crate holds its own rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
