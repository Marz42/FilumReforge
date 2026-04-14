<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { listDepartments } from '@/api/departments'
import {
  createDelegation,
  createPosition,
  createProfile,
  createProfileEvent,
  createProfilePosition,
  createProfileReportingLine,
  getProfile,
  listPositions,
  listProfileFieldDefinitions,
  listProfiles,
  updateDelegation,
  updateProfile,
} from '@/api/profiles'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type {
  Delegation,
  DelegationScopeType,
  DelegationStatus,
  Department,
  EmploymentEventType,
  Position,
  PositionAssignmentType,
  Profile,
  ProfileFieldDefinition,
  ProfileFieldAccess,
  ReportingLineType,
  User,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDate, formatDateTime } from '@/utils/formatters'

type SelectionOption = {
  value: string
  label: string
}

const ASSIGNMENT_TYPE_OPTIONS: Array<{ label: string; value: PositionAssignmentType }> = [
  { label: '主任职', value: 'primary' },
  { label: '兼职', value: 'part_time' },
  { label: '代理岗', value: 'acting' },
]

const REPORTING_LINE_OPTIONS: Array<{ label: string; value: ReportingLineType }> = [
  { label: '直属汇报', value: 'solid' },
  { label: '虚线汇报', value: 'dotted' },
]

const EVENT_TYPE_OPTIONS: Array<{ label: string; value: EmploymentEventType }> = [
  { label: '入职', value: 'onboard' },
  { label: '转岗', value: 'transfer' },
  { label: '晋升', value: 'promotion' },
  { label: '奖励', value: 'reward' },
  { label: '处分', value: 'discipline' },
  { label: '离职', value: 'offboard' },
  { label: '返聘', value: 'rehire' },
]

const DELEGATION_SCOPE_OPTIONS: Array<{ label: string; value: DelegationScopeType }> = [
  { label: '数据访问', value: 'data_access' },
  { label: '审批', value: 'approval' },
  { label: '任务', value: 'task' },
  { label: '全部', value: 'all' },
]

const DELEGATION_STATUS_LABELS: Record<DelegationStatus, string> = {
  pending: '待生效',
  active: '生效中',
  expired: '已过期',
  revoked: '已撤销',
}

const DELEGATION_STATUS_TAG_TYPES: Record<
  DelegationStatus,
  '' | 'info' | 'success' | 'warning' | 'danger'
> = {
  pending: 'info',
  active: 'success',
  expired: 'warning',
  revoked: 'danger',
}

const authStore = useAuthStore()
const loading = ref(false)
const detailLoading = ref(false)
const createDialogVisible = ref(false)
const createSubmitting = ref(false)
const basicSubmitting = ref(false)
const positionCatalogSubmitting = ref(false)
const positionSubmitting = ref(false)
const reportingSubmitting = ref(false)
const eventSubmitting = ref(false)
const delegationSubmitting = ref(false)
const activeTab = ref('basic')
const selectedProfileId = ref('')

const profiles = ref<Profile[]>([])
const selectedProfile = ref<Profile | null>(null)
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const positions = ref<Position[]>([])
const fieldDefinitions = ref<ProfileFieldDefinition[]>([])

const createForm = reactive({
  user_id: '',
  employee_no: '',
  real_name: '',
  department_id: '',
  job_title: '',
  phone: '',
  hire_date: '',
  custom_fields_text: '{\n  "skills": []\n}',
})

const basicForm = reactive({
  employee_no: '',
  real_name: '',
  phone: '',
  hire_date: '',
  custom_fields_text: '{}',
})

const positionCatalogForm = reactive({
  code: '',
  name: '',
  level: '',
  extra_metadata_text: '{\n  "band": ""\n}',
})

const positionForm = reactive({
  position_id: '',
  department_id: '',
  assignment_type: 'primary' as PositionAssignmentType,
  is_primary: true,
  starts_at: '',
  ends_at: '',
})

const reportingForm = reactive({
  manager_user_id: '',
  department_id: '',
  line_type: 'solid' as ReportingLineType,
  is_primary: true,
  starts_at: '',
  ends_at: '',
})

const eventForm = reactive({
  event_type: 'promotion' as EmploymentEventType,
  effective_date: '',
  title: '',
  summary: '',
  payload_text: '{\n  "job_title": ""\n}',
})

