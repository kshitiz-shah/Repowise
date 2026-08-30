# RepoWise

RepoWise is an AI-powered repository intelligence platform. It includes a Node/Express backend and an independent FastAPI AI service for repository indexing, RAG, deterministic architecture analysis, and structured issue analysis.

## Architecture

The API follows a deliberate request flow: **route → middleware → controller → service → Prisma/external service**. Controllers only translate HTTP requests and responses; auth, repository rules, and GitHub communication live in dedicated services.

- `server/src/config` — validated environment configuration and the Prisma client.
- `server/src/controllers` — thin HTTP handlers.
- `server/src/services` — authentication, user, repository, and GitHub business logic.
- `server/src/middleware` — security, request validation, authentication, rate limiting, and error handling.
- `server/src/validators` — Zod schemas for untrusted input.
- `server/src/utils` — reusable password, JWT, and API-error utilities.
- `server/prisma` — PostgreSQL schema and the initial migration.
- `ai-service` — FastAPI service for Qdrant, embeddings, LLM providers, RAG, and architecture analysis.

The database already models repository files, dependencies, issues, bug-to-file mappings, and analysis jobs so the future intelligence features can be added without redesigning the core data relationships.

## Run locally

1. Start PostgreSQL: `docker compose up -d postgres`
2. Copy `server/.env.example` to `server/.env` and replace the JWT secrets with unique random values.
3. Install backend packages: `cd server && npm install`
4. Apply migrations: `npm run prisma:deploy`
5. Start the API: `npm run dev`

The health endpoint is `GET http://localhost:3000/api/health`.

### AI service

1. Start Qdrant: `docker run --rm -p 6333:6333 -p 6334:6334 qdrant/qdrant`
2. Copy `ai-service/.env.example` to `ai-service/.env`.
3. Generate one long random `AI_SERVICE_API_KEY`; put the exact same value in `server/.env` and `ai-service/.env`.
4. Add a Gemini or Groq API key only to `ai-service/.env`.
5. Run `cd ai-service && source .venv/bin/activate && pip install -r requirements.txt && python run.py`.

The local AI service uses port `8000` because port `5000` is commonly occupied by macOS services. The Node backend calls it internally; the frontend should call only the Node backend.

## Phase 1 API

All responses use `{ success, data }` or `{ success, error }`.

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout` (Bearer token required)
- `GET /api/auth/me` (Bearer token required)
- `POST /api/repositories` (Bearer token required)
- `GET /api/repositories` (Bearer token required)
- `GET /api/repositories/:id` (Bearer token required)
- `DELETE /api/repositories/:id` (owner only; Bearer token required)
- `POST /api/repositories/:id/index` (Bearer token required)
- `POST /api/repositories/:id/architecture` (Bearer token required)
- `POST /api/repositories/:id/query` (Bearer token required)
- `POST /api/repositories/:id/issues/analyze` (Bearer token required)

The index and architecture routes fetch up to 100 supported source files from the public GitHub repository, store file metadata in PostgreSQL, then send source content to the AI service using its private service key. `architecture` returns file nodes and local-import edges ready for a graph UI. Run `index` before using `query`.

Access tokens are short-lived JWTs. Refresh credentials are opaque, HttpOnly cookies and only their Argon2id hashes are stored in PostgreSQL; logout revokes the backing session, invalidating subsequent authenticated requests.
