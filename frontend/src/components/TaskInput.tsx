import { useState } from 'react'
import { Play } from 'lucide-react'

interface Props {
  onSubmit: (task: string) => void
  disabled?: boolean
  suggestions?: string[]
  placeholder?: string
}

const DEFAULT_SUGGESTIONS = [
  'Find a software engineering job in Bangalore',
  'Search for Python developer roles',
  'Apply to the top result',
  'Check inbox for new messages',
]

export function TaskInput({ onSubmit, disabled, suggestions = DEFAULT_SUGGESTIONS, placeholder = 'Describe the task…' }: Props) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSubmit(trimmed)
    setValue('')
  }

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && submit()}
          placeholder={placeholder}
          disabled={disabled}
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 disabled:opacity-50"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-zinc-800 disabled:text-zinc-600 text-white text-sm rounded-lg transition-colors"
        >
          <Play className="w-3.5 h-3.5" />
          Run
        </button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {suggestions.map((s) => (
          <button
            key={s}
            onClick={() => setValue(s)}
            disabled={disabled}
            className="text-xs px-2.5 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 rounded-full transition-colors disabled:opacity-40"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  )
}
