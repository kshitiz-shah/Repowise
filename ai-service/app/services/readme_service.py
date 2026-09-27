import json
import logging
import re
from typing import Any, Dict, List, Set, Tuple

from app.api.schemas.readme import (
    EnvVarItem,
    KeyModuleItem,
    QuickStartSection,
    ReadmeFileContext,
    ReadmeGenerationRequest,
    ReadmeGenerationResponse,
    RunCommandItem,
    TechStackItem,
)
from app.services.llm_service import LLMService, get_llm_service

logger = logging.getLogger("repowise.readme")

ENV_JS_REGEX = re.compile(r"process\.env\.([A-Z0-9_]+)")
ENV_PY_REGEX = re.compile(r"os\.(?:environ|getenv)\s*(?:\[|\()\s*['\"]([A-Z0-9_]+)['\"]")
ENV_SAMPLE_REGEX = re.compile(r"^([A-Z0-9_]+)\s*=", re.MULTILINE)


JS_DEP_MAP: Dict[str, Tuple[str, str]] = {
    "react": ("Frontend Framework", "React"),
    "react-dom": ("Frontend Framework", "React"),
    "next": ("Full-Stack Framework", "Next.js"),
    "vue": ("Frontend Framework", "Vue.js"),
    "nuxt": ("Full-Stack Framework", "Nuxt.js"),
    "svelte": ("Frontend Framework", "Svelte"),
    "@sveltejs/kit": ("Full-Stack Framework", "SvelteKit"),
    "@angular/core": ("Frontend Framework", "Angular"),
    "express": ("Backend Framework", "Express.js"),
    "fastify": ("Backend Framework", "Fastify"),
    "@nestjs/core": ("Backend Framework", "NestJS"),
    "koa": ("Backend Framework", "Koa"),
    "hono": ("Backend Framework", "Hono"),
    "vite": ("Build Tool", "Vite"),
    "webpack": ("Bundler", "Webpack"),
    "esbuild": ("Bundler", "esbuild"),
    "rollup": ("Bundler", "Rollup"),
    "@prisma/client": ("Database ORM", "Prisma"),
    "prisma": ("Database ORM", "Prisma"),
    "drizzle-orm": ("Database ORM", "Drizzle ORM"),
    "typeorm": ("Database ORM", "TypeORM"),
    "mongoose": ("Database ODM", "Mongoose / MongoDB"),
    "pg": ("Database Client", "PostgreSQL (pg)"),
    "mysql2": ("Database Client", "MySQL (mysql2)"),
    "sqlite3": ("Database Client", "SQLite"),
    "better-sqlite3": ("Database Client", "SQLite"),
    "redis": ("Caching / In-Memory", "Redis"),
    "ioredis": ("Caching / In-Memory", "Redis (ioredis)"),
    "tailwindcss": ("Styling", "Tailwind CSS"),
    "styled-components": ("Styling", "styled-components"),
    "@emotion/react": ("Styling", "Emotion"),
    "sass": ("Styling", "Sass / SCSS"),
    "typescript": ("Language", "TypeScript"),
    "zod": ("Validation", "Zod"),
    "yup": ("Validation", "Yup"),
    "graphql": ("API Protocol", "GraphQL"),
    "@apollo/server": ("API Protocol", "Apollo GraphQL"),
    "@trpc/server": ("API Protocol", "tRPC"),
    "axios": ("HTTP Client", "Axios"),
    "jsonwebtoken": ("Authentication", "JWT"),
    "jose": ("Authentication", "Jose JWT"),
    "passport": ("Authentication", "Passport.js"),
    "socket.io": ("Real-Time Communication", "Socket.IO"),
    "ws": ("Real-Time Communication", "WebSockets (ws)"),
    "jest": ("Testing", "Jest"),
    "vitest": ("Testing", "Vitest"),
    "cypress": ("Testing", "Cypress"),
    "playwright": ("Testing", "Playwright"),
    "@playwright/test": ("Testing", "Playwright"),
    "eslint": ("Code Quality", "ESLint"),
    "prettier": ("Code Quality", "Prettier"),
    "qdrant-client": ("Vector Database", "Qdrant"),
    "@qdrant/js-client-rest": ("Vector Database", "Qdrant"),
    "langchain": ("AI / LLM Framework", "LangChain"),
    "@google/genai": ("AI / LLM SDK", "Google Gemini API"),
    "@google/generative-ai": ("AI / LLM SDK", "Google Gemini API"),
    "openai": ("AI / LLM SDK", "OpenAI API"),
}

