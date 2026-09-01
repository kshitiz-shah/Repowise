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
# Multi-Level Semantic System Architecture
# ---------------------------------------------------------------------------

class InternalFlowStep(BaseModel):
    from_symbol: str = Field(..., description="Originating function/module/route")
    to_symbol: str = Field(..., description="Target service/function/database")
    action: str = Field(..., description="Description of the operation or data transfer")
    file_path: str | None = Field(default=None, description="Primary file implementing this step")


class ExecutionFlowStep(BaseModel):
    component: str = Field(..., description="Component ID or Name handling this step")
    action: str = Field(..., description="Specific action performed at this stage")
    file: str | None = Field(default=None, description="Associated source file")
    symbol: str | None = Field(default=None, description="Associated function or route symbol")


class ExecutionFlow(BaseModel):
    name: str = Field(..., description="Name of the end-to-end flow (e.g. 'User Authentication')")
    description: str = Field(..., description="Summary of how data and requests move")
    steps: list[ExecutionFlowStep] = Field(default_factory=list)


class ComponentEvidence(BaseModel):
    files: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)


class ArchitectureComponent(BaseModel):
    id: str
    name: str
    type: str = "service"
    description: str
    responsibilities: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    internal_flow: list[InternalFlowStep] = Field(default_factory=list)
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
    architecture_style: str = "Modular Architecture"
    entry_points: list[str] = Field(default_factory=list)
    components: list[ArchitectureComponent] = Field(default_factory=list)
    relationships: list[ArchitectureRelationship] = Field(default_factory=list)
    flows: list[ExecutionFlow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-Level Architecture Payload
# ---------------------------------------------------------------------------

class ArchitectureData(BaseModel):
    repository_id: str
    architecture: SemanticArchitecture
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
    statistics: ArchitectureStatistics
