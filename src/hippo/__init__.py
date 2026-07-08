"""Deprecated alias: the ``hippo`` package is now ``mosaic`` (ADR-0004).

This shim keeps ``import hippo`` and ``import hippo.<submodule>`` working
during the deprecation window. Submodule imports resolve to the *same*
module objects as their ``mosaic`` counterparts (a meta-path finder aliases
``hippo.*`` onto ``mosaic.*``), so ``isinstance``/``issubclass`` checks and
module identity hold across both spellings.
"""

import importlib
import importlib.abc
import importlib.util
import sys
import warnings

warnings.warn(
    "'hippo' has been renamed to 'mosaic' (ADR-0004); the 'hippo' alias will "
    "be removed in a future release. Use 'import mosaic'.",
    DeprecationWarning,
    stacklevel=2,
)

_mosaic = importlib.import_module("mosaic")


class _AliasLoader(importlib.abc.Loader):
    def __init__(self, target):
        self._target = target

    def create_module(self, spec):
        mod = importlib.import_module(self._target)
        sys.modules[spec.name] = mod
        return mod

    def exec_module(self, module):
        pass


class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("hippo."):
            return importlib.util.spec_from_loader(
                fullname, _AliasLoader("mosaic" + fullname[5:])
            )
        return None


sys.meta_path.append(_AliasFinder())


def __getattr__(name):  # hippo.HippoClient, hippo.__version__, ...
    return getattr(_mosaic, name)


def __dir__():
    return sorted(set(globals()) | set(dir(_mosaic)))
