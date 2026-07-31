import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, Database } from 'lucide-react'
import { KBViewer } from '../components/KBViewer'
import { kbApi, type KBDoc } from '../api/client'

export function KnowledgeBasePage() {
  const [appName, setAppName] = useState('linkedin')
  const [docs, setDocs] = useState<KBDoc[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (app: string) => {
    if (!app.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await kbApi.list(app)
      setDocs(res.docs)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load')
      setDocs([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(appName)
    // Intentionally load once on mount: depending on `appName` would refetch on
    // every keystroke; reloads are user-triggered via the Load button instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleClear = async () => {
    if (!confirm(`Clear all knowledge base entries for "${appName}"?`)) return
    await kbApi.clear(appName)
    setDocs([])
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-6 px-4">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <Link
            to="/setup"
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Setup
          </Link>
          <h1 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Database className="w-5 h-5" />
            Knowledge Base
          </h1>
          <div className="w-16" />
        </div>

        <div className="flex gap-2">
          <input
            value={appName}
            onChange={(e) => setAppName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && load(appName)}
            placeholder="App name (e.g. linkedin)"
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
          />
          <button
            onClick={() => load(appName)}
            className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-sm rounded-lg transition-colors"
          >
            Load
          </button>
        </div>

        {error && (
          <div className="px-3 py-2 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">
            {error}
          </div>
        )}

        {loading ? (
          <div className="text-center text-zinc-600 text-sm py-12">Loading…</div>
        ) : (
          <KBViewer docs={docs} onClear={docs.length > 0 ? handleClear : undefined} />
        )}
      </div>
    </div>
  )
}
