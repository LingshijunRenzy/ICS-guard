<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import type { UiEventItem } from '@/api/client'

const connecting = ref(true)
const events = reactive<UiEventItem[]>([])

interface UiFlow {
  flow_id: string
  src_ip?: string
  dst_ip?: string
  src_port?: number
  dst_port?: number
  protocol?: string
  detect_status?: string
  prob?: number
  decision_level?: string
  timestamp: string
  // 新增字段（根据新版API文档）
  policy_effects?: Array<{
    id: string
    name: string
    action: string
    priority: number
    matched_at: string
    result: string
    reason?: string
  }>
  redirect_to?: {
    dst_ip: string
    dst_port: number
    node_id?: string
  }
  final_dst?: {
    dst_ip: string
    dst_port: number
  }
  blocked?: boolean
  blocked_at?: string
  block_reason?: string
  path_hops?: Array<{
    node_id: string
    ip?: string
    type?: string
    entered_at?: string
    left_at?: string
  }>
}

const flows = reactive<Record<string, UiFlow>>({})

function statusClass(status?: string) {
  if (!status) return 'cli-tag-info'
  const s = status.toLowerCase()
  if (s === 'dangerous') return 'cli-tag-dangerous'
  if (s === 'suspicious') return 'cli-tag-suspicious'
  if (s === 'safe') return 'cli-tag-safe'
  return 'cli-tag-info'
}

// 格式化显示策略效果
function formatPolicyEffects(effects?: Array<any>): string {
  if (!effects || effects.length === 0) return '-'
  return effects.map(e => `${e.name}(${e.action})`).join(', ')
}
let ws: WebSocket | null = null

function formatEventContent(row: UiEventItem) {
  const type = row.type
  const data = row.data as any
  if (!data) return '-'

  if (type === 'network_status_update') {
    return `节点 ${data.node_id} 状态变更为 ${data.status?.toUpperCase()}`
  }
  if (type === 'traffic_anomaly') {
    return `流量 ${data.flow_id} (${data.src_ip} -> ${data.dst_ip}) 异常，分数: ${data.anomaly_score}。详情: ${data.details}`
  }
  if (type === 'honeypot_interaction') {
    return `蜜罐收到来自 ${data.source_ip} 的请求: ${data.request}`
  }
  if (type === 'topology_change') {
    return `拓扑变更: ${data.change_type}`
  }
  if (type === 'flow_update') {
    const f = data.flow || data
    const src = f.src_ip || f.source || f.src || '?'
    const dst = f.dst_ip || f.destination || f.dst || '?'
    const status = f.status || 'unknown'
    return `Flow ${f.id || f.flow_id} (${src} -> ${dst}) 更新，状态: ${status}`
  }
  if (type === 'flow_detection_result' || type === 'flow_detection_update') {
    return `Flow ${data.flow_id} 检测结果: ${data.detect_status} (置信度: ${(data.prob * 100).toFixed(1)}%)`
  }

  return JSON.stringify(data)
}

function getEventTypeLabel(type: string) {
  const map: Record<string, string> = {
    'network_status_update': '网络状态',
    'traffic_anomaly': '流量异常',
    'honeypot_interaction': '蜜罐交互',
    'topology_change': '拓扑变更',
    'flow_update': '流量更新',
    'flow_detection_result': '检测结果',
    'flow_detection_update': '检测更新'
  }
  return map[type] || type
}

function getEventTypeColor(type: string) {
  if (type === 'traffic_anomaly' || type === 'honeypot_interaction') return '#FF7C7C'
  if (type === 'network_status_update' || type === 'topology_change') return '#ffe47c'
  return '#d0d7de'
}

function appendEvent(e: UiEventItem) {
  // 忽略高频指标更新事件，避免淹没重要告警
  if (e.type === 'node_metrics_update') return

  events.push(e)
  if (events.length > 200) {
    events.splice(0, events.length - 200)
  }
}

function getWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.hostname
  // UI WS 服务目前默认监听 8766 端口，生产中建议通过反向代理暴露为 /ws/ui-events
  const port = 8766
  return `${protocol}://${host}:${port}/ui-events`
}

