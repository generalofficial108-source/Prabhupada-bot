"use client"

import { useState } from "react"
import { ChevronDown, ChevronUp } from "lucide-react"
import { Badge } from "@/components/ui/Badge"
import type { SourceVerse } from "@/types"

interface SourceCardProps {
  verse:       SourceVerse
  showScores?: boolean
}

export function SourceCard({ verse, showScores = false }: SourceCardProps) {
  const [purportOpen, setPurportOpen] = useState(false)

  return (
    <div className="rounded-xl border border-[#ddc9a8] bg-[#f5ede0] p-4 text-sm">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-2 mb-3">
        <div>
          <span className="font-bold text-[#7B3F00] text-base">{verse.reference}</span>
          {verse.total_parts > 1 && (
            <span className="ml-2 text-xs text-[#8B6340]">Part {verse.part}/{verse.total_parts}</span>
          )}
          <p className="text-xs text-[#8B6340] mt-0.5">{verse.book}</p>
        </div>
        <div className="flex items-center gap-1.5 flex-wrap">
          {verse.direct_lookup && <Badge variant="green">✓ Exact Match</Badge>}
          {showScores && !verse.direct_lookup && (
            <>
              <Badge variant="muted">v {verse.vector_score.toFixed(2)}</Badge>
              <Badge variant="saffron">r {verse.rerank_score.toFixed(2)}</Badge>
            </>
          )}
        </div>
      </div>

      {/* Sanskrit */}
      {verse.verse_sanskrit && (
        <div className="mb-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#7B3F00] mb-1">
            Sanskrit Verse
          </p>
          <p className="italic text-[#4a2e0e] leading-relaxed text-sm">
            {verse.verse_sanskrit}
          </p>
        </div>
      )}

      {/* Word-for-word */}
      {verse.word_for_word && (
        <div className="mb-3">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-[#7B3F00] mb-1">
            Word-for-Word
          </p>
          <p className="text-[#3d2b10] leading-relaxed text-[13px]">
            {verse.word_for_word}
          </p>
        </div>
      )}

      {/* Translation */}
      <div className="mb-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-[#7B3F00] mb-1">
          Translation
        </p>
        <p className="text-[#2c1a0e] leading-relaxed">{verse.translation}</p>
      </div>

      {/* Purport toggle */}
      {verse.purport && (
        <div className="mt-3 border-t border-[#ddc9a8] pt-3">
          <button
            onClick={() => setPurportOpen(o => !o)}
            className="flex items-center gap-1.5 text-xs font-medium text-[#7B3F00] hover:text-saffron-700 transition-colors"
          >
            {purportOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            {purportOpen ? "Hide Purport" : "Read Full Purport"}
          </button>

          {purportOpen && (
            <div className="mt-3 max-h-64 overflow-y-auto pr-1 animate-fade-in">
              {verse.purport.split("\n\n").map((para, i) => (
                <p key={i} className="text-[#2c1a0e] leading-relaxed text-sm mb-3 last:mb-0">
                  {para}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}