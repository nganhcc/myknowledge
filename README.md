# AI Knowledge Base

AI-powered document intelligence and retrieval-augmented generation (RAG)
platform. The application lets users create workspaces, upload documents, ask
questions, and receive streamed answers with source citations.

## Stack

- Backend: Python 3.13, FastAPI, Uvicorn, SQLAlchemy, and Alembic
- Frontend: React 18, TypeScript, and Vite
- Data services: PostgreSQL 16 with pgvector and Redis 7
- AI: Gemini for embeddings and answer generation
- Reranking: local `sentence-transformers` cross-encoder

## Prerequisites

- Docker Desktop with Compose
- [uv](https://docs.astral.sh/uv/) for local backend development
- Node.js 20.19+ or 22.12+
- A Gemini API key for document embeddings and chat generation

## Configuration

Create a `.env` file in the repository root:

```dotenv
SECRET_KEY=replace-with-a-random-value-at-least-32-characters-long
GEMINI_API_KEY=your-gemini-api-key
```

`SECRET_KEY` is required. `GEMINI_API_KEY` is required for uploads that create
embeddings and for chat. Never commit `.env` or API keys.

The Docker Compose file supplies the container connection URLs. For local
backend execution, the defaults target PostgreSQL and Redis on `localhost`.
Override them in `.env` when needed:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | local PostgreSQL URL | Async database connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Queue and retrieval-cache connection |
| `CORS_ORIGINS` | empty | Comma-separated frontend origins allowed by the API |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-2` | Embedding model |
| `GEMINI_GENERATION_MODEL` | `gemini-3.6-flash` | Chat and evaluation-judge model |
| `RETRIEVAL_CANDIDATE_LIMIT` | `50` | Candidates retained before reranking |
| `RETRIEVAL_FINAL_LIMIT` | `5` | Chunks sent to the generation model |
| `RERANKER_ENABLED` | `true` | Enable local cross-encoder reranking |
| `RERANKER_MODEL` | `BAAI/bge-reranker-base` | Hugging Face reranker model |
| `RETRIEVAL_CACHE_ENABLED` | `true` | Cache retrieved chunks in Redis |
| `RETRIEVAL_CACHE_TTL_SECONDS` | `300` | Retrieval-cache lifetime |
| `CHAT_RATE_LIMIT` | `20` | Chat requests per user per minute |
| `UPLOAD_RATE_LIMIT` | `10` | Upload requests per user per minute |

All backend settings are defined in `backend/app/core/config.py`.

## Run With Docker

From the repository root, start the API, document worker, PostgreSQL, and Redis:

```bash
docker compose up -d --build
```

The API container applies all Alembic migrations before starting. The worker
processes document jobs from Redis and shares the storage volume with the API.

Check the API and open its documentation:

```bash
curl http://localhost:8000/health
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

Stop the services with:

```bash
docker compose down
```

Add `-v` only when you intentionally want to remove PostgreSQL and file-storage
volumes.

## Run Locally

Start PostgreSQL and Redis first, either with Docker or existing local services.
Then install backend dependencies and apply migrations:

```bash
cd backend
uv sync
uv run alembic upgrade head
```

Run the API in one terminal:

```bash
uv run uvicorn app.main:app --reload
```

Run the document worker in a second terminal:

```bash
cd backend
uv run python -m app.worker
```

Install and run the frontend in a third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api/*` and `/health` to the backend
at `http://localhost:8000`. Set `VITE_API_BASE_URL` in `frontend/.env` when the
API runs on another origin. For a deployed frontend, set it to the full Render
API URL and rebuild the frontend.

## API Surface

The API is versioned under `/api/v1`:

| Area | Capabilities |
| --- | --- |
| Authentication | Register, login, and current-user profile |
| Workspaces | Create, list, update, delete, and manage members |
| Documents | Upload, list, inspect processing status, and delete |
| Chat | Stream answers and list conversations and messages |

Use the Swagger UI for request schemas and authenticated endpoint details. Chat
uses a fetch-based Server-Sent Events stream.

## Retrieval Pipeline

For each question, the backend:

1. Optionally rewrites follow-up questions using bounded conversation history.
2. Runs pgvector cosine search and PostgreSQL full-text search.
3. Merges ranked lists with reciprocal rank fusion.
4. Reranks fused candidates with `BAAI/bge-reranker-base`.
5. Builds bounded context and streams a Gemini answer with citations.

The default flow retains 50 candidates, returns 5 final chunks, and falls back
to fused ranking if the local reranker is unavailable. The reranker loads lazily;
its first use may download the model into the Hugging Face cache and use
additional memory. Set `RERANKER_ENABLED=false` to disable it.

Retrieval results are cached in Redis. Cache keys include the workspace,
retrieval settings, and workspace retrieval version, so document changes make
older results unreachable.

## Tests and Quality Checks

Start PostgreSQL before running the backend tests. Tests apply migrations and
use the configured test database:

```bash
cd backend
uv run ruff check .
uv run mypy app
uv run pytest
```

Frontend checks:

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

## Retrieval Evaluation

The benchmark runner compares vector-only, hybrid/RRF, and reranked retrieval.
It does not modify conversations, documents, or usage logs. Configure
`SECRET_KEY` and `GEMINI_API_KEY`, then run it from `backend/`:

```bash
cd backend
uv run python -m app.evaluation.runner \
  --dataset evals/benchmark.jsonl \
  --workspace-id 00000000-0000-0000-0000-000000000000 \
  --output evals/report.json
```

Use `--e2e` to include answer generation, citation metrics, and Gemini judge
scores. See [backend/evals/benchmark.example.jsonl](backend/evals/benchmark.example.jsonl)
for the dataset shape. End-to-end evaluation has higher API cost because each
case and retrieval mode uses generation and judge requests.

## Project Layout

```text
backend/
  app/          FastAPI routes, models, schemas, and services
  alembic/      Database migrations
  evals/        Versioned benchmark datasets
  tests/        Backend tests
frontend/
  src/          React application, API clients, pages, and components
  public/       Static frontend assets
docker-compose.yml
```

The frontend API contract is [frontend/openapi.json](frontend/openapi.json).

huhu