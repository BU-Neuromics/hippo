"""RecipeService - Recipe export, inspection, lineage, and bootstrap import facade.

Service facade following the same pattern as :class:`IngestionService`,
:class:`ProvenanceService`, and :class:`QueryService`. Composed once in
``HippoClient.__init__`` and exposed through thin ``client.recipe_<verb>``
wrappers.

Architecture invariants (sec10 §10.10) that this module preserves:

- (1) :class:`SchemaManager` owns schema merging — this service never
  touches ``SchemaView`` directly to merge.
- (2) All recipe schema writes flow through ``SchemaManager.merge_fragment(...)``.
- (3) Provenance is unconditional; every successful import emits exactly
  one ``recipe_imported`` event in the same transaction.

Phase 2 (PTS-290) implements only :meth:`__init__` and :meth:`list_installed`.
The remaining surface (``inspect``, ``import_``, ``export``, ``extend``,
``diff``, ``export_lockfile``, ``install_from_lockfile``) lands in Phase 3+.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

from hippo.core.meta import get_meta
from hippo.core.recipe import InstalledRecipe, RecipeRef
from hippo.core.storage.adapters.sqlite_adapter import SQLiteAdapter

if TYPE_CHECKING:
    from hippo.core.provenance_service import ProvenanceService
    from hippo.core.schema_manager import SchemaManager


META_KEY_INSTALLED_RECIPES = "installed_recipes"
"""``hippo_meta`` key under which installed-recipe records live.

Mirrors the ``reference_versions`` convention used by the Reference
Loader install/upgrade machinery (sec2 §2.14 step 5). The stored value
is a JSON object keyed by recipe ``id``; each entry conforms to
:class:`InstalledRecipe` (sec10 §10.3.4).
"""


class RecipeService:
    """Recipe export, inspection, lineage, and bootstrap import.

    Delegates schema merging to :class:`SchemaManager` and provenance
    writes to :class:`ProvenanceService`. Reference Loader installs do
    NOT go through this service in v1.
    """

    def __init__(
        self,
        storage: Optional[SQLiteAdapter] = None,
        schema_manager: Optional["SchemaManager"] = None,
        provenance_service: Optional["ProvenanceService"] = None,
        *,
        cache_dir: Optional[Path] = None,
        resolvers: Optional[Sequence[object]] = None,
    ) -> None:
        """Compose the service.

        ``cache_dir`` and ``resolvers`` are accepted now so :class:`HippoClient`'s
        wiring is stable across phases; both go unused in Phase 2 because
        the install pipeline does not exist yet. ``resolvers`` is typed as
        ``object`` for the same reason — the ``RecipeResolver`` interface
        lands in Phase 3.
        """
        self._storage = storage
        self._schema_manager = schema_manager
        self._provenance_service = provenance_service
        self._cache_dir = cache_dir
        self._resolvers = tuple(resolvers) if resolvers else ()

    def list_installed(self) -> list[InstalledRecipe]:
        """Return every entry in ``hippo_meta.installed_recipes``.

        Returns ``[]`` on a clean instance, on adapters with no storage
        backing, or when the ``hippo_meta`` table predates the recipe
        subsystem (the key is simply absent).
        """
        if self._storage is None or not hasattr(self._storage, "_transaction"):
            return []
        with self._storage._transaction() as conn:
            payload = get_meta(conn, META_KEY_INSTALLED_RECIPES)
        if not payload:
            return []
        return [_installed_recipe_from_dict(entry) for entry in payload.values()]


def _installed_recipe_from_dict(entry: dict) -> InstalledRecipe:
    """Hydrate one ``InstalledRecipe`` from its persisted JSON form.

    The persisted shape mirrors ``InstalledRecipe`` exactly (sec10 §10.3.4)
    plus an optional embedded ``parent`` ``RecipeRef``. Missing optional
    fields default per the dataclass.
    """
    parent_data = entry.get("parent")
    parent = None
    if parent_data is not None:
        parent = RecipeRef(
            id=parent_data["id"],
            version=parent_data["version"],
            source=parent_data["source"],
            digest=parent_data.get("digest"),
        )
    return InstalledRecipe(
        id=entry["id"],
        version=entry["version"],
        source=entry["source"],
        digest=entry["digest"],
        installed_at=entry["installed_at"],
        parent=parent,
    )