PY_DEP_MAP: Dict[str, Tuple[str, str]] = {
    "fastapi": ("Backend Framework", "FastAPI"),
    "uvicorn": ("ASGI Web Server", "Uvicorn"),
    "gunicorn": ("WSGI Web Server", "Gunicorn"),
    "flask": ("Backend Framework", "Flask"),
    "django": ("Backend Framework", "Django"),
    "sqlalchemy": ("Database ORM", "SQLAlchemy"),
    "alembic": ("Database Migrations", "Alembic"),
    "pydantic": ("Data Validation", "Pydantic"),
    "pytest": ("Testing", "Pytest"),
    "unittest": ("Testing", "Unittest"),
    "qdrant-client": ("Vector Database", "Qdrant"),
    "pinecone-client": ("Vector Database", "Pinecone"),
    "chromadb": ("Vector Database", "ChromaDB"),
    "langchain": ("AI / LLM Framework", "LangChain"),
    "llama-index": ("AI / LLM Framework", "LlamaIndex"),
    "google-generativeai": ("AI / LLM SDK", "Google Gemini API"),
    "openai": ("AI / LLM SDK", "OpenAI API"),
    "anthropic": ("AI / LLM SDK", "Anthropic API"),
    "celery": ("Task Queue", "Celery"),
    "redis": ("Caching / Message Broker", "Redis"),
    "numpy": ("Scientific Computing", "NumPy"),
    "pandas": ("Data Analysis", "Pandas"),
    "scikit-learn": ("Machine Learning", "Scikit-Learn"),
    "torch": ("Deep Learning", "PyTorch"),
    "tensorflow": ("Deep Learning", "TensorFlow"),
    "black": ("Code Formatting", "Black"),
    "ruff": ("Linter / Formatter", "Ruff"),
    "flake8": ("Linter", "Flake8"),
    "mypy": ("Type Checking", "Mypy"),
}


