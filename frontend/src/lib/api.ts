import type { AskRequest, AskResponse, HealthResponse, BackendTaskType, ConversationMessage } from "@/types"

// Prefer same-origin Next.js proxy routes in production:
//   /api/ask    -> backend /api/ask
//   /api/health -> backend /health
// You can still override with NEXT_PUBLIC_API_URL for direct calls.
const API_URL = process.env.NEXT_PUBLIC_API_URL || ""
const REQUEST_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_API_TIMEOUT_MS || 60000)

// ---------------------------------------------------------------------------
// Core fetch helper — handles errors consistently
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS)

  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
    signal: controller.signal,
  }).finally(() => clearTimeout(timeoutId))

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(error.detail || `API error ${res.status}`)
  }

  return res.json()
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

export async function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health")
}

// ---------------------------------------------------------------------------
// Main RAG call
// task accepts BackendTaskType — the full 5-value union the backend understands.
// The frontend only ever sends "ask" | "reference" | "quiz" from the 3 tabs,
// but "ask" is auto-detected into "explain" | "summarise" by the backend.
// ---------------------------------------------------------------------------

export async function ask(params: {
  task:          BackendTaskType
  query:         string
  bookFilter?:   string[]
  topN?:         number
  scope?:        string | null
  history?:      ConversationMessage[]
  useExpansion?: boolean
}): Promise<AskResponse> {
  const body: AskRequest = {
    task:          params.task,
    query:         params.query,
    book_filter:   params.bookFilter ?? [],
    top_n:         params.topN ?? 5,
    scope:         params.scope ?? null,
    history:       params.history ?? [],
    use_expansion: params.useExpansion ?? true,
  }
  return apiFetch<AskResponse>("/api/ask", {
    method: "POST",
    body:   JSON.stringify(body),
  })
}