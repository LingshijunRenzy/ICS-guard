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
      <header class="layout-header scanline">
        <div class="layout-header-left">
          <div class="layout-header-logo cyber-glow">ICS-GUARD // SYSTEM</div>
          <div class="layout-header-title">>> {{ route.meta.title ? route.meta.title.toUpperCase() : 'CONSOLE' }}</div>
        </div>
        <div class="layout-header-right">
          <div class="header-status">SYSTEM STATUS: <span style="color: var(--cyber-success)">NORMAL</span></div>
          <el-button type="text" @click="handleLogout" class="logout-btn">LOGOUT</el-button>
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
                <span class="menu-label">{{ item.label }}</span>
                <span class="menu-decoration"></span>
              </el-menu-item>
            </el-menu>
            <div class="aside-footer">
              <div class="sys-info">VER: 1.0.0-ALPHA</div>
            </div>
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
  background-color: var(--cyber-bg);
  overflow: hidden;
}

.layout-header {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid var(--cyber-primary);
  background: rgba(10, 14, 23, 0.9);
  position: relative;
  z-index: 100;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
}

.layout-header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.layout-header-logo {
  font-family: 'Orbitron', sans-serif;
  font-weight: 700;
  font-size: 24px;
  color: var(--cyber-primary);
  letter-spacing: 2px;
  text-shadow: 0 0 10px rgba(45, 254, 255, 0.5);
}

.layout-header-title {
  font-family: 'Rajdhani', sans-serif;
  font-size: 16px;
  color: var(--cyber-text-sub);
  letter-spacing: 1px;
}

.layout-header-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.header-status {
  font-family: 'Rajdhani', sans-serif;
  font-size: 14px;
  color: var(--cyber-text-sub);
  letter-spacing: 1px;
}

.logout-btn {
  color: var(--cyber-danger) !important;
  font-family: 'Orbitron', sans-serif;
  letter-spacing: 1px;
}

.logout-btn:hover {
  text-shadow: 0 0 5px var(--cyber-danger);
}

.layout-body {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.layout-body-container {
  height: 100%;
}

.layout-aside {
  background: rgba(10, 14, 23, 0.8);
  border-right: 1px solid rgba(45, 254, 255, 0.2);
  display: flex;
  flex-direction: column;
  backdrop-filter: blur(4px);
}

.layout-menu {
  border-right: none;
  background: transparent;
  flex: 1;
  padding-top: 20px;
}

.menu-label {
  font-family: 'Rajdhani', sans-serif;
  font-weight: 500;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.aside-footer {
  padding: 16px;
  border-top: 1px solid rgba(45, 254, 255, 0.1);
}

.sys-info {
  font-family: 'Rajdhani', sans-serif;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.3);
  text-align: center;
}

.layout-main {
  padding: 20px;
  background: transparent;
  overflow-y: auto;
  /* 滚动条样式 */
  scrollbar-width: thin;
  scrollbar-color: var(--cyber-primary) rgba(0, 0, 0, 0.3);
}

.layout-main::-webkit-scrollbar {
  width: 6px;
}

.layout-main::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.3);
}

.layout-main::-webkit-scrollbar-thumb {
  background-color: var(--cyber-primary);
  border-radius: 3px;
}
</style>

