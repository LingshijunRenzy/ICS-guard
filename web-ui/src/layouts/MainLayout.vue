<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const menus = [
  { path: '/', label: '概览', name: 'home' },
  { path: '/topology', label: '拓扑视图', name: 'topology' },
  { path: '/monitor', label: '实时监控', name: 'monitor' },
  { path: '/policies', label: '策略管理', name: 'policies' },
  { path: '/alerts', label: '告警中心', name: 'alerts' },
  { path: '/honeypot', label: '蜜罐日志', name: 'honeypot' },
  { path: '/model', label: '模型与系统', name: 'model' },
  { path: '/users', label: '用户管理', name: 'users' },
]

const isFullScreenPage = computed(
  () =>
    route.meta?.public === true &&
    (route.path === '/login' || route.path === '/401' || route.path === '/403')
)

function handleSelect(index: string) {
  const item = menus.find((m) => m.path === index)
  if (item) {
    router.push(item.path)
  }
}

function handleLogout() {
  auth.setToken(null)
  ElMessage.success('已退出登录')
  router.push('/login')
}
</script>

<template>
  <div class="layout-root">
    <template v-if="!isFullScreenPage">
      <header class="layout-header">
        <div class="layout-header-left">
          <div class="layout-header-logo">ICS-Guard</div>
          <div class="layout-header-title">{{ route.meta.title ?? '控制台' }}</div>
        </div>
        <div class="layout-header-right">
          <el-button type="text" @click="handleLogout">登出</el-button>
        </div>
      </header>

      <div class="layout-body">
        <el-container class="layout-body-container">
          <el-aside width="220px" class="layout-aside">
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
            <el-main class="layout-main">
              <router-view />
            </el-main>
          </el-container>
        </el-container>
      </div>
    </template>
    <template v-else>
      <router-view />
    </template>
  </div>
</template>

<style scoped>
.layout-root {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.layout-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #e5e7eb;
  background-color: #ffffff;
}

.layout-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.layout-header-logo {
  font-weight: 600;
  font-size: 18px;
}

.layout-header-title {
  font-size: 16px;
  color: #4b5563;
}

.layout-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.layout-body {
  flex: 1;
  overflow: hidden;
}

.layout-body-container {
  height: 100%;
}

.layout-aside {
  background-color: #001529;
  color: #fff;
  display: flex;
  flex-direction: column;
}

.layout-menu {
  border-right: none;
  flex: 1;
}

.layout-main {
  padding: 16px 24px 24px;
  background-color: #f5f7fa;
}
</style>

