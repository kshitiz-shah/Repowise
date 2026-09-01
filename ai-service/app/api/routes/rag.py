import logging
from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.indexing import IndexRepositoryRequest
from app.api.schemas.rag import RagQueryData, RagQueryRequest
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.indexing_service import IndexingService
from app.services.llm_service import LLMService, get_llm_service
from app.services.qdrant_service import QdrantService, get_qdrant_service
from app.services.repository_service import to_code_documents
from app.services.retrieval_service import RetrievalService
from app.services.vector_service import VectorService

logger = logging.getLogger("repowise.ai.rag_api")

router = APIRouter(tags=["rag"], dependencies=[Depends(require_service_key)])

# Approximate character budget for context to stay within Gemini's input token limit.
# gemini-3.6-flash supports ~1M tokens, but we keep a conservative limit to avoid
# unnecessary latency and cost. 1 token ≈ 4 chars, so 60k chars ≈ 15k tokens.
_MAX_CONTEXT_CHARS = 60_000


@router.post("/rag/query", response_model=SuccessResponse[RagQueryData])
def query_rag(
    request: RagQueryRequest,
    embeddings: EmbeddingService = Depends(get_embedding_service),
    qdrant: QdrantService = Depends(get_qdrant_service),
    llm: LLMService = Depends(get_llm_service),
) -> SuccessResponse[RagQueryData]:
    vector_service = VectorService(qdrant)
    documents, _ = to_code_documents(request.repository_id, request.files) if request.files else ([], 0)

    # Step 1 (inspired by RAG_AI): Transform query into search-optimized terms
    search_query = llm.transform_query(request.question)

    retrieval = RetrievalService(embeddings, vector_service)
    results = retrieval.retrieve(
        request.repository_id,
        request.question,
        top_k=request.top_k,
        documents=documents,
        search_query=search_query,
    )

    # If no vectors found and files were supplied, automatically index on demand
    if not results and request.files:
        logger.info(
            "[On-Demand Indexing] Repository %s has no vectors yet. Auto-indexing %d files...",
            request.repository_id, len(request.files),
        )
        try:
            indexing_service = IndexingService(embeddings, vector_service)
            indexing_service.index_repository(
                IndexRepositoryRequest(
                    repository_id=request.repository_id,
                    files=request.files,
                    replace_existing=False,
                )
            )
            # Re-retrieve with newly created embeddings
            results = retrieval.retrieve(
                request.repository_id,
                request.question,
                top_k=request.top_k,
                documents=documents,
                search_query=search_query,
            )
        except Exception:
            logger.exception("[On-Demand Indexing] Auto-indexing failed for repository %s", request.repository_id)

    sources = retrieval.sources(results)

    if not results:
        return SuccessResponse(
            data=RagQueryData(
                answer=(
                    "I could not find sufficient code evidence in the indexed repository files to answer your question. "
                    "Please ensure the repository has been indexed, or try rephrasing your question with specific file names or component keywords."
                ),
                sources=[],
            )
        )

    # Build structured code context with clean file & line headers
    context_blocks: list[str] = []
    total_chars = 0
    for item in results:
        symbol_info = f" | Symbol: {item['symbol']}" if item.get("symbol") else ""
        header = f"=== FILE: {item['file_path']} (Lines {item['start_line']}-{item['end_line']}{symbol_info}) ==="
        block = f"{header}\n{item['content']}"

        if total_chars + len(block) > _MAX_CONTEXT_CHARS:
            logger.warning(
                "[Context] Truncating context at %d chars (limit: %d). Dropping remaining %d chunks.",
                total_chars, _MAX_CONTEXT_CHARS, len(results) - len(context_blocks),
            )
            break

        context_blocks.append(block)
        total_chars += len(block)

    context_str = "\n\n---\n\n".join(context_blocks)
    logger.info("[Context] Built %d characters of context from %d code chunks", len(context_str), len(context_blocks))

    # Step 2 (inspired by RAG_AI systemInstruction & grounded prompt engineering):
    system_prompt = (
        "You are RepoWise, a Principal Software Architect and Codebase Intelligence Expert.\n\n"
        "You will be given code context from the repository and a user question.\n"
        "Your task is to answer the user's question accurately and educationally based strictly on the provided repository code evidence.\n\n"
        "STRICT ANSWERING GUIDELINES:\n"
        "1. DIRECT ANSWER: Provide a clear, direct answer in the first 1-2 sentences.\n"
        "2. STEP-BY-STEP FLOW: Walk through the runtime execution flow or architecture using clear numbered steps or bullet points "
        "(e.g., Entry Point -> Controller / Router -> Business Service Logic -> Data Model / Database -> Output).\n"
        "3. EXACT CITATIONS: Mention the specific file paths (`path/to/file`), functions, classes, and line numbers where each part is implemented.\n"
        "4. ACCURACY & NO HALLUCINATIONS: Base your answer ONLY on the provided code context. "
        "If some detail is not visible in the context, explicitly state what is visible and what is not in the context.\n"
        "5. FORMATTING: Use clean Markdown with headers, bold text, bullet points, and code snippets where relevant.\n\n"
        f"REPOSITORY CODE EVIDENCE:\n{context_str}\n\n"
        f"USER QUESTION: {request.question}\n\n"
        "EXPERT CODEBASE EXPLANATION:"
    )

    logger.info("[LLM] Sending grounded Q&A prompt to provider (total prompt: %d chars)", len(system_prompt))

    try:
        answer_text = llm.generate_text(system_prompt)
    except Exception:
        logger.exception("[LLM Error] Generation failed. Full traceback above.")
        answer_text = (
            "An error occurred while generating the answer. "
            "This may be due to API limits or context length. "
            "Please try asking a more specific question or try again in a moment."
        )

    return SuccessResponse(data=RagQueryData(answer=answer_text, sources=sources))
