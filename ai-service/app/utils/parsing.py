import re
from pathlib import PurePosixPath


LANGUAGE_BY_EXTENSION = {
    ".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript", ".jsx": "jsx",
    ".java": "java", ".go": "go", ".rs": "rust", ".cs": "csharp", ".cpp": "cpp",
    ".c": "c", ".h": "c", ".md": "markdown", ".json": "json", ".yml": "yaml", ".yaml": "yaml",
    ".prisma": "prisma", ".sql": "sql", ".toml": "toml", ".graphql": "graphql", ".gql": "graphql",
}


def detect_language(file_path: str) -> str:
    return LANGUAGE_BY_EXTENSION.get(PurePosixPath(file_path).suffix.lower(), "text")


def extract_imports(content: str, language: str) -> list[str]:
    """Extract module references deterministically for common repository languages."""
    if language in {"typescript", "tsx", "javascript", "jsx"}:
        patterns = [r"(?:import|export)\s+(?:.+?\s+from\s+)?[\"']([^\"']+)[\"']", r"require\(\s*[\"']([^\"']+)[\"']\s*\)"]
    elif language == "python":
        patterns = [r"^\s*from\s+([.\w]+)\s+import\s+", r"^\s*import\s+([\w.]+)"]
    else:
        return []
    return [item for pattern in patterns for item in re.findall(pattern, content, flags=re.MULTILINE)]


def resolve_import(source_path: str, module: str, paths: set[str], language: str) -> str | None:
    """Resolve local TypeScript/JavaScript and relative Python imports to repository files."""
    source_parent = PurePosixPath(source_path).parent
    if language in {"typescript", "tsx", "javascript", "jsx"}:
        if not module.startswith("."):
            return None
        base = source_parent / module
        candidates = [str(base), *[f"{base}{suffix}" for suffix in (".ts", ".tsx", ".js", ".jsx")], *[str(base / f"index{suffix}") for suffix in (".ts", ".tsx", ".js", ".jsx")]]
    elif language == "python":
        if not module.startswith("."):
            return None
        dots = len(module) - len(module.lstrip("."))
        parent = source_parent
        for _ in range(max(dots - 1, 0)):
            parent = parent.parent
        module_path = module.lstrip(".").replace(".", "/")
        base = parent / module_path
        candidates = [f"{base}.py", str(base / "__init__.py")]
    else:
        return None
    return next((candidate for candidate in candidates if candidate in paths), None)
