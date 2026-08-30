import logging
import re
from pathlib import PurePosixPath
from typing import Any

from app.api.schemas.architecture import (
    ArchitectureComponent,
    ArchitectureRelationship,
    ComponentEvidence,
    SemanticArchitecture,
)
from app.models.document import CodeDocument
from app.services.llm_service import LLMService, LLMUnavailableError
from app.utils.parsing import extract_imports, resolve_import

logger = logging.getLogger("repowise.ai.architecture_agent")


class ArchitectureAgent:
    """Agent that synthesizes a human-level system architecture from static repository evidence."""

    def __init__(self, llm: LLMService | None = None) -> None:
        self._llm = llm

    def discover_architecture(
        self,
        repository_id: str,
        documents: list[CodeDocument],
    ) -> SemanticArchitecture:
        if not documents:
            return SemanticArchitecture(
                title="Empty Repository",
                summary="No source files were available to analyze.",
                components=[],
                relationships=[],
            )

        # 1. Extract static repository signals
        context = self._build_repository_context(documents)

        # 2. Try LLM semantic synthesis if LLM service is available
        if self._llm:
            try:
                semantic_arch = self._synthesize_with_llm(repository_id, context, documents)
                validated = self._validate_and_sanitize(semantic_arch, documents)
                if validated.components:
                    return validated
            except Exception as e:
                logger.warning("LLM architecture synthesis failed, using deterministic fallback: %s", e)

        # 3. Deterministic structural fallback
        return self._generate_structural_fallback(repository_id, documents, context)

    def _build_repository_context(self, documents: list[CodeDocument]) -> dict[str, Any]:
        file_paths = [doc.file_path for doc in documents]
        path_set = set(file_paths)

        # Detect entry points
        entry_points: list[str] = []
        configs: list[dict[str, str]] = []
        file_summaries: list[dict[str, Any]] = []

        entry_patterns = {
            "main.ts", "server.ts", "app.ts", "index.ts", "main.py", "app.py",
            "run.py", "server.py", "App.tsx", "main.tsx", "index.js", "server.js",
            "main.go", "Cargo.toml", "pom.xml"
        }

        config_names = {
            "package.json", "requirements.txt", "pyproject.toml", "docker-compose.yml",
            "Dockerfile", "schema.prisma", "tsconfig.json", "vite.config.ts", "go.mod"
        }

        # Identify frameworks & tech from content
        detected_tech = set()
        for doc in documents:
            p_name = PurePosixPath(doc.file_path).name
            if p_name in entry_patterns:
                entry_points.append(doc.file_path)

            if p_name in config_names or doc.file_path.endswith((".env.example", "schema.prisma", "compose.yml")):
                # Extract first 40 lines of config
                sample = "\n".join(doc.content.splitlines()[:40])
                configs.append({"path": doc.file_path, "sample": sample})

            # Check framework signatures
            lower_content = doc.content.lower()
            if "express" in lower_content:
                detected_tech.add("Express.js")
            if "fastapi" in lower_content:
                detected_tech.add("FastAPI")
            if "react" in lower_content:
                detected_tech.add("React")
            if "prisma" in lower_content or "schema.prisma" in doc.file_path:
                detected_tech.add("Prisma ORM")
            if "postgres" in lower_content:
                detected_tech.add("PostgreSQL")
            if "qdrant" in lower_content:
                detected_tech.add("Qdrant Vector DB")
            if "jwt" in lower_content or "jsonwebtoken" in lower_content:
                detected_tech.add("JWT Authentication")

            # Extract compact file summary
            imports = extract_imports(doc.content, doc.language)
            local_imports = [imp for imp in imports if resolve_import(doc.file_path, imp, path_set, doc.language)]
            file_summaries.append({
                "path": doc.file_path,
                "language": doc.language,
                "lines": doc.content.count("\n") + 1,
                "imports_count": len(imports),
                "local_imports": local_imports[:8],
            })

        # Group directory clusters
        dir_clusters: dict[str, list[str]] = {}
        for doc in documents:
            parent = str(PurePosixPath(doc.file_path).parent)
            top_dir = parent.split("/")[0] if "/" in parent else parent
            dir_clusters.setdefault(top_dir, []).append(doc.file_path)

        return {
            "total_files": len(documents),
            "entry_points": entry_points[:10],
            "detected_technologies": list(detected_tech),
            "configs": configs[:6],
            "directory_clusters": {k: len(v) for k, v in dir_clusters.items()},
            "files": file_summaries[:75],  # Compact context window limit
        }

    def _synthesize_with_llm(
        self,
        repository_id: str,
        context: dict[str, Any],
        documents: list[CodeDocument],
    ) -> SemanticArchitecture:
        if not self._llm:
            raise LLMUnavailableError("No LLM service configured")

        prompt = f"""You are a Principal Software Architect analyzing an unfamiliar repository.
Repository ID: {repository_id}

STATIC CODE ANALYSIS & SIGNALS:
- Detected Technologies / Frameworks: {", ".join(context["detected_technologies"]) or "Standard"}
- Entry Points: {", ".join(context["entry_points"]) or "None identified"}
- Directory Structure & File Counts: {context["directory_clusters"]}
- Config / Manifest Files:
{self._format_configs(context["configs"])}

FILES & LOCAL IMPORTS (Sample):
{self._format_files(context["files"])}

YOUR GOAL:
Group this repository into 4 to 8 meaningful, high-level ARCHITECTURAL COMPONENTS (subsystems), similar to how a staff engineer draws a system diagram on a whiteboard.
DO NOT list raw individual files as components. Group related files into coherent logical components (e.g. Frontend, API Layer, Authentication Service, Data Access / Database, AI Service, Worker, etc.).

REQUIREMENTS:
1. "title": Short descriptive architecture title (e.g. "RepoWise Multi-Service Architecture").
2. "summary": 2-4 sentences explaining the high-level system architecture, data flow, and technologies.
3. "components": List of 4 to 8 architectural components. Each component must contain:
   - "id": lowercase slug (e.g. "frontend", "api_gateway", "auth_service", "database", "ai_service")
   - "name": human title (e.g. "Frontend Client", "API Gateway", "Authentication Service")
   - "type": one of "frontend", "backend", "api", "service", "database", "cache", "queue", "authentication", "business_logic", "data_access", "storage", "infrastructure", "middleware", "custom"
   - "description": 1-2 sentence human explanation of what this component does.
   - "responsibilities": 2-4 key responsibilities.
   - "files": exact file paths from the repository that implement this component.
   - "evidence": {{"files": [...], "imports": [...], "keywords": [...]}}
4. "relationships": List of directional semantic relationships between components.
   - "source": component id
   - "target": component id
   - "type": one of "HTTP_REQUEST", "CALLS", "QUERIES", "AUTHENTICATES", "READS_FROM", "WRITES_TO", "USES", "STORES_IN", "DEPENDS_ON"
   - "label": short 1-2 word label for the diagram (e.g. "HTTP", "Calls", "Queries", "Auth tokens", "User data")
   - "description": short explanation of why and how they interact.

STRICT RULE: Do NOT invent external databases/queues unless evidence is present in the provided configs or code.

Return valid JSON matching the schema."""

        return self._llm.generate_structured(prompt, SemanticArchitecture)

    def _format_configs(self, configs: list[dict[str, str]]) -> str:
        out = []
        for cfg in configs:
            out.append(f"--- {cfg['path']} ---\n{cfg['sample']}\n")
        return "\n".join(out) or "No config files found"

    def _format_files(self, files: list[dict[str, Any]]) -> str:
        out = []
        for f in files:
            imports = f", imports: {f['local_imports']}" if f["local_imports"] else ""
            out.append(f"- {f['path']} ({f['language']}, {f['lines']} lines{imports})")
        return "\n".join(out)

    def _validate_and_sanitize(
        self,
        arch: SemanticArchitecture,
        documents: list[CodeDocument],
    ) -> SemanticArchitecture:
        all_paths = {doc.file_path for doc in documents}
        valid_comp_ids = set()
        sanitized_components: list[ArchitectureComponent] = []

        for comp in arch.components:
            comp_id = re.sub(r"[^a-z0-9_-]", "_", comp.id.lower().strip()) or "component"
            if comp_id in valid_comp_ids:
                comp_id = f"{comp_id}_{len(valid_comp_ids)}"
            valid_comp_ids.add(comp_id)

            # Filter files to those actually in repo
            matched_files = [f for f in comp.files if f in all_paths]
            if not matched_files:
                # If LLM guessed partial path, match by basename/suffix
                for f in comp.files:
                    target = next((p for p in all_paths if p.endswith(f) or f.endswith(p)), None)
                    if target and target not in matched_files:
                        matched_files.append(target)

            evidence_files = [f for f in comp.evidence.files if f in all_paths] or matched_files[:5]

            sanitized_components.append(
                ArchitectureComponent(
                    id=comp_id,
                    name=comp.name or comp_id.replace("_", " ").title(),
                    type=comp.type or "service",
                    description=comp.description or f"Handles {comp.name} operations.",
                    responsibilities=comp.responsibilities or ["Core subsystem responsibility"],
                    files=matched_files,
                    evidence=ComponentEvidence(
                        files=evidence_files,
                        imports=comp.evidence.imports[:8],
                        keywords=comp.evidence.keywords[:8],
                    ),
                )
            )

        # Sanitize relationships
        sanitized_relationships: list[ArchitectureRelationship] = []
        seen_rel = set()
        for rel in arch.relationships:
            src = re.sub(r"[^a-z0-9_-]", "_", rel.source.lower().strip())
            tgt = re.sub(r"[^a-z0-9_-]", "_", rel.target.lower().strip())

            if src in valid_comp_ids and tgt in valid_comp_ids and src != tgt:
                key = (src, tgt, rel.type)
                if key not in seen_rel:
                    seen_rel.add(key)
                    sanitized_relationships.append(
                        ArchitectureRelationship(
                            source=src,
                            target=tgt,
                            type=rel.type or "CALLS",
                            label=rel.label or "Interacts with",
                            description=rel.description,
                        )
                    )

        title = arch.title or "System Architecture"
        summary = arch.summary or "High-level modular architecture of the application."

        return SemanticArchitecture(
            title=title,
            summary=summary,
            components=sanitized_components,
            relationships=sanitized_relationships,
        )

    def _generate_structural_fallback(
        self,
        repository_id: str,
        documents: list[CodeDocument],
        context: dict[str, Any],
    ) -> SemanticArchitecture:
        """Deterministic architectural clustering fallback when LLM is unavailable."""
        all_paths = {doc.file_path for doc in documents}
        dir_to_files: dict[str, list[str]] = {}

        for doc in documents:
            parts = PurePosixPath(doc.file_path).parts
            if len(parts) > 1:
                cluster_key = f"{parts[0]}/{parts[1]}" if len(parts) > 2 and parts[0] in ("src", "app", "server", "client") else parts[0]
            else:
                cluster_key = "root"
            dir_to_files.setdefault(cluster_key, []).append(doc.file_path)

        components: list[ArchitectureComponent] = []
        for key, files in dir_to_files.items():
            comp_id = re.sub(r"[^a-z0-9_-]", "_", key.lower())
            readable_name = key.replace("/", " ").replace("_", " ").title()

            comp_type = "service"
            if any(term in key.lower() for term in ("client", "frontend", "ui", "web")):
                comp_type = "frontend"
            elif any(term in key.lower() for term in ("api", "route", "controller")):
                comp_type = "api"
            elif any(term in key.lower() for term in ("auth", "login", "jwt")):
                comp_type = "authentication"
            elif any(term in key.lower() for term in ("db", "database", "model", "prisma", "repo")):
                comp_type = "data_access"
            elif any(term in key.lower() for term in ("ai", "ml", "rag", "embed")):
                comp_type = "service"

            components.append(
                ArchitectureComponent(
                    id=comp_id,
                    name=readable_name,
                    type=comp_type,
                    description=f"Subsystem managing {readable_name.lower()} components and files.",
                    responsibilities=[f"Manage {readable_name} operations", f"Process {len(files)} subsystem files"],
                    files=files,
                    evidence=ComponentEvidence(
                        files=files[:5],
                        keywords=[key, comp_type],
                    ),
                )
            )

        # Build relationships from cross-cluster imports
        file_to_comp = {f: c.id for c in components for f in c.files}
        relationships: list[ArchitectureRelationship] = []
        seen = set()

        for doc in documents:
            src_comp = file_to_comp.get(doc.file_path)
            if not src_comp:
                continue
            for module in extract_imports(doc.content, doc.language):
                target_path = resolve_import(doc.file_path, module, all_paths, doc.language)
                if target_path:
                    tgt_comp = file_to_comp.get(target_path)
                    if tgt_comp and tgt_comp != src_comp and (src_comp, tgt_comp) not in seen:
                        seen.add((src_comp, tgt_comp))
                        relationships.append(
                            ArchitectureRelationship(
                                source=src_comp,
                                target=tgt_comp,
                                type="CALLS",
                                label="Calls",
                                description=f"{src_comp} imports modules from {tgt_comp}",
                            )
                        )

        tech_str = ", ".join(context["detected_technologies"]) if context["detected_technologies"] else "standard modular patterns"
        summary = (
            f"Structural architecture containing {len(components)} primary subsystems "
            f"utilizing {tech_str}."
        )

        return SemanticArchitecture(
            title="System Architecture",
            summary=summary,
            components=components,
            relationships=relationships,
        )
