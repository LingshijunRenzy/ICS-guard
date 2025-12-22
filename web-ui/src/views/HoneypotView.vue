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
    <el-table v-else :data="items" size="small" border>
      <el-table-column prop="id" label="ID" width="160" />
      <el-table-column prop="src_ip" label="源 IP" width="140" />
      <el-table-column prop="dst_ip" label="目标 IP" width="140" />
      <el-table-column prop="request" label="请求" />
      <el-table-column prop="timestamp" label="时间" width="200" />
    </el-table>
  </el-card>
</template>

<style scoped></style>


