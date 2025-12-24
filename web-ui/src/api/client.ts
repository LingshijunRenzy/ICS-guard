import axios from 'axios'

import router from '@/router'

// 统一的 HTTP 客户端，所有调用应用层后端 API 都从这里走
export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// 请求拦截：自动附加 Authorization 头
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('ics_guard_token')
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截：处理 401/403
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      if (router.currentRoute.value.path !== '/login') {
        const redirect = router.currentRoute.value.fullPath
        router.push({ path: '/login', query: { redirect } })
      }
    } else if (status === 403) {
      if (router.currentRoute.value.path !== '/403') {
        router.push('/403')
      }
    }
    return Promise.reject(error)
  }
)

// ---- 基础类型（与后端 TypedDict 对齐的最小子集） ----

export interface TopologyNode {
  id: string
  name: string
  type: string
  ip?: string
  status?: string
}

export interface TopologyLink {
  id: string
  source: string
  target: string
  bandwidth?: number
  status?: string
}

export interface TopologyResponse {
  nodes: TopologyNode[]
  links: TopologyLink[]
}

export interface PolicySummary {
  id: string
  name: string
  type: string
  status: string
  priority?: number
  metadata?: Record<string, any>
}

export interface PolicyDetail {
  id: string
  name: string
  description: string
  type: string
  subtype: string
  status: string
  priority: number
  scope: {
    target_type: string
    target_identifier: string
  }
  conditions: Record<string, any>
  actions: {
    primary_action: {
      action_type: string
      action_params: Record<string, any>
    }
    secondary_actions: Array<{
      action_type: string
      action_params: Record<string, any>
    }>
  }
  monitoring?: Record<string, any>
  metadata?: Record<string, any>
}

export interface AlertItem {
  id: string
  level: string
  message: string
  created_at: string
  source?: string
}

export interface HoneypotLogItem {
  id: string
  src_ip: string
  dst_ip: string
  request: string
  timestamp: string
}

export interface ModelMeta {
  loaded: boolean
  model_type: string
  feature_columns: string[]
  thresholds: Record<string, number>
}

export interface AppUser {
  id: number
  username: string
  email?: string
  display_name?: string
  is_active: boolean
  roles: string[]
  created_at?: string
  updated_at?: string
  last_login_at?: string
}

export interface AppRole {
  id: number
  name: string
  display_name?: string
  description?: string
  is_system: boolean
}

export interface CurrentUserProfile {
  id: number
  username: string
  email?: string
  display_name?: string
  is_active: boolean
  roles: string[]
  permissions: string[]
}

export interface UiEventItem {
  type: string
  timestamp: string
  data: Record<string, any>
}

export interface AuditLog {
  id: number
  user_id: number | null
  username: string | null
  action: string
  resource: string | null
  resource_id: string | null
  payload_snapshot: string | null
  ip_address: string | null
  user_agent: string | null
  status: string
  error_message: string | null
  created_at: string
}

export interface AuditLogsResponse {
  total: number
  page: number
  per_page: number
  logs: AuditLog[]
}

// ---- 封装的 API 函数（只做最小封装，不加多余逻辑） ----

export async function fetchTopology() {
  const res = await apiClient.get<TopologyResponse>('/topology')
  return res.data
}

export async function fetchPolicies(params?: { type?: string; status?: string }) {
  const res = await apiClient.get<{ policies: PolicySummary[] }>('/policies', { params })
  return res.data.policies
}

export async function fetchPolicy(policyId: string) {
  const res = await apiClient.get<{ policy: PolicyDetail }>(`/policies/${policyId}`)
  return res.data.policy
}

export async function createPolicy(policy: Partial<PolicyDetail>) {
  const res = await apiClient.post<{ status: string; message: string; policy_id: string }>('/policies', {
    policy,
  })
  return res.data
}

export async function updatePolicy(policyId: string, policy: Partial<PolicyDetail>) {
  const res = await apiClient.put<{ status: string; message: string; policy_id: string }>(
    `/policies/${policyId}`,
    { policy }
  )
  return res.data
}

