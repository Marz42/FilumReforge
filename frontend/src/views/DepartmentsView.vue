<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createDepartment,
  deleteDepartment,
  listDepartments,
  listDepartmentTree,
  updateDepartment,
} from '@/api/departments'
import { listUsers } from '@/api/users'
import type { Department, DepartmentTreeNode, User } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const editingDepartmentId = ref<string | null>(null)
const departments = ref<Department[]>([])
const departmentTree = ref<DepartmentTreeNode[]>([])
const users = ref<User[]>([])

const form = reactive({
  name: '',
  code: '',
  parent_id: '',
  manager_id: '',
  sort_order: 0,
  is_active: true,
})

const treeProps = {
  label: 'name',
  children: 'children',
}

const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const userEmailMap = computed(() => new Map(users.value.map((user) => [user.id, user.email])))
const activeUsers = computed(() => users.value.filter((user) => user.status === 'active'))
const isEditing = computed(() => editingDepartmentId.value !== null)
const currentDepartment = computed(
  () => departments.value.find((department) => department.id === editingDepartmentId.value) ?? null,
)
const isEditingRootDepartment = computed(() => currentDepartment.value?.code === 'root')
const dialogTitle = computed(() => (isEditing.value ? '编辑部门' : '新建部门'))
const parentOptions = computed(() =>
  departments.value.filter((department) => department.id !== editingDepartmentId.value),
)

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }

  return departmentNameMap.value.get(departmentId) ?? '—'
}

function resolveUserEmail(userId: string | null): string {
  if (!userId) {
    return '—'
  }

  return userEmailMap.value.get(userId) ?? '—'
}

function resetForm(): void {
  editingDepartmentId.value = null
  form.name = ''
  form.code = ''
  form.parent_id = ''
  form.manager_id = ''
  form.sort_order = 0
  form.is_active = true
}

function isRootDepartment(department: Department): boolean {
  return department.code === 'root'
}

function openCreateDialog(): void {
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(department: Department): void {
  editingDepartmentId.value = department.id
  form.name = department.name
  form.code = department.code
  form.parent_id = department.parent_id ?? ''
  form.manager_id = department.manager_id ?? ''
  form.sort_order = department.sort_order
  form.is_active = department.is_active
  dialogVisible.value = true
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [departmentList, treeList, userList] = await Promise.all([
      listDepartments(),
      listDepartmentTree(),
      listUsers(),
    ])

    departments.value = departmentList
    departmentTree.value = treeList
    users.value = userList
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleSubmit(): Promise<void> {
  submitting.value = true

  try {
    if (isEditing.value && editingDepartmentId.value) {
      await updateDepartment(editingDepartmentId.value, {
        name: form.name.trim(),
        code: form.code.trim(),
        parent_id: form.parent_id || null,
        manager_id: form.manager_id || null,
        sort_order: form.sort_order,
        is_active: form.is_active,
      })
      ElMessage.success('部门已更新')
    } else {
      await createDepartment({
        name: form.name.trim(),
        code: form.code.trim(),
        parent_id: form.parent_id || null,
        manager_id: form.manager_id || null,
        sort_order: form.sort_order,
      })
      ElMessage.success('部门已创建')
    }

    dialogVisible.value = false
    resetForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(department: Department): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确认删除“${department.name}”吗？仅允许删除没有子部门和关联数据的空部门。`,
      '删除部门',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
    await deleteDepartment(department.id)
    ElMessage.success('部门已删除')
    await loadData()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(getErrorMessage(error))
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="20">
      <el-col :xs="24" :lg="16">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>部门列表</span>
              <el-button type="primary" @click="openCreateDialog">新建部门</el-button>
            </div>
          </template>

          <el-table :data="departments" stripe>
            <el-table-column label="部门名称" min-width="180">
              <template #default="{ row }: { row: Department }">
                <el-space>
                  <span>{{ row.name }}</span>
                  <el-tag v-if="isRootDepartment(row)" size="small" type="warning">公司</el-tag>
                </el-space>
              </template>
            </el-table-column>
            <el-table-column prop="code" label="编码" min-width="120" />
            <el-table-column label="上级部门" min-width="140">
              <template #default="{ row }: { row: Department }">
                {{ resolveDepartmentName(row.parent_id) }}
              </template>
            </el-table-column>
            <el-table-column label="负责人" min-width="180">
              <template #default="{ row }: { row: Department }">
                {{ resolveUserEmail(row.manager_id) }}
              </template>
            </el-table-column>
            <el-table-column prop="sort_order" label="排序" width="100" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }: { row: Department }">
                <el-tag :type="row.is_active ? 'success' : 'info'">
                  {{ row.is_active ? '启用' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }: { row: Department }">
                <el-space>
                  <el-button link type="primary" @click="openEditDialog(row)">编辑</el-button>
                  <el-button
                    v-if="!isRootDepartment(row)"
                    link
                    type="danger"
                    @click="handleDelete(row)"
                  >
                    删除
                  </el-button>
                </el-space>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="8">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <span>组织树</span>
          </template>

          <el-tree
            :data="departmentTree"
            :props="treeProps"
            node-key="id"
            default-expand-all
            empty-text="暂无部门数据"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" @closed="resetForm">
      <el-form label-position="top">
        <el-form-item label="部门名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="编码">
          <el-input v-model="form.code" :disabled="isEditingRootDepartment" />
        </el-form-item>
        <el-form-item label="上级部门">
          <el-select
            v-model="form.parent_id"
            clearable
            placeholder="可选"
            :disabled="isEditingRootDepartment"
          >
            <el-option
              v-for="department in parentOptions"
              :key="department.id"
              :label="department.name"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.manager_id" clearable placeholder="可选">
            <el-option
              v-for="user in activeUsers"
              :key="user.id"
              :label="user.email"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" />
        </el-form-item>
        <el-form-item v-if="isEditing" label="状态">
          <el-switch v-model="form.is_active" :disabled="isEditingRootDepartment" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
