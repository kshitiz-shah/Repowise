from pydantic import BaseModel, Field


class RagQueryRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=256)
    question: str = Field(min_length=3, max_length=10_000)
    top_k: int = Field(default=8, ge=1, le=20)


class SourceReference(BaseModel):
    file_id: str
    file_path: str
    start_line: int
    end_line: int
    score: float


class RagQueryData(BaseModel):
    answer: str
    sources: list[SourceReference]
