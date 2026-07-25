import { Link } from 'react-router-dom'
import { Smartphone, Database, ChevronRight } from 'lucide-react'
import { StatusChip } from '../components/StatusChip'
import { useAgentStore } from '../store/agentStore'
import { useDevice } from '../hooks/useDevice'

export function SetupPage() {
  const { deviceStatus } = useAgentStore()
  useDevice(4000)

  return (
    <div className="max-w-2xl mx-auto py-12 px-4 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-zinc-100">Setup</h1>
        <p className="text-zinc-500 text-sm mt-1">Verify your device and environment before running the agent.</p>
      </div>

      {/* Device status */}
      <div className="border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Smartphone className="w-5 h-5 text-zinc-400" />
            <div>
              <div className="text-sm font-medium text-zinc-200">Android Device</div>
              <div className="text-xs text-zinc-500">Connected via ADB</div>
            </div>
          </div>
          <StatusChip status={deviceStatus} />
        </div>

        {deviceStatus?.connected && (
          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-zinc-800">
            <div>
              <div className="text-xs text-zinc-500">Serial</div>
              <div className="text-sm font-mono text-zinc-300">{deviceStatus.serial}</div>
            </div>
            <div>
              <div className="text-xs text-zinc-500">Resolution</div>
              <div className="text-sm font-mono text-zinc-300">
                {deviceStatus.resolution?.[0]}×{deviceStatus.resolution?.[1]}
              </div>
            </div>
          </div>
        )}

        {!deviceStatus?.connected && (
          <div className="text-xs text-zinc-500 bg-zinc-900 rounded-lg p-3">
            Make sure USB debugging is enabled on your device and <code className="text-sky-400">adb devices</code> shows it connected.
            The backend polls every 5 seconds automatically.
          </div>
        )}
      </div>

      {/* Instructions */}
      <div className="border border-zinc-800 rounded-xl p-5 space-y-3">
        <div className="flex items-center gap-3">
          <Database className="w-5 h-5 text-zinc-400" />
          <div className="text-sm font-medium text-zinc-200">Knowledge Base</div>
        </div>
        <p className="text-xs text-zinc-500">
          The KB stores per-element documentation gathered during Explore runs. It persists across sessions via ChromaDB (cosine similarity search).
          Each app gets its own namespace — documented behaviors transfer semantically between similar apps.
        </p>
      </div>

      {/* Environment */}
      <div className="border border-zinc-800 rounded-xl p-5 space-y-3">
        <div className="text-sm font-medium text-zinc-200">Environment</div>
        <div className="space-y-1.5 text-xs font-mono">
          {[
            ['LLM_PROVIDER', 'gemini (default)'],
            ['GEMINI_API_KEY', '…set in .env…'],
            ['CHROMA_HOST', 'chromadb (docker) or localhost'],
            ['ANDROID_SERIAL', 'auto-detect or emulator-5554'],
          ].map(([k, v]) => (
            <div key={k} className="flex gap-3">
              <span className="text-sky-400 w-36 shrink-0">{k}</span>
              <span className="text-zinc-500">{v}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Navigate */}
      <div className="flex gap-3">
        <Link
          to="/explore"
          className="flex-1 flex items-center justify-between px-4 py-3 border border-zinc-700 hover:border-zinc-500 rounded-xl text-sm text-zinc-300 hover:text-zinc-100 transition-colors"
        >
          <span>Explore Mode</span>
          <ChevronRight className="w-4 h-4" />
        </Link>
        <Link
          to="/deploy"
          className="flex-1 flex items-center justify-between px-4 py-3 border border-zinc-700 hover:border-zinc-500 rounded-xl text-sm text-zinc-300 hover:text-zinc-100 transition-colors"
        >
          <span>Deploy Mode</span>
          <ChevronRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  )
}
