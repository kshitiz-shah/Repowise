import logging
import re
from typing import Any
import numpy as np
from pydantic import BaseModel, Field

from app.api.schemas.triage import (
    BatchTriageRequest,
    BatchTriageResponse,
    IssueToTriage,
    RelatedIssueRef,
    TriageSummary,
    TriagedIssue,
)
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

logger = logging.getLogger("repowise.ai.triage")

SEVERITY_SCORES = {
    "CRITICAL": 1.0,
    "HIGH": 0.8,
    "MEDIUM": 0.5,
    "LOW": 0.2,
    "UNKNOWN": 0.3,
}

VALID_CATEGORIES = [
    "Bug",
    "Feature Request",
    "Enhancement",
    "Documentation",
    "Performance",
    "Security",
    "UI/UX",
    "Configuration",
    "Build/Deployment",
    "Other",
]


class SingleIssueAnalysis(BaseModel):
    issue_number: int
    severity: str = "UNKNOWN"
    category: str = "Bug"
    confidence: float = 0.5
    reason: str = ""
    affected_subsystem: str = "core"


class BatchAnalysisResult(BaseModel):
    classifications: list[SingleIssueAnalysis] = Field(default_factory=list)


class TriageService:
    def __init__(self, llm: LLMService, embeddings: EmbeddingService) -> None:
        self._llm = llm
        self._embeddings = embeddings

    def triage_repository_issues(self, request: BatchTriageRequest) -> BatchTriageResponse:
        logger.info(
            "[Triage] Starting batch triage for repo %s with %d issues",
            request.repository_id,
            len(request.issues),
        )

        if not request.issues:
            return BatchTriageResponse(
                repository_id=request.repository_id,
                summary=TriageSummary(total_issues=0),
                issues=[],
            )

        # 1. Classify severity and category (batched LLM calls)
        classified_map = self._classify_issues(request.issues, request.architecture_components)

        # 2. Semantic Duplicate & Related Issue Detection
        duplicate_groups, related_map = self._detect_duplicates_and_relations(request.issues)

        # 3. Assemble TriagedIssue list
        triaged_issues: list[TriagedIssue] = []
        for issue in request.issues:
            c = classified_map.get(issue.number, self._heuristic_classify(issue))
            dup_group = duplicate_groups.get(issue.number)
            is_dup = bool(dup_group and dup_group.get("is_duplicate", False))
            group_id = dup_group.get("group_id") if dup_group else None
            related = related_map.get(issue.number, [])

            severity_clean = c.severity.upper() if c.severity.upper() in SEVERITY_SCORES else "UNKNOWN"
            score = SEVERITY_SCORES.get(severity_clean, 0.3)

            category_clean = c.category if c.category in VALID_CATEGORIES else "Bug"

            triaged_issues.append(
                TriagedIssue(
                    number=issue.number,
                    title=issue.title,
                    body=issue.body,
                    labels=issue.labels,
                    severity=severity_clean,  # type: ignore
                    severity_score=round(score, 2),
                    category=category_clean,
                    confidence=round(max(0.1, min(1.0, c.confidence)), 2),
                    reason=c.reason or f"Categorized as {category_clean} with {severity_clean} severity.",
                    affected_subsystem=c.affected_subsystem or "core",
                    duplicate_group_id=group_id,
                    is_duplicate=is_dup,
                    related_issues=related,
                )
            )

        # 4. Generate summary
        summary = self._compute_summary(triaged_issues)

        logger.info(
            "[Triage] Complete for repo %s. Critical: %d, High: %d, Medium: %d, Low: %d, Duplicates: %d",
            request.repository_id,
            summary.critical_count,
            summary.high_count,
            summary.medium_count,
            summary.low_count,
            summary.duplicate_groups_count,
        )

        return BatchTriageResponse(
            repository_id=request.repository_id,
            summary=summary,
            issues=triaged_issues,
        )

    def _classify_issues(
        self,
        issues: list[IssueToTriage],
        architecture_components: list[str],
    ) -> dict[int, SingleIssueAnalysis]:
        """Classify issues in batches of up to 8 using LLM structured generation."""
        results: dict[int, SingleIssueAnalysis] = {}
        batch_size = 8

        for i in range(0, len(issues), batch_size):
            chunk = issues[i : i + batch_size]
            prompt = self._build_classification_prompt(chunk, architecture_components)
            try:
                batch_res = self._llm.generate_structured(prompt, BatchAnalysisResult)
                for item in batch_res.classifications:
                    results[item.issue_number] = item
            except Exception as e:
                logger.warning("[Triage] LLM classification batch failed: %s. Using heuristics.", e)
                for issue in chunk:
                    results[issue.number] = self._heuristic_classify(issue)

        # Backfill any missing issues with heuristics
        for issue in issues:
            if issue.number not in results:
                results[issue.number] = self._heuristic_classify(issue)

        return results

    def _build_classification_prompt(
        self,
        issues: list[IssueToTriage],
        architecture_components: list[str],
    ) -> str:
        component_hints = f"Known architecture components: {', '.join(architecture_components[:8])}" if architecture_components else ""

        issues_text = ""
        for issue in issues:
            label_text = f" (Labels: {', '.join(issue.labels)})" if issue.labels else ""
            desc = (issue.body or "").strip()[:300].replace("\n", " ")
            issues_text += f"\n- Issue #{issue.number}: \"{issue.title}\"{label_text}\n  Description: {desc or '(No description)'}"

        return (
            "You are a Senior Engineering Lead triaging GitHub issues for a repository.\n"
            f"{component_hints}\n"
            "Analyze each issue and classify its severity, category, confidence, and reason.\n\n"
            "SEVERITY GUIDELINES (do not claim certainty, use UNKNOWN if unsure):\n"
            "- CRITICAL: Complete service crash, data loss, security breach, total auth block.\n"
            "- HIGH: Major feature broken, severe regression, blocking flow without workaround.\n"
            "- MEDIUM: Functional bug with workaround, non-critical validation error.\n"
            "- LOW: Cosmetic UI flaw, minor text typo, small non-blocking request.\n"
            "- UNKNOWN: Insufficient details or ambiguous report.\n\n"
            "CATEGORIES: Bug, Feature Request, Enhancement, Documentation, Performance, Security, UI/UX, Configuration, Build/Deployment, Other.\n\n"
            f"ISSUES TO CLASSIFY:{issues_text}\n\n"
            "Return valid JSON matching the BatchAnalysisResult schema with a classification for every issue."
        )

    def _heuristic_classify(self, issue: IssueToTriage) -> SingleIssueAnalysis:
        """Deterministic heuristic classifier based on keywords and existing labels."""
        text = f"{issue.title} {issue.body} {' '.join(issue.labels)}".lower()

        # Severity heuristic
        if any(w in text for w in ("cve", "vulnerability", "exploit", "data loss", "corrupt", "unusable", "critical")):
            severity = "CRITICAL"
            confidence = 0.85
            reason = "High risk security, data integrity, or complete outage keywords detected."
        elif any(w in text for w in ("crash", "infinite loop", "deadlock", "cannot login", "fatal", "out of memory", "panic")):
            severity = "HIGH"
            confidence = 0.80
            reason = "Severe crash, blocking authentication, or fatal execution terms detected."
        elif any(w in text for w in ("error", "fails", "failed", "broken", "incorrect", "invalid", "timeout")):
            severity = "MEDIUM"
            confidence = 0.65
            reason = "Standard functional defect or error message reported."
        elif any(w in text for w in ("typo", "cosmetic", "color", "padding", "alignment", "minor", "docs", "documentation")):
            severity = "LOW"
            confidence = 0.75
            reason = "Cosmetic, documentation, or minor polish issue."
        else:
            severity = "UNKNOWN"
            confidence = 0.40
            reason = "General issue description without clear severity indicators."

        # Category heuristic
        if any(w in text for w in ("security", "cve", "auth", "token", "permission")):
            category = "Security" if "security" in text or "cve" in text else "Bug"
        elif any(w in text for w in ("slow", "latency", "benchmark", "memory leak", "cpu", "performance")):
            category = "Performance"
        elif any(w in text for w in ("doc", "readme", "guide", "tutorial", "typo in docs")):
            category = "Documentation"
        elif any(w in text for w in ("feature", "support for", "add new", "proposal", "rfc")):
            category = "Feature Request"
        elif any(w in text for w in ("ui", "button", "css", "layout", "dark mode", "font")):
            category = "UI/UX"
        elif any(w in text for w in ("docker", "ci", "github actions", "deploy", "build", "webpack", "vite")):
            category = "Build/Deployment"
        elif any(w in text for w in ("config", "env", "settings", "yaml", "toml")):
            category = "Configuration"
        else:
            category = "Bug"

        return SingleIssueAnalysis(
            issue_number=issue.number,
            severity=severity,
            category=category,
            confidence=confidence,
            reason=reason,
            affected_subsystem="core",
        )

    def _detect_duplicates_and_relations(
        self,
        issues: list[IssueToTriage],
    ) -> tuple[dict[int, dict[str, Any]], dict[int, list[RelatedIssueRef]]]:
        """Compute pairwise semantic cosine similarity to detect duplicates and related issues."""
        if len(issues) < 2:
            return {}, {}

        texts = [f"{iss.title}\n{iss.body[:400]}" for iss in issues]
        embeddings = np.array(self._embeddings.embed(texts))  # shape: (N, 384)

        # Normalize rows for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normed_embeddings = embeddings / norms
        sim_matrix = np.dot(normed_embeddings, normed_embeddings.T)

        duplicate_groups: dict[int, dict[str, Any]] = {}
        related_map: dict[int, list[RelatedIssueRef]] = {iss.number: [] for iss in issues}

        group_counter = 1
        visited: set[int] = set()

        for i in range(len(issues)):
            for j in range(i + 1, len(issues)):
                sim = float(sim_matrix[i, j])
                iss_i = issues[i]
                iss_j = issues[j]

                if sim >= 0.70:
                    rel_type = "DUPLICATE" if sim >= 0.85 else "RELATED"
                    related_map[iss_i.number].append(
                        RelatedIssueRef(
                            number=iss_j.number,
                            title=iss_j.title,
                            similarity=round(sim, 2),
                            relation_type=rel_type,
                        )
                    )
                    related_map[iss_j.number].append(
                        RelatedIssueRef(
                            number=iss_i.number,
                            title=iss_i.title,
                            similarity=round(sim, 2),
                            relation_type=rel_type,
                        )
                    )

                    if sim >= 0.85:
                        # Cluster into duplicate group
                        if iss_i.number not in duplicate_groups and iss_j.number not in duplicate_groups:
                            gid = f"dup-cluster-{group_counter}"
                            group_counter += 1
                            duplicate_groups[iss_i.number] = {"group_id": gid, "is_duplicate": False}  # Primary
                            duplicate_groups[iss_j.number] = {"group_id": gid, "is_duplicate": True}   # Duplicate
                        elif iss_i.number in duplicate_groups and iss_j.number not in duplicate_groups:
                            gid = duplicate_groups[iss_i.number]["group_id"]
                            duplicate_groups[iss_j.number] = {"group_id": gid, "is_duplicate": True}
                        elif iss_j.number in duplicate_groups and iss_i.number not in duplicate_groups:
                            gid = duplicate_groups[iss_j.number]["group_id"]
                            duplicate_groups[iss_i.number] = {"group_id": gid, "is_duplicate": True}

        # Sort related issues by similarity descending
        for num in related_map:
            related_map[num].sort(key=lambda r: r.similarity, reverse=True)
            related_map[num] = related_map[num][:5]

        return duplicate_groups, related_map

    def _compute_summary(self, issues: list[TriagedIssue]) -> TriageSummary:
        total = len(issues)
        crit = sum(1 for i in issues if i.severity == "CRITICAL")
        high = sum(1 for i in issues if i.severity == "HIGH")
        med = sum(1 for i in issues if i.severity == "MEDIUM")
        low = sum(1 for i in issues if i.severity == "LOW")
        unk = sum(1 for i in issues if i.severity == "UNKNOWN")

        unique_groups = len({i.duplicate_group_id for i in issues if i.duplicate_group_id})

        categories: dict[str, int] = {}
        for i in issues:
            categories[i.category] = categories.get(i.category, 0) + 1

        return TriageSummary(
            total_issues=total,
            critical_count=crit,
            high_count=high,
            medium_count=med,
            low_count=low,
            unknown_count=unk,
            duplicate_groups_count=unique_groups,
            categories_breakdown=categories,
        )
