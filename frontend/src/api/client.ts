import axios from 'axios'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 10_000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg = err.response?.data?.detail ?? err.message ?? 'Unknown error'
    return Promise.reject(new Error(msg))
  },
)

// ── Types ─────────────────────────────────────────────────────────────────────

export interface DeviceStatus {
  connected: boolean
  serial: string | null
  resolution: [number, number] | null
  message: string
}

export interface SessionResponse {
  session_id: string
  message: string
}

export interface AgentStatus {
  session_id: string
  status: string
  round_num: number
  task_complete: boolean
  failure_reason: string | null
  errors: string[]
}

export interface KBDoc {
  id: string
  app_name: string
  element_sig: string
  class_name: string
  resource_id: string
  content_desc: string
  text: string
  documentation: string
  observed_result: string
  last_explored_at: string
}

export interface KBList {
  app_name: string
  count: number
  docs: KBDoc[]
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const deviceApi = {
  status: () => api.get<DeviceStatus>('/device/status').then((r) => r.data),
  screenshot: () => api.get<{ screenshot_b64: string }>('/device/screenshot').then((r) => r.data),
  tap: (x: number, y: number) => api.post('/device/tap', { x, y }),
  keyEvent: (code: number) => api.post('/device/keyevent', { code }),
}

export const agentApi = {
  explore: (app_name: string, max_rounds: number, provider: string) =>
    api.post<SessionResponse>('/agent/explore', { app_name, max_rounds, provider }).then((r) => r.data),
  deploy: (task: string, app_name: string, max_rounds: number, provider: string) =>
    api.post<SessionResponse>('/agent/deploy', { task, app_name, max_rounds, provider }).then((r) => r.data),
  status: (session_id: string) =>
    api.get<AgentStatus>(`/agent/${session_id}`).then((r) => r.data),
  stop: (session_id: string) =>
    api.delete<AgentStatus>(`/agent/${session_id}`).then((r) => r.data),
}

export const kbApi = {
  list: (app_name: string) => api.get<KBList>(`/kb/${app_name}`).then((r) => r.data),
  search: (app_name: string, q: string) =>
    api.get<KBList>(`/kb/${app_name}/search`, { params: { q } }).then((r) => r.data),
  clear: (app_name: string) => api.delete(`/kb/${app_name}`).then((r) => r.data),
}
