import logging
import re
from pathlib import PurePosixPath
from typing import Any

from app.api.schemas.architecture import (
    ArchitectureComponent,
    ArchitectureGroup,
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
from app.utils.mermaid_compiler import compile_mermaid_architecture

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
            empty_arch = SemanticArchitecture(
                title="Empty Repository",
                summary="No source files were available to analyze.",
                architecture_style="None",
                entry_points=[],
                groups=[],
                components=[],
                relationships=[],
                flows=[],
            )
            empty_arch.mermaid_code = compile_mermaid_architecture(empty_arch)
            return empty_arch

        # 1. Gather comprehensive static repository evidence
        context = self._build_repository_context(documents)

        # 2. Try LLM semantic synthesis if configured
        if self._llm:
            try:
                semantic_arch = self._synthesize_with_llm(repository_id, context, documents)
                validated = self._validate_and_sanitize(semantic_arch, documents, context)
                if validated.components:
                    validated.mermaid_code = compile_mermaid_architecture(validated)
                    logger.info("Successfully synthesized architecture with LLM for %s", repository_id)
                    return validated
            except Exception as e:
                logger.warning("LLM architecture synthesis failed (%s), using deterministic fallback", e)

        # 3. Deterministic code-grounded fallback
        deterministic_arch = self._generate_deterministic_architecture(repository_id, documents, context)
        deterministic_arch.mermaid_code = compile_mermaid_architecture(deterministic_arch)
        return deterministic_arch


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

        # Build a compact but information-rich file listing with actual code snippets
        file_listing = self._format_files(context["files"])

        # Build a sample code snippets section for the most important files
        key_snippets = self._build_key_snippets(documents, context)

        prompt = f"""You are a Principal Software Architect. Analyze this repository and produce a PRECISE system architecture diagram specification.

REPOSITORY: {repository_id}

═══ HARD EVIDENCE (from static code analysis) ═══

Technologies: {", ".join(context["detected_technologies"]) or "Standard"}
External SDKs: {", ".join(context["external_sdks"]) or "None"}
Entry Points: {", ".join(context["entry_points"]) or "Not identified"}
Directory Structure: {context["directory_clusters"]}

API Routes:
{self._format_routes(context["routes"])}

Database Models:
{self._format_models(context["models"])}

Config Files:
{self._format_configs(context["configs"])}

Source Files:
{file_listing}

Key Code Snippets:
{key_snippets}

═══ YOUR TASK ═══

Generate a JSON object with EXACTLY this structure. Every field is required:

{{
  "title": "<Descriptive Title> Architecture",
  "summary": "3-5 sentences explaining how data flows through the system at runtime.",
  "architecture_style": "Client-Server" | "Modular Monolith" | "Microservices" | "Event-Driven" | "Layered",
  "entry_points": ["file1.py", "server.ts"],
  "groups": [
    {{"id": "group_xxx", "label": "Human-Readable Layer Name"}}
  ],
  "components": [
    {{
      "id": "lowercase_slug",
      "name": "Human Readable Name",
      "type": "frontend|backend|api|service|database|cache|queue|authentication|middleware|infrastructure",
      "shape": "box|database|circle|queue|hexagon",
      "group_id": "group_xxx",
      "description": "2-3 sentences on what this does and how.",
      "responsibilities": ["Bullet 1", "Bullet 2", "Bullet 3"],
      "files": ["exact/path/from/evidence.py"],
      "symbols": ["functionName", "ClassName"],
      "routes": ["/api/endpoint"],
      "internal_flow": [
        {{"from_symbol": "handler", "to_symbol": "service", "action": "validates and forwards request", "file_path": "exact/path.py"}}
      ],
      "evidence": {{"files": [], "symbols": [], "imports": [], "routes": [], "keywords": []}}
    }}
  ],
  "relationships": [
    {{"source": "component_id_1", "target": "component_id_2", "type": "CALLS|READS|WRITES|ASYNC|PUBLISHES", "label": "Short verb phrase", "style": "solid|dashed", "description": "One sentence"}}
  ],
  "flows": [
    {{
      "name": "Flow Name (e.g. User Authentication)",
      "description": "How data moves end-to-end for this use case.",
      "steps": [
        {{"component": "component_id", "action": "What happens here", "file": "path/to/file.py", "symbol": "functionName"}}
      ]
    }}
  ]
}}

═══ STRICT RULES ═══

1. ONLY reference files that appear in the Source Files list above. Do NOT invent file paths.
2. Create 4-10 components. Each must map to real files.
3. Create 3-6 groups to organize components into logical layers.
4. Shape rules: "database" for any DB/cache/store, "circle" for user/browser/actor, "queue" for workers/queues, "box" for everything else.
5. Create meaningful relationships showing HOW data flows (not just "interacts with").
6. Create 2-4 end-to-end flows tracing real user scenarios.
7. Component IDs must be lowercase slugs using only [a-z0-9_].
8. Relationship source/target must exactly match component IDs.
9. Return ONLY the JSON object. No markdown fences, no explanation.
"""
        return self._llm.generate_structured(prompt, SemanticArchitecture)

    def _build_key_snippets(self, documents: list[CodeDocument], context: dict[str, Any]) -> str:
        """Extract brief code snippets from the most architecturally significant files."""
        snippets: list[str] = []
        priority_files = set(context.get("entry_points", []))

        # Add route-owning files
        for r in context.get("routes", []):
            priority_files.add(r["file"])

        # Add config files
        for c in context.get("configs", []):
            priority_files.add(c["path"])

        # Grab snippets from priority files, then fill with highest-symbol files
        seen = set()
        for doc in documents:
            if doc.file_path in priority_files and doc.file_path not in seen:
                seen.add(doc.file_path)
                lines = doc.content.splitlines()[:40]
                snippets.append(f"--- {doc.file_path} (first 40 lines) ---\n" + "\n".join(lines))
            if len(snippets) >= 8:
                break

        # Fill remaining slots with files that have the most symbols
        file_syms = context.get("file_symbols", {})
        ranked = sorted(file_syms.items(), key=lambda x: len(x[1]), reverse=True)
        for fpath, syms in ranked:
            if fpath not in seen and len(snippets) < 12:
                seen.add(fpath)
                doc = next((d for d in documents if d.file_path == fpath), None)
                if doc:
                    lines = doc.content.splitlines()[:30]
                    snippets.append(f"--- {fpath} (first 30 lines) ---\n" + "\n".join(lines))

        return "\n\n".join(snippets) if snippets else "No key snippets extracted."


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

        # Validate Groups
        groups = arch.groups or []
        group_id_set = {g.id for g in groups}

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

            # Validate shape
            shape = comp.shape or "box"
            words = f"{comp.name} {comp.type} {comp_id}".lower()
            if shape == "box":
                if any(w in words for w in ("database", "storage", "cache", "postgres", "sqlite", "redis", "qdrant", "prisma")):
                    shape = "database"
                elif any(w in words for w in ("actor", "user", "browser", "client")):
                    shape = "circle"
                elif any(w in words for w in ("queue", "worker", "task", "job")):
                    shape = "queue"

            # Validate group
            group_id = comp.group_id
            if group_id and group_id not in group_id_set:
                group_id = None

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
                    shape=shape,
                    group_id=group_id,
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
                            style=rel.style or "solid",
                            description=rel.description,
                        )
                    )

        # Sanitize execution flows
        sanitized_flows: list[ExecutionFlow] = []
        for flow in arch.flows:
            valid_steps: list[ExecutionFlowStep] = []
            for step in flow.steps:
                c_id = re.sub(r"[^a-z0-9_-]", "_", step.component.lower().strip())
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
            groups=groups,
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
        """Dynamic, code-grounded architecture synthesizer constructing GitDiagram-grade system architecture."""
        all_paths = {doc.file_path for doc in documents}
        
        # 1. Filter out pure test data / fixtures if real source files exist
        source_docs = [
            d for d in documents
            if not any(t in d.file_path.lower() for t in ("/test/", "/tests/", "__test__", ".spec.", ".test.", "/acceptance/"))
        ]
        if not source_docs or len(source_docs) < 3:
            source_docs = documents

        # Build file-level import graph
        file_to_imports: dict[str, list[str]] = {}
        for doc in documents:
            raw_imports = extract_imports(doc.content, doc.language)
            resolved = [
                resolve_import(doc.file_path, imp, all_paths, doc.language)
                for imp in raw_imports
            ]
            file_to_imports[doc.file_path] = [r for r in resolved if r and r in all_paths]

        # Key entry file patterns
        entry_patterns = {
            "index.js", "index.ts", "main.py", "app.py", "server.ts", "server.js",
            "app.ts", "main.go", "app.tsx", "main.tsx", "run.py", "express.js",
        }

        # Role keywords for smarter naming
        ROLE_HINTS = {
            "frontend": {"keywords": ("client", "browser", "user", "frontend", "view", "react", "ui", "template", "component", "page", "layout", ".tsx", ".jsx"), "type": "frontend", "shape": "box", "group_id": "group_ui", "group_label": "Presentation & UI", "suffix": "Interface"},
            "api": {"keywords": ("route", "router", "controller", "api", "endpoint", "request", "response", "http", "handler", "middleware"), "type": "api", "shape": "box", "group_id": "group_http", "group_label": "HTTP & Routing Layer", "suffix": "API"},
            "database": {"keywords": ("database", "storage", "cache", "postgres", "sqlite", "redis", "qdrant", "prisma", "model", "db", "repository", "migration", "schema.prisma"), "type": "database", "shape": "database", "group_id": "group_data", "group_label": "Persistence & Storage", "suffix": "Store"},
            "ai": {"keywords": ("ai", "llm", "rag", "vector", "embedding", "agent", "inference", "genai", "gemini", "groq", "prompt"), "type": "service", "shape": "box", "group_id": "group_ai", "group_label": "AI & Intelligence Engine", "suffix": "Engine"},
            "auth": {"keywords": ("auth", "login", "session", "jwt", "token", "password", "signup", "register"), "type": "authentication", "shape": "box", "group_id": "group_http", "group_label": "HTTP & Routing Layer", "suffix": "Guard"},
            "queue": {"keywords": ("queue", "worker", "job", "event", "task", "scheduler", "cron"), "type": "queue", "shape": "queue", "group_id": "group_core", "group_label": "Core Services", "suffix": "Worker"},
            "util": {"keywords": ("util", "helper", "common", "shared", "parsing", "format", "lib", "tools", "config"), "type": "infrastructure", "shape": "box", "group_id": "group_utils", "group_label": "Utilities & Configuration", "suffix": "Utilities"},
        }

        clusters: dict[str, dict[str, Any]] = {}

        # Strategy: group by meaningful parent directory or top-level source files
        for doc in source_docs:
            p = PurePosixPath(doc.file_path)
            name = p.name
            parent = str(p.parent)

            if parent in (".", "lib", "src", "app") and name in entry_patterns:
                cluster_key = f"entry_{name.split('.')[0]}"
                cluster_name = f"{name.split('.')[0].replace('_', ' ').replace('-', ' ').title()} Entrypoint"
            elif parent != ".":
                parts = p.parts
                if len(parts) >= 2 and parts[0] in ("lib", "src", "app", "packages", "pkg") and len(parts) >= 3:
                    cluster_key = f"{parts[0]}_{parts[1]}"
                    cluster_name = f"{parts[1].replace('_', ' ').replace('-', ' ').title()}"
                elif len(parts) >= 2 and parts[0] in ("lib", "src", "app", "packages", "pkg"):
                    stem = p.stem
                    cluster_key = f"{parts[0]}_{stem}"
                    cluster_name = f"{stem.replace('_', ' ').replace('-', ' ').title()}"
                else:
                    top = parts[0]
                    cluster_key = f"mod_{top}"
                    cluster_name = f"{top.replace('_', ' ').replace('-', ' ').title()}"
            else:
                stem = p.stem
                cluster_key = f"mod_{stem}"
                cluster_name = f"{stem.replace('_', ' ').replace('-', ' ').title()}"

            if cluster_key not in clusters:
                clusters[cluster_key] = {
                    "name": cluster_name,
                    "files": [],
                    "symbols": set(),
                    "routes": [],
                    "languages": set(),
                }
            clusters[cluster_key]["files"].append(doc.file_path)
            clusters[cluster_key]["languages"].add(doc.language)
            if doc.file_path in context.get("file_symbols", {}):
                clusters[cluster_key]["symbols"].update(context["file_symbols"][doc.file_path])

        # If too few clusters, split large ones or create individual file components
        if len(clusters) < 4:
            for doc in source_docs[:14]:
                p = PurePosixPath(doc.file_path)
                c_key = f"file_{p.stem.replace('-', '_').replace('.', '_')}"
                if c_key not in clusters:
                    clusters[c_key] = {
                        "name": f"{p.stem.replace('_', ' ').replace('-', ' ').title()}",
                        "files": [doc.file_path],
                        "symbols": set(context.get("file_symbols", {}).get(doc.file_path, [])),
                        "routes": [],
                        "languages": {doc.language},
                    }

        # Assign discovered routes to clusters
        for route_info in context.get("routes", []):
            route_file = route_info.get("file", "")
            for c_key, data in clusters.items():
                if route_file in data["files"]:
                    data["routes"].append(f"{route_info['method']} {route_info['path']}")
                    break

        # Build Components from Clusters
        components: list[ArchitectureComponent] = []
        file_to_comp_id: dict[str, str] = {}

        # Take up to 14 most meaningful clusters
        sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]["files"]), reverse=True)[:14]

        for c_key, data in sorted_clusters:
            comp_id = re.sub(r"[^a-z0-9_-]", "_", c_key.lower())
            for f in data["files"]:
                file_to_comp_id[f] = comp_id

            # Determine role by matching keywords against file paths and cluster name
            c_text = f"{data['name']} {' '.join(data['files'])}".lower()
            matched_role = None
            for role_name, role_info in ROLE_HINTS.items():
                if any(kw in c_text for kw in role_info["keywords"]):
                    matched_role = role_info
                    break

            if not matched_role:
                matched_role = {"type": "service", "shape": "box", "group_id": "group_core", "group_label": "Core Services", "suffix": "Service"}

            comp_type = matched_role["type"]
            comp_shape = matched_role["shape"]
            group_id = matched_role["group_id"]
            group_label = matched_role["group_label"]

            # Generate a better component name
            base_name = data["name"]
            if not any(w in base_name.lower() for w in ("service", "api", "store", "engine", "guard", "worker", "interface", "utilities", "entrypoint")):
                base_name = f"{base_name} {matched_role['suffix']}"

            sym_list = list(data["symbols"])[:8]
            route_list = data.get("routes", [])[:6]

            # Build richer internal flows
            internal_flows = []
            if len(sym_list) >= 2:
                for i in range(min(3, len(sym_list) - 1)):
                    internal_flows.append(
                        InternalFlowStep(
                            from_symbol=sym_list[i],
                            to_symbol=sym_list[i + 1],
                            action=f"Invokes {sym_list[i + 1]} for processing",
                            file_path=data["files"][0] if data["files"] else None,
                        )
                    )

            key_files = [PurePosixPath(f).name for f in data["files"][:4]]
            responsibilities = [
                f"Manages {len(data['files'])} source files including {', '.join(key_files[:3])}",
                f"Provides {len(sym_list)} exported symbols: {', '.join(sym_list[:4]) or 'internal modules'}",
            ]
            if route_list:
                responsibilities.append(f"Exposes endpoints: {', '.join(route_list[:3])}")
            responsibilities.append(f"Implemented in {', '.join(sorted(data['languages']))}")

            components.append(
                ArchitectureComponent(
                    id=comp_id,
                    name=base_name,
                    type=comp_type,
                    shape=comp_shape,
                    group_id=group_id,
                    group_label=group_label,
                    description=f"{base_name} handles {data['name'].lower()} functionality across {len(data['files'])} files ({', '.join(key_files[:3])}).",
                    responsibilities=responsibilities,
                    files=data["files"][:10],
                    symbols=sym_list,
                    routes=route_list,
                    internal_flow=internal_flows,
                    evidence=ComponentEvidence(
                        files=data["files"][:6],
                        symbols=sym_list[:6],
                        routes=route_list[:4],
                        keywords=list(data["languages"]),
                    ),
                )
            )

        # Build Subsystem Groups from present components
        group_id_to_label = {c.group_id: c.group_label for c in components if c.group_id and c.group_label}
        groups = [
            ArchitectureGroup(id=g_id, label=g_lbl)
            for g_id, g_lbl in group_id_to_label.items()
        ]

        # Build Relationships based on cross-component imports with descriptive labels
        relationships: list[ArchitectureRelationship] = []
        seen_edges: set[tuple[str, str]] = set()
        comp_id_to_name = {c.id: c.name for c in components}

        for source_file, target_files in file_to_imports.items():
            source_comp = file_to_comp_id.get(source_file)
            if not source_comp:
                continue
            for target_file in target_files:
                target_comp = file_to_comp_id.get(target_file)
                if target_comp and target_comp != source_comp:
                    edge_key = (source_comp, target_comp)
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        src_name = comp_id_to_name.get(source_comp, source_comp)
                        tgt_name = comp_id_to_name.get(target_comp, target_comp)
                        # Determine relationship type based on target role
                        tgt_comp_obj = next((c for c in components if c.id == target_comp), None)
                        if tgt_comp_obj and tgt_comp_obj.type == "database":
                            rel_type, rel_label = "READS", "Reads/Writes data"
                        elif tgt_comp_obj and tgt_comp_obj.type == "api":
                            rel_type, rel_label = "CALLS", "Sends request"
                        elif tgt_comp_obj and tgt_comp_obj.type == "queue":
                            rel_type, rel_label = "PUBLISHES", "Enqueues task"
                        else:
                            rel_type, rel_label = "CALLS", "Invokes"
                        
                        relationships.append(
                            ArchitectureRelationship(
                                source=source_comp,
                                target=target_comp,
                                type=rel_type,
                                label=rel_label,
                                style="solid",
                                description=f"{src_name} imports from {tgt_name}.",
                            )
                        )

        # If sparse relationships, connect entrypoints to first-level components
        if len(relationships) < 3 and len(components) >= 2:
            first_comp = components[0]
            for other_comp in components[1:6]:
                edge_key = (first_comp.id, other_comp.id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    relationships.append(
                        ArchitectureRelationship(
                            source=first_comp.id,
                            target=other_comp.id,
                            type="CALLS",
                            label="Dispatches to",
                            style="solid",
                            description=f"{first_comp.name} coordinates with {other_comp.name}.",
                        )
                    )

        # Generate Multiple End-to-End Execution Flows
        flows = []

        # Flow 1: Primary request flow
        if len(components) >= 3:
            flows.append(
                ExecutionFlow(
                    name="Primary Request Flow",
                    description="Main operational flow through the system's core components.",
                    steps=[
                        ExecutionFlowStep(
                            component=components[i].id,
                            action=f"{'Receives incoming request' if i == 0 else 'Processes and forwards' if i < len(components) - 1 else 'Returns final response'} via {components[i].name}",
                            file=components[i].files[0] if components[i].files else None,
                            symbol=components[i].symbols[0] if components[i].symbols else None,
                        )
                        for i in range(min(5, len(components)))
                    ],
                )
            )

        # Flow 2: Data access flow (if we have a database component)
        db_comps = [c for c in components if c.type == "database"]
        api_comps = [c for c in components if c.type == "api"]
        if db_comps and api_comps:
            flows.append(
                ExecutionFlow(
                    name="Data Access Flow",
                    description=f"Data retrieval path from {api_comps[0].name} through to {db_comps[0].name}.",
                    steps=[
                        ExecutionFlowStep(component=api_comps[0].id, action=f"API request handled by {api_comps[0].name}", file=api_comps[0].files[0] if api_comps[0].files else None),
                        ExecutionFlowStep(component=db_comps[0].id, action=f"Query executed against {db_comps[0].name}", file=db_comps[0].files[0] if db_comps[0].files else None),
                        ExecutionFlowStep(component=api_comps[0].id, action="Response formatted and returned to client"),
                    ],
                )
            )

        # Flow 3: AI/Intelligence flow (if we have AI components)
        ai_comps = [c for c in components if c.group_id == "group_ai"]
        if ai_comps and len(components) >= 2:
            entry_comp = api_comps[0] if api_comps else components[0]
            flows.append(
                ExecutionFlow(
                    name="AI Intelligence Pipeline",
                    description=f"AI-powered processing through {ai_comps[0].name}.",
                    steps=[
                        ExecutionFlowStep(component=entry_comp.id, action=f"Request arrives at {entry_comp.name}"),
                        ExecutionFlowStep(component=ai_comps[0].id, action=f"AI processing by {ai_comps[0].name}", file=ai_comps[0].files[0] if ai_comps[0].files else None),
                        ExecutionFlowStep(component=entry_comp.id, action="AI results returned to caller"),
                    ],
                )
            )

        repo_name = repository_id.split("/")[-1].replace("_", " ").title()
        tech_str = ", ".join(context.get("detected_technologies", [])[:5]) or "standard technologies"
        return SemanticArchitecture(
            title=f"{repo_name} System Architecture",
            summary=f"{repo_name} is built with {tech_str}. It consists of {len(components)} subsystems organized across {len(groups)} architectural layers, processing requests through {len(relationships)} interconnected data paths.",
            architecture_style="Modular Multi-Layer Architecture",
            entry_points=context.get("entry_points", []),
            groups=groups,
            components=components,
            relationships=relationships,
            flows=flows,
        )

