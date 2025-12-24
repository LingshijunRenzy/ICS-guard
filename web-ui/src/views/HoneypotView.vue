<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { HoneypotLogItem } from '@/api/client'
import { fetchHoneypotLogs } from '@/api/client'

const loading = ref(false)
const items = ref<HoneypotLogItem[]>([])

onMounted(async () => {
  loading.value = true
  try {
    items.value = await fetchHoneypotLogs()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <el-card>
    <template #header>
      <span>蜜罐日志</span>
    </template>
    <el-skeleton v-if="loading" animated :rows="4" />
    <el-table v-else :data="items" size="small" border stripe>
      <el-table-column prop="id" label="ID" width="160" />
      <el-table-column prop="src_ip" label="源 IP" width="140" />
      <el-table-column prop="dst_ip" label="目标 IP" width="140" />
      <el-table-column prop="request" label="请求" />
      <el-table-column prop="timestamp" label="时间" width="200" />
    </el-table>
  </el-card>
</template>

<style scoped>
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
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

/* 斑马纹样式 */
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background-color: rgba(255, 255, 255, 0.05);
}

/* Hover 样式 */
:deep(.el-table--enable-row-hover .el-table__body tr:hover > td.el-table__cell) {
  background-color: rgba(0, 240, 255, 0.1);
}

/* Card 样式适配 */
:deep(.el-card) {
  background-color: rgba(0, 20, 40, 0.6);
  border: 1px solid rgba(0, 240, 255, 0.3);
  color: var(--cyber-text);
}

:deep(.el-card__header) {
  border-bottom: 1px solid rgba(0, 240, 255, 0.3);
}

/* 骨架屏样式适配 */
:deep(.el-skeleton) {
  --el-skeleton-color: rgba(255, 255, 255, 0.1);
  --el-skeleton-to-color: rgba(255, 255, 255, 0.05);
}
</style>


