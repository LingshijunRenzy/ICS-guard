<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { 
  fetchTopology, 
  fetchAlerts, 
  fetchHoneypotLogs, 
  fetchModelMeta, 
  fetchUiEvents,
  type TopologyResponse,
  type AlertItem,
  type HoneypotLogItem,
  type ModelMeta,
  type UiEventItem
} from '@/api/client'

// Data Refs
const topology = ref<TopologyResponse>({ nodes: [], links: [] })
const alerts = ref<AlertItem[]>([])
const honeypotLogs = ref<HoneypotLogItem[]>([])
const modelMeta = ref<ModelMeta | null>(null)
const uiEvents = ref<UiEventItem[]>([])
const loading = ref(true)

// Stats Computed
const nodeCount = computed(() => topology.value.nodes.length)
const linkCount = computed(() => topology.value.links.length)
const onlineNodes = computed(() => topology.value.nodes.filter(n => n.status === 'online').length)
const highAlerts = computed(() => alerts.value.filter(a => a.level === 'critical' || a.level === 'high').length)
const honeypotHits = computed(() => honeypotLogs.value.length)
const systemStatus = computed(() => {
  if (highAlerts.value > 0) return 'WARNING'
  if (!modelMeta.value?.loaded) return 'INITIALIZING'
  return 'NORMAL'
})

