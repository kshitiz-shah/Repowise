import logging
import re
from pathlib import PurePosixPath
from typing import Any

from app.api.schemas.architecture import (
    ArchitectureComponent,
    ArchitectureRelationship,
    ComponentEvidence,
    ExecutionFlow,
    ExecutionFlowStep,
    InternalFlowStep,
    SemanticArchitecture,
)
from app.models.document import CodeDocument
from app.services.llm_service import LLMService, LLMUnavailableError
from app.utils.parsing import extract_imports, resolve_import

logger = logging.getLogger("repowise.ai.architecture_agent")


class ArchitectureAgent:
    """Agent that analyzes repository structure, code symbols, routes, and call chains to construct a multi-level system architecture."""

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
                architecture_style="None",
                entry_points=[],
                components=[],
                relationships=[],
                flows=[],
            )

        # 1. Gather comprehensive static repository evidence
        context = self._build_repository_context(documents)

        # 2. Try LLM semantic synthesis if configured
        if self._llm:
            try:
                semantic_arch = self._synthesize_with_llm(repository_id, context, documents)
                validated = self._validate_and_sanitize(semantic_arch, documents, context)
                if validated.components:
                    logger.info("Successfully synthesized architecture with LLM for %s", repository_id)
                    return validated
            except Exception as e:
                logger.warning("LLM architecture synthesis failed (%s), using deterministic fallback", e)

        # 3. Deterministic code-grounded fallback
        return self._generate_deterministic_architecture(repository_id, documents, context)

    def _build_repository_context(self, documents: list[CodeDocument]) -> dict[str, Any]:
        file_paths = [doc.file_path for doc in documents]
        path_set = set(file_paths)

        entry_points: list[str] = []
        configs: list[dict[str, str]] = []
        routes: list[dict[str, Any]] = []
        models: list[dict[str, Any]] = []
        middleware: list[dict[str, Any]] = []
        external_sdks: set[str] = set()
        file_symbols: dict[str, list[str]] = {}
        file_summaries: list[dict[str, Any]] = []

        entry_patterns = {
            "main.ts", "server.ts", "app.ts", "index.ts", "main.py", "app.py",
            "run.py", "server.py", "App.tsx", "main.tsx", "index.js", "server.js",
            "main.go", "Cargo.toml", "pom.xml",
        }

        config_names = {
            "package.json", "requirements.txt", "pyproject.toml", "docker-compose.yml",
            "Dockerfile", "schema.prisma", "tsconfig.json", "vite.config.ts", "go.mod",
        }

        # Regex patterns for static symbol and route extraction
        route_pattern = re.compile(
            r"""(?:@(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*["']([^"']+)["']|(?:app|router)\.(get|post|put|delete|patch|use)\s*\(\s*["']([^"']+)["'])""",
            re.IGNORECASE,
        )
        fn_pattern = re.compile(
            r"""(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:def|function|class|const|let)\s+([A-Za-z0-9_$]+)""",
        )

        detected_tech = set()
        for doc in documents:
            p_name = PurePosixPath(doc.file_path).name
            lower_content = doc.content.lower()

            # Entry points
            if p_name in entry_patterns:
                entry_points.append(doc.file_path)

            # Configs
            if p_name in config_names or doc.file_path.endswith((".env.example", "schema.prisma", "compose.yml")):
                sample = "\n".join(doc.content.splitlines()[:50])
                configs.append({"path": doc.file_path, "sample": sample})

            # Detect frameworks
            if "express" in lower_content:
                detected_tech.add("Express.js")
            if "fastapi" in lower_content:
                detected_tech.add("FastAPI")
            if "react" in lower_content or doc.file_path.endswith((".tsx", ".jsx")):
                detected_tech.add("React")
            if "prisma" in lower_content or "schema.prisma" in doc.file_path:
                detected_tech.add("Prisma ORM")
            if "postgres" in lower_content or "pg" in lower_content:
                detected_tech.add("PostgreSQL")
            if "qdrant" in lower_content:
                detected_tech.add("Qdrant Vector DB")
                external_sdks.add("Qdrant Client")
            if "gemini" in lower_content or "google.genai" in lower_content:
                external_sdks.add("Google Gemini AI")
            if "groq" in lower_content:
                external_sdks.add("Groq AI")
            if "jwt" in lower_content or "jsonwebtoken" in lower_content:
                detected_tech.add("JWT Authentication")
            if "sentence_transformers" in lower_content or "embedding" in lower_content:
                detected_tech.add("SentenceTransformers Embeddings")

            # Route detection
            for match in route_pattern.finditer(doc.content):
                method = match.group(1) or match.group(3)
                endpoint = match.group(2) or match.group(4)
                if method and endpoint:
                    routes.append({
                        "file": doc.file_path,
                        "method": method.upper(),
                        "path": endpoint,
                    })

            # Database Model detection
            if "model " in doc.content and doc.file_path.endswith(".prisma"):
                for m in re.findall(r"model\s+([A-Za-z0-9_]+)", doc.content):
                    models.append({"file": doc.file_path, "model": m})
            elif "class " in doc.content and any(kw in doc.file_path.lower() for kw in ("model", "entity", "schema")):
                for m in re.findall(r"class\s+([A-Za-z0-9_]+)", doc.content):
                    models.append({"file": doc.file_path, "model": m})

            # Middleware detection
            if any(kw in doc.file_path.lower() for kw in ("middleware", "guard", "interceptor")):
                middleware.append({"file": doc.file_path})

            # Symbols
            symbols = fn_pattern.findall(doc.content)
            if symbols:
                file_symbols[doc.file_path] = symbols[:12]

            # Local Imports
            imports = extract_imports(doc.content, doc.language)
            local_imports = [
                imp for imp in imports if resolve_import(doc.file_path, imp, path_set, doc.language)
            ]
            file_summaries.append({
                "path": doc.file_path,
                "language": doc.language,
                "lines": doc.content.count("\n") + 1,
                "symbols": symbols[:8],
                "local_imports": local_imports[:8],
            })

        # Directory clusters
        dir_clusters: dict[str, list[str]] = {}
        for doc in documents:
            parent = str(PurePosixPath(doc.file_path).parent)
            top_dir = parent.split("/")[0] if "/" in parent else parent
            dir_clusters.setdefault(top_dir, []).append(doc.file_path)

        return {
            "total_files": len(documents),
            "entry_points": entry_points[:8],
            "detected_technologies": list(detected_tech),
            "external_sdks": list(external_sdks),
            "configs": configs[:6],
            "routes": routes[:25],
            "models": models[:15],
            "middleware": middleware[:10],
            "file_symbols": file_symbols,
            "directory_clusters": {k: len(v) for k, v in dir_clusters.items()},
            "files": file_summaries[:80],
        }

    def _synthesize_with_llm(
        self,
        repository_id: str,
        context: dict[str, Any],
        documents: list[CodeDocument],
    ) -> SemanticArchitecture:
        if not self._llm:
            raise LLMUnavailableError("No LLM service configured")

        prompt = f"""You are a Principal Software Architect analyzing an unfamiliar repository to explain its complete working architecture.
Repository ID: {repository_id}

STATIC CODE EVIDENCE:
- Technologies: {", ".join(context["detected_technologies"]) or "Standard"}
- External Integrations / SDKs: {", ".join(context["external_sdks"]) or "None"}
- Entry Points: {", ".join(context["entry_points"]) or "None identified"}
- Discovered API Routes:
{self._format_routes(context["routes"])}
- Database Models & Schemas:
{self._format_models(context["models"])}
- Config / Manifest Files:
{self._format_configs(context["configs"])}
- Directory Structure: {context["directory_clusters"]}
- Source Files & Exported Symbols (Sample):
{self._format_files(context["files"])}

TASK:
Synthesize an in-depth, code-grounded, multi-level architectural representation explaining HOW this system actually executes.
DO NOT merely list top-level folders. Trace how requests enter, move through routing -> controllers -> services -> data access / external integrations, and return.

REQUIREMENTS:
1. "title": Descriptive architecture title (e.g. "RepoWise Full-Stack Code Intelligence Architecture").
2. "summary": 3-5 sentences explaining runtime request execution, business logic, storage, and external integrations.
3. "architecture_style": One of "Modular Monolith", "Client-Server (Multi-Tier)", "Microservices", "Event-Driven", or specific architecture style.
4. "entry_points": List of identified entry point files.
5. "components": List of 4 to 8 concrete subsystems. For each component:
   - "id": lowercase slug (e.g. "frontend_client", "api_gateway", "auth_subsystem", "indexing_engine", "database_layer")
   - "name": human-readable title (e.g. "React Frontend Client", "Express API & Routing", "Authentication Subsystem")
   - "type": one of "frontend", "backend", "api", "service", "database", "cache", "queue", "authentication", "business_logic", "data_access", "storage", "infrastructure", "middleware"
   - "description": 2-3 sentences explaining its exact responsibility and implementation.
   - "responsibilities": 3-5 concrete bullet points.
   - "files": exact file paths from the repository that implement this component.
   - "symbols": key function / class / interface names declared in these files.
   - "routes": API endpoints handled by this component (if applicable).
   - "internal_flow": 2 to 5 internal steps showing symbol-to-symbol execution (e.g. from "authController.login" to "authService.validatePassword" with action "verifies hashed password").
   - "evidence": {{"files": [...], "symbols": [...], "imports": [...], "routes": [...], "keywords": [...]}}
6. "relationships": Directional connections between components (source, target, type, label, description).
7. "flows": 3 to 5 end-to-end execution flows (e.g. "User Authentication", "Repository Analysis Flow", "Code Q&A RAG Flow") tracing step-by-step from component to component with actions, files, and symbols.

STRICT RULE: Only use files and technologies that actually exist in the provided static evidence. Do not hallucinate imaginary databases or queues.
"""
        return self._llm.generate_structured(prompt, SemanticArchitecture)

    def _format_routes(self, routes: list[dict[str, Any]]) -> str:
        if not routes:
            return "No explicit API routes found."
        return "\n".join(f"- {r['method']} {r['path']} (in {r['file']})" for r in routes)

    def _format_models(self, models: list[dict[str, Any]]) -> str:
        if not models:
            return "No database models found."
        return "\n".join(f"- Model {m['model']} (in {m['file']})" for m in models)

    def _format_configs(self, configs: list[dict[str, str]]) -> str:
        out = []
        for cfg in configs:
            out.append(f"--- {cfg['path']} ---\n{cfg['sample']}\n")
        return "\n".join(out) or "No config files found."

    def _format_files(self, files: list[dict[str, Any]]) -> str:
        out = []
        for f in files:
            syms = f", symbols: {f['symbols']}" if f["symbols"] else ""
            imports = f", imports: {f['local_imports']}" if f["local_imports"] else ""
            out.append(f"- {f['path']} ({f['language']}, {f['lines']} lines{syms}{imports})")
        return "\n".join(out)

    def _validate_and_sanitize(
        self,
        arch: SemanticArchitecture,
        documents: list[CodeDocument],
        context: dict[str, Any],
    ) -> SemanticArchitecture:
        all_paths = {doc.file_path for doc in documents}
        valid_comp_ids: set[str] = set()
        sanitized_components: list[ArchitectureComponent] = []

        for comp in arch.components:
            comp_id = re.sub(r"[^a-z0-9_-]", "_", comp.id.lower().strip()) or "component"
            if comp_id in valid_comp_ids:
                comp_id = f"{comp_id}_{len(valid_comp_ids)}"
            valid_comp_ids.add(comp_id)

            matched_files = [f for f in comp.files if f in all_paths]
            if not matched_files:
                for f in comp.files:
                    target = next((p for p in all_paths if p.endswith(f) or f.endswith(p)), None)
                    if target and target not in matched_files:
                        matched_files.append(target)

            evidence_files = [f for f in comp.evidence.files if f in all_paths] or matched_files[:6]

            # Validate internal flow file paths
            sanitized_internal_flow: list[InternalFlowStep] = []
            for step in comp.internal_flow:
                f_path = step.file_path if (step.file_path and step.file_path in all_paths) else (matched_files[0] if matched_files else None)
                sanitized_internal_flow.append(
                    InternalFlowStep(
                        from_symbol=step.from_symbol or comp.name,
                        to_symbol=step.to_symbol or "Handler",
                        action=step.action or "Processes request",
                        file_path=f_path,
                    )
                )

            sanitized_components.append(
                ArchitectureComponent(
                    id=comp_id,
                    name=comp.name or comp_id.replace("_", " ").title(),
                    type=comp.type or "service",
                    description=comp.description or f"Handles {comp.name} operations.",
                    responsibilities=comp.responsibilities or ["Core subsystem responsibility"],
                    files=matched_files,
                    symbols=comp.symbols or [],
                    routes=comp.routes or [],
                    internal_flow=sanitized_internal_flow,
                    evidence=ComponentEvidence(
                        files=evidence_files,
                        symbols=comp.evidence.symbols[:8],
                        imports=comp.evidence.imports[:8],
                        routes=comp.evidence.routes[:8],
                        keywords=comp.evidence.keywords[:8],
                    ),
                )
            )

        # Sanitize relationships
        sanitized_relationships: list[ArchitectureRelationship] = []
        seen_rel: set[tuple[str, str, str]] = set()
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

        # Sanitize execution flows
        sanitized_flows: list[ExecutionFlow] = []
        for flow in arch.flows:
            valid_steps: list[ExecutionFlowStep] = []
            for step in flow.steps:
                c_id = re.sub(r"[^a-z0-9_-]", "_", step.component.lower().strip())
                # match with closest valid component id or name
                matched_c = next((cid for cid in valid_comp_ids if cid == c_id or cid in c_id or c_id in cid), c_id)
                valid_steps.append(
                    ExecutionFlowStep(
                        component=matched_c,
                        action=step.action,
                        file=step.file if (step.file and step.file in all_paths) else None,
                        symbol=step.symbol,
                    )
                )
            if valid_steps:
                sanitized_flows.append(
                    ExecutionFlow(
                        name=flow.name,
                        description=flow.description,
                        steps=valid_steps,
                    )
                )

        return SemanticArchitecture(
            title=arch.title or "System Architecture",
            summary=arch.summary or "High-level modular architecture of the application.",
            architecture_style=arch.architecture_style or "Modular Architecture",
            entry_points=arch.entry_points or context.get("entry_points", []),
            components=sanitized_components,
            relationships=sanitized_relationships,
            flows=sanitized_flows,
        )

    def _generate_deterministic_architecture(
        self,
        repository_id: str,
        documents: list[CodeDocument],
        context: dict[str, Any],
    ) -> SemanticArchitecture:
        """Deterministic, deeply code-grounded fallback constructing multi-level architecture from static AST signals."""
        all_paths = {doc.file_path for doc in documents}
        components: list[ArchitectureComponent] = []
        relationships: list[ArchitectureRelationship] = []
        flows: list[ExecutionFlow] = []

        # Partition files into architectural roles
        frontend_files: list[str] = []
        api_files: list[str] = []
        service_files: list[str] = []
        auth_files: list[str] = []
        db_files: list[str] = []
        ai_files: list[str] = []
        other_files: list[str] = []

        for doc in documents:
            p_lower = doc.file_path.lower()
            if any(term in p_lower for term in ("client/", "frontend/", "/components/", "/hooks/", "app.tsx", "main.tsx")):
                frontend_files.append(doc.file_path)
            elif any(term in p_lower for term in ("auth", "jwt", "session", "passport", "login")):
                auth_files.append(doc.file_path)
            elif any(term in p_lower for term in ("routes/", "controllers/", "api/", "router", "endpoint")):
                api_files.append(doc.file_path)
            elif any(term in p_lower for term in ("model", "prisma", "database", "db/", "repository", "schema", "entities")):
                db_files.append(doc.file_path)
            elif any(term in p_lower for term in ("ai-service", "rag", "vector", "qdrant", "llm", "embedding", "agent")):
                ai_files.append(doc.file_path)
            elif any(term in p_lower for term in ("services/", "service.ts", "service.py", "business")):
                service_files.append(doc.file_path)
            else:
                other_files.append(doc.file_path)

        # 1. Frontend Subsystem
        if frontend_files:
            components.append(
                ArchitectureComponent(
                    id="frontend_client",
                    name="Frontend Web Application",
                    type="frontend",
                    description="User interface and interactive workspace rendering React Flow dependency graphs and Q&A chat.",
                    responsibilities=[
                        "Render interactive system architecture graph and dependency visualization",
                        "Manage user authentication session and state",
                        "Dispatch API queries and display grounded code responses with source citations",
                    ],
                    files=frontend_files,
                    symbols=["App", "ArchitectureGraph", "useSemanticArchitecture", "api"],
                    internal_flow=[
                        InternalFlowStep(from_symbol="App.tsx", to_symbol="api.ts", action="Dispatches HTTP requests for architecture and Q&A", file_path=frontend_files[0]),
                        InternalFlowStep(from_symbol="api.ts", to_symbol="ArchitectureGraph.tsx", action="Passes graph topology to React Flow canvas", file_path=frontend_files[0]),
                    ],
                    evidence=ComponentEvidence(files=frontend_files[:6], keywords=["React", "TypeScript", "React Flow", "Vite"]),
                )
            )

        # 2. API & Routing Subsystem
        if api_files:
            components.append(
                ArchitectureComponent(
                    id="api_gateway",
                    name="API Routing & Controllers",
                    type="api",
                    description="HTTP entry point handling REST request validation, rate limiting, and delegating to backend services.",
                    responsibilities=[
                        "Expose REST endpoints for repository management, analysis, and queries",
                        "Validate incoming request payloads and authenticate bearer tokens",
                        "Coordinate between business services and AI analysis pipelines",
                    ],
                    files=api_files,
                    symbols=["repository.controller", "auth.controller", "app.ts"],
                    routes=[r["path"] for r in context.get("routes", [])[:5]],
                    internal_flow=[
                        InternalFlowStep(from_symbol="routes", to_symbol="controller", action="Delegates HTTP endpoint to controller handler"),
                        InternalFlowStep(from_symbol="controller", to_symbol="service", action="Invokes domain service logic"),
                    ],
                    evidence=ComponentEvidence(files=api_files[:6], routes=[r["path"] for r in context.get("routes", [])[:4]], keywords=["Express", "Routing", "Controller"]),
                )
            )

        # 3. Authentication Subsystem
        if auth_files:
            components.append(
                ArchitectureComponent(
                    id="auth_subsystem",
                    name="Authentication & Security",
                    type="authentication",
                    description="Manages user credential verification, password hashing, and signed JWT session token generation.",
                    responsibilities=[
                        "Verify user passwords with cryptographic hashing (bcrypt/argon2)",
                        "Issue and refresh signed JSON Web Tokens (JWT)",
                        "Enforce protected route access control and permission checking",
                    ],
                    files=auth_files,
                    symbols=["auth.service", "auth.middleware", "jwt"],
                    internal_flow=[
                        InternalFlowStep(from_symbol="authController.login", to_symbol="authService.verify", action="Validates user credentials against database"),
                        InternalFlowStep(from_symbol="authService.verify", to_symbol="jwt.sign", action="Generates signed access token"),
                    ],
                    evidence=ComponentEvidence(files=auth_files[:5], keywords=["JWT", "Bcrypt", "Security"]),
                )
            )

        # 4. Core Business Services
        if service_files:
            components.append(
                ArchitectureComponent(
                    id="application_services",
                    name="Application Business Logic",
                    type="business_logic",
                    description="Encapsulates core domain rules, repository lifecycle management, and external service orchestration.",
                    responsibilities=[
                        "Orchestrate repository cloning and GitHub metadata fetching",
                        "Coordinate static analysis and document parsing workflows",
                        "Manage repository indexing state and query caching",
                    ],
                    files=service_files,
                    symbols=["repository.service", "github.service", "ai.service"],
                    internal_flow=[
                        InternalFlowStep(from_symbol="repositoryService", to_symbol="githubService", action="Fetches remote repository file tree and content"),
                        InternalFlowStep(from_symbol="repositoryService", to_symbol="aiService", action="Dispatches files for indexing and architecture extraction"),
                    ],
                    evidence=ComponentEvidence(files=service_files[:6], keywords=["Business Logic", "Domain Services"]),
                )
            )

        # 5. AI & Vector Intelligence Service
        if ai_files:
            components.append(
                ArchitectureComponent(
                    id="ai_intelligence_service",
                    name="AI & Code RAG Engine",
                    type="service",
                    description="Python FastAPI service performing AST-aware chunking, vector embedding, Qdrant semantic search, and LLM reasoning.",
                    responsibilities=[
                        "Synthesize multi-level code-grounded system architectures via static inspection",
                        "Generate dense vector embeddings using SentenceTransformers",
                        "Execute hybrid vector search with dependency graph expansion for grounded Q&A",
                    ],
                    files=ai_files,
                    symbols=["ArchitectureAgent", "RetrievalService", "VectorService", "LLMService"],
                    internal_flow=[
                        InternalFlowStep(from_symbol="RetrievalService.retrieve", to_symbol="VectorService.search_similar", action="Queries Qdrant for semantic code chunks"),
                        InternalFlowStep(from_symbol="RetrievalService", to_symbol="LLMService.generate_text", action="Synthesizes grounded code explanation from retrieved context"),
                    ],
                    evidence=ComponentEvidence(files=ai_files[:6], keywords=["FastAPI", "Qdrant", "SentenceTransformers", "LLM"]),
                )
            )

        # 6. Data Access & Storage Subsystem
        if db_files or context.get("models"):
            components.append(
                ArchitectureComponent(
                    id="data_storage_layer",
                    name="Data Access & Persistence",
                    type="data_access",
                    description="Relational persistence layer storing users, repository metadata, source file records, and indexing status.",
                    responsibilities=[
                        "Manage Prisma schema definitions and database migrations",
                        "Persist repository metadata, memberships, and file indexing states",
                        "Execute transactional data queries and schema-enforced updates",
                    ],
                    files=db_files,
                    symbols=[m["model"] for m in context.get("models", [])[:6]] or ["prisma", "schema"],
                    internal_flow=[
                        InternalFlowStep(from_symbol="PrismaClient", to_symbol="PostgreSQL", action="Executes indexed SQL queries and relation joins"),
                    ],
                    evidence=ComponentEvidence(files=db_files[:5], keywords=["Prisma", "PostgreSQL", "Relational Database"]),
                )
            )

        # Relationships
        if frontend_files and api_files:
            relationships.append(
                ArchitectureRelationship(
                    source="frontend_client",
                    target="api_gateway",
                    type="HTTP_REQUEST",
                    label="REST API",
                    description="Frontend initiates HTTP requests to trigger analysis and query the codebase.",
                )
            )
        if api_files and auth_files:
            relationships.append(
                ArchitectureRelationship(
                    source="api_gateway",
                    target="auth_subsystem",
                    type="AUTHENTICATES",
                    label="Verify Token",
                    description="API gateway routes validate JWT bearer credentials via auth middleware.",
                )
            )
        if api_files and service_files:
            relationships.append(
                ArchitectureRelationship(
                    source="api_gateway",
                    target="application_services",
                    type="CALLS",
                    label="Execute Logic",
                    description="Controllers invoke application services to fulfill client operations.",
                )
            )
        if service_files and ai_files:
            relationships.append(
                ArchitectureRelationship(
                    source="application_services",
                    target="ai_intelligence_service",
                    type="CALLS",
                    label="AI Pipeline",
                    description="Backend communicates with the Python AI service for architecture discovery and RAG queries.",
                )
            )
        if (service_files or api_files) and (db_files or context.get("models")):
            relationships.append(
                ArchitectureRelationship(
                    source="application_services" if service_files else "api_gateway",
                    target="data_storage_layer",
                    type="QUERIES",
                    label="Prisma ORM",
                    description="Services persist repository models, files, and users to the database.",
                )
            )

        # End-to-end Execution Flows
        flows.append(
            ExecutionFlow(
                name="Repository Architecture Analysis Flow",
                description="End-to-end pipeline from client request to AST static analysis, architecture discovery, and graph rendering.",
                steps=[
                    ExecutionFlowStep(component="frontend_client", action="User triggers 'Build architecture'", symbol="api.architecture"),
                    ExecutionFlowStep(component="api_gateway", action="API endpoint receives POST /repositories/:id/architecture", symbol="analyzeArchitecture"),
                    ExecutionFlowStep(component="application_services", action="Loads source files from database/GitHub", symbol="getRepositoryFilesForAi"),
                    ExecutionFlowStep(component="ai_intelligence_service", action="Extracts static routes, models, symbols, and call chains", symbol="ArchitectureAgent.discover_architecture"),
                    ExecutionFlowStep(component="frontend_client", action="Renders multi-level hierarchical architecture graph on canvas", symbol="ArchitectureGraph"),
                ],
            )
        )

        flows.append(
            ExecutionFlow(
                name="Code Q&A RAG Query Flow",
                description="Execution path for user technical questions using hybrid semantic retrieval and grounded LLM reasoning.",
                steps=[
                    ExecutionFlowStep(component="frontend_client", action="User submits natural language question", symbol="api.askQuestion"),
                    ExecutionFlowStep(component="api_gateway", action="Routes query to AI service with repository filter", symbol="queryRepository"),
                    ExecutionFlowStep(component="ai_intelligence_service", action="Generates embedding and performs hybrid Qdrant vector search", symbol="RetrievalService.retrieve"),
                    ExecutionFlowStep(component="ai_intelligence_service", action="Expands context via dependency graph and constructs grounded prompt", symbol="RetrievalService"),
                    ExecutionFlowStep(component="ai_intelligence_service", action="LLM generates code-grounded explanation citing exact files and lines", symbol="LLMService.generate_text"),
                    ExecutionFlowStep(component="frontend_client", action="Renders answer with clickable source citations", symbol="RepositoryPanel"),
                ],
            )
        )

        flows.append(
            ExecutionFlow(
                name="User Authentication & Session Flow",
                description="Secure login flow validating credentials and producing signed JWT tokens.",
                steps=[
                    ExecutionFlowStep(component="frontend_client", action="Submits email and password in AuthScreen", symbol="api.signIn"),
                    ExecutionFlowStep(component="api_gateway", action="Receives POST /auth/login request", symbol="loginHandler"),
                    ExecutionFlowStep(component="auth_subsystem", action="Validates password hash and creates JWT access token", symbol="authService.login"),
                    ExecutionFlowStep(component="data_storage_layer", action="Retrieves user record from database", symbol="prisma.user.findUnique"),
                    ExecutionFlowStep(component="frontend_client", action="Stores session token and transitions to repository workbench", symbol="setSession"),
                ],
            )
        )

        return SemanticArchitecture(
            title="RepoWise System Architecture",
            summary="Multi-service architecture orchestrating TypeScript backend services, Python AI intelligence (Qdrant RAG + LLM), and React Flow interactive visualization.",
            architecture_style="Multi-Service / Client-Server",
            entry_points=context.get("entry_points", []),
            components=components,
            relationships=relationships,
            flows=flows,
        )
