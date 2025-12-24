import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { fetchCurrentUser } from '@/api/client'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    meta: { title: '概览' },
    component: () => import('@/views/HomeView.vue'),
  },
  {
    path: '/topology',
    name: 'topology',
    meta: { title: '拓扑视图', requiredPermissions: ['topology:read'] },
    component: () => import('@/views/TopologyView.vue'),
  },
  {
    path: '/monitor',
    name: 'monitor',
    meta: { title: '实时监控', requiredPermissions: ['topology:read'] },
    component: () => import('@/views/MonitorView.vue'),
  },
  {
    path: '/policies',
    name: 'policies',
    meta: { title: '策略管理', requiredPermissions: ['policy:read'] },
    component: () => import('@/views/PoliciesView.vue'),
  },
  {
    path: '/alerts',
    name: 'alerts',
    meta: { title: '告警中心', requiredPermissions: ['alert:read'] },
    component: () => import('@/views/AlertsView.vue'),
  },
  {
    path: '/honeypot',
    name: 'honeypot',
    meta: { title: '蜜罐日志', requiredPermissions: ['honeypot:read'] },
    component: () => import('@/views/HoneypotView.vue'),
  },
  {
    path: '/model',
    name: 'model',
    meta: { title: '模型与系统', requiredPermissions: ['model:read'] },
    component: () => import('@/views/ModelInfoView.vue'),
  },
  {
    path: '/users',
    name: 'users',
    meta: { title: '用户管理', requiredPermissions: ['user:manage'] },
    component: () => import('@/views/UsersView.vue'),
  },
  {
    path: '/audit',
    name: 'audit',
    meta: { title: '审计日志', requiredPermissions: ['audit:read'] },
    component: () => import('@/views/AuditView.vue'),
  },
  {
    path: '/login',
    name: 'login',
    meta: { title: '登录', public: true },
    component: () => import('@/views/LoginView.vue'),
  },
  {
    path: '/401',
    name: 'unauthorized',
    meta: { title: '未认证', public: true },
    component: () => import('@/views/UnauthorizedView.vue'),
  },
  {
    path: '/403',
    name: 'forbidden',
    meta: { title: '无权限', public: true },
    component: () => import('@/views/ForbiddenView.vue'),
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  // 与 Vite base=/ui/ 对齐，前端路由实际挂载在 /ui 下
  history: createWebHistory('/ui/'),
  routes,
})

// 路由守卫：未登录禁止访问受保护页面，并基于权限做路由级 RBAC
router.beforeEach(async (to, _from, next) => {
  const isPublic = to.meta?.public === true
  const token = localStorage.getItem('ics_guard_token')

  if (isPublic) {
    next()
    return
  }

  if (!token) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  const auth = useAuthStore()

  // 确保 store 中的 token 与 localStorage 同步
  if (!auth.isAuthenticated) {
    auth.setToken(token)
  }

  // 首次需要时加载当前用户权限
  if (!auth.permissionsLoaded) {
    try {
      const profile = await fetchCurrentUser()
      auth.setPermissions(profile.permissions || [])
    } catch {
      // 失败时交给全局 axios 拦截器处理（可能跳转到 401/403 或登录）
    }
  }

  const required = (to.meta?.requiredPermissions as string[] | undefined) || []
  if (required.length > 0) {
    const allowed = required.some((p) => auth.hasPermission(p))
    if (!allowed) {
      next('/403')
      return
    }
  }

  next()
})

export default router


