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

// ---- 封装的 API 函数（只做最小封装，不加多余逻辑） ----

export async function fetchTopology() {
  const res = await apiClient.get<TopologyResponse>('/topology')
  return res.data
}

export async function fetchPolicies() {
  const res = await apiClient.get<PolicySummary[]>('/policies')
  return res.data
}

export async function fetchAlerts() {
  const res = await apiClient.get<AlertItem[]>('/alerts')
  return res.data
}

export async function fetchHoneypotLogs() {
  const res = await apiClient.get<HoneypotLogItem[]>('/honeypot/logs')
  return res.data
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

export async function deleteUser(userId: number) {
  const res = await apiClient.delete<{ status: string }>(`/users/${userId}`)
  return res.data
}


