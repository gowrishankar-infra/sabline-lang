"""Reading the in-toto Statements Velaris writes - attestations and receipts -
and holding one to the bytes it names: `velaris verify` (8.3).
"""
import hashlib
import json
import os
import re
import stat
import sys

from .version import _INSTALL_DIR
from .values import log_line
from .predicates import (CAPABILITY_PREDICATE_TYPE, RECEIPT_PREDICATE_TYPE,
                         predicate_kind)
from .attestation import INTOTO_STATEMENT_TYPE
from .recorder import RECEIPT_SCHEMA
from .mcp_manifest import OIDC_ISSUER
from typing import Any

# ---------------------------------------------------------------------------
# 19c. STATEMENTS - what a reader of an attestation or a receipt checks
#
#     `velaris verify FILE` reads a Statement Velaris wrote, as it is, in a
#     DSSE envelope, or in a Sigstore bundle, and says three things: whether
#     its predicate type is one Velaris defines (capability/v1 or receipt/v1,
#     at velaris-lang.dev or where 8.2.1 and earlier named them - nothing
#     else), whether its predicate has the shape that type requires, and
#     whether each subject is the bytes on this disk. A signature in a bundle
#     is checked against the identity the caller names. What it does not say
#     is what the Statement means: that is the attestation's or the
#     receipt's own limit, in THREAT_MODEL.md.
#
#     A Statement is text from someone else. It is parsed with duplicate keys
#     refused, so two readers cannot see two different predicate types in
#     one file; a subject's name is read only when it stays inside the
#     directory it is read from, and only as a regular file.
# ---------------------------------------------------------------------------


VERIFY_SCHEMA = "velaris.verify/1"          # provisional (STABILITY.md)
DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"
STATEMENT_MAX_BYTES = 16 * 1024 * 1024
SUBJECT_MAX_BYTES = 64 * 1024 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}")


class StatementError(ValueError):
    """A file that holds no Statement this module can read, and why."""


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    seen: dict[str, Any] = {}
    for key, value in pairs:
        if key in seen:
            raise StatementError(f"the key {key!r} appears twice in one "
                                 f"object, so what it says is not one thing")
        seen[key] = value
    return seen


def _not_a_number(text: str) -> Any:
    raise StatementError(f"{text} is not a JSON number")


def parse_json(text: str) -> Any:
    """json.loads, refusing a key given twice in one object and NaN or
    Infinity, which JSON does not have."""
    return json.loads(text, object_pairs_hook=_no_duplicates,
                      parse_constant=_not_a_number)


def _envelope_statement(envelope: Any) -> dict[str, Any]:
    import base64
    import binascii
    if not isinstance(envelope, dict) \
            or not isinstance(envelope.get("payload"), str):
        raise StatementError("a DSSE envelope with no payload")
    if envelope.get("payloadType") != DSSE_PAYLOAD_TYPE:
        raise StatementError(
            f"a DSSE envelope whose payloadType is "
            f"{envelope.get('payloadType')!r}, not {DSSE_PAYLOAD_TYPE}")
    try:
        payload = base64.b64decode(envelope["payload"], validate=True)
        doc = parse_json(payload.decode("utf-8"))
    except (binascii.Error, ValueError, UnicodeDecodeError) as e:
        raise StatementError(f"a DSSE envelope whose payload is not a JSON "
                             f"Statement ({e})")
    if not isinstance(doc, dict):
        raise StatementError("a DSSE envelope whose payload is not an object")
    return doc


def unwrap(doc: Any) -> tuple[dict[str, Any], str]:
    """(the Statement, what carried it): 'statement', 'dsse envelope' or
    'sigstore bundle'. StatementError for anything else."""
    if isinstance(doc, dict) and "_type" in doc:
        return doc, "statement"
    if isinstance(doc, dict) and "dsseEnvelope" in doc:
        return _envelope_statement(doc["dsseEnvelope"]), "sigstore bundle"
    if isinstance(doc, dict) and "payloadType" in doc:
        return _envelope_statement(doc), "dsse envelope"
    raise StatementError("not an in-toto Statement, a DSSE envelope or a "
                         "Sigstore bundle")