const delegationForm = reactive({
  delegate_user_id: '',
  scope_type: 'data_access' as DelegationScopeType,
  scope_department_id: '',
  starts_at: null as Date | null,
  ends_at: null as Date | null,
})

const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const positionNameMap = computed(
  () => new Map(positions.value.map((position) => [position.id, position.name])),
)
const userEmailMap = computed(() => new Map(users.value.map((user) => [user.id, user.email])))
const profileLabelMap = computed(
  () =>
    new Map(
      profiles.value.map((profile) => [
        profile.user_id,
        profile.real_name ?? profile.user_email ?? profile.user_id,
      ]),
    ),
)
const existingProfileUsers = computed(() => new Set(profiles.value.map((profile) => profile.user_id)))
const availableUsers = computed(() =>
  authStore.isManagementRole
    ? users.value.filter(
        (user) => !existingProfileUsers.value.has(user.id) && user.status === 'active',
      )
    : [],
)
const managerOptions = computed<SelectionOption[]>(() => {
  if (authStore.isManagementRole) {
    return users.value
      .filter((user) => user.status === 'active')
      .map((user) => ({
        value: user.id,
        label: user.email,
      }))
  }

  return profiles.value.map((profile) => ({
    value: profile.user_id,
    label: profile.real_name ?? profile.user_email ?? profile.user_id,
  }))
})
const delegateOptions = computed<SelectionOption[]>(() =>
  profiles.value
    .filter((profile) => profile.user_id !== selectedProfile.value?.user_id)
    .map((profile) => ({
      value: profile.user_id,
      label: profile.real_name ?? profile.user_email ?? profile.user_id,
    })),
)
const visibleFields = computed(() => selectedProfile.value?.visible_fields ?? [])
const generalFields = computed(() => visibleFields.value.filter((field) => !field.is_sensitive))
const sensitiveFields = computed(() => visibleFields.value.filter((field) => field.is_sensitive))
const selectedProfileLabel = computed(
  () => selectedProfile.value?.real_name ?? selectedProfile.value?.user_email ?? '未选择档案',
)
const canCreateProfile = computed(() => authStore.isManagementRole)
const canManageRelations = computed(() => authStore.isManagementRole && Boolean(selectedProfile.value))
const canManageLifecycle = computed(() => authStore.isManagementRole && Boolean(selectedProfile.value))
const canManageDelegations = computed(
  () =>
    Boolean(selectedProfile.value) &&
    (authStore.isManagementRole || authStore.user?.id === selectedProfile.value?.user_id),
)

function resolveDepartmentName(departmentId: string | null): string {
  if (!departmentId) {
    return '—'
  }

  return departmentNameMap.value.get(departmentId) ?? '—'
}

function resolvePositionName(positionId: string): string {
  return positionNameMap.value.get(positionId) ?? `岗位 ${positionId.slice(0, 8)}`
}

function resolveUserLabel(userId: string): string {
  return (
    userEmailMap.value.get(userId) ??
    profileLabelMap.value.get(userId) ??
    `用户 ${userId.slice(0, 8)}`
  )
}

function resolveDelegationStatusLabel(status: DelegationStatus): string {
  return DELEGATION_STATUS_LABELS[status]
}

function resolveDelegationStatusTagType(
  status: DelegationStatus,
): '' | 'info' | 'success' | 'warning' | 'danger' {
  return DELEGATION_STATUS_TAG_TYPES[status]
}

function resetCreateForm(): void {
  createForm.user_id = ''
  createForm.employee_no = ''
  createForm.real_name = ''
  createForm.department_id = ''
  createForm.job_title = ''
  createForm.phone = ''
  createForm.hire_date = ''
  createForm.custom_fields_text = '{\n  "skills": []\n}'
}

function resetPositionCatalogForm(): void {
  positionCatalogForm.code = ''
  positionCatalogForm.name = ''
  positionCatalogForm.level = ''
  positionCatalogForm.extra_metadata_text = '{\n  "band": ""\n}'
}

function resetPositionForm(): void {
  positionForm.position_id = ''
  positionForm.department_id = selectedProfile.value?.department_id ?? ''
  positionForm.assignment_type = 'primary'
  positionForm.is_primary = true
  positionForm.starts_at = ''
  positionForm.ends_at = ''
}

function resetReportingForm(): void {
  reportingForm.manager_user_id = ''
  reportingForm.department_id = selectedProfile.value?.department_id ?? ''
  reportingForm.line_type = 'solid'
  reportingForm.is_primary = true
  reportingForm.starts_at = ''
  reportingForm.ends_at = ''
}

function resetEventForm(): void {
  eventForm.event_type = 'promotion'
  eventForm.effective_date = ''
  eventForm.title = ''
  eventForm.summary = ''
  eventForm.payload_text = '{\n  "job_title": ""\n}'
}

function resetDelegationForm(): void {
  delegationForm.delegate_user_id = ''
  delegationForm.scope_type = 'data_access'
  delegationForm.scope_department_id = selectedProfile.value?.department_id ?? ''
  delegationForm.starts_at = null
  delegationForm.ends_at = null
}

function hydrateBasicForm(profile: Profile): void {
  basicForm.employee_no = profile.employee_no ?? ''
  basicForm.real_name = profile.real_name ?? ''
  basicForm.phone = profile.phone ?? ''
  basicForm.hire_date = profile.hire_date ?? ''
  basicForm.custom_fields_text = JSON.stringify(profile.custom_fields, null, 2)
  positionForm.department_id = profile.department_id ?? ''
  reportingForm.department_id = profile.department_id ?? ''
  delegationForm.scope_department_id = profile.department_id ?? ''
}

async function loadSelectedProfile(userId: string): Promise<void> {
  detailLoading.value = true

  try {
    const profile = await getProfile(userId)
    selectedProfile.value = profile
    hydrateBasicForm(profile)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

async function loadData(): Promise<void> {
  loading.value = true

  try {
    const [profileList, departmentList, positionList] = await Promise.all([
      listProfiles(),
      listDepartments(),
      listPositions(),
    ])

    profiles.value = profileList
    departments.value = departmentList
    positions.value = positionList

    if (authStore.isManagementRole) {
      const [userList, definitionList] = await Promise.all([
        listUsers(),
        listProfileFieldDefinitions(),
      ])
      users.value = userList
      fieldDefinitions.value = definitionList
    } else {
      users.value = []
      fieldDefinitions.value = []
    }

    const stillExists = profileList.some((profile) => profile.user_id === selectedProfileId.value)
    if (!stillExists) {
      selectedProfileId.value = profileList[0]?.user_id ?? ''
    }

    if (selectedProfileId.value) {
      await loadSelectedProfile(selectedProfileId.value)
    } else {
      selectedProfile.value = null
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

function selectProfile(userId: string): void {
  if (selectedProfileId.value === userId) {
    return
  }

  selectedProfileId.value = userId
  void loadSelectedProfile(userId)
}

async function handleCreateProfile(): Promise<void> {
  createSubmitting.value = true

  try {
    const customFields = JSON.parse(createForm.custom_fields_text) as Record<string, unknown>
    const profile = await createProfile({
      user_id: createForm.user_id,
      employee_no: createForm.employee_no.trim(),
      real_name: createForm.real_name.trim(),
      department_id: createForm.department_id,
      job_title: createForm.job_title || null,
      phone: createForm.phone || null,
      hire_date: createForm.hire_date || null,
      custom_fields: customFields,
    })

    ElMessage.success('档案已创建')
    createDialogVisible.value = false
    resetCreateForm()
    selectedProfileId.value = profile.user_id
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    createSubmitting.value = false
  }
}

async function handleSaveBasic(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  basicSubmitting.value = true

  try {
    const customFields = JSON.parse(basicForm.custom_fields_text) as Record<string, unknown>

    await updateProfile(selectedProfile.value.user_id, {
      employee_no: basicForm.employee_no.trim() || null,
      real_name: basicForm.real_name.trim() || null,
      phone: basicForm.phone.trim() || null,
      hire_date: basicForm.hire_date || null,
      custom_fields: customFields,
    })

    ElMessage.success('档案已更新')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    basicSubmitting.value = false
  }
}

async function handleCreatePositionCatalog(): Promise<void> {
  positionCatalogSubmitting.value = true

  try {
    const extraMetadata = JSON.parse(positionCatalogForm.extra_metadata_text) as Record<string, unknown>

    await createPosition({
      code: positionCatalogForm.code.trim(),
      name: positionCatalogForm.name.trim(),
      level: positionCatalogForm.level || null,
      extra_metadata: extraMetadata,
      is_active: true,
    })

    ElMessage.success('岗位已创建')
    resetPositionCatalogForm()
    positions.value = await listPositions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    positionCatalogSubmitting.value = false
  }
}

async function handleCreatePositionAssignment(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  positionSubmitting.value = true

  try {
    await createProfilePosition(selectedProfile.value.user_id, {
      position_id: positionForm.position_id,
      department_id: positionForm.department_id,
      assignment_type: positionForm.assignment_type,
      is_primary: positionForm.is_primary,
      starts_at: positionForm.starts_at,
      ends_at: positionForm.ends_at || null,
    })

    ElMessage.success('任职关系已新增')
    resetPositionForm()
    await loadSelectedProfile(selectedProfile.value.user_id)
    profiles.value = await listProfiles()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    positionSubmitting.value = false
  }
}

async function handleCreateReportingLine(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  reportingSubmitting.value = true

  try {
    await createProfileReportingLine(selectedProfile.value.user_id, {
      manager_user_id: reportingForm.manager_user_id,
      department_id: reportingForm.department_id || null,
      line_type: reportingForm.line_type,
      is_primary: reportingForm.is_primary,
      starts_at: reportingForm.starts_at,
      ends_at: reportingForm.ends_at || null,
    })

    ElMessage.success('汇报线已新增')
    resetReportingForm()
    await loadSelectedProfile(selectedProfile.value.user_id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    reportingSubmitting.value = false
  }
}

async function handleCreateEvent(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  eventSubmitting.value = true

  try {
    const payload = JSON.parse(eventForm.payload_text) as Record<string, unknown>

    await createProfileEvent(selectedProfile.value.user_id, {
      event_type: eventForm.event_type,
      effective_date: eventForm.effective_date,
      title: eventForm.title.trim(),
      summary: eventForm.summary.trim() || null,
      payload,
    })

    ElMessage.success('生命周期事件已记录')
    resetEventForm()
    await loadSelectedProfile(selectedProfile.value.user_id)
    profiles.value = await listProfiles()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    eventSubmitting.value = false
  }
}

async function handleCreateDelegation(): Promise<void> {
  if (!selectedProfile.value || !delegationForm.starts_at || !delegationForm.ends_at) {
    ElMessage.warning('请填写完整的授权时间范围')
    return
  }

  delegationSubmitting.value = true

  try {
    await createDelegation({
      delegator_user_id: selectedProfile.value.user_id,
      delegate_user_id: delegationForm.delegate_user_id,
      scope_type: delegationForm.scope_type,
      scope_department_id: delegationForm.scope_department_id || null,
      scope_filters: {},
      starts_at: delegationForm.starts_at.toISOString(),
      ends_at: delegationForm.ends_at.toISOString(),
    })

    ElMessage.success('授权已创建')
    resetDelegationForm()
    await loadSelectedProfile(selectedProfile.value.user_id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    delegationSubmitting.value = false
  }
}

async function handleRevokeDelegation(delegation: Delegation): Promise<void> {
  try {
    await updateDelegation(delegation.id, {
      status: 'revoked',
    })
    ElMessage.success('授权已撤销')
    if (selectedProfile.value) {
      await loadSelectedProfile(selectedProfile.value.user_id)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function renderFieldValue(field: ProfileFieldAccess): string {
  if (field.value === null || field.value === undefined) {
    return '—'
  }

  if (typeof field.value === 'object') {
    return JSON.stringify(field.value)
  }

  return String(field.value)
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
          <div>
            <div class="page__title">员工档案</div>
            <div class="page__subtitle">Phase 3 / HR Governance & Org Modeling</div>
          </div>
          <el-button v-if="canCreateProfile" type="primary" @click="createDialogVisible = true">
            新建档案
          </el-button>
        </div>
      </template>

      <el-table :data="profiles" stripe highlight-current-row @row-click="(row: Profile) => selectProfile(row.user_id)">
        <el-table-column prop="real_name" label="姓名" min-width="140" />
        <el-table-column prop="employee_no" label="员工编号" min-width="120" />
        <el-table-column label="邮箱" min-width="220">
          <template #default="{ row }: { row: Profile }">
            {{ row.user_email ?? '—' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" min-width="110">
          <template #default="{ row }: { row: Profile }">
            <el-tag size="small">{{ row.user_status ?? '—' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="部门" min-width="160">
          <template #default="{ row }: { row: Profile }">
            {{ resolveDepartmentName(row.department_id) }}
          </template>
        </el-table-column>
        <el-table-column prop="job_title" label="岗位" min-width="160" />
        <el-table-column label="可见字段" min-width="160">
          <template #default="{ row }: { row: Profile }">
            {{ row.visible_fields.length }} 项
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="selectedProfile" class="page__detail" shadow="never" v-loading="detailLoading">
      <template #header>
        <div class="page__detail-header">
          <div>
            <div class="page__title">{{ selectedProfileLabel }}</div>
            <div class="page__subtitle">
              {{ selectedProfile.user_email ?? '—' }} · {{ resolveDepartmentName(selectedProfile.department_id) }}
            </div>
          </div>
          <div class="page__detail-meta">
            <el-tag size="small">{{ selectedProfile.user_status ?? 'unknown' }}</el-tag>
            <span>更新时间：{{ formatDateTime(selectedProfile.updated_at) }}</span>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane label="基础信息" name="basic">
          <div class="page__grid page__grid--two">
            <el-card shadow="never">
              <template #header>基础概览</template>
              <el-descriptions :column="2" border>
                <el-descriptions-item label="员工编号">
                  {{ selectedProfile.employee_no ?? '—' }}
                </el-descriptions-item>
                <el-descriptions-item label="姓名">
                  {{ selectedProfile.real_name ?? '—' }}
                </el-descriptions-item>
                <el-descriptions-item label="电话">
                  {{ selectedProfile.phone ?? '—' }}
                </el-descriptions-item>
                <el-descriptions-item label="入职日期">
                  {{ formatDate(selectedProfile.hire_date) }}
                </el-descriptions-item>
                <el-descriptions-item label="主部门">
                  {{ resolveDepartmentName(selectedProfile.department_id) }}
                </el-descriptions-item>
                <el-descriptions-item label="当前岗位">
                  {{ selectedProfile.job_title ?? '—' }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card shadow="never">
              <template #header>可编辑基础字段</template>
              <el-form label-position="top">
                <el-form-item label="员工编号">
                  <el-input v-model="basicForm.employee_no" />
                </el-form-item>
                <el-form-item label="姓名">
                  <el-input v-model="basicForm.real_name" />
                </el-form-item>
                <el-form-item label="电话">
                  <el-input v-model="basicForm.phone" />
                </el-form-item>
                <el-form-item label="入职日期">
                  <el-date-picker
                    v-model="basicForm.hire_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                    placeholder="选择日期"
                  />
                </el-form-item>
                <el-form-item label="可见动态字段(JSON)">
                  <el-input
                    v-model="basicForm.custom_fields_text"
                    type="textarea"
                    :rows="8"
                    placeholder='例如 {"hobby": "摄影"}'
                  />
                </el-form-item>
                <div class="page__actions">
                  <el-button type="primary" :loading="basicSubmitting" @click="handleSaveBasic">
                    保存基础信息
                  </el-button>
                </div>
              </el-form>
            </el-card>
          </div>

          <el-card class="page__section" shadow="never">
            <template #header>当前可见字段</template>
            <el-table :data="generalFields" stripe>
              <el-table-column prop="label" label="字段" min-width="160" />
              <el-table-column prop="field_key" label="Key" min-width="160" />
              <el-table-column label="值" min-width="220">
                <template #default="{ row }: { row: ProfileFieldAccess }">
                  {{ renderFieldValue(row) }}
                </template>
              </el-table-column>
              <el-table-column label="可编辑" min-width="100">
                <template #default="{ row }: { row: ProfileFieldAccess }">
                  <el-tag size="small" :type="row.can_edit ? 'success' : 'info'">
                    {{ row.can_edit ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="任职关系" name="positions">
          <div class="page__grid page__grid--two">
            <el-card shadow="never">
              <template #header>任职记录</template>
              <el-table :data="selectedProfile.positions" stripe>
                <el-table-column label="岗位" min-width="160">
                  <template #default="{ row }">
                    {{ resolvePositionName(row.position_id) }}
                  </template>
                </el-table-column>
                <el-table-column label="部门" min-width="160">
                  <template #default="{ row }">
                    {{ resolveDepartmentName(row.department_id) }}
                  </template>
                </el-table-column>
                <el-table-column prop="assignment_type" label="类型" min-width="110" />
                <el-table-column label="主任职" min-width="100">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.is_primary ? 'success' : 'info'">
                      {{ row.is_primary ? '是' : '否' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="生效日期" min-width="120">
                  <template #default="{ row }">
                    {{ formatDate(row.starts_at) }}
                  </template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-card shadow="never">
              <template #header>汇报关系</template>
              <el-table :data="selectedProfile.reporting_lines" stripe>
                <el-table-column label="上级" min-width="180">
                  <template #default="{ row }">
                    {{ resolveUserLabel(row.manager_user_id) }}
                  </template>
                </el-table-column>
                <el-table-column prop="line_type" label="类型" min-width="110" />
                <el-table-column label="关联部门" min-width="160">
                  <template #default="{ row }">
                    {{ resolveDepartmentName(row.department_id) }}
                  </template>
                </el-table-column>
                <el-table-column label="主要汇报" min-width="100">
                  <template #default="{ row }">
                    <el-tag size="small" :type="row.is_primary ? 'success' : 'info'">
                      {{ row.is_primary ? '是' : '否' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>

          <div v-if="canManageRelations" class="page__grid page__grid--three page__section">
            <el-card shadow="never">
              <template #header>岗位目录</template>
              <el-form label-position="top">
                <el-form-item label="岗位编码">
                  <el-input v-model="positionCatalogForm.code" />
                </el-form-item>
                <el-form-item label="岗位名称">
                  <el-input v-model="positionCatalogForm.name" />
                </el-form-item>
                <el-form-item label="岗位级别">
                  <el-input v-model="positionCatalogForm.level" />
                </el-form-item>
                <el-form-item label="扩展配置(JSON)">
                  <el-input
                    v-model="positionCatalogForm.extra_metadata_text"
                    type="textarea"
                    :rows="4"
                  />
                </el-form-item>
                <div class="page__actions">
                  <el-button
                    type="primary"
                    :loading="positionCatalogSubmitting"
                    @click="handleCreatePositionCatalog"
                  >
                    新增岗位
                  </el-button>
                </div>
              </el-form>
            </el-card>

            <el-card shadow="never">
              <template #header>新增任职</template>
              <el-form label-position="top">
                <el-form-item label="岗位">
                  <el-select v-model="positionForm.position_id" placeholder="请选择岗位">
                    <el-option
                      v-for="position in positions"
                      :key="position.id"
                      :label="position.name"
                      :value="position.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="挂载部门">
                  <el-select v-model="positionForm.department_id" placeholder="请选择部门">
                    <el-option
                      v-for="department in departments"
                      :key="department.id"
                      :label="department.name"
                      :value="department.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="任职类型">
                  <el-select v-model="positionForm.assignment_type">
                    <el-option
                      v-for="option in ASSIGNMENT_TYPE_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="是否主任职">
                  <el-switch v-model="positionForm.is_primary" />
                </el-form-item>
                <el-form-item label="开始日期">
                  <el-date-picker
                    v-model="positionForm.starts_at"
                    type="date"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
                <el-form-item label="结束日期">
                  <el-date-picker
                    v-model="positionForm.ends_at"
                    type="date"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
                <div class="page__actions">
                  <el-button type="primary" :loading="positionSubmitting" @click="handleCreatePositionAssignment">
                    新增任职
                  </el-button>
                </div>
              </el-form>
            </el-card>

            <el-card shadow="never">
              <template #header>新增汇报线</template>
              <el-form label-position="top">
                <el-form-item label="上级">
                  <el-select v-model="reportingForm.manager_user_id" placeholder="请选择上级">
                    <el-option
                      v-for="option in managerOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="关联部门">
                  <el-select v-model="reportingForm.department_id" placeholder="请选择部门">
                    <el-option
                      v-for="department in departments"
                      :key="department.id"
                      :label="department.name"
                      :value="department.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="汇报类型">
                  <el-select v-model="reportingForm.line_type">
                    <el-option
                      v-for="option in REPORTING_LINE_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="是否主要汇报">
                  <el-switch v-model="reportingForm.is_primary" />
                </el-form-item>
                <el-form-item label="开始日期">
                  <el-date-picker
                    v-model="reportingForm.starts_at"
                    type="date"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
                <div class="page__actions">
                  <el-button
                    type="primary"
                    :loading="reportingSubmitting"
                    @click="handleCreateReportingLine"
                  >
                    新增汇报线
                  </el-button>
                </div>
              </el-form>
            </el-card>
          </div>
        </el-tab-pane>

        <el-tab-pane label="生命周期事件" name="events">
          <el-card shadow="never">
            <template #header>生命周期事件</template>
            <el-table :data="selectedProfile.employment_events" stripe>
              <el-table-column prop="event_type" label="事件类型" min-width="120" />
              <el-table-column prop="title" label="标题" min-width="200" />
              <el-table-column prop="summary" label="摘要" min-width="220" />
              <el-table-column label="生效日期" min-width="120">
                <template #default="{ row }">
                  {{ formatDate(row.effective_date) }}
                </template>
              </el-table-column>
              <el-table-column label="创建时间" min-width="160">
                <template #default="{ row }">
                  {{ formatDateTime(row.created_at) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card v-if="canManageLifecycle" class="page__section" shadow="never">
            <template #header>记录生命周期事件</template>
            <el-form label-position="top">
              <div class="page__grid page__grid--two">
                <el-form-item label="事件类型">
                  <el-select v-model="eventForm.event_type">
                    <el-option
                      v-for="option in EVENT_TYPE_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="生效日期">
                  <el-date-picker
                    v-model="eventForm.effective_date"
                    type="date"
                    value-format="YYYY-MM-DD"
                  />
                </el-form-item>
                <el-form-item label="事件标题">
                  <el-input v-model="eventForm.title" />
                </el-form-item>
                <el-form-item label="摘要">
                  <el-input v-model="eventForm.summary" />
                </el-form-item>
              </div>
              <el-form-item label="事件负载(JSON)">
                <el-input v-model="eventForm.payload_text" type="textarea" :rows="8" />
              </el-form-item>
              <div class="page__actions">
                <el-button type="primary" :loading="eventSubmitting" @click="handleCreateEvent">
                  记录事件
                </el-button>
              </div>
            </el-form>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="敏感字段" name="sensitive">
          <el-card shadow="never">
            <template #header>当前可见敏感字段</template>
            <el-table :data="sensitiveFields" stripe>
              <el-table-column prop="label" label="字段" min-width="160" />
              <el-table-column prop="field_key" label="Key" min-width="160" />
              <el-table-column label="值" min-width="220">
                <template #default="{ row }: { row: ProfileFieldAccess }">
                  {{ renderFieldValue(row) }}
                </template>
              </el-table-column>
              <el-table-column label="可编辑" min-width="100">
                <template #default="{ row }: { row: ProfileFieldAccess }">
                  <el-tag size="small" :type="row.can_edit ? 'success' : 'info'">
                    {{ row.can_edit ? '是' : '否' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-if="sensitiveFields.length === 0" description="当前身份没有可见的敏感字段" />
          </el-card>

          <el-card v-if="authStore.isManagementRole" class="page__section" shadow="never">
            <template #header>字段定义目录</template>
            <el-table :data="fieldDefinitions" stripe>
              <el-table-column prop="label" label="字段名称" min-width="160" />
              <el-table-column prop="field_key" label="Key" min-width="160" />
              <el-table-column prop="storage_target" label="存储目标" min-width="120" />
              <el-table-column label="敏感" min-width="100">
                <template #default="{ row }: { row: ProfileFieldDefinition }">
                  <el-tag size="small" :type="row.is_sensitive ? 'danger' : 'info'">
                    {{ row.is_sensitive ? '敏感' : '普通' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="启用" min-width="100">
                <template #default="{ row }: { row: ProfileFieldDefinition }">
                  <el-tag size="small" :type="row.is_active ? 'success' : 'warning'">
                    {{ row.is_active ? '启用' : '停用' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="代理授权" name="delegations">
          <el-card shadow="never">
            <template #header>代理授权记录</template>
            <el-table :data="selectedProfile.delegations" stripe>
              <el-table-column label="委托人" min-width="180">
                <template #default="{ row }">
                  {{ resolveUserLabel(row.delegator_user_id) }}
                </template>
              </el-table-column>
              <el-table-column label="被委托人" min-width="180">
                <template #default="{ row }">
                  {{ resolveUserLabel(row.delegate_user_id) }}
                </template>
              </el-table-column>
              <el-table-column prop="scope_type" label="授权范围" min-width="120" />
              <el-table-column label="状态" min-width="110">
                <template #default="{ row }">
                  <el-tag size="small" :type="resolveDelegationStatusTagType(row.status)">
                    {{ resolveDelegationStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="开始时间" min-width="160">
                <template #default="{ row }">
                  {{ formatDateTime(row.starts_at) }}
                </template>
              </el-table-column>
              <el-table-column label="结束时间" min-width="160">
                <template #default="{ row }">
                  {{ formatDateTime(row.ends_at) }}
                </template>
              </el-table-column>
              <el-table-column v-if="canManageDelegations" label="操作" min-width="120">
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'pending' || row.status === 'active'"
                    type="danger"
                    link
                    @click="handleRevokeDelegation(row)"
                  >
                    撤销
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card v-if="canManageDelegations" class="page__section" shadow="never">
            <template #header>创建代理授权</template>
            <el-form label-position="top">
              <div class="page__grid page__grid--two">
                <el-form-item label="被委托人">
                  <el-select v-model="delegationForm.delegate_user_id" placeholder="请选择被委托人">
                    <el-option
                      v-for="option in delegateOptions"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="授权范围">
                  <el-select v-model="delegationForm.scope_type">
                    <el-option
                      v-for="option in DELEGATION_SCOPE_OPTIONS"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="范围部门">
                  <el-select v-model="delegationForm.scope_department_id" placeholder="可选">
                    <el-option
                      v-for="department in departments"
                      :key="department.id"
                      :label="department.name"
                      :value="department.id"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item label="开始时间">
                  <el-date-picker v-model="delegationForm.starts_at" type="datetime" placeholder="选择时间" />
                </el-form-item>
                <el-form-item label="结束时间">
                  <el-date-picker v-model="delegationForm.ends_at" type="datetime" placeholder="选择时间" />
                </el-form-item>
              </div>
              <div class="page__actions">
                <el-button
                  type="primary"
                  :loading="delegationSubmitting"
                  @click="handleCreateDelegation"
                >
                  创建授权
                </el-button>
              </div>
            </el-form>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-empty v-else class="page__empty" description="当前没有可查看的档案" />

    <el-dialog v-model="createDialogVisible" title="新建档案" width="640px" @closed="resetCreateForm">
      <el-form label-position="top">
        <el-form-item label="用户">
          <el-select v-model="createForm.user_id" placeholder="请选择用户">
            <el-option
              v-for="user in availableUsers"
              :key="user.id"
              :label="user.email"
              :value="user.id"
            />
          </el-select>
        </el-form-item>
        <div class="page__grid page__grid--two">
          <el-form-item label="员工编号">
            <el-input v-model="createForm.employee_no" />
          </el-form-item>
          <el-form-item label="姓名">
            <el-input v-model="createForm.real_name" />
          </el-form-item>
          <el-form-item label="部门">
            <el-select v-model="createForm.department_id" placeholder="请选择部门">
              <el-option
                v-for="department in departments"
                :key="department.id"
                :label="department.name"
                :value="department.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="岗位名称">
            <el-input v-model="createForm.job_title" />
          </el-form-item>
          <el-form-item label="电话">
            <el-input v-model="createForm.phone" />
          </el-form-item>
          <el-form-item label="入职日期">
            <el-date-picker
              v-model="createForm.hire_date"
              type="date"
              value-format="YYYY-MM-DD"
            />
          </el-form-item>
        </div>
        <el-form-item label="动态字段(JSON)">
          <el-input v-model="createForm.custom_fields_text" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="handleCreateProfile">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page__header,
.page__detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page__title {
  font-size: 16px;
  font-weight: 600;
}

.page__subtitle {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.page__detail {
  margin-bottom: 24px;
}

.page__detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.page__grid {
  display: grid;
  gap: 16px;
}

.page__grid--two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.page__grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.page__section {
  margin-top: 16px;
}

.page__actions {
  display: flex;
  justify-content: flex-end;
}

.page__empty {
  padding: 48px 0;
}

@media (max-width: 1200px) {
  .page__grid--three {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .page__grid--two {
    grid-template-columns: 1fr;
  }
}
</style>
