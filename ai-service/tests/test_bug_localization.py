import os

os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key-for-pytest")

from fastapi.testclient import TestClient

from app.api.schemas.bug_localization import IssueAnalysis
from app.services.bug_localization_service import BugExplanationResponse, CandidateExplanationItem
from app.main import app
from app.services.embedding_service import get_embedding_service
from app.services.llm_service import get_llm_service
from app.services.qdrant_service import get_qdrant_service


class FakeEmbeddingService:
    def embed(self, texts: list[str]) -> list[list[float]]:
        # Return dummy 384-dimensional vector
        return [[0.05] * 384 for _ in texts]


class FakeQdrantClient:
    def collection_exists(self, _name: str) -> bool:
        return True

    def query_points(self, **_kwargs):
        class Point:
            score = 0.82
            payload = {
                "file_path": "src/services/auth.ts",
                "file_id": "file-1",
                "start_line": 10,
                "end_line": 35,
                "symbol": "refreshToken",
                "chunk_type": "function",
                "content": "export async function refreshToken() { ... }",
            }
        class Result:
            points = [Point()]
        return Result()


class FakeQdrantService:
    def __init__(self):
        self._client = FakeQdrantClient()


class FakeLLMService:
    def generate_structured(self, _prompt, output_type):
        if output_type == IssueAnalysis:
            return IssueAnalysis(
                problem_summary="Token refresh fails intermittently during session renewal",
                error_messages=["InvalidTokenError: jwt expired"],
                entities=["refreshToken", "verifySession"],
                file_path_hints=["src/services/auth.ts"],
                api_endpoints=["/api/auth/refresh"],
                domain_concepts=["jwt", "session", "authentication"],
                affected_subsystem="auth",
                search_queries=["refreshToken session renewal"],
            )
        if output_type == BugExplanationResponse:
            return BugExplanationResponse(
                analysis_summary="The issue appears to stem from expired token validation in auth.ts.",
                file_explanations=[
                    CandidateExplanationItem(
                        file_path="src/services/auth.ts",
                        explanation="Contains refreshToken function which directly handles token renewal.",
                    )
                ],
            )
        raise ValueError(f"Unexpected output_type: {output_type}")


def test_localize_bug_endpoint_returns_ranked_candidates() -> None:
    app.dependency_overrides[get_llm_service] = FakeLLMService
    app.dependency_overrides[get_embedding_service] = FakeEmbeddingService
    app.dependency_overrides[get_qdrant_service] = FakeQdrantService

    client = TestClient(app)
    response = client.post(
        "/api/bugs/localize",
        headers={"Authorization": "Bearer test-service-key-for-pytest"},
        json={
            "repository_id": "repo-123",
            "issue": {
                "number": 42,
                "title": "Token refresh fails intermittently",
                "body": "Users are encountering InvalidTokenError: jwt expired when calling /api/auth/refresh",
            },
            "files": [
                {
                    "file_id": "file-1",
                    "path": "src/services/auth.ts",
                    "content": "export async function refreshToken(token: string) {\n  if (!token) throw new Error();\n}\n",
                },
                {
                    "file_id": "file-2",
                    "path": "src/routes/auth.routes.ts",
                    "content": "import { refreshToken } from '../services/auth';\n",
                },
            ],
            "commit_history": [
                {
                    "sha": "abc1234",
                    "message": "fix: resolve token refresh race condition",
                    "files": [
                        {"filename": "src/services/auth.ts", "additions": 5, "deletions": 2, "status": "modified"}
                    ],
                }
            ],
            "top_k": 3,
            "include_explanation": True,
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["repository_id"] == "repo-123"
    assert data["issue_analysis"]["problem_summary"] == "Token refresh fails intermittently during session renewal"
    assert len(data["candidates"]) >= 1

    top_candidate = data["candidates"][0]
    assert top_candidate["file_path"] == "src/services/auth.ts"
    assert top_candidate["rank"] == 1
    assert top_candidate["final_score"] > 0.0
    assert top_candidate["confidence"] > 0.0

    # Verify all 5 signals exist and are bounded [0, 1]
    signals = top_candidate["signals"]
    for signal_name in ("semantic_similarity", "keyword_score", "dependency_score", "path_score", "historical_score"):
        assert signal_name in signals
        assert 0.0 <= signals[signal_name] <= 1.0

    assert "refreshToken" in top_candidate["evidence"]["matched_symbols"] or "refreshToken" in top_candidate["evidence"]["matched_keywords"]
    assert top_candidate["explanation"] is not None

    app.dependency_overrides.clear()
