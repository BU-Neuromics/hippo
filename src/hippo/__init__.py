"""Hippo SDK - Metadata Tracking Service."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("hippo")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

from hippo.core.client import HippoClient
from hippo.core.exceptions import ValidationFailure
from hippo.core.pipeline import ValidationPipeline
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
    ValidationError,
    ValidationResult,
    WriteOperation,
)

__all__ = [
    "HippoClient",
    "ValidationFailure",
    "ValidationPipeline",
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
    "ValidationError",
    "ValidationResult",
    "WriteOperation",
]
