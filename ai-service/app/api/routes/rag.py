from fastapi import APIRouter, Depends

from app.api.dependencies import require_service_key
from app.api.schemas.common import SuccessResponse
from app.api.schemas.rag import RagQueryData, RagQueryRequest
from app.services.embedding_service import EmbeddingService, get_embedding_service
from app.services.llm_service import LLMService, get_llm_service
from app.services.qdrant_service import QdrantService, get_qdrant_service
from app.services.retrieval_service import RetrievalService
from app.services.vector_service import VectorService

router = APIRouter(tags=["rag"], dependencies=[Depends(require_service_key)])


@router.post("/rag/query", response_model=SuccessResponse[RagQueryData])
def query_rag(request: RagQueryRequest, embeddings: EmbeddingService = Depends(get_embedding_service), qdrant: QdrantService = Depends(get_qdrant_service), llm: LLMService = Depends(get_llm_service)) -> SuccessResponse[RagQueryData]:
    results = RetrievalService(embeddings, VectorService(qdrant)).retrieve(request.repository_id, request.question, request.top_k)
    sources = RetrievalService.sources(results)
    if not results:
        return SuccessResponse(data=RagQueryData(answer="The repository context does not provide enough information to answer this question.", sources=[]))
    context = "\n\n".join(f"[{item['file_path']}:{item['start_line']}-{item['end_line']}]\n{item['content']}" for item in results)
    prompt = (
        "Answer only from the repository context below. If it is insufficient, say so explicitly. "
        "Do not invent behavior.\n\n"
        f"Question: {request.question}\n\nRepository context:\n{context}"
    )
    return SuccessResponse(data=RagQueryData(answer=llm.generate_text(prompt), sources=sources))
