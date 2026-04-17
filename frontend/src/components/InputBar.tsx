"use client"

import { useRef, useEffect, type KeyboardEvent } from "react"
import { Send } from "lucide-react"
import { Spinner } from "@/components/ui/Spinner"
import { TASK_CONFIGS, type TaskType } from "@/types"

interface InputBarProps {
  value:       string
  onChange:    (v: string) => void
  onSubmit:    () => void
  loading:     boolean
  activeTask:  TaskType
}

export function InputBar({ value, onChange, onSubmit, loading, activeTask }: InputBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const config = TASK_CONFIGS.find(t => t.id === activeTask)

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = Math.min(el.scrollHeight, 160) + "px"
  }, [value])

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      if (!loading && value.trim()) onSubmit()
    }
  }

  return (
    <div className="relative flex items-end gap-2 rounded-2xl border border-[#ddc9a8] bg-white px-3 py-2 shadow-sm focus-within:border-saffron-400 focus-within:ring-1 focus-within:ring-saffron-200 transition-all">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKey}
        placeholder={config?.placeholder ?? "Ask a question…"}
        disabled={loading}
        rows={1}
        className="flex-1 resize-none bg-transparent text-[#2c1a0e] placeholder-[#c4a882] text-sm leading-relaxed focus:outline-none disabled:opacity-60"
      />
      <button
        onClick={onSubmit}
        disabled={loading || !value.trim()}
        className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-saffron-600 text-white transition-all hover:bg-saffron-700 disabled:opacity-40 disabled:cursor-not-allowed"
        aria-label="Send"
      >
        {loading ? <Spinner size="sm" /> : <Send size={13} />}
      </button>
    </div>
  )
}
