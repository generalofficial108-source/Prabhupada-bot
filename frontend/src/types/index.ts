// =============================================================================
// src/types/index.ts
//
// Frontend tabs: "ask" | "reference" | "quiz"
//   - "ask"       → backend auto-detects ask / explain / summarise from query
//   - "reference" → direct verse lookup by citation
//   - "quiz"      → MCQ generation with chapter/book parsing
//
// Backend accepts all 5 task types; "ask" is the smart catch-all.
// =============================================================================

// What the frontend exposes to the user — 3 tabs
export type TaskType = "ask" | "reference" | "quiz"

// What the backend may return (includes auto-detected sub-tasks)
export type BackendTaskType = "ask" | "reference" | "explain" | "quiz" | "summarise"

export interface SourceVerse {
  reference:      string
  book:           string
  book_code:      string
  verse_sanskrit: string
  word_for_word:  string
  translation:    string
  purport:        string
  part:           number
  total_parts:    number
  vector_score:   number
  rerank_score:   number
  direct_lookup:  boolean
}

export interface AskRequest {
  task:            BackendTaskType
  query:           string
  book_filter:     string[]
  top_n:           number
  scope?:          string | null
  history?:        ConversationMessage[]
  use_expansion?:  boolean
}

export interface AskResponse {
  task:         BackendTaskType
  query:        string
  answer:       string
  sources:      SourceVerse[]
  context_used: string[]
  is_direct:    boolean
  llm_model:    string
  mode:         string
  quiz_data:    QuizQuestion[] | null
}

export interface QuizQuestion {
  question:    string
  options:     string[]   // exactly 4 options e.g. ["A. ...", "B. ...", ...]
  answer:      string     // the correct option text (must match one of options[])
  reference:   string     // source verse e.g. "BG 2.47"
  explanation: string     // one sentence why it is correct
}

export interface ConversationMessage {
  role:    "user" | "assistant"
  content: string
}

export interface HealthResponse {
  status:         string
  db_count:       number
  llm_provider:   string
  llm_model:      string
  embed_provider: string
}

// UI-only types
export interface ChatEntry {
  id:        string
  task:      TaskType       // what the user selected (3 tabs)
  query:     string
  response:  AskResponse    // backend may return a sub-task in response.task
  timestamp: Date
  animate?:  boolean        // client-side token streaming effect for new answers
}

export interface TaskConfig {
  id:          TaskType
  label:       string
  icon:        string
  description: string
  placeholder: string
  hint:        string
}

// =============================================================================
// 3 TABS
// =============================================================================

export const TASK_CONFIGS: TaskConfig[] = [
  {
    id:          "ask",
    label:       "Ask",
    icon:        "💬",
    description: "Ask anything — AI detects if it needs a direct answer, explanation, or summary",
    placeholder: "What is the purpose of human life? / Explain karma yoga / Summarise teachings on bhakti",
    hint:        "Smart mode — handles questions, explanations and summaries automatically",
  },
  {
    id:          "reference",
    label:       "Verse Lookup",
    icon:        "📖",
    description: "Fetch an exact verse with Sanskrit, word-for-word, translation and purport",
    placeholder: "BG 2.47  ·  NOI 1  ·  ISO Invocation  ·  BS 5.1  ·  BG 18.66",
    hint:        "Enter a verse citation exactly — e.g. BG 2.47, NOI 3, ISO 1, BS 5.1",
  },
  {
    id:          "quiz",
    label:       "Quiz",
    icon:        "📝",
    description: "Generate interactive MCQs from any book or chapter",
    placeholder: "5 MCQs from NOI  ·  Quiz on BG Chapter 2  ·  10 questions from Isopanishad",
    hint:        "Specify count + book or chapter — e.g. \"10 questions from BG Chapter 3\"",
  },
]

export const BOOK_OPTIONS = [
  { code: "bg",  name: "Bhagavad Gita As It Is", short: "BG"  },
  { code: "iso", name: "Sri Isopanishad",         short: "ISO" },
  { code: "noi", name: "Nectar of Instruction",   short: "NOI" },
  { code: "bs",  name: "Brahma Samhita",          short: "BS"  },
]

export const SAMPLE_QUESTIONS: Record<TaskType, string[]> = {
  ask: [
    "What is the purpose of human life?",
    "Explain the concept of maya",
    "How to control the mind according to Krishna?",
    "Summarise teachings on devotional service",
    "What happens after death?",
    "Explain karma yoga in simple terms",
  ],
  reference: [
    "BG 2.47",
    "NOI 1",
    "ISO Invocation",
    "BS 5.1",
    "BG 18.66",
    "NOI 5",
  ],
  quiz: [
    "Make 5 MCQs from Nectar of Instruction",
    "Quiz on BG Chapter 2",
    "10 questions from Isopanishad",
    "5 MCQs from Brahma Samhita",
    "Quiz on BG Chapter 12",
  ],
}

// Mode label → icon mapping (for what backend returns in response.mode)
export const MODE_ICONS: Record<string, string> = {
  "Semantic Q&A":        "💬",
  "Direct Verse Lookup": "📖",
  "Explanation":         "🪔",
  "Quiz":                "📝",
  "Summary":             "📋",
}