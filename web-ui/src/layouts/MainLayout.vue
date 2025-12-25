<script lang="ts">
// 使用模块级变量确保 WebSocket 单例，防止 HMR 或组件重载导致重复连接
let sharedWs: WebSocket | null = null
</script>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElNotification } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const themeStore = useThemeStore()

function getWsUrl(): string {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const host = window.location.hostname
  const port = 8766
  return `${protocol}://${host}:${port}/ui-events`
}

function connectWs() {
  // 如果已存在连接，先关闭，确保只保留一个活跃连接
  if (sharedWs) {
    sharedWs.close()
    sharedWs = null
  }

  const url = getWsUrl()
  sharedWs = new WebSocket(url)

  sharedWs.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data)
      handleGlobalNotification(msg)
    } catch (e) {
      console.error('Failed to parse WS message', e)
    }
  }

  sharedWs.onclose = () => {
    // 只有当 sharedWs 还是当前这个实例时才重连
    // 防止旧的连接关闭触发重连
    if (sharedWs === thisWs) {
      sharedWs = null
      setTimeout(connectWs, 5000)
    }
  }
  
  // 保存当前引用以便在 onclose 中比对
  const thisWs = sharedWs
}

// ---- 通知管理 ----
const activeNotifications: any[] = []
const MAX_NOTIFICATIONS = 5

function showNotification(options: any) {
  // 1. 检查并清理最早的通知
  if (activeNotifications.length >= MAX_NOTIFICATIONS) {
    const oldest = activeNotifications.shift()
    if (oldest) oldest.close()
  }

  // 2. 包装 onClose 回调以维护队列
  const userOnClose = options.onClose
  // 使用一个 holder 对象来捕获稍后生成的 instance
  const holder: { instance: any } = { instance: null }

  const newOptions = {
    ...options,
    onClose: () => {
      // 从队列中移除
      if (holder.instance) {
        const idx = activeNotifications.indexOf(holder.instance)
        if (idx !== -1) {
          activeNotifications.splice(idx, 1)
        }
      }
      // 调用用户原本的 onClose (如果有)
      if (userOnClose) userOnClose()
    }
  }

  // 3. 创建通知
  const instance = ElNotification(newOptions)
  holder.instance = instance
  activeNotifications.push(instance)
}

function handleGlobalNotification(msg: any) {
  const { type, data } = msg
  if (!type || !data) return

  const commonOptions = {
    position: 'bottom-right' as const,
    duration: 5000,
    customClass: 'compact-notification',
  }

  // 1. 自动创建策略 / 流量异常 (auto_mitigation)
  if (type === 'traffic_anomaly') {
    if (data.type === 'auto_mitigation') {
      const details = data.details || {}
      showNotification({
        ...commonOptions,
        title: '自动响应执行',
        message: `已自动创建策略 ${details.policy_id}。动作: ${details.action}，目标: ${details.target}`,
        type: 'warning',
        duration: 6000,
      })
    } else {
      showNotification({
        ...commonOptions,
        title: '流量异常警告',
        message: `检测到异常流量 ${data.flow_id}。${data.description || ''}`,
        type: 'warning',
      })
    }
  }

  // 2. 流量阻断
  else if (type === 'traffic_block') {
    showNotification({
      ...commonOptions,
      title: '流量被阻断',
      message: `Flow ${data.flow_id} 已被阻断。原因: ${data.reason || data.block_reason || '策略执行'}`,
      type: 'error',
    })
  }

  // 3. 流量重定向
  else if (type === 'traffic_redirect') {
    showNotification({
      ...commonOptions,
      title: '流量被重定向',
      message: `Flow ${data.flow_id} 已重定向至 ${data.redirect_to}。原因: ${data.reason || '策略执行'}`,
      type: 'warning',
    })
  }

  // 4. AI 检测结果 (仅高危)
  else if (type === 'flow_detection_result') {
    if (data.detect_status === 'dangerous') {
      const flow = data.flow_details || {}
      showNotification({
        ...commonOptions,
        title: '检测到高危流量',
        message: `源: ${flow.src_ip}:${flow.src_port} -> 目的: ${flow.dst_ip}:${flow.dst_port}。置信度: ${(data.prob * 100).toFixed(1)}%`,
        type: 'error',
        duration: 6000,
      })
    }
  }

  // 5. 蜜罐交互
  else if (type === 'honeypot_interaction') {
    showNotification({
      ...commonOptions,
      title: '蜜罐入侵警告',
      message: `蜜罐收到来自 ${data.source_ip} 的请求: ${data.request}`,
      type: 'error',
      duration: 6000,
    })
  }

  // 6. 节点状态变更
  else if (type === 'network_status_update') {
    const status = data.status || 'unknown'
    const nodeId = data.node_id || 'Unknown Node'

    if (status === 'online') {
      showNotification({
        ...commonOptions,
        title: '节点上线',
        message: `节点 ${nodeId} 已连接到网络。`,
        type: 'success',
        duration: 4000,
      })
    } else if (status === 'offline') {
      showNotification({
        ...commonOptions,
        title: '节点下线',
        message: `节点 ${nodeId} 已断开连接！`,
        type: 'warning',
      })
    }
  }
}

onMounted(() => {
  connectWs()
})

onBeforeUnmount(() => {
  if (sharedWs) {
    sharedWs.close()
    sharedWs = null
  }
})

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
            <el-menu :default-active="route.path" class="layout-menu" @select="handleSelect">
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

<style>
/* 全局通知样式 - 紧凑模式 */
.compact-notification {
  width: 400px !important;
  padding: 10px 15px !important;
}

.compact-notification .el-notification__title {
  font-size: 14px !important;
  margin-bottom: 5px !important;
  font-weight: 600 !important;
}

.compact-notification .el-notification__content {
  font-size: 12px !important;
  margin: 0 !important;
  line-height: 1.4 !important;

  /* 多行省略 */
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-all;
}

.compact-notification .el-notification__icon {
  height: 20px !important;
  width: 20px !important;
  font-size: 20px !important;
}

.compact-notification .el-notification__group {
  margin-left: 10px !important;
  margin-right: 0 !important;
}
</style>
