import { useEffect, useState } from 'react'
import { deviceApi, type DeviceListEntry } from '../api/client'

export function useDeviceList() {
  const [devices, setDevices] = useState<DeviceListEntry[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let mounted = true
    deviceApi
      .list()
      .then((res) => {
        if (mounted) setDevices(res)
      })
      .catch(() => {
        if (mounted) setDevices([])
      })
      .finally(() => {
        if (mounted) setLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  return { devices, loading }
}
