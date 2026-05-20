<script setup lang="ts">
import { computed } from 'vue'

import type { Department, PeopleManagementPerson, User } from '@/types/api'

interface DepartmentFormState {
  name: string
  code: string
  parent_id: string
  manager_id: string
  sort_order: number
  is_active: boolean
}

interface Props {
  department: Department | null
  isCreating?: boolean
  createModeTitle?: string
  departments: Department[]
  users: User[]
  subordinates: PeopleManagementPerson[]
  form: DepartmentFormState
  submitting?: boolean
  isEditingRootDepartment?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isCreating: false,
  createModeTitle: '新建部门',
  submitting: false,
  isEditingRootDepartment: false,
  subordinates: () => [],
})

const emit = defineEmits<{
  submit: []
  delete: []
  'cancel-create': []
}>()

const showForm = computed(() => props.isCreating || props.department !== null)

const activeUsers = computed(() => props.users.filter((user) => user.status === 'active'))

const parentOptions = computed(() =>
  props.departments.filter((department) => department.id !== props.department?.id),
)

const departmentNameMap = computed(
  () => new Map(props.departments.map((department) => [department.id, department.name])),
)

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }
  return departmentNameMap.value.get(departmentId) ?? '—'
}
</script>

<template>
  <el-card shadow="never" class="department-detail-panel" data-testid="departments-detail-panel">
    <template v-if="showForm" #header>
      <div v-if="isCreating" class="department-detail-panel__header">
        <div>
          <div class="department-detail-panel__title">{{ createModeTitle }}</div>
          <div class="department-detail-panel__subtitle">填写信息后点击「创建部门」保存</div>
        </div>
        <el-button @click="emit('cancel-create')">取消</el-button>
      </div>
      <div v-else-if="department" class="department-detail-panel__header">
        <div>
          <div class="department-detail-panel__title">{{ department.name }}</div>
          <div class="department-detail-panel__subtitle">
            编码 {{ department.code }} · 上级 {{ resolveDepartmentName(department.parent_id) }}
          </div>
        </div>
        <el-space>
          <el-tag :type="department.is_active ? 'success' : 'info'">
            {{ department.is_active ? '启用' : '停用' }}
          </el-tag>
          <el-button
            v-if="department.code !== 'root'"
            type="danger"
            plain
            @click="emit('delete')"
          >
            删除
          </el-button>
        </el-space>
      </div>
    </template>

    <template v-if="showForm">
      <el-form label-position="top" data-testid="departments-form">
        <div class="department-detail-panel__form-grid">
          <el-form-item label="部门名称">
            <el-input v-model="form.name" data-testid="departments-form-name" />
          </el-form-item>
          <el-form-item label="编码">
            <el-input
              v-model="form.code"
              :disabled="!isCreating && isEditingRootDepartment"
              data-testid="departments-form-code"
            />
          </el-form-item>
          <el-form-item label="上级部门">
            <el-select
              v-model="form.parent_id"
              clearable
              placeholder="可选"
              :disabled="!isCreating && isEditingRootDepartment"
              data-testid="departments-form-parent"
            >
              <el-option
                v-for="option in parentOptions"
                :key="option.id"
                :label="option.name"
                :value="option.id"
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
          <el-form-item v-if="!isCreating" label="状态">
            <el-switch v-model="form.is_active" :disabled="isEditingRootDepartment" />
          </el-form-item>
        </div>
        <div class="department-detail-panel__actions">
          <el-button
            type="primary"
            :loading="submitting"
            data-testid="departments-form-submit"
            @click="emit('submit')"
          >
            {{ isCreating ? '创建部门' : '保存部门' }}
          </el-button>
        </div>
      </el-form>

      <template v-if="department && !isCreating">
        <el-divider content-position="left">下属人员</el-divider>
        <el-empty v-if="subordinates.length === 0" description="暂无关联人员（按人员工作台主部门过滤）" />
        <el-table v-else :data="subordinates" stripe>
          <el-table-column label="姓名" min-width="160">
            <template #default="{ row }: { row: PeopleManagementPerson }">
              {{ row.real_name ?? row.email }}
            </template>
          </el-table-column>
          <el-table-column prop="email" label="邮箱" min-width="220" />
          <el-table-column prop="job_title" label="岗位" min-width="160" />
          <el-table-column label="建档" width="120">
            <template #default="{ row }: { row: PeopleManagementPerson }">
              {{ row.has_profile ? '已建档' : '未建档' }}
            </template>
          </el-table-column>
        </el-table>
      </template>
    </template>

    <el-empty v-else description="请选择左侧部门节点，或点击「新建根部门」" />
  </el-card>
</template>

<style scoped>
.department-detail-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.department-detail-panel__title {
  font-size: 18px;
  font-weight: 600;
}

.department-detail-panel__subtitle {
  margin-top: 4px;
  color: var(--filum-text-secondary);
  font-size: 13px;
}

.department-detail-panel__form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.department-detail-panel__actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

@media (max-width: 900px) {
  .department-detail-panel__form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
