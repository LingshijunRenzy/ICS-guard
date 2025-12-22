<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { TopologyResponse } from '@/api/client'
import { fetchTopology } from '@/api/client'

const loading = ref(false)
const data = ref<TopologyResponse | null>(null)

onMounted(async () => {
    loading.value = true
    try {
        data.value = await fetchTopology()
    } finally {
        loading.value = false
    }
})
</script>

<template>
    <el-card>
        <template #header>
            <span>拓扑视图（简化版：表格占位）</span>
        </template>
        <el-skeleton v-if="loading" animated :rows="4" />
        <template v-else>
            <el-row :gutter="16">
                <el-col :span="12">
                    <h3>节点</h3>
                    <el-table :data="data?.nodes ?? []" size="small" border>
                        <el-table-column prop="id" label="ID" width="120" />
                        <el-table-column prop="name" label="名称" />
                        <el-table-column prop="type" label="类型" width="100" />
                        <el-table-column prop="status" label="状态" width="100" />
                    </el-table>
                </el-col>
                <el-col :span="12">
                    <h3>连接</h3>
                    <el-table :data="data?.links ?? []" size="small" border>
                        <el-table-column prop="id" label="ID" />
                        <el-table-column prop="source" label="源" width="120" />
                        <el-table-column prop="target" label="宿" width="120" />
                        <el-table-column prop="status" label="状态" width="100" />
                    </el-table>
                </el-col>
            </el-row>
        </template>
    </el-card>
</template>

<style scoped>
h3 {
    margin: 8px 0;
}
</style>
