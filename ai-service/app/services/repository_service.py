from app.api.schemas.repository import RepositoryFile
from app.models.document import CodeDocument
from app.utils.parsing import detect_language

SUPPORTED_LANGUAGES = {"python", "typescript", "tsx", "javascript", "jsx", "java", "go", "rust", "csharp", "cpp", "c"}


def to_code_documents(repository_id: str, files: list[RepositoryFile]) -> tuple[list[CodeDocument], int]:
    """Filter input once, keeping routing code independent of file rules."""
    documents: list[CodeDocument] = []
    skipped = 0
    for file in files:
        language = detect_language(file.path)
        if language not in SUPPORTED_LANGUAGES:
            skipped += 1
            continue
        documents.append(CodeDocument(repository_id, file.file_id, file.path, file.content, language))
    return documents, skipped
