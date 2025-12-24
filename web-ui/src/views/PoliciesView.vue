<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { PolicySummary, PolicyDetail, TopologyResponse } from '@/api/client'
import {
  fetchPolicies,
  fetchPolicy,
  createPolicy,
  updatePolicy,
  deletePolicy,
  applyPolicy,
  revokePolicy,
  fetchTopology,
} from '@/api/client'

// 数据状态
const loading = ref(false)
const policies = ref<PolicySummary[]>([])
const drawerVisible = ref(false)
const drawerMode = ref<'view' | 'edit' | 'create'>('view')
const currentPolicy = ref<PolicyDetail | null>(null)
const topology = ref<TopologyResponse>({ nodes: [], links: [] })

// 筛选和搜索
const filterType = ref<string>('')
const filterStatus = ref<string>('')
const searchText = ref('')

// 表单数据
const formData = ref<Partial<PolicyDetail>>({
  name: '',
  description: '',
  type: 'node',
  subtype: '',
  status: 'active',
  priority: 100,
  scope: {
    target_type: 'device',
    target_identifier: '',
  },
  conditions: {},
  actions: {
    primary_action: {
      action_type: 'allow',
      action_params: {}
    },
    secondary_actions: [],
  },
})

// 计算属性
const filteredPolicies = computed(() => {
  let result = policies.value

  if (filterType.value) {
    result = result.filter((p) => p.type === filterType.value)
  }

  if (filterStatus.value) {
    result = result.filter((p) => p.status === filterStatus.value)
  }

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    result = result.filter(
      (p) =>
        p.id.toLowerCase().includes(search) ||
        p.name.toLowerCase().includes(search)
    )
  }

  return result.sort((a, b) => (a.priority || 999) - (b.priority || 999))
})

// 加载数据
const loadPolicies = async () => {
  loading.value = true
  try {
    policies.value = await fetchPolicies({
      type: filterType.value || undefined,
      status: filterStatus.value || undefined,
    })
  } catch (e) {
    ElMessage.error('加载策略列表失败')
    console.error(e)
  } finally {
    loading.value = false
  }
}

const loadTopology = async () => {
  try {
    topology.value = await fetchTopology()
  } catch (e) {
    console.error('加载拓扑数据失败', e)
  }
}

// 打开抽屉
const openDrawer = async (mode: 'view' | 'edit' | 'create', policyId?: string) => {
  drawerMode.value = mode

  if (mode === 'create') {
    formData.value = {
      name: '',
      description: '',
      type: 'node',
      subtype: '',
      status: 'active',
      priority: 100,
      scope: {
        target_type: 'device',
        target_identifier: '',
      },
      conditions: {},
      actions: {
        primary_action: {
          action_type: 'allow',
          action_params: {}
        },
        secondary_actions: [],
      },
    }
    currentPolicy.value = null
  } else if (policyId) {
    try {
      currentPolicy.value = await fetchPolicy(policyId)
      formData.value = { ...currentPolicy.value }
    } catch (e) {
      ElMessage.error('加载策略详情失败')
      return
    }
  }

  drawerVisible.value = true
}

// 保存策略
const savePolicy = async () => {
  try {
    if (drawerMode.value === 'create') {
      await createPolicy(formData.value)
      ElMessage.success('策略创建成功')
    } else if (currentPolicy.value) {
      await updatePolicy(currentPolicy.value.id, formData.value)
      ElMessage.success('策略更新成功')
    }
    drawerVisible.value = false
    await loadPolicies()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '保存策略失败')
  }
}

