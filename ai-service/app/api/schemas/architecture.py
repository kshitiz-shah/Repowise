from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
    from_symbol: str = Field(default="", description="Originating function/module/route")
    to_symbol: str = Field(default="", description="Target service/function/database")
    action: str = Field(default="Processes request", description="Description of the operation or data transfer")
    file_path: str | None = Field(default=None, description="Primary file implementing this step")

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "from_symbol" not in data or not data["from_symbol"]:
                data["from_symbol"] = data.get("from") or data.get("source") or data.get("caller") or "Caller"
            if "to_symbol" not in data or not data["to_symbol"]:
                data["to_symbol"] = data.get("to") or data.get("target") or data.get("callee") or "Target"
            if "file_path" not in data:
                data["file_path"] = data.get("file") or data.get("filepath") or data.get("path")
            if "action" not in data or not data["action"]:
                data["action"] = data.get("description") or data.get("label") or "Processes request"
        return data


class ExecutionFlowStep(BaseModel):
    component: str = Field(default="system", description="Component ID or Name handling this step")
    action: str = Field(default="Processes request", description="Specific action performed at this stage")
    file: str | None = Field(default=None, description="Associated source file")
    symbol: str | None = Field(default=None, description="Associated function or route symbol")

    @model_validator(mode="before")
    @classmethod
    def _normalize_step(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "component" not in data or not data["component"]:
                data["component"] = data.get("service") or data.get("target") or data.get("name") or "system"
            if "action" not in data or not data["action"]:
                data["action"] = data.get("description") or data.get("step") or "Executes step"
            if "file" not in data:
                data["file"] = data.get("file_path") or data.get("path")
        return data


class ExecutionFlow(BaseModel):
    name: str = Field(..., description="Name of the end-to-end flow (e.g. 'User Authentication')")
    description: str = Field(default="", description="Summary of how data and requests move")
    steps: list[ExecutionFlowStep] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_flow(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "description" not in data or not data["description"]:
                data["description"] = data.get("summary") or data.get("details") or f"Executes {data.get('name', 'flow')}"
            if "steps" not in data or not isinstance(data.get("steps"), list):
                data["steps"] = []
        return data


class ComponentEvidence(BaseModel):
    files: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_evidence(cls, data: Any) -> Any:
        if isinstance(data, dict):
            for k in ("files", "symbols", "imports", "routes", "keywords"):
                val = data.get(k)
                if isinstance(val, str):
                    data[k] = [val]
                elif val is None:
                    data[k] = []
        return data


class ArchitectureGroup(BaseModel):
    id: str
    label: str
    description: str | None = None


class ArchitectureComponent(BaseModel):
    id: str
    name: str = ""
    type: str = "service"
    shape: str = "box"  # box, database, circle, queue, hexagon, document
    group_id: str | None = None
    group_label: str | None = None
    description: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    routes: list[str] = Field(default_factory=list)
    internal_flow: list[InternalFlowStep] = Field(default_factory=list)
    evidence: ComponentEvidence = Field(default_factory=ComponentEvidence)

    @model_validator(mode="before")
    @classmethod
    def _normalize_component(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("name") and data.get("id"):
                data["name"] = str(data["id"]).replace("_", " ").title()
            if not data.get("description"):
                data["description"] = f"Handles {data.get('name', 'subsystem')} logic."
            if "groupId" in data and not data.get("group_id"):
                data["group_id"] = data["groupId"]
            for k in ("responsibilities", "files", "symbols", "routes"):
                val = data.get(k)
                if isinstance(val, str):
                    data[k] = [val]
                elif val is None:
                    data[k] = []
        return data


class ArchitectureRelationship(BaseModel):
    source: str
    target: str
    type: str = "CALLS"
    label: str = "Calls"
    style: str = "solid"  # solid, dashed
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_rel(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "source" not in data or not data["source"]:
                data["source"] = data.get("from") or data.get("src") or ""
            if "target" not in data or not data["target"]:
                data["target"] = data.get("to") or data.get("dst") or ""
            if "label" not in data or not data["label"]:
                data["label"] = data.get("type") or "Interacts with"
        return data


class SemanticArchitecture(BaseModel):
    title: str = "System Architecture"
    summary: str = ""
    architecture_style: str = "Modular Architecture"
    entry_points: list[str] = Field(default_factory=list)
    groups: list[ArchitectureGroup] = Field(default_factory=list)
    components: list[ArchitectureComponent] = Field(default_factory=list)
    relationships: list[ArchitectureRelationship] = Field(default_factory=list)
    flows: list[ExecutionFlow] = Field(default_factory=list)
    mermaid_code: str | None = None



# ---------------------------------------------------------------------------
# Top-Level Architecture Payload
# ---------------------------------------------------------------------------

class ArchitectureData(BaseModel):
    repository_id: str
    architecture: SemanticArchitecture
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
    statistics: ArchitectureStatistics
