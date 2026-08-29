from pydantic import BaseModel

from app.api.schemas.repository import RepositoryInput


class ArchitectureRequest(RepositoryInput):
    pass


class ArchitectureNode(BaseModel):
    id: str
    label: str
    type: str = "file"
    language: str


class ArchitectureEdge(BaseModel):
    source: str
    target: str
    type: str


class ArchitectureData(BaseModel):
    repository_id: str
    nodes: list[ArchitectureNode]
    edges: list[ArchitectureEdge]
