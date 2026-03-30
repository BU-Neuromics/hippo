"""Core SDK types for Hippo.

The core module provides the fundamental types and abstractions for the Hippo
Metadata Tracking Service SDK.

Key Components:
- Validation: SchemaValidator, ValidationResult, WriteOperation
- Storage: EntityStore, ValidatingEntityStore
- Types: ProvenanceRecord, IngestResult, Filter

Quick Start - Validation:
```python
from hippo.core.validation import SchemaValidator, SchemaValidationConfig
from hippo.config.models import SchemaConfig, FieldDefinition

schema = SchemaConfig(
    name="Sample",
    version="1.0",
    fields=[
        FieldDefinition(name="id", type="string", required=True),
        FieldDefinition(name="name", type="string", required=True),
    ]
)

config = SchemaValidationConfig(schemas={"Sample": schema})
validator = SchemaValidator(config)

# Validate write operations before persisting
from hippo.core.validation import WriteOperation
op = WriteOperation(
    operation="insert",
    entity_type="Sample",
    data={"id": "123", "name": "Test"}
)
result = validator.validate(op)
if not result.is_valid:
    print(f"Errors: {result.errors}")
```
"""

from hippo.core.client import HippoClient
from hippo.core.ingestion_service import IngestionService
from hippo.core.provenance_service import ProvenanceService
from hippo.core.query_service import QueryService
from hippo.core.schema_manager import SchemaManager
from hippo.core.exceptions import (
    AdapterError,
    ConfigError,
    EntityAlreadySupersededError,
    EntityNotFoundError,
    HippoError,
    SchemaError,
    ValidationError,
    ValidationFailure,
)
from hippo.core.middleware import (
    AuthMiddleware,
    PassThroughAuthMiddleware,
    RequestContext,
    create_auth_middleware,
)
from hippo.core.pipeline import ValidationPipeline
from hippo.core.relationship import (
    RelationshipExistsError,
    RelationshipManager,
    RelationshipNotFoundError,
)
from hippo.core.types import (
    Filter,
    FilterCondition,
    FilterGroup,
    FilterOperator,
    IngestResult,
    IngestStatus,
    LogicalOperator,
    PaginatedResult,
    ProvenanceRecord,
    ScoredMatch,
    ValidationError as ValidationErrorModel,
    ValidationResult,
    WriteOperation,
)

__all__ = [
    "HippoClient",
    "IngestionService",
    "ProvenanceService",
    "QueryService",
    "SchemaManager",
    "HippoError",
    "ConfigError",
    "SchemaError",
    "ValidationError",
    "ValidationFailure",
    "EntityNotFoundError",
    "EntityAlreadySupersededError",
    "AdapterError",
    "ValidationPipeline",
    "RelationshipManager",
    "RelationshipExistsError",
    "RelationshipNotFoundError",
    "AuthMiddleware",
    "PassThroughAuthMiddleware",
    "RequestContext",
    "create_auth_middleware",
    "Filter",
    "FilterCondition",
    "FilterGroup",
    "FilterOperator",
    "IngestResult",
    "IngestStatus",
    "LogicalOperator",
    "PaginatedResult",
    "ProvenanceRecord",
    "ScoredMatch",
    "ValidationErrorModel",
    "ValidationResult",
    "WriteOperation",
]
