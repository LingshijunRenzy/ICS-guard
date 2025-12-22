<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const menus = [
  { path: '/', label: '概览', name: 'home' },
  { path: '/topology', label: '拓扑视图', name: 'topology' },
  { path: '/monitor', label: '实时监控', name: 'monitor' },
  { path: '/policies', label: '策略管理', name: 'policies' },
  { path: '/alerts', label: '告警中心', name: 'alerts' },
  { path: '/honeypot', label: '蜜罐日志', name: 'honeypot' },
  { path: '/model', label: '模型与系统', name: 'model' },
]

function handleSelect(index: string) {
  const item = menus.find((m) => m.path === index)
  if (item) {
    router.push(item.path)
  }
}
</script>

<template>
  <el-container class="layout-root">
    <el-aside width="220px" class="layout-aside">
      <div class="logo">ICS-Guard</div>
      <el-menu
        :default-active="route.path"
        class="layout-menu"
        @select="handleSelect"
      >
        <el-menu-item v-for="item in menus" :key="item.path" :index="item.path">
          {{ item.label }}
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="layout-header">
        <div class="layout-header-title">{{ route.meta.title ?? '控制台' }}</div>
      </el-header>
      <el-main class="layout-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout-root {
  width: 100%;
  height: 100vh;
}

.layout-aside {
  background-color: #001529;
  color: #fff;
  display: flex;
  flex-direction: column;
}

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.layout-menu {
  border-right: none;
  flex: 1;
}

.layout-header {
  display: flex;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid #e5e7eb;
  background-color: #fff;
}

.layout-header-title {
  font-size: 18px;
  font-weight: 500;
}

.layout-main {
  padding: 16px 24px 24px;
  background-color: #f5f7fa;
}
</style>


