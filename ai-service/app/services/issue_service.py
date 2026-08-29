from app.api.schemas.issues import AnalyzeIssueRequest, IssueAnalysisData
from app.services.llm_service import LLMService


class IssueService:
    """LLM-assisted issue classification; its output is evidence, not ground truth."""

    def __init__(self, llm: LLMService) -> None:
        self._llm = llm

    def analyze(self, request: AnalyzeIssueRequest) -> IssueAnalysisData:
        issue = request.issue
        prompt = f"""Analyze this GitHub issue for repository {request.repository_id}.

Title: {issue.title}
Body: {issue.body or '(no description provided)'}

Classify likely impact, not certainty. Return JSON with exactly these fields:
- severity: one of CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
- confidence: a number from 0 to 1
- reason: concise explanation
- concepts: relevant technical concepts
- affected_components: likely components, if supported by the issue text

Do not claim the classification is confirmed. Use UNKNOWN and lower confidence when information is insufficient."""
        return self._llm.generate_structured(prompt, IssueAnalysisData)
