import { useEffect } from 'react'
import { deviceApi } from '../api/client'
import { useAgentStore } from '../store/agentStore'

export function useDevice(pollMs = 5000) {
  const setDeviceStatus = useAgentStore((s) => s.setDeviceStatus)

  useEffect(() => {
    const fetch = () => {
      deviceApi
        .status()
        .then(setDeviceStatus)
        .catch(() => setDeviceStatus({ connected: false, serial: null, resolution: null, message: 'Unreachable' }))
    }
    fetch()
    const interval = setInterval(fetch, pollMs)
    return () => clearInterval(interval)
  }, [pollMs])
}
