# Frontend Agent Instructions

## Scope

This directory contains the frontend application.

For frontend tasks, treat these files as the primary source of truth:

- `/frontend/openapi.json` — machine-readable API contract
- Files inside `/frontend`

## Backend access policy

Do not inspect backend source code by default.

Do not read files under `/backend` unless at least one of these conditions is true:

1. The required API behavior is missing or ambiguous in `openapi.json`.
2. The user explicitly asks to inspect the backend implementation.
3. A frontend integration bug cannot be diagnosed from frontend code and the API contract alone.

Before reading backend code, briefly explain which behavior is unclear and why backend inspection is necessary.

If backend behavior differs from `openapi.json`, report the discrepancy instead of silently guessing.

## API integration

- Use `/frontend/openapi.json` for request and response schemas.
- Do not invent endpoints, fields, enum values, or error formats.
- Centralize the API base URL in frontend configuration.
- Centralize authentication and Bearer token handling in one API client.
- Keep API calls out of UI components where practical.
- Handle `401`, `403`, `404`, `422`, and SSE `error` events explicitly.
- Chat uses `POST /api/v1/chat` with Server-Sent Events. Do not use native
  `EventSource`; use `fetch()` because the endpoint requires POST and an
  Authorization header.

## Development rules

- Read existing frontend files before creating new abstractions.
- Prefer small, focused changes.
- Do not modify backend files for frontend-only tasks.
- Do not add frontend dependencies without checking existing dependencies first.
- Run frontend lint, type-check, and tests after changes.
