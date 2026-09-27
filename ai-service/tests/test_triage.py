import os

os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key-for-pytest")

from fastapi.testclient import TestClient

from app.services.triage_service import BatchAnalysisResult, SingleIssueAnalysis
from app.main import app
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service


class FakeEmbeddingService:
    def embed(self, texts: list[str]) -> list[list[float]]:
        # If texts are similar, return similar vectors
        vectors = []
        for t in texts:
            val = 0.9 if "login" in t.lower() or "auth" in t.lower() else 0.1
            vectors.append([val] * 384)
        return vectors


class FakeLLMService:
    def generate_structured(self, _prompt, output_type):
        if output_type == BatchAnalysisResult:
            return BatchAnalysisResult(
                classifications=[
                    SingleIssueAnalysis(
                        issue_number=1,
                        severity="HIGH",
                        category="Security",
                        confidence=0.92,
                        reason="Authentication failure affects all user sessions.",
                        affected_subsystem="auth",
                    ),
                    SingleIssueAnalysis(
                        issue_number=2,
                        severity="HIGH",
                        category="Bug",
                        confidence=0.88,
                        reason="Duplicate login crash report.",
                        affected_subsystem="auth",
                    ),
                    SingleIssueAnalysis(
                        issue_number=3,
                        severity="LOW",
                        category="Documentation",
                        confidence=0.95,
                        reason="Typo in README installation section.",
                        affected_subsystem="docs",
                    ),
                ]
            )
        raise ValueError(f"Unexpected output_type: {output_type}")


def test_batch_triage_endpoint_categorizes_and_detects_duplicates() -> None:
    app.dependency_overrides[get_llm_service] = FakeLLMService
    app.dependency_overrides[get_embedding_service] = FakeEmbeddingService

    client = TestClient(app)
    response = client.post(
        "/api/triage/analyze",
        headers={"Authorization": "Bearer test-service-key-for-pytest"},
        json={
            "repository_id": "repo-456",
            "issues": [
                {
                    "number": 1,
                    "title": "Cannot login after password reset",
                    "body": "Users are encountering 401 Unauthorized after resetting credentials.",
                    "labels": ["security", "auth"],
                },
                {
                    "number": 2,
                    "title": "Login fails following credential reset",
                    "body": "Duplicate issue: password reset causes auth 401 error.",
                    "labels": ["auth"],
                },
                {
                    "number": 3,
                    "title": "Fix typo in getting started guide",
                    "body": "npm intall -> npm install typo in readme.",
                    "labels": ["documentation"],
                },
            ],
            "architecture_components": ["Authentication", "Documentation"],
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["repository_id"] == "repo-456"
    assert data["summary"]["total_issues"] == 3
    assert data["summary"]["high_count"] == 2
    assert data["summary"]["low_count"] == 1
    assert data["summary"]["duplicate_groups_count"] >= 1

    issues = data["issues"]
    assert len(issues) == 3

    # Check issue 1 & 2 clustered as duplicates
    iss1 = next(i for i in issues if i["number"] == 1)
    iss2 = next(i for i in issues if i["number"] == 2)
    assert iss1["duplicate_group_id"] is not None
    assert iss1["duplicate_group_id"] == iss2["duplicate_group_id"]
    assert iss2["is_duplicate"] is True

    app.dependency_overrides.clear()
