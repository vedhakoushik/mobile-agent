import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ChevronLeft, History as HistoryIcon } from 'lucide-react'
import { clsx } from 'clsx'
import { agentApi, type SessionSummary, type HistoryEntry } from '../api/client'

const ACTION_COLORS: Record<string, string> = {
  tap:        'text-sky-400',
  text:       'text-violet-400',
  swipe:      'text-amber-400',
  long_press: 'text-orange-400',
  finish:     'text-emerald-400',
  grid:       'text-pink-400',
  back:       'text-zinc-400',
}

function statusBadgeClass(status: string): string {
  if (status === 'done' || status === 'running') return 'bg-emerald-950 border-emerald-700 text-emerald-300'
  if (status === 'error') return 'bg-red-950 border-red-800 text-red-300'
  return 'bg-zinc-900 border-zinc-700 text-zinc-400'
}

export function HistoryPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const isDetail = !!sessionId

  const [summaries, setSummaries] = useState<SessionSummary[]>([])
  const [history, setHistory] = useState<HistoryEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let mounted = true
    setLoading(true)
    setError(null)
    if (sessionId) {
      agentApi
        .getSessionHistory(sessionId)
        .then((res) => {
          if (mounted) setHistory(res)
        })
        .catch((err) => {
          if (mounted) setError(err instanceof Error ? err.message : 'Failed to load history')
        })
        .finally(() => {
          if (mounted) setLoading(false)
        })
    } else {
      agentApi
        .listSessions()
        .then((res) => {
          if (mounted) setSummaries(res)
        })
        .catch((err) => {
          if (mounted) setError(err instanceof Error ? err.message : 'Failed to load sessions')
        })
        .finally(() => {
          if (mounted) setLoading(false)
        })
    }
    return () => {
      mounted = false
    }
  }, [sessionId])

  return (
    <div className="min-h-screen bg-zinc-950 py-6 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <Link
            to={isDetail ? '/history' : '/setup'}
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            {isDetail ? 'History' : 'Setup'}
          </Link>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <HistoryIcon className="w-5 h-5" />
            {isDetail ? 'Session Detail' : 'History'}
          </h1>
          <div className="w-16" />
        </div>

        {error && (
          <div className="px-3 py-2 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center text-zinc-600 text-sm py-12">Loading…</div>
        ) : isDetail ? (
          <div className="border border-zinc-800 rounded-xl overflow-hidden">
            {history.length === 0 ? (
              <div className="text-center text-zinc-600 text-sm py-12">No actions recorded</div>
            ) : (
              history.map((entry) => (
                <div key={entry.round_num} className="px-3 py-2 text-xs font-mono border-b border-zinc-900 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-zinc-500 w-10 shrink-0">R{entry.round_num}</span>
                    <span className={clsx('w-20 shrink-0 font-semibold', ACTION_COLORS[entry.action.action] ?? 'text-zinc-300')}>
                      {entry.action.action.toUpperCase()}
                    </span>
                    {entry.action.thought && (
                      <span className="flex-1 text-zinc-300 truncate min-w-0" title={entry.action.thought}>
                        {entry.action.thought}
                      </span>
                    )}
                    <span className="text-zinc-600 shrink-0">{new Date(entry.created_at).toLocaleString()}</span>
                  </div>
                  {entry.action.observation && (
                    <div className="pl-32 text-zinc-500 mt-1 truncate" title={entry.action.observation}>
                      {entry.action.observation}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="space-y-2">
            {summaries.length === 0 ? (
              <div className="text-center text-zinc-600 text-sm py-12">No sessions yet</div>
            ) : (
              summaries.map((s) => (
                <Link
                  key={s.session_id}
                  to={`/history/${s.session_id}`}
                  className="block border border-zinc-800 rounded-xl p-4 hover:border-zinc-600 transition-colors"
                >
                  <div className="flex items-center justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-zinc-200 truncate">{s.task}</span>
                        <span className={clsx('px-2 py-0.5 rounded-full text-xs border', statusBadgeClass(s.status))}>
                          {s.status}
                        </span>
                      </div>
                      <div className="text-xs font-mono text-zinc-500 mt-1 space-x-2">
                        <span className="text-sky-400">{s.app_name}</span>
                        <span>·</span>
                        <span>{s.mode}</span>
                        <span>·</span>
                        <span>{s.provider}</span>
                        {s.reasoning_mode && (
                          <>
                            <span>·</span>
                            <span>{s.reasoning_mode}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-xs text-zinc-500">
                      <div>R{s.round_num}</div>
                      <div>{new Date(s.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  )
}
