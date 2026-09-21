"""The `velaris` package, which is now `sabline`.

Velaris was renamed Sabline in 8.6.0, because the name belongs to an
unrelated company in this market (velaris.io). STABILITY.md covers the
library API - `velaris.check`, `velaris.audit`, `velaris.run`,
`velaris.Pool`, `velaris.card`, `velaris.attest` - so removing the name
`velaris` would be a breaking change, and a breaking change ships only in
a major version (rule 1). This package is how 8.6 is not one: it is an
alias, announced now, warning now, and removed no sooner than 9.0
(rule 2).

It is an alias and not a copy. `velaris` *is* the `sabline` module - the
same object, the same classes, the same ERROR_TABLE - so a program that
catches `velaris.VelarisError` catches what `sabline` raises, and one that
does `isinstance(p, velaris.Problem)` gets the same answer. There is no
second implementation to drift.

What to change: `import velaris` becomes `import sabline`, and nothing
else. Every name is where it was.
"""
from __future__ import annotations

import importlib
import sys
import warnings
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from types import ModuleType
from typing import Any, Sequence

import sabline

_OLD, _NEW = "velaris", "sabline"


class _Alias(MetaPathFinder, Loader):
    """Answers for every velaris.* module with the sabline.* module of the
    same name, so a submodule added after 8.6 needs nothing here."""

    def find_spec(self, name: str, path: Sequence[str] | None = None,
                  target: ModuleType | None = None) -> ModuleSpec | None:
        if name != _OLD and not name.startswith(_OLD + "."):
            return None
        return ModuleSpec(name, self, is_package=True)

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        return importlib.import_module(_NEW + spec.name[len(_OLD):])

    def exec_module(self, module: ModuleType) -> None:
        return None


warnings.warn("the `velaris` package is now `sabline`; `import velaris` "
              "works until 9.0", DeprecationWarning, stacklevel=3)
sabline.naming.say_renamed("velaris", "sabline", "the `velaris` package")

if not any(isinstance(f, _Alias) for f in sys.meta_path):
    sys.meta_path.insert(0, _Alias())

# Every module already imported, aliased eagerly, so that `import
# velaris.cli` and `from velaris.budget import Budget` find it in
# sys.modules without reaching the finder at all.
for _name in getattr(sabline, "_MODULES", ()):
    _module: Any = getattr(sabline, _name, None)
    if isinstance(_module, ModuleType):
        sys.modules[f"{_OLD}.{_name}"] = _module

# and `velaris` itself is `sabline`: the same module object, so nothing
# here shadows a name and nothing has to be kept in step.
sys.modules[_OLD] = sabline
