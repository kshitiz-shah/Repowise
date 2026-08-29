import hashlib
import uuid


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def stable_chunk_id(repository_id: str, file_id: str, chunk_hash: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"repowise:{repository_id}:{file_id}:{chunk_hash}"))
