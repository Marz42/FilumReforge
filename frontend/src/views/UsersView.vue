<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createUser, listUsers, updateUser } from '@/api/users'
import type { User, UserRole, UserStatus } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

const ROLE_LABELS: Record<UserRole, string> = {
  admin: '管理员',
  hr: 'HR',
  employee: '员工',
}

const STATUS_LABELS: Record<UserStatus, string> = {
  active: '启用',
  inactive: '未启用',
  suspended: '停用',
  offboarded: '已离职',
}

const STATUS_TAG_TYPES: Record<UserStatus, '' | 'success' | 'info' | 'warning' | 'danger'> = {
  active: 'success',
  inactive: 'info',
  suspended: 'warning',
  offboarded: 'danger',
}

const ROLE_OPTIONS: Array<{ label: string; value: UserRole }> = [
  { label: '员工', value: 'employee' },
  { label: 'HR', value: 'hr' },
  { label: '管理员', value: 'admin' },
]

const STATUS_OPTIONS: Array<{ label: string; value: UserStatus }> = [
  { label: '启用', value: 'active' },
  { label: '未启用', value: 'inactive' },
  { label: '停用', value: 'suspended' },
  { label: '已离职', value: 'offboarded' },
]

const loading = ref(false)
const createSubmitting = ref(false)
const editSubmitting = ref(false)
const createDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingUserId = ref('')
const users = ref<User[]>([])

const createForm = reactive({
  email: '',
  password: '',
  role: 'employee' as UserRole,
  status: 'active' as UserStatus,
})

const editForm = reactive({
  email: '',
  password: '',
  role: 'employee' as UserRole,
  status: 'active' as UserStatus,
})

const activeUserCount = computed(() => users.value.filter((user) => user.status === 'active').length)
const managementUserCount = computed(
  () => users.value.filter((user) => user.role === 'admin' || user.role === 'hr').length,
)
const inactiveUserCount = computed(() => users.value.filter((user) => user.status !== 'active').length)

function resetCreateForm(): void {
  createForm.email = ''
  createForm.password = ''
  createForm.role = 'employee'
  createForm.status = 'active'
}

function resetEditForm(): void {
  editingUserId.value = ''
  editForm.email = ''
  editForm.password = ''
  editForm.role = 'employee'
  editForm.status = 'active'
}

function openEditDialog(user: User): void {
  editingUserId.value = user.id
  editForm.email = user.email
  editForm.password = ''
  editForm.role = user.role
  editForm.status = user.status
  editDialogVisible.value = true
}

async function loadUsers(): Promise<void> {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleCreate(): Promise<void> {
  createSubmitting.value = true
  try {
    await createUser({
      email: createForm.email.trim(),
      password: createForm.password,
      role: createForm.role,
      status: createForm.status,
    })
    ElMessage.success('用户已创建')
    createDialogVisible.value = false
    resetCreateForm()
    await loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    createSubmitting.value = false
  }
}

async function handleUpdate(): Promise<void> {
  if (!editingUserId.value) {
    return
  }

  editSubmitting.value = true
  try {
    await updateUser(editingUserId.value, {
      email: editForm.email.trim(),
      password: editForm.password.trim() || undefined,
      role: editForm.role,
      status: editForm.status,
    })
    ElMessage.success('用户已更新')
    editDialogVisible.value = false
    resetEditForm()
    await loadUsers()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    editSubmitting.value = false
  }
}

onMounted(() => {
  void loadUsers()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="16" class="page__summary">
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <div class="summary-card">
            <span>用户总数</span>
            <strong>{{ users.length }}</strong>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <div class="summary-card">
            <span>启用账号</span>
            <strong>{{ activeUserCount }}</strong>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="8">
        <el-card shadow="never">
          <div class="summary-card">
            <span>管理角色 / 非启用</span>
            <strong>{{ managementUserCount }} / {{ inactiveUserCount }}</strong>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" v-loading="loading">
      <template #header>
        <div class="page__header">
          <div>
            <h3>用户管理</h3>
            <p>直接管理 `/users` 接口对应的账号、角色与状态。</p>
          </div>
          <el-button type="primary" @click="createDialogVisible = true">新建用户</el-button>
        </div>
      </template>

      <el-table :data="users" stripe>
        <el-table-column prop="email" label="邮箱" min-width="240" />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }: { row: User }">
            {{ ROLE_LABELS[row.role] }}
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="120">
          <template #default="{ row }: { row: User }">
            <el-tag :type="STATUS_TAG_TYPES[row.status]">
              {{ STATUS_LABELS[row.status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" min-width="180">
          <template #default="{ row }: { row: User }">
            {{ formatDateTime(row.last_login_at) }}
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }: { row: User }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }: { row: User }">
            <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="createDialogVisible"
      title="新建用户"
      width="520px"
      :teleported="false"
      @closed="resetCreateForm"
    >
      <el-form label-position="top">
        <el-form-item label="邮箱">
          <el-input v-model="createForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item label="初始密码">
          <el-input
            v-model="createForm.password"
            type="password"
            show-password
            placeholder="请输入初始密码"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createForm.role">
            <el-option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="createForm.status">
            <el-option
              v-for="option in STATUS_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="handleCreate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="editDialogVisible"
      title="编辑用户"
      width="520px"
      :teleported="false"
      @closed="resetEditForm"
    >
      <el-form label-position="top">
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" placeholder="修改邮箱" />
        </el-form-item>
        <el-form-item label="重置密码">
          <el-input
            v-model="editForm.password"
            type="password"
            show-password
            placeholder="留空则不修改密码"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role">
            <el-option
              v-for="option in ROLE_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status">
            <el-option
              v-for="option in STATUS_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="handleUpdate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page__summary {
  margin-bottom: 4px;
}

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__header h3 {
  margin: 0;
}

.page__header p {
  margin: 8px 0 0;
  color: #606266;
}

.summary-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.summary-card strong {
  font-size: 24px;
}
</style>
