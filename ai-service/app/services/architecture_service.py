import logging
from collections import defaultdict
from pathlib import PurePosixPath

from app.api.schemas.architecture import (
    ArchitectureData,
    ArchitectureEdge,
    ArchitectureNode,
    ArchitectureRequest,
    ArchitectureStatistics,
    SemanticArchitecture,
)
from app.services.architecture_agent import ArchitectureAgent
from app.services.llm_service import get_llm_service
from app.services.repository_service import to_code_documents
from app.utils.parsing import extract_imports, resolve_import

logger = logging.getLogger("repowise.ai.architecture_service")


class ArchitectureService:
    """Combines semantic human-level architecture with deterministic code hierarchy."""

    def __init__(self) -> None:
        try:
            self._agent = ArchitectureAgent(get_llm_service())
        except Exception as e:
            logger.info("LLM service not initialized for architecture agent: %s", e)
            self._agent = ArchitectureAgent(None)

    def analyze(self, request: ArchitectureRequest) -> ArchitectureData:
        documents, _ = to_code_documents(request.repository_id, request.files)

        # 1. Semantic Architecture Discovery (LLM + Agent with Fallback)
        semantic_arch: SemanticArchitecture = self._agent.discover_architecture(
            request.repository_id,
            documents,
        )

        # 2. Deterministic Hierarchical File Graph (For Secondary / Drill-down view)
        file_paths: set[str] = set()
        path_to_language: dict[str, str] = {}
        path_to_lines: dict[str, int] = {}
        path_to_content: dict[str, str] = {}

        for doc in documents:
            file_paths.add(doc.file_path)
            path_to_language[doc.file_path] = doc.language
            path_to_lines[doc.file_path] = doc.content.count("\n") + 1
            path_to_content[doc.file_path] = doc.content

        folder_paths: set[str] = set()
        for file_path in file_paths:
            parts = PurePosixPath(file_path).parts
            for i in range(1, len(parts)):
                folder_paths.add(str(PurePosixPath(*parts[:i])))

        children_count: dict[str, int] = defaultdict(int)
        for file_path in file_paths:
            parent = str(PurePosixPath(file_path).parent)
            if parent != ".":
                children_count[parent] += 1
        for folder_path in folder_paths:
            parent = str(PurePosixPath(folder_path).parent)
            if parent != "." and parent in folder_paths:
                children_count[parent] += 1

        nodes: list[ArchitectureNode] = []
        for folder_path in sorted(folder_paths):
            nodes.append(
                ArchitectureNode(
                    id=f"folder:{folder_path}",
                    label=PurePosixPath(folder_path).name,
                    type="folder",
                    path=folder_path,
                    children_count=children_count.get(folder_path, 0),
                )
            )

        for file_path in sorted(file_paths):
            nodes.append(
                ArchitectureNode(
                    id=f"file:{file_path}",
                    label=PurePosixPath(file_path).name,
                    type="file",
                    language=path_to_language[file_path],
                    path=file_path,
                    lines_of_code=path_to_lines[file_path],
                )
            )

        edges: list[ArchitectureEdge] = []
        for folder_path in sorted(folder_paths):
            parent = str(PurePosixPath(folder_path).parent)
            if parent != "." and parent in folder_paths:
                edges.append(
                    ArchitectureEdge(
                        source=f"folder:{parent}",
                        target=f"folder:{folder_path}",
                        type="CONTAINS",
                    )
                )

        for file_path in sorted(file_paths):
            parent = str(PurePosixPath(file_path).parent)
            if parent != "." and parent in folder_paths:
                edges.append(
                    ArchitectureEdge(
                        source=f"folder:{parent}",
                        target=f"file:{file_path}",
                        type="CONTAINS",
                    )
                )

        dependency_count = 0
        seen: set[tuple[str, str]] = set()
        for file_path in sorted(file_paths):
            language = path_to_language[file_path]
            content = path_to_content[file_path]
            for module in extract_imports(content, language):
                target_path = resolve_import(file_path, module, file_paths, language)
                if target_path is None:
                    continue
                source_id = f"file:{file_path}"
                target_id = f"file:{target_path}"
                if (source_id, target_id) not in seen:
                    seen.add((source_id, target_id))
                    edges.append(
                        ArchitectureEdge(
                            source=source_id,
                            target=target_id,
                            type="IMPORTS",
                        )
                    )
                    dependency_count += 1

        return ArchitectureData(
            repository_id=request.repository_id,
            architecture=semantic_arch,
            nodes=nodes,
            edges=edges,
            statistics=ArchitectureStatistics(
                files=len(file_paths),
                folders=len(folder_paths),
                dependencies=dependency_count,
            ),
        )
