<script setup lang="ts">
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'

import type { UiEventItem } from '@/api/client'

const connecting = ref(true)
const events = reactive<UiEventItem[]>([])
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
      if (data && data.type && data.timestamp) {
        appendEvent(data)
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
  <el-card>
    <template #header>
      <span>实时监控（WS 实时事件）</span>
    </template>
    <el-alert
      v-if="connecting"
      title="正在连接实时事件通道..."
      type="info"
      show-icon
      class="mb-2"
    />
    <div v-else>
      <el-empty v-if="events.length === 0" description="当前没有收到任何实时事件" />
      <el-table
        v-else
        :data="events.slice().reverse()"
        size="small"
        height="400"
        border
      >
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
</template>

<style scoped>
.payload {
  margin: 0;
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

