"""Network-free ``ReferenceLoader`` for use in Hippo test suites.

Implements every abstract method against an in-memory dataset so tests
exercising loader discovery, the install lifecycle, and CLI plumbing
have a concrete entry-point target without depending on a real
reference package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from hippo.core.loaders.reference import LoadResult, ReferenceLoader

if TYPE_CHECKING:
    from hippo.core.client import HippoClient


class FakeLoadParams(BaseModel):
    """Parameter model rendered by the CLI when the fake loader is
    invoked with ``--flag`` args."""

    tag: str = "default"


class FakeReferenceLoader(ReferenceLoader):
    """Deterministic, in-memory ``ReferenceLoader`` for the test suite."""

    name = "fake"
    description = "In-memory fake reference loader (test fixture)"
    load_params_schema = FakeLoadParams

    # In-memory dataset keyed by version. Kept tiny on purpose.
    _DATASET: dict[str, list[dict[str, Any]]] = {
        "test": [
            {"id": "fake:001", "label": "alpha"},
            {"id": "fake:002", "label": "beta"},
        ],
        "v1": [
            {"id": "fake:001", "label": "alpha"},
            {"id": "fake:002", "label": "beta"},
            {"id": "fake:003", "label": "gamma"},
        ],
    }

    def versions(self) -> list[str]:
        return list(self._DATASET.keys())

    def entity_types(self) -> list[str]:
        return ["FakeTerm"]

    def schema_fragment(self) -> dict:
        return {
            "id": "https://example.org/hippo/fake",
            "name": "fake",
            "default_prefix": "fake",
            "prefixes": {"fake": "https://example.org/hippo/fake/"},
            "classes": {
                "FakeTerm": {
                    "is_a": "Entity",
                    "attributes": {
                        "label": {"range": "string", "required": True},
                    },
                },
            },
        }

    def load(
        self,
        client: HippoClient,
        version: str,
        params: BaseModel | None = None,
    ) -> LoadResult:
        rows = self._DATASET.get(version)
        if rows is None:
            return LoadResult(
                errors=1,
                error_messages=[f"unknown version: {version}"],
                entity_type="FakeTerm",
            )
        return LoadResult(
            created=len(rows),
            entity_type="FakeTerm",
        )