def read_statements(path: str) -> list[tuple[dict[str, Any], str, Any]]:
    """Every Statement in a file - one JSON document, or JSON Lines of them
    as `velaris attest DIR` writes - each as (Statement, carrier, the
    document as read). StatementError when the file cannot be read as one."""
    try:
        info = os.stat(path)
    except OSError as e:
        raise StatementError(f"{path}: {e.strerror or e}")
    if not stat.S_ISREG(info.st_mode):
        raise StatementError(f"{path} is not a regular file")
    if info.st_size > STATEMENT_MAX_BYTES:
        raise StatementError(f"{path} is larger than 16 MiB")
    with open(path, "rb") as fh:
        raw = fh.read(STATEMENT_MAX_BYTES + 1)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise StatementError(f"{path} is not UTF-8 text")
    docs: list[Any] = []
    try:
        docs = [parse_json(text)]
    except StatementError:
        raise
    except ValueError:
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                docs.append(parse_json(line))
            except StatementError as e:
                raise StatementError(f"{path}: line {n}: {e}")
            except ValueError:
                raise StatementError(f"{path}: line {n} is not JSON")
    if not docs:
        raise StatementError(f"{path} holds no Statement")
    out = []
    for doc in docs:
        statement, carrier = unwrap(doc)
        out.append((statement, carrier, doc))
    return out


def statement_problems(statement: dict[str, Any]) -> tuple[str | None, list[str]]:
    """(the kind of Statement - 'capability', 'receipt' or None - and what
    is wrong with it). A predicate type Velaris does not define is a
    problem, whatever else the Statement holds."""
    problems: list[str] = []
    if statement.get("_type") != INTOTO_STATEMENT_TYPE:
        problems.append(f"_type is {statement.get('_type')!r}, not "
                        f"{INTOTO_STATEMENT_TYPE}")
    kind = predicate_kind(statement.get("predicateType"))
    if kind is None:
        problems.append(
            f"the predicate type {statement.get('predicateType')!r} is not "
            f"one Velaris defines: {CAPABILITY_PREDICATE_TYPE} and "
            f"{RECEIPT_PREDICATE_TYPE}, or either as Velaris 8.2.1 and "
            f"earlier named it")
    subjects = statement.get("subject")
    if not isinstance(subjects, list) or not subjects:
        problems.append("it names no subject")
    else:
        for i, subject in enumerate(subjects):
            digest = subject.get("digest") if isinstance(subject, dict) \
                else None
            if not (isinstance(subject, dict)
                    and isinstance(subject.get("name"), str)
                    and isinstance(digest, dict)
                    and isinstance(digest.get("sha256"), str)
                    and _SHA256.fullmatch(digest["sha256"])):
                problems.append(f"subject {i} has no name and lower-case "
                                f"sha256 digest")
    predicate = statement.get("predicate")
    if not isinstance(predicate, dict):
        problems.append("it holds no predicate")
    elif kind == "capability":
        audit = predicate.get("audit")
        if not (isinstance(audit, dict)
                and audit.get("schema") == "velaris.audit/1"):
            problems.append("its predicate holds no velaris.audit/1 document")
        producer = predicate.get("producer")
        if not (isinstance(producer, dict)
                and isinstance(producer.get("name"), str)):
            problems.append("its predicate names no producer")
    elif kind == "receipt":
        problems += receipt_shape_problems(predicate)
    return kind, problems


def receipt_shape_problems(predicate: dict[str, Any]) -> list[str]:
    """What a velaris.receipt/1 document lacks that section 8.7 requires,
    and what it holds of the wrong type - a count that is not a whole
    number of at least zero among them."""
    out: list[str] = []
    if predicate.get("schema") != RECEIPT_SCHEMA:
        out.append(f"its predicate is not {RECEIPT_SCHEMA}")
    if not isinstance(predicate.get("budget"), str):
        out.append("its predicate has no budget")
    if not isinstance(predicate.get("complete"), bool):
        out.append("its predicate does not say whether it is complete")
    used = predicate.get("effects_used")
    if used is not None and not (
            isinstance(used, dict) and all(
                isinstance(k, str) and _count(v) for k, v in used.items())):
        out.append("its effects_used is not a count per effect")
    for field, keys in (("refusals", ("code", "effect", "line", "times")),
                        ("declassifications", ("reason", "line", "times"))):
        rows = predicate.get(field)
        if not isinstance(rows, list) or not all(
                isinstance(r, dict) and all(k in r for k in keys)
                and _count(r.get("times")) for r in rows):
            out.append(f"its {field} are not a list of {', '.join(keys)}")
    exit_ = predicate.get("exit")
    if not (isinstance(exit_, dict) and isinstance(exit_.get("outcome"), str)):
        out.append("its predicate has no exit outcome")
    parameters = predicate.get("run_parameters")
    if not isinstance(parameters, dict):
        out.append("its predicate has no run_parameters")
    return out


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) \
        and value >= 0


