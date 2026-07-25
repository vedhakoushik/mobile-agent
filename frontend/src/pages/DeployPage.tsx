import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ChevronLeft, Square, CheckCircle2, Circle, ArrowRight } from 'lucide-react'
import { clsx } from 'clsx'
import { DeviceScreen } from '../components/DeviceScreen'
import { ActionLog } from '../components/ActionLog'
import { RoundProgress } from '../components/RoundProgress'
import { TaskInput } from '../components/TaskInput'
import { StatusChip } from '../components/StatusChip'
import { useAgentStore } from '../store/agentStore'
import { useDevice } from '../hooks/useDevice'
import { useAgentStream } from '../hooks/useAgentStream'
import { agentApi } from '../api/client'

export function DeployPage() {
  const [appName, setAppName] = useState('linkedin')
  const [maxRounds, setMaxRounds] = useState('20')
  const [provider, setProvider] = useState('gemini')
  const [task, setTask] = useState('')
  const [running, setRunning] = useState(false)

  const {
    deviceStatus,
    sessionId,
    agentStatus,
    roundNum,
    taskComplete,
    failureReason,
    screenshotB64,
    screenshotRound,
    planSteps,
    currentStepIdx,
    logEntries,
    setSessionId,
    resetSession,
  } = useAgentStore()

  useDevice()
  useAgentStream(sessionId)

  const handleDeploy = async (submittedTask: string) => {
    if (!submittedTask.trim() || !appName.trim()) return
    setTask(submittedTask)
    setRunning(true)
    try {
      const res = await agentApi.deploy(submittedTask, appName, parseInt(maxRounds), provider)
      setSessionId(res.session_id)
    } catch (err) {
      console.error('Failed to start deploy:', err)
      setRunning(false)
    }
  }

  const handleStop = async () => {
    if (sessionId) {
      await agentApi.stop(sessionId)
      resetSession()
      setRunning(false)
    }
  }

  useEffect(() => {
    if (agentStatus === 'done' || agentStatus === 'error') {
      setRunning(false)
    }
  }, [agentStatus])

  const isRunning = running || agentStatus === 'running'

  return (
    <div className="min-h-screen bg-zinc-950 py-6 px-4">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <Link
            to="/setup"
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            Setup
          </Link>
          <h1 className="text-xl font-bold text-zinc-100">Deploy Mode</h1>
          <StatusChip status={deviceStatus} />
        </div>

        {isRunning ? (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-4">
              <div className="border border-zinc-800 rounded-xl p-4 space-y-2">
                <div className="text-xs text-zinc-500">Task</div>
                <div className="text-sm text-zinc-200">{task}</div>
              </div>

              {planSteps.length > 0 && (
                <div className="border border-zinc-800 rounded-xl p-4 space-y-2">
                  <div className="text-xs text-zinc-500 mb-2">Plan</div>
                  {planSteps.map((step, i) => (
                    <div
                      key={i}
                      className={clsx(
                        'flex items-start gap-2 text-xs py-1',
                        i === currentStepIdx ? 'text-sky-400' : i < currentStepIdx ? 'text-zinc-500' : 'text-zinc-600',
                      )}
                    >
                      {i < currentStepIdx ? (
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      ) : i === currentStepIdx ? (
                        <ArrowRight className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      ) : (
                        <Circle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      )}
                      <span className={i < currentStepIdx ? 'line-through' : ''}>{step}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="border border-zinc-800 rounded-xl p-4">
                <RoundProgress current={roundNum} max={parseInt(maxRounds)} status={agentStatus} />
              </div>

              {taskComplete && (
                <div className="flex items-center gap-2 px-3 py-2 bg-emerald-950 border border-emerald-800 rounded-lg text-emerald-300 text-xs">
                  <CheckCircle2 className="w-4 h-4" />
                  Task completed
                </div>
              )}

              {failureReason && (
                <div className="px-3 py-2 bg-red-950 border border-red-800 rounded-lg text-red-300 text-xs">
                  {failureReason}
                </div>
              )}

              <button
                onClick={handleStop}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-red-950 hover:bg-red-900 text-red-300 text-sm rounded-lg transition-colors"
              >
                <Square className="w-4 h-4" />
                Stop
              </button>
            </div>

            <div className="lg:col-span-2 space-y-4">
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/50">
                <DeviceScreen screenshotB64={screenshotB64} round={screenshotRound} />
              </div>
              <div className="border border-zinc-800 rounded-xl overflow-hidden bg-zinc-900/50">
                <ActionLog entries={logEntries} height={240} />
              </div>
            </div>
          </div>
        ) : (
          <div className="max-w-xl mx-auto space-y-4">
            <div className="border border-zinc-800 rounded-xl p-5 space-y-4">
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

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-500 mb-2">Max Rounds</label>
                  <input
                    type="number"
                    value={maxRounds}
                    onChange={(e) => setMaxRounds(e.target.value)}
                    min="1"
                    max="100"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
                  />
                </div>
                <div>
                  <label className="block text-xs text-zinc-500 mb-2">LLM Provider</label>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500"
                  >
                    <option value="gemini">Gemini 2.5 Flash</option>
                    <option value="openai">GPT-4o</option>
                    <option value="anthropic">Claude</option>
                    <option value="ollama">Ollama (local)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs text-zinc-500 mb-2">Task</label>
                <TaskInput onSubmit={handleDeploy} disabled={!deviceStatus?.connected} />
              </div>

              <p className="text-xs text-zinc-500 bg-zinc-900 rounded-lg p-3">
                Deploy mode decomposes your task into ordered sub-steps, then executes them using the knowledge base
                built during Explore runs. Progress is re-checked every 5 rounds.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
