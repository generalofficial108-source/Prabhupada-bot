"use client"

import { useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface StreamedMarkdownProps {
  content: string
  enabled?: boolean
  charsPerTick?: number
  tickMs?: number
}

export function StreamedMarkdown({
  content,
  enabled = true,
  charsPerTick = 12,
  tickMs = 16,
}: StreamedMarkdownProps) {
  const [visibleChars, setVisibleChars] = useState(enabled ? 0 : content.length)

  useEffect(() => {
    if (!enabled) {
      setVisibleChars(content.length)
      return
    }
    setVisibleChars(0)
    const id = window.setInterval(() => {
      setVisibleChars((prev) => {
        const next = prev + charsPerTick
        if (next >= content.length) {
          window.clearInterval(id)
          return content.length
        }
        return next
      })
    }, tickMs)
    return () => window.clearInterval(id)
  }, [content, enabled, charsPerTick, tickMs])

  const text = useMemo(() => content.slice(0, visibleChars), [content, visibleChars])

  return (
    <div className="prose-answer max-w-none text-slate-800">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
      {enabled && visibleChars < content.length && (
        <span className="inline-block h-4 w-[2px] animate-pulse bg-amber-600 align-middle" />
      )}
    </div>
  )
}
