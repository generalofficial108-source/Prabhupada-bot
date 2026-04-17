"use client"

import { useState, useRef, useEffect, useCallback } from "react"
import {
  Trash2, Settings, PanelLeftClose, PanelLeftOpen,
  MessageSquare, Clock, Sparkles, X, Plus,
} from "lucide-react"
import { BookFilter } from "@/components/BookFilter"
import { InputBar } from "@/components/InputBar"
import { AnswerCard } from "@/components/AnswerCard"
import { Spinner } from "@/components/ui/Spinner"
import { ask } from "@/lib/api"
import {
  TASK_CONFIGS, BOOK_OPTIONS, SAMPLE_QUESTIONS,
  type TaskType, type ChatEntry, type BackendTaskType,
} from "@/types"

interface ChatSession {
  id:        string
  title:     string
  task:      TaskType
  entries:   ChatEntry[]
  createdAt: Date
  updatedAt: Date
}

const TASK_ICON: Record<TaskType, string> = {
  ask: "💬", 
  reference: "📖", 
  quiz: "📝",
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------
function Sidebar({ open, sessions, activeSessionId, onSelectSession, onNewSession, onDeleteSession, onClose }: {
  open: boolean; sessions: ChatSession[]; activeSessionId: string | null
  onSelectSession: (id: string) => void; onNewSession: () => void
  onDeleteSession: (id: string) => void; onClose: () => void
}) {
  const fmt = (d: Date) => {
    const diff = Date.now() - new Date(d).getTime()
    if (diff < 60_000) return "Just now"
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
    return new Date(d).toLocaleDateString()
  }
  return (
    <>
      {open && <div className="fixed inset-0 z-20 bg-black/30 backdrop-blur-sm lg:hidden" onClick={onClose} />}
      <aside className={`fixed top-0 left-0 z-30 h-full flex flex-col bg-gradient-to-b from-[#2a1308] via-[#35180b] to-[#2b1408] border-r border-[#4c2815] transition-transform duration-300 ease-in-out shadow-2xl lg:shadow-none lg:static lg:z-auto lg:h-auto ${open ? "translate-x-0 w-52 lg:flex" : "-translate-x-full w-52 lg:hidden"}`}>
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-[#4c2815]">
          <span className="text-xl">🪷</span>
          <span className="font-bold text-amber-50 text-sm tracking-wide">Prabhupada GPT</span>
        </div>
        <div className="px-3 pt-3 pb-2">
          <button onClick={onNewSession} className="w-full flex items-center justify-center gap-2 rounded-lg border border-[#6e3a19] bg-[#6a390f] px-4 py-2.5 text-sm font-medium text-amber-50 hover:bg-[#7a4313] hover:border-[#9a5a2b] transition-all active:scale-[0.98] shadow-sm">
            <Plus size={14} /> New Conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {sessions.length === 0 ? (
            <div className="flex flex-col items-center py-10 text-[#c8a88d]">
              <MessageSquare size={22} className="mb-2 opacity-40" />
              <p className="text-xs">No conversations yet</p>
            </div>
          ) : (
            <>
              <p className="text-[10px] font-semibold uppercase tracking-widest text-[#c8a88d] px-2 py-2">History</p>
              {sessions.slice().reverse().map(s => (
                <div key={s.id} onClick={() => onSelectSession(s.id)} className={`group relative flex items-start gap-2.5 rounded-lg px-3 py-2.5 cursor-pointer mb-0.5 transition-all duration-150 ${activeSessionId === s.id ? "bg-[#5a2f14] text-amber-50 ring-1 ring-[#8f5227]" : "text-[#f1ddcc] hover:bg-[#4b2611]"}`}>
                  <span className="text-sm mt-0.5 flex-shrink-0">{TASK_ICON[s.task]}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate leading-snug">{s.title}</p>
                    <p className="text-[10px] text-[#d1b39b] mt-0.5 flex items-center gap-1">
                      <Clock size={9} />{fmt(s.updatedAt)}
                      {s.entries.length > 0 && <span className="ml-1 opacity-60">· {s.entries.length} msg</span>}
                    </p>
                  </div>
                  <button onClick={e => { e.stopPropagation(); onDeleteSession(s.id) }} className="opacity-0 group-hover:opacity-100 text-[#d1b39b] hover:text-red-300 p-0.5 rounded transition-all flex-shrink-0 mt-0.5" title="Delete"><X size={12} /></button>
                </div>
              ))}
            </>
          )}
        </div>
        <div className="flex-shrink-0 px-3 py-3 border-t border-[#4c2815]">
          <div className="rounded-lg bg-[#2a1308]/40 border border-[#5b3118] p-3">
            <div className="flex items-center gap-2 mb-1.5"><span className="text-base">🏛️</span><p className="font-semibold text-amber-100 text-xs">ISKCON Pune NVCC</p></div>
            <p className="text-[10px] text-[#e2c6b0]/80 leading-relaxed mb-2">Personal guidance, classes &amp; spiritual programs.</p>
            <div className="space-y-1.5">
              <a href="tel:+91-XXXXXXXXXX" className="flex items-center gap-1.5 text-[10px] text-amber-100 hover:text-white transition-colors"><span>📞</span><span>+91-XXXXXXXXXX</span></a>
              <a href="mailto:nvcc@iskconpune.org" className="flex items-center gap-1.5 text-[10px] text-amber-100 hover:text-white transition-colors"><span>📧</span><span>nvcc@iskconpune.org</span></a>
              <a href="https://iskconpune.com" target="_blank" rel="noopener noreferrer" className="flex items-center gap-1.5 text-[10px] text-amber-100 hover:text-white transition-colors"><span>🌐</span><span>iskconpune.com</span></a>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------
export default function HomePage() {
  const [task, setTask]                 = useState<TaskType>("ask")
  const [query, setQuery]               = useState("")
  const [bookFilter, setBookFilter]     = useState<string[]>(BOOK_OPTIONS.map(b => b.code))
  const [topN, setTopN]                 = useState(5)
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState<string | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showScores, setShowScores]     = useState(false)
  const [sidebarOpen, setSidebarOpen]   = useState(true)
  const [sessions, setSessions]         = useState<ChatSession[]>([])
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  const activeSession = sessions.find(s => s.id === activeSessionId) ?? null
  const history       = activeSession?.entries ?? []

  useEffect(() => {
    if (history.length > 0) bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [history.length])

  // Better mobile UX: sidebar closed by default on small screens.
  useEffect(() => {
    if (typeof window !== "undefined" && window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }, [])

  const handleNewSession = useCallback(() => {
    const id = crypto.randomUUID()
    setSessions(prev => [...prev, { id, title: "New conversation", task, entries: [], createdAt: new Date(), updatedAt: new Date() }])
    setActiveSessionId(id); setQuery(""); setError(null)
  }, [task])

  const handleDeleteSession = useCallback((id: string) => {
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id)
      if (activeSessionId === id) setActiveSessionId(next.length > 0 ? next[next.length - 1].id : null)
      return next
    })
  }, [activeSessionId])

  const handleSubmit = useCallback(async () => {
    const q = query.trim()
    if (!q || loading) return
    setLoading(true); setError(null); setQuery("")

    let sid = activeSessionId
    if (!sid) {
      sid = crypto.randomUUID()
      setSessions(prev => [...prev, { id: sid!, title: q.length > 45 ? q.slice(0, 42) + "…" : q, task, entries: [], createdAt: new Date(), updatedAt: new Date() }])
      setActiveSessionId(sid)
    }

    const scope = task === "quiz" ? (bookFilter.length === 1 ? bookFilter[0] : null) : null
    const currentEntries = sessions.find(s => s.id === sid)?.entries ?? []
    const conversationHistory = currentEntries.flatMap(e => [
      { role: "user" as const, content: e.query },
      { role: "assistant" as const, content: e.response.answer },
    ])

    try {
      const response = await ask({
        task:       task as BackendTaskType,
        query:      q,
        bookFilter: bookFilter.length === BOOK_OPTIONS.length ? [] : bookFilter,
        topN, scope, history: conversationHistory,
      })
      const entryId = crypto.randomUUID()
      const entry: ChatEntry = {
        id: entryId,
        task,
        query: q,
        response,
        timestamp: new Date(),
        animate: response.task !== "quiz",
      }
      setSessions(prev => prev.map(s => s.id !== sid ? s : {
        ...s,
        title:     s.entries.length === 0 ? (q.length > 45 ? q.slice(0, 42) + "…" : q) : s.title,
        task, entries: [...s.entries, entry], updatedAt: new Date(),
      }))
      // Turn off animation after initial render cycle.
      window.setTimeout(() => {
        setSessions(prev => prev.map(s => s.id !== sid ? s : {
          ...s,
          entries: s.entries.map(e => e.id === entryId ? { ...e, animate: false } : e),
        }))
      }, 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong. Please try again.")
    } finally {
      setLoading(false)
    }
  }, [query, task, bookFilter, topN, loading, activeSessionId, sessions])

  const taskConfig = TASK_CONFIGS.find(t => t.id === task)!

  return (
    <div className="flex h-screen overflow-hidden bg-[#efeeec]">
      <Sidebar open={sidebarOpen} sessions={sessions} activeSessionId={activeSessionId}
        onSelectSession={id => { setActiveSessionId(id); setError(null) }}
        onNewSession={handleNewSession} onDeleteSession={handleDeleteSession}
        onClose={() => setSidebarOpen(false)} />

      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {/* Header */}
        <header className="flex-shrink-0 border-b border-[#d8cdbb] bg-[#F0E9DE] px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <button onClick={() => setSidebarOpen(o => !o)} title={sidebarOpen ? "Close sidebar" : "Open sidebar"} className="flex-shrink-0 rounded-lg p-2 text-[#8B6340] hover:bg-[#f5ede0] hover:text-[#7B3F00] transition-colors">
                {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
              </button>
              {!sidebarOpen && <span className="text-lg flex-shrink-0">🪷</span>}
              <div className="min-w-0">
                <h1 className="font-bold text-slate-800 text-base leading-tight truncate">
                  {activeSession && activeSession.entries.length > 0 ? activeSession.title : "Prabhupada GPT"}
                </h1>
                {(!activeSession || activeSession.entries.length === 0) && (
                  <p className="text-xs text-slate-500 hidden sm:block truncate">Teachings of A.C. Bhaktivedanta Swami Prabhupada</p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              {activeSessionId && history.length > 0 && (
                <button onClick={() => handleDeleteSession(activeSessionId)} title="Delete conversation" className="rounded-lg p-2 text-[#8B6340] hover:bg-red-50 hover:text-red-500 transition-colors"><Trash2 size={16} /></button>
              )}
              <button onClick={() => setShowSettings(s => !s)} title="Settings" className={`rounded-lg p-2 transition-colors ${showSettings ? "bg-[#f5ede0] text-[#7B3F00]" : "text-[#8B6340] hover:bg-[#f5ede0] hover:text-[#7B3F00]"}`}><Settings size={16} /></button>
            </div>
          </div>
        </header>

        {/* Settings */}
        {showSettings && (
          <div className="flex-shrink-0 border-b border-[#ddc9a8] bg-[#f5ede0]/80 px-4 py-3 animate-fade-in">
            <div className="max-w-3xl mx-auto flex flex-wrap items-center gap-6">
              <p className="text-xs font-semibold text-[#7B3F00] uppercase tracking-wider">Settings</p>
              <label className="flex items-center gap-2 text-sm text-[#7B3F00] cursor-pointer">
                <input type="checkbox" checked={showScores} onChange={e => setShowScores(e.target.checked)} className="rounded border-[#ddc9a8] accent-amber-600" />
                Show relevance scores
              </label>
            </div>
          </div>
        )}

        {/* Chat area */}
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-4xl px-4">
            {history.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center min-h-[62vh] text-center animate-fade-in">
                <div className="w-full rounded-2xl border border-[#e6dfd2] bg-[#f8f8f6] shadow-md p-8 mb-8">
                  <nav className="mb-8 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-slate-800 font-semibold">
                      <span className="text-xl">🪷</span>
                      <span>Prabhupada GPT</span>
                    </div>
                    <div className="text-xs text-slate-500">Grounded in Srila Prabhupada&apos;s books</div>
                  </nav>

                  <h2 className="text-3xl sm:text-4xl font-bold text-slate-800 mb-3">
                    Scripture-grounded AI for
                    <span className="text-amber-700"> thoughtful spiritual study</span>
                  </h2>
                  <p className="text-sm sm:text-base text-slate-600 mb-6 max-w-2xl mx-auto leading-relaxed">
                    Ask, explore references, and generate quizzes from Srila Prabhupada&apos;s books with citations and transparent source context.
                  </p>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
                    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                      <p className="text-xs uppercase tracking-wide text-slate-500 mb-1">Grounded Answers</p>
                      <p className="text-sm text-slate-700">Every response is linked to retrieved scripture context.</p>
                    </div>
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                      <p className="text-xs uppercase tracking-wide text-amber-700 mb-1">Verse Lookup</p>
                      <p className="text-sm text-slate-700">Direct references like BG 2.47 with Sanskrit and translation.</p>
                    </div>
                    <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                      <p className="text-xs uppercase tracking-wide text-emerald-700 mb-1">Quiz Mode</p>
                      <p className="text-sm text-slate-700">Generate chapter/book-based MCQs for revision and classes.</p>
                    </div>
                  </div>
                </div>

                <p className="text-sm text-slate-600 mb-8 max-w-sm leading-relaxed">
                  {task === "ask" && "Ask any question — I'll automatically answer, explain or summarise based on what you need."}
                  {task === "reference" && "Enter any verse citation to get the full Sanskrit, word-for-word, translation and purport."}
                  {task === "quiz" && "Generate an interactive MCQ quiz from any book or chapter of Srila Prabhupada's books."}
                </p>
                <div className="w-full max-w-lg">
                  <p className="text-[11px] font-semibold text-[#8B6340] mb-3 uppercase tracking-widest flex items-center justify-center gap-1.5">
                    <Sparkles size={11} /> Try asking…
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {SAMPLE_QUESTIONS[task].map(q => (
                      <button key={q} onClick={() => setQuery(q)} className="rounded-xl border border-[#ddc9a8] bg-white px-4 py-3 text-sm text-[#7B3F00] text-left hover:bg-[#fdf4e8] hover:border-amber-300 hover:shadow-sm transition-all">{q}</button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {history.length > 0 && (
            <div className="py-6 space-y-8">
                {history.map(entry => <AnswerCard key={entry.id} entry={entry} showScores={showScores} />)}
                {loading && (
                  <div className="flex items-center gap-3 text-sm text-[#8B6340] animate-pulse-soft py-2">
                    <Spinner size="sm" /><span>Searching scriptures…</span>
                  </div>
                )}
                <div ref={bottomRef} />
              </div>
            )}

            {history.length === 0 && loading && (
              <div className="flex flex-col items-center justify-center min-h-[50vh] gap-3">
                <Spinner size="lg" />
                <p className="text-sm text-[#8B6340] animate-pulse-soft">Searching scriptures…</p>
              </div>
            )}

            {error && (
              <div className="mt-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-start gap-2 animate-fade-in">
                <span className="flex-shrink-0">⚠️</span>
                <span className="flex-1">{error}</span>
                <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 flex-shrink-0"><X size={14} /></button>
              </div>
            )}
          </div>
        </main>

        {/* Input area */}
        <div className="flex-shrink-0 border-t border-[#d8cdbb] bg-[#F0E9DE] px-3 py-2">
          <div className="mx-auto max-w-4xl space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-y-1.5 gap-x-2">
              {/* 3-tab selector */}
              <div className="flex gap-1.5 flex-wrap">
                {TASK_CONFIGS.map(config => (
                  <button
                    key={config.id}
                    onClick={() => { setTask(config.id as TaskType); setQuery(""); setError(null) }}
                    title={config.description}
                    className={`flex items-center gap-1 rounded-full px-2.5 py-1.5 text-[11px] sm:text-xs font-medium border transition-all duration-150 focus:outline-none ${task === config.id ? "bg-amber-600 border-amber-600 text-white shadow-sm" : "bg-white border-[#ddc9a8] text-[#7B3F00] hover:bg-amber-50 hover:border-amber-400"}`}
                  >
                    <span>{config.icon}</span><span>{config.label}</span>
                  </button>
                ))}
              </div>

              <div className="flex items-center gap-2">
                {/* Sources stepper — hidden for quiz (question count parsed from query) */}
                {task !== "quiz" && (
                  <div className="flex items-center gap-1 rounded-full border border-[#ddc9a8] bg-white px-2 py-0.5 text-[11px] text-[#7B3F00]">
                    <span className="text-[#8B6340] font-medium pr-1">Sources:</span>
                    <button onClick={() => setTopN(n => Math.max(1, n - 1))} disabled={topN <= 1} className="w-5 h-5 rounded-full flex items-center justify-center hover:bg-[#f5ede0] disabled:opacity-30 disabled:cursor-not-allowed font-bold">−</button>
                    <span className="w-4 text-center font-semibold tabular-nums">{topN}</span>
                    <button onClick={() => setTopN(n => Math.min(10, n + 1))} disabled={topN >= 10} className="w-5 h-5 rounded-full flex items-center justify-center hover:bg-[#f5ede0] disabled:opacity-30 disabled:cursor-not-allowed font-bold">+</button>
                  </div>
                )}
                <BookFilter selected={bookFilter} onChange={setBookFilter} />
              </div>
            </div>

            <p className="text-[11px] text-[#8B6340] hidden sm:block">
              {taskConfig.icon}{" "}<strong className="font-medium text-[#7B3F00]">{taskConfig.label}:</strong>{" "}{taskConfig.hint}
            </p>

            <InputBar value={query} onChange={setQuery} onSubmit={handleSubmit} loading={loading} activeTask={task} />

            <p className="text-center text-[10px] text-slate-500 hidden md:block">
              Answers are based strictly on Srila Prabhupada's books. Always verify with a qualified devotee.
            </p>
            <footer className="text-center text-[10px] text-slate-400 hidden md:block">
              © {new Date().getFullYear()} Prabhupada GPT · Built for devotional study
            </footer>
          </div>
        </div>
      </div>
    </div>
  )
}