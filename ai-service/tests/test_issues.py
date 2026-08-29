import os

os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key-for-pytest")

from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_service import get_llm_service


class FakeLLM:
    def generate_structured(self, _prompt, output_type):
        return output_type(
            severity="HIGH", confidence=0.87,
            reason="Authentication failures prevent active users from accessing the application.",
            concepts=["authentication", "session"], affected_components=["auth service"],
        )


def test_issue_analysis_returns_structured_assessment() -> None:
    app.dependency_overrides[get_llm_service] = FakeLLM
    response = TestClient(app).post("/api/issues/analyze", headers={"Authorization": "Bearer test-service-key-for-pytest"}, json={
        "repository_id": "repo-1",
        "issue": {"number": 15, "title": "Users are logged out", "body": "Refreshing the page logs users out."},
    })

    assert response.status_code == 200
    assert response.json()["data"]["severity"] == "HIGH"
    assert response.json()["data"]["confidence"] == 0.87
    app.dependency_overrides.clear()
