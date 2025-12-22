import axios from 'axios'

// 统一的 HTTP 客户端，所有调用应用层后端 API 都从这里走
export const apiClient = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

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


