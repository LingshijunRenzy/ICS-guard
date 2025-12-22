<script setup lang="ts">
import { onMounted, ref } from 'vue'
import type { ModelMeta } from '@/api/client'
import { fetchModelMeta } from '@/api/client'

const loading = ref(false)
const meta = ref<ModelMeta | null>(null)

onMounted(async () => {
  loading.value = true
  try {
    meta.value = await fetchModelMeta()
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <el-card>
    <template #header>
      <span>模型与系统信息</span>
    </template>
    <el-skeleton v-if="loading" animated :rows="4" />
    <template v-else>
      <el-descriptions v-if="meta" :column="2" border>
        <el-descriptions-item label="模型已加载">
          <el-tag :type="meta.loaded ? 'success' : 'danger'">
            {{ meta.loaded ? '是' : '否' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="模型类型">
          {{ meta.model_type }}
        </el-descriptions-item>
        <el-descriptions-item label="特征数量">
          {{ meta.feature_columns.length }}
        </el-descriptions-item>
        <el-descriptions-item label="阈值配置">
          <div v-for="(v, k) in meta.thresholds" :key="k">
            {{ k }}: {{ v }}
          </div>
        </el-descriptions-item>
      </el-descriptions>
      <p v-else>后端暂未返回模型元信息。</p>
    </template>
  </el-card>
</template>

<style scoped></style>


