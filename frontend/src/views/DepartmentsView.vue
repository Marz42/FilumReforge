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
import { getPeopleManagement } from '@/api/people-management'
import DepartmentDetailPanel from '@/components/departments/DepartmentDetailPanel.vue'
import DepartmentTreePanel from '@/components/departments/DepartmentTreePanel.vue'
import { listUsers } from '@/api/users'
import type { Department, DepartmentTreeNode, PeopleManagementPerson, User } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'

const loading = ref(false)
const submitting = ref(false)
const selectedDepartmentId = ref('')
const departments = ref<Department[]>([])
const departmentTree = ref<DepartmentTreeNode[]>([])
const users = ref<User[]>([])
const people = ref<PeopleManagementPerson[]>([])

const form = reactive({
  name: '',
  code: '',
  parent_id: '',
  manager_id: '',
  sort_order: 0,
  is_active: true,
})

const selectedDepartment = computed(
  () => departments.value.find((department) => department.id === selectedDepartmentId.value) ?? null,
)

const isEditingRootDepartment = computed(() => selectedDepartment.value?.code === 'root')

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [departmentList, treeList, userList, workspace] = await Promise.all([
      listDepartments(),
      listDepartmentTree(),
      listUsers(),
      getPeopleManagement().catch(() => null),
    ])

    departments.value = departmentList
    departmentTree.value = treeList
    users.value = userList
    people.value = workspace?.people ?? []

    if (!selectedDepartmentId.value && departmentList.length > 0) {
      selectDepartment(departmentList[0]!.id)
    } else if (selectedDepartmentId.value) {
      hydrateForm(selectedDepartmentId.value)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function resetForm(parentId = ''): void {
  form.name = ''
  form.code = ''
  form.parent_id = parentId
  form.manager_id = ''
  form.sort_order = 0
  form.is_active = true
}

function hydrateForm(departmentId: string): void {
  const department = departments.value.find((item) => item.id === departmentId)
  if (!department) {
    resetForm()
    return
  }

  form.name = department.name
  form.code = department.code
  form.parent_id = department.parent_id ?? ''
  form.manager_id = department.manager_id ?? ''
  form.sort_order = department.sort_order
  form.is_active = department.is_active
}

function selectDepartment(departmentId: string): void {
  selectedDepartmentId.value = departmentId
  hydrateForm(departmentId)
}

function openCreateRootDialog(): void {
  selectedDepartmentId.value = ''
  resetForm('')
}

function openCreateChildDialog(parentId: string): void {
  selectedDepartmentId.value = ''
  resetForm(parentId)
}

async function handleSubmit(): Promise<void> {
  submitting.value = true

  try {
    if (selectedDepartment.value) {
      await updateDepartment(selectedDepartment.value.id, {
        name: form.name.trim(),
        code: form.code.trim(),
        parent_id: form.parent_id || null,
        manager_id: form.manager_id || null,
        sort_order: form.sort_order,
        is_active: form.is_active,
      })
      ElMessage.success('部门已更新')
    } else {
      const created = await createDepartment({
        name: form.name.trim(),
        code: form.code.trim(),
        parent_id: form.parent_id || null,
        manager_id: form.manager_id || null,
        sort_order: form.sort_order,
      })
      ElMessage.success('部门已创建')
      selectedDepartmentId.value = created.id
    }

    await loadData()
    if (selectedDepartmentId.value) {
      hydrateForm(selectedDepartmentId.value)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(): Promise<void> {
  if (!selectedDepartment.value || selectedDepartment.value.code === 'root') {
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认删除“${selectedDepartment.value.name}”吗？仅允许删除没有子部门和关联数据的空部门。`,
      '删除部门',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
    await deleteDepartment(selectedDepartment.value.id)
    ElMessage.success('部门已删除')
    selectedDepartmentId.value = ''
    resetForm()
    await loadData()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(getErrorMessage(error))
  }
}

const subordinatePeople = computed(() => {
  if (!selectedDepartmentId.value) {
    return []
  }
  return people.value.filter((person) => person.department_id === selectedDepartmentId.value)
})

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="departments-page filum-page" data-testid="departments-view">
    <el-card shadow="never" class="filum-panel-card">
      <template #header>
        <div class="departments-page__header filum-page-header">
          <div class="filum-page-header__copy">
            <span class="filum-page-header__eyebrow">Organization</span>
            <strong class="filum-page-header__title">部门管理</strong>
            <p class="departments-page__subtitle">左侧组织树选中部门，右侧维护详情、负责人与下属人员。</p>
          </div>
        </div>
      </template>

      <div class="departments-page__layout">
        <DepartmentTreePanel
          :tree="departmentTree"
          :selected-department-id="selectedDepartmentId"
          :loading="loading"
          @select="selectDepartment"
          @create-root="openCreateRootDialog"
          @create-child="openCreateChildDialog"
        />

        <DepartmentDetailPanel
          :department="selectedDepartment"
          :departments="departments"
          :users="users"
          :subordinates="subordinatePeople"
          :form="form"
          :submitting="submitting"
          :is-editing-root-department="isEditingRootDepartment"
          @submit="handleSubmit"
          @delete="handleDelete"
        />
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.departments-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.departments-page__subtitle {
  margin: 6px 0 0;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.departments-page__layout {
  display: grid;
  grid-template-columns: minmax(260px, 34%) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

@media (max-width: 1080px) {
  .departments-page__layout {
    grid-template-columns: 1fr;
  }
}
</style>
