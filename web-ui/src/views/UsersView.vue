<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { AppRole, AppUser } from '@/api/client'
import { fetchUsers, fetchRoles, createUser, updateUser, deleteUser } from '@/api/client'

const loading = ref(false)
const users = ref<AppUser[]>([])
const roles = ref<AppRole[]>([])

const dialogVisible = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const currentUserId = ref<number | null>(null)

const form = reactive<{
  username: string
  password: string
  email: string
  display_name: string
  is_active: boolean
  roles: string[]
}>({
  username: '',
  password: '',
  email: '',
  display_name: '',
  is_active: true,
  roles: [],
})

async function loadData() {
  loading.value = true
  try {
    const [userRes, roleRes] = await Promise.all([fetchUsers(), fetchRoles()])
    users.value = userRes.users
    roles.value = roleRes.roles
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialogMode.value = 'create'
  currentUserId.value = null
  form.username = ''
  form.password = ''
  form.email = ''
  form.display_name = ''
  form.is_active = true
  form.roles = []
  dialogVisible.value = true
}

function openEdit(row: AppUser) {
  dialogMode.value = 'edit'
  currentUserId.value = row.id
  form.username = row.username
  form.password = ''
  form.email = row.email ?? ''
  form.display_name = row.display_name ?? ''
  form.is_active = row.is_active
  form.roles = [...row.roles]
  dialogVisible.value = true
}

async function handleSubmit() {
  if (dialogMode.value === 'create') {
    await createUser({
      username: form.username,
      password: form.password,
      email: form.email || undefined,
      display_name: form.display_name || undefined,
      is_active: form.is_active,
      roles: form.roles,
    })
  } else if (dialogMode.value === 'edit' && currentUserId.value != null) {
    const payload: any = {
      email: form.email || undefined,
      display_name: form.display_name || undefined,
      is_active: form.is_active,
      roles: form.roles,
    }
    if (form.password) {
      payload.password = form.password
    }
    await updateUser(currentUserId.value, payload)
  }
  dialogVisible.value = false
  await loadData()
}

async function handleDelete(row: AppUser) {
  await deleteUser(row.id)
  await loadData()
}

const roleColors: Record<string, string> = {
  admin: '#FF7C7C',
  operator: '#2DFEFF',
  viewer: '#ffe47c',
  default: '#ffffff'
}

function getRoleStyle(role: string) {
  return {
    backgroundColor: roleColors[role] || roleColors.default,
    color: '#000000'
  }
}

onMounted(() => {
  loadData()
})
</script>

<template>
  <div>
    <el-card>
      <template #header>
        <div class="card-header">
          <span>用户管理</span>
          <el-button type="primary" size="small" @click="openCreate">新建用户</el-button>
        </div>
      </template>

      <el-table :data="users" v-loading="loading" style="width: 100%" stripe>
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="display_name" label="显示名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="160" />
        <el-table-column label="角色" min-width="160">
          <template #default="{ row }">
            <span v-for="r in row.roles" :key="r" class="cli-tag" :style="getRoleStyle(r)">
              {{ r.toUpperCase() }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="cli-tag" :style="{ backgroundColor: row.is_active ? '#7CFF7C' : '#d0d7de', color: '#000000' }">
              {{ row.is_active ? 'ACTIVE' : 'INACTIVE' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新建用户' : '编辑用户'" width="520px">
      <el-form label-width="90px">
        <el-form-item label="用户名" v-if="dialogMode === 'create'">
          <el-input v-model="form.username" autocomplete="off" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" autocomplete="new-password" />
          <div v-if="dialogMode === 'edit'" class="hint">留空则不修改密码</div>
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" autocomplete="off" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="form.email" autocomplete="off" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.roles" multiple placeholder="选择角色" style="width: 100%">
            <el-option
              v-for="r in roles"
              :key="r.id"
              :label="r.display_name || r.name"
              :value="r.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tag {
  margin-right: 4px;
}

.hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
}

.cli-tag {
  display: inline-block;
  padding: 2px 8px;
  font-family: '0xProto Nerd Font', monospace;
  font-size: 12px;
  font-weight: bold;
  margin-right: 4px;
  border-radius: 0;
}

/* 覆盖 Element Plus 表格样式，适配暗色主题 */
:deep(.el-table) {
  background-color: transparent;
  color: var(--cyber-text);
  --el-table-header-bg-color: rgba(0, 0, 0, 0.3);
  --el-table-border-color: rgba(255, 255, 255, 0.1);
  --el-table-tr-bg-color: transparent;
}

:deep(.el-table__inner-wrapper::before) {
  background-color: rgba(255, 255, 255, 0.1);
}

:deep(.el-table th.el-table__cell) {
  background-color: rgba(0, 0, 0, 0.3);
  color: var(--cyber-primary);
  font-weight: bold;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

:deep(.el-table td.el-table__cell) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

/* 斑马纹样式 */
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background-color: rgba(255, 255, 255, 0.05);
}

/* Hover 样式 */
:deep(.el-table--enable-row-hover .el-table__body tr:hover > td.el-table__cell) {
  background-color: rgba(0, 240, 255, 0.1);
}

/* Card 样式适配 */
:deep(.el-card) {
  background-color: rgba(0, 20, 40, 0.6);
  border: 1px solid rgba(0, 240, 255, 0.3);
  color: var(--cyber-text);
}

:deep(.el-card__header) {
  border-bottom: 1px solid rgba(0, 240, 255, 0.3);
}
</style>


