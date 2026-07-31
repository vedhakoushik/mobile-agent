import { useDeviceList } from '../hooks/useDeviceList'

interface Props {
  value: string
  onChange: (v: string) => void
}

export function DevicePicker({ value, onChange }: Props) {
  const { devices, loading } = useDeviceList()

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      disabled={loading}
      className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-200 focus:outline-none focus:border-zinc-500 disabled:opacity-50"
    >
      <option value="">Auto (any idle device)</option>
      {devices.map((d) => (
        <option key={d.serial} value={d.serial}>
          {d.serial}
          {d.busy ? ' (busy)' : ''}
        </option>
      ))}
    </select>
  )
}
