import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import architecture, bug_localization, health, hotspots, indexing, issues, rag, readme, test, triage
from app.config import get_settings
from app.services.qdrant_service import QdrantUnavailableError
from app.services.embedding_service import EmbeddingError
from app.services.llm_service import LLMUnavailableError

logger = logging.getLogger("repowise.ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan handler — runs startup logic before yielding, cleanup after."""
    # --- Startup ---
    try:
        from app.services.qdrant_service import get_qdrant_service
        from app.services.vector_service import VectorService
        vs = VectorService(get_qdrant_service())
        vs.ensure_repository_index()
        logger.info("Qdrant repository_id payload index verified")
    except Exception as e:
        logger.warning("Qdrant startup index check skipped: %s", e)

    yield  # Application runs here

    # --- Shutdown (if needed) ---


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="RepoWise AI Service", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def log_request(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("Unhandled request failure", extra={"request_id": request_id})
            raise
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "%s %s -> %s in %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, __: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Invalid request"}},
        )

    @app.exception_handler(QdrantUnavailableError)
    async def qdrant_unavailable_handler(_: Request, __: QdrantUnavailableError):
        return JSONResponse(
            status_code=503,
            content={"success": False, "error": {"code": "QDRANT_UNAVAILABLE", "message": "Vector database is unavailable"}},
        )

    @app.exception_handler(EmbeddingError)
    async def embedding_error_handler(_: Request, __: EmbeddingError):
        return JSONResponse(status_code=503, content={"success": False, "error": {"code": "EMBEDDING_UNAVAILABLE", "message": "Embedding service is unavailable"}})

    @app.exception_handler(LLMUnavailableError)
    async def llm_error_handler(_: Request, __: LLMUnavailableError):
        return JSONResponse(status_code=503, content={"success": False, "error": {"code": "LLM_UNAVAILABLE", "message": "Language model is unavailable"}})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, error: Exception):
        logger.exception("Unhandled application error", exc_info=error)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "INTERNAL_SERVER_ERROR", "message": "Internal server error"}},
        )

    app.include_router(health.router, prefix="/api")
    app.include_router(test.router, prefix="/api")
    app.include_router(indexing.router, prefix="/api")
    app.include_router(rag.router, prefix="/api")
    app.include_router(architecture.router, prefix="/api")
    app.include_router(issues.router, prefix="/api")
    app.include_router(bug_localization.router, prefix="/api")
    app.include_router(triage.router, prefix="/api")
    app.include_router(hotspots.router, prefix="/api")
    app.include_router(readme.router, prefix="/api")

    logger.info("Configured %s for %s", settings.service_name, settings.environment)
    return app


app = create_app()
