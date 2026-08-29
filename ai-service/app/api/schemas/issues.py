from typing import Literal

from pydantic import BaseModel, Field


class IssueInput(BaseModel):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=50_000)


class AnalyzeIssueRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=256)
    issue: IssueInput


class IssueAnalysisData(BaseModel):
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)
    concepts: list[str] = Field(default_factory=list)
    affected_components: list[str] = Field(default_factory=list)