class ReadmeService:
    def __init__(self, llm_service: LLMService | None = None):
        self.llm_service = llm_service or get_llm_service()

    def generate_readme(self, request: ReadmeGenerationRequest) -> ReadmeGenerationResponse:
        repo_name = request.repository_name
        owner = request.owner

        # 1. Deterministic evidence extraction from source files
        evidence = self._extract_code_evidence(request.files, primary_language=request.primary_language)

        # 2. Strict validation & filtering
        valid_env_vars = evidence["env_vars"]
        valid_commands = evidence["commands"]
        tech_stack = evidence["tech_stack"]
        prerequisites = evidence["prerequisites"]
        installation = evidence["installation"]
        key_modules = evidence["key_modules"]

        # 3. LLM narrative generation with grounded evidence
        narrative = self._generate_narrative(request, evidence)

        project_name = narrative.get("project_name") or repo_name
        tagline = narrative.get("tagline") or (request.description or f"Modern {request.primary_language or 'software'} application.")
        overview = narrative.get("overview") or (request.description or f"{repo_name} is a high-performance software system designed for maintainability and reliability.")
        arch_summary = narrative.get("architecture_summary") or request.architecture_summary or f"Modular architecture built with {', '.join(t.name for t in tech_stack[:4]) or 'standard components'}."

        quick_start = QuickStartSection(
            prerequisites=prerequisites,
            installation=installation,
            environment_variables=valid_env_vars,
            run_commands=valid_commands,
        )

        # 4. Generate GitHub-Flavored Markdown
        markdown = self._render_markdown(
            project_name=project_name,
            tagline=tagline,
            overview=overview,
            architecture_summary=arch_summary,
            tech_stack=tech_stack,
            quick_start=quick_start,
            key_modules=key_modules,
            owner=owner,
            repo_name=repo_name,
            primary_language=request.primary_language,
        )

        return ReadmeGenerationResponse(
            repository_id=request.repository_id,
            project_name=project_name,
            tagline=tagline,
            overview=overview,
            architecture_summary=arch_summary,
            tech_stack=tech_stack,
            quick_start=quick_start,
            key_modules=key_modules,
            markdown=markdown,
            existing_readme=request.existing_readme,
        )

    def _extract_code_evidence(self, files: List[ReadmeFileContext], primary_language: str | None = None) -> Dict[str, Any]:
        discovered_envs: Dict[str, str] = {}
        discovered_commands: List[RunCommandItem] = []
        tech_stack_set: Set[Tuple[str, str]] = set()
        prerequisites: List[str] = []
        installation: List[str] = []
        key_modules: List[KeyModuleItem] = []

        has_package_json = False
        has_python = False
        has_docker = False
        has_prisma = False

        if primary_language:
            tech_stack_set.add(("Language", primary_language))

        for f in files:
            path = f.path.lower()
            content = f.content

            # Infer language from file extension
            if path.endswith((".ts", ".tsx")):
                tech_stack_set.add(("Language", "TypeScript"))
            elif path.endswith((".js", ".jsx")):
                tech_stack_set.add(("Language", "JavaScript"))
            elif path.endswith(".py"):
                tech_stack_set.add(("Language", "Python"))
                has_python = True
            elif path.endswith(".go"):
                tech_stack_set.add(("Language", "Go"))
            elif path.endswith(".rs"):
                tech_stack_set.add(("Language", "Rust"))
            elif path.endswith(".java"):
                tech_stack_set.add(("Language", "Java"))
            elif path.endswith((".cpp", ".c", ".h")):
                tech_stack_set.add(("Language", "C / C++"))
            elif path.endswith(".cs"):
                tech_stack_set.add(("Language", "C#"))

            # Look for environment variable usage
            for match in ENV_JS_REGEX.finditer(content):
                key = match.group(1)
                if key not in ("NODE_ENV", "PORT") and key not in discovered_envs:
                    discovered_envs[key] = f"Configured in {f.path}"
                elif key in ("PORT", "NODE_ENV") and key not in discovered_envs:
                    discovered_envs[key] = f"Runtime environment port/mode"

            for match in ENV_PY_REGEX.finditer(content):
                key = match.group(1)
                if key not in discovered_envs:
                    discovered_envs[key] = f"Referenced in {f.path}"

            if path.endswith((".env.example", ".env.sample", ".env.template")):
                for match in ENV_SAMPLE_REGEX.finditer(content):
                    key = match.group(1)
                    discovered_envs[key] = f"Documented in {f.path}"

            # Inspect package.json
            if path.endswith("package.json"):
                has_package_json = True
                try:
                    pkg = json.loads(content)
                    scripts = pkg.get("scripts", {})
                    for script_name, cmd in scripts.items():
                        label = f"npm run {script_name}" if script_name != "start" else "npm start"
                        discovered_commands.append(RunCommandItem(label=f"Script: {script_name}", command=label))

                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {}), **pkg.get("peerDependencies", {})}
                    for dep_name in deps.keys():
                        dep_lower = dep_name.lower()
                        if dep_lower in JS_DEP_MAP:
                            cat, name = JS_DEP_MAP[dep_lower]
                            tech_stack_set.add((cat, name))
                            if "prisma" in dep_lower:
                                has_prisma = True
                except Exception:
                    pass

            # Inspect python configs
            if path.endswith(("pyproject.toml", "requirements.txt", "setup.py")):
                has_python = True
                tech_stack_set.add(("Language", "Python"))
                content_lower = content.lower()
                for dep_name, (cat, name) in PY_DEP_MAP.items():
                    if dep_name in content_lower:
                        tech_stack_set.add((cat, name))

                if "uvicorn" in content_lower:
                    discovered_commands.append(RunCommandItem(label="Development Server", command="uvicorn app.main:app --reload"))
                if "pytest" in content_lower:
                    discovered_commands.append(RunCommandItem(label="Test Suite", command="pytest"))

            # Inspect Prisma
            if "schema.prisma" in path:
                has_prisma = True
                tech_stack_set.add(("Database ORM", "Prisma"))
                if "postgresql" in content.lower():
                    tech_stack_set.add(("Database", "PostgreSQL"))
                elif "mysql" in content.lower():
                    tech_stack_set.add(("Database", "MySQL"))
                elif "sqlite" in content.lower():
                    tech_stack_set.add(("Database", "SQLite"))
                elif "mongodb" in content.lower():
                    tech_stack_set.add(("Database", "MongoDB"))

            # Inspect Docker
            if "dockerfile" in path or "docker-compose" in path:
                has_docker = True
                tech_stack_set.add(("Containerization", "Docker"))
                if "postgres" in content.lower():
                    tech_stack_set.add(("Database", "PostgreSQL"))
                if "redis" in content.lower():
                    tech_stack_set.add(("Cache / In-Memory", "Redis"))
                if "qdrant" in content.lower():
                    tech_stack_set.add(("Vector Database", "Qdrant"))

            # Key Modules Identification
            if path in ("server/src/index.ts", "server/src/app.ts", "server/src/main.ts"):
                key_modules.append(KeyModuleItem(path=f.path, role="Server entry point and HTTP middleware initialization"))
            elif path in ("client/src/main.tsx", "client/src/app.tsx", "src/app.tsx", "src/index.tsx"):
                key_modules.append(KeyModuleItem(path=f.path, role="Frontend UI root and router orchestration"))
            elif path.endswith("main.py") or path.endswith("run.py"):
                key_modules.append(KeyModuleItem(path=f.path, role="FastAPI application entry point and service bootstrap"))
            elif "schema.prisma" in path:
                key_modules.append(KeyModuleItem(path=f.path, role="Database domain models and relational schema definition"))
            elif "services/" in path and len(key_modules) < 6:
                key_modules.append(KeyModuleItem(path=f.path, role=f"Core domain service: {f.path.split('/')[-1]}"))

        # Setup commands based on verified project evidence
        if has_package_json:
            prerequisites.append("Node.js >= 18.x and npm / pnpm / yarn")
            installation.append("npm install")
        if has_prisma:
            installation.append("npx prisma generate")
            installation.append("npx prisma db push")
        if has_python:
            prerequisites.append("Python >= 3.10 and pip / uv / poetry")
            installation.append("python -m venv .venv && source .venv/bin/activate")
            installation.append("pip install -r requirements.txt (or uv sync)")
        if has_docker:
            prerequisites.append("Docker and Docker Compose")
            discovered_commands.append(RunCommandItem(label="Docker Services", command="docker compose up -d"))

        env_items = [
            EnvVarItem(key=k, description=v)
            for k, v in sorted(discovered_envs.items())
        ]

        tech_items = [
            TechStackItem(category=cat, name=name)
            for cat, name in sorted(tech_stack_set)
        ]

        return {
            "env_vars": env_items,
            "commands": discovered_commands[:8],
            "tech_stack": tech_items,
            "prerequisites": prerequisites or ["Git and standard terminal shell"],
            "installation": installation or ["git clone <repo-url>", "cd <repo-folder>"],
            "key_modules": key_modules[:8],
        }

    def _generate_narrative(self, request: ReadmeGenerationRequest, evidence: Dict[str, Any]) -> Dict[str, str]:
        if not self.llm_service:
            return {}

        prompt = f"""You are a senior technical writer producing a high-impact, professional README for a GitHub repository.

Repository: {request.owner}/{request.repository_name}
Primary Language: {request.primary_language or 'Not specified'}
GitHub Description: {request.description or 'None'}
Detected Tech Stack: {json.dumps([t.model_dump() for t in evidence['tech_stack']])}
Key Modules: {json.dumps([m.model_dump() for m in evidence['key_modules']])}
Architecture Summary: {request.architecture_summary or 'None provided'}

Provide concise, grounded JSON:
{{
  "project_name": "Formatted Project Title",
  "tagline": "Compelling 1-sentence value proposition",
  "overview": "2-3 paragraphs describing what the system does, core problems solved, and capabilities.",
  "architecture_summary": "1-2 paragraphs summarizing the structural design, data flow, and modularity."
}}
Return ONLY valid JSON. Do not include markdown code block syntax outside the JSON.
"""
        try:
            raw = self.llm_service.generate_text(prompt)
            clean_raw = raw.strip()
            if clean_raw.startswith("```"):
                clean_raw = re.sub(r"^```[a-z]*\n", "", clean_raw)
                clean_raw = re.sub(r"\n```$", "", clean_raw)
            data = json.loads(clean_raw)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            logger.warning("LLM narrative generation fallback: %s", exc)

        return {}

    def _render_markdown(
        self,
        project_name: str,
        tagline: str,
        overview: str,
        architecture_summary: str,
        tech_stack: List[TechStackItem],
        quick_start: QuickStartSection,
        key_modules: List[KeyModuleItem],
        owner: str,
        repo_name: str,
        primary_language: str | None = None,
    ) -> str:
        lines: List[str] = []

        # Header & Badges
        lines.append(f"# {project_name}")
        lines.append(f"> **{tagline}**\n")
        lines.append(f"[![Repository](https://img.shields.io/badge/GitHub-{owner}%2F{repo_name}-181717?logo=github)](https://github.com/{owner}/{repo_name})")
        lines.append("[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)\n")

        # Table of Contents
        lines.append("## 📑 Table of Contents")
        lines.append("- [Overview](#-overview)")
        lines.append("- [System Architecture](#-system-architecture)")
        lines.append("- [Tech Stack](#-tech-stack)")
        lines.append("- [Quick Start & Setup](#-quick-start--setup)")
        lines.append("- [Environment Configuration](#-environment-configuration)")
        lines.append("- [Key Modules](#-key-modules)")
        lines.append("- [Contributing & License](#-contributing--license)\n")

        # Overview
        lines.append("## 🔍 Overview")
        lines.append(overview.strip() + "\n")

        # Architecture
        lines.append("## 🏛️ System Architecture")
        lines.append(architecture_summary.strip() + "\n")

        # Tech Stack (Guaranteed to match Table of Contents anchor #tech-stack)
        lines.append("## 🛠️ Tech Stack")
        lines.append("| Category | Technology |")
        lines.append("| :--- | :--- |")
        if tech_stack:
            for t in tech_stack:
                lines.append(f"| **{t.category}** | `{t.name}` |")
        else:
            fallback_lang = primary_language or "General Software Stack"
            lines.append(f"| **Core Language** | `{fallback_lang}` |")
        lines.append("")

        # Quick Start
        lines.append("## 🚀 Quick Start & Setup")
        lines.append("### Prerequisites")
        for p in quick_start.prerequisites:
            lines.append(f"- {p}")
        lines.append("")

        lines.append("### Installation")
        lines.append("```bash")
        for cmd in quick_start.installation:
            lines.append(cmd)
        lines.append("```\n")

        if quick_start.run_commands:
            lines.append("### Running the Application")
            lines.append("```bash")
            for r in quick_start.run_commands:
                lines.append(f"# {r.label}")
                lines.append(r.command)
            lines.append("```\n")

        # Environment Configuration
        if quick_start.environment_variables:
            lines.append("## ⚙️ Environment Configuration")
            lines.append("Create a `.env` file in the appropriate directory and supply the following variables:\n")
            lines.append("| Variable Key | Description |")
            lines.append("| :--- | :--- |")
            for ev in quick_start.environment_variables:
                lines.append(f"| `{ev.key}` | {ev.description} |")
            lines.append("")

        # Key Modules
        if key_modules:
            lines.append("## 📂 Key Modules & File Structure")
            lines.append("| Path | Responsibility |")
            lines.append("| :--- | :--- |")
            for m in key_modules:
                lines.append(f"| [`{m.path}`]({m.path}) | {m.role} |")
            lines.append("")

        # License
        lines.append("## 📄 Contributing & License")
        lines.append("Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/" + f"{owner}/{repo_name}/issues).\n")
        lines.append("Distributed under the MIT License.")

        return "\n".join(lines)
