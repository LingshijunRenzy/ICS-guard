<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { fetchEventLogs, type EventLogItem } from '@/api/client'

const loading = ref(false)
const logs = ref<EventLogItem[]>([])
const total = ref(0)

const query = reactive({
    page: 1,
    per_page: 20,
    type: '',
    severity: '',
    resource: '',
})

const eventTypes = [
    { label: '全部类型', value: '' },
    { label: '网络状态', value: 'network_status_update' },
    { label: '流量异常', value: 'traffic_anomaly' },
    { label: '蜜罐交互', value: 'honeypot_interaction' },
    { label: '拓扑变更', value: 'topology_change' },
    { label: '流更新', value: 'flow_update' },
]

const severities = [
    { label: '全部等级', value: '' },
    { label: 'Info', value: 'info' },
    { label: 'Warning', value: 'warning' },
    { label: 'High', value: 'high' },
    { label: 'Critical', value: 'critical' },
]

async function loadData() {
    loading.value = true
    try {
        const res = await fetchEventLogs({
            page: query.page,
            per_page: query.per_page,
            type: query.type || undefined,
            severity: query.severity || undefined,
            resource: query.resource || undefined,
        })
        logs.value = res.items
        total.value = res.total
    } catch (err) {
        console.error(err)
        ElMessage.error('加载日志失败')
    } finally {
        loading.value = false
    }
}

function handleSearch() {
    query.page = 1
    loadData()
}

function handlePageChange(page: number) {
    query.page = page
    loadData()
}

function formatPayload(payload: string | null) {
    if (!payload) return '-'
    try {
        const obj = JSON.parse(payload)
        return JSON.stringify(obj, null, 2)
    } catch {
        return payload
    }
}

function getTypeClass(type: string) {
    if (type === 'traffic_anomaly') return 'cli-tag-dangerous'
    if (type === 'honeypot_interaction') return 'cli-tag-suspicious'
    if (type === 'network_status_update') return 'cli-tag-primary'
    if (type === 'flow_detection') return 'cli-tag-secondary'
    return 'cli-tag-info'
}

onMounted(() => {
    loadData()
})
</script>

<template>
    <div class="view-container">
        <div class="cyber-card">
            <div class="card-header">
                <div class="header-title">AUTOMATION LOGS // 自动化操作记录</div>
            </div>

            <div class="filter-bar">
                <el-select v-model="query.type" placeholder="事件类型" style="width: 180px" @change="handleSearch">
                    <el-option v-for="opt in eventTypes" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>

                <el-select v-model="query.severity" placeholder="严重等级" style="width: 140px" @change="handleSearch">
                    <el-option v-for="opt in severities" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>

                <el-input v-model="query.resource" placeholder="资源ID (如 flow_id)" style="width: 200px" clearable
                    @keyup.enter="handleSearch" />

                <el-button type="primary" @click="handleSearch">SEARCH</el-button>
                <el-button :icon="Refresh" circle @click="loadData" title="刷新" />
            </div>

            <el-table :data="logs" v-loading="loading" style="width: 100%" class="cyber-table">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="timestamp" label="TIME" width="180">
                    <template #default="{ row }">
                        <span class="mono-text">{{ new Date(row.timestamp).toLocaleString() }}</span>
                    </template>
                </el-table-column>
                <el-table-column prop="type" label="TYPE" width="180">
                    <template #default="{ row }">
                        <div :class="['cli-tag', getTypeClass(row.type)]">{{ row.type }}</div>
                    </template>
                </el-table-column>
                <el-table-column prop="severity" label="SEVERITY" width="100">
                    <template #default="{ row }">
                        <span :class="`severity-${row.severity}`">{{ row.severity.toUpperCase() }}</span>
                    </template>
                </el-table-column>
                <el-table-column prop="resource" label="RESOURCE" width="200" show-overflow-tooltip />
                <el-table-column prop="source" label="SOURCE" width="120" />
                <el-table-column label="PAYLOAD" min-width="300">
                    <template #default="{ row }">
                        <el-popover placement="left" :width="400" trigger="click">
                            <template #reference>
                                <el-button link type="primary" size="small">VIEW DETAILS</el-button>
                            </template>
                            <pre class="json-preview">{{ formatPayload(row.payload) }}</pre>
                        </el-popover>
                    </template>
                </el-table-column>
            </el-table>

            <div class="pagination-container">
                <el-pagination background layout="prev, pager, next" :total="total" :page-size="query.per_page"
                    :current-page="query.page" @current-change="handlePageChange" />
            </div>
        </div>
    </div>
</template>

<style scoped>
.view-container {
    padding: 20px;
    height: 100%;
    box-sizing: border-box;
    overflow: auto;
}

.cyber-card {
    background: var(--cyber-card-bg);
    border: 1px solid var(--cyber-border);
    padding: 20px;
}

.card-header {
    margin-bottom: 20px;
    border-bottom: 1px solid var(--cyber-border);
    padding-bottom: 10px;
}

.header-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 1.2rem;
    color: var(--cyber-primary);
    letter-spacing: 1px;
}

.filter-bar {
    display: flex;
    gap: 15px;
    margin-bottom: 20px;
}

.cyber-table {
    background: transparent;
    --el-table-bg-color: transparent;
    --el-table-tr-bg-color: transparent;
    --el-table-header-bg-color: rgba(0, 0, 0, 0.2);
    --el-table-border-color: var(--cyber-border);
    --el-table-text-color: var(--cyber-text-main);
    --el-table-header-text-color: var(--cyber-primary);
}

.mono-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.9em;
}

.severity-info {
    color: var(--cyber-text-main);
}

.severity-warning {
    color: var(--cyber-warning);
    font-weight: bold;
}

.severity-high {
    color: var(--cyber-danger);
    font-weight: bold;
}

.severity-critical {
    color: #ff00ff;
    font-weight: bold;
    text-shadow: 0 0 5px #ff00ff;
}

.json-preview {
    max-height: 300px;
    overflow: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85em;
    background: var(--el-bg-color);
    padding: 10px;
    border-radius: 4px;
    color: var(--el-text-color-primary);
    border: 1px solid var(--el-border-color);
}

/* CLI 风格标签：白底黑字，高对比度，类似终端反色块 */
.cli-tag {
    display: inline-block;
    padding: 2px 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: bold;
    color: #000000;
    background-color: #ffffff;
    border-radius: 0;
    margin: 0;
}

.cli-tag-primary {
    background-color: #2DFEFF;
    color: #000000;
}

.cli-tag-secondary {
    background-color: #ffe47c;
    color: #000000;
}

.cli-tag-safe {
    background-color: #7CFF7C;
    color: #000000;
}

.cli-tag-suspicious {
    background-color: #FFD27C;
    color: #000000;
}

.cli-tag-dangerous {
    background-color: #FF7C7C;
    color: #000000;
}

.cli-tag-info {
    background-color: #d0d7de;
    color: #000000;
}

.pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
}

/* 暗色模式下的分页样式适配 */
:global(.dark) .el-pagination.is-background .el-pager li:not(.is-disabled).is-active {
    background-color: var(--cyber-primary);
    color: #000;
}

:global(.dark) .el-pagination.is-background .el-pager li {
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--cyber-text-main);
}

:global(.dark) .el-pagination.is-background .btn-prev,
:global(.dark) .el-pagination.is-background .btn-next {
    background-color: rgba(255, 255, 255, 0.1);
    color: var(--cyber-text-main);
}
</style>
