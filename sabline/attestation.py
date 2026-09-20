"""sabline attest: the audit as an in-toto Statement, bound to the bytes it
describes.
"""
import json
import os
import sys

from . import state as _state
from .version import _INSTALL_DIR
from .predicates import CAPABILITY_PREDICATE_TYPE as CAPABILITY_PREDICATE_TYPE
from .tables import CHECK_MEMORY_MB_DEFAULT, CHECK_TIMEOUT_DEFAULT
from .loader import load_program
from .library import _audit_here, _ceiling_args
from .pool import Pool
from .findings import REPOSITORY
from .ratchet import _capability_files
from typing import Any

# ---------------------------------------------------------------------------
# 19. ATTESTATION - the audit, bound to the bytes it describes
#
#     `sabline attest` wraps sabline.audit/1 in an in-toto Statement v1 of
#     the predicate type sabline-spec 8.5 defines: the audited file and
#     every file it loads are the subjects, by sha256, and the predicate's
#     audit is audit()'s own output - not a copy recomputed here - so the
#     attestation and the audit cannot disagree, and the attestation says
#     nothing the audit does not. What the audit could not determine it
#     says so in its own fields (ffi_any, read_any, any, a null count, ok
#     false), and the Statement carries them as they are. Nothing here
#     signs: EMBEDDING.md shows how, with cosign or sigstore-python, and
#     the release workflow does it for one example program.
# ---------------------------------------------------------------------------


INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
# the type is sabline/predicates.py's: at sabline.dev from 8.3, and the
# version of sabline-spec that names it there
CAPABILITY_SPEC = "sabline-spec 0.13.0"


def _attested_at() -> str:
    """When the audit was made, RFC 3339 in UTC to the second - from
    SOURCE_DATE_EPOCH when it is set, so a build that fixes that gets the
    same Statement twice."""
    import datetime
    epoch = os.environ.get("SOURCE_DATE_EPOCH", "")
    when = (datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc)
            if epoch.isdigit() else
            datetime.datetime.now(datetime.timezone.utc))
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_of(path: str) -> str:
    import hashlib
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _subject_name(path: str, entry: str, entry_name: str) -> str:
    """How a Statement names a file the audited program loads: in the
    terms the audited file was named in, or <stdlib>/NAME for the
    standard library this Sabline ships, whose place on disk is this
    machine's business."""
    import posixpath
    full = os.path.abspath(path)
    base = os.path.dirname(os.path.abspath(entry))
    std = os.path.join(_INSTALL_DIR, "stdlib")
    try:
        rel = os.path.relpath(full, base).replace(os.sep, "/")
    except ValueError:                     # another drive, on Windows
        rel = None
    if rel is not None and rel != ".." and not rel.startswith("../"):
        return posixpath.normpath(posixpath.join(
            posixpath.dirname(entry_name), rel))
    if full.startswith(std + os.sep):
        return "<stdlib>/" + os.path.relpath(full, std).replace(os.sep, "/")
    if rel is not None:
        return posixpath.normpath(posixpath.join(
            posixpath.dirname(entry_name), rel))
    return full.replace(os.sep, "/")


def attest_statement(path: str, name: str | None = None, *,
                     auditor: Any = None) -> dict[str, Any]:
    """The in-toto Statement for one .vel file (sabline-spec 8.5): the
    file first among the subjects, then each file it imports, each by
    the sha256 of its bytes; the predicate, audit() of those bytes.
    ValueError when the file is not UTF-8, or changed while it was being
    attested. `auditor` is what audits the source - a pool's, under a
    ceiling, from attest(); this process's with no ceiling otherwise."""
    import hashlib
    import posixpath
    name = name or posixpath.normpath(path.replace(os.sep, "/"))
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"{path} is not UTF-8 text")
    entry_digest = hashlib.sha256(raw).hexdigest()

    def imports() -> list[Any]:
        read: list[Any] = []
        try:
            load_program(path, source, loaded=read)
        except Exception:          # the audit reports why; what could be
            pass                   # read is still what it read
        out, seen = [], {os.path.abspath(path)}
        for p in read:
            if os.path.abspath(p) not in seen:
                seen.add(os.path.abspath(p))
                out.append((p, _sha256_of(p)))
        return out

    before = imports()
    doc = (auditor or _audit_here)(source, path=path).as_dict()
    # the audit read the imported files from disk; if one changed while it
    # did, a digest would name bytes the audit may not have read
    if imports() != before or _sha256_of(path) != entry_digest:
        raise ValueError(f"{path}, or a file it imports, changed while it "
                         f"was being attested; attest it again")
    subjects = [{"name": name, "digest": {"sha256": entry_digest}}]
    subjects += [{"name": _subject_name(p, path, name),
                  "digest": {"sha256": d}} for p, d in before]
    return {"_type": INTOTO_STATEMENT_TYPE,
            "subject": subjects,
            "predicateType": CAPABILITY_PREDICATE_TYPE,
            "predicate": {"producer": {"name": "sabline-lang",
                                       "uri": REPOSITORY},
                          "specification": CAPABILITY_SPEC,
                          "auditedAt": _attested_at(),
                          "audit": doc}}


