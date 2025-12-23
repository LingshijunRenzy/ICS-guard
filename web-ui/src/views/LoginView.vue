<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { apiClient, fetchCurrentUser } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const loading = ref(false)

const form = reactive({
    username: 'admin',
    password: 'admin',
})

async function handleSubmit() {
    if (!form.username || !form.password) {
        ElMessage.error('请输入用户名和密码')
        return
    }
    loading.value = true
    try {
        const res = await apiClient.post<{
            access_token: string
            token_type: string
            expires_in: number
        }>('/auth/login', {
            username: form.username,
            password: form.password,
        })
        auth.setToken(res.data.access_token)
        // 登录成功后立即拉取当前用户权限，避免进入页面后再闪烁
        try {
            const profile = await fetchCurrentUser()
            auth.setPermissions(profile.permissions || [])
        } catch {
            // 出错时交由全局拦截器和路由守卫兜底处理
        }
        ElMessage.success('登录成功')
        const redirect = (route.query.redirect as string) || '/'
        router.push(redirect)
    } catch (e) {
        ElMessage.error('登录失败，请检查用户名或密码')
    } finally {
        loading.value = false
    }
}
</script>

<template>
    <div class="login-page">
        <div class="login-card">
            <div class="login-title">ICS-Guard 控制台</div>
            <el-form label-width="80px" @keyup.enter="handleSubmit">
                <el-form-item label="用户名">
                    <el-input v-model="form.username" autocomplete="username" />
                </el-form-item>
                <el-form-item label="密码">
                    <el-input v-model="form.password" type="password" autocomplete="current-password" />
                </el-form-item>
                <el-form-item>
                    <el-button type="primary" :loading="loading" style="width: 100%" @click="handleSubmit">
                        登录
                    </el-button>
                </el-form-item>
                <div class="login-hint">
                    默认账户：<code>admin / admin</code>
                </div>
            </el-form>
        </div>
    </div>
</template>

<style scoped>
.login-page {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #0f172a, #1f2937);
}

.login-card {
    width: 360px;
    padding: 32px 32px 24px;
    background-color: #ffffff;
    border-radius: 12px;
    box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
}

.login-title {
    font-size: 20px;
    font-weight: 600;
    text-align: center;
    margin-bottom: 24px;
}

.login-hint {
    margin-top: -8px;
    font-size: 12px;
    color: #6b7280;
    text-align: center;
}

code {
    padding: 1px 4px;
    background-color: #f3f4f6;
    border-radius: 4px;
}
</style>