def subject_file(name: str, root: str) -> tuple[str | None, str]:
    """(the file a subject names, '') or (None, why it is not read). A name
    is read inside `root`, or inside this Velaris's standard library for
    <stdlib>/NAME; one that is absolute, or that leaves that directory -
    through '..' or a link - is not read at all."""
    import posixpath
    if name == "<source>":
        return None, "a program given as text, with no file"
    if name.startswith("<stdlib>/"):
        rest, base = name[len("<stdlib>/"):], os.path.join(_INSTALL_DIR,
                                                           "stdlib")
    else:
        rest, base = name, root
    if (rest.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", rest)
            or "\\" in rest or "\x00" in rest):
        return None, "an absolute name, which verify does not read"
    norm = posixpath.normpath(rest)
    if norm in (".", "..") or norm.startswith("../"):
        return None, "a name that leaves the directory it is read from"
    base_real = os.path.realpath(base)
    full = os.path.realpath(os.path.join(base_real, *norm.split("/")))
    try:
        inside = os.path.commonpath([full, base_real]) == base_real
    except ValueError:                     # another drive, on Windows
        inside = False
    if not inside:
        return None, "a name that resolves outside the directory it is " \
                     "read from"
    return full, ""


def file_sha256(path: str) -> tuple[str | None, str]:
    """(sha256, '') of a regular file of at most 64 MiB, or (None, why)."""
    try:
        info = os.stat(path)
    except OSError:
        return None, "no such file"
    if not stat.S_ISREG(info.st_mode):
        return None, "not a regular file"
    if info.st_size > SUBJECT_MAX_BYTES:
        return None, "larger than 64 MiB"
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as e:
        return None, e.strerror or str(e)
    return digest.hexdigest(), ""


def check_subjects(statement: dict[str, Any], root: str) -> list[dict[str, Any]]:
    """One row per subject: name, expected, found, and status 'ok',
    'differs' or 'not checked' with why."""
    rows = []
    for subject in statement.get("subject") or []:
        if not isinstance(subject, dict):
            continue
        name = subject.get("name")
        expected = (subject.get("digest") or {}).get("sha256") \
            if isinstance(subject.get("digest"), dict) else None
        if not isinstance(name, str):
            continue
        where, why = subject_file(name, root)
        found = None
        if where is not None:
            found, why = file_sha256(where)
        status = ("not checked" if found is None else
                  "ok" if found == expected else "differs")
        rows.append({"name": name, "expected": expected, "found": found,
                     "status": status, "why": why})
    return rows


