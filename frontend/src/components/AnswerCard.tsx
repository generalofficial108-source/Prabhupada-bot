"use client"

// =============================================================================
// src/components/AnswerCard.tsx
//
// Renders one chat entry (question + answer + sources).
// For quiz task: delegates to QuizCard for interactive MCQ UI.
// ISKCON contact is shown once in the sidebar — NOT repeated here.
// =============================================================================

import { useState } from "react"
import { ChevronDown, ChevronUp, BookOpen } from "lucide-react"
import { Badge } from "@/components/ui/Badge"
import { SourceCard } from "@/components/SourceCard"
import { QuizCard } from "@/components/QuizCard"
import { StreamedMarkdown } from "@/components/StreamedMarkdown"
import { TASK_CONFIGS, MODE_ICONS } from "@/types"
import type { ChatEntry } from "@/types"

interface AnswerCardProps {
  entry:       ChatEntry
  showScores?: boolean
}

export function AnswerCard({ entry, showScores = false }: AnswerCardProps) {
  const [sourcesOpen, setSourcesOpen] = useState(entry.response.is_direct)

  const taskConfig = TASK_CONFIGS.find(t => t.id === entry.task)
  const modeIcon   = MODE_ICONS[entry.response.mode] ?? taskConfig?.icon ?? "💬"

  const isQuiz = entry.response.task === "quiz"

  return (
    <div className="animate-slide-up space-y-3">

      {/* ── Question row ── */}
      <div className="flex items-start gap-2">
        <span className="text-lg">{modeIcon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-0.5">
            <p className="font-semibold text-[#2c1a0e] break-words">{entry.query}</p>
            {entry.response.is_direct
              ? <Badge variant="green">Direct Lookup</Badge>
              : <Badge variant="saffron">{entry.response.mode}</Badge>
            }
          </div>
          <p className="text-xs text-[#8B6340]">
            {entry.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            {" · "}{entry.response.llm_model}
          </p>
        </div>
      </div>

      {/* ── Answer / Quiz ── */}
      <div className="rounded-xl border-l-4 border-saffron-500 bg-[#fffdf7] px-5 py-4 shadow-sm">
        {isQuiz && entry.response.quiz_data && entry.response.quiz_data.length > 0 ? (
          <QuizCard
            questions={entry.response.quiz_data as any}
            scope={entry.response.context_used.join(", ")}
          />
        ) : (
          <StreamedMarkdown content={entry.response.answer} enabled={Boolean(entry.animate)} />
        )}
      </div>

      {/* ── Sources toggle (hidden for quiz — references are inline per question) ── */}
      {!isQuiz && entry.response.sources.length > 0 && (
        <div>
          <button
            onClick={() => setSourcesOpen(o => !o)}
            className="flex items-center gap-2 text-sm font-medium text-[#7B3F00] hover:text-saffron-700 transition-colors"
          >
            <BookOpen size={15} />
            <span>Sources: {entry.response.context_used.join(", ")}</span>
            {sourcesOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {sourcesOpen && (
            <div className="mt-3 space-y-3 animate-fade-in">
              {entry.response.sources.map((verse, i) => (
                <SourceCard key={i} verse={verse} showScores={showScores} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}