<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Search, Refresh, View } from '@element-plus/icons-vue'
import {
    fetchAuditLogs,
    fetchAuditActions,
    fetchAuditResources,
    fetchUsers,
    exportAuditLogs,
    type AuditLog,
    type AppUser
} from '@/api/client'
import dayjs from 'dayjs'

const loading = ref(false)
const logs = ref<AuditLog[]>([])
const total = ref(0)
const actions = ref<string[]>([])
const resources = ref<string[]>([])
const users = ref<AppUser[]>([])

const filter = reactive({
    start_time: '',
    end_time: '',
    action: '',
    status: '',
    resource: '',
    user_id: undefined as number | undefined,
    page: 1,
    per_page: 20
})

const timeRange = ref<[string, string] | null>(null)

async function loadActions() {
    try {
        actions.value = await fetchAuditActions()
    } catch (err) {
        console.error('Failed to load audit actions', err)
    }
}

async function loadResources() {
    try {
        resources.value = await fetchAuditResources()
    } catch (err) {
        console.error('Failed to load audit resources', err)
    }
}

async function loadUsers() {
    try {
        const res = await fetchUsers()
        users.value = res.users
    } catch (err) {
        console.error('Failed to load users', err)
    }
}

async function loadLogs() {
    loading.value = true
    try {
        if (timeRange.value) {
            filter.start_time = timeRange.value[0]
            filter.end_time = timeRange.value[1]
        } else {
            filter.start_time = ''
            filter.end_time = ''
        }
        const res = await fetchAuditLogs(filter)
        logs.value = res.logs
        total.value = res.total
    } catch (err) {
        ElMessage.error('获取审计日志失败')
    } finally {
        loading.value = false
    }
}

function handleFilter() {
    filter.page = 1
    loadLogs()
}

function handleReset() {
    timeRange.value = null
    filter.action = ''
    filter.status = ''
    filter.resource = ''
    filter.user_id = undefined
    filter.page = 1
    loadLogs()
}