def verify_bundle(document: Any, statement: dict[str, Any], identity: str,
                  issuer: str) -> str | None:
    """None when the Sigstore bundle's DSSE signature verifies as
    `identity` from `issuer` over exactly this Statement; else why not."""
    try:
        from sigstore.models import Bundle
        from sigstore.verify import Verifier
        from sigstore.verify.policy import Identity
    except ImportError:
        return ("the sigstore package is not installed, so the signature "
                "cannot be checked: pip install sigstore - or check it with "
                "cosign verify-blob-attestation and pass --skip-signature")
    try:
        bundle = Bundle.from_json(json.dumps(document))
        payload_type, payload = Verifier.production().verify_dsse(
            bundle, Identity(identity=identity, issuer=issuer))
    except Exception as e:
        return f"the signature does not verify: {type(e).__name__}: {e}"
    try:
        signed = parse_json(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "the signed payload is not a JSON Statement"
    if payload_type != DSSE_PAYLOAD_TYPE or signed != statement:
        return "the signature is over something other than this Statement"
    return None


def verify_file(path: str, *, root: str, identity: str | None = None,
                issuer: str = OIDC_ISSUER,
                skip_signature: bool = False) -> dict[str, Any]:
    """The velaris.verify/1 report of one file, and its exit status: 0 when
    every Statement in it is verified, 1 when one is refused or names
    bytes that differ, 2 when one could not be checked."""
    report: dict[str, Any] = {"schema": VERIFY_SCHEMA, "file": path,
                              "statements": [], "problems": []}
    try:
        found = read_statements(path)
    except StatementError as e:
        report["problems"].append(str(e))
        report["exit"] = 2
        return report
    for statement, carrier, document in found:
        kind, problems = statement_problems(statement)
        rows = check_subjects(statement, root) if not any(
            p.startswith(("it names no subject", "subject ")) for p in
            problems) else []
        signature: dict[str, Any] = {"carried": carrier != "statement",
                                     "checked": False, "verified": None,
                                     "identity": None, "why": ""}
        unchecked = []
        if carrier == "sigstore bundle" and not skip_signature:
            if identity is None:
                unchecked.append("the file is signed; name --identity (and "
                                 "--issuer) to check the signature, or pass "
                                 "--skip-signature")
            else:
                why = verify_bundle(document, statement, identity, issuer)
                signature.update(checked=why is None or "does not verify"
                                 in why or "something other" in why,
                                 verified=why is None, identity=identity,
                                 why=why or "")
                if why is not None:
                    if signature["checked"]:
                        problems.append(why)
                    else:
                        unchecked.append(why)
        elif carrier == "dsse envelope" and not skip_signature:
            unchecked.append("a DSSE envelope outside a Sigstore bundle: "
                             "check its signature with the key that made it "
                             "(cosign verify-blob-attestation --key), then "
                             "pass --skip-signature")
        unchecked += [f"{r['name']}: {r['why']}" for r in rows
                      if r["status"] == "not checked"]
        differs = [r for r in rows if r["status"] == "differs"]
        verdict = ("refused" if problems or differs else
                   "not checked" if unchecked else "verified")
        report["statements"].append({
            "predicateType": statement.get("predicateType"), "kind": kind,
            "earlier_spelling": kind is not None and statement.get(
                "predicateType") not in (CAPABILITY_PREDICATE_TYPE,
                                         RECEIPT_PREDICATE_TYPE),
            "carrier": carrier, "signature": signature, "subjects": rows,
            "problems": problems, "not_checked": unchecked,
            "verdict": verdict})
    verdicts = {s["verdict"] for s in report["statements"]}
    report["exit"] = (1 if "refused" in verdicts else
                      2 if "not checked" in verdicts else 0)
    return report


def verify_main(argv: list[Any]) -> int:
    """velaris verify STATEMENT [--root DIR] [--identity ID] [--issuer URL]
    [--skip-signature] [--json]"""
    usage = ("usage: velaris verify <statement> [--root DIR] [--identity ID] "
             "[--issuer URL] [--skip-signature] [--json]")
    files: list[str] = []
    root, identity, issuer = ".", None, OIDC_ISSUER
    skip = as_json = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--root", "--identity", "--issuer"):
            if i + 1 >= len(argv):
                print(f"velaris verify: {a} needs a value", file=sys.stderr)
                return 2
            if a == "--root":
                root = argv[i + 1]
            elif a == "--identity":
                identity = argv[i + 1]
            else:
                issuer = argv[i + 1]
            i += 2
            continue
        if a == "--skip-signature":
            skip = True
        elif a == "--json":
            as_json = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            files.append(a)
        i += 1
    if len(files) != 1:
        print(usage, file=sys.stderr)
        return 2
    report = verify_file(files[0], root=root, identity=identity,
                         issuer=issuer, skip_signature=skip)
    if as_json:
        print(json.dumps(report, indent=2))
        return int(report["exit"])
    def say(text: str) -> None:
        # a Statement is someone else's text: a name or a type holding a
        # line feed or an escape must not forge a line of this report
        print(log_line(text))

    say(f"file:      {files[0]}")
    for p in report["problems"]:
        say(f"  NOT READ  {p}")
    for s in report["statements"]:
        kind = s["kind"]
        say(f"type:      {s['predicateType']!s}"
              + (f" ({kind}/v1" + (", as Velaris 8.2.1 and earlier named it"
                                   if s["earlier_spelling"] else "") + ")"
                 if kind else " (REFUSED: not a type Velaris defines)"))
        sig = s["signature"]
        if not sig["carried"]:
            say("signature: none in this file - an unsigned Statement is a "
                  "claim anyone could write")
        elif sig["verified"]:
            say(f"signature: verified, signed by {sig['identity']}")
        elif skip:
            say("signature: NOT CHECKED (--skip-signature)")
        for r in s["subjects"]:
            short = (r["expected"] or "")[:16]
            if r["status"] == "ok":
                say(f"  ok       {r['name']}  sha256:{short}")
            elif r["status"] == "differs":
                say(f"  DIFFERS  {r['name']}  the Statement names "
                      f"sha256:{short}, the file is sha256:"
                      f"{(r['found'] or '')[:16]}")
            else:
                say(f"  NOT READ {r['name']}  {r['why']}")
        for p in s["problems"]:
            say(f"  REFUSED  {p}")
        for p in s["not_checked"]:
            if not any(p == f"{r['name']}: {r['why']}" for r in s["subjects"]):
                say(f"  NOT CHECKED  {p}")
        say({"verified": "verified: a type Velaris defines, and every "
                           "subject is these bytes",
               "refused": "refused",
               "not checked": "not checked: see above"}[s["verdict"]])
    return int(report["exit"])
