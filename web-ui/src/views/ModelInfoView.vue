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

<style scoped>
/* Card 样式适配 */
:deep(.el-card) {
  background-color: rgba(0, 20, 40, 0.6);
  border: 1px solid rgba(0, 240, 255, 0.3);
  color: var(--cyber-text);
}

:deep(.el-card__header) {
  border-bottom: 1px solid rgba(0, 240, 255, 0.3);
}

/* Descriptions 样式适配 */
:deep(.el-descriptions__body) {
  background-color: transparent;
  color: var(--cyber-text);
}

:deep(.el-descriptions__label) {
  background-color: rgba(0, 0, 0, 0.3) !important;
  color: var(--cyber-primary) !important;
  font-weight: bold;
}

:deep(.el-descriptions__content) {
  background-color: rgba(255, 255, 255, 0.05) !important;
  color: var(--cyber-text) !important;
}

:deep(.el-descriptions__table) {
  border-color: rgba(255, 255, 255, 0.1);
}

/* 骨架屏样式适配 */
:deep(.el-skeleton) {
  --el-skeleton-color: rgba(255, 255, 255, 0.1);
  --el-skeleton-to-color: rgba(255, 255, 255, 0.05);
}
</style>


