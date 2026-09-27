import logging
import re
from pathlib import PurePosixPath
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.bug_localization import (
    BugLocalizationResult,
    CommitItem,
    FileCandidate,
    FileCandidateEvidence,
    FileCandidateSignals,
    IssueAnalysis,
    RelevantChunk,
)
from app.api.schemas.issues import IssueInput
from app.api.schemas.repository import RepositoryFile
from app.models.document import CodeChunk, CodeDocument
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.retrieval_service import QueryClassifier
from app.services.vector_service import VectorService
from app.utils.chunking import chunk_document
from app.utils.parsing import detect_language, extract_imports, resolve_import

logger = logging.getLogger("repowise.ai.bug_localization")

_BUG_COMMIT_KEYWORDS = re.compile(
    r"\b(fix|fixed|fixes|bug|bugs|issue|issues|defect|error|resolve|resolved|patch|prevent|crash|failure)\b",
    re.IGNORECASE,
)

_MAX_EXPLANATION_CONTEXT_CHARS = 24_000


class CandidateExplanationItem(BaseModel):
    file_path: str
    explanation: str


class BugExplanationResponse(BaseModel):
    analysis_summary: str = Field(description="High-level summary of the bug analysis and root cause hypothesis")
    file_explanations: list[CandidateExplanationItem] = Field(default_factory=list)