// Fetch Data
const refreshData = async () => {
  loading.value = true
  try {
    const [topoRes, alertsRes, honeyRes, modelRes, eventsRes] = await Promise.allSettled([
      fetchTopology(),
      fetchAlerts(),
      fetchHoneypotLogs(),
      fetchModelMeta(),
      fetchUiEvents({ limit: 20 })
    ])

    if (topoRes.status === 'fulfilled') topology.value = topoRes.value
    if (alertsRes.status === 'fulfilled') alerts.value = alertsRes.value
    if (honeyRes.status === 'fulfilled') honeypotLogs.value = honeyRes.value
    if (modelRes.status === 'fulfilled') modelMeta.value = modelRes.value
    if (eventsRes.status === 'fulfilled') uiEvents.value = eventsRes.value.items
  } catch (e) {
    console.error('Failed to load dashboard data', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshData()
  // Auto refresh every 30s
  setInterval(refreshData, 30000)
})
</script>

<template>
  <div class="dashboard-container">
    <div class="bento-grid">
      <!-- Row 1: Key Metrics -->
      <div class="bento-card stat-card cyber-border">
        <div class="card-inner">
          <div class="stat-label">NETWORK NODES</div>
          <div class="stat-value">{{ nodeCount }}</div>
          <div class="stat-sub">ONLINE: <span class="highlight-green">{{ onlineNodes }}</span></div>
        </div>
        <div class="card-decoration-corner"></div>
      </div>

      <div class="bento-card stat-card cyber-border">
        <div class="card-inner">
          <div class="stat-label">ACTIVE ALERTS</div>
          <div class="stat-value" :class="{ 'text-danger': highAlerts > 0 }">{{ alerts.length }}</div>
          <div class="stat-sub">CRITICAL: <span class="highlight-red">{{ highAlerts }}</span></div>
        </div>
        <div class="card-decoration-corner"></div>
      </div>

      <div class="bento-card stat-card cyber-border">
        <div class="card-inner">
          <div class="stat-label">HONEYPOT HITS</div>
          <div class="stat-value">{{ honeypotHits }}</div>
          <div class="stat-sub">LAST 24H</div>
        </div>
        <div class="card-decoration-corner"></div>
      </div>

      <div class="bento-card stat-card cyber-border">
        <div class="card-inner">
          <div class="stat-label">SYSTEM STATUS</div>
          <div class="stat-value status-text" :class="systemStatus.toLowerCase()">{{ systemStatus }}</div>
          <div class="stat-sub">MODEL: {{ modelMeta?.loaded ? 'ACTIVE' : 'OFFLINE' }}</div>
        </div>
        <div class="card-decoration-corner"></div>
      </div>

      <!-- Row 2: Recent Alerts & Honeypot Map (Placeholder) -->
      <div class="bento-card wide-card cyber-border span-2">
        <div class="card-header">
          <span class="header-title">>> RECENT ALERTS</span>
          <span class="header-decoration">/// MONITORING</span>
        </div>
        <div class="card-content scrollable-list">
          <div v-if="alerts.length === 0" class="empty-state">NO ACTIVE ALERTS</div>
          <div v-else v-for="alert in alerts.slice(0, 5)" :key="alert.id" class="list-item alert-item" :class="alert.level">
            <span class="item-time">{{ new Date(alert.created_at).toLocaleTimeString() }}</span>
            <span class="item-level">[{{ alert.level.toUpperCase() }}]</span>
            <span class="item-msg">{{ alert.message }}</span>
          </div>
        </div>
      </div>

      <div class="bento-card wide-card cyber-border span-2">
        <div class="card-header">
          <span class="header-title">>> HONEYPOT ACTIVITY</span>
          <span class="header-decoration">/// TRAP LOGS</span>
        </div>
        <div class="card-content scrollable-list">
          <div v-if="honeypotLogs.length === 0" class="empty-state">NO ACTIVITY DETECTED</div>
          <div v-else v-for="log in honeypotLogs.slice(0, 5)" :key="log.id" class="list-item honey-item">
            <span class="item-time">{{ new Date(log.timestamp).toLocaleTimeString() }}</span>
            <span class="item-source">{{ log.src_ip }}</span>
            <span class="item-arrow">-></span>
            <span class="item-target">{{ log.dst_ip }}</span>
            <span class="item-proto">{{ log.request.split(' ')[0] || 'TCP' }}</span>
          </div>
        </div>
      </div>

      <!-- Row 3: System Events -->
      <div class="bento-card full-width-card cyber-border span-4">
        <div class="card-header">
          <span class="header-title">>> SYSTEM EVENT LOG</span>
        </div>
        <div class="card-content events-grid">
          <div v-for="(event, idx) in uiEvents.slice(0, 6)" :key="idx" class="event-pill">
            <span class="event-time">{{ new Date(event.timestamp).toLocaleTimeString() }}</span>
            <span class="event-type">{{ event.type }}</span>
            <span class="event-data">{{ JSON.stringify(event.data).slice(0, 50) }}...</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard-container {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
  background-color: var(--cyber-bg);
  color: var(--cyber-text);
  font-family: '0xProto Nerd Font', monospace;
}

.bento-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

.bento-card {
  background: rgba(10, 15, 20, 0.7);
  border: 1px solid var(--cyber-border);
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: all 0.3s ease;
}

.bento-card:hover {
  border-color: var(--cyber-primary);
  box-shadow: 0 0 15px rgba(0, 240, 255, 0.1);
}

.stat-card {
  height: 160px;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.card-inner {
  z-index: 2;
}

.stat-label {
  font-size: 0.9rem;
  color: var(--cyber-secondary);
  letter-spacing: 2px;
  margin-bottom: 10px;
}

.stat-value {
  font-size: 3rem;
  font-weight: bold;
  color: #fff;
  line-height: 1.2;
  text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
}

.status-text.normal { color: var(--cyber-success); }
.status-text.warning { color: var(--cyber-warning); }
.status-text.initializing { color: var(--cyber-secondary); }

.text-danger {
  color: var(--cyber-danger);
  text-shadow: 0 0 10px rgba(255, 0, 60, 0.5);
  animation: pulse 2s infinite;
}

.stat-sub {
  font-size: 0.8rem;
  color: var(--cyber-text-dim);
  margin-top: 5px;
}

.span-2 { grid-column: span 2; }
.span-4 { grid-column: span 4; }

.wide-card {
  height: 300px;
}

.full-width-card {
  height: 200px;
}

.card-header {
  padding: 15px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: rgba(255, 255, 255, 0.02);
}

.header-title {
  font-weight: bold;
  color: var(--cyber-primary);
}

.header-decoration {
  font-size: 0.8rem;
  color: var(--cyber-text-dim);
}

.card-content {
  flex: 1;
  padding: 15px;
  overflow: hidden;
}

.scrollable-list {
  overflow-y: auto;
}

.list-item {
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
  font-size: 0.9rem;
}

.item-time {
  color: var(--cyber-text-dim);
  margin-right: 15px;
  font-size: 0.8rem;
}

.alert-item.critical .item-level { color: var(--cyber-danger); }
.alert-item.high .item-level { color: var(--cyber-warning); }
.alert-item.info .item-level { color: var(--cyber-primary); }

.item-level {
  width: 80px;
  font-weight: bold;
}

.item-msg {
  color: #fff;
}

.honey-item {
  color: var(--cyber-secondary);
}

.item-arrow {
  margin: 0 10px;
  color: var(--cyber-text-dim);
}

.events-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 15px;
}

.event-pill {
  background: rgba(255, 255, 255, 0.05);
  padding: 10px;
  border-left: 2px solid var(--cyber-primary);
  display: flex;
  flex-direction: column;
}

.event-type {
  color: var(--cyber-primary);
  font-weight: bold;
  font-size: 0.9rem;
}

.event-data {
  font-size: 0.8rem;
  color: var(--cyber-text-dim);
  margin-top: 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-decoration-corner {
  position: absolute;
  top: 0;
  right: 0;
  width: 20px;
  height: 20px;
  border-top: 2px solid var(--cyber-primary);
  border-right: 2px solid var(--cyber-primary);
}

@keyframes pulse {
  0% { opacity: 1; }
  50% { opacity: 0.5; }
  100% { opacity: 1; }
}

.highlight-green { color: var(--cyber-success); }
.highlight-red { color: var(--cyber-danger); }

::-webkit-scrollbar {
  width: 6px;
}
::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
}
::-webkit-scrollbar-thumb {
  background: var(--cyber-border);
}
</style>
