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

## Retrieval

Chat retrieval combines PostgreSQL full-text search (`simple` configuration) with
pgvector cosine search. The two ranked lists are merged with reciprocal rank
fusion, then the merged candidates are reranked to the final context size.

The default flow is 50 vector candidates plus 50 full-text candidates, merged
to 50, then reranked to 5 with `BAAI/bge-reranker-base`. The reranker loads
lazily and failures fall back to the fused ranking so chat remains available.
The first local inference downloads the model into the Hugging Face cache and
requires the `sentence-transformers` runtime, which includes PyTorch.

Apply the full-text search migration before starting the application:

```bash
uv run alembic upgrade head
```

The retrieval and reranker defaults can be overridden with `RETRIEVAL_*`,
`QUERY_REWRITE_HISTORY_LIMIT`, `RERANKER_ENABLED`, and `RERANKER_MODEL`
environment variables. Follow-up questions are rewritten with bounded prior
conversation context before embedding; the original question is retained in
conversation history and citations.
