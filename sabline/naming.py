"""The names this project answers to, and the ones it still answers to.

Velaris was renamed Sabline in 8.6.0 (CHANGELOG, STABILITY.md). The rename
is additive: everything an operator or a document could have written under
the old name keeps working for one major version, and this module is where
that is decided, so there is one place to look and one place to delete in
9.0.

Three kinds of old name live here:

  the environment        SABLINE_TOKEN is read, and VELARIS_TOKEN is read
                         when the new name is not set. Setting both, with
                         different values, is an error: it is far more
                         likely to be a half-finished migration than a
                         choice, and silently preferring one would hide it.
  the documents          a file Sabline writes says sabline.audit/1; a file
                         it reads may say either. schema_matches() is what
                         every reader asks.
  the files on disk      sabline.toml, sabline.lock and sabline.capabilities
                         are written; the velaris.* spelling of each is read
                         when the new one is not beside it.

What is NOT here: the `velaris` command and the `velaris` import, which are
a console script and a shim package of their own (see sabline/cli.py and
the velaris/ package), and the predicate types, which are names that were
signed rather than names that were typed (sabline/predicates.py).
"""
from __future__ import annotations

import os
from typing import overload

OLD_NAME, NEW_NAME = "velaris", "sabline"
OLD_ENV_PREFIX, NEW_ENV_PREFIX = "VELARIS_", "SABLINE_"

# the release that renamed the project, named in every notice
RENAMED_IN = "8.6.0"


class BothNames(Exception):
    """Both spellings of one name are set, and they disagree."""


def _old(name: str) -> str:
    if not name.startswith(NEW_ENV_PREFIX):
        raise ValueError(f"not a Sabline environment variable: {name}")
    return OLD_ENV_PREFIX + name[len(NEW_ENV_PREFIX):]


@overload
def env(name: str) -> str | None: ...
@overload
def env(name: str, default: str) -> str: ...


def env(name: str, default: str | None = None) -> str | None:
    """`name`, or its VELARIS_ spelling if the SABLINE_ one is not set.

    With a default it answers a str, as os.environ.get(name, default) did,
    so a caller can go on treating the answer as text.

    Both set to the same text is one name written twice, and is fine. Both
    set to different text is a half-migrated environment, and raises: there
    is no answer that is not a guess, and a guess here decides what a run is
    allowed to do (SABLINE_TOKEN) or how long a proof gets."""
    new, old = os.environ.get(name), os.environ.get(_old(name))
    if new is not None and old is not None and new != old:
        raise BothNames(
            f"{name} and {_old(name)} are both set, and differ. "
            f"{_old(name)} is the name before this project was renamed "
            f"Sabline in {RENAMED_IN}; it is still read, but not against "
            f"{name}. Unset one of them.")
    if new is not None:
        return new
    if old is not None:
        return old
    return default


def env_is_set(name: str) -> bool:
    return env(name) is not None


def env_name(name: str) -> str:
    """Which spelling of `name` actually supplied the value - so a message
    about a variable names the one the operator wrote. Telling somebody
    SABLINE_PROOF_TIMEOUT is not a number, when what they set is
    VELARIS_PROOF_TIMEOUT, sends them to look at a variable they never
    set. The new name when neither is set, since that is the one to use."""
    if os.environ.get(name) is not None:
        return name
    if os.environ.get(_old(name)) is not None:
        return _old(name)
    return name


def pop_env(name: str) -> str | None:
    """env(), and both spellings taken out of os.environ - so that a value
    read once here does not reach a child process (doors.py's token)."""
    value = env(name)
    os.environ.pop(name, None)
    os.environ.pop(_old(name), None)
    return value


# ---------------------------------------------------------------------------
# the documents
# ---------------------------------------------------------------------------

def old_schema(schema: str) -> str:
    """The velaris.* spelling of a sabline.* schema name."""
    if schema.startswith(NEW_NAME + "."):
        return OLD_NAME + schema[len(NEW_NAME):]
    return schema


def schema_matches(value: object, schema: str) -> bool:
    """Whether a document's `schema` field is `schema`, under either name.

    Sabline writes sabline.audit/1 and reads both spellings, so an audit,
    a receipt, a capability baseline or a lockfile written by any release
    from 1.x on is still read. Nothing else is accepted: a name this
    function does not know is still refused where it was."""
    return value == schema or value == old_schema(schema)


def schema_names(schema: str) -> tuple[str, ...]:
    """Both spellings, the written one first - for a message that has to
    name what it accepts."""
    return (schema, old_schema(schema))


# ---------------------------------------------------------------------------
# the files on disk
# ---------------------------------------------------------------------------

def old_filename(name: str) -> str:
    """The velaris.* spelling of a sabline.* file name."""
    if name.startswith(NEW_NAME + "."):
        return OLD_NAME + name[len(NEW_NAME):]
    return name


def existing(directory: str, name: str) -> str | None:
    """The path to `name` in `directory`, or to its velaris.* spelling if
    only that one is there. None if neither is. What Sabline writes is
    always `name`; what it reads may be either, so a repository that has
    committed a velaris.capabilities keeps working until it is renamed."""
    new = os.path.join(directory, name)
    if os.path.exists(new):
        return new
    old = os.path.join(directory, old_filename(name))
    if old != new and os.path.exists(old):
        return old
    return None


# ---------------------------------------------------------------------------
# the notices
# ---------------------------------------------------------------------------

_said: set[str] = set()


def say_renamed(old: str, new: str, what: str = "") -> None:
    """One line on stderr, once per process per name, saying that `old` is
    now `new`. Every alias this release keeps - the `velaris` command, the
    `velaris` package, `velaris_mcp` and `velaris_magic` - says it through
    here, so they all say it the same way and one place decides whether
    they say it at all. A deprecation that does not warn is not one
    (STABILITY.md rule 2)."""
    import sys
    if old in _said:
        return
    _said.add(old)
    print(f"note: {what or old} is now `{new}` (this project was renamed "
          f"Sabline in {RENAMED_IN}, because the name Velaris belongs to an "
          f"unrelated company). The old name works until 9.0.",
          file=sys.stderr)
