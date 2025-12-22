import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

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
    meta: { title: '拓扑视图' },
    component: () => import('@/views/TopologyView.vue'),
  },
  {
    path: '/monitor',
    name: 'monitor',
    meta: { title: '实时监控' },
    component: () => import('@/views/MonitorView.vue'),
  },
  {
    path: '/policies',
    name: 'policies',
    meta: { title: '策略管理' },
    component: () => import('@/views/PoliciesView.vue'),
  },
  {
    path: '/alerts',
    name: 'alerts',
    meta: { title: '告警中心' },
    component: () => import('@/views/AlertsView.vue'),
  },
  {
    path: '/honeypot',
    name: 'honeypot',
    meta: { title: '蜜罐日志' },
    component: () => import('@/views/HoneypotView.vue'),
  },
  {
    path: '/model',
    name: 'model',
    meta: { title: '模型与系统' },
    component: () => import('@/views/ModelInfoView.vue'),
  },
  {
    path: '/users',
    name: 'users',
    meta: { title: '用户管理' },
    component: () => import('@/views/UsersView.vue'),
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

// 简单路由守卫：未登录时禁止访问受保护页面
router.beforeEach((to, _from, next) => {
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

  next()
})

export default router


