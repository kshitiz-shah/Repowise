from pathlib import PurePosixPath

from app.api.schemas.architecture import ArchitectureData, ArchitectureEdge, ArchitectureNode, ArchitectureRequest
from app.services.repository_service import to_code_documents
from app.utils.parsing import extract_imports, resolve_import


class ArchitectureService:
    """Creates a deterministic file dependency graph; an LLM is not needed here."""

    def analyze(self, request: ArchitectureRequest) -> ArchitectureData:
        documents, _ = to_code_documents(request.repository_id, request.files)
        paths = {document.file_path for document in documents}
        path_to_id = {document.file_path: document.file_id for document in documents}
        nodes = [ArchitectureNode(id=document.file_id, label=PurePosixPath(document.file_path).name, language=document.language) for document in documents]
        edges: list[ArchitectureEdge] = []
        seen: set[tuple[str, str]] = set()
        for document in documents:
            for module in extract_imports(document.content, document.language):
                target_path = resolve_import(document.file_path, module, paths, document.language)
                if target_path and (document.file_id, target_path) not in seen:
                    seen.add((document.file_id, target_path))
                    edges.append(ArchitectureEdge(source=document.file_id, target=path_to_id[target_path], type="IMPORT"))
        return ArchitectureData(repository_id=request.repository_id, nodes=nodes, edges=edges)
