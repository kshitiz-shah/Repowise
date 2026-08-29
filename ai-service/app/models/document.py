from dataclasses import dataclass


@dataclass(frozen=True)
class CodeDocument:
    repository_id: str
    file_id: str
    file_path: str
    content: str
    language: str


@dataclass(frozen=True)
class CodeChunk:
    id: str
    repository_id: str
    file_id: str
    file_path: str
    language: str
    chunk_index: int
    start_line: int
    end_line: int
    content: str
    file_hash: str
    chunk_hash: str
