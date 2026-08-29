import os

from fastapi.testclient import TestClient

os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key-for-pytest")

from app.main import app
from app.api.routes.health import get_qdrant_service
from app.services.qdrant_service import QdrantUnavailableError


class FakeQdrantService:
    def collection_count(self) -> int:
        return 3


class UnavailableQdrantService:
    def collection_count(self) -> int:
        raise QdrantUnavailableError("Qdrant is unavailable")


def test_health_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


def test_test_endpoint_requires_service_key() -> None:
    client = TestClient(app)

    assert client.get("/api/test").status_code == 401
    assert client.get("/api/test", headers={"Authorization": "Bearer test-service-key-for-pytest"}).status_code == 200


def test_qdrant_health_requires_service_key_and_reports_connection() -> None:
    app.dependency_overrides[get_qdrant_service] = FakeQdrantService
    client = TestClient(app)

    assert client.get("/api/health/qdrant").status_code == 401
    response = client.get("/api/health/qdrant", headers={"Authorization": "Bearer test-service-key-for-pytest"})

    assert response.status_code == 200
    assert response.json()["data"] == {"status": "ok", "collections": 3}
    app.dependency_overrides.clear()


def test_qdrant_health_returns_safe_error_when_unavailable() -> None:
    app.dependency_overrides[get_qdrant_service] = UnavailableQdrantService
    client = TestClient(app)

    response = client.get("/api/health/qdrant", headers={"Authorization": "Bearer test-service-key-for-pytest"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "QDRANT_UNAVAILABLE"
    app.dependency_overrides.clear()
