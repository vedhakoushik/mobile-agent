import { useEffect, useRef } from 'react'
import { AgentWebSocket, type AgentEvent } from '../api/websocket'
import { useAgentStore } from '../store/agentStore'

export function useAgentStream(sessionId: string | null) {
  const {
    setScreenshot,
    appendLog,
    appendKbDoc,
    setAgentStatus,
    setTaskComplete,
    setFailureReason,
    setPlan,
    setRoundNum,
  } = useAgentStore()

  const wsRef = useRef<AgentWebSocket | null>(null)

  useEffect(() => {
    if (!sessionId) return

    const handler = (event: AgentEvent) => {
      switch (event.type) {
        case 'screenshot_update':
          setScreenshot(event.screenshot, event.round)
          setRoundNum(event.round)
          break
        case 'action_event':
          appendLog(event)
          break
        case 'kb_update':
          appendKbDoc(event.doc)
          break
        case 'plan_ready':
          setPlan(event.steps)
          break
        case 'status_change':
          setAgentStatus(event.status)
          if (event.task_complete !== undefined) setTaskComplete(event.task_complete)
          if (event.failure_reason) setFailureReason(event.failure_reason)
          break
        case 'error':
          setAgentStatus('error')
          break
      }
    }

    const ws = new AgentWebSocket(sessionId, handler)
    ws.connect()
    wsRef.current = ws

    return () => {
      ws.disconnect()
      wsRef.current = null
    }
  }, [sessionId])

  const stop = () => wsRef.current?.send({ type: 'stop' })
  const pause = () => wsRef.current?.send({ type: 'pause' })
  const resume = () => wsRef.current?.send({ type: 'resume' })

  return { stop, pause, resume }
}