function connect() {
  const url = getWsUrl()
  ws = new WebSocket(url)
  connecting.value = true

  ws.onopen = () => {
    connecting.value = false
  }

  ws.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data) as UiEventItem
      if (!data || !data.type || !data.timestamp) return

      appendEvent(data)

      // Flow 相关事件处理
      if (data.type === 'flow_update') {
        const d = data.data || {}
        // 兼容两种结构：
        // 1) data: { flow_id, src_ip, ... }
        // 2) data: { flow: { id/flow_id, src_ip, ... } }（见 docs/api/README.md）
        const flow = (d.flow || d) as Record<string, unknown>
        const flowId = (flow.flow_id as string) || (flow.id as string)
        if (!flowId) return
        const existing = flows[flowId] || {
          flow_id: flowId,
          timestamp: data.timestamp,
        }

        // 兼容不同的字段名
        const srcIp = (flow.src_ip || flow.source || flow.src) as string | undefined
        const dstIp = (flow.dst_ip || flow.destination || flow.dst) as string | undefined

        flows[flowId] = {
          ...existing,
          src_ip: srcIp,
          dst_ip: dstIp,
          src_port: flow.src_port as number | undefined,
          dst_port: flow.dst_port as number | undefined,
          protocol: flow.protocol as string | undefined,
          detect_status: (flow.detect_status as string | undefined) ?? existing.detect_status ?? 'pending',
          // 新增字段
          policy_effects: (flow.policy_effects as any) ?? existing.policy_effects,
          redirect_to: (flow.redirect_to as any) ?? existing.redirect_to,
          final_dst: (flow.final_dst as any) ?? existing.final_dst,
          blocked: (flow.blocked as boolean | undefined) ?? existing.blocked,
          blocked_at: (flow.blocked_at as string | undefined) ?? existing.blocked_at,
          block_reason: (flow.block_reason as string | undefined) ?? existing.block_reason,
          path_hops: (flow.path_hops as any) ?? existing.path_hops,
          timestamp: data.timestamp,
        }
      } else if (data.type === 'flow_detection_result' || data.type === 'flow_detection_update') {
        const d = data.data || {}
        const flowId = d.flow_id as string
        if (!flowId) return
        const existing = flows[flowId]
        // 检测结果只用于更新已有 flow，不创建新条目
        if (!existing) return
        flows[flowId] = {
          ...existing,
          detect_status: (d.detect_status as string | undefined) ?? existing.detect_status,
          prob: typeof d.prob === 'number' ? d.prob : existing.prob,
          decision_level: (d.decision_level as string | undefined) ?? existing.decision_level,
          // 保持原始 flow timestamp，不因检测结果重排
          timestamp: existing.timestamp,
        }
      }
    } catch (err) {
      console.error('解析 WS 消息失败', err)
    }
  }

  ws.onclose = () => {
    connecting.value = false
    // 简单重连策略：1 秒后重连
    setTimeout(() => {
      connect()
    }, 1000)
  }

  ws.onerror = (err) => {
    console.error('WS 连接出错', err)
  }
}

onMounted(() => {
  connect()
})

onBeforeUnmount(() => {
  if (ws) {
    ws.close()
    ws = null
  }
})
</script>

