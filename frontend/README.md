# Prabhupada GPT Frontend (Next.js)

Production-ready web UI for `PrabhupadaGPT` powered by the backend API.

## Stack

- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS

## Environment

Copy:

```bash
cp .env.example .env.local
```

Key vars:

- `BACKEND_URL` (server-side proxy target, default `http://127.0.0.1:8000`)
- `NEXT_PUBLIC_API_URL` (optional direct client URL; leave unset to use proxy)
- `NEXT_PUBLIC_API_TIMEOUT_MS` (optional timeout)

## Run locally

```bash
npm install
npm run dev
```

App runs at:

- Frontend: `http://localhost:3000`
- Backend (expected): `http://localhost:8000`

## API Wiring

Frontend uses same-origin proxy routes by default:

- `POST /api/ask` -> `${BACKEND_URL}/api/ask`
- `GET /api/health` -> `${BACKEND_URL}/health`

This avoids browser CORS issues and keeps backend URL private on server-side.

## Deploy on Vercel

1. Import `frontend/` as a Vercel project.
2. Add environment variables in Vercel Project Settings:
   - `BACKEND_URL=https://your-backend-domain.com`
   - `NEXT_PUBLIC_API_TIMEOUT_MS=60000`
3. Deploy.

The frontend continues calling same-origin Next routes (`/api/ask`, `/api/health`),
and those routes proxy to your backend using `BACKEND_URL`.

### Backend CORS note

If you use proxy routes (default), browser calls are same-origin and frontend CORS
is usually not required. Keep backend CORS configured for your own direct API tests
or non-proxy clients.
