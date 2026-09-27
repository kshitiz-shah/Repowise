from typing import Literal
from pydantic import BaseModel, Field


class FileHotspotInput(BaseModel):
    id: str
    path: str
    name: str = ""
    language: str | None = None
    lines_of_code: int = Field(default=0, ge=0)
    size: int = Field(default=0, ge=0)
    component: str | None = None


class CommitHotspotInput(BaseModel):
    sha: str
    message: str = ""
    author: str | None = None
    date: str | None = None
    files: list[str] = Field(default_factory=list)


class BugMappingHotspotInput(BaseModel):
    file_id: str | None = None
    file_path: str
    issue_number: int | None = None
    score: float = 0.5


class DependencyHotspotInput(BaseModel):
    source_path: str
    target_path: str
    type: str = "IMPORTS"


class HotspotCalculationRequest(BaseModel):
    repository_id: str = Field(min_length=1)
    files: list[FileHotspotInput] = Field(default_factory=list)
    commits: list[CommitHotspotInput] = Field(default_factory=list)
    bug_mappings: list[BugMappingHotspotInput] = Field(default_factory=list)
    dependencies: list[DependencyHotspotInput] = Field(default_factory=list)


class FileHotspotEvidence(BaseModel):
    churn_commits: int = 0
    bug_associations: int = 0
    bug_fix_commits: int = 0
    in_degree: int = 0
    drivers: list[str] = Field(default_factory=list)


class FileHotspotResult(BaseModel):
    id: str
    path: str
    name: str
    language: str | None = None
    lines_of_code: int = 0
    churn_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    bug_count: int = 0
    component_name: str | None = None
    evidence: FileHotspotEvidence


class ComponentHotspotResult(BaseModel):
    name: str
    risk_level: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    avg_risk_score: float
    max_risk_score: float
    file_count: int
    total_churn: int
    total_bug_density: int


class HotspotCalculationResponse(BaseModel):
    repository_id: str
    components: list[ComponentHotspotResult]
    files: list[FileHotspotResult]
    high_risk_count: int
    medium_risk_count: int
    low_risk_count: int