<template>
  <div class="monitor-layout">
    <el-card class="flows-card">
      <template #header>
        <span>Flow 实时监控（含检测状态）</span>
      </template>
      <el-empty v-if="Object.keys(flows).length === 0" description="当前没有收到任何 Flow 事件" />
      <el-table v-else :data="Object.values(flows).sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))" size="small"
        style="width: 100%; height: 100%" border stripe>
        <el-table-column prop="flow_id" label="Flow ID" min-width="220">
          <template #default="{ row }">
            <div class="flow-id">{{ row.flow_id }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="timestamp" label="时间" width="200">
          <template #default="{ row }">
            <div class="mono">{{ new Date(row.timestamp).toLocaleString() }}</div>
          </template>
        </el-table-column>
        <el-table-column label="源 -> 目的" min-width="260">
          <template #default="{ row }">
            <span class="cli-tag cli-tag-primary">
              {{ row.src_ip || 'N/A' }}{{ row.src_port ? ':' + row.src_port : '' }}
            </span>
            <span class="arrow">→</span>
            <span class="cli-tag cli-tag-secondary">
              {{ row.dst_ip || 'N/A' }}{{ row.dst_port ? ':' + row.dst_port : '' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="protocol" label="协议" width="100" />
        <el-table-column label="检测状态" width="150">
          <template #default="{ row }">
            <span v-if="row.detect_status" :class="['cli-tag', statusClass(row.detect_status)]">
              {{ row.detect_status.toUpperCase() }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="得分" width="100">
          <template #default="{ row }">
            <span v-if="typeof row.prob === 'number'">{{ (row.prob * 100).toFixed(1) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="decision_level" label="决策等级" width="140" />
        <!-- 新增字段列 -->
        <el-table-column label="阻断状态" width="100">
          <template #default="{ row }">
            <span v-if="row.blocked !== undefined" :class="['cli-tag', row.blocked ? 'cli-tag-dangerous' : 'cli-tag-safe']">
              {{ row.blocked ? '已阻断' : '未阻断' }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="block_reason" label="阻断原因" width="150" />
      </el-table>
    </el-card>

    <el-card class="events-card">
      <template #header>
        <span>实时事件流（WS）</span>
      </template>
      <el-alert v-if="connecting" title="正在连接实时事件通道..." type="info" show-icon class="mb-2" />
      <div v-else class="table-wrapper">
        <el-empty v-if="events.length === 0" description="当前没有收到任何实时事件" />
        <el-table v-else :data="events.slice().reverse()" size="small" style="width: 100%; height: 100%" border stripe>
          <el-table-column label="时间" width="180">
            <template #default="{ row }">
              <div class="mono">{{ new Date(row.timestamp).toLocaleString() }}</div>
            </template>
          </el-table-column>
          <el-table-column label="事件类型" width="120">
            <template #default="{ row }">
              <span class="cli-tag" :style="{ backgroundColor: getEventTypeColor(row.type), color: '#000000' }">
                {{ getEventTypeLabel(row.type) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="内容">
            <template #default="{ row }">
              <div class="event-content" :title="JSON.stringify(row.data, null, 2)">
                {{ formatEventContent(row) }}
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.event-content {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: '0xProto Nerd Font', monospace;
  font-size: 12px;
}

/* 覆盖 Element Plus 表格样式，适配暗色主题 */
:deep(.el-table) {
  background-color: transparent;
  color: var(--cyber-text);
  --el-table-header-bg-color: rgba(0, 0, 0, 0.3);
  --el-table-border-color: rgba(255, 255, 255, 0.1);
  --el-table-tr-bg-color: transparent;
}

:deep(.el-table__inner-wrapper::before) {
  background-color: rgba(255, 255, 255, 0.1);
}

:deep(.el-table th.el-table__cell) {
  background-color: rgba(0, 0, 0, 0.3);
  color: var(--cyber-primary);
  font-weight: bold;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid var(--cyber-table-border);
}

/* 斑马纹样式 */
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background-color: var(--cyber-table-header-bg);
}

/* Hover 样式 */
:deep(.el-table--enable-row-hover .el-table__body tr:hover > td.el-table__cell) {
  background-color: var(--cyber-row-hover);
}

/* Card 样式适配 */
:deep(.el-card) {
  background-color: var(--cyber-card-bg);
  border: var(--cyber-border-primary);
  color: var(--cyber-text-main);
}

:deep(.el-card__header) {
  border-bottom: var(--cyber-border-primary);
}
.monitor-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow: hidden;
}

.events-card,
.flows-card {
  width: 100%;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

:deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.table-wrapper {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.flow-id {
  font-family: '0xProto Nerd Font', monospace;
  font-size: 12px;
  color: var(--cyber-text-main);
}

.mono {
  font-family: '0xProto Nerd Font', monospace;
  font-size: 12px;
}

/* CLI 风格标签：白底黑字，高对比度，类似终端反色块 */
.cli-tag {
  display: inline-block;
  padding: 0;
  font-family: '0xProto Nerd Font', monospace;
  font-size: 12px;
  font-weight: bold;
  color: #000000;
  background-color: #ffffff;
  border-radius: 0;
  /* CLI 风格通常是方块 */
  margin: 0;
}

/* 源 IP：青色背景 */
.cli-tag-primary {
  background-color: #2DFEFF;
  color: #000000;
  width: 100%;
  max-width: 150px;
}

/* 目的 IP：黄色背景 */
.cli-tag-secondary {
  background-color: #ffe47c;
  color: #000000;
  width: 100%;
  max-width: 150px;
}

/* 状态：安全 (绿色) */
.cli-tag-safe {
  background-color: #7CFF7C;
  color: #000000;
  padding: 0;
  width: 100%;
  max-width: 100px;
}

/* 状态：疑似 (橙色) */
.cli-tag-suspicious {
  background-color: #FFD27C;
  color: #000000;
  width: 100%;
  max-width: 100px;
}

/* 状态：危险 (红色) */
.cli-tag-dangerous {
  background-color: #FF7C7C;
  color: #000000;
  width: 100%;
  max-width: 100px;
}

/* 状态：信息/默认 (灰色) */
.cli-tag-info {
  background-color: #d0d7de;
  color: #000000;
}

.arrow {
  margin: 0 8px;
  color: var(--cyber-text-sub);
  font-family: monospace;
}
.payload {
  margin: 0;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

