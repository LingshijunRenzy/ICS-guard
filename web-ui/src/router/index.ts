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
]

const router = createRouter({
  // 与 Vite base=/ui/ 对齐，前端路由实际挂载在 /ui 下
  history: createWebHistory('/ui/'),
  routes,
})

export default router


