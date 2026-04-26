"""hippo.models — generated Pydantic classes by schema namespace.

Populated at ``HippoClient`` construction time when a ``SchemaRegistry``
is present. After construction, classes are importable directly:

    from hippo.models import RootClass          # root-namespace class
    from hippo.models.tissue import Sample      # namespace: tissue
    from hippo.models.assay.quant import Measurement  # namespace: assay.quant

Load-order note: these modules are only available *after*
``HippoClient(registry=...)`` has been constructed. Importing
``hippo.models`` before that point yields an empty module.

Multi-client note: if multiple ``HippoClient`` instances are constructed
with different registries in the same process, the last construction wins
(last-write-wins on ``sys.modules``). Concurrent multi-registry use in
the same process is not supported.
"""

from __future__ import annotations

import sys
import types
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hippo.core.typed_client import Namespace

__all__: list[str] = []

_ROOT_MODULE = "hippo.models"


def _ensure_module(full_name: str) -> types.ModuleType:
    """Return the synthetic module for *full_name*, creating it if needed."""
    if full_name not in sys.modules:
        mod = types.ModuleType(full_name)
        mod.__package__ = full_name
        mod.__spec__ = None
        mod.__all__ = []  # type: ignore[attr-defined]
        sys.modules[full_name] = mod
    return sys.modules[full_name]


def _link_to_parent(full_name: str, child_mod: types.ModuleType) -> None:
    """Set the child module as an attribute on its immediate parent.

    Python's import machinery does this for real subpackages; we must do
    it ourselves for synthetic ones so that attribute traversal
    (``hippo.models.assay.quant``) resolves even without an explicit
    ``import hippo.models.assay.quant``.
    """
    if "." not in full_name:
        return
    parent_name, _, attr = full_name.rpartition(".")
    if parent_name in sys.modules:
        setattr(sys.modules[parent_name], attr, child_mod)


def _walk(ns: "Namespace", module_path: str) -> None:
    """Recursively populate one namespace level and all descendants."""
    mod = _ensure_module(module_path)

    # Place each Pydantic class (keyed by class name, not accessor name)
    # on this module. Skip accessors whose model_class is None.
    new_names: list[str] = []
    for accessor in ns.accessors().values():
        cls = accessor.model_class
        if cls is None:
            continue
        class_name = accessor.class_name
        setattr(mod, class_name, cls)
        new_names.append(class_name)

    # Merge into __all__ without duplicates.
    existing: list[str] = list(getattr(mod, "__all__", []))
    for name in new_names:
        if name not in existing:
            existing.append(name)
    mod.__all__ = existing  # type: ignore[attr-defined]

    # Attach this module to its parent so attribute access works.
    _link_to_parent(module_path, mod)

    # Recurse into sub-namespaces, ensuring intermediate empty modules
    # (e.g. hippo.models.assay when only assay.quant has classes) are
    # registered so import chains resolve correctly.
    for seg_name, sub_ns in ns.subnamespaces().items():
        child_path = f"{module_path}.{seg_name}"
        _walk(sub_ns, child_path)


def populate(typed_root: "Namespace") -> None:
    """Register ``hippo.models.<namespace>`` modules from the typed-client tree.

    Walks the ``Namespace`` tree produced by ``build_typed_surface`` and
    registers each level as a synthetic module in ``sys.modules``.

    - Root-namespace classes land on ``hippo.models`` itself.
    - A class with ``hippo_namespace: tissue`` lands on ``hippo.models.tissue``.
    - A class with ``hippo_namespace: assay.quant`` lands on
      ``hippo.models.assay.quant``; an empty ``hippo.models.assay`` module
      is also registered so the dotted import chain resolves.

    Calling ``populate()`` again (e.g. on ``HippoClient`` re-construction
    with a different registry) overwrites previously registered symbols.
    """
    _walk(typed_root, _ROOT_MODULE)
