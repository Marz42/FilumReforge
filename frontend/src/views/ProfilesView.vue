<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listDepartments } from '@/api/departments'
import { createProfile, listProfiles } from '@/api/profiles'
import { listUsers } from '@/api/users'
import type { Department, Profile, User } from '@/types/api'
import { formatDate } from '@/utils/formatters'
import { getErrorMessage } from '@/utils/errors'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const profiles = ref<Profile[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])

const form = reactive({
  user_id: '',
  employee_no: '',
  real_name: '',
  department_id: '',
  job_title: '',
  phone: '',
  hire_date: '',
  custom_fields_text: '{\n  "skills": []\n}',
})

const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const existingProfileUsers = computed(() => new Set(profiles.value.map((profile) => profile.user_id)))
const availableUsers = computed(() =>
  users.value.filter((user) => !existingProfileUsers.value.has(user.id) && user.status === 'active'),
)

function resolveDepartmentName(departmentId: string): string {
  return departmentNameMap.value.get(departmentId) ?? '—'
}

function resetForm(): void {
  form.user_id = ''
  form.employee_no = ''
  form.real_name = ''
  form.department_id = ''
  form.job_title = ''
  form.phone = ''
  form.hire_date = ''
  form.custom_fields_text = '{\n  "skills": []\n}'
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [profileList, departmentList, userList] = await Promise.all([
      listProfiles(),
      listDepartments(),
      listUsers(),
    ])

    profiles.value = profileList
    departments.value = departmentList
    users.value = userList
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleCreate(): Promise<void> {
  submitting.value = true

  try {
    const customFields = JSON.parse(form.custom_fields_text) as Record<string, unknown>

    await createProfile({
      user_id: form.user_id,
      employee_no: form.employee_no.trim(),
      real_name: form.real_name.trim(),
      department_id: form.department_id,
      job_title: form.job_title || null,
      phone: form.phone || null,
      hire_date: form.hire_date || null,
      custom_fields: customFields,
    })

    ElMessage.success('档案已创建')
    dialogVisible.value = false
    resetForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-card shadow="never" v-loading="loading">
      <template #header>
        <div class="page__header">
          <span>员工档案</span>
          <el-button type="primary" @click="dialogVisible = true">新建档案</el-button>
        </div>
      </template>

      <el-table :data="profiles" stripe>
        <el-table-column prop="real_name" label="姓名" min-width="140" />
        <el-table-column prop="employee_no" label="员工编号" min-width="120" />
        <el-table-column label="部门" min-width="160">
          <template #default="{ row }: { row: Profile }">
            {{ resolveDepartmentName(row.department_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="job_title" label="岗位" min-width="140" />
        <el-table-column prop="phone" label="电话" min-width="140" />
        <el-table-column label="入职日期" min-width="140">
          <template #default="{ row }: { row: Profile }">
            {{ formatDate(row.hire_date) }}
          </template>
        </el-table-column>
        <el-table-column label="动态字段" min-width="220">
          <template #default="{ row }: { row: Profile }">
            <code class="page__code">{{ JSON.stringify(row.custom_fields) }}</code>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" title="新建档案" width="560px" @closed="resetForm">
      <el-form label-position="top">
        <el-form-item label="用户">
          <el-select v-model="form.user_id" placeholder="请选择用户">
            <el-option
              v-for="user in availableUsers"
              :key="user.id"
              :label="user.email"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="员工编号">
          <el-input v-model="form.employee_no" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="form.real_name" />
        </el-form-item>
        <el-form-item label="部门">
          <el-select v-model="form.department_id" placeholder="请选择部门">
            <el-option
              v-for="department in departments"
              :key="department.id"
              :label="department.name"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位">
          <el-input v-model="form.job_title" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.phone" />
        </el-form-item>
        <el-form-item label="入职日期">
          <el-date-picker
            v-model="form.hire_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择日期"
          />
        </el-form-item>
        <el-form-item label="动态字段(JSON)">
          <el-input
            v-model="form.custom_fields_text"
            type="textarea"
            :rows="6"
            placeholder='例如 {"skills": ["python"]}'
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">保存</el-button>
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

.page__code {
  display: inline-block;
  max-width: 100%;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
