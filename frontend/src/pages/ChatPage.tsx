import { useEffect, useRef, useState } from 'react'
import { MessageSquare, SendHorizontal, Sparkles, Loader2, CheckCircle2, XCircle } from 'lucide-react'
import { clsx } from 'clsx'
import { DevicePicker } from '../components/DevicePicker'
import { useAgentStore } from '../store/agentStore'
import { useAgentStream } from '../hooks/useAgentStream'
import { agentApi } from '../api/client'

const PROVIDERS = [
  { value: 'gemini', label: 'Gemini 2.5 Flash' },
  { value: 'openai', label: 'GPT-4o' },
  { value: 'anthropic', label: 'Claude' },
  { value: 'ollama', label: 'Ollama (local)' },
  { value: 'cerebras', label: 'Cerebras' },
  { value: 'glm', label: 'GLM' },
]

const SUGGESTIONS = [
  'Post a status update on LinkedIn',
  'Search for flights in Chrome',
  'Compose a draft email in Gmail',
]

interface ChatMessage {
  id: number
  role: 'user' | 'agent'
  kind?: 'understood' | 'summary' | 'error'
  text: string
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [provider, setProvider] = useState('gemini')
  const [deviceSerial, setDeviceSerial] = useState('')
  const [starting, setStarting] = useState(false)
  const idRef = useRef(0)
  const scrollRef = useRef<HTMLDivElement>(null)

  const { sessionId, agentStatus, taskComplete, failureReason, logEntries, setSessionId, resetSession } =
    useAgentStore()

  useAgentStream(sessionId)

  useEffect(() => {
    resetSession()
  }, [resetSession])

  const addMessage = (partial: Omit<ChatMessage, 'id'>) => {
    setMessages((prev) => [...prev, { ...partial, id: ++idRef.current }])
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, logEntries, agentStatus])

  const isStreaming = starting || agentStatus === 'running'

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    setStarting(true)
    resetSession()
    setMessages([])
    addMessage({ role: 'user', text })
    try {
      const res = await agentApi.chat({
        message: text,
        provider,
        ...(deviceSerial ? { device_serial: deviceSerial } : {}),
      })
      addMessage({ role: 'agent', kind: 'understood', text: `Got it — ${res.task} on ${res.app_name}` })
      setSessionId(res.session_id)
    } catch (err) {
      addMessage({
        role: 'agent',
        kind: 'error',
        text: err instanceof Error ? err.message : 'Something went wrong',
      })
      setStarting(false)
    }
  }

  const showSummary = (agentStatus === 'done' || agentStatus === 'error') && sessionId !== null && !starting
  const summaryText = taskComplete
    ? `Task completed${failureReason ? ` — ${failureReason}` : ''}`
    : (failureReason ?? 'The agent stopped before finishing.')

  return (
    <div className="max-w-2xl mx-auto px-4 py-6 h-[calc(100vh-3.5rem)] flex flex-col space-y-4">
      <header className="flex items-center gap-2">
        <MessageSquare className="w-6 h-6 text-sky-400" />
        <h1 className="text-xl font-bold text-zinc-100">Chat</h1>
        <span className="text-zinc-500 text-sm">Describe a task — no setup required</span>
      </header>

      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-3 pr-1">
        {messages.length === 0 && logEntries.length === 0 && !showSummary ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center space-y-4">
              <Sparkles className="w-8 h-8 text-zinc-700 mx-auto" />
              <p className="text-sm text-zinc-500">Tell the agent what to do on your phone.</p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => setInput(s)}
                    className="px-3 py-1.5 text-xs rounded-lg border border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <>
            {messages.map((m) => (
              <div key={m.id} className={clsx('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
                <div
                  className={clsx(
                    'max-w-[85%] rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap',
                    m.role === 'user' && 'bg-sky-600 text-white',
                    m.role === 'agent' && m.kind === 'understood' && 'bg-zinc-900 border border-zinc-800 text-zinc-200',
                    m.kind === 'error' && 'bg-red-950 border border-red-800 text-red-300',
                  )}
                >
                  {m.text}
                </div>
              </div>
            ))}

            {logEntries.map((entry, i) => (
              <div key={i} className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl px-3.5 py-2 bg-zinc-900 border border-zinc-800 text-xs">
                  <div className="font-mono text-zinc-300">
                    <span className="text-zinc-500">Round {entry.round}:</span>{' '}
                    <span className="font-semibold text-sky-400">{entry.action}</span>
                    {entry.element_id !== null && <span className="text-zinc-500"> #{entry.element_id}</span>}
                  </div>
                  {entry.thought && <div className="text-zinc-500 mt-0.5">{entry.thought}</div>}
                </div>
              </div>
            ))}

            {showSummary && (
              <div className="flex justify-start">
                <div
                  className={clsx(
                    'flex items-start gap-2 max-w-[85%] rounded-2xl px-3.5 py-2 text-sm border',
                    taskComplete
                      ? 'bg-emerald-950 border-emerald-800 text-emerald-300'
                      : 'bg-red-950 border-red-800 text-red-300',
                  )}
                >
                  {taskComplete ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
                  )}
                  {summaryText}
                </div>
              </div>
            )}

            {starting && (
              <div className="flex justify-start">
                <div className="rounded-2xl px-3.5 py-2 bg-zinc-900 border border-zinc-800 text-zinc-500 text-sm flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Understanding…
                </div>
              </div>
            )}
          </>
        )}
      </div>

      <div className="space-y-2 shrink-0">
        <div className="grid grid-cols-2 gap-2">
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 focus:outline-none focus:border-zinc-500"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <DevicePicker value={deviceSerial} onChange={setDeviceSerial} />
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                handleSend()
              }
            }}
            disabled={isStreaming}
            placeholder={isStreaming ? 'Agent is working…' : 'e.g. Post a status update on LinkedIn'}
            className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            className="flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:hover:bg-sky-600 text-white text-sm rounded-lg transition-colors"
          >
            <SendHorizontal className="w-4 h-4" />
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
