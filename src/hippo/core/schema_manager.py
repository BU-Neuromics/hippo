"""SchemaManager - Schema loading, validation pipeline, and FTS metadata facade."""

from typing import Any, Optional

from hippo.config.models import SchemaConfig
from hippo.core.pipeline import ValidationPipeline
from hippo.core.storage.adapters.sqlite_adapter import SQLiteAdapter
from hippo.core.storage.fts import FTSTableMetadata
from hippo.core.validation.validators import (
    ValidationResult,
    WriteOperation,
    WriteValidator,
)


class SchemaManager:
    """Manages schema loading, validation pipeline, DSL compilation, and FTS metadata.

    This facade owns all schema-related state and validation logic extracted
    from HippoClient.
    """

    def __init__(
        self,
        schemas: Optional[dict[str, SchemaConfig]] = None,
        pipeline: Optional[ValidationPipeline] = None,
        bypass_validation: bool = False,
        storage: Optional[SQLiteAdapter] = None,
    ) -> None:
        self._schemas = schemas
        self._pipeline = pipeline
        self._bypass_validation = bypass_validation
        self._storage = storage
        self._fts_table_metadata: dict[str, list[FTSTableMetadata]] = {}
        self._build_fts_metadata()
        self._validate_search_capabilities()

    @property
    def schemas(self) -> Optional[dict[str, SchemaConfig]]:
        return self._schemas

    @property
    def pipeline(self) -> Optional[ValidationPipeline]:
        return self._pipeline

    @pipeline.setter
    def pipeline(self, value: Optional[ValidationPipeline]) -> None:
        self._pipeline = value

    @property
    def bypass_validation(self) -> bool:
        return self._bypass_validation

    @property
    def fts_table_metadata(self) -> dict[str, list[FTSTableMetadata]]:
        return self._fts_table_metadata

    def _build_fts_metadata(self) -> None:
        """Populate _fts_table_metadata from self._schemas."""
        if not self._schemas:
            return
        for entity_type, schema in self._schemas.items():
            fts_tables = []
            for field in schema.fields:
                if field.search and "fts" in field.search.lower():
                    meta = FTSTableMetadata.from_field(field, entity_type=entity_type)
                    fts_tables.append(meta)
            if fts_tables:
                self._fts_table_metadata[entity_type] = fts_tables

    def _validate_search_capabilities(self) -> None:
        """Validate that the storage adapter supports all search modes declared in schemas."""
        from hippo.core.exceptions import SearchCapabilityError

        if self._storage is None:
            return

        if self._schemas is None:
            return

        adapter_capabilities = self._storage.search_capabilities()

        declared_modes: set[str] = set()
        for schema in self._schemas.values():
            for field in schema.fields:
                if field.search is not None:
                    normalized_mode = (
                        "fts" if field.search in ("fts", "fts5") else field.search
                    )
                    declared_modes.add(normalized_mode)

        unsupported_modes = declared_modes - adapter_capabilities
        if unsupported_modes:
            raise SearchCapabilityError(
                message=f"Storage adapter does not support search modes: {', '.join(sorted(unsupported_modes))}",
                unsupported_modes=list(unsupported_modes),
            )

    def schema_references(self, entity_type: str) -> list[dict]:
        """Return reference edges for an entity type from the loaded schema."""
        if not self._schemas or entity_type not in self._schemas:
            return []
        schema = self._schemas[entity_type]
        return [
            {"field": field.name, "target_entity_type": field.references["entity_type"]}
            for field in schema.fields
            if field.references and "entity_type" in field.references
        ]

    def get_fts_tables_for_entity_type(
        self, entity_type: str
    ) -> list[FTSTableMetadata]:
        """Get FTS table metadata for an entity type."""
        return self._fts_table_metadata.get(entity_type, [])

    def add_validator(self, validator: WriteValidator) -> None:
        """Add a validator to the pipeline. Creates pipeline if needed."""
        if self._pipeline is None:
            self._pipeline = ValidationPipeline()
        self._pipeline.add_validator(validator)

    def validate(self, operation: WriteOperation) -> ValidationResult:
        """Validate a write operation using the validation pipeline."""
        if self._bypass_validation or self._pipeline is None:
            return ValidationResult(is_valid=True, errors=[])
        return self._pipeline.execute(operation)
