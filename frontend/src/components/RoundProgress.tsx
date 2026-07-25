interface Props {
  current: number
  max: number
  status: string
}

const STATUS_COLOR: Record<string, string> = {
  running: '#22d3ee',
  done:    '#4ade80',
  error:   '#f87171',
  paused:  '#facc15',
  idle:    '#52525b',
}

export function RoundProgress({ current, max, status }: Props) {
  const pct = max > 0 ? Math.min((current / max) * 100, 100) : 0
  const color = STATUS_COLOR[status] ?? '#52525b'

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-zinc-400">
        <span className="capitalize font-medium" style={{ color }}>{status}</span>
        <span className="font-mono">{current} / {max}</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}
