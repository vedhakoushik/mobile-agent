import { useState, useEffect, useCallback } from 'react'
import { Radio, Play, Square, Trash2, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'
import { clsx } from 'clsx'
import { DevicePicker } from '../components/DevicePicker'
import { demonstrationsApi, type DemoListItem, type ReplayResponse } from '../api/client'

type ActionType = 'tap' | 'text' | 'swipe' | 'long_press' | 'key_event' | 'wait'

const ACTION_TYPES: ActionType[] = ['tap', 'text', 'swipe', 'long_press', 'key_event', 'wait']

const ACTION_LABELS: Record<ActionType, string> = {
  tap: 'Tap',
  text: 'Text',
  swipe: 'Swipe',
  long_press: 'Long Press',
  key_event: 'Key Event',
  wait: 'Wait',
}

interface FieldDef {
  key: string
  label: string
  type: 'number' | 'text' | 'select'
  options?: string[]
  placeholder?: string
}

const ACTION_FIELDS: Record<ActionType, FieldDef[]> = {
  tap: [
    { key: 'x', label: 'X', type: 'number' },
    { key: 'y', label: 'Y', type: 'number' },
  ],
  text: [{ key: 'content', label: 'Content', type: 'text' }],
  swipe: [
    { key: 'direction', label: 'Direction', type: 'select', options: ['up', 'down', 'left', 'right'] },
    { key: 'from_x', label: 'From X (optional)', type: 'number' },
    { key: 'from_y', label: 'From Y (optional)', type: 'number' },
  ],
  long_press: [
    { key: 'x', label: 'X', type: 'number' },
    { key: 'y', label: 'Y', type: 'number' },
  ],
  key_event: [{ key: 'code', label: 'Key Code', type: 'number', placeholder: 'e.g. 4 = BACK' }],
  wait: [{ key: 'duration', label: 'Duration (s)', type: 'number' }],
}

const ACTION_DEFAULTS: Record<ActionType, Record<string, string>> = {
  tap: { x: '0', y: '0' },
  text: { content: '' },
  swipe: { direction: 'up', from_x: '', from_y: '' },
  long_press: { x: '0', y: '0' },
  key_event: { code: '' },
  wait: { duration: '1' },
}

function ActionForm({
  actionType,
  onRecord,
}: {
  actionType: ActionType
  onRecord: (params: Record<string, unknown>) => void
}) {
  const [values, setValues] = useState<Record<string, string>>(() => ({ ...ACTION_DEFAULTS[actionType] }))

  const submit = () => {
    const params: Record<string, unknown> = {}
    for (const field of ACTION_FIELDS[actionType]) {
      const raw = values[field.key] ?? ''
      if (field.type === 'number') {
        if (raw === '') continue
        params[field.key] = Number(raw)
      } else {
        params[field.key] = raw
      }
    }
    onRecord(params)
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        {ACTION_FIELDS[actionType].map((field) =>
          field.type === 'select' ? (
            <div key={field.key}>
              <label className="block text-xs text-zinc-500 mb-1.5">{field.label}</label>
              <select
                value={values[field.key]}
                onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
              >
                {field.options?.map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
            </div>
          ) : (
            <div key={field.key}>
              <label className="block text-xs text-zinc-500 mb-1.5">{field.label}</label>
              <input
                type={field.type === 'number' ? 'number' : 'text'}
                value={values[field.key] ?? ''}
                onChange={(e) => setValues((v) => ({ ...v, [field.key]: e.target.value }))}
                placeholder={field.placeholder}
                step={field.type === 'number' ? '1' : undefined}
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>
          ),
        )}
      </div>
      <button
        onClick={submit}
        className="px-4 py-2 bg-emerald-700 hover:bg-emerald-600 text-white text-sm rounded-lg transition-colors"
      >
        Record {ACTION_LABELS[actionType]}
      </button>
    </div>
  )
}

interface ReplayView {
  status: 'ok' | 'error'
  data?: ReplayResponse
  message?: string
}

export function DemonstrationsPage() {
  const [appName, setAppName] = useState('linkedin')
  const [deviceSerial, setDeviceSerial] = useState('')
  const [taskDescription, setTaskDescription] = useState('')
  const [recordingId, setRecordingId] = useState<string | null>(null)
  const [stepsRecorded, setStepsRecorded] = useState(0)
  const [activeAction, setActiveAction] = useState<ActionType | null>(null)
  const [recordingBusy, setRecordingBusy] = useState(false)
  const [pageError, setPageError] = useState<string | null>(null)
  const [demos, setDemos] = useState<DemoListItem[]>([])
  const [loadingDemos, setLoadingDemos] = useState(false)
  const [demosError, setDemosError] = useState<string | null>(null)
  const [replayViews, setReplayViews] = useState<Record<string, ReplayView>>({})
  const [replayingId, setReplayingId] = useState<string | null>(null)

  const loadDemos = useCallback(async (app: string) => {
    if (!app.trim()) return
    setLoadingDemos(true)
    setDemosError(null)
    try {
      const res = await demonstrationsApi.list(app)
      setDemos(res)
    } catch (err) {
      setDemosError(err instanceof Error ? err.message : 'Failed to load demonstrations')
      setDemos([])
    } finally {
      setLoadingDemos(false)
    }
  }, [])

  useEffect(() => {
    const t = setTimeout(() => loadDemos(appName), 300)
    return () => clearTimeout(t)
  }, [appName, loadDemos])

  const handleStart = async () => {
    if (!appName.trim() || !taskDescription.trim()) return
    setPageError(null)
    try {
      const res = await demonstrationsApi.startRecording(appName, {
        task_description: taskDescription,
        ...(deviceSerial ? { device_serial: deviceSerial } : {}),
      })
      setRecordingId(res.recording_id)
      setStepsRecorded(0)
      setActiveAction(null)
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'Failed to start recording')
    }
  }

  const handleRecordStep = async (actionType: ActionType, params: Record<string, unknown>) => {
    if (!recordingId) return
    setRecordingBusy(true)
    setPageError(null)
    try {
      const res = await demonstrationsApi.recordStep(appName, {
        recording_id: recordingId,
        action_type: actionType,
        params,
      })
      setStepsRecorded(res.steps_recorded)
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'Failed to record step')
    } finally {
      setRecordingBusy(false)
    }
  }

  const handleStop = async () => {
    if (!recordingId) return
    try {
      await demonstrationsApi.stopRecording(appName, { recording_id: recordingId })
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'Failed to stop recording')
    } finally {
      setRecordingId(null)
      setStepsRecorded(0)
      setActiveAction(null)
      loadDemos(appName)
    }
  }

  const handleReplay = async (demo: DemoListItem) => {
    setReplayingId(demo.recording_id)
    setPageError(null)
    try {
      const res = await demonstrationsApi.replay(appName, demo.recording_id, {
        ...(deviceSerial ? { device_serial: deviceSerial } : {}),
        on_drift: 'stop',
      })
      setReplayViews((prev) => ({ ...prev, [demo.recording_id]: { status: 'ok', data: res } }))
    } catch (err) {
      setReplayViews((prev) => ({
        ...prev,
        [demo.recording_id]: { status: 'error', message: err instanceof Error ? err.message : 'Failed to replay' },
      }))
    } finally {
      setReplayingId(null)
    }
  }

  const handleDelete = async (demo: DemoListItem) => {
    if (!confirm(`Delete demonstration "${demo.task_description}"?`)) return
    setPageError(null)
    try {
      await demonstrationsApi.delete(appName, demo.recording_id)
      setReplayViews((prev) => {
        const next = { ...prev }
        delete next[demo.recording_id]
        return next
      })
      loadDemos(appName)
    } catch (err) {
      setPageError(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100 flex items-center gap-2">
          <Radio className="w-6 h-6 text-sky-400" />
          Demonstrations
        </h1>
        <p className="text-zinc-500 text-sm mt-1">Record a manual macro on your device and replay it any time.</p>
      </div>

      {pageError && (
        <div className="px-3 py-2 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">{pageError}</div>
      )}

      <div className="border border-zinc-800 rounded-xl p-5 space-y-4">
        {!recordingId ? (
          <>
            <div>
              <label className="block text-xs text-zinc-500 mb-2">App Name</label>
              <input
                type="text"
                value={appName}
                onChange={(e) => setAppName(e.target.value)}
                placeholder="e.g. linkedin, twitter, gmail"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>

            <div>
              <label className="block text-xs text-zinc-500 mb-2">Device</label>
              <DevicePicker value={deviceSerial} onChange={setDeviceSerial} />
            </div>

            <div>
              <label className="block text-xs text-zinc-500 mb-2">Task Description</label>
              <input
                type="text"
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
                placeholder="What does this macro do?"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 focus:outline-none focus:border-zinc-500"
              />
            </div>

            <button
              onClick={handleStart}
              disabled={!appName.trim() || !taskDescription.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 disabled:hover:bg-sky-600 text-white text-sm rounded-lg transition-colors"
            >
              <Play className="w-4 h-4" />
              Start Recording
            </button>
          </>
        ) : (
          <>
            <div className="flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-zinc-200 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  Recording
                </div>
                <div className="text-xs text-zinc-500 mt-1">{taskDescription}</div>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-emerald-400 font-mono">{stepsRecorded}</div>
                <div className="text-xs text-zinc-500">steps recorded</div>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              {ACTION_TYPES.map((action) => (
                <button
                  key={action}
                  onClick={() => setActiveAction(action === activeAction ? null : action)}
                  className={clsx(
                    'px-3 py-1.5 text-xs rounded-lg border transition-colors',
                    activeAction === action
                      ? 'bg-zinc-800 border-zinc-500 text-zinc-100'
                      : 'bg-zinc-900 border-zinc-700 text-zinc-400 hover:text-zinc-200',
                  )}
                >
                  {ACTION_LABELS[action]}
                </button>
              ))}
            </div>

            {activeAction && (
              <div className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/50">
                <ActionForm
                  key={activeAction}
                  actionType={activeAction}
                  onRecord={(params) => handleRecordStep(activeAction, params)}
                />
              </div>
            )}

            <button
              onClick={handleStop}
              disabled={recordingBusy}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-950 hover:bg-red-900 text-red-300 text-sm rounded-lg transition-colors disabled:opacity-50"
            >
              <Square className="w-4 h-4" />
              Stop Recording
            </button>
          </>
        )}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-zinc-300">Saved Demonstrations</h2>
          <button
            onClick={() => loadDemos(appName)}
            className="text-xs text-sky-400 hover:text-sky-300 transition-colors"
          >
            Refresh
          </button>
        </div>

        {demosError && (
          <div className="px-3 py-2 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">{demosError}</div>
        )}

        {loadingDemos ? (
          <div className="text-center text-zinc-600 text-sm py-8">Loading…</div>
        ) : demos.length === 0 ? (
          <div className="text-center text-zinc-600 text-sm py-8 border border-zinc-800 rounded-xl">
            No demonstrations saved for this app
          </div>
        ) : (
          demos.map((demo) => {
            const view = replayViews[demo.recording_id]
            return (
              <div key={demo.recording_id} className="border border-zinc-800 rounded-xl p-4 space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-zinc-200 truncate" title={demo.task_description}>
                      {demo.task_description}
                    </div>
                    <div className="text-xs text-zinc-500 mt-1">
                      {demo.step_count} steps · {new Date(demo.created_at).toLocaleString()}
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => handleReplay(demo)}
                      disabled={replayingId === demo.recording_id}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs rounded-lg transition-colors"
                    >
                      {replayingId === demo.recording_id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      Replay
                    </button>
                    <button
                      onClick={() => handleDelete(demo)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-900 border border-zinc-700 hover:border-red-700 text-zinc-400 hover:text-red-300 text-xs rounded-lg transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      Delete
                    </button>
                  </div>
                </div>

                {view?.status === 'error' && (
                  <div className="px-3 py-2 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">
                    {view.message}
                  </div>
                )}

                {view?.status === 'ok' && view.data && (() => {
                  const r = view.data
                  return (
                    <div
                      className={clsx(
                        'px-3 py-2 rounded-lg text-xs border',
                        r.completed
                          ? 'bg-emerald-950 border-emerald-800 text-emerald-300'
                          : 'bg-amber-950 border-amber-800 text-amber-300',
                      )}
                    >
                      <div className="flex items-center gap-2">
                        {r.completed ? (
                          <CheckCircle2 className="w-3.5 h-3.5" />
                        ) : (
                          <AlertTriangle className="w-3.5 h-3.5" />
                        )}
                        <span className="font-medium">
                          {r.completed ? 'Replay completed' : 'Replay stopped'}
                        </span>
                      </div>
                      <div className="mt-1 font-mono">
                        {r.steps_executed} / {r.steps_total} steps executed
                      </div>
                      {r.reason && <div className="mt-1 text-red-300">Reason: {r.reason}</div>}
                      {r.similarity != null && !r.completed && (
                        <div className="mt-1 text-amber-200">State similarity: {(r.similarity * 100).toFixed(0)}%</div>
                      )}
                      {r.failures.length > 0 && (
                        <div className="mt-2 space-y-1">
                          {r.failures.map((f, i) => (
                            <div key={i} className="text-amber-200/80">
                              Step {f.step}: {f.reason}
                              {f.similarity != null ? ` (similarity ${(f.similarity * 100).toFixed(0)}%)` : ''}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