// 删除策略
const handleDelete = async (policy: PolicySummary) => {
  try {
    await ElMessageBox.confirm(`确定要删除策略 "${policy.name}" 吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await deletePolicy(policy.id)
    ElMessage.success('策略已删除')
    await loadPolicies()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('删除策略失败')
    }
  }
}

// 切换状态
const toggleStatus = async (policy: PolicySummary) => {
  try {
    const newStatus = policy.status === 'active' ? 'inactive' : 'active'
    await updatePolicy(policy.id, { status: newStatus })
    ElMessage.success(`策略已${newStatus === 'active' ? '启用' : '禁用'}`)
    await loadPolicies()
  } catch (e) {
    ElMessage.error('更新策略状态失败')
  }
}

// 应用策略
const handleApply = async (policy: PolicySummary) => {
  try {
    const { value: targets } = await ElMessageBox.prompt(
      '请输入要应用的目标（JSON格式，包含 target_nodes, target_links, target_flows）',
      '应用策略',
      {
        confirmButtonText: '应用',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputValue: JSON.stringify({ target_nodes: [], target_links: [], target_flows: [] }, null, 2),
      }
    )
    const targetsObj = JSON.parse(targets)
    await applyPolicy(policy.id, targetsObj)
    ElMessage.success('策略已应用')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.message || '应用策略失败')
    }
  }
}

// 撤销策略
const handleRevoke = async (policy: PolicySummary) => {
  try {
    const { value: targets } = await ElMessageBox.prompt(
      '请输入要撤销的目标（JSON格式，包含 target_nodes, target_links, target_flows）',
      '撤销策略',
      {
        confirmButtonText: '撤销',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputValue: JSON.stringify({ target_nodes: [], target_links: [], target_flows: [] }, null, 2),
      }
    )
    const targetsObj = JSON.parse(targets)
    await revokePolicy(policy.id, targetsObj)
    ElMessage.success('策略已撤销')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.message || '撤销策略失败')
    }
  }
}

// 添加次要动作
const addSecondaryAction = () => {
  if (!formData.value.actions) {
    formData.value.actions = {
      primary_action: {
        action_type: 'allow',
        action_params: {}
      },
      secondary_actions: []
    }
  }
  if (!formData.value.actions.secondary_actions) {
    formData.value.actions.secondary_actions = []
  }
  formData.value.actions.secondary_actions.push({
    action_type: 'log',
    action_params: {
      log_level: 'info',
      log_message: '',
    }
  })
}

// 删除次要动作
const removeSecondaryAction = (index: number) => {
  if (formData.value.actions?.secondary_actions) {
    formData.value.actions.secondary_actions.splice(index, 1)
  }
}

// 初始化
onMounted(() => {
  loadPolicies()
  loadTopology()
})
</script>

<template>
  <div class="policies-container">
    <div class="page-header">
      <div class="header-left">
        <h2 class="cli-title">POLICY_MANAGEMENT</h2>
        <p class="cli-subtitle">安全策略配置与下发</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" @click="openDrawer('create')">+ 新建策略</el-button>
      </div>
    </div>

    <!-- 顶部工具栏 -->
    <el-card class="filter-card cli-card">
      <el-form :inline="true" class="filter-form">
        <el-form-item label="类型">
          <el-select v-model="filterType" placeholder="全部" clearable style="width: 150px" @change="loadPolicies">
            <el-option label="全部" value="" />
            <el-option label="节点 (Node)" value="node" />
            <el-option label="连接 (Link)" value="connection" />
            <el-option label="流 (Flow)" value="flow" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filterStatus" placeholder="全部" clearable style="width: 150px" @change="loadPolicies">
            <el-option label="全部" value="" />
            <el-option label="激活" value="active" />
            <el-option label="禁用" value="inactive" />
            <el-option label="待定" value="pending" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-input v-model="searchText" placeholder="搜索 ID 或名称" style="width: 250px" clearable />
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 策略列表 -->
    <el-card class="table-card cli-card">
      <el-table v-loading="loading" :data="filteredPolicies" style="width: 100%" class="cli-table">
        <el-table-column prop="id" label="ID" width="180" show-overflow-tooltip />
        <el-table-column prop="name" label="名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="type" label="类型" width="150">
          <template #default="{ row }">
            <el-tag :type="row.type === 'flow' ? 'danger' : row.type === 'connection' ? 'warning' : 'success'"
              effect="dark" class="cli-tag">
              {{ row.type.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : row.status === 'inactive' ? 'info' : 'warning'"
              effect="plain" class="cli-tag">
              {{ row.status.toUpperCase() }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" sortable>
          <template #default="{ row }">
            <span class="priority-value">{{ row.priority || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openDrawer('view', row.id)">查看</el-button>
            <el-button link type="primary" size="small" @click="openDrawer('edit', row.id)">编辑</el-button>
            <el-button link type="primary" size="small" @click="toggleStatus(row)">
              {{ row.status === 'active' ? '禁用' : '启用' }}
            </el-button>
            <el-button link type="primary" size="small" @click="handleApply(row)">应用</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 右侧抽屉 -->
    <el-drawer v-model="drawerVisible"
      :title="drawerMode === 'create' ? '创建策略' : drawerMode === 'edit' ? '编辑策略' : '策略详情'" direction="rtl" size="600px"
      class="policy-drawer">
      <div v-if="drawerMode === 'view' && currentPolicy" class="policy-detail">
        <div class="detail-section">
          <div class="section-title">基本信息</div>
          <div class="detail-row">
            <span class="detail-label">ID:</span>
            <span class="detail-value">{{ currentPolicy.id }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">名称:</span>
            <span class="detail-value">{{ currentPolicy.name }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">描述:</span>
            <span class="detail-value">{{ currentPolicy.description }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">类型:</span>
            <span class="detail-value">{{ currentPolicy.type }} / {{ currentPolicy.subtype }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">状态:</span>
            <span class="detail-value status-badge" :class="currentPolicy.status">
              {{ currentPolicy.status.toUpperCase() }}
            </span>
          </div>
          <div class="detail-row">
            <span class="detail-label">优先级:</span>
            <span class="detail-value">{{ currentPolicy.priority }}</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">作用域</div>
          <div class="detail-row">
            <span class="detail-label">目标类型:</span>
            <span class="detail-value">{{ currentPolicy.scope.target_type }}</span>
          </div>
          <div class="detail-row">
            <span class="detail-label">目标标识:</span>
            <span class="detail-value">{{ currentPolicy.scope.target_identifier }}</span>
          </div>
        </div>

        <div class="detail-section">
          <div class="section-title">条件</div>
          <pre class="json-preview">{{ JSON.stringify(currentPolicy.conditions, null, 2) }}</pre>
        </div>

        <div class="detail-section">
          <div class="section-title">动作</div>
          <div class="detail-row">
            <span class="detail-label">主要动作:</span>
            <span class="detail-value">{{ currentPolicy.actions.primary_action.action_type }}</span>
          </div>
          <div v-if="currentPolicy.actions.secondary_actions?.length" class="secondary-actions">
            <div class="detail-label">次要动作:</div>
            <pre class="json-preview">{{ JSON.stringify(currentPolicy.actions.secondary_actions, null, 2) }}</pre>
          </div>
        </div>

        <div class="drawer-actions">
          <el-button type="primary" @click="openDrawer('edit', currentPolicy.id)">编辑</el-button>
          <el-button @click="handleApply(currentPolicy as any)">应用</el-button>
          <el-button @click="handleRevoke(currentPolicy as any)">撤销</el-button>
          <el-button type="danger" @click="handleDelete(currentPolicy as any)">删除</el-button>
        </div>
      </div>

      <div v-else class="policy-form">
        <el-form :model="formData" label-width="120px" label-position="left">
          <!-- 基本信息 -->
          <div class="form-section">
            <div class="section-title">基本信息</div>
            <el-form-item label="名称" required>
              <el-input v-model="formData.name" placeholder="策略名称" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="formData.description" type="textarea" :rows="3" placeholder="策略描述" />
            </el-form-item>
            <el-form-item label="类型" required>
              <el-select v-model="formData.type" placeholder="选择类型" style="width: 100%">
                <el-option label="节点" value="node" />
                <el-option label="连接" value="connection" />
                <el-option label="流" value="flow" />
              </el-select>
            </el-form-item>
            <el-form-item label="子类型" required>
              <el-input v-model="formData.subtype" placeholder="例如: access_control, bandwidth_control" />
            </el-form-item>
            <el-form-item label="状态" required>
              <el-select v-model="formData.status" placeholder="选择状态" style="width: 100%">
                <el-option label="激活" value="active" />
                <el-option label="禁用" value="inactive" />
                <el-option label="待定" value="pending" />
              </el-select>
            </el-form-item>
            <el-form-item label="优先级" required>
              <el-input-number v-model="formData.priority" :min="1" :max="1000" style="width: 100%" />
              <div class="form-hint">数值越小优先级越高</div>
            </el-form-item>
          </div>

          <!-- 作用域 -->
          <div class="form-section">
            <div class="section-title">作用域</div>
            <el-form-item label="目标类型" required>
              <el-select v-model="formData.scope!.target_type" placeholder="选择目标类型" style="width: 100%">
                <el-option label="设备" value="device" />
                <el-option label="连接" value="connection" />
                <el-option label="协议" value="protocol" />
                <el-option label="IP段" value="ip_range" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标标识" required>
              <el-select v-if="formData.scope!.target_type === 'device'" v-model="formData.scope!.target_identifier"
                placeholder="选择设备" filterable style="width: 100%">
                <el-option v-for="node in topology.nodes" :key="node.id" :label="`${node.name} (${node.id})`"
                  :value="node.id" />
              </el-select>
              <el-select v-else-if="formData.scope!.target_type === 'connection'"
                v-model="formData.scope!.target_identifier" placeholder="选择连接" filterable style="width: 100%">
                <el-option v-for="link in topology.links" :key="link.id"
                  :label="`${link.id} (${link.source} -> ${link.target})`" :value="link.id" />
              </el-select>
              <el-input v-else v-model="formData.scope!.target_identifier" placeholder="输入标识符（如协议名、IP段等）" />
            </el-form-item>
          </div>

          <!-- 条件配置（根据类型动态显示） -->
          <div class="form-section">
            <div class="section-title">条件配置</div>
            <div v-if="formData.type === 'node'" class="conditions-node">
              <el-form-item label="允许IP">
                <el-input :model-value="Array.isArray((formData.conditions as any)?.allowed_ips)
                    ? (formData.conditions as any).allowed_ips.join(', ')
                    : ''
                  " placeholder="逗号分隔的IP地址，如: 192.168.1.10, 192.168.1.20" @input="
                    (val: string) => {
                      if (!formData.conditions) formData.conditions = {}
                        ; (formData.conditions as any).allowed_ips = val
                          .split(',')
                          .map((s: string) => s.trim())
                          .filter(Boolean)
                    }
                  " />
              </el-form-item>
              <el-form-item label="拒绝IP">
                <el-input :model-value="Array.isArray((formData.conditions as any)?.denied_ips)
                    ? (formData.conditions as any).denied_ips.join(', ')
                    : ''
                  " placeholder="逗号分隔的IP地址，如: 192.168.1.30" @input="
                    (val: string) => {
                      if (!formData.conditions) formData.conditions = {}
                        ; (formData.conditions as any).denied_ips = val
                          .split(',')
                          .map((s: string) => s.trim())
                          .filter(Boolean)
                    }
                  " />
              </el-form-item>
              <el-form-item label="CPU阈值 (%)">
                <el-input-number :model-value="(formData.conditions as any)?.trigger_thresholds?.cpu_usage_percent"
                  :min="0" :max="100" style="width: 100%" @update:model-value="
                    (val: number) => {
                      if (!formData.conditions) formData.conditions = {}
                      if (!(formData.conditions as any).trigger_thresholds) {
                        ; (formData.conditions as any).trigger_thresholds = {}
                      }
                      ; (formData.conditions as any).trigger_thresholds.cpu_usage_percent = val
                    }
                  " />
              </el-form-item>
              <el-form-item label="内存阈值 (%)">
                <el-input-number :model-value="(formData.conditions as any)?.trigger_thresholds?.memory_usage_percent"
                  :min="0" :max="100" style="width: 100%" @update:model-value="
                    (val: number) => {
                      if (!formData.conditions) formData.conditions = {}
                      if (!(formData.conditions as any).trigger_thresholds) {
                        ; (formData.conditions as any).trigger_thresholds = {}
                      }
                      ; (formData.conditions as any).trigger_thresholds.memory_usage_percent = val
                    }
                  " />
              </el-form-item>
            </div>
            <div v-else-if="formData.type === 'connection'" class="conditions-connection">
              <el-form-item label="允许协议">
                <el-input :model-value="Array.isArray((formData.conditions as any)?.allowed_protocols)
                    ? (formData.conditions as any).allowed_protocols.join(', ')
                    : ''
                  " placeholder="逗号分隔的协议名，如: modbus, http" @input="
                    (val: string) => {
                      if (!formData.conditions) formData.conditions = {}
                        ; (formData.conditions as any).allowed_protocols = val
                          .split(',')
                          .map((s: string) => s.trim())
                          .filter(Boolean)
                    }
                  " />
              </el-form-item>
              <el-form-item label="时间窗口">
                <div style="display: flex; gap: 10px">
                  <el-time-picker :model-value="(formData.conditions as any)?.time_window?.start_time" format="HH:mm"
                    placeholder="开始时间" style="flex: 1" @update:model-value="
                      (val: any) => {
                        if (!formData.conditions) formData.conditions = {}
                        if (!(formData.conditions as any).time_window) {
                          ; (formData.conditions as any).time_window = {}
                        }
                        ; (formData.conditions as any).time_window.start_time = val
                      }
                    " />
                  <el-time-picker :model-value="(formData.conditions as any)?.time_window?.end_time" format="HH:mm"
                    placeholder="结束时间" style="flex: 1" @update:model-value="
                      (val: any) => {
                        if (!formData.conditions) formData.conditions = {}
                        if (!(formData.conditions as any).time_window) {
                          ; (formData.conditions as any).time_window = {}
                        }
                        ; (formData.conditions as any).time_window.end_time = val
                      }
                    " />
                </div>
              </el-form-item>
            </div>
            <div v-else-if="formData.type === 'flow'" class="conditions-flow">
              <el-form-item label="功能码熵值">
                <el-input-number :model-value="(formData.conditions as any)?.trigger_thresholds?.function_code_entropy"
                  :min="0" :max="1" :step="0.1" style="width: 100%" @update:model-value="
                    (val: number) => {
                      if (!formData.conditions) formData.conditions = {}
                      if (!(formData.conditions as any).trigger_thresholds) {
                        ; (formData.conditions as any).trigger_thresholds = {}
                      }
                      ; (formData.conditions as any).trigger_thresholds.function_code_entropy = val
                    }
                  " />
              </el-form-item>
              <el-form-item label="持续时间 (秒)">
                <el-input-number :model-value="(formData.conditions as any)?.trigger_thresholds?.duration_seconds"
                  :min="0" style="width: 100%" @update:model-value="
                    (val: number) => {
                      if (!formData.conditions) formData.conditions = {}
                      if (!(formData.conditions as any).trigger_thresholds) {
                        ; (formData.conditions as any).trigger_thresholds = {}
                      }
                      ; (formData.conditions as any).trigger_thresholds.duration_seconds = val
                    }
                  " />
              </el-form-item>
              <el-form-item label="怀疑级别">
                <el-select v-model="(formData.conditions as any).suspicion_level" placeholder="选择级别"
                  style="width: 100%">
                  <el-option label="低" value="low" />
                  <el-option label="中" value="medium" />
                  <el-option label="高" value="high" />
                </el-select>
              </el-form-item>
            </div>
          </div>

          <!-- 动作配置 -->
          <div class="form-section">
            <div class="section-title">动作配置</div>
            <el-form-item label="主要动作" required>
              <el-select v-model="formData.actions!.primary_action.action_type" placeholder="选择动作" style="width: 100%">
                <el-option label="允许" value="allow" />
                <el-option label="阻止" value="block" />
                <el-option label="限流" value="throttle" />
                <el-option label="禁用" value="disable" />
                <el-option label="关闭" value="shutdown" />
                <el-option label="终止" value="terminate" />
                <el-option label="重定向" value="redirect" />
                <el-option label="告警" value="alert" />
              </el-select>
            </el-form-item>
            <el-form-item label="次要动作">
              <div v-for="(action, index) in formData.actions!.secondary_actions" :key="index"
                class="secondary-action-item">
                <el-select v-model="action.action_type" placeholder="动作类型" style="width: 150px">
                  <el-option label="日志" value="log" />
                  <el-option label="告警" value="alert" />
                  <el-option label="阻止" value="block" />
                  <el-option label="重定向" value="redirect" />
                  <el-option label="限流" value="rate_limit" />
                </el-select>
                <el-button link type="danger" @click="removeSecondaryAction(index)">删除</el-button>
              </div>
              <el-button link type="primary" @click="addSecondaryAction">+ 添加次要动作</el-button>
            </el-form-item>
          </div>

          <div class="drawer-actions">
            <el-button type="primary" @click="savePolicy">保存</el-button>
            <el-button @click="drawerVisible = false">取消</el-button>
          </div>
        </el-form>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.policies-container {
  padding: 20px;
    max-width: 1600px;
    margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left h2 {
  margin: 0;
  font-size: 24px;
  color: var(--el-text-color-primary);
}

.header-left p {
  margin: 8px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.filter-card {
  margin-bottom: 20px;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-form .el-form-item {
  margin-bottom: 0;
  margin-right: 16px;
}

.priority-value {
  font-weight: bold;
  color: var(--cyber-secondary);
}

.policy-drawer :deep(.el-drawer__header) {
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  color: var(--el-text-color-primary);
  padding: 20px;
}

.policy-drawer :deep(.el-drawer__body) {
  background: var(--el-bg-color);
    color: var(--el-text-color-primary);
  padding: 20px;
  overflow-y: auto;
}

.policy-detail,
.policy-form {
  color: var(--el-text-color-primary);
}

.detail-section,
.form-section {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 1px dashed var(--el-border-color);
}

.section-title {
  font-size: 1.1rem;
  font-weight: bold;
  color: var(--el-color-primary);
  margin-bottom: 15px;
  letter-spacing: 1px;
}

.detail-row {
  display: flex;
  margin-bottom: 12px;
  align-items: flex-start;
}

.detail-label {
  min-width: 100px;
  color: var(--el-text-color-secondary);
  font-weight: bold;
}

.detail-value {
  flex: 1;
  color: var(--el-text-color-primary);
}

.json-preview {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color);
  padding: 15px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.9rem;
  color: var(--el-text-color-regular);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.secondary-actions {
  margin-top: 15px;
}

.secondary-action-item {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
  padding: 10px;
  background: var(--el-fill-color-lighter);
    border: 1px solid var(--el-border-color);
}

.drawer-actions {
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid var(--el-border-color);
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.form-hint {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
    margin-top: 5px;
  }
  
  /* Dark mode overrides to maintain Cyberpunk style */
  :global(.dark) .policy-drawer :deep(.el-drawer__header) {
    background: rgba(10, 15, 20, 0.9);
    color: var(--cyber-text-main);
  }
  
  :global(.dark) .policy-drawer :deep(.el-drawer__body) {
    background: var(--cyber-bg);
    color: var(--cyber-text-main);
  }
  
  :global(.dark) .detail-section,
  :global(.dark) .form-section {
    border-bottom: 1px dashed rgba(255, 255, 255, 0.1);
  }
  
  :global(.dark) .section-title {
    color: var(--cyber-secondary);
  }
  
  :global(.dark) .detail-label {
    color: var(--cyber-text-sub);
  }
  
  :global(.dark) .detail-value {
    color: #fff;
  }
  
  :global(.dark) .json-preview {
    background: rgba(0, 0, 0, 0.3);
    color: var(--cyber-secondary);
  }
  
  :global(.dark) .secondary-action-item {
    background: var(--cyber-row-hover);
    border: 1px solid var(--cyber-table-border);
  }
  
  :global(.dark) .form-hint {
  color: var(--cyber-text-sub);
}

/* 修复表格斑马纹背景色 */
:deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: var(--cyber-row-hover);
}
</style>
