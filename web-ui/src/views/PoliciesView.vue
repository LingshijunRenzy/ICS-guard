<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { PolicySummary } from '@/api/client'
import { fetchPolicies } from '@/api/client'

const loading = ref(false)
const items = ref<PolicySummary[]>([])

onMounted(async () => {
  loading.value = true
  try {
    items.value = await fetchPolicies()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <el-card>
    <template #header>
      <span>策略管理（只读列表占位）</span>
    </template>
    <el-skeleton v-if="loading" animated :rows="4" />
    <el-table v-else :data="items" size="small" border>
      <el-table-column prop="id" label="ID" width="160" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="type" label="类型" width="120" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="priority" label="优先级" width="100" />
    </el-table>
  </el-card>
</template>

<style scoped></style>


