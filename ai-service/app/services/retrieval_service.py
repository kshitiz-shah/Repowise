import logging
import re
from typing import Any

from app.api.schemas.rag import SourceReference
from app.models.document import CodeDocument
from app.services.embedding_service import EmbeddingService
from app.services.vector_service import VectorService
from app.utils.parsing import extract_imports, resolve_import

logger = logging.getLogger("repowise.ai.retrieval")


class QueryClassifier:
    """Classifies user technical questions to guide retrieval strategy."""

    @staticmethod
    def classify(query: str) -> str:
        q_lower = query.lower()
        if any(kw in q_lower for kw in ("how does", "request flow", "step by step", "execution", "lifecycle", "what happens when", "how do")):
            return "FLOW"
        if any(kw in q_lower for kw in ("where is", "which file", "where are", "location", "find", "endpoint")):
            return "LOCATION"
        if any(kw in q_lower for kw in ("depends on", "imports", "imported by", "who calls", "dependency")):
            return "DEPENDENCY"
        if any(kw in q_lower for kw in ("why", "error", "fail", "bug", "issue", "crash", "debug")):
            return "DEBUGGING"
        if any(kw in q_lower for kw in ("architecture", "overview", "subsystem", "design", "structure")):
            return "ARCHITECTURE"
        if any(kw in q_lower for kw in (".ts", ".tsx", ".py", ".js", ".go", ".rs", "file")):
            return "FILE"
        return "GENERAL"

    @staticmethod
    def extract_keywords(query: str) -> list[str]:
        # Extract potential symbols, filenames, and keywords
        tokens = re.findall(r"[A-Za-z0-9_.\-/]+", query)
        stopwords = {
            "the", "a", "an", "is", "are", "how", "what", "where", "why", "which",
            "in", "on", "at", "to", "for", "of", "with", "by", "from", "and", "or",
            "does", "do", "when", "this", "that", "it", "my", "code", "repo", "project",
        }
        return [t for t in tokens if len(t) > 2 and t.lower() not in stopwords]


class RetrievalService:
    """Hybrid Code RAG Retrieval combining semantic vector search, AST symbol matching, and dependency graph expansion."""

    def __init__(self, embeddings: EmbeddingService, vectors: VectorService) -> None:
        self._embeddings = embeddings
        self._vectors = vectors

    def retrieve(
        self,
        repository_id: str,
        question: str,
        top_k: int = 10,
        documents: list[CodeDocument] | None = None,
        search_query: str | None = None,
    ) -> list[dict[str, Any]]:
        effective_query = search_query if search_query else question
        query_type = QueryClassifier.classify(question)
        keywords = list(dict.fromkeys(
            QueryClassifier.extract_keywords(question) + 
            (QueryClassifier.extract_keywords(search_query) if search_query else [])
        ))

        logger.info(
            "[Q&A] Processing query: '%s' | Effective Search: '%s' | Type: %s | Keywords: %s",
            question, effective_query, query_type, keywords,
        )

        # 1. Semantic Vector Search with transformed query vector
        query_vector = self._embeddings.embed([effective_query])[0]
        logger.info("[Vector Search] Querying Qdrant for repository_id: %s (limit: %d)", repository_id, top_k * 2)
        raw_vector_results = self._vectors.search_similar(repository_id, query_vector, limit=max(top_k * 2, 16))

        # 2. Dependency Graph Expansion
        # If we have retrieved files, identify imported / importing files to expand flow context
        expanded_chunks: list[dict[str, Any]] = []
        if documents and raw_vector_results:
            path_set = {doc.file_path for doc in documents}
            doc_map = {doc.file_path: doc for doc in documents}
            
            retrieved_files = {res["file_path"] for res in raw_vector_results[:4] if "file_path" in res}
            related_files: set[str] = set()

            for r_file in retrieved_files:
                doc = doc_map.get(r_file)
                if not doc:
                    continue
                # Find outgoing imports
                for imp in extract_imports(doc.content, doc.language):
                    resolved = resolve_import(r_file, imp, path_set, doc.language)
                    if resolved and resolved not in retrieved_files:
                        related_files.add(resolved)

                # Find incoming importers
                for other_path, other_doc in doc_map.items():
                    if other_path in retrieved_files or other_path in related_files:
                        continue
                    for imp in extract_imports(other_doc.content, other_doc.language):
                        resolved = resolve_import(other_path, imp, path_set, other_doc.language)
                        if resolved == r_file:
                            related_files.add(other_path)
                            break

            if related_files:
                logger.info("[Dependency Expansion] Expanding context to related files: %s", list(related_files)[:4])
                expanded_chunks = self._vectors.get_chunks_for_files(repository_id, list(related_files)[:4], limit=4)

        # 3. Combine, Deduplicate, and Rerank
        combined_pool: dict[str, dict[str, Any]] = {}

        # Add vector results
        for res in raw_vector_results:
            chunk_id = str(res.get("file_path", "")) + ":" + str(res.get("start_line", 0))
            score = float(res.get("score", 0.0))
            
            # Boost score if chunk matches query keywords, file path, or declared symbols
            chunk_content_lower = str(res.get("content", "")).lower()
            chunk_symbol = str(res.get("symbol", "")).lower()
            chunk_path_lower = str(res.get("file_path", "")).lower()
            
            keyword_boost = 0.0
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in chunk_symbol:
                    keyword_boost += 0.15
                if kw_lower in chunk_path_lower:
                    keyword_boost += 0.10
                elif kw_lower in chunk_content_lower:
                    keyword_boost += 0.05
                    
            combined_pool[chunk_id] = {**res, "rerank_score": min(score + keyword_boost, 1.0)}

        # Add dependency expanded chunks
        for res in expanded_chunks:
            chunk_id = str(res.get("file_path", "")) + ":" + str(res.get("start_line", 0))
            if chunk_id not in combined_pool:
                # Inherit a moderate score for related context
                combined_pool[chunk_id] = {**res, "rerank_score": 0.65, "score": 0.65}

        # Sort by rerank score descending
        sorted_results = sorted(combined_pool.values(), key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        final_results = sorted_results[:top_k]

        logger.info("[Retrieved] Selected %d chunks across %d files", len(final_results), len({r.get('file_path') for r in final_results}))
        for i, r in enumerate(final_results[:5], 1):
            logger.info("  %d. %s:%s-%s (symbol: %s, score: %.3f)", i, r.get("file_path"), r.get("start_line"), r.get("end_line"), r.get("symbol"), r.get("rerank_score", 0.0))

        return final_results

    @staticmethod
    def sources(results: list[dict[str, Any]]) -> list[SourceReference]:
        seen: set[tuple[str, int, int]] = set()
        sources_list: list[SourceReference] = []

        for item in results:
            key = (str(item.get("file_path")), int(item.get("start_line", 1)), int(item.get("end_line", 1)))
            if key not in seen:
                seen.add(key)
                sources_list.append(
                    SourceReference(
                        file_id=str(item.get("file_id", "")),
                        file_path=str(item.get("file_path", "")),
                        start_line=int(item.get("start_line", 1)),
                        end_line=int(item.get("end_line", 1)),
                        score=float(item.get("rerank_score", item.get("score", 0.0))),
                    )
                )
        return sources_list