def attest(path: str, *, timeout: Any = CHECK_TIMEOUT_DEFAULT,
           max_memory_mb: Any = CHECK_MEMORY_MB_DEFAULT) -> list[Any]:
    """One in-toto Statement per .vel file: the file itself, or every
    .vel file under a directory, as `sabline capabilities` finds them
    (.git and what git ignores left out). ValueError when there is
    nothing to attest.

    From 8.1 each audit runs under the ceiling audit() has - one worker
    for the whole call - and a file whose audit passes it is attested
    with `ok: false` and E613 or E614, which says nothing was determined.
    None for both audits in this process, as before."""
    _ceiling_args(timeout, max_memory_mb)
    if (timeout is not None or max_memory_mb is not None) and not _state._IN_CHILD:
        with Pool(size=1, timeout=timeout,
                  max_memory_mb=max_memory_mb) as pool:
            return _attest(path, pool.audit)
    return _attest(path, None)


def _attest(path: str, auditor: Any) -> list[Any]:
    import posixpath
    if os.path.isdir(path):
        base = posixpath.normpath(path.replace(os.sep, "/"))
        files = _capability_files(path)
        if not files:
            raise ValueError(f"no .vel file under {path}")
        return [attest_statement(os.path.join(path, *rel.split("/")),
                                 rel if base == "." else f"{base}/{rel}",
                                 auditor=auditor)
                for rel in files]
    if not os.path.isfile(path):
        raise ValueError(f"{path}: no such file or directory")
    return [attest_statement(path, auditor=auditor)]


def attest_main(argv: list[Any]) -> int:
    """sabline attest <path> [--output FILE] [--json]"""
    usage = "usage: sabline attest <path> [--output FILE] [--json]"
    places, output, as_json = [], None, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--output" and i + 1 < len(argv):
            output = argv[i + 1]
            i += 2
            continue
        if a == "--json":
            as_json = True
        elif a.startswith("-"):
            print(usage, file=sys.stderr)
            return 2
        else:
            places.append(a)
        i += 1
    if len(places) != 1:
        print(usage, file=sys.stderr)
        return 2
    target = places[0]
    try:
        statements = attest(target)
    except (ValueError, OSError) as e:
        print(f"sabline attest: {e}", file=sys.stderr)
        return 2
    # a file gives one Statement; a directory gives one per file, one to a
    # line (JSON Lines; an in-toto Bundle is the same, of signed envelopes)
    if os.path.isdir(target):
        text = "".join(json.dumps(s, ensure_ascii=False,
                                  separators=(",", ":")) + "\n"
                       for s in statements)
    else:
        text = json.dumps(statements[0], indent=2, ensure_ascii=False) + "\n"
    if output:
        with open(output, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    if as_json:
        sys.stdout.write(text)
        return 0
    print(f"sabline attest: {len(statements)} in-toto Statement(s) of "
          f"{CAPABILITY_PREDICATE_TYPE}")
    for s in statements:
        a = s["predicate"]["audit"]
        first = s["subject"][0]
        state = ("compiles" if a["ok"] else
                 "does not compile: " + ", ".join(
                     sorted({p["code"] for p in a["problems"]})))
        print(f"  {first['name']}  sha256:{first['digest']['sha256'][:16]}"
              f"  {state}")
        print(f"      effects: {', '.join(a['effects']) or 'none'}"
              + ("; a module named while running (ffi_any)"
                 if a.get("ffi_any") else ""))
        for extra in s["subject"][1:]:
            print(f"      also read: {extra['name']}  "
                  f"sha256:{extra['digest']['sha256'][:16]}")
    print(f"written to {output}" if output else
          "not written: pass --output FILE, or --json to print it")
    return 0
