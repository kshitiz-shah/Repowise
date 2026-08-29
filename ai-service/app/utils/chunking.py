import re

from app.models.document import CodeChunk, CodeDocument
from app.utils.hashing import content_hash, stable_chunk_id

BOUNDARY = re.compile(r"^\s*(?:async\s+def|def|class|function|async\s+function|export\s+(?:default\s+)?(?:class|function)|public\s+class|private\s+|protected\s+)")


def chunk_document(document: CodeDocument, max_lines: int = 120) -> list[CodeChunk]:
    """Split code at declarations when possible, with a bounded line-count fallback."""
    lines = document.content.splitlines()
    if not lines:
        return []
    file_hash = content_hash(document.content)
    ranges: list[tuple[int, int]] = []
    start = 0
    for index, line in enumerate(lines):
        at_boundary = index > start and bool(BOUNDARY.match(line))
        if index - start >= max_lines or (at_boundary and index - start >= 20):
            ranges.append((start, index))
            start = index
    ranges.append((start, len(lines)))

    chunks: list[CodeChunk] = []
    for chunk_index, (first, last) in enumerate(ranges):
        content = "\n".join(lines[first:last]).strip()
        if not content:
            continue
        chunk_hash = content_hash(content)
        chunks.append(CodeChunk(
            id=stable_chunk_id(document.repository_id, document.file_id, chunk_hash),
            repository_id=document.repository_id, file_id=document.file_id, file_path=document.file_path,
            language=document.language, chunk_index=chunk_index, start_line=first + 1, end_line=last,
            content=content, file_hash=file_hash, chunk_hash=chunk_hash,
        ))
    return chunks
