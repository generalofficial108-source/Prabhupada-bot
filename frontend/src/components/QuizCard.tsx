"use client"

// =============================================================================
// src/components/QuizCard.tsx
//
// Interactive MCQ quiz component.
// Expects questions shaped exactly as the backend returns:
//   { question, options: ["A. ...", ...], answer: "A. ...", reference, explanation }
// =============================================================================

import { useState } from "react"
import { CheckCircle, XCircle, ChevronDown, ChevronUp } from "lucide-react"
import { clsx } from "clsx"
import type { QuizQuestion } from "@/types"

interface QuizCardProps {
  questions: QuizQuestion[]
  scope:     string   // e.g. "NOI 1, NOI 2, NOI 3"
}

export function QuizCard({ questions, scope }: QuizCardProps) {
  const [answers,   setAnswers]   = useState<Record<number, string>>({})
  const [submitted, setSubmitted] = useState(false)
  const [expanded,  setExpanded]  = useState<Record<number, boolean>>({})

  const answeredCount = Object.keys(answers).length
  const score = submitted
    ? questions.filter((q, i) => answers[i] === q.answer).length
    : null

  const handleSelect = (qi: number, option: string) => {
    if (submitted) return
    setAnswers(prev => ({ ...prev, [qi]: option }))
  }

  const toggleExpand = (i: number) =>
    setExpanded(prev => ({ ...prev, [i]: !prev[i] }))

  const handleReset = () => {
    setAnswers({})
    setSubmitted(false)
    setExpanded({})
  }

  return (
    <div className="space-y-4">

      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-[#7B3F00] text-sm flex items-center gap-1.5">
            📝 Quiz
          </h3>
          <p className="text-[11px] text-[#8B6340] mt-0.5">
            {questions.length} questions
            {!submitted && ` · ${answeredCount} answered`}
          </p>
        </div>

        {submitted && score !== null && (
          <div className={clsx(
            "rounded-full px-4 py-1.5 text-sm font-bold flex-shrink-0",
            score === questions.length
              ? "bg-emerald-100 text-emerald-800"
              : score >= Math.ceil(questions.length / 2)
                ? "bg-amber-100 text-amber-800"
                : "bg-red-100 text-red-800"
          )}>
            {score}/{questions.length}
            <span className="font-normal ml-1 text-xs">
              {score === questions.length
                ? "🎉 Perfect!"
                : score >= Math.ceil(questions.length / 2)
                  ? "Good"
                  : "Try again"}
            </span>
          </div>
        )}
      </div>

      {/* ── Questions ── */}
      {questions.map((q, qi) => {
        const selected     = answers[qi]
        const isCorrectAns = submitted && selected === q.answer
        const isWrongAns   = submitted && !!selected && selected !== q.answer

        return (
          <div
            key={qi}
            className={clsx(
              "rounded-xl border overflow-hidden transition-all",
              submitted && isCorrectAns ? "border-emerald-300" :
              submitted && isWrongAns   ? "border-red-300"     :
              "border-[#ddc9a8]"
            )}
          >
            {/* Question text + options */}
            <div className="px-4 pt-4 pb-3 bg-[#fdfaf5]">
              <p className="text-sm font-medium text-[#2c1a0e] mb-3 flex items-start gap-2.5">
                <span className="inline-flex items-center justify-center flex-shrink-0 w-5 h-5 rounded-full bg-saffron-100 text-saffron-700 text-[11px] font-bold mt-0.5">
                  {qi + 1}
                </span>
                {q.question}
              </p>

              <div className="space-y-2 pl-7">
                {q.options.map((opt) => {
                  const isSelected   = selected === opt
                  const isCorrectOpt = opt === q.answer

                  let optStyle: string
                  if (!submitted) {
                    optStyle = isSelected
                      ? "border-saffron-500 bg-saffron-50 text-saffron-900"
                      : "border-[#ddc9a8] bg-white text-[#2c1a0e] hover:border-saffron-300 hover:bg-[#fdf4e8]"
                  } else if (isCorrectOpt) {
                    optStyle = "border-emerald-500 bg-emerald-50 text-emerald-900"
                  } else if (isSelected && !isCorrectOpt) {
                    optStyle = "border-red-400 bg-red-50 text-red-900"
                  } else {
                    optStyle = "border-[#ddc9a8] bg-white text-[#8B6340] opacity-60"
                  }

                  return (
                    <button
                      key={opt}
                      onClick={() => handleSelect(qi, opt)}
                      disabled={submitted}
                      className={clsx(
                        "w-full text-left rounded-lg border px-3 py-2 text-xs",
                        "flex items-center gap-2 transition-all",
                        optStyle,
                        !submitted ? "cursor-pointer" : "cursor-default",
                      )}
                    >
                      {submitted && isCorrectOpt && (
                        <CheckCircle size={13} className="text-emerald-600 flex-shrink-0" />
                      )}
                      {submitted && isSelected && !isCorrectOpt && (
                        <XCircle size={13} className="text-red-500 flex-shrink-0" />
                      )}
                      <span className="leading-relaxed">{opt}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Explanation — visible only after submit */}
            {submitted && (
              <div className="border-t border-[#ddc9a8] bg-[#f5ede0]">
                <button
                  onClick={() => toggleExpand(qi)}
                  className="flex items-center gap-1.5 w-full px-4 py-2.5 text-[11px] font-medium text-[#7B3F00] hover:text-saffron-700 transition-colors text-left"
                >
                  {expanded[qi] ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                  {expanded[qi] ? "Hide" : "See"} explanation
                  <span className="ml-auto text-[#8B6340] font-normal">{q.reference}</span>
                </button>

                {expanded[qi] && (
                  <div className="px-4 pb-3 animate-fade-in">
                    <p className="text-[11px] text-[#4a2e0e] leading-relaxed border-l-2 border-saffron-300 pl-3">
                      {/* explanation may be undefined if LLM omits it — fallback gracefully */}
                      {q.explanation ?? `Correct answer: ${q.answer}`}
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}

      {/* ── Actions ── */}
      <div className="flex items-center gap-3 pt-1">
        {!submitted ? (
          <button
            onClick={() => setSubmitted(true)}
            disabled={answeredCount < questions.length}
            className={clsx(
              "rounded-xl px-5 py-2 text-sm font-semibold transition-all",
              answeredCount === questions.length
                ? "bg-saffron-600 text-white hover:bg-saffron-700 active:scale-95"
                : "bg-[#f0e4d0] text-[#c4a882] cursor-not-allowed"
            )}
          >
            Submit ({answeredCount}/{questions.length})
          </button>
        ) : (
          <button
            onClick={handleReset}
            className="rounded-xl px-5 py-2 text-sm font-medium border border-[#ddc9a8] text-[#7B3F00] hover:bg-saffron-50 transition-all"
          >
            Try Again
          </button>
        )}

        {!submitted && answeredCount < questions.length && (
          <p className="text-[11px] text-[#8B6340]">
            Answer all {questions.length} questions to submit
          </p>
        )}
      </div>
    </div>
  )
}