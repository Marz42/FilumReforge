<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { createInvitation } from '@/api/auth'
import { listDepartments } from '@/api/departments'
import { getPeopleManagement, getPeopleManagementDetail } from '@/api/people-management'
import {
  createDelegation,
  createPosition,
  createProfile,
  createProfileEvent,
  createProfilePosition,
  createProfileReportingLine,
  listPositions,
  updateDelegation,
  updateProfile,
} from '@/api/profiles'
import { createUser, deleteUser, updateUser } from '@/api/users'
import type {
  Delegation,
  DelegationScopeType,
  DelegationStatus,
  Department,
  EmploymentEventType,
  PeopleManagementDetail,
  PeopleManagementPerson,
  PeopleManagementSnapshot,
  Position,
  PositionAssignmentType,
  ProfileFieldAccess,
  ReportingLineType,
  UserRole,
  UserInvitation,
  UserStatus,
} from '@/types/api'
import PeopleDetailDrawer from '@/components/people/PeopleDetailDrawer.vue'
import type { PeopleAnchorId } from '@/components/people/PeopleAnchorNav.vue'
import { getErrorMessage } from '@/utils/errors'
import { formatPasswordValidationMessage, validatePasswordClient } from '@/utils/passwordPolicy'
import { formatDate, formatDateTime } from '@/utils/formatters'

type DetailTab = PeopleAnchorId

type SelectionOption = {
  value: string
  label: string
}

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

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detailLoading = ref(false)
const relationSubmitting = ref(false)
const lifecycleSubmitting = ref(false)
const delegationSubmitting = ref(false)
const accountSubmitting = ref(false)
const deleteUserSubmitting = ref(false)
const profileSubmitting = ref(false)
const positionCatalogSubmitting = ref(false)
const createUserSubmitting = ref(false)
const createProfileSubmitting = ref(false)
const positionsLoading = ref(false)
const selectedPersonId = ref('')
const workspace = ref<PeopleManagementSnapshot | null>(null)
const selectedDetail = ref<PeopleManagementDetail | null>(null)
const departments = ref<Department[]>([])
const positions = ref<Position[]>([])

const keyword = ref('')
const roleFilter = ref<'all' | UserRole>('all')
const statusFilter = ref<'all' | UserStatus>('all')
const profileFilter = ref<'all' | 'profiled' | 'unprofiled'>('all')
const departmentFilter = ref<'all' | string>('all')

const createUserDialogVisible = ref(false)
const createProfileDialogVisible = ref(false)
const detailDrawerVisible = ref(false)
const createUserMode = ref<'direct' | 'invite'>('direct')
const createdInvitation = ref<UserInvitation | null>(null)

const createUserForm = reactive({
  email: '',
  password: '',
  role: 'employee' as UserRole,
  status: 'active' as UserStatus,
})

const accountForm = reactive({
  email: '',
  password: '',
  role: 'employee' as UserRole,
  status: 'active' as UserStatus,
})

const createProfileForm = reactive({
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
  department_id: '',
  job_title: '',
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

const people = computed(() => workspace.value?.people ?? [])
const summary = computed(() => workspace.value?.summary)
const selectedProfile = computed(() => selectedDetail.value?.profile ?? null)
const selectedSummary = computed(() => selectedDetail.value?.summary ?? null)
const activeDetailTab = computed<DetailTab>(() => {
  const value = typeof route.query.detailTab === 'string' ? route.query.detailTab : ''
  if (['account', 'profile', 'relations', 'lifecycle', 'permissions'].includes(value)) {
    return value as DetailTab
  }

  if (route.query.tab === 'users') {
    return 'account'
  }
  if (route.query.tab === 'profiles') {
    return 'profile'
  }
  return 'account'
})

const peopleMap = computed(() => new Map(people.value.map((person) => [person.user_id, person])))
const departmentNameMap = computed(
  () => new Map(departments.value.map((department) => [department.id, department.name])),
)
const positionNameMap = computed(
  () => new Map(positions.value.map((position) => [position.id, position.name])),
)

const filteredPeople = computed(() => {
  const keywordValue = keyword.value.trim().toLowerCase()

  return people.value.filter((person) => {
    if (roleFilter.value !== 'all' && person.role !== roleFilter.value) {
      return false
    }
    if (statusFilter.value !== 'all' && person.status !== statusFilter.value) {
      return false
    }
    if (profileFilter.value === 'profiled' && !person.has_profile) {
      return false
    }
    if (profileFilter.value === 'unprofiled' && person.has_profile) {
      return false
    }
    if (departmentFilter.value !== 'all' && person.department_id !== departmentFilter.value) {
      return false
    }
    if (!keywordValue) {
      return true
    }

    return [person.real_name, person.employee_no, person.email, person.department_name, person.job_title]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keywordValue))
  })
})

const selectedPersonLabel = computed(() => {
  return selectedSummary.value?.real_name ?? selectedDetail.value?.account.email ?? '未选择人员'
})

const anchorItems = [
  { id: 'account' as const, label: '账号', testId: 'people-anchor-account' },
  { id: 'profile' as const, label: '档案', testId: 'people-anchor-profile' },
  { id: 'relations' as const, label: '岗位与汇报', testId: 'people-anchor-relations' },
  { id: 'lifecycle' as const, label: '生命周期', testId: 'people-anchor-lifecycle' },
  { id: 'permissions' as const, label: '权限', testId: 'people-anchor-permissions' },
]

const managerOptions = computed<SelectionOption[]>(() =>
  people.value
    .filter((person) => person.status === 'active' && person.user_id !== selectedPersonId.value)
    .map((person) => ({
      value: person.user_id,
      label: person.real_name ? `${person.real_name} (${person.email})` : person.email,
    })),
)

const delegateOptions = computed<SelectionOption[]>(() =>
  people.value
    .filter((person) => person.status === 'active' && person.user_id !== selectedPersonId.value)
    .map((person) => ({
      value: person.user_id,
      label: person.real_name ? `${person.real_name} (${person.email})` : person.email,
    })),
)

const unprofiledPersonOptions = computed<SelectionOption[]>(() =>
  people.value
    .filter((person) => !person.has_profile)
    .map((person) => ({
      value: person.user_id,
      label: person.real_name ? `${person.real_name} (${person.email})` : person.email,
    })),
)

const generalFields = computed(() =>
  (selectedProfile.value?.visible_fields ?? []).filter((field) => !field.is_sensitive),
)
const sensitiveFields = computed(() =>
  (selectedProfile.value?.visible_fields ?? []).filter((field) => field.is_sensitive),
)

function updateRouteQuery(patch: Record<string, string | null>): void {
  const nextQuery = { ...route.query }
  for (const [key, value] of Object.entries(patch)) {
    if (!value) {
      delete nextQuery[key]
    } else {
      nextQuery[key] = value
    }
  }

  void router.replace({
    name: 'people',
    query: nextQuery,
  })
}

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
  const person = peopleMap.value.get(userId)
  if (!person) {
    return `用户 ${userId.slice(0, 8)}`
  }
  return person.real_name ? `${person.real_name} (${person.email})` : person.email
}

function resolveDelegationStatusLabel(status: DelegationStatus): string {
  return DELEGATION_STATUS_LABELS[status]
}

function resolveDelegationStatusTagType(
  status: DelegationStatus,
): '' | 'info' | 'success' | 'warning' | 'danger' {
  return DELEGATION_STATUS_TAG_TYPES[status]
}

function resolveInvitationLifecycleLabel(user: {
  invitation_sent_at?: string | null
  invitation_expires_at?: string | null
  invitation_revoked_at?: string | null
  invitation_accepted_at?: string | null
}): string {
  if (user.invitation_revoked_at) {
    return '已手动撤销'
  }
  if (user.invitation_accepted_at) {
    return '已完成注册（非撤销）'
  }
  if (user.invitation_expires_at && new Date(user.invitation_expires_at).getTime() <= Date.now()) {
    return '已过期'
  }
  if (user.invitation_sent_at) {
    return '待注册'
  }
  return '未使用邀请注册'
}

function resetCreateUserForm(): void {
  createUserMode.value = 'direct'
  createdInvitation.value = null
  createUserForm.email = ''
  createUserForm.password = ''
  createUserForm.role = 'employee'
  createUserForm.status = 'active'
}

function resetCreateProfileForm(userId?: string): void {
  createProfileForm.user_id = userId ?? ''
  createProfileForm.employee_no = ''
  createProfileForm.real_name = ''
  createProfileForm.department_id = ''
  createProfileForm.job_title = ''
  createProfileForm.phone = ''
  createProfileForm.hire_date = ''
  createProfileForm.custom_fields_text = '{\n  "skills": []\n}'
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

function parseJsonObject(text: string, fieldLabel: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(text) as unknown
    if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
      throw new Error('not-object')
    }
    return parsed as Record<string, unknown>
  } catch {
    throw new Error(`${fieldLabel} 需要是合法 JSON 对象`)
  }
}

function hydrateForms(detail: PeopleManagementDetail): void {
  accountForm.email = detail.account.email
  accountForm.password = ''
  accountForm.role = detail.account.role
  accountForm.status = detail.account.status

  if (detail.profile) {
    basicForm.employee_no = detail.profile.employee_no ?? ''
    basicForm.real_name = detail.profile.real_name ?? ''
    basicForm.department_id = detail.profile.department_id ?? ''
    basicForm.job_title = detail.profile.job_title ?? ''
    basicForm.phone = detail.profile.phone ?? ''
    basicForm.hire_date = detail.profile.hire_date ?? ''
    basicForm.custom_fields_text = JSON.stringify(detail.profile.custom_fields, null, 2)
    createProfileForm.user_id = detail.account.id
    createProfileForm.real_name = detail.profile.real_name ?? ''
    createProfileForm.department_id = detail.profile.department_id ?? ''
    delegationForm.scope_department_id = detail.profile.department_id ?? ''
    positionForm.department_id = detail.profile.department_id ?? ''
    reportingForm.department_id = detail.profile.department_id ?? ''
  } else {
    basicForm.employee_no = ''
    basicForm.real_name = ''
    basicForm.department_id = ''
    basicForm.job_title = ''
    basicForm.phone = ''
    basicForm.hire_date = ''
    basicForm.custom_fields_text = '{}'
    resetCreateProfileForm(detail.account.id)
  }

  resetPositionForm()
  resetReportingForm()
  resetEventForm()
  resetDelegationForm()
}

async function loadSupportingData(): Promise<void> {
  positionsLoading.value = true
  try {
    const [departmentList, positionList] = await Promise.all([listDepartments(), listPositions()])
    departments.value = departmentList
    positions.value = positionList
  } finally {
    positionsLoading.value = false
  }
}

async function loadSelectedPerson(userId: string): Promise<void> {
  detailLoading.value = true
  try {
    const detail = await getPeopleManagementDetail(userId)
    selectedDetail.value = detail
    selectedPersonId.value = userId
    hydrateForms(detail)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    detailLoading.value = false
  }
}

async function refreshWorkspace(preferredUserId?: string): Promise<void> {
  loading.value = true
  try {
    workspace.value = await getPeopleManagement()
    const requestedRouteUserId =
      typeof route.query.selected === 'string' ? route.query.selected : undefined
    const nextSelectedUserId =
      preferredUserId ??
      requestedRouteUserId ??
      selectedPersonId.value ??
      workspace.value.people[0]?.user_id ??
      ''

    if (!nextSelectedUserId) {
      selectedPersonId.value = ''
      selectedDetail.value = null
      return
    }

    const fallbackUserId = peopleMap.value.has(nextSelectedUserId)
      ? nextSelectedUserId
      : workspace.value.people[0]?.user_id ?? ''

    if (!fallbackUserId) {
      selectedPersonId.value = ''
      selectedDetail.value = null
      return
    }

    await loadSelectedPerson(fallbackUserId)
    if (requestedRouteUserId) {
      detailDrawerVisible.value = true
    }
    updateRouteQuery({
      selected: fallbackUserId,
      detailTab: activeDetailTab.value,
      tab: null,
    })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function selectPerson(userId: string): Promise<void> {
  if (!userId) {
    return
  }

  detailDrawerVisible.value = true
  if (userId !== selectedPersonId.value) {
    await loadSelectedPerson(userId)
  }
  updateRouteQuery({
    selected: userId,
    detailTab: activeDetailTab.value,
    tab: null,
  })
}

function handleDetailAnchorChange(value: DetailTab): void {
  updateRouteQuery({
    selected: selectedPersonId.value || null,
    detailTab: value,
    tab: null,
  })
}

function scrollToAccountSection(): void {
  detailDrawerVisible.value = true
  handleDetailAnchorChange('account')
}

async function handleCreateUser(): Promise<void> {
  createUserSubmitting.value = true
  try {
    createdInvitation.value = null
    if (createUserMode.value === 'invite') {
      const invitation = await createInvitation({
        email: createUserForm.email.trim(),
        role: createUserForm.role,
      })
      createdInvitation.value = invitation
      ElMessage.success('邀请链接已生成')
      await refreshWorkspace(invitation.user.id)
      return
    }

    const passwordValidation = validatePasswordClient(createUserForm.password)
    if (!passwordValidation.valid) {
      ElMessage.error(formatPasswordValidationMessage(passwordValidation.reasons))
      return
    }

    const createdUser = await createUser({
      email: createUserForm.email.trim(),
      password: createUserForm.password,
      role: createUserForm.role,
      status: createUserForm.status,
    })
    ElMessage.success('账号已创建')
    createUserDialogVisible.value = false
    resetCreateUserForm()
    await refreshWorkspace(createdUser.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    createUserSubmitting.value = false
  }
}

async function handleSaveAccount(): Promise<void> {
  if (!selectedDetail.value) {
    return
  }

  accountSubmitting.value = true
  try {
    const nextPassword = accountForm.password.trim()
    if (nextPassword) {
      const passwordValidation = validatePasswordClient(nextPassword)
      if (!passwordValidation.valid) {
        ElMessage.error(formatPasswordValidationMessage(passwordValidation.reasons))
        return
      }
    }

    await updateUser(selectedDetail.value.account.id, {
      email: accountForm.email.trim(),
      password: nextPassword || undefined,
      role: accountForm.role,
      status: accountForm.status,
    })
    ElMessage.success('账号信息已更新')
    await refreshWorkspace(selectedDetail.value.account.id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    accountSubmitting.value = false
  }
}

async function handleDeleteUser(): Promise<void> {
  if (!selectedDetail.value || !selectedDetail.value.actions.can_delete_user) {
    return
  }

  deleteUserSubmitting.value = true
  try {
    await ElMessageBox.confirm(
      `确认删除账号“${selectedDetail.value.account.email}”吗？仅允许删除未建档账号；若已有业务引用将被拒绝。`,
      '删除账号',
      {
        type: 'warning',
        confirmButtonText: '删除',
        cancelButtonText: '取消',
      },
    )
    await deleteUser(selectedDetail.value.account.id)
    ElMessage.success('账号已删除')
    await refreshWorkspace()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    ElMessage.error(getErrorMessage(error))
  } finally {
    deleteUserSubmitting.value = false
  }
}

async function handleCreateProfile(): Promise<void> {
  if (!createProfileForm.user_id) {
    ElMessage.warning('请选择需要建档的账号')
    return
  }

  createProfileSubmitting.value = true
  try {
    const customFields = parseJsonObject(createProfileForm.custom_fields_text, '动态字段')
    const profile = await createProfile({
      user_id: createProfileForm.user_id,
      employee_no: createProfileForm.employee_no.trim(),
      real_name: createProfileForm.real_name.trim(),
      department_id: createProfileForm.department_id,
      job_title: createProfileForm.job_title.trim() || undefined,
      phone: createProfileForm.phone.trim() || undefined,
      hire_date: createProfileForm.hire_date || undefined,
      custom_fields: customFields,
    })
    ElMessage.success('档案已创建')
    createProfileDialogVisible.value = false
    resetCreateProfileForm(profile.user_id)
    await refreshWorkspace(profile.user_id)
    updateRouteQuery({
      selected: profile.user_id,
      detailTab: 'profile',
      tab: null,
    })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    createProfileSubmitting.value = false
  }
}

async function handleSaveProfile(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  profileSubmitting.value = true
  try {
    const customFields = parseJsonObject(basicForm.custom_fields_text, '动态字段')
    await updateProfile(selectedProfile.value.user_id, {
      employee_no: basicForm.employee_no.trim(),
      real_name: basicForm.real_name.trim(),
      department_id: basicForm.department_id || null,
      job_title: basicForm.job_title.trim() || null,
      phone: basicForm.phone.trim() || null,
      hire_date: basicForm.hire_date || null,
      custom_fields: customFields,
    })
    ElMessage.success('档案信息已更新')
    await refreshWorkspace(selectedProfile.value.user_id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    profileSubmitting.value = false
  }
}

async function handleCreatePositionCatalog(): Promise<void> {
  positionCatalogSubmitting.value = true
  try {
    const extraMetadata = parseJsonObject(positionCatalogForm.extra_metadata_text, '岗位扩展配置')
    await createPosition({
      code: positionCatalogForm.code.trim(),
      name: positionCatalogForm.name.trim(),
      level: positionCatalogForm.level.trim() || undefined,
      extra_metadata: extraMetadata,
      is_active: true,
    })
    positions.value = await listPositions()
    resetPositionCatalogForm()
    ElMessage.success('岗位目录已更新')
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

  relationSubmitting.value = true
  try {
    await createProfilePosition(selectedProfile.value.user_id, {
      position_id: positionForm.position_id,
      department_id: positionForm.department_id,
      assignment_type: positionForm.assignment_type,
      is_primary: positionForm.is_primary,
      starts_at: positionForm.starts_at,
      ends_at: positionForm.ends_at || undefined,
    })
    ElMessage.success('任职关系已创建')
    resetPositionForm()
    await refreshWorkspace(selectedProfile.value.user_id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    relationSubmitting.value = false
  }
}

async function handleCreateReportingLine(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  relationSubmitting.value = true
  try {
    await createProfileReportingLine(selectedProfile.value.user_id, {
      manager_user_id: reportingForm.manager_user_id,
      department_id: reportingForm.department_id || null,
      line_type: reportingForm.line_type,
      is_primary: reportingForm.is_primary,
      starts_at: reportingForm.starts_at,
      ends_at: reportingForm.ends_at || undefined,
    })
    ElMessage.success('汇报线已创建')
    resetReportingForm()
    await refreshWorkspace(selectedProfile.value.user_id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    relationSubmitting.value = false
  }
}

async function handleCreateEvent(): Promise<void> {
  if (!selectedProfile.value) {
    return
  }

  lifecycleSubmitting.value = true
  try {
    const payload = parseJsonObject(eventForm.payload_text, '事件载荷')
    await createProfileEvent(selectedProfile.value.user_id, {
      event_type: eventForm.event_type,
      effective_date: eventForm.effective_date,
      title: eventForm.title.trim(),
      summary: eventForm.summary.trim() || undefined,
      payload,
    })
    ElMessage.success('生命周期事件已记录')
    resetEventForm()
    await refreshWorkspace(selectedProfile.value.user_id)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    lifecycleSubmitting.value = false
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
    ElMessage.success('代理授权已创建')
    resetDelegationForm()
    await refreshWorkspace(selectedProfile.value.user_id)
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
    ElMessage.success('代理授权已撤销')
    if (selectedProfile.value) {
      await refreshWorkspace(selectedProfile.value.user_id)
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

function openCreateProfileDialogForSelected(): void {
  if (!selectedDetail.value) {
    return
  }
  resetCreateProfileForm(selectedDetail.value.account.id)
  createProfileDialogVisible.value = true
}

function renderFieldValue(field: ProfileFieldAccess): string {
  if (field.value == null) {
    return '—'
  }
  if (typeof field.value === 'object') {
    return JSON.stringify(field.value)
  }
  return String(field.value)
}

onMounted(async () => {
  await Promise.all([loadSupportingData(), refreshWorkspace()])
})

watch(
  () => route.query.selected,
  async (value) => {
    if (typeof value !== 'string' || !value || !peopleMap.value.has(value)) {
      return
    }
    detailDrawerVisible.value = true
    if (value !== selectedPersonId.value) {
      await loadSelectedPerson(value)
    }
  },
)
</script>

<template>
  <div class="people-workspace">
    <el-row :gutter="16" class="people-workspace__summary">
      <el-col :xs="24" :md="6">
        <el-card shadow="never">
          <div class="summary-card">
            <span>人员总数</span>
            <strong>{{ summary?.total_people ?? 0 }}</strong>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="6">
        <el-card shadow="never">
          <div class="summary-card">
            <span>已建档人数</span>
            <strong>{{ summary?.profiled_people ?? 0 }}</strong>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="6">
        <el-card shadow="never">
          <div class="summary-card">
            <span>未建档账号</span>
            <strong>{{ summary?.unprofiled_people ?? 0 }}</strong>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="6">
        <el-card shadow="never">
          <div class="summary-card">
            <span>非启用账号</span>
            <strong>{{ summary?.inactive_people ?? 0 }}</strong>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="people-workspace__header">
          <div>
            <h3>档案管理 & 用户管理</h3>
            <p>统一查看账号状态、档案信息、任职汇报、生命周期和权限可见结果。</p>
          </div>
          <div class="people-workspace__header-actions">
            <el-button @click="createUserDialogVisible = true">新建账号</el-button>
            <el-button
              v-if="selectedDetail?.actions.can_create_profile"
              type="primary"
              @click="openCreateProfileDialogForSelected"
            >
              补建档案
            </el-button>
          </div>
        </div>
      </template>

      <div class="people-workspace__list-only">
        <el-card shadow="never">
          <template #header>
            <div class="people-workspace__panel-header">
              <span>人员列表</span>
              <el-tag type="info" effect="plain">{{ filteredPeople.length }} / {{ people.length }}</el-tag>
            </div>
          </template>

          <div class="filters">
            <el-input v-model="keyword" placeholder="搜索姓名、邮箱、部门、岗位" clearable />
            <div class="filters__grid">
              <el-select v-model="roleFilter">
                <el-option label="全部角色" value="all" />
                <el-option v-for="option in ROLE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <el-select v-model="statusFilter">
                <el-option label="全部状态" value="all" />
                <el-option
                  v-for="option in STATUS_OPTIONS"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-select v-model="profileFilter">
                <el-option label="全部档案状态" value="all" />
                <el-option label="已建档" value="profiled" />
                <el-option label="未建档" value="unprofiled" />
              </el-select>
              <el-select v-model="departmentFilter">
                <el-option label="全部部门" value="all" />
                <el-option
                  v-for="department in departments"
                  :key="department.id"
                  :label="department.name"
                  :value="department.id"
                />
              </el-select>
            </div>
          </div>

          <el-table
            v-loading="loading"
            :data="filteredPeople"
            stripe
            highlight-current-row
            row-key="user_id"
            @row-click="(row: PeopleManagementPerson) => void selectPerson(row.user_id)"
          >
            <el-table-column label="人员" min-width="220">
              <template #default="{ row }: { row: PeopleManagementPerson }">
                <div class="person-cell">
                  <strong>{{ row.real_name ?? '未建档账号' }}</strong>
                  <span>{{ row.email }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="部门 / 岗位" min-width="180">
              <template #default="{ row }: { row: PeopleManagementPerson }">
                <div class="person-cell">
                  <strong>{{ row.department_name ?? '—' }}</strong>
                  <span>{{ row.job_title ?? '—' }}</span>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="状态" min-width="130">
              <template #default="{ row }: { row: PeopleManagementPerson }">
                <el-tag :type="STATUS_TAG_TYPES[row.status]" size="small">
                  {{ STATUS_LABELS[row.status] }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="建档" min-width="110">
              <template #default="{ row }: { row: PeopleManagementPerson }">
                <el-tag :type="row.has_profile ? 'success' : 'warning'" size="small">
                  {{ row.has_profile ? '已建档' : '未建档' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </el-card>

    <PeopleDetailDrawer
      v-model="detailDrawerVisible"
      :active-anchor="activeDetailTab"
      :loading="detailLoading"
      :person-label="selectedPersonLabel"
      :person-email="selectedDetail?.account.email ?? ''"
      :status-label="selectedDetail ? STATUS_LABELS[selectedDetail.account.status] : ''"
      :status-tag-type="selectedDetail ? STATUS_TAG_TYPES[selectedDetail.account.status] : 'info'"
      :can-create-profile="selectedDetail?.actions.can_create_profile ?? false"
      :anchor-items="anchorItems"
      @update:active-anchor="handleDetailAnchorChange"
      @create-profile="openCreateProfileDialogForSelected"
      @scroll-to-account="scrollToAccountSection"
    >
      <template v-if="selectedDetail">
        <section id="people-section-account" class="people-detail-section" data-people-section="account">
          <h3 class="people-detail-section__title">账号信息</h3>
          <div class="tab-grid tab-grid--two">
                      <el-card shadow="never">
                        <template #header>账号概览</template>
                        <el-descriptions :column="2" border>
                          <el-descriptions-item label="邮箱">
                            {{ selectedDetail.account.email }}
                          </el-descriptions-item>
                          <el-descriptions-item label="角色">
                            {{ ROLE_LABELS[selectedDetail.account.role] }}
                          </el-descriptions-item>
                          <el-descriptions-item label="状态">
                            {{ STATUS_LABELS[selectedDetail.account.status] }}
                          </el-descriptions-item>
                          <el-descriptions-item label="最后登录">
                            {{ formatDateTime(selectedDetail.account.last_login_at) }}
                          </el-descriptions-item>
                          <el-descriptions-item label="是否已建档">
                            {{ selectedDetail.summary.has_profile ? '是' : '否' }}
                          </el-descriptions-item>
                          <el-descriptions-item label="邀请状态">
                            {{ resolveInvitationLifecycleLabel(selectedDetail.account) }}
                          </el-descriptions-item>
                          <el-descriptions-item label="创建时间">
                            {{ formatDateTime(selectedDetail.account.created_at) }}
                          </el-descriptions-item>
                        </el-descriptions>
                      </el-card>

                      <el-card shadow="never">
                        <template #header>编辑账号</template>
                        <el-form label-position="top">
                          <el-form-item label="邮箱">
                            <el-input v-model="accountForm.email" />
                          </el-form-item>
                          <el-form-item label="重置密码">
                            <el-input
                              v-model="accountForm.password"
                              type="password"
                              show-password
                              placeholder="留空则不修改密码"
                            />
                          </el-form-item>
                          <el-form-item label="角色">
                            <el-select v-model="accountForm.role">
                              <el-option
                                v-for="option in ROLE_OPTIONS"
                                :key="option.value"
                                :label="option.label"
                                :value="option.value"
                              />
                            </el-select>
                          </el-form-item>
                          <el-form-item label="状态">
                            <el-select v-model="accountForm.status">
                              <el-option
                                v-for="option in STATUS_OPTIONS"
                                :key="option.value"
                                :label="option.label"
                                :value="option.value"
                              />
                            </el-select>
                          </el-form-item>
                          <p v-if="selectedDetail.actions.can_delete_user" class="page__helper">
                            仅未建档账号支持物理删除；已建档人员请通过状态管理停用或离职。
                          </p>
                          <div class="page__actions page__actions--split">
                            <el-button
                              v-if="selectedDetail.actions.can_delete_user"
                              type="danger"
                              plain
                              :loading="deleteUserSubmitting"
                              @click="handleDeleteUser"
                            >
                              删除未建档账号
                            </el-button>
                            <el-button type="primary" :loading="accountSubmitting" @click="handleSaveAccount">
                              保存账号信息
                            </el-button>
                          </div>
                        </el-form>
                      </el-card>
                    </div>
          </section>

          <section id="people-section-profile" class="people-detail-section" data-people-section="profile">
            <h3 class="people-detail-section__title">档案信息</h3>
                    <el-empty
                      v-if="!selectedProfile"
                      description="当前账号尚未建立档案"
                    >
                      <el-button type="primary" @click="openCreateProfileDialogForSelected">补建档案</el-button>
                    </el-empty>

                    <template v-else>
                      <div class="tab-grid tab-grid--two">
                        <el-card shadow="never">
                          <template #header>档案概览</template>
                          <el-descriptions :column="2" border>
                            <el-descriptions-item label="员工编号">
                              {{ selectedProfile.employee_no ?? '—' }}
                            </el-descriptions-item>
                            <el-descriptions-item label="姓名">
                              {{ selectedProfile.real_name ?? '—' }}
                            </el-descriptions-item>
                            <el-descriptions-item label="部门">
                              {{ resolveDepartmentName(selectedProfile.department_id) }}
                            </el-descriptions-item>
                            <el-descriptions-item label="岗位">
                              {{ selectedProfile.job_title ?? '—' }}
                            </el-descriptions-item>
                            <el-descriptions-item label="电话">
                              {{ selectedProfile.phone ?? '—' }}
                            </el-descriptions-item>
                            <el-descriptions-item label="入职日期">
                              {{ formatDate(selectedProfile.hire_date) }}
                            </el-descriptions-item>
                            <el-descriptions-item label="直属上级">
                              {{ selectedDetail.primary_manager_label ?? '—' }}
                            </el-descriptions-item>
                            <el-descriptions-item label="最近事件">
                              {{ selectedDetail.latest_employment_event?.title ?? '—' }}
                            </el-descriptions-item>
                          </el-descriptions>
                        </el-card>

                        <el-card shadow="never">
                          <template #header>编辑档案</template>
                          <el-form label-position="top">
                            <el-form-item label="员工编号">
                              <el-input v-model="basicForm.employee_no" />
                            </el-form-item>
                            <el-form-item label="姓名">
                              <el-input v-model="basicForm.real_name" />
                            </el-form-item>
                            <el-form-item label="主部门">
                              <el-select v-model="basicForm.department_id">
                                <el-option
                                  v-for="department in departments"
                                  :key="department.id"
                                  :label="department.name"
                                  :value="department.id"
                                />
                              </el-select>
                            </el-form-item>
                            <el-form-item label="岗位">
                              <el-input v-model="basicForm.job_title" />
                            </el-form-item>
                            <el-form-item label="电话">
                              <el-input v-model="basicForm.phone" />
                            </el-form-item>
                            <el-form-item label="入职日期">
                              <el-date-picker
                                v-model="basicForm.hire_date"
                                type="date"
                                value-format="YYYY-MM-DD"
                                placeholder="请选择日期"
                              />
                            </el-form-item>
                            <el-form-item label="动态字段(JSON)">
                              <el-input v-model="basicForm.custom_fields_text" type="textarea" :rows="8" />
                            </el-form-item>
                            <div class="page__actions">
                              <el-button type="primary" :loading="profileSubmitting" @click="handleSaveProfile">
                                保存档案信息
                              </el-button>
                            </div>
                          </el-form>
                        </el-card>
                      </div>
                    </template>
          </section>

          <section id="people-section-relations" class="people-detail-section" data-people-section="relations">
            <h3 class="people-detail-section__title">岗位 / 汇报</h3>
                    <el-empty v-if="!selectedProfile" description="请先建立档案后再维护任职关系" />

                    <template v-else>
                      <div class="tab-grid tab-grid--two">
                        <el-card shadow="never">
                          <template #header>任职记录</template>
                          <el-table :data="selectedProfile.positions" stripe>
                            <el-table-column label="岗位" min-width="160">
                              <template #default="{ row }">
                                {{ resolvePositionName(row.position_id) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="部门" min-width="140">
                              <template #default="{ row }">
                                {{ resolveDepartmentName(row.department_id) }}
                              </template>
                            </el-table-column>
                            <el-table-column prop="assignment_type" label="类型" min-width="110" />
                            <el-table-column label="主任职" min-width="90">
                              <template #default="{ row }">
                                {{ row.is_primary ? '是' : '否' }}
                              </template>
                            </el-table-column>
                            <el-table-column label="开始日期" min-width="120">
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
                            <el-table-column label="部门" min-width="140">
                              <template #default="{ row }">
                                {{ resolveDepartmentName(row.department_id) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="主要汇报" min-width="90">
                              <template #default="{ row }">
                                {{ row.is_primary ? '是' : '否' }}
                              </template>
                            </el-table-column>
                          </el-table>
                        </el-card>
                      </div>

                      <div class="tab-grid tab-grid--three">
                        <el-card shadow="never" v-loading="positionsLoading">
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
                              <el-input v-model="positionCatalogForm.extra_metadata_text" type="textarea" :rows="4" />
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
                              <el-select v-model="positionForm.position_id">
                                <el-option
                                  v-for="position in positions"
                                  :key="position.id"
                                  :label="position.name"
                                  :value="position.id"
                                />
                              </el-select>
                            </el-form-item>
                            <el-form-item label="挂载部门">
                              <el-select v-model="positionForm.department_id">
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
                            <el-form-item label="主任职">
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
                              <el-button type="primary" :loading="relationSubmitting" @click="handleCreatePositionAssignment">
                                新增任职
                              </el-button>
                            </div>
                          </el-form>
                        </el-card>

                        <el-card shadow="never">
                          <template #header>新增汇报线</template>
                          <el-form label-position="top">
                            <el-form-item label="上级">
                              <el-select v-model="reportingForm.manager_user_id">
                                <el-option
                                  v-for="option in managerOptions"
                                  :key="option.value"
                                  :label="option.label"
                                  :value="option.value"
                                />
                              </el-select>
                            </el-form-item>
                            <el-form-item label="关联部门">
                              <el-select v-model="reportingForm.department_id">
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
                            <el-form-item label="主要汇报">
                              <el-switch v-model="reportingForm.is_primary" />
                            </el-form-item>
                            <el-form-item label="开始日期">
                              <el-date-picker
                                v-model="reportingForm.starts_at"
                                type="date"
                                value-format="YYYY-MM-DD"
                              />
                            </el-form-item>
                            <el-form-item label="结束日期">
                              <el-date-picker
                                v-model="reportingForm.ends_at"
                                type="date"
                                value-format="YYYY-MM-DD"
                              />
                            </el-form-item>
                            <div class="page__actions">
                              <el-button type="primary" :loading="relationSubmitting" @click="handleCreateReportingLine">
                                新增汇报线
                              </el-button>
                            </div>
                          </el-form>
                        </el-card>
                      </div>
                    </template>
          </section>

          <section id="people-section-lifecycle" class="people-detail-section" data-people-section="lifecycle">
            <h3 class="people-detail-section__title">生命周期</h3>
                    <el-empty v-if="!selectedProfile" description="请先建立档案后再记录生命周期事件" />

                    <template v-else>
                      <div class="tab-grid tab-grid--two">
                        <el-card shadow="never">
                          <template #header>生命周期事件</template>
                          <el-table :data="selectedProfile.employment_events" stripe>
                            <el-table-column prop="event_type" label="类型" min-width="120" />
                            <el-table-column label="生效日期" min-width="120">
                              <template #default="{ row }">
                                {{ formatDate(row.effective_date) }}
                              </template>
                            </el-table-column>
                            <el-table-column prop="title" label="标题" min-width="220" />
                            <el-table-column prop="summary" label="摘要" min-width="200" />
                          </el-table>
                        </el-card>

                        <el-card shadow="never">
                          <template #header>记录事件</template>
                          <el-form label-position="top">
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
                            <el-form-item label="标题">
                              <el-input v-model="eventForm.title" />
                            </el-form-item>
                            <el-form-item label="摘要">
                              <el-input v-model="eventForm.summary" type="textarea" :rows="3" />
                            </el-form-item>
                            <el-form-item label="扩展载荷(JSON)">
                              <el-input v-model="eventForm.payload_text" type="textarea" :rows="8" />
                            </el-form-item>
                            <div class="page__actions">
                              <el-button type="primary" :loading="lifecycleSubmitting" @click="handleCreateEvent">
                                记录事件
                              </el-button>
                            </div>
                          </el-form>
                        </el-card>
                      </div>
                    </template>
          </section>

          <section id="people-section-permissions" class="people-detail-section" data-people-section="permissions">
            <h3 class="people-detail-section__title">权限视图</h3>
                    <el-empty v-if="!selectedProfile" description="请先建立档案后再查看权限视图" />

                    <template v-else>
                      <div class="tab-grid tab-grid--two">
                        <el-card shadow="never">
                          <template #header>可见字段</template>
                          <el-table :data="generalFields" stripe>
                            <el-table-column prop="label" label="字段" min-width="140" />
                            <el-table-column prop="field_key" label="Key" min-width="140" />
                            <el-table-column label="值" min-width="200">
                              <template #default="{ row }: { row: ProfileFieldAccess }">
                                {{ renderFieldValue(row) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="可编辑" min-width="100">
                              <template #default="{ row }: { row: ProfileFieldAccess }">
                                {{ row.can_edit ? '是' : '否' }}
                              </template>
                            </el-table-column>
                          </el-table>
                        </el-card>

                        <el-card shadow="never">
                          <template #header>敏感字段</template>
                          <el-table :data="sensitiveFields" stripe>
                            <el-table-column prop="label" label="字段" min-width="140" />
                            <el-table-column prop="field_key" label="Key" min-width="140" />
                            <el-table-column label="值" min-width="200">
                              <template #default="{ row }: { row: ProfileFieldAccess }">
                                {{ renderFieldValue(row) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="可编辑" min-width="100">
                              <template #default="{ row }: { row: ProfileFieldAccess }">
                                {{ row.can_edit ? '是' : '否' }}
                              </template>
                            </el-table-column>
                          </el-table>
                        </el-card>
                      </div>

                      <div class="tab-grid tab-grid--two">
                        <el-card shadow="never">
                          <template #header>代理授权</template>
                          <el-table :data="selectedProfile.delegations" stripe>
                            <el-table-column label="被委托人" min-width="180">
                              <template #default="{ row }">
                                {{ resolveUserLabel(row.delegate_user_id) }}
                              </template>
                            </el-table-column>
                            <el-table-column prop="scope_type" label="范围" min-width="110" />
                            <el-table-column label="状态" min-width="110">
                              <template #default="{ row }">
                                <el-tag :type="resolveDelegationStatusTagType(row.status)">
                                  {{ resolveDelegationStatusLabel(row.status) }}
                                </el-tag>
                              </template>
                            </el-table-column>
                            <el-table-column label="有效期" min-width="220">
                              <template #default="{ row }">
                                {{ formatDateTime(row.starts_at) }} ~ {{ formatDateTime(row.ends_at) }}
                              </template>
                            </el-table-column>
                            <el-table-column label="操作" width="100">
                              <template #default="{ row }: { row: Delegation }">
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

                        <el-card shadow="never">
                          <template #header>创建代理授权</template>
                          <el-form label-position="top">
                            <el-form-item label="被委托人">
                              <el-select v-model="delegationForm.delegate_user_id">
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
                            <div class="page__actions">
                              <el-button type="primary" :loading="delegationSubmitting" @click="handleCreateDelegation">
                                创建授权
                              </el-button>
                            </div>
                          </el-form>
                        </el-card>
                      </div>
                    </template>
          </section>
      </template>
    </PeopleDetailDrawer>

    <el-dialog
      v-model="createUserDialogVisible"
      title="新建账号"
      width="520px"
      :teleported="false"
      @closed="resetCreateUserForm"
    >
      <el-form label-position="top">
        <el-form-item label="开通方式">
          <el-radio-group v-model="createUserMode">
            <el-radio-button value="direct">直接创建</el-radio-button>
            <el-radio-button value="invite">邀请注册</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="createUserForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item v-if="createUserMode === 'direct'" label="初始密码">
          <el-input
            v-model="createUserForm.password"
            type="password"
            show-password
            placeholder="请输入初始密码"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="createUserForm.role">
            <el-option v-for="option in ROLE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="createUserMode === 'direct'" label="状态">
          <el-select v-model="createUserForm.status">
            <el-option
              v-for="option in STATUS_OPTIONS"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-alert
          v-if="createUserMode === 'invite'"
          title="将创建一个未启用账号并生成邀请注册链接；用户通过链接设置密码后自动激活。"
          type="info"
          :closable="false"
          show-icon
        />
        <el-form-item v-if="createdInvitation" label="邀请链接" class="people-management__invite-result">
          <el-input :model-value="createdInvitation.invite_url" readonly />
          <small>有效期至 {{ createdInvitation.expires_at }}</small>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createUserDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createUserSubmitting" @click="handleCreateUser">
          {{ createUserMode === 'invite' ? '生成邀请' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="createProfileDialogVisible"
      title="补建档案"
      width="640px"
      :teleported="false"
      @closed="resetCreateProfileForm(selectedPersonId)"
    >
      <el-form label-position="top">
        <el-form-item label="目标账号">
          <el-select v-model="createProfileForm.user_id">
            <el-option
              v-for="option in unprofiledPersonOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="员工编号">
          <el-input v-model="createProfileForm.employee_no" />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="createProfileForm.real_name" />
        </el-form-item>
        <el-form-item label="主部门">
          <el-select v-model="createProfileForm.department_id">
            <el-option
              v-for="department in departments"
              :key="department.id"
              :label="department.name"
              :value="department.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位">
          <el-input v-model="createProfileForm.job_title" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="createProfileForm.phone" />
        </el-form-item>
        <el-form-item label="入职日期">
          <el-date-picker
            v-model="createProfileForm.hire_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="请选择日期"
          />
        </el-form-item>
        <el-form-item label="动态字段(JSON)">
          <el-input v-model="createProfileForm.custom_fields_text" type="textarea" :rows="8" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createProfileDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createProfileSubmitting" @click="handleCreateProfile">创建档案</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.people-workspace {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.people-workspace__summary {
  margin-bottom: 4px;
}

.people-workspace__header,
.people-workspace__detail-header,
.people-workspace__panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.people-workspace__header h3,
.page__title {
  margin: 0;
}

.people-workspace__header p,
.page__subtitle {
  margin: 8px 0 0;
  color: #606266;
}

.people-workspace__header-actions,
.people-workspace__detail-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}

.people-workspace__list-only,
.people-workspace__body,
.people-workspace__column {
  min-height: 100%;
}

.filters {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.filters__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
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

.person-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.person-cell strong {
  font-weight: 600;
}

.person-cell span {
  color: #606266;
  font-size: 13px;
}

.tab-grid {
  display: grid;
  gap: 16px;
  margin-bottom: 16px;
}

.tab-grid--two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.tab-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.page__actions {
  display: flex;
  justify-content: flex-end;
}

.page__actions--split {
  justify-content: space-between;
  gap: 12px;
}

.page__helper {
  margin: 0 0 12px;
  color: #606266;
  font-size: 13px;
}

.people-management__invite-result :deep(small) {
  display: block;
  margin-top: 8px;
  color: var(--filum-text-secondary);
}

@media (max-width: 1200px) {
  .tab-grid--two,
  .tab-grid--three,
  .filters__grid {
    grid-template-columns: 1fr;
  }
}
</style>
