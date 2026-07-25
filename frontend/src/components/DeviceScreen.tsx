import { Smartphone } from 'lucide-react'

interface Props {
  screenshotB64: string
  round?: number
}

export function DeviceScreen({ screenshotB64, round }: Props) {
  return (
    <div className="relative rounded-2xl overflow-hidden border border-zinc-800 bg-zinc-900 aspect-[9/19.5] max-w-xs w-full mx-auto">
      {screenshotB64 ? (
        <>
          <img
            src={`data:image/png;base64,${screenshotB64}`}
            className="w-full h-full object-contain"
            alt="Device screen"
          />
          {round !== undefined && (
            <div className="absolute top-2 right-2 bg-black/60 text-zinc-300 text-xs px-2 py-0.5 rounded-full font-mono">
              R{round}
            </div>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center justify-center h-full gap-3 text-zinc-600">
          <Smartphone className="w-10 h-10" />
          <p className="text-sm">No screenshot yet</p>
        </div>
      )}
    </div>
  )
}
