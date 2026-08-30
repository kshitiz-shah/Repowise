from typing import Literal

from pydantic import BaseModel, Field

from app.api.schemas.repository import RepositoryInput


class ArchitectureRequest(RepositoryInput):
    pass


# ---------------------------------------------------------------------------
# File-Level Hierarchical Graph (Secondary View: Code Dependencies)
# ---------------------------------------------------------------------------

class ArchitectureNode(BaseModel):
    id: str
    label: str
    type: Literal["folder", "file"]
    language: str | None = None
    path: str | None = None
    children_count: int | None = None
    lines_of_code: int | None = None


class ArchitectureEdge(BaseModel):
    source: str
    target: str
    type: Literal["CONTAINS", "IMPORTS"]


class ArchitectureStatistics(BaseModel):
    files: int
    folders: int
    dependencies: int


# ---------------------------------------------------------------------------
# Semantic System Architecture (Primary View: Subsystems & Human Diagram)
# ---------------------------------------------------------------------------

class ComponentEvidence(BaseModel):
    files: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ArchitectureComponent(BaseModel):
    id: str
    name: str
    type: str = "service"
    description: str
    responsibilities: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    evidence: ComponentEvidence = Field(default_factory=ComponentEvidence)


class ArchitectureRelationship(BaseModel):
    source: str
    target: str
    type: str = "CALLS"
    label: str = "Calls"
    description: str | None = None


class SemanticArchitecture(BaseModel):
    title: str = "System Architecture"
    summary: str = ""
    components: list[ArchitectureComponent] = Field(default_factory=list)
    relationships: list[ArchitectureRelationship] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-Level Architecture Payload
# ---------------------------------------------------------------------------

class ArchitectureData(BaseModel):
    repository_id: str
    architecture: SemanticArchitecture
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
    statistics: ArchitectureStatistics
