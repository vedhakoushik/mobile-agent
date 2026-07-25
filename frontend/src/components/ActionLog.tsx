import { Virtuoso } from 'react-virtuoso'
import { clsx } from 'clsx'
import type { LogEntry } from '../store/agentStore'

interface Props {
  entries: LogEntry[]
  height?: number
}

const ACTION_COLORS: Record<string, string> = {
  tap:        'text-sky-400',
  text:       'text-violet-400',
  swipe:      'text-amber-400',
  long_press: 'text-orange-400',
  finish:     'text-emerald-400',
  grid:       'text-pink-400',
  back:       'text-zinc-400',
}

export function ActionLog({ entries, height = 320 }: Props) {
  if (entries.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-zinc-600 text-sm border border-zinc-800 rounded-xl"
        style={{ height }}
      >
        Agent actions will appear here
      </div>
    )
  }

  return (
    <div className="border border-zinc-800 rounded-xl overflow-hidden" style={{ height }}>
      <Virtuoso
        data={entries}
        followOutput="smooth"
        itemContent={(_, entry) => (
          <div className="flex gap-2 px-3 py-1.5 text-xs font-mono border-b border-zinc-900 hover:bg-zinc-900/50">
            <span className="text-zinc-500 w-10 shrink-0">R{entry.round}</span>
            <span className={clsx('w-20 shrink-0 font-semibold', ACTION_COLORS[entry.action] ?? 'text-zinc-300')}>
              {entry.action.toUpperCase()}
              {entry.element_id !== null && (
                <span className="text-zinc-500 font-normal"> #{entry.element_id}</span>
              )}
            </span>
            <span className="text-zinc-300 truncate" title={entry.thought}>
              {entry.thought}
            </span>
          </div>
        )}
      />
    </div>
  )
}
