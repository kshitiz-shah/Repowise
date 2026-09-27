# 🧠 RepoWise

> **Autonomous Repository Intelligence Platform**  
> Map architectures, localize bugs to source code, chat with codebases, triage GitHub issues, detect architectural hotspots, and generate comprehensive documentation.

[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Node.js](https://img.shields.io/badge/Node.js-18+-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![Express](https://img.shields.io/badge/Express-4.x-000000?logo=express&logoColor=white)](https://expressjs.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC382D?logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

---

## 🌟 Overview

**RepoWise** is an end-to-end repository intelligence system engineered for engineering teams, open-source maintainers, and developers exploring unfamiliar codebases. By combining static abstract syntax tree (AST) parsing, lexical graph traversal, commit history analysis, dense vector embeddings, and large language model reasoning, RepoWise provides real-time architectural understanding and automated debugging workflows.

---

## 🚀 Key Features

```
                                      REPOWISE PLATFORM
  ┌────────────────────────┬────────────────────────┬────────────────────────┐
  │  🎨 System Architecture │  💬 Code Q&A Assistant │  🐛 Bug → File Mapping │
  │  • GitDiagram Explorer │  • RAG over Codebases  │  • Multi-Signal Ranker │
  │  • Execution Flow Map  │  • Exact Line Evidence │  • Culprit Hypotheses  │
  ├────────────────────────┼────────────────────────┼────────────────────────┤
  │  📝 Auto README Agent  │  📋 Bug Triage Board   │  🔥 Hotspot Detector   │
  │  • Manifest Inspection │  • Semantic Clustering │  • Architectural Risk  │
  │  • Tech Stack Detection│  • Severity & Urgency  │  • Churn & Complexity  │
  └────────────────────────┴────────────────────────┴────────────────────────┘
```

### 1. 🎨 Hierarchical System Architecture & GitDiagram Explorer
- **AST & Semantic Extraction**: Detects controllers, API routes, database models, background queues, and client interfaces.
- **Interactive GitDiagram View**: Renders dynamic, responsive Mermaid.js diagrams with cursor-anchored smooth pan and zoom, node details drawer, execution flows, raw Mermaid code inspection, and SVG export.
- **Card Flow View**: Alternate ReactFlow graph with folder hierarchies and file import dependency tracking.

### 2. 💬 Code Q&A Assistant (RAG Engine)
- **Dense Vector Search**: Powered by `sentence-transformers/all-MiniLM-L6-v2` and Qdrant vector database with multi-tenant filtering on `repository_id`.
- **Code Grounding**: Answers questions with verified file paths, exact line ranges (`Lines X–Y`), relevance percentages, and syntax-highlighted code evidence.

### 3. 🐛 Multi-Signal Bug → File Mapping
- Given a GitHub issue title and body, accurately identifies the source files responsible for the bug.
- **Multi-Signal Ranking Pipeline**:
  - **Dense Semantic Retrieval**: Vector embedding comparison between issue description and code chunks.
  - **Lexical Matching**: BM25 and symbol-level scoring for identifiers, stack traces, and error tokens.
  - **Dependency Graph Expansion**: Graph traversal of 1st and 2nd-degree imports from high-scoring candidate files.
  - **Git History & Recency**: Recency-weighted commit churn, change frequency, and historical bug-fix co-changes.
- **LLM Reasoning**: Generates debugging explanations, culprit line ranges, and confidence ratings (`HIGH`, `MEDIUM`, `LOW`).

### 4. 📝 Code-Grounded Auto README Generator
- Reads project manifest files (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.) alongside core source code.
- Produces production-grade `README.md` documents complete with Project Overview, Architecture Summary, Tech Stack with detected versions, Setup Guides, API Specifications, and Contributing Rules.
- Includes formatted Markdown preview, Raw Markdown tab, Copy to Clipboard, and One-Click File Download.

### 5. 📋 Bug Triage Board & Duplicate Clustering
- Fetches open issues directly from GitHub.
- **Semantic Clustering**: Groups related and duplicate bug reports using sentence embeddings and cosine similarity.
- **Automated Triage Scoring**: Classifies priority, severity, urgency, and area tags (Backend, Frontend, Auth, Database, etc.) with resolution advice.
- **Direct Localization Bridge**: One click on "Map Bug to File" sends any triaged issue directly into the Bug → File Mapping engine.

### 6. 🔥 Architectural Hotspot Detector
- Surfaces high-risk maintenance bottlenecks across the codebase.
- **Composite Risk Formula**: Evaluates code churn (git commit activity), lines of code complexity, import coupling (centrality), and issue frequency.
- Pinpoints `CRITICAL`, `HIGH`, `MEDIUM`, and `LOW` risk components with clear refactoring recommendations.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
  subgraph Client ["Client (React 19 + TypeScript + Vite)"]
    UI["Single-Page Dashboard\n(GitDiagram, RAG Q&A, Bug Localization, Hotspots, README)"]
    Mermaid["Mermaid.js + ReactFlow Canvas"]
  end

  subgraph Backend ["Backend Gateway (Node.js + Express)"]
    Routes["API Routers & Middleware\n(JWT Auth, Rate Limiter, Zod Validation)"]
    Controllers["Repository & Intelligence Controllers"]
    Prisma["Prisma ORM"]
  end

  subgraph AIService ["AI Intelligence Service (Python + FastAPI)"]
    ArchAgent["Architecture Agent"]
    BugRanker["Multi-Signal Bug Ranker"]
    TriageAgent["Triage & Clustering Service"]
    HotspotAgent["Hotspot Analysis Engine"]
    ReadmeAgent["Documentation Generator"]
    RAGEngine["Retrieval-Augmented Generation"]
  end

  subgraph Storage ["Databases & Search"]
    Postgres[("PostgreSQL 16\n(Users, Repos, Analyses, Issues)")]
    Qdrant[("Qdrant Vector Database\n(Code Chunk Embeddings)")]
  end

  subgraph External ["External Providers"]
    GitHub["GitHub REST API"]
    GroqGemini["Groq / Gemini LLMs"]
  end

  UI -->|HTTP / JSON / JWT| Routes
  Routes --> Controllers
  Controllers --> Prisma
  Prisma --> Postgres
  Controllers -->|Internal API Key| AIService
  Controllers --> GitHub
  AIService --> Qdrant
  AIService --> GroqGemini
```

---

## 💻 Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React 19, TypeScript, Vite, `@xyflow/react`, `mermaid`, `dompurify`, Custom Editorial Theme |
| **Backend** | Node.js, Express, TypeScript, Prisma ORM, Argon2id, JWT, Zod |
| **AI Service** | Python 3.11+, FastAPI, Pydantic v2, `sentence-transformers`, `scikit-learn` |
| **LLM Inference** | Groq (`qwen/qwen3.8-27b`) with automatic fallback to Google Gemini (`gemini-2.0-flash`) |
| **Databases** | PostgreSQL 16 (Relational & Auth), Qdrant (Vector Engine) |
| **Infrastructure** | Docker, Docker Compose |

---

## 📁 Repository Structure

```
Repowise/
├── client/                     # React 19 + Vite frontend
│   ├── src/
│   │   ├── components/         # Feature components (MermaidDiagram, BugTriage, Hotspots, README)
│   │   │   └── architecture/   # GitDiagram, drawers, custom nodes & edges
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # Client-side compilers & utilities
│   │   ├── App.tsx             # Main dashboard & tab routing
│   │   └── api.ts              # Type-safe API client
│   └── package.json
│
├── server/                     # Express + TypeScript backend gateway
│   ├── prisma/
│   │   ├── schema.prisma       # Database schema & relationships
│   │   └── migrations/         # PostgreSQL migration history
│   ├── src/
│   │   ├── controllers/        # Thin HTTP request handlers
│   │   ├── services/           # GitHub, AI-bridge, Repository, and Auth services
│   │   ├── routes/             # Express route definitions
│   │   ├── middleware/         # Security, JWT auth, validation, rate limiting
│   │   └── index.ts            # Server entrypoint (Port 3000)
│   └── package.json
│
├── ai-service/                 # FastAPI + Python AI intelligence engine
│   ├── app/
│   │   ├── api/routes/         # Endpoints (architecture, rag, bug_localization, triage, hotspots, readme)
│   │   ├── services/           # Multi-signal ranker, architecture agent, vector service, LLM service
│   │   ├── providers/          # Groq and Gemini API integrations
│   │   ├── utils/              # Chunking, AST parsing, and Mermaid compilation
│   │   └── main.py             # FastAPI entrypoint (Port 8000)
│   ├── requirements.txt
│   └── run.py
│
└── docker-compose.yml          # Container configuration for PostgreSQL & Qdrant
```

---

## 🛠️ Local Development Setup

### Prerequisites
- [Docker](https://www.docker.com/) & Docker Compose
- [Node.js](https://nodejs.org/) (v18 or higher) & `npm`
- [Python](https://www.python.org/) (v3.11 or higher) & `pip`

---

### Step 1: Start Database Containers
Start PostgreSQL and Qdrant in the background:
```bash
docker compose up -d
```
Check status:
```bash
docker compose ps
```
- PostgreSQL runs on `localhost:5432`
- Qdrant runs on `localhost:6333`

---

### Step 2: Configure Environment Variables

#### Backend Gateway (`server/.env`):
```env
PORT=3000
NODE_ENV=development
DATABASE_URL=postgresql://repowise:repowise_dev_password@localhost:5432/repowise?schema=public

JWT_ACCESS_SECRET=your_super_secret_jwt_access_key_min_32_chars
JWT_REFRESH_SECRET=your_super_secret_jwt_refresh_key_min_32_chars

AI_SERVICE_URL=http://localhost:8000
AI_SERVICE_API_KEY=your_shared_internal_secret_api_key_min_16_chars

GITHUB_API_URL=https://api.github.com
GITHUB_TOKEN=optional_github_personal_access_token_to_avoid_rate_limits
CLIENT_URL=http://localhost:5173
```

#### AI Intelligence Service (`ai-service/.env`):
```env
AI_SERVICE_PORT=8000
AI_SERVICE_API_KEY=your_shared_internal_secret_api_key_min_16_chars

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=repowise_code

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=qwen/qwen3.8-27b
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
```

---

### Step 3: Start Backend Server
```bash
cd server
npm install
npm run prisma:deploy
npm run dev
```
The Node.js server will run on **`http://localhost:3000`**.

---

### Step 4: Start AI Intelligence Service
In a separate terminal:
```bash
cd ai-service
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```
The FastAPI AI service will run on **`http://localhost:8000`**.

---

### Step 5: Start Client Application
In a third terminal:
```bash
cd client
npm install
npm run dev
```
Open **`http://localhost:5173`** in your browser to access the RepoWise dashboard!

---

## 📡 API Reference

All responses follow the standard envelope format: `{ success: true, data: ... }` or `{ success: false, error: ... }`.

### Authentication
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register a new user account |
| `POST` | `/api/auth/login` | Log in and receive access token + HttpOnly cookie |
| `POST` | `/api/auth/logout` | Revoke session and clear cookies |
| `GET` | `/api/auth/me` | Fetch authenticated user profile |

### Repository Management
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/repositories` | Connect a public GitHub repository |
| `GET` | `/api/repositories` | List connected repositories for the current user |
| `GET` | `/api/repositories/:id` | Fetch repository status and details |
| `DELETE` | `/api/repositories/:id` | Disconnect and remove repository data |

### Intelligence & AI Features
| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/repositories/:id/architecture` | Generate hierarchical system architecture & GitDiagram |
| `POST` | `/api/repositories/:id/index` | Chunk and embed repository source files into Qdrant |
| `POST` | `/api/repositories/:id/query` | Ask questions to the indexed codebase (RAG) |
| `POST` | `/api/repositories/:id/bugs/locate` | Run multi-signal bug-to-file localization |
| `GET` | `/api/repositories/:id/bugs/history` | Retrieve past bug localization analyses |
| `GET` | `/api/repositories/:id/issues/open` | Fetch live open issues from GitHub |
| `POST` | `/api/repositories/:id/triage` | Analyze open issues for priority & duplicate clusters |
| `GET` | `/api/repositories/:id/triage` | Retrieve latest bug triage report |
| `GET` | `/api/repositories/:id/hotspots` | Compute architectural risk and code hotspots |
| `POST` | `/api/repositories/:id/readme` | Generate code-grounded repository README |
| `GET` | `/api/repositories/:id/readme` | Fetch cached or generated README |

---

## 🔒 Security & Privacy

- **Data Isolation**: Multi-tenant Qdrant payloads indexed strictly by `repository_id` with payload filtering to prevent cross-repository vector leakage.
- **Secure Authentication**: Short-lived JSON Web Tokens (15 min) paired with argon2id-hashed refresh tokens stored in secure, HttpOnly, SameSite cookies.
- **Service Perimeter**: The AI Service is completely isolated behind an internal bearer token validation layer; clients only communicate through the Express API gateway.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
