<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function goHome() {
  router.push('/')
}

function logout() {
  auth.setToken(null)
  router.push('/login')
}
</script>

<template>
  <div class="page">
    <div class="card">
      <h1>403 无权限</h1>
      <p>你已登录，但没有访问当前资源的权限。如需访问，请联系管理员调整角色或权限。</p>
      <div class="actions">
        <el-button type="primary" @click="goHome">返回首页</el-button>
        <el-button type="danger" @click="logout">退出登录</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f3f4f6;
}

.card {
  padding: 32px 40px;
  background-color: #ffffff;
  border-radius: 12px;
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.15);
  text-align: center;
}

h1 {
  margin-bottom: 12px;
}

p {
  margin-bottom: 24px;
  color: #6b7280;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>


