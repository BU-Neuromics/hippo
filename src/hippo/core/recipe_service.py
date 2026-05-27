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

Phase 2 (PTS-290) shipped :meth:`__init__` + :meth:`list_installed`.
Phase 3 PR 5 (PTS-291) adds :meth:`inspect`. The remaining surface
(``import_``, ``export``, ``extend``, ``diff``, ``export_lockfile``,
``install_from_lockfile``) lands in subsequent PRs.
"""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

import yaml

from hippo.core.exceptions import (
    RecipeDigestMismatchError,
    RecipeManifestError,
    RecipeRequiresUnsatisfiedError,
    RecipeVersionIncompatibleError,
    RecipeLineageCycleError,
    RecipeSchemaError,
)
from hippo.core.meta import get_meta, set_meta
from hippo.core.recipe import (
    FileResolver,
    HttpsResolver,
    ImportResult,
    InstalledRecipe,
    RecipeAuthor,
    RecipeManifest,
    RecipeRef,
    RecipeReport,
    RecipeRequires,
    RecipeResolver,
    canonical_content_hash,
)
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


_RECIPE_MANIFEST_SCHEMA_NAME = "recipe_manifest.yaml"


class _ManifestYAMLLoader(yaml.SafeLoader):
    """YAML loader that keeps ISO timestamps as strings.

    LinkML's ``datetime`` range serialises to a JSON Schema ``string``,
    so the bundled JSON-schema validator rejects a Python ``datetime``
    even when the value would round-trip cleanly. Stripping the
    timestamp implicit resolver leaves ISO 8601 instants as strings,
    which is what the manifest schema expects.
    """


_ManifestYAMLLoader.yaml_implicit_resolvers = {
    k: [(t, r) for t, r in v if t != "tag:yaml.org,2002:timestamp"]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


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
        resolvers: Optional[Sequence[RecipeResolver]] = None,
    ) -> None:
        """Compose the service.

        ``cache_dir`` overrides :func:`default_recipe_cache_dir` for the
        bundled :class:`HttpsResolver`. ``resolvers`` defaults to
        ``[FileResolver(), HttpsResolver(cache_dir)]`` when not supplied;
        passing an explicit list disables the default registration so
        tests can wire isolated resolver chains.
        """
        self._storage = storage
        self._schema_manager = schema_manager
        self._provenance_service = provenance_service
        self._cache_dir = cache_dir
        if resolvers is None:
            self._resolvers: tuple[RecipeResolver, ...] = (
                FileResolver(),
                HttpsResolver(cache_dir=cache_dir),
            )
        else:
            self._resolvers = tuple(resolvers)

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

    def inspect(
        self,
        source: str | Path,
        *,
        base_dir: Optional[Path] = None,
        expected_digest: Optional[str] = None,
    ) -> RecipeReport:
        """Parse, validate, and digest a recipe without any state change (sec10 §10.2.3).

        Pipeline (sec10 §10.4): resolve ``source`` → read
        ``recipe.yaml`` → closed-schema validation against
        ``recipe_manifest.yaml`` → compute canonical content hash →
        enumerate the embedded ``schema.yaml``'s classes/slots. No DB
        writes. No cache writes. No provenance.

        Args:
            source: ``file:`` URI, ``https:`` URI, bare absolute path,
                or bare relative path. Tarballs are accepted.
            base_dir: Resolves bare relative paths and relative
                ``file:`` URIs. Defaults to ``Path.cwd()`` when
                ``source`` is a string and to ``source.parent`` when
                ``source`` is an existing ``Path`` (so callers passing
                a path-like get the natural local resolution behavior).
            expected_digest: Optional declared digest. When supplied,
                the resolver verifies the canonical content hash and
                raises :class:`RecipeDigestMismatchError` on mismatch.
                ``inspect`` is read-only, so the install-path rule
                "``https:`` requires a digest" is NOT enforced here —
                that lives in :meth:`import_` (PR 7).

        Raises:
            RecipeManifestError: Manifest fails closed-schema validation.
            RecipeFetchError: HTTPS fetch failed (network, HTTP error,
                corrupt tarball).
            RecipeDigestMismatchError: ``expected_digest`` did not
                match the fetched/loaded recipe's canonical content
                hash.
        """
        src_str = str(source)
        effective_base = base_dir
        if effective_base is None and isinstance(source, Path) and source.exists():
            effective_base = source.parent if source.is_file() else None

        resolver = self._select_resolver(src_str)
        with resolver.resolve(
            src_str,
            base_dir=effective_base,
            expected_digest=expected_digest,
        ) as recipe_dir:
            manifest_dict = self._read_manifest_yaml(recipe_dir, source=src_str)
            self._validate_manifest(manifest_dict, source=src_str)
            manifest = _manifest_from_dict(manifest_dict)
            digest = canonical_content_hash(recipe_dir)
            classes, slots = self._inspect_schema_elements(recipe_dir)

        return RecipeReport(
            manifest=manifest,
            digest=digest,
            classes=classes,
            slots=slots,
        )

    def import_(
        self,
        source: str | Path,
        *,
        dry_run: bool = False,
        base_dir: Optional[Path] = None,
        expected_digest: Optional[str] = None,
    ) -> ImportResult:
        """Bootstrap-install a recipe end-to-end (sec10 §10.4 / invariant 3).

        Pipeline:

        1. Resolve ``source`` and parse + validate ``recipe.yaml`` (same
           preflight as :meth:`inspect`).
        2. Check ``hippo_version`` against the running Hippo via
           :class:`packaging.specifiers.SpecifierSet`.
        3. Recursively resolve every dependency (``parent`` +
           ``requires.recipes``) bottom-up with cycle detection. Each
           dep is fetched, validated, and pre-flighted just like the
           top-level recipe.
        4. Check every ``requires.reference_loaders`` pin is satisfied
           (sec10 §10.4.5 — precondition only, no transitive install).
        5. Inside one storage transaction (atomicity, invariant 3):
           - For each recipe in dependency order: call
             :meth:`SchemaManager.merge_fragment`, write the
             ``installed_recipes`` entry, emit a ``recipe_imported``
             provenance event.
           - On any failure mid-merge, the transaction rolls back and
             no state change persists.

        ``dry_run`` performs steps 1–4 and returns an :class:`ImportResult`
        with ``dry_run=True`` and an empty ``installed`` list; no
        transaction is opened.

        Returns:
            :class:`ImportResult` carrying the per-recipe ``InstalledRecipe``
            entries (in install order) and the top-level recipe's
            added classes / slots.
        """
        # 1. Preflight the top-level recipe (parse, validate, digest).
        src_str = str(source)
        effective_base = base_dir
        if effective_base is None and isinstance(source, Path) and source.exists():
            effective_base = source.parent if source.is_file() else None

        plan = self._plan_import(
            src_str,
            base_dir=effective_base,
            expected_digest=expected_digest,
        )

        # 2. Reference-loader preconditions are checked against the live
        # `reference_versions` registry.
        self._verify_reference_loader_preconditions(plan)

        if dry_run:
            installed = tuple(
                _installed_recipe_from_plan_entry(entry)
                for entry in plan
            )
            top = plan[-1]
            return ImportResult(
                installed=installed,
                classes_added=tuple(top.classes_added),
                slots_added=tuple(top.slots_added),
                dry_run=True,
            )

        if self._storage is None or not hasattr(self._storage, "_transaction"):
            raise ValueError(
                "Cannot import a recipe: RecipeService has no storage. "
                "Construct HippoClient with a storage adapter."
            )
        if self._schema_manager is None:
            raise ValueError(
                "Cannot import a recipe: RecipeService has no SchemaManager."
            )

        installed_records: list[InstalledRecipe] = []
        with self._storage._transaction() as conn:
            existing = get_meta(conn, META_KEY_INSTALLED_RECIPES) or {}
            for entry in plan:
                # Re-merge a previously-installed recipe at the same
                # version is a no-op; this lets a child import skip
                # re-installing its parent.
                if (
                    entry.manifest.id in existing
                    and existing[entry.manifest.id].get("version")
                    == entry.manifest.version
                ):
                    installed_records.append(
                        _installed_recipe_from_dict(existing[entry.manifest.id])
                    )
                    continue

                self._merge_one(entry)
                record = _installed_recipe_from_plan_entry(entry)
                existing[entry.manifest.id] = _installed_recipe_to_dict(record)
                set_meta(conn, META_KEY_INSTALLED_RECIPES, existing)
                self._emit_recipe_imported(conn, entry)
                installed_records.append(record)

        top = plan[-1]
        return ImportResult(
            installed=tuple(installed_records),
            classes_added=tuple(top.classes_added),
            slots_added=tuple(top.slots_added),
            dry_run=False,
        )

    def _plan_import(
        self,
        source: str,
        *,
        base_dir: Optional[Path],
        expected_digest: Optional[str],
    ) -> list["_PlanEntry"]:
        """Resolve dependencies bottom-up; return install order with cycle detection.

        Returns the install order as a list whose last entry is the
        top-level recipe. Each entry carries the parsed manifest, the
        resolved schema fragment, the canonical-content digest, and
        the post-resolution source URI (so provenance carries the
        exact URI Hippo fetched from).
        """
        plan: list[_PlanEntry] = []
        seen: dict[str, str] = {}
        stack: list[str] = []
        self._resolve_recursive(
            source=source,
            base_dir=base_dir,
            expected_digest=expected_digest,
            plan=plan,
            seen=seen,
            stack=stack,
        )
        return plan

    def _resolve_recursive(
        self,
        *,
        source: str,
        base_dir: Optional[Path],
        expected_digest: Optional[str],
        plan: list["_PlanEntry"],
        seen: dict[str, str],
        stack: list[str],
    ) -> None:
        """Bottom-up resolve ``source`` and append to ``plan`` (dependencies first)."""
        resolver = self._select_resolver(source)
        with resolver.resolve(
            source, base_dir=base_dir, expected_digest=expected_digest
        ) as recipe_dir:
            manifest_dict = self._read_manifest_yaml(recipe_dir, source=source)
            self._validate_manifest(manifest_dict, source=source)
            manifest = _manifest_from_dict(manifest_dict)
            self._check_hippo_version(manifest, source=source)

            self._enforce_https_digest_required(source, expected_digest, manifest)

            if manifest.id in stack:
                cycle = stack[stack.index(manifest.id):] + [manifest.id]
                raise RecipeLineageCycleError(
                    f"Recipe lineage cycle detected: {' -> '.join(cycle)}",
                    source=source,
                    recipe_id=manifest.id,
                    recipe_version=manifest.version,
                    cycle=cycle,
                )

            if manifest.id in seen:
                # Already planned via an earlier branch; do not enqueue
                # twice (this is how the merge-step deduplicates).
                if seen[manifest.id] != manifest.version:
                    raise RecipeRequiresUnsatisfiedError(
                        f"Recipe {manifest.id!r} appears at multiple versions in "
                        f"the dependency graph: {seen[manifest.id]!r} and "
                        f"{manifest.version!r}.",
                        source=source,
                        recipe_id=manifest.id,
                        recipe_version=manifest.version,
                    )
                return

            stack.append(manifest.id)
            try:
                # Parent first, then sibling requires — sec10 §10.4.4 order.
                if manifest.parent is not None:
                    self._resolve_recursive(
                        source=manifest.parent.source,
                        base_dir=recipe_dir,
                        expected_digest=manifest.parent.digest,
                        plan=plan,
                        seen=seen,
                        stack=stack,
                    )
                for ref in manifest.requires.recipes:
                    self._resolve_recursive(
                        source=ref.source,
                        base_dir=recipe_dir,
                        expected_digest=ref.digest,
                        plan=plan,
                        seen=seen,
                        stack=stack,
                    )
            finally:
                stack.pop()

            digest = canonical_content_hash(recipe_dir)
            if expected_digest is not None:
                # The resolver already verified, but stamp the recorded
                # digest with the canonical hex form (no sha256: prefix).
                pass
            schema_path = recipe_dir / "schema.yaml"
            if schema_path.is_file():
                fragment_text = schema_path.read_text(encoding="utf-8")
                fragment = yaml.safe_load(fragment_text) or {}
            else:
                fragment = {}

            classes_added = sorted((fragment.get("classes") or {}).keys())
            slots_added = sorted((fragment.get("slots") or {}).keys())

            seen[manifest.id] = manifest.version
            plan.append(
                _PlanEntry(
                    manifest=manifest,
                    source=source,
                    digest=digest,
                    fragment=fragment,
                    classes_added=classes_added,
                    slots_added=slots_added,
                )
            )

    def _check_hippo_version(
        self, manifest: RecipeManifest, *, source: str
    ) -> None:
        """Reject the import if the running Hippo version is excluded."""
        from packaging.specifiers import InvalidSpecifier, SpecifierSet

        try:
            spec = SpecifierSet(manifest.hippo_version)
        except InvalidSpecifier as e:
            raise RecipeVersionIncompatibleError(
                f"Recipe {manifest.id}@{manifest.version} declares an "
                f"invalid hippo_version specifier {manifest.hippo_version!r}: {e}",
                source=source,
                recipe_id=manifest.id,
                recipe_version=manifest.version,
                specifier=manifest.hippo_version,
            ) from e

        from hippo import __version__ as _hippo_version_module

        # The hippo package version is not yet imported in older builds —
        # fall through gracefully when the attribute is missing.
        if _hippo_version_module not in spec:
            raise RecipeVersionIncompatibleError(
                f"Recipe {manifest.id}@{manifest.version} requires "
                f"hippo {manifest.hippo_version!r} but installed Hippo is "
                f"{_hippo_version_module!r}.",
                source=source,
                recipe_id=manifest.id,
                recipe_version=manifest.version,
                specifier=manifest.hippo_version,
                hippo_version=_hippo_version_module,
            )

    def _enforce_https_digest_required(
        self,
        source: str,
        expected_digest: Optional[str],
        manifest: RecipeManifest,
    ) -> None:
        """Sec10 invariant 4: ``https:`` source MUST declare a digest at install."""
        if expected_digest is None and source.startswith("https:"):
            raise RecipeDigestMismatchError(
                "Install of an https: source requires a declared digest "
                "(sec10 invariant 4). Pass a digest on the RecipeRef or "
                "use `hippo recipe inspect` to discover it.",
                source=source,
                recipe_id=manifest.id,
                recipe_version=manifest.version,
            )

    def _verify_reference_loader_preconditions(
        self, plan: list["_PlanEntry"]
    ) -> None:
        """Each ``requires.reference_loaders`` pin must already be installed.

        Sec10 §10.4.5: v1 treats these as preconditions only — Hippo
        does NOT install Reference Loaders as a side effect of recipe
        import.
        """
        if self._storage is None or not hasattr(self._storage, "_transaction"):
            # Nothing to check against; skip silently rather than fail.
            return
        with self._storage._transaction() as conn:
            installed_versions = get_meta(conn, "reference_versions") or {}

        for entry in plan:
            for pin in entry.manifest.requires.reference_loaders:
                if "==" not in pin:
                    raise RecipeRequiresUnsatisfiedError(
                        f"requires.reference_loaders entry {pin!r} is not a "
                        f"valid pin (expected 'name==version').",
                        source=entry.source,
                        recipe_id=entry.manifest.id,
                        recipe_version=entry.manifest.version,
                        loader_pin=pin,
                    )
                name, _, version = pin.partition("==")
                installed = installed_versions.get(name)
                installed_version = (
                    installed.get("version") if isinstance(installed, dict) else None
                )
                if installed_version != version:
                    raise RecipeRequiresUnsatisfiedError(
                        f"Recipe {entry.manifest.id}@{entry.manifest.version} "
                        f"requires reference loader {pin!r} but installed "
                        f"version is {installed_version!r}.",
                        source=entry.source,
                        recipe_id=entry.manifest.id,
                        recipe_version=entry.manifest.version,
                        loader_pin=pin,
                    )

    def _merge_one(self, entry: "_PlanEntry") -> None:
        """Merge one recipe's fragment via ``SchemaManager.merge_fragment``."""
        assert self._schema_manager is not None
        if not entry.fragment:
            return
        try:
            new_registry = self._schema_manager.merge_fragment(
                entry.fragment,
                recipe_id=entry.manifest.id,
                recipe_version=entry.manifest.version,
            )
        except RecipeSchemaError:
            raise
        self._schema_manager.set_registry(new_registry)
        if self._storage is not None and hasattr(self._storage, "schema_registry"):
            self._storage.schema_registry = new_registry

    def _emit_recipe_imported(
        self,
        conn: object,
        entry: "_PlanEntry",
    ) -> None:
        """Insert one ``recipe_imported`` ProvenanceRecord on this connection."""
        if self._storage is None or not hasattr(self._storage, "_get_provenance_store"):
            return
        prov_store = self._storage._get_provenance_store(conn)
        parent_payload = None
        if entry.manifest.parent is not None:
            parent_payload = {
                "id": entry.manifest.parent.id,
                "version": entry.manifest.parent.version,
                "source": entry.manifest.parent.source,
                "digest": entry.manifest.parent.digest,
            }
        prov_store.record(
            entity_id=None,
            entity_type=None,
            operation="recipe_imported",
            patch={
                "recipe_id": entry.manifest.id,
                "recipe_version": entry.manifest.version,
                "recipe_digest": entry.digest,
                "recipe_source": entry.source,
                "parent": parent_payload,
                "classes_added": list(entry.classes_added),
                "slots_added": list(entry.slots_added),
            },
        )

    def _select_resolver(self, source: str) -> RecipeResolver:
        for r in self._resolvers:
            if r.can_handle(source):
                return r
        raise ValueError(
            f"No registered RecipeResolver handles source: {source!r}"
        )

    def _read_manifest_yaml(self, recipe_dir: Path, *, source: str) -> dict:
        manifest_path = recipe_dir / "recipe.yaml"
        if not manifest_path.is_file():
            raise RecipeManifestError(
                "Recipe is missing recipe.yaml at its root.",
                source=source,
            )
        try:
            data = yaml.load(
                manifest_path.read_text(encoding="utf-8"),
                Loader=_ManifestYAMLLoader,
            )
        except yaml.YAMLError as e:
            raise RecipeManifestError(
                f"Failed to parse recipe.yaml: {e}",
                source=source,
            ) from e
        if not isinstance(data, dict):
            raise RecipeManifestError(
                "recipe.yaml must be a YAML mapping at the top level.",
                source=source,
            )
        return data

    def _validate_manifest(self, manifest_dict: dict, *, source: str) -> None:
        """Closed-schema-validate ``manifest_dict`` against ``recipe_manifest.yaml``.

        Uses the bundled LinkML schema shipped under
        ``hippo.schemas`` and the same ``JsonschemaValidationPlugin(closed=True)``
        wiring exercised by the Phase-2 schema tests.
        """
        from linkml.validator import Validator
        from linkml.validator.plugins import JsonschemaValidationPlugin

        schema_path = importlib.resources.files("hippo.schemas").joinpath(
            _RECIPE_MANIFEST_SCHEMA_NAME
        )
        validator = Validator(
            schema=str(schema_path),
            validation_plugins=[JsonschemaValidationPlugin(closed=True)],
        )
        report = validator.validate(manifest_dict, "RecipeManifest")
        if report.results:
            messages = [r.message for r in report.results]
            raise RecipeManifestError(
                f"recipe.yaml failed validation ({len(messages)} error(s)): "
                f"{messages[0]}",
                source=source,
                recipe_id=manifest_dict.get("id"),
                recipe_version=manifest_dict.get("version"),
                errors=messages,
            )

    def _inspect_schema_elements(
        self,
        recipe_dir: Path,
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return ``(classes, slots)`` declared in the recipe's ``schema.yaml``.

        ``inspect`` is read-only; no merge or LinkML SchemaView wiring
        happens here. When ``schema.yaml`` is absent or malformed, the
        report carries empty tuples — the merge layer (PR 7) is the
        gate that turns those into hard failures.
        """
        schema_path = recipe_dir / "schema.yaml"
        if not schema_path.is_file():
            return (), ()
        try:
            content = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            return (), ()
        if not isinstance(content, dict):
            return (), ()

        classes = tuple(sorted((content.get("classes") or {}).keys()))
        slots = tuple(sorted((content.get("slots") or {}).keys()))
        return classes, slots


from dataclasses import dataclass, field as _dc_field


@dataclass(frozen=True)
class _PlanEntry:
    """One node in the recipe dependency-resolution plan.

    Private to :class:`RecipeService`. Captures everything ``import_``
    needs after the recursive resolve step has finished — manifest,
    post-resolution source URI, canonical-content digest, parsed
    schema fragment, and the lists of classes/slots the fragment adds.
    The fragment dict is the un-modified author content; the merge
    layer is responsible for ``provided_by`` injection (invariant 7).
    """

    manifest: RecipeManifest
    source: str
    digest: str
    fragment: dict = _dc_field(default_factory=dict)
    classes_added: tuple[str, ...] | list[str] = ()
    slots_added: tuple[str, ...] | list[str] = ()


def _installed_recipe_from_plan_entry(entry: _PlanEntry) -> InstalledRecipe:
    """Convert a planned install into the persisted :class:`InstalledRecipe`."""
    from datetime import datetime, timezone

    parent = entry.manifest.parent
    return InstalledRecipe(
        id=entry.manifest.id,
        version=entry.manifest.version,
        source=entry.source,
        digest=entry.digest,
        installed_at=datetime.now(timezone.utc).isoformat(),
        parent=parent,
    )


def _installed_recipe_to_dict(record: InstalledRecipe) -> dict:
    """Serialise :class:`InstalledRecipe` to its persisted JSON shape."""
    parent_payload = None
    if record.parent is not None:
        parent_payload = {
            "id": record.parent.id,
            "version": record.parent.version,
            "source": record.parent.source,
            "digest": record.parent.digest,
        }
    return {
        "id": record.id,
        "version": record.version,
        "source": record.source,
        "digest": record.digest,
        "installed_at": record.installed_at,
        "parent": parent_payload,
    }


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


def _manifest_from_dict(data: dict) -> RecipeManifest:
    """Hydrate a :class:`RecipeManifest` from a closed-schema-validated dict.

    Optional sub-objects (``author``, ``parent``, ``requires``) are
    materialized into their typed counterparts. The caller is
    responsible for having validated ``data`` first — this function
    assumes the closed-schema contract holds.
    """
    author = None
    if (raw_author := data.get("author")) is not None:
        author = RecipeAuthor(
            name=raw_author.get("name"),
            email=raw_author.get("email"),
            organization=raw_author.get("organization"),
        )

    parent = None
    if (raw_parent := data.get("parent")) is not None:
        parent = RecipeRef(
            id=raw_parent["id"],
            version=raw_parent["version"],
            source=raw_parent["source"],
            digest=raw_parent.get("digest"),
        )

    requires_data = data.get("requires") or {}
    requires = RecipeRequires(
        recipes=tuple(
            RecipeRef(
                id=r["id"],
                version=r["version"],
                source=r["source"],
                digest=r.get("digest"),
            )
            for r in (requires_data.get("recipes") or [])
        ),
        reference_loaders=tuple(requires_data.get("reference_loaders") or []),
    )

    return RecipeManifest(
        id=data["id"],
        name=data["name"],
        version=data["version"],
        created_at=str(data["created_at"]),
        hippo_version=data["hippo_version"],
        description=data.get("description"),
        author=author,
        license=data.get("license"),
        source=data.get("source"),
        parent=parent,
        requires=requires,
    )
