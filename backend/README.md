# AI-Powered Knowledge Base

AI-powered document intelligence and RAG platform.

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- pgvector
- Redis
- OpenAI

## Development

From the repository root:

```bash
docker compose up -d
```

To run the API directly:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

## Health Check

GET /health
