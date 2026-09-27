from typing import Literal
from pydantic import BaseModel, Field


class IssueToTriage(BaseModel):
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(default="", max_length=50_000)
    labels: list[str] = Field(default_factory=list)


class RelatedIssueRef(BaseModel):
    number: int
    title: str
    similarity: float
    relation_type: Literal["DUPLICATE", "RELATED", "SIMILAR_TOPIC"]


class TriagedIssue(BaseModel):
    number: int
    title: str
    body: str = ""
    labels: list[str] = Field(default_factory=list)
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"] = "UNKNOWN"
    severity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    category: str = "Bug"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reason: str = Field(default="Standard issue evaluation based on title and description.")
    affected_subsystem: str = "core"
    duplicate_group_id: str | None = None
    is_duplicate: bool = False
    related_issues: list[RelatedIssueRef] = Field(default_factory=list)


class BatchTriageRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=256)
    issues: list[IssueToTriage] = Field(default_factory=list)
    architecture_components: list[str] = Field(default_factory=list)


class TriageSummary(BaseModel):
    total_issues: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    unknown_count: int = 0
    duplicate_groups_count: int = 0
    categories_breakdown: dict[str, int] = Field(default_factory=dict)


class BatchTriageResponse(BaseModel):
    repository_id: str
    summary: TriageSummary
    issues: list[TriagedIssue]