class BugLocalizationService:
    """
    Multi-signal bug localization pipeline:
    1. Issue Understanding: LLM structured analysis (summary, errors, entities, paths, concepts).
    2. Candidate Retrieval: Multi-query semantic search + entity/path symbol matching.
    3. Multi-Signal Scoring: 5 explainable signals (semantic, keyword, dependency, path, historical).
    4. LLM Explanation: Grounded code reasoning for top-K candidates.
    """

    def __init__(
        self,
        llm: LLMService,
        embeddings: EmbeddingService,
        vectors: VectorService,
    ) -> None:
        self._llm = llm
        self._embeddings = embeddings
        self._vectors = vectors

    def localize(
        self,
        repository_id: str,
        issue: IssueInput,
        documents: list[CodeDocument],
        commit_history: list[CommitItem] | None = None,
        top_k: int = 5,
        include_explanation: bool = True,
    ) -> BugLocalizationResult:
        logger.info(
            "[Bug Localization] Starting localization for repo %s, issue #%s: '%s'",
            repository_id, issue.number, issue.title,
        )

        doc_by_path: dict[str, CodeDocument] = {doc.file_path: doc for doc in documents}
        total_files = len(doc_by_path)

        # Stage 1: Issue Analysis (LLM structured extraction with heuristic fallback)
        issue_analysis = self._analyze_issue(issue)
        logger.info(
            "[Issue Analysis] Subsystem: %s | Entities: %s | Hints: %s | Concepts: %s",
            issue_analysis.affected_subsystem,
            issue_analysis.entities[:5],
            issue_analysis.file_path_hints,
            issue_analysis.domain_concepts[:5],
        )

        # Stage 2: Candidate Retrieval (Multi-query semantic + entity/path pool)
        candidate_pool = self._retrieve_candidates(repository_id, issue_analysis, documents)
        logger.info("[Candidate Pool] Retrieved %d candidate files for scoring", len(candidate_pool))

        if not candidate_pool and documents:
            # Fallback if no vector hits: seed pool from all documents up to 25
            for doc in documents[:25]:
                candidate_pool[doc.file_path] = {
                    "file_path": doc.file_path,
                    "file_id": doc.file_id,
                    "vector_score": 0.3,
                    "chunks": [],
                }

        # Stage 3: Multi-Signal Scoring
        scored_candidates = self._score_candidates(
            issue_analysis=issue_analysis,
            candidate_pool=candidate_pool,
            documents=documents,
            commit_history=commit_history or [],
        )

        # Sort descending by final_score
        scored_candidates.sort(key=lambda c: c.final_score, reverse=True)

        # Assign ranks
        for idx, candidate in enumerate(scored_candidates, start=1):
            candidate.rank = idx

        top_candidates = scored_candidates[:top_k]

        # Stage 4: LLM Explanation Generation (Top-K only)
        analysis_summary = f"Identified {len(top_candidates)} high-probability candidate files for Issue #{issue.number}."
        if include_explanation and top_candidates:
            analysis_summary, explanations = self._generate_explanations(
                issue=issue,
                issue_analysis=issue_analysis,
                top_candidates=top_candidates,
                doc_by_path=doc_by_path,
            )
            for candidate in top_candidates:
                if candidate.file_path in explanations:
                    candidate.explanation = explanations[candidate.file_path]
                elif not candidate.explanation:
                    candidate.explanation = self._build_fallback_explanation(candidate)

        logger.info(
            "[Bug Localization] Complete. Top file: %s (score: %.3f)",
            top_candidates[0].file_path if top_candidates else "None",
            top_candidates[0].final_score if top_candidates else 0.0,
        )

        return BugLocalizationResult(
            repository_id=repository_id,
            issue_analysis=issue_analysis,
            candidates=top_candidates,
            total_files_analyzed=total_files,
            analysis_summary=analysis_summary,
        )

    # -------------------------------------------------------------------------
    # Stage 1: Issue Understanding
    # -------------------------------------------------------------------------

    def _analyze_issue(self, issue: IssueInput) -> IssueAnalysis:
        """Extract structured entities, error messages, and search queries using LLM."""
        prompt = (
            "You are a principal software engineer and expert bug triage specialist.\n"
            "Analyze the following GitHub issue and extract key technical signals to help locate "
            "the bug in the source code.\n\n"
            f"ISSUE NUMBER: #{issue.number}\n"
            f"TITLE: {issue.title}\n"
            f"BODY:\n{issue.body or '(No description provided)'}\n\n"
            "Extract:\n"
            "- problem_summary: A concise, technical 1-2 sentence summary of what went wrong or fails.\n"
            "- error_messages: Any error messages, exceptions, or error codes mentioned.\n"
            "- entities: Function names, method names, class names, variable names, interfaces, or symbol names.\n"
            "- file_path_hints: Any file paths, directory fragments, or file names mentioned.\n"
            "- api_endpoints: Any HTTP endpoints, URL routes, or API names mentioned.\n"
            "- domain_concepts: 3-6 core software domain concepts (e.g. 'jwt', 'session', 'database', 'middleware').\n"
            "- affected_subsystem: The likely subsystem or architectural layer (e.g. 'auth', 'database', 'frontend', 'api', 'storage').\n"
            "- search_queries: 2-3 focused search queries for semantic code search."
        )

        try:
            analysis = self._llm.generate_structured(prompt, IssueAnalysis)
            # Ensure search queries has at least one query
            if not analysis.search_queries:
                analysis.search_queries = [f"{issue.title} {analysis.problem_summary}"]
            return analysis
        except Exception as e:
            logger.warning("[Issue Analysis] LLM structured analysis failed: %s. Using heuristic extraction.", e)
            return self._heuristic_analyze_issue(issue)

    def _heuristic_analyze_issue(self, issue: IssueInput) -> IssueAnalysis:
        """Deterministic heuristic fallback for issue analysis."""
        full_text = f"{issue.title}\n{issue.body or ''}"

        # Extract backtick mentions (e.g. `authService.login`)
        backtick_matches = re.findall(r"`([^`\n]{2,60})`", full_text)
        entities = [b.strip() for b in backtick_matches if not re.match(r"^\d+$", b.strip())]

        # Extract potential file paths (e.g. src/auth/login.ts or auth.py)
        path_matches = re.findall(r"\b([a-zA-Z0-9_\-\.\/]+\.[a-zA-Z0-9]{1,5})\b", full_text)
        file_path_hints = [p for p in path_matches if "/" in p or any(p.endswith(ext) for ext in (".ts", ".js", ".py", ".go", ".rs", ".java", ".tsx", ".jsx"))]

        # Extract HTTP endpoints
        endpoint_matches = re.findall(r"(?:POST|GET|PUT|DELETE|PATCH)\s+(\/[a-zA-Z0-9_\-\/]+)", full_text, re.IGNORECASE)
        endpoint_matches += re.findall(r"(\/api\/[a-zA-Z0-9_\-\/]+)", full_text)

        # Extract common error patterns
        error_matches = re.findall(r"((?:Error|Exception|Failed|Crash|NullPointer|TypeError|ReferenceError)[^:\n]*:?[^\n]{0,80})", full_text, re.IGNORECASE)

        # Keywords / domain concepts
        keywords = QueryClassifier.extract_keywords(full_text)
        domain_concepts = keywords[:6]

        search_query = f"{issue.title} {' '.join(entities[:3])}"

        return IssueAnalysis(
            problem_summary=issue.title,
            error_messages=list(dict.fromkeys(error_matches))[:4],
            entities=list(dict.fromkeys(entities))[:10],
            file_path_hints=list(dict.fromkeys(file_path_hints))[:6],
            api_endpoints=list(dict.fromkeys(endpoint_matches))[:4],
            domain_concepts=domain_concepts,
            affected_subsystem="core",
            search_queries=[search_query],
        )

    # -------------------------------------------------------------------------
    # Stage 2: Candidate Retrieval
    # -------------------------------------------------------------------------

    def _retrieve_candidates(
        self,
        repository_id: str,
        issue_analysis: IssueAnalysis,
        documents: list[CodeDocument],
    ) -> dict[str, dict[str, Any]]:
        """
        Multi-query vector retrieval combined with symbol and path matching
        to assemble a candidate pool of 20-30 files.
        """
        candidate_pool: dict[str, dict[str, Any]] = {}

        # 1. Multi-query vector searches
        queries = list(dict.fromkeys([
            issue_analysis.problem_summary,
            *issue_analysis.search_queries,
            " ".join(issue_analysis.entities[:5] + issue_analysis.domain_concepts[:4]),
        ]))

        # Filter out empty queries
        queries = [q for q in queries if q.strip()]

        for query_str in queries[:3]:
            try:
                query_vec = self._embeddings.embed([query_str])[0]
                results = self._vectors.search_similar(repository_id, query_vec, limit=20)
                for chunk in results:
                    fpath = chunk.get("file_path")
                    if not fpath:
                        continue
                    score = float(chunk.get("score", 0.0))
                    if fpath not in candidate_pool:
                        candidate_pool[fpath] = {
                            "file_path": fpath,
                            "file_id": chunk.get("file_id", ""),
                            "vector_score": score,
                            "chunks": [chunk],
                        }
                    else:
                        candidate_pool[fpath]["vector_score"] = max(candidate_pool[fpath]["vector_score"], score)
                        candidate_pool[fpath]["chunks"].append(chunk)
            except Exception as e:
                logger.warning("[Candidate Retrieval] Search failed for query '%s': %s", query_str[:50], e)

        # 2. Add files matching file_path_hints directly
        doc_by_path = {d.file_path: d for d in documents}
        for hint in issue_analysis.file_path_hints:
            hint_clean = hint.lower().strip()
            for doc in documents:
                if hint_clean in doc.file_path.lower():
                    if doc.file_path not in candidate_pool:
                        candidate_pool[doc.file_path] = {
                            "file_path": doc.file_path,
                            "file_id": doc.file_id,
                            "vector_score": 0.5,
                            "chunks": [],
                        }

        # 3. Add files matching exact symbol names in entities
        entity_set = {e.lower() for e in issue_analysis.entities if len(e) >= 3}
        if entity_set:
            for doc in documents:
                if doc.file_path in candidate_pool:
                    continue
                # Quick check if any entity is in doc content
                content_lower = doc.content.lower()
                matched_count = sum(1 for e in entity_set if e in content_lower)
                if matched_count >= 2:
                    candidate_pool[doc.file_path] = {
                        "file_path": doc.file_path,
                        "file_id": doc.file_id,
                        "vector_score": 0.45,
                        "chunks": [],
                    }

        return candidate_pool

    # -------------------------------------------------------------------------
    # Stage 3: Multi-Signal Scoring
    # -------------------------------------------------------------------------

    def _score_candidates(
        self,
        issue_analysis: IssueAnalysis,
        candidate_pool: dict[str, dict[str, Any]],
        documents: list[CodeDocument],
        commit_history: list[CommitItem],
    ) -> list[FileCandidate]:
        """Compute the 5 scoring signals for each candidate file and combine."""
        doc_map = {doc.file_path: doc for doc in documents}
        all_paths = set(doc_map.keys())

        # Precompute dependency graph for candidate files
        dep_graph_out, dep_graph_in = self._build_dependency_graph(documents, all_paths)

        # Precompute commit stats
        commit_bug_counts, commit_total_counts = self._compute_commit_stats(commit_history)
        max_bug_commits = max(commit_bug_counts.values(), default=1)
        max_total_commits = max(commit_total_counts.values(), default=1)
        has_history = len(commit_history) > 0

        # Precompute entities and concepts
        entity_tokens = {e.lower() for e in issue_analysis.entities if len(e) >= 2}
        concept_tokens = {c.lower() for c in issue_analysis.domain_concepts if len(c) >= 2}
        error_tokens = {err.lower() for err in issue_analysis.error_messages if len(err) >= 3}
        path_hint_tokens = {p.lower() for p in issue_analysis.file_path_hints if len(p) >= 2}

        # Pre-chunk documents in pool if they don't have chunk symbols
        doc_symbols_map: dict[str, list[str]] = {}
        for fpath, data in candidate_pool.items():
            doc = doc_map.get(fpath)
            if not doc:
                continue
            symbols: list[str] = []
            for chunk in data.get("chunks", []):
                sym = chunk.get("symbol")
                if sym:
                    symbols.append(sym)
            if not symbols:
                # Extract symbols on the fly
                chunks = chunk_document(doc)
                symbols = [c.symbol for c in chunks if c.symbol]
            doc_symbols_map[fpath] = symbols

        # Score each candidate
        candidates: list[FileCandidate] = []

        # Find top 8 preliminary candidates by raw vector score to measure dependency centrality
        preliminary_top_paths = set(
            sorted(candidate_pool.keys(), key=lambda p: candidate_pool[p]["vector_score"], reverse=True)[:8]
        )

        for fpath, cand_data in candidate_pool.items():
            doc = doc_map.get(fpath)
            doc_content = doc.content if doc else ""
            content_lower = doc_content.lower()

            # Signal 1: Semantic Similarity (0.35)
            raw_v_score = cand_data.get("vector_score", 0.0)
            # Normalize cosine score (typically 0.3 - 0.95 in miniLM)
            semantic_similarity = round(max(0.0, min(1.0, (raw_v_score - 0.25) / 0.70)), 4)

            # Signal 2: Keyword / Symbol Matching (0.25)
            matched_keywords: list[str] = []
            matched_symbols: list[str] = []
            symbols = doc_symbols_map.get(fpath, [])

            # Check symbol matches (highest weight)
            for sym in symbols:
                sym_lower = sym.lower()
                for entity in entity_tokens:
                    if entity in sym_lower or sym_lower in entity:
                        matched_symbols.append(sym)
                        break

            # Check keyword / entity matches in file content and path
            fpath_lower = fpath.lower()
            for entity in entity_tokens:
                if entity in fpath_lower:
                    matched_keywords.append(entity)
                elif entity in content_lower and entity not in matched_keywords:
                    matched_keywords.append(entity)

            for concept in concept_tokens:
                if concept in fpath_lower and concept not in matched_keywords:
                    matched_keywords.append(concept)
                elif concept in content_lower and concept not in matched_keywords:
                    matched_keywords.append(concept)

            for err in error_tokens:
                if err in content_lower and err not in matched_keywords:
                    matched_keywords.append(err[:30])

            # Deduplicate
            matched_symbols = list(dict.fromkeys(matched_symbols))[:8]
            matched_keywords = list(dict.fromkeys(matched_keywords))[:12]

            symbol_weight = min(len(matched_symbols) * 0.35, 0.70)
            keyword_weight = min(len(matched_keywords) * 0.10, 0.30)
            keyword_score = round(min(1.0, symbol_weight + keyword_weight), 4)

            # Signal 3: Dependency Relevance (0.15)
            # Check how connected this candidate is to other top candidates
            outgoing = dep_graph_out.get(fpath, set())
            incoming = dep_graph_in.get(fpath, set())
            connected_top = (outgoing | incoming) & preliminary_top_paths

            dependency_chain: list[str] = []
            for target in outgoing & preliminary_top_paths:
                dependency_chain.append(f"{fpath} -> {target}")
            for source in incoming & preliminary_top_paths:
                dependency_chain.append(f"{source} -> {fpath}")

            dependency_score = round(min(1.0, len(connected_top) * 0.35), 4)

            # Signal 4: Path / Module Relevance (0.10)
            path_segments = set(re.split(r"[/._\-]", fpath_lower))
            # Check direct hint match
            direct_hint_match = any(hint in fpath_lower for hint in path_hint_tokens if len(hint) >= 3)

            if direct_hint_match:
                path_score = 1.0
            else:
                overlap = path_segments & (concept_tokens | entity_tokens | {issue_analysis.affected_subsystem.lower()})
                path_score = round(min(1.0, len(overlap) * 0.30), 4)

            # Signal 5: Historical Score (0.15)
            if has_history:
                bug_hits = commit_bug_counts.get(fpath, 0)
                total_hits = commit_total_counts.get(fpath, 0)
                norm_bug = bug_hits / max_bug_commits if max_bug_commits > 0 else 0.0
                norm_total = total_hits / max_total_commits if max_total_commits > 0 else 0.0
                historical_score = round(min(1.0, 0.70 * norm_bug + 0.30 * norm_total), 4)
            else:
                historical_score = 0.50  # Neutral baseline when history is unavailable

            # Combined weighted score
            final_score = round(
                0.35 * semantic_similarity
                + 0.25 * keyword_score
                + 0.15 * dependency_score
                + 0.10 * path_score
                + 0.15 * historical_score,
                4,
            )

            # Confidence based on multi-signal agreement
            active_signals = sum([
                1 if semantic_similarity > 0.4 else 0,
                1 if keyword_score > 0.3 else 0,
                1 if dependency_score > 0.2 else 0,
                1 if path_score > 0.3 else 0,
                1 if historical_score > 0.6 else 0,
            ])
            confidence = round(min(1.0, final_score * 0.70 + (active_signals / 5.0) * 0.30), 4)

            # Relevant chunks for display
            relevant_chunks: list[RelevantChunk] = []
            for ch in cand_data.get("chunks", [])[:3]:
                relevant_chunks.append(
                    RelevantChunk(
                        start_line=int(ch.get("start_line", 1)),
                        end_line=int(ch.get("end_line", 1)),
                        symbol=ch.get("symbol"),
                        chunk_type=ch.get("chunk_type", "block"),
                        score=round(float(ch.get("score", 0.0)), 4),
                    )
                )

            signals = FileCandidateSignals(
                semantic_similarity=semantic_similarity,
                keyword_score=keyword_score,
                dependency_score=dependency_score,
                path_score=path_score,
                historical_score=historical_score,
            )

            evidence = FileCandidateEvidence(
                matched_keywords=matched_keywords,
                matched_symbols=matched_symbols,
                dependency_chain=dependency_chain[:5],
                relevant_chunks=relevant_chunks,
            )

            candidates.append(
                FileCandidate(
                    file_path=fpath,
                    file_id=cand_data.get("file_id", doc.file_id if doc else ""),
                    final_score=final_score,
                    confidence=confidence,
                    rank=1,  # will be reassigned after sorting
                    signals=signals,
                    evidence=evidence,
                    explanation=None,
                )
            )

        return candidates

    def _build_dependency_graph(
        self,
        documents: list[CodeDocument],
        all_paths: set[str],
    ) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Build bidirectional import dependency graph for all documents."""
        outgoing: dict[str, set[str]] = {doc.file_path: set() for doc in documents}
        incoming: dict[str, set[str]] = {doc.file_path: set() for doc in documents}

        for doc in documents:
            imports = extract_imports(doc.content, doc.language)
            for imp in imports:
                resolved = resolve_import(doc.file_path, imp, all_paths, doc.language)
                if resolved and resolved != doc.file_path:
                    outgoing[doc.file_path].add(resolved)
                    if resolved in incoming:
                        incoming[resolved].add(doc.file_path)

        return outgoing, incoming

    def _compute_commit_stats(
        self,
        commits: list[CommitItem],
    ) -> tuple[dict[str, int], dict[str, int]]:
        """Count bug-fixing commits and total commits per file path."""
        bug_counts: dict[str, int] = {}
        total_counts: dict[str, int] = {}

        for commit in commits:
            is_bug_commit = bool(_BUG_COMMIT_KEYWORDS.search(commit.message))
            for f in commit.files:
                path = f.filename
                total_counts[path] = total_counts.get(path, 0) + 1
                if is_bug_commit:
                    bug_counts[path] = bug_counts.get(path, 0) + 1

        return bug_counts, total_counts

    # -------------------------------------------------------------------------
    # Stage 4: LLM Grounded Explanation
    # -------------------------------------------------------------------------

    def _generate_explanations(
        self,
        issue: IssueInput,
        issue_analysis: IssueAnalysis,
        top_candidates: list[FileCandidate],
        doc_by_path: dict[str, CodeDocument],
    ) -> tuple[str, dict[str, str]]:
        """
        Generate grounded reasoning explanations for the top-ranked files
        in a single structured LLM call.
        """
        code_context_blocks: list[str] = []
        total_chars = 0

        for candidate in top_candidates:
            doc = doc_by_path.get(candidate.file_path)
            content_snippet = ""
            if doc:
                # If there are relevant chunks, use the top chunk
                if candidate.evidence.relevant_chunks:
                    top_chunk = candidate.evidence.relevant_chunks[0]
                    lines = doc.content.splitlines()
                    start = max(0, top_chunk.start_line - 1)
                    end = min(len(lines), top_chunk.end_line + 5)
                    content_snippet = "\n".join(lines[start:end])
                else:
                    # Take first 40 lines
                    content_snippet = "\n".join(doc.content.splitlines()[:40])

            block = (
                f"--- FILE: {candidate.file_path} (Score: {candidate.final_score:.2f}, Rank: {candidate.rank}) ---\n"
                f"Matched Symbols: {', '.join(candidate.evidence.matched_symbols) or 'None'}\n"
                f"Matched Keywords: {', '.join(candidate.evidence.matched_keywords[:6]) or 'None'}\n"
                f"Dependencies: {', '.join(candidate.evidence.dependency_chain[:2]) or 'None'}\n"
                f"Code Excerpt:\n{content_snippet}\n"
            )

            if total_chars + len(block) > _MAX_EXPLANATION_CONTEXT_CHARS:
                break

            code_context_blocks.append(block)
            total_chars += len(block)

        code_context_str = "\n".join(code_context_blocks)

        prompt = (
            "You are a Principal Software Architect performing root cause triage on a repository bug report.\n\n"
            f"BUG REPORT:\n"
            f"Title: #{issue.number} {issue.title}\n"
            f"Description: {issue.body or '(No description provided)'}\n"
            f"Extracted Problem: {issue_analysis.problem_summary}\n\n"
            f"TOP CANDIDATE FILES (identified via multi-signal analysis):\n"
            f"{code_context_str}\n\n"
            "TASK:\n"
            "1. In 'analysis_summary', provide a 2-3 sentence overview explaining the probable root cause of the bug "
            "and how the affected files interact.\n"
            "2. For each candidate file in 'file_explanations', provide a concise 2-3 sentence technical explanation of "
            "WHY this file is likely responsible or affected. Explicitly reference relevant function/method names, "
            "variables, or line logic from the code excerpt.\n\n"
            "Return valid JSON matching the BugExplanationResponse schema."
        )

        try:
            response = self._llm.generate_structured(prompt, BugExplanationResponse)
            explanations_map = {item.file_path: item.explanation for item in response.file_explanations}
            summary = response.analysis_summary.strip() or f"Analyzed candidate files for Issue #{issue.number}."
            return summary, explanations_map
        except Exception as e:
            logger.warning("[Explanation Generation] LLM explanation call failed: %s. Using heuristic explanations.", e)
            fallback_map = {c.file_path: self._build_fallback_explanation(c) for c in top_candidates}
            return f"Multi-signal analysis identified {len(top_candidates)} candidate files matching Issue #{issue.number}.", fallback_map

    def _build_fallback_explanation(self, candidate: FileCandidate) -> str:
        """Deterministic explanation when LLM is unavailable."""
        reasons: list[str] = []
        if candidate.signals.semantic_similarity > 0.5:
            reasons.append(f"strong semantic similarity ({candidate.signals.semantic_similarity:.2f})")
        if candidate.evidence.matched_symbols:
            reasons.append(f"matching declared symbols ({', '.join(candidate.evidence.matched_symbols[:3])})")
        if candidate.evidence.matched_keywords:
            reasons.append(f"matching technical keywords ({', '.join(candidate.evidence.matched_keywords[:4])})")
        if candidate.evidence.dependency_chain:
            reasons.append("direct import dependency with affected subsystem components")
        if candidate.signals.historical_score > 0.6:
            reasons.append("frequent modification history in past bug-fixing commits")

        if not reasons:
            reasons.append("structural and semantic alignment with the reported issue")

        return (
            f"Ranked #{candidate.rank} with a confidence score of {candidate.final_score:.2f} due to "
            + "; ".join(reasons)
            + "."
        )
