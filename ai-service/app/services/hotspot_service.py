import logging
import re
from collections import defaultdict
from typing import Dict, List, Set

from app.api.schemas.hotspots import (
    CommitHotspotInput,
    ComponentHotspotResult,
    DependencyHotspotInput,
    FileHotspotEvidence,
    FileHotspotInput,
    FileHotspotResult,
    HotspotCalculationRequest,
    HotspotCalculationResponse,
)

logger = logging.getLogger("repowise.hotspots")

BUG_FIX_KEYWORDS = re.compile(
    r"\b(fix|fixed|fixes|bug|bugs|patch|patched|resolve|resolved|resolves|issue|crash|crashed|error|exception|hotfix|leak)\b",
    re.IGNORECASE,
)


class HotspotService:
    def __init__(self):
        pass

    def calculate_hotspots(self, request: HotspotCalculationRequest) -> HotspotCalculationResponse:
        files = request.files
        if not files:
            return HotspotCalculationResponse(
                repository_id=request.repository_id,
                components=[],
                files=[],
                high_risk_count=0,
                medium_risk_count=0,
                low_risk_count=0,
            )

        # 1. Index files by path and name
        file_path_map: Dict[str, FileHotspotInput] = {f.path: f for f in files}
        file_id_map: Dict[str, FileHotspotInput] = {f.id: f for f in files}

        # 2. Count commit churn and bug-fix commits per file
        churn_counts: Dict[str, int] = defaultdict(int)
        bug_fix_counts: Dict[str, int] = defaultdict(int)

        for commit in request.commits:
            is_bug_fix = bool(BUG_FIX_KEYWORDS.search(commit.message or ""))
            for commit_file in commit.files:
                # Find matching file in our index
                matched_path = self._find_matching_path(commit_file, file_path_map)
                if matched_path:
                    churn_counts[matched_path] += 1
                    if is_bug_fix:
                        bug_fix_counts[matched_path] += 1

        # 3. Count bug mappings per file
        bug_counts: Dict[str, int] = defaultdict(int)
        for bm in request.bug_mappings:
            matched_path = None
            if bm.file_id and bm.file_id in file_id_map:
                matched_path = file_id_map[bm.file_id].path
            elif bm.file_path:
                matched_path = self._find_matching_path(bm.file_path, file_path_map)

            if matched_path:
                bug_counts[matched_path] += 1

        # 4. Count architectural dependencies (in-degree)
        in_degree_counts: Dict[str, int] = defaultdict(int)
        for dep in request.dependencies:
            target_path = self._find_matching_path(dep.target_path, file_path_map)
            if target_path:
                in_degree_counts[target_path] += 1

        # 5. Normalization bases
        max_churn = max(churn_counts.values()) if churn_counts else 1
        max_bugs = max(bug_counts.values()) if bug_counts else 1
        max_bug_fixes = max(bug_fix_counts.values()) if bug_fix_counts else 1
        max_in_degree = max(in_degree_counts.values()) if in_degree_counts else 1

        # Avoid zero division
        max_churn = max(max_churn, 1)
        max_bugs = max(max_bugs, 1)
        max_bug_fixes = max(max_bug_fixes, 1)
        max_in_degree = max(max_in_degree, 1)

        # 6. Compute scores for each file
        file_results: List[FileHotspotResult] = []

        for f in files:
            path = f.path
            c_count = churn_counts.get(path, 0)
            b_count = bug_counts.get(path, 0)
            bf_count = bug_fix_counts.get(path, 0)
            ind_count = in_degree_counts.get(path, 0)

            churn_norm = c_count / max_churn
            bug_norm = b_count / max_bugs
            bf_norm = bf_count / max_bug_fixes
            ind_norm = ind_count / max_in_degree

            # Weighted Formula: 0.35 churn + 0.35 bug density + 0.15 bug fix history + 0.15 centrality
            risk_score = (
                0.35 * churn_norm
                + 0.35 * bug_norm
                + 0.15 * bf_norm
                + 0.15 * ind_norm
            )
            # Round for precision and bounds
            risk_score = min(max(round(risk_score, 4), 0.0), 1.0)
            churn_score = min(max(round(churn_norm, 4), 0.0), 1.0)

            # Determine risk level
            if risk_score >= 0.65:
                risk_level = "CRITICAL"
            elif risk_score >= 0.45:
                risk_level = "HIGH"
            elif risk_score >= 0.25:
                risk_level = "MEDIUM"
            else:
                risk_level = "LOW"

            # Explainable drivers
            drivers: List[str] = []
            if c_count > 0:
                drivers.append(f"Modified across {c_count} recorded commits ({round(churn_norm * 100)}% relative churn)")
            if b_count > 0:
                drivers.append(f"Linked to {b_count} localized bug reports")
            if bf_count > 0:
                drivers.append(f"Touched by {bf_count} bug-fix patches")
            if ind_count > 0:
                drivers.append(f"Imported/depended on by {ind_count} files in the codebase")
            if not drivers:
                drivers.append("Stable file with low historical churn and no bug associations.")

            # Component derivation if not provided
            comp_name = f.component
            if not comp_name:
                parts = path.split("/")
                comp_name = parts[0] if len(parts) > 1 else "root"

            file_results.append(
                FileHotspotResult(
                    id=f.id,
                    path=f.path,
                    name=f.name or (path.split("/")[-1]),
                    language=f.language,
                    lines_of_code=f.lines_of_code,
                    churn_score=churn_score,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    bug_count=b_count,
                    component_name=comp_name,
                    evidence=FileHotspotEvidence(
                        churn_commits=c_count,
                        bug_associations=b_count,
                        bug_fix_commits=bf_count,
                        in_degree=ind_count,
                        drivers=drivers,
                    ),
                )
            )

        # Sort files by risk score descending
        file_results.sort(key=lambda x: (x.risk_score, x.churn_score), reverse=True)

        # 7. Aggregate by component
        component_groups: Dict[str, List[FileHotspotResult]] = defaultdict(list)
        for fr in file_results:
            comp = fr.component_name or "root"
            component_groups[comp].append(fr)

        component_results: List[ComponentHotspotResult] = []
        for comp_name, comp_files in component_groups.items():
            avg_risk = sum(cf.risk_score for cf in comp_files) / len(comp_files)
            max_risk = max(cf.risk_score for cf in comp_files)
            total_c = sum(cf.evidence.churn_commits for cf in comp_files)
            total_b = sum(cf.bug_count for cf in comp_files)

            # Determine component risk level
            if max_risk >= 0.70 or avg_risk >= 0.50:
                c_level = "CRITICAL"
            elif max_risk >= 0.50 or avg_risk >= 0.35:
                c_level = "HIGH"
            elif avg_risk >= 0.20:
                c_level = "MEDIUM"
            else:
                c_level = "LOW"

            component_results.append(
                ComponentHotspotResult(
                    name=comp_name,
                    risk_level=c_level,
                    avg_risk_score=round(avg_risk, 4),
                    max_risk_score=round(max_risk, 4),
                    file_count=len(comp_files),
                    total_churn=total_c,
                    total_bug_density=total_b,
                )
            )

        # Sort components by risk
        component_results.sort(key=lambda c: (c.avg_risk_score, c.max_risk_score), reverse=True)

        high_count = sum(1 for f in file_results if f.risk_level in ("CRITICAL", "HIGH"))
        med_count = sum(1 for f in file_results if f.risk_level == "MEDIUM")
        low_count = sum(1 for f in file_results if f.risk_level == "LOW")

        return HotspotCalculationResponse(
            repository_id=request.repository_id,
            components=component_results,
            files=file_results,
            high_risk_count=high_count,
            medium_risk_count=med_count,
            low_risk_count=low_count,
        )

    def _find_matching_path(self, target: str, path_map: Dict[str, FileHotspotInput]) -> str | None:
        if target in path_map:
            return target
        clean_target = target.strip("/").lower()
        for p in path_map:
            clean_p = p.strip("/").lower()
            if clean_p == clean_target or clean_p.endswith(clean_target) or clean_target.endswith(clean_p):
                return p
        return None