export async function deletePolicy(policyId: string) {
  const res = await apiClient.delete<{ status: string; message: string; policy_id: string }>(
    `/policies/${policyId}`
  )
  return res.data
}

export async function applyPolicy(
  policyId: string,
  targets: {
    target_nodes?: string[]
    target_links?: string[]
    target_flows?: string[]
  }
) {
  const res = await apiClient.post<{ status: string; message: string; policy_id: string }>(
    `/policies/${policyId}/apply`,
    targets
  )
  return res.data
}

export async function revokePolicy(
  policyId: string,
  targets: {
    target_nodes?: string[]
    target_links?: string[]
    target_flows?: string[]
  }
) {
  const res = await apiClient.post<{ status: string; message: string; policy_id: string }>(
    `/policies/${policyId}/revoke`,
    targets
  )
  return res.data
}

export async function fetchAlerts() {
  const res = await apiClient.get<{ alerts: Array<{
    id: string
    timestamp: string
    type: string
    severity: string
    source_ip: string
    description: string
  }> }>('/alerts')

  return res.data.alerts.map((item) => {
    const mapped: AlertItem = {
      id: item.id,
      level: item.severity ?? 'info',
      message: item.description ?? '',
      created_at: item.timestamp,
      source: item.source_ip,
    }
    return mapped
  })
}

export async function fetchHoneypotLogs() {
  const res = await apiClient.get<{
    logs: Array<{
      id: string
      timestamp: string
      source_ip: string
      request: string
      response: string
    }>
  }>('/honeypot/logs')

  return res.data.logs.map((item) => {
    const mapped: HoneypotLogItem = {
      id: item.id,
      src_ip: item.source_ip,
      dst_ip: 'HONEYPOT', // 后端目前未返回 dst_ip，这里用固定值标识目标为蜜罐
      request: item.request,
      timestamp: item.timestamp,
    }
    return mapped
  })
}

export async function fetchModelMeta() {
  const res = await apiClient.get<ModelMeta>('/model/meta')
  return res.data
}

// ---- 用户管理 ----

export async function fetchUsers() {
  const res = await apiClient.get<{ users: AppUser[] }>('/users')
  return res.data
}

export async function fetchRoles() {
  const res = await apiClient.get<{ roles: AppRole[] }>('/roles')
  return res.data
}

export async function createUser(payload: {
  username: string
  password: string
  email?: string
  display_name?: string
  is_active?: boolean
  roles?: string[]
}) {
  const res = await apiClient.post<{ user: AppUser }>('/users', payload)
  return res.data
}

export async function updateUser(userId: number, payload: Partial<{
  password: string
  email: string
  display_name: string
  is_active: boolean
  roles: string[]
}>) {
  const res = await apiClient.put<{ user: AppUser }>(`/users/${userId}`, payload)
  return res.data
}

// ---- 审计日志 ----

export async function fetchAuditLogs(params: {
  start_time?: string
  end_time?: string
  user_id?: number
  action?: string
  status?: string
  resource?: string
  page?: number
  per_page?: number
}) {
  const res = await apiClient.get<AuditLogsResponse>('/audit', { params })
  return res.data
}

export async function fetchAuditActions() {
  const res = await apiClient.get<{ actions: string[] }>('/audit/actions')
  return res.data.actions
}

export async function exportAuditLogs(params: {
  start_time?: string
  end_time?: string
  user_id?: number
  action?: string
  status?: string
  resource?: string
}) {
  const res = await apiClient.get('/audit/export', {
    params,
    responseType: 'blob',
  })
  return res.data
}

export async function deleteUser(userId: number) {
  const res = await apiClient.delete<{ status: string }>(`/users/${userId}`)
  return res.data
}

export async function fetchUiEvents(params?: { limit?: number; types?: string }) {
  const res = await apiClient.get<{ items: UiEventItem[] }>('/events', {
    params,
  })
  return res.data
}

export async function fetchCurrentUser() {
  const res = await apiClient.get<CurrentUserProfile>('/auth/me')
  return res.data
}


