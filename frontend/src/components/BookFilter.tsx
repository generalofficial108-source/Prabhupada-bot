"use client"

import { BOOK_OPTIONS } from "@/types"
import { clsx } from "clsx"

interface BookFilterProps {
  selected:  string[]
  onChange:  (codes: string[]) => void
}

export function BookFilter({ selected, onChange }: BookFilterProps) {
  const toggle = (code: string) => {
    if (selected.includes(code)) {
      // Don't allow deselecting all
      if (selected.length === 1) return
      onChange(selected.filter(c => c !== code))
    } else {
      onChange([...selected, code])
    }
  }

  const allSelected = selected.length === BOOK_OPTIONS.length

  return (
    <div className="flex items-center gap-2 min-w-0">
      <span className="text-[11px] font-medium text-slate-500 mr-1 hidden sm:inline">Books:</span>
      <div className="flex items-center gap-2 overflow-x-auto whitespace-nowrap no-scrollbar py-0.5">

        <button
          onClick={() => onChange(allSelected ? [BOOK_OPTIONS[0].code] : BOOK_OPTIONS.map(b => b.code))}
          className={clsx(
            "rounded-full px-2.5 py-1 text-[11px] font-medium border transition-all",
            allSelected
              ? "bg-amber-100 border-amber-300 text-amber-800"
              : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
          )}
        >
          All
        </button>

        {BOOK_OPTIONS.map(book => (
          <button
            key={book.code}
            onClick={() => toggle(book.code)}
            className={clsx(
              "rounded-full px-2.5 py-1 text-[11px] font-medium border transition-all",
              selected.includes(book.code) && !allSelected
                ? "bg-amber-100 border-amber-300 text-amber-800"
                : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"
            )}
          >
            {book.code.toUpperCase()}
          </button>
        ))}
      </div>
    </div>
  )
}
