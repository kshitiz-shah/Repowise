import os

os.environ.setdefault("AI_SERVICE_API_KEY", "test-service-key-for-pytest")

from app.api.schemas.architecture import ArchitectureRequest
from app.api.schemas.repository import RepositoryFile
from app.main import app
from app.services.architecture_service import ArchitectureService
from app.utils.chunking import chunk_document
from app.models.document import CodeDocument
from fastapi.testclient import TestClient


def test_architecture_resolves_local_typescript_imports_hierarchically() -> None:
    result = ArchitectureService().analyze(ArchitectureRequest(
        repository_id="repo-1",
        files=[
            RepositoryFile(file_id="server-uuid", path="src/server.ts", content="import { authenticate } from './auth';\nexport const app = authenticate;"),
            RepositoryFile(file_id="auth-uuid", path="src/auth.ts", content="export function authenticate() { return true; }"),
        ],
    ))

    # File nodes
    node_ids = [node.id for node in result.nodes]
    assert "folder:src" in node_ids
    assert "file:src/server.ts" in node_ids
    assert "file:src/auth.ts" in node_ids

    # CONTAINS edges
    contains_edges = [e for e in result.edges if e.type == "CONTAINS"]
    assert len(contains_edges) == 2
    assert any(e.source == "folder:src" and e.target == "file:src/server.ts" for e in contains_edges)
    assert any(e.source == "folder:src" and e.target == "file:src/auth.ts" for e in contains_edges)

    # IMPORTS edges
    import_edges = [e for e in result.edges if e.type == "IMPORTS"]
    assert len(import_edges) == 1
    assert import_edges[0].source == "file:src/server.ts"
    assert import_edges[0].target == "file:src/auth.ts"

    # Semantic Architecture
    assert result.architecture.title
    assert len(result.architecture.components) > 0
    comp = result.architecture.components[0]
    assert comp.name
    assert comp.description
    assert comp.responsibilities

    # Statistics
    assert result.statistics.files == 2
    assert result.statistics.folders == 1
    assert result.statistics.dependencies == 1


def test_duplicate_filenames_in_different_folders_are_distinct_nodes() -> None:
    result = ArchitectureService().analyze(ArchitectureRequest(
        repository_id="repo-1",
        files=[
            RepositoryFile(file_id="init-a", path="src/a/__init__.py", content="# init a"),
            RepositoryFile(file_id="init-b", path="src/b/__init__.py", content="# init b"),
        ],
    ))

    node_ids = {node.id for node in result.nodes}
    assert "file:src/a/__init__.py" in node_ids
    assert "file:src/b/__init__.py" in node_ids
    assert "folder:src" in node_ids
    assert "folder:src/a" in node_ids
    assert "folder:src/b" in node_ids


def test_chunking_preserves_line_metadata_and_declaration_boundaries() -> None:
    document = CodeDocument("repo-1", "file-1", "app.py", "\n".join(["# setup"] * 20 + ["def login():", "    return True"] + ["# auth"] * 20 + ["def logout():", "    return True"]), "python")
    chunks = chunk_document(document, max_lines=120)

    assert len(chunks) == 3
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 20
    assert chunks[2].start_line == 43
    assert "def logout" in chunks[2].content


def test_architecture_endpoint_returns_semantic_and_hierarchical_data() -> None:
    response = TestClient(app).post("/api/architecture/analyze", headers={"Authorization": "Bearer test-service-key-for-pytest"}, json={
        "repository_id": "repo-1",
        "files": [
            {"file_id": "server", "path": "src/server.ts", "content": "import { authenticate } from './auth';"},
            {"file_id": "auth", "path": "src/auth.ts", "content": "export function authenticate() { return true; }"},
        ],
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert "architecture" in data
    assert "components" in data["architecture"]
    assert "relationships" in data["architecture"]
    assert "summary" in data["architecture"]
    assert data["statistics"] == {"files": 2, "folders": 1, "dependencies": 1}
    assert any(e["type"] == "IMPORTS" and e["source"] == "file:src/server.ts" and e["target"] == "file:src/auth.ts" for e in data["edges"])
    assert any(e["type"] == "CONTAINS" and e["source"] == "folder:src" for e in data["edges"])
