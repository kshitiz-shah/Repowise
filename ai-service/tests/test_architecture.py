import os

os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key-for-pytest")

from app.api.schemas.architecture import ArchitectureRequest
from app.api.schemas.repository import RepositoryFile
from app.main import app
from app.services.architecture_service import ArchitectureService
from app.utils.chunking import chunk_document
from app.models.document import CodeDocument
from fastapi.testclient import TestClient


def test_architecture_resolves_local_typescript_imports() -> None:
    result = ArchitectureService().analyze(ArchitectureRequest(
        repository_id="repo-1",
        files=[
            RepositoryFile(file_id="server", path="src/server.ts", content="import { authenticate } from './auth';\nexport const app = authenticate;"),
            RepositoryFile(file_id="auth", path="src/auth.ts", content="export function authenticate() { return true; }"),
        ],
    ))

    assert [node.id for node in result.nodes] == ["server", "auth"]
    assert result.edges[0].model_dump() == {"source": "server", "target": "auth", "type": "IMPORT"}


def test_chunking_preserves_line_metadata_and_declaration_boundaries() -> None:
    document = CodeDocument("repo-1", "file-1", "app.py", "\n".join(["# setup"] * 20 + ["def login():", "    return True"] + ["# auth"] * 20 + ["def logout():", "    return True"]), "python")
    chunks = chunk_document(document, max_lines=120)

    assert len(chunks) == 3
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 20
    assert chunks[2].start_line == 43
    assert "def logout" in chunks[2].content


def test_architecture_endpoint_returns_a_drawable_graph() -> None:
    response = TestClient(app).post("/api/architecture/analyze", headers={"Authorization": "Bearer test-service-key-for-pytest"}, json={
        "repository_id": "repo-1",
        "files": [
            {"file_id": "server", "path": "src/server.ts", "content": "import { authenticate } from './auth';"},
            {"file_id": "auth", "path": "src/auth.ts", "content": "export function authenticate() { return true; }"},
        ],
    })

    assert response.status_code == 200
    assert response.json()["data"]["edges"] == [{"source": "server", "target": "auth", "type": "IMPORT"}]