async function handleExport() {
    try {
        const blob = await exportAuditLogs({
            start_time: timeRange.value ? timeRange.value[0] : undefined,
            end_time: timeRange.value ? timeRange.value[1] : undefined,
            action: filter.action || undefined,
            status: filter.status || undefined,
            resource: filter.resource || undefined,
            user_id: filter.user_id
        })
        const url = window.URL.createObjectURL(new Blob([blob]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', `audit_logs_${dayjs().format('YYYYMMDD_HHmmss')}.csv`)
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    } catch (err) {
        ElMessage.error('导出失败')
    }
}

const selectedLog = ref<AuditLog | null>(null)
const detailVisible = ref(false)

function showDetail(row: AuditLog) {
    selectedLog.value = row
    detailVisible.value = true
}

function getActionType(action: string) {
    if (action.includes('DELETE') || action.includes('STOP') || action.includes('DISABLE')) return 'danger'
    if (action.includes('CREATE') || action.includes('START') || action.includes('ENABLE')) return 'success'
    if (action.includes('UPDATE') || action.includes('APPLY')) return 'warning'
    return 'info'
}

onMounted(() => {
    loadActions()
    loadResources()
    loadUsers()
    loadLogs()
})
</script>

<template>
    <div class="audit-container">
        <div class="page-header">
            <div class="header-left">
                <h2 class="cli-title">SYSTEM_AUDIT_LOGS</h2>
                <p class="cli-subtitle">系统操作审计与追溯</p>
            </div>
            <div class="header-actions">
                <el-button type="primary" :icon="Download" @click="handleExport">导出日志 (CSV)</el-button>
            </div>
        </div>

        <!-- 过滤器 -->
        <el-card class="filter-card cli-card">
            <el-form :inline="true" :model="filter" class="filter-form">
                <el-form-item label="时间范围">
                    <el-date-picker v-model="timeRange" type="datetimerange" range-separator="至"
                        start-placeholder="开始时间" end-placeholder="结束时间" value-format="YYYY-MM-DDTHH:mm:ss" :shortcuts="[
                            { text: '最近1小时', value: () => [dayjs().subtract(1, 'hour').toISOString(), dayjs().toISOString()] },
                            { text: '最近24小时', value: () => [dayjs().subtract(24, 'hour').toISOString(), dayjs().toISOString()] },
                            { text: '最近7天', value: () => [dayjs().subtract(7, 'day').toISOString(), dayjs().toISOString()] }
                        ]" />
                </el-form-item>
                <el-form-item label="操作类型">
                    <el-select v-model="filter.action" placeholder="全部" clearable style="width: 180px">
                        <el-option v-for="act in actions" :key="act" :label="act" :value="act" />
                    </el-select>
                </el-form-item>
                <el-form-item label="资源类型">
                    <el-select v-model="filter.resource" placeholder="全部" clearable style="width: 150px">
                        <el-option v-for="res in resources" :key="res" :label="res" :value="res" />
                    </el-select>
                </el-form-item>
                <el-form-item label="用户">
                    <el-select v-model="filter.user_id" placeholder="全部" clearable style="width: 150px">
                        <el-option v-for="u in users" :key="u.id" :label="u.username" :value="u.id" />
                    </el-select>
                </el-form-item>
                <el-form-item label="状态">
                    <el-select v-model="filter.status" placeholder="全部" clearable style="width: 120px">
                        <el-option label="成功" value="success" />
                        <el-option label="失败" value="failure" />
                    </el-select>
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" :icon="Search" @click="handleFilter">查询</el-button>
                    <el-button :icon="Refresh" @click="handleReset">重置</el-button>
                </el-form-item>
            </el-form>
        </el-card>

        <!-- 表格 -->
        <el-card class="table-card cli-card">
            <el-table v-loading="loading" :data="logs" style="width: 100%" class="cli-table">
                <el-table-column prop="created_at" label="时间" width="180">
                    <template #default="{ row }">
                        {{ dayjs(row.created_at).format('YYYY-MM-DD HH:mm:ss') }}
                    </template>
                </el-table-column>
                <el-table-column prop="username" label="用户" width="120">
                    <template #default="{ row }">
                        <span class="cli-text-primary">{{ row.username || 'System' }}</span>
                    </template>
                </el-table-column>
                <el-table-column prop="action" label="操作" min-width="150">
                    <template #default="{ row }">
                        <el-tag :type="getActionType(row.action)" effect="dark" class="cli-tag">
                            {{ row.action }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column prop="resource" label="资源" width="120">
                    <template #default="{ row }">
                        <span v-if="row.resource" class="cli-tag-info">{{ row.resource }}</span>
                        <span v-else>-</span>
                    </template>
                </el-table-column>
                <el-table-column prop="resource_id" label="资源ID" min-width="200" show-overflow-tooltip />
                <el-table-column prop="ip_address" label="IP地址" width="140" />
                <el-table-column prop="status" label="状态" width="100">
                    <template #default="{ row }">
                        <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                            {{ row.status === 'success' ? '成功' : '失败' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="100" fixed="right">
                    <template #default="{ row }">
                        <el-button link type="primary" :icon="View" @click="showDetail(row)">详情</el-button>
                    </template>
                </el-table-column>
            </el-table>

            <div class="pagination-container">
                <el-pagination v-model:current-page="filter.page" v-model:page-size="filter.per_page" :total="total"
                    :page-sizes="[20, 50, 100]" layout="total, sizes, prev, pager, next" @size-change="handleFilter"
                    @current-change="loadLogs" />
            </div>
        </el-card>

        <!-- 详情弹窗 -->
        <el-dialog v-model="detailVisible" title="审计日志详情" width="600px" class="cli-dialog">
            <div v-if="selectedLog" class="log-detail">
                <div class="detail-item">
                    <span class="label">操作用户:</span>
                    <span class="value">{{ selectedLog.username }} (ID: {{ selectedLog.user_id }})</span>
                </div>
                <div class="detail-item">
                    <span class="label">User Agent:</span>
                    <span class="value">{{ selectedLog.user_agent }}</span>
                </div>
                <div class="detail-item" v-if="selectedLog.error_message">
                    <span class="label">错误信息:</span>
                    <span class="value cli-text-danger">{{ selectedLog.error_message }}</span>
                </div>
                <div class="detail-item full-width">
                    <span class="label">Payload Snapshot:</span>
                    <pre class="cli-code-block">{{ selectedLog.payload_snapshot ?
                        JSON.stringify(JSON.parse(selectedLog.payload_snapshot), null, 2) : 'None' }}</pre>
                </div>
            </div>
        </el-dialog>
    </div>
</template>

<style scoped>
.audit-container {
    padding: 20px;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
}

.filter-card {
    margin-bottom: 20px;
}

.pagination-container {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
}

.log-detail {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
}

.detail-item {
    width: calc(50% - 10px);
    display: flex;
    flex-direction: column;
}

.detail-item.full-width {
    width: 100%;
}

.detail-item .label {
    font-size: 12px;
    color: var(--el-text-color-secondary);
    margin-bottom: 5px;
}

.detail-item .value {
    font-family: 'Courier New', Courier, monospace;
}

:deep(.el-range-editor.el-input__inner) {
    background-color: var(--cyber-input-bg) !important;
}
</style>
