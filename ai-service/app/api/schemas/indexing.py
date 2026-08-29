from pydantic import BaseModel

from app.api.schemas.repository import RepositoryInput


class IndexRepositoryRequest(RepositoryInput):
    replace_existing: bool = False


class IndexRepositoryData(BaseModel):
    repository_id: str
    indexed_files: int
    indexed_chunks: int
    skipped_files: int
