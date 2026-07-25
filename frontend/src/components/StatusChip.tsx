import { clsx } from 'clsx'
import { Wifi, WifiOff } from 'lucide-react'
import type { DeviceStatus } from '../api/client'

interface Props {
  status: DeviceStatus | null
}

export function StatusChip({ status }: Props) {
  const connected = status?.connected ?? false

  return (
    <div
      className={clsx(
        'inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border',
        connected
          ? 'bg-emerald-950 border-emerald-700 text-emerald-300'
          : 'bg-zinc-900 border-zinc-700 text-zinc-400',
      )}
    >
      {connected ? (
        <Wifi className="w-3.5 h-3.5 text-emerald-400" />
      ) : (
        <WifiOff className="w-3.5 h-3.5 text-zinc-500" />
      )}
      {connected
        ? `${status?.serial ?? 'device'} · ${status?.resolution?.[0]}×${status?.resolution?.[1]}`
        : status?.message ?? 'No device'}
    </div>
  )
}
