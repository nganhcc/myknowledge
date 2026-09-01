# Frontend

React 18 + TypeScript SPA built with Vite for the AI Knowledge Base platform.

## Prerequisites

- Node.js 20.19+ / 22.12+.
- Backend API running on `http://localhost:8000` (see root `docker-compose.yml`).

## Setup

```bash
npm install
```

## Development

```bash
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api/*` and `/health`
to the FastAPI backend on `:8000` (see `vite.config.ts`) — the backend exposes no
CORS middleware, so all API traffic must stay same-origin in development.

Set `VITE_API_BASE_URL` in a `.env` file if the API lives on another origin.

## Scripts

| Script             | Purpose                                        |
| ------------------ | ---------------------------------------------- |
| `npm run dev`      | Start the Vite dev server (port 5173)          |
| `npm run build`    | Type-check and produce a production build      |
| `npm run typecheck`| TypeScript type-check only                     |
| `npm run lint`     | ESLint                                         |
| `npm run preview`  | Serve the production build locally             |

## API contract

The primary API contract is `frontend/openapi.json`. All request/response types
under `src/types/api.ts` are hand-mapped from that file; update them by hand if
the contract changes.

## Directory layout

```
src/
  api/
    client.ts      # centralized fetch wrapper: base URL, Bearer token, error mapping
    token.ts       # access-token persistence (localStorage)
    sse.ts         # fetch-based SSE reader for POST /api/v1/chat
    auth.ts        # register / login / me / logout
    workspaces.ts  # workspace + membership endpoints
    documents.ts   # upload / list / status / delete
    chat.ts        # conversations + messages
  types/
    api.ts         # TS types mirroring frontend/openapi.json
```
