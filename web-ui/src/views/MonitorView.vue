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
let ws: WebSocket | null = null

function appendEvent(e: UiEventItem) {
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
          timestamp: data.timestamp,
        }
      } else if (data.type === 'flow_detection_update') {
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
        height="260" border>
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
      </el-table>
    </el-card>

    <el-card class="events-card">
      <template #header>
        <span>实时事件流（WS）</span>
      </template>
      <el-alert v-if="connecting" title="正在连接实时事件通道..." type="info" show-icon class="mb-2" />
      <div v-else>
        <el-empty v-if="events.length === 0" description="当前没有收到任何实时事件" />
        <el-table v-else :data="events.slice().reverse()" size="small" height="260" border>
          <el-table-column prop="timestamp" label="时间" width="220" />
          <el-table-column prop="type" label="事件类型" width="200" />
          <el-table-column label="详情">
            <template #default="{ row }">
              <pre class="payload">{{ JSON.stringify(row.data, null, 2) }}</pre>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.monitor-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

.events-card,
.flows-card {
  width: 100%;
}

.flow-id {
  font-family: '0xProto Nerd Font', monospace;
  font-size: 12px;
  color: var(--cyber-text);
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

