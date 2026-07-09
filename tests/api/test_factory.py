"""Tests for Hippo API factory."""

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.testclient import TestClient
from fastapi.exceptions import RequestValidationError

from hippo.api import create_app, EntityNotFoundError
from hippo.core.exceptions import (
    AdapterError,
    ConfigError,
    EntityAlreadySupersededError,
    IngestionError,
    ProvenanceIntegrityError,
    RecipeFetchError,
    SchemaError,
    SearchCapabilityError,
    TemporalQueryError,
    ValidationError as HippoValidationError,
    ValidationFailure,
)


def test_factory_creates_app_without_routers():
    """Test that factory creates app without routers."""
    app = create_app()
    assert isinstance(app, FastAPI)
    assert app.title == "Hippo API"


def test_factory_creates_app_with_routers():
    """Test that factory creates app with routers."""
    router = APIRouter()

    @router.get("/test")
    def test_endpoint():
        return {"message": "test"}

    app = create_app(routers=[router])
    assert isinstance(app, FastAPI)

    client = TestClient(app)
    response = client.get("/test")
    assert response.status_code == 200
    assert response.json() == {"message": "test"}


def test_request_validation_error_handler_returns_422():
    """Test that RequestValidationError handler returns 422."""
    app = create_app()

    @app.get("/validate")
    def validate():
        raise RequestValidationError(
            [{"type": "missing", "loc": ("body",), "msg": "Field required"}]
        )

    client = TestClient(app)
    response = client.get("/validate")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"] == "Validation Error"


def test_entity_not_found_error_handler_returns_404():
    """Test that EntityNotFoundError handler returns 404."""
    app = create_app()

    @app.get("/entity/{entity_id}")
    def get_entity(entity_id: str):
        raise EntityNotFoundError(
            message="Entity not found",
            entity_type="Sample",
            entity_id=entity_id,
        )

    client = TestClient(app)
    response = client.get("/entity/abc123")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"] == "Entity Not Found"


def test_generic_exception_handler_returns_500():
    """Test that generic Exception handler returns 500."""
    app = create_app()

    @app.get("/error")
    def trigger_error():
        raise HTTPException(status_code=500, detail="Internal Server Error")

    client = TestClient(app)
    response = client.get("/error")
    assert response.status_code == 500
    assert "detail" in response.json()


def test_hippo_validation_error_handler_returns_422():
    """Test that HippoValidationError handler returns 422."""
    app = create_app()

    @app.get("/hippo-validate")
    def hippo_validate():
        raise HippoValidationError(
            message="Invalid input",
            expected_type="string",
            actual_value=123,
        )

    client = TestClient(app)
    response = client.get("/hippo-validate")
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"] == "Validation Error"


# ---------------------------------------------------------------------------
# sec4 §4.3 HippoError -> HTTP status mapping (issue #62)
# ---------------------------------------------------------------------------


def _raising_app(exc: Exception):
    app = create_app()

    @app.get("/raise")
    def raise_it():
        raise exc

    return app


def test_entity_already_superseded_error_returns_409():
    client = TestClient(
        _raising_app(
            EntityAlreadySupersededError(
                message="Already superseded", entity_id="abc123", superseded_by="def456"
            )
        )
    )
    response = client.get("/raise")
    assert response.status_code == 409
    assert response.json()["error"] == "Already Superseded"


def test_config_error_returns_409():
    client = TestClient(
        _raising_app(ConfigError(message="Bad adapter config", field_name="database_url"))
    )
    response = client.get("/raise")
    assert response.status_code == 409
    assert response.json()["error"] == "Config Error"


def test_validation_failure_returns_422():
    client = TestClient(
        _raising_app(ValidationFailure(message="Write validation failed", rule_id="r1"))
    )
    response = client.get("/raise")
    assert response.status_code == 422
    assert response.json()["error"] == "Validation Failure"


def test_ingestion_error_returns_400():
    client = TestClient(_raising_app(IngestionError(message="Bad ingest input")))
    response = client.get("/raise")
    assert response.status_code == 400
    assert response.json()["error"] == "Ingestion Error"


def test_search_capability_error_returns_400():
    client = TestClient(
        _raising_app(
            SearchCapabilityError(message="FTS not enabled", field_name="name")
        )
    )
    response = client.get("/raise")
    assert response.status_code == 400
    assert response.json()["error"] == "Search Capability Error"


def test_temporal_query_error_returns_400():
    client = TestClient(
        _raising_app(TemporalQueryError(message="Invalid as-of timestamp"))
    )
    response = client.get("/raise")
    assert response.status_code == 400
    assert response.json()["error"] == "Temporal Query Error"


def test_schema_error_returns_400():
    client = TestClient(_raising_app(SchemaError(message="Invalid schema")))
    response = client.get("/raise")
    assert response.status_code == 400
    assert response.json()["error"] == "Schema Error"


def test_adapter_error_returns_named_500():
    client = TestClient(
        _raising_app(AdapterError(message="Storage backend unreachable"))
    )
    response = client.get("/raise")
    assert response.status_code == 500
    assert response.json()["error"] == "AdapterError"


def test_provenance_integrity_error_returns_named_500():
    client = TestClient(
        _raising_app(
            ProvenanceIntegrityError(message="Missing provenance", entity_id="abc123")
        )
    )
    response = client.get("/raise")
    assert response.status_code == 500
    assert response.json()["error"] == "ProvenanceIntegrityError"


def test_unmapped_hippo_error_falls_back_to_named_500():
    """Recipe/migration/cache/orchestration errors share the catch-all."""
    client = TestClient(
        _raising_app(RecipeFetchError(message="Could not fetch recipe"))
    )
    response = client.get("/raise")
    assert response.status_code == 500
    assert response.json()["error"] == "RecipeFetchError"
