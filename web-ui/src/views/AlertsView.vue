<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { AlertItem } from '@/api/client'
import { fetchAlerts } from '@/api/client'

const loading = ref(false)
const items = ref<AlertItem[]>([])

onMounted(async () => {
  loading.value = true
  try {
    items.value = await fetchAlerts()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <el-card>
    <template #header>
      <span>告警中心</span>
    </template>
    <el-skeleton v-if="loading" animated :rows="4" />
    <el-table v-else :data="items" size="small" border>
      <el-table-column prop="id" label="ID" width="180" />
      <el-table-column prop="level" label="级别" width="100" />
      <el-table-column prop="source" label="来源" width="140" />
      <el-table-column prop="message" label="描述" />
      <el-table-column prop="created_at" label="时间" width="200" />
    </el-table>
  </el-card>
</template>

<style scoped></style>


