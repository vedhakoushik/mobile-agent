import { useState } from 'react'
import { Search, Trash2 } from 'lucide-react'
import type { KBDoc } from '../api/client'

interface Props {
  docs: KBDoc[]
  onClear?: () => void
}

export function KBViewer({ docs, onClear }: Props) {
  const [query, setQuery] = useState('')

  const filtered = query
    ? docs.filter(
        (d) =>
          d.documentation.toLowerCase().includes(query.toLowerCase()) ||
          d.element_sig.toLowerCase().includes(query.toLowerCase()),
      )
    : docs

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search docs…"
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg pl-9 pr-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
          />
        </div>
        {onClear && (
          <button
            onClick={onClear}
            className="flex items-center gap-1.5 px-3 py-2 text-xs text-zinc-400 border border-zinc-700 rounded-lg hover:border-red-700 hover:text-red-400 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear
          </button>
        )}
      </div>

      <div className="text-xs text-zinc-500">
        {filtered.length} / {docs.length} elements documented
      </div>

      <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
        {filtered.map((doc) => (
          <div key={doc.id} className="border border-zinc-800 rounded-lg p-3 space-y-1 hover:border-zinc-700">
            <div className="font-mono text-xs text-zinc-400 truncate">{doc.element_sig}</div>
            <div className="text-sm text-zinc-200">{doc.documentation}</div>
            {doc.observed_result && (
              <div className="text-xs text-zinc-500 italic">{doc.observed_result}</div>
            )}
          </div>
        ))}
        {filtered.length === 0 && (
          <div className="text-center text-zinc-600 text-sm py-6">No matching docs</div>
        )}
      </div>
    </div>
  )
}
