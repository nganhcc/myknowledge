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

- [ ] Evaluate recall@50 before reranking versus precision@5 after reranking
- [ ] Benchmark local reranker latency, memory usage, and cold-start behavior
- [ ] Add broader database-backed tests for full-text search and reranking
