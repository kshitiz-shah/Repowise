from pydantic import BaseModel, Field

from app.api.schemas.issues import IssueInput
from app.api.schemas.repository import RepositoryFile


class CommitFile(BaseModel):
    filename: str
    additions: int = 0
    deletions: int = 0
    status: str = ""


class CommitItem(BaseModel):
    sha: str
    message: str
    author: str | None = None
    date: str | None = None
    files: list[CommitFile] = Field(default_factory=list)


class BugLocalizationRequest(BaseModel):
    repository_id: str = Field(min_length=1, max_length=256)
    issue: IssueInput
    files: list[RepositoryFile] = Field(default_factory=list)
    commit_history: list[CommitItem] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=20)
    include_explanation: bool = True


class IssueAnalysis(BaseModel):
    problem_summary: str = Field(description="Clear summary of the bug or reported issue")
    error_messages: list[str] = Field(default_factory=list, description="Extracted error messages, stack trace lines, or exception names")
    entities: list[str] = Field(default_factory=list, description="Extracted function names, class names, method names, variable names, or symbols")
    file_path_hints: list[str] = Field(default_factory=list, description="Direct or partial file path hints mentioned in the issue")
    api_endpoints: list[str] = Field(default_factory=list, description="API endpoints or route fragments mentioned")
    domain_concepts: list[str] = Field(default_factory=list, description="Key domain concepts, e.g. authentication, session, parsing, layout")
    affected_subsystem: str = Field(default="unknown", description="Subsystem or architectural component likely affected")
    search_queries: list[str] = Field(default_factory=list, description="2-3 targeted search queries for vector retrieval")


class FileCandidateSignals(BaseModel):
    semantic_similarity: float = Field(ge=0.0, le=1.0)
    keyword_score: float = Field(ge=0.0, le=1.0)
    dependency_score: float = Field(ge=0.0, le=1.0)
    path_score: float = Field(ge=0.0, le=1.0)
    historical_score: float = Field(ge=0.0, le=1.0)


class RelevantChunk(BaseModel):
    start_line: int
    end_line: int
    symbol: str | None = None
    chunk_type: str = "block"
    score: float = 0.0


class FileCandidateEvidence(BaseModel):
    matched_keywords: list[str] = Field(default_factory=list)
    matched_symbols: list[str] = Field(default_factory=list)
    dependency_chain: list[str] = Field(default_factory=list)
    relevant_chunks: list[RelevantChunk] = Field(default_factory=list)


class FileCandidate(BaseModel):
    file_path: str
    file_id: str
    final_score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)
    signals: FileCandidateSignals
    evidence: FileCandidateEvidence
    explanation: str | None = None


class BugLocalizationResult(BaseModel):
    repository_id: str
    issue_analysis: IssueAnalysis
    candidates: list[FileCandidate]
    total_files_analyzed: int
    analysis_summary: str
