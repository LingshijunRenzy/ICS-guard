<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

function goLogin() {
  router.push('/login')
}
</script>

<template>
  <div class="page">
    <div class="card">
      <h1>401 未认证</h1>
      <p>当前访问需要登录，请先完成身份认证。</p>
      <el-button type="primary" @click="goLogin">前往登录</el-button>
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
</style>


