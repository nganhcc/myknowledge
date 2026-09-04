# Progress

## Completed

- [x] FastAPI async project foundation and configuration (pydantic-settings, structlog)
- [x] Database models and migrations: users, workspaces, documents, and workspace members
- [x] Authentication API: register, login, and current-user endpoints (JWT + bcrypt)
- [x] Test infrastructure: isolated test database, automatic migrations, and cleanup between tests
- [x] CI pipeline: Ruff, mypy, pytest, and Docker build
- [x] Review fixes: registration race condition, EmailStr validation, Docker health checks,
         JWT claims, and duplicate logging handlers
- [x] Workspaces API: CRUD operations and membership management (OWNER/ADMIN/MEMBER)
- [x] Documents API: file uploads, content-hash deduplication, and storage adapter
- [x] Document processing pipeline: PENDING -> PROCESSING -> READY/FAILED
- [x] Document chunking, embeddings with pgvector, and Redis queue
- [x] Retrieval, context assembly, citations, and streaming chat
- [x] Hybrid retrieval: PostgreSQL full-text search + pgvector with reciprocal rank fusion
- [x] Local reranking adapter with RRF fallback
- [x] Conversational query rewriting using bounded conversation history

## Next

### RAG Evaluation

- [x] Create a small dataset of 20-30 questions with `question`, `ground_truth`,
  and `expected_sources`
- [x] Measure retrieval recall
- [x] Add deterministic claim-level citation accuracy metrics
- [ ] Run end-to-end evaluation against the benchmark workspace
- [ ] Measure answer correctness with a simple LLM judge or manual review
- [ ] Measure context relevance
- [x] Add a lightweight end-to-end evaluation script; RAGAS remains optional
- [ ] Compare results before and after hybrid retrieval and reranking
- [ ] Add the quantitative results to the README as evidence of improvement

### Redis Retrieval Caching

Cache retrieval results, not complete LLM responses:

`query -> normalize -> hash -> Redis -> cache hit? -> result or retrieval`

- [x] Normalize retrieval queries consistently
- [x] Hash the normalized query with workspace and retrieval settings included
- [x] Cache and deserialize retrieved chunk results with a TTL
- [x] Invalidate or version cache entries when the workspace documents change
- [x] Add cache-hit and cache-miss metrics/logging

### Simple Rate Limiting

Use a Redis fixed-window counter:

- [x] Limit chat requests to 20 requests per minute per user
- [x] Limit uploads to 10 requests per minute per user
- [x] Return a clear rate-limit response with retry information
- [x] Add tests for window boundaries, separate users, and separate endpoints
