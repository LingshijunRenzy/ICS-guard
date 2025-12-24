<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()

const menus = [
  { path: '/', label: '概览', name: 'home' },
  { path: '/topology', label: '拓扑视图', name: 'topology' },
  { path: '/monitor', label: '实时监控', name: 'monitor' },
  { path: '/policies', label: '策略管理', name: 'policies' },
  { path: '/alerts', label: '告警中心', name: 'alerts' },
  { path: '/honeypot', label: '蜜罐日志', name: 'honeypot' },
  { path: '/model', label: '模型与系统', name: 'model' },
  { path: '/users', label: '用户管理', name: 'users' },
  { path: '/audit', label: '审计日志', name: 'audit' },
  { path: '/automation-logs', label: '自动化日志', name: 'automation-logs' },
] as const

const menuPermissions: Record<string, string[] | undefined> = {
  '/': [],
  '/topology': ['topology:read'],
  '/monitor': ['topology:read'],
  '/policies': ['policy:read'],
  '/alerts': ['alert:read'],
  '/honeypot': ['honeypot:read'],
  '/model': ['model:read'],
  '/users': ['user:manage'],
  '/audit': ['audit:read'],
  '/automation-logs': ['event_log:read'],
}

const visibleMenus = computed(() => {
  const permsLoaded = auth.permissionsLoaded
  const hasAnyPerm = auth.permissions.length > 0

  // 权限尚未加载时，先展示全部菜单，后续由路由守卫兜底
  if (!permsLoaded) return menus.slice()

  return menus.filter((m) => {
    const required = menuPermissions[m.path]
    if (!required || required.length === 0) return true
    if (!hasAnyPerm) return false
    return required.some((p) => auth.hasPermission(p))
  })
})

const isFullScreenPage = computed(
  () =>
    route.meta?.public === true &&
    (route.path === '/login' || route.path === '/401' || route.path === '/403')
)

function handleSelect(index: string) {
  const item = visibleMenus.value.find((m) => m.path === index)
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
          <div class="layout-header-logo">ICS-GUARD // SYSTEM</div>
          <div class="layout-header-title">>> {{ route.meta.title ? String(route.meta.title).toUpperCase() : 'CONSOLE'
            }}</div>
        </div>
        <div class="layout-header-right">
          <div class="header-status">SYSTEM STATUS: <span style="color: var(--cyber-success)">NORMAL</span></div>
          <el-button type="text" @click="themeStore.toggleTheme" class="theme-toggle-btn">
            {{ themeStore.theme === 'dark' ? 'LIGHT_MODE' : 'DARK_MODE' }}
          </el-button>
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
              <el-menu-item v-for="item in visibleMenus" :key="item.path" :index="item.path">
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
  border-bottom: 1px solid var(--cyber-border-color);
    background: var(--cyber-header-bg);
  position: relative;
  z-index: 100;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.layout-header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.layout-header-logo {
  font-family: 'Orbitron', sans-serif;
  font-weight: 700;
  font-size: 20px;
    color: var(--cyber-btn-hover-text);
    background-color: var(--cyber-primary);
    padding: 2px 10px;
  letter-spacing: 2px;
  text-shadow: none;
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

.logout-btn,
.theme-toggle-btn {
  color: var(--cyber-text-main) !important;
  font-family: 'Orbitron', sans-serif;
  letter-spacing: 1px;
}

.logout-btn:hover,
.theme-toggle-btn:hover {
  text-shadow: 0 0 5px var(--cyber-secondary);
  color: var(--cyber-secondary) !important;
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
  background: var(--cyber-aside-bg);
    border-right: 1px solid var(--cyber-aside-border);
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
  border-top: 1px solid var(--cyber-aside-border);
}

.sys-info {
  font-family: 'Rajdhani', sans-serif;
  font-size: 12px;
  color: var(--cyber-text-sub);
  text-align: center;
}

.layout-main {
  padding: 20px;
  background: var(--cyber-main-bg);
  overflow-y: auto;
  /* 滚动条样式 */
  scrollbar-width: thin;
  scrollbar-color: var(--cyber-primary) var(--cyber-table-border);
}

.layout-main::-webkit-scrollbar {
  width: 6px;
}

.layout-main::-webkit-scrollbar-track {
  background: var(--cyber-table-border);
}

.layout-main::-webkit-scrollbar-thumb {
  background-color: var(--cyber-primary);
  border-radius: 3px;
}
</style>

