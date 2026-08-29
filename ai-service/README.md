# RepoWise AI Service

The independent Python service for repository intelligence. It receives repository context from the Node backend; it does not manage users, passwords, JWTs, or PostgreSQL.

## Run locally

```bash
cd ai-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Set a secure `AI_SERVICE_API_KEY` in `.env` before running. The service starts at `http://localhost:5000` by default.

## Current endpoints

- `GET /api/health` — public liveness check.
- `GET /api/test` — service-to-service authentication check. Send `Authorization: Bearer <AI_SERVICE_API_KEY>`.
- `GET /api/health/qdrant` — protected Qdrant connectivity check.
- `POST /api/index/repository` — index code files sent by the Node backend.
- `POST /api/rag/query` — answer a question from indexed repository context.
- `POST /api/architecture/analyze` — return a file dependency graph for the frontend to draw.
- `POST /api/issues/analyze` — return an LLM-assisted, structured severity assessment.

## Qdrant

Run Qdrant locally before using the protected connectivity endpoint:

```bash
docker run --rm -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Set `QDRANT_URL` and, for Qdrant Cloud, `QDRANT_API_KEY` in `.env`. The service deliberately exposes only a Qdrant adapter at this stage; collection creation and vector operations arrive with repository indexing.

## Repository architecture analysis

The Node backend fetches/clones GitHub content, then sends the relevant files. This preserves the boundary: the AI service has no GitHub-user credentials or authentication responsibilities.

```http
POST /api/architecture/analyze
Authorization: Bearer <AI_SERVICE_API_KEY>
Content-Type: application/json
```

```json
{
  "repository_id": "repo-123",
  "files": [
    {"file_id": "server", "path": "src/server.ts", "content": "import { auth } from './auth';"},
    {"file_id": "auth", "path": "src/auth.ts", "content": "export function auth() {}"}
  ]
}
```

It returns nodes and deterministic `IMPORT` edges; use those directly in React Flow. The service resolves local JavaScript/TypeScript and relative Python imports. External packages are intentionally omitted because they are not repository files.
