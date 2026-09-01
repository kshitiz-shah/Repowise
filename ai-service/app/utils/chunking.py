import re

from app.models.document import CodeChunk, CodeDocument
from app.utils.hashing import content_hash, stable_chunk_id

SYMBOL_PATTERNS = [
    # Route decorators/definitions
    (re.compile(r"^\s*(?:@(?:router|app)\.(?:get|post|put|delete|patch|options|head)\s*\(\s*[\"']([^\"']+)[\"'])", re.IGNORECASE), "route"),
    (re.compile(r"^\s*(?:app|router)\.(?:get|post|put|delete|patch|options|use)\s*\(\s*[\"']([^\"']+)[\"']", re.IGNORECASE), "route"),
    # Class declarations
    (re.compile(r"^\s*(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_$]+)"), "class"),
    # Functions and methods (Python, TS, JS, Go, Rust, Java)
    (re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?def\s+([A-Za-z0-9_$]+)"), "function"),
    (re.compile(r"^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s*([A-Za-z0-9_$]*)"), "function"),
    (re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"), "function"),
    (re.compile(r"^\s*func\s+(?:\([^)]+\)\s*)?([A-Za-z0-9_$]+)"), "function"),
    (re.compile(r"^\s*(?:pub\s+)?fn\s+([A-Za-z0-9_$]+)"), "function"),
    # Interface / Type / Schema declarations
    (re.compile(r"^\s*(?:export\s+)?(?:interface|type)\s+([A-Za-z0-9_$]+)"), "type"),
]


def extract_symbol_and_type(line: str) -> tuple[str | None, str]:
    for pattern, chunk_type in SYMBOL_PATTERNS:
        match = pattern.search(line)
        if match:
            symbol = match.group(1) if match.groups() and match.group(1) else None
            return symbol, chunk_type
    return None, "block"


def chunk_document(document: CodeDocument, max_lines: int = 120) -> list[CodeChunk]:
    """Split code at declaration boundaries when possible, preserving symbol metadata."""
    lines = document.content.splitlines()
    if not lines:
        return []
    file_hash = content_hash(document.content)
    ranges: list[tuple[int, int, str | None, str]] = []
    start = 0
    curr_symbol: str | None = None
    curr_type = "block"

    for index, line in enumerate(lines):
        symbol, chunk_type = extract_symbol_and_type(line)
        at_boundary = (chunk_type != "block")
        if index > start and (index - start >= max_lines or (at_boundary and index - start >= 20)):
            ranges.append((start, index, curr_symbol, curr_type))
            start = index
            curr_symbol = symbol
            curr_type = chunk_type
        elif at_boundary and curr_symbol is None:
            curr_symbol = symbol
            curr_type = chunk_type

    ranges.append((start, len(lines), curr_symbol, curr_type))

    chunks: list[CodeChunk] = []
    for chunk_index, (first, last, symbol, chunk_type) in enumerate(ranges):
        content = "\n".join(lines[first:last]).strip()
        if not content:
            continue
        chunk_hash = content_hash(content)
        chunks.append(
            CodeChunk(
                id=stable_chunk_id(document.repository_id, document.file_id, chunk_hash),
                repository_id=document.repository_id,
                file_id=document.file_id,
                file_path=document.file_path,
                language=document.language,
                chunk_index=chunk_index,
                start_line=first + 1,
                end_line=last,
                content=content,
                file_hash=file_hash,
                chunk_hash=chunk_hash,
                symbol=symbol,
                chunk_type=chunk_type,
            )
        )
    return chunks
