# Progress

## Đã xong

- [x] Khung dự án FastAPI async + cấu hình (pydantic-settings, structlog)
- [x] Models & migration: users, workspaces, documents, workspace_members
- [x] Auth API: register / login / me (JWT + bcrypt)
- [x] Test infra: conftest tự tạo test DB + migrate + truncate giữa các test
- [x] CI: ruff → mypy → pytest → docker build
- [x] Fix review: race condition register, EmailStr, healthchecks compose,
      JWT claims (iat/type), logging chống nhân bản handler

## Đang làm / Kế tiếp

- [x] Workspaces API: CRUD + membership (role OWNER/ADMIN/MEMBER)
- [ ] Documents API: upload file, dedup theo content_hash, storage adapter
- [ ] Pipeline xử lý tài liệu (status PENDING → PROCESSING → READY/FAILED)
- [ ] Chunking + embedding (pgvector) + Redis queue
- [ ] Query API: retrieval + LLM streaming response kèm citations

