from pydantic import BaseModel, Field


class RepositoryFile(BaseModel):
    file_id: str = Field(min_length=1, max_length=256)
    path: str = Field(min_length=1, max_length=2048)
    content: str = Field(min_length=1, max_length=1_000_000)


class RepositoryInput(BaseModel):
    repository_id: str = Field(min_length=1, max_length=256)
    files: list[RepositoryFile] = Field(min_length=1, max_length=10_000)
