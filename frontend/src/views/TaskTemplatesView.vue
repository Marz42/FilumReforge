<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { listDepartments } from '@/api/departments'
import {
  type TaskTemplateStepPayload,
  createTaskSchedule,
  createTaskTemplate,
  deleteTaskTemplate,
  instantiateTaskTemplate,
  listTaskSchedules,
  listTaskTemplateInstances,
  listTaskTemplates,
  updateTaskSchedule,
  updateTaskTemplate,
} from '@/api/task-templates'
import { listUsers } from '@/api/users'
import { useAuthStore } from '@/stores/auth'
import type {
  Department,
  Task,
  TaskCenterDepartmentOption,
  TaskSchedule,
  TaskTemplate,
  TaskTemplateInstance,
  User,
} from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatDateTime } from '@/utils/formatters'

interface Props {
  canManageTemplates?: boolean
  canPublishTask?: boolean
  departmentOptions?: TaskCenterDepartmentOption[]
}

type StepAssigneeRuleType = 'initiator' | 'department_manager' | 'department_members' | 'user' | 'user_ids'
type StepAssignmentMode = 'single' | 'fan_out'
type StepJoinMode = 'all' | 'any'

interface StepFormState {
  step_key: string
  title: string
  description: string
  step_type: string
  assignment_mode: StepAssignmentMode
  join_mode: StepJoinMode
  assignee_rule_type: StepAssigneeRuleType
  assignee_user_id: string
  assignee_user_ids: string[]
  default_due_offset_hours?: number
  depends_on_step_keys: string[]
  approval_type: string
  reject_target_step_key: string
  downstream_template_code: string
  downstream_spawn_mode: string
  downstream_spawn_source_step_key: string
}

const authStore = useAuthStore()
const props = withDefaults(defineProps<Props>(), {
  canManageTemplates: undefined,
  canPublishTask: undefined,
  departmentOptions: undefined,
})

const loading = ref(false)
const instancesLoading = ref(false)
const createDialogVisible = ref(false)
const importDialogVisible = ref(false)
const createSubmitting = ref(false)
const instantiateSubmitting = ref(false)
const scheduleSubmitting = ref(false)
const templateStatusSubmitting = ref(false)
const templates = ref<TaskTemplate[]>([])
const templateInstances = ref<TaskTemplateInstance[]>([])
const schedules = ref<TaskSchedule[]>([])
const departments = ref<Department[]>([])
const users = ref<User[]>([])
const templateDialogMode = ref<'create' | 'edit'>('create')
const scheduleFormMode = ref<'create' | 'edit'>('create')
const editingTemplateId = ref('')
const editingScheduleId = ref('')
const selectedTemplateId = ref('')
const selectedTemplateInstanceId = ref('')
const importStepsText = ref('[]')

let stepDraftSeed = 0

function nextStepKey(prefix = 'step'): string {
  stepDraftSeed += 1
  return `${prefix}_${stepDraftSeed}`
}

function createStepState(overrides: Partial<StepFormState> = {}): StepFormState {
  return {
    step_key: overrides.step_key?.trim() || nextStepKey(),
    title: overrides.title ?? `步骤 ${stepDraftSeed}`,
    description: overrides.description ?? '',
    step_type: overrides.step_type ?? 'task',
    assignment_mode: overrides.assignment_mode ?? 'single',
    join_mode: overrides.join_mode ?? 'all',
    assignee_rule_type: overrides.assignee_rule_type ?? 'initiator',
    assignee_user_id: overrides.assignee_user_id ?? '',
    assignee_user_ids: [...(overrides.assignee_user_ids ?? [])],
    default_due_offset_hours: overrides.default_due_offset_hours,
    depends_on_step_keys: [...(overrides.depends_on_step_keys ?? [])],
    approval_type: overrides.approval_type ?? 'none',
    reject_target_step_key: overrides.reject_target_step_key ?? '',
    downstream_template_code: overrides.downstream_template_code ?? '',
    downstream_spawn_mode: overrides.downstream_spawn_mode ?? 'single',
    downstream_spawn_source_step_key: overrides.downstream_spawn_source_step_key ?? '',
  }
}

const createForm = reactive({
  code: '',
  name: '',
  category: 'ops',
  description: '',
  steps: [createStepState({ step_key: 'draft', title: '发起执行' })] as StepFormState[],
})

const instantiateForm = reactive({
  department_id: '',
})

const scheduleForm = reactive({
  template_id: '',
  cron_expr: '0 9 * * 1-5',
  timezone: 'UTC',
  payloadText: '{}',
  is_active: true,
})

const selectedTemplate = computed(
  () => templates.value.find((template) => template.id === selectedTemplateId.value) ?? null,
)
const selectedTemplateInstance = computed(
  () =>
    templateInstances.value.find((instance) => instance.id === selectedTemplateInstanceId.value)
    ?? templateInstances.value[0]
    ?? null,
)
const selectedInstanceTasks = computed(() =>
  selectedTemplateInstance.value
    ? selectedTemplateInstance.value.step_snapshots.flatMap((snapshot) =>
        snapshot.step_runs
          .map((stepRun) => stepRun.task)
          .filter((task): task is Task => task !== null),
      )
    : [],
)
const isEditingTemplate = computed(() => templateDialogMode.value === 'edit')
const templateDialogTitle = computed(() => (isEditingTemplate.value ? '编辑模板' : '新建模板'))
const templateDialogSubmitLabel = computed(() => (isEditingTemplate.value ? '更新模板' : '保存模板'))
const templateStructureLocked = computed(() => isEditingTemplate.value && templateInstances.value.length > 0)
const isEditingSchedule = computed(() => scheduleFormMode.value === 'edit')
const scheduleSubmitLabel = computed(() => (isEditingSchedule.value ? '更新调度' : '创建调度'))
const canManageTemplates = computed(() => props.canManageTemplates ?? authStore.isManagementRole)
const canPublishTask = computed(() => props.canPublishTask ?? authStore.isManagementRole)
const instantiateDepartmentOptions = computed(() => {
  if (props.departmentOptions && props.departmentOptions.length > 0) {
    return props.departmentOptions
  }
  return departments.value.map((department) => ({
    id: department.id,
    label: department.name,
  }))
})
const userOptions = computed(() =>
  users.value.map((user) => ({
    id: user.id,
    label: user.email,
  })),
)
const assigneeRuleOptions = computed(() => {
  const options = [
    { value: 'initiator', label: '发起人' },
    { value: 'department_manager', label: '部门负责人' },
    { value: 'department_members', label: '部门全员' },
  ]
  if (userOptions.value.length > 0) {
    options.push(
      { value: 'user', label: '指定单人' },
      { value: 'user_ids', label: '指定多人' },
    )
  }
  return options
})
const stepsJsonPreview = computed(() => JSON.stringify(buildStepPayloads(false), null, 2))

function normalizeAssignmentMode(value: unknown): StepAssignmentMode {
  return value === 'fan_out' ? 'fan_out' : 'single'
}

function normalizeJoinMode(value: unknown): StepJoinMode {
  return value === 'any' ? 'any' : 'all'
}

function createStepStateFromPayload(payload: TaskTemplateStepPayload, index: number): StepFormState {
  const assignmentMode = normalizeAssignmentMode(payload.assignment_mode)
  const joinMode = assignmentMode === 'single' ? 'all' : normalizeJoinMode(payload.join_mode)
  const defaultAssigneeRule = payload.default_assignee_rule ?? {}
  let assigneeRuleType = String(defaultAssigneeRule.type ?? 'initiator') as StepAssigneeRuleType
  if (!['initiator', 'department_manager', 'department_members', 'user', 'user_ids'].includes(assigneeRuleType)) {
    assigneeRuleType = 'initiator'
  }

  let assigneeUserId = typeof defaultAssigneeRule.user_id === 'string' ? defaultAssigneeRule.user_id : ''
  let assigneeUserIds = Array.isArray(defaultAssigneeRule.user_ids)
    ? defaultAssigneeRule.user_ids.map((value) => String(value)).filter(Boolean)
    : []
  if (assignmentMode === 'fan_out' && assigneeRuleType === 'user' && assigneeUserId) {
    assigneeRuleType = 'user_ids'
    assigneeUserIds = [assigneeUserId]
    assigneeUserId = ''
  }
  if (assignmentMode === 'single' && assigneeRuleType === 'user_ids' && assigneeUserIds.length === 1) {
    assigneeRuleType = 'user'
    assigneeUserId = assigneeUserIds[0] ?? ''
    assigneeUserIds = []
  }

  return createStepState({
    step_key:
      typeof payload.step_key === 'string' && payload.step_key.trim()
        ? payload.step_key.trim()
        : `step_${index + 1}`,
    title:
      typeof payload.title === 'string' && payload.title.trim()
        ? payload.title.trim()
        : `步骤 ${index + 1}`,
    description: typeof payload.description === 'string' ? payload.description : '',
    step_type:
      typeof payload.step_type === 'string' && payload.step_type.trim()
        ? payload.step_type
        : 'task',
    assignment_mode: assignmentMode,
    join_mode: joinMode,
    assignee_rule_type: assigneeRuleType,
    assignee_user_id: assigneeUserId,
    assignee_user_ids: assigneeUserIds,
    default_due_offset_hours:
      typeof payload.default_due_offset_hours === 'number' ? payload.default_due_offset_hours : undefined,
    depends_on_step_keys: Array.isArray(payload.depends_on_step_keys)
      ? payload.depends_on_step_keys.map((value) => String(value)).filter(Boolean)
      : [],
    approval_type: typeof payload.approval_type === 'string' ? payload.approval_type : 'none',
    reject_target_step_key:
      typeof payload.reject_target_step_key === 'string' ? payload.reject_target_step_key : '',
    downstream_template_code:
      typeof payload.downstream_trigger?.template_code === 'string'
        ? payload.downstream_trigger.template_code
        : '',
    downstream_spawn_mode:
      typeof payload.downstream_trigger?.spawn_mode === 'string'
        ? payload.downstream_trigger.spawn_mode
        : 'single',
    downstream_spawn_source_step_key:
      typeof payload.downstream_trigger?.spawn_source_step_key === 'string'
        ? payload.downstream_trigger.spawn_source_step_key
        : '',
  })
}

function parseJsonValue<T>(text: string, fallback: T): T {
  if (!text.trim()) {
    return fallback
  }
  return JSON.parse(text) as T
}

function normalizeStepOrder(): void {
  createForm.steps = createForm.steps.map((step) => ({
    ...step,
    depends_on_step_keys: step.depends_on_step_keys.filter((value) => value !== step.step_key),
  }))
}

function syncStepDraftSeed(steps: StepFormState[]): void {
  const maxNumericSuffix = steps.reduce((maxValue, step) => {
    const match = step.step_key.match(/_(\d+)$/)
    return Math.max(maxValue, match ? Number(match[1]) : 0)
  }, 0)
  stepDraftSeed = Math.max(maxNumericSuffix, steps.length)
}

function resetCreateForm(): void {
  templateDialogMode.value = 'create'
  editingTemplateId.value = ''
  createForm.code = ''
  createForm.name = ''
  createForm.category = 'ops'
  createForm.description = ''
  createForm.steps = [createStepState({ step_key: 'draft', title: '发起执行' })]
  importStepsText.value = '[]'
  syncStepDraftSeed(createForm.steps)
}

function resetScheduleForm(): void {
  scheduleFormMode.value = 'create'
  editingScheduleId.value = ''
  scheduleForm.template_id = selectedTemplateId.value || templates.value[0]?.id || ''
  scheduleForm.cron_expr = '0 9 * * 1-5'
  scheduleForm.timezone = 'UTC'
  scheduleForm.payloadText = '{}'
  scheduleForm.is_active = true
}

function populateTemplateForm(template: TaskTemplate): void {
  templateDialogMode.value = 'edit'
  editingTemplateId.value = template.id
  createForm.code = template.code
  createForm.name = template.name
  createForm.category = template.category
  createForm.description = template.description ?? ''
  createForm.steps = template.steps.map((step, index) =>
    createStepStateFromPayload(
      {
        step_key: step.step_key,
        title: step.title,
        description: step.description,
        step_type: step.step_type,
        assignment_mode: step.assignment_mode,
        join_mode: step.join_mode,
        default_assignee_rule: step.default_assignee_rule,
        default_due_offset_hours: step.default_due_offset_hours,
        sort_order: step.sort_order,
        config: step.config,
        depends_on_step_keys: step.depends_on_step_keys,
        approval_type: step.approval_type,
        reject_target_step_key: step.reject_target_step_key,
        downstream_trigger: step.downstream_trigger ?? undefined,
      },
      index,
    ),
  )
  syncStepDraftSeed(createForm.steps)
}

function openCreateDialog(): void {
  resetCreateForm()
  createDialogVisible.value = true
}

function openEditDialog(): void {
  if (!selectedTemplate.value) {
    ElMessage.warning('请先选择模板')
    return
  }
  populateTemplateForm(selectedTemplate.value)
  createDialogVisible.value = true
}

function openEditSchedule(schedule: TaskSchedule): void {
  scheduleFormMode.value = 'edit'
  editingScheduleId.value = schedule.id
  scheduleForm.template_id = schedule.template_id
  scheduleForm.cron_expr = schedule.cron_expr
  scheduleForm.timezone = schedule.timezone
  scheduleForm.payloadText = JSON.stringify(schedule.payload ?? {}, null, 2)
  scheduleForm.is_active = schedule.is_active
}

function openImportDialog(): void {
  importStepsText.value = stepsJsonPreview.value
  importDialogVisible.value = true
}

function addStep(): void {
  createForm.steps.push(
    createStepState({
      title: `步骤 ${createForm.steps.length + 1}`,
    }),
  )
  normalizeStepOrder()
}

function duplicateStep(index: number): void {
  const sourceStep = createForm.steps[index]
  if (!sourceStep) {
    return
  }
  createForm.steps.splice(
    index + 1,
    0,
    createStepState({
      step_key: nextStepKey(`${sourceStep.step_key || 'step'}_copy`),
      title: `${sourceStep.title || `步骤 ${index + 1}`} 副本`,
      description: sourceStep.description,
      step_type: sourceStep.step_type,
      assignment_mode: sourceStep.assignment_mode,
      join_mode: sourceStep.join_mode,
      assignee_rule_type: sourceStep.assignee_rule_type,
      assignee_user_id: sourceStep.assignee_user_id,
      assignee_user_ids: [...sourceStep.assignee_user_ids],
      default_due_offset_hours: sourceStep.default_due_offset_hours,
      depends_on_step_keys: [...sourceStep.depends_on_step_keys],
    }),
  )
  normalizeStepOrder()
}

function removeStep(index: number): void {
  if (createForm.steps.length <= 1) {
    ElMessage.warning('模板至少保留一个步骤')
    return
  }
  const removedStepKey = createForm.steps[index]?.step_key
  createForm.steps.splice(index, 1)
  if (removedStepKey) {
    createForm.steps.forEach((step) => {
      step.depends_on_step_keys = step.depends_on_step_keys.filter((value) => value !== removedStepKey)
    })
  }
  normalizeStepOrder()
}

function moveStep(index: number, direction: -1 | 1): void {
  const targetIndex = index + direction
  if (targetIndex < 0 || targetIndex >= createForm.steps.length) {
    return
  }
  const currentStep = createForm.steps[index]
  const targetStep = createForm.steps[targetIndex]
  if (!currentStep || !targetStep) {
    return
  }
  createForm.steps[index] = targetStep
  createForm.steps[targetIndex] = currentStep
  normalizeStepOrder()
}

function handleAssignmentModeChange(step: StepFormState): void {
  if (step.assignment_mode === 'single') {
    step.join_mode = 'all'
    if (step.assignee_rule_type === 'user_ids' && step.assignee_user_ids.length === 1) {
      step.assignee_rule_type = 'user'
      step.assignee_user_id = step.assignee_user_ids[0] ?? ''
      step.assignee_user_ids = []
    }
    return
  }
  if (step.assignee_rule_type === 'user' && step.assignee_user_id) {
    step.assignee_rule_type = 'user_ids'
    step.assignee_user_ids = [step.assignee_user_id]
    step.assignee_user_id = ''
  }
}

function handleAssigneeRuleTypeChange(step: StepFormState): void {
  if (step.assignee_rule_type !== 'user') {
    step.assignee_user_id = ''
  }
  if (step.assignee_rule_type !== 'user_ids') {
    step.assignee_user_ids = []
  }
  if (step.assignee_rule_type === 'department_members') {
    step.assignment_mode = 'fan_out'
  }
  if (step.assignment_mode === 'fan_out' && step.assignee_rule_type === 'user') {
    step.assignee_rule_type = 'user_ids'
  }
}

function getDependencyOptions(currentStepKey: string): Array<{ value: string; label: string }> {
  return createForm.steps
    .filter((step) => step.step_key !== currentStepKey)
    .map((step) => ({
      value: step.step_key,
      label: `${step.step_key} · ${step.title || '未命名步骤'}`,
    }))
}

function parseImportedSteps(text: string): TaskTemplateStepPayload[] {
  const parsed = parseJsonValue<unknown>(text, [])
  if (!Array.isArray(parsed)) {
    throw new Error('导入内容必须是步骤数组 JSON')
  }
  if (parsed.length === 0) {
    throw new Error('至少需要导入一个步骤')
  }
  return parsed.map((item, index) => {
    if (!item || typeof item !== 'object') {
      throw new Error(`第 ${index + 1} 个步骤不是合法对象`)
    }
    return item as TaskTemplateStepPayload
  })
}

function handleImportSteps(): void {
  try {
    const importedSteps = parseImportedSteps(importStepsText.value)
    createForm.steps = importedSteps.map((step, index) => createStepStateFromPayload(step, index))
    syncStepDraftSeed(createForm.steps)
    importDialogVisible.value = false
    ElMessage.success(`已导入 ${importedSteps.length} 个步骤`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : getErrorMessage(error))
  }
}

function buildAssigneeRule(step: StepFormState, strict: boolean): Record<string, unknown> {
  if (step.assignee_rule_type === 'user') {
    if (!step.assignee_user_id) {
      if (strict) {
        throw new Error(`步骤「${step.title || step.step_key}」需要选择负责人`)
      }
      return { type: 'initiator' }
    }
    return { type: 'user', user_id: step.assignee_user_id }
  }
  if (step.assignee_rule_type === 'user_ids') {
    const userIds = step.assignee_user_ids.filter(Boolean)
    if (userIds.length === 0) {
      if (strict) {
        throw new Error(`步骤「${step.title || step.step_key}」需要至少选择一位负责人`)
      }
      return { type: 'initiator' }
    }
    return { type: 'user_ids', user_ids: userIds }
  }
  if (step.assignee_rule_type === 'department_manager') {
    return { type: 'department_manager' }
  }
  if (step.assignee_rule_type === 'department_members') {
    return { type: 'department_members' }
  }
  return { type: 'initiator' }
}

function buildStepPayloads(strict: boolean): TaskTemplateStepPayload[] {
  const availableStepKeys = new Set(
    createForm.steps
      .map((step, index) => step.step_key.trim() || `step_${index + 1}`)
      .filter(Boolean),
  )
  const seenStepKeys = new Set<string>()

  return createForm.steps.map((step, index) => {
    const stepKey = step.step_key.trim() || `step_${index + 1}`
    const title = step.title.trim() || `步骤 ${index + 1}`
    if (strict && !step.step_key.trim()) {
      throw new Error(`第 ${index + 1} 个步骤缺少步骤编码`)
    }
    if (strict && !step.title.trim()) {
      throw new Error(`步骤 ${stepKey} 缺少步骤名称`)
    }
    if (strict && seenStepKeys.has(stepKey)) {
      throw new Error(`步骤编码 ${stepKey} 重复`)
    }
    seenStepKeys.add(stepKey)
    return {
      step_key: stepKey,
      title,
      description: step.description.trim() || null,
      step_type: step.step_type,
      assignment_mode: step.assignment_mode,
      join_mode: step.assignment_mode === 'single' ? 'all' : step.join_mode,
      default_assignee_rule: buildAssigneeRule(step, strict),
      default_due_offset_hours: step.default_due_offset_hours ?? null,
      sort_order: index + 1,
      config: {},
      depends_on_step_keys: step.depends_on_step_keys.filter(
        (value) => value !== stepKey && availableStepKeys.has(value),
      ),
      approval_type: step.approval_type || 'none',
      reject_target_step_key:
        step.approval_type !== 'none' && step.reject_target_step_key.trim()
          ? step.reject_target_step_key.trim()
          : null,
      downstream_trigger:
        step.downstream_template_code.trim()
          ? {
              template_code: step.downstream_template_code.trim(),
              trigger_condition: 'approved',
              spawn_mode: step.downstream_spawn_mode || 'single',
              ...(step.downstream_spawn_mode === 'per_step_run' && step.downstream_spawn_source_step_key.trim()
                ? { spawn_source_step_key: step.downstream_spawn_source_step_key.trim() }
                : {}),
            }
          : null,
    }
  })
}

function formatAssigneeRule(rule: Record<string, unknown>): string {
  const ruleType = String(rule.type ?? 'initiator')
  if (ruleType === 'department_manager') {
    return '部门负责人'
  }
  if (ruleType === 'department_members') {
    return '部门全员'
  }
  if (ruleType === 'user') {
    return '指定单人'
  }
  if (ruleType === 'user_ids') {
    return '指定多人'
  }
  return '发起人'
}

function formatStepMode(step: TaskTemplate['steps'][number]): string {
  if (step.assignment_mode === 'fan_out') {
    return step.join_mode === 'any' ? '多人扇出 / 任一完成推进' : '多人扇出 / 全部完成推进'
  }
  return '单任务步骤'
}

function formatTemplateInstanceStatus(status: TaskTemplateInstance['status']): string {
  if (status === 'completed') {
    return '已完成'
  }
  if (status === 'cancelled') {
    return '已取消'
  }
  return '进行中'
}

function resolveTemplateInstanceTagType(
  status: TaskTemplateInstance['status'],
): 'success' | 'info' | 'warning' {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'cancelled') {
    return 'info'
  }
  return 'warning'
}

function formatStepSnapshotStatus(
  status: TaskTemplateInstance['step_snapshots'][number]['status'],
): string {
  if (status === 'completed') {
    return '已完成'
  }
  if (status === 'active') {
    return '进行中'
  }
  if (status === 'ready') {
    return '待激活'
  }
  return '未激活'
}

function resolveStepSnapshotTagType(
  status: TaskTemplateInstance['step_snapshots'][number]['status'],
): 'success' | 'info' | 'warning' {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'active') {
    return 'warning'
  }
  return 'info'
}

function formatStepRunStatus(
  status: TaskTemplateInstance['step_snapshots'][number]['step_runs'][number]['status'],
): string {
  if (status === 'completed') {
    return '已完成'
  }
  if (status === 'skipped') {
    return '已跳过'
  }
  if (status === 'cancelled') {
    return '已取消'
  }
  return '执行中'
}

function resolveStepRunTagType(
  status: TaskTemplateInstance['step_snapshots'][number]['step_runs'][number]['status'],
): 'success' | 'info' | 'warning' {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'active') {
    return 'warning'
  }
  return 'info'
}

function formatTaskStatus(status: Task['status']): string {
  if (status === 'done') {
    return '已完成'
  }
  if (status === 'review') {
    return '评审中'
  }
  if (status === 'doing') {
    return '进行中'
  }
  return '待办'
}

function formatStepSnapshotProgress(snapshot: TaskTemplateInstance['step_snapshots'][number]): string {
  if (snapshot.total_run_count === 0) {
    return snapshot.status === 'blocked' ? '等待前置步骤完成' : '等待激活'
  }
  return `完成 ${snapshot.completed_run_count}/${snapshot.total_run_count}`
}

function formatTemplateInstanceOptionLabel(instance: TaskTemplateInstance): string {
  const labelParts = [formatDateTime(instance.created_at), formatTemplateInstanceStatus(instance.status)]
  if (instance.initiator_email) {
    labelParts.push(instance.initiator_email)
  }
  return labelParts.join(' · ')
}

async function loadTemplateInstances(templateId: string, preferredInstanceId?: string): Promise<void> {
  if (!templateId) {
    templateInstances.value = []
    selectedTemplateInstanceId.value = ''
    return
  }

  instancesLoading.value = true
  try {
    const instances = await listTaskTemplateInstances(templateId)
    templateInstances.value = instances
    if (preferredInstanceId && instances.some((instance) => instance.id === preferredInstanceId)) {
      selectedTemplateInstanceId.value = preferredInstanceId
    } else {
      selectedTemplateInstanceId.value = instances[0]?.id ?? ''
    }
  } catch (error) {
    templateInstances.value = []
    selectedTemplateInstanceId.value = ''
    ElMessage.error(getErrorMessage(error))
  } finally {
    instancesLoading.value = false
  }
}

async function handleTemplateSelection(templateId: string): Promise<void> {
  selectedTemplateId.value = templateId
  await loadTemplateInstances(templateId)
}

async function loadData(): Promise<void> {
  loading.value = true
  try {
    const [templateList, scheduleList, departmentList, userList] = await Promise.all([
      listTaskTemplates(),
      canManageTemplates.value ? listTaskSchedules() : Promise.resolve([] as TaskSchedule[]),
      listDepartments(),
      canManageTemplates.value ? listUsers().catch(() => [] as User[]) : Promise.resolve([] as User[]),
    ])
    templates.value = templateList
    schedules.value = scheduleList
    departments.value = departmentList
    users.value = userList

    const nextSelectedTemplateId =
      selectedTemplateId.value && templateList.some((template) => template.id === selectedTemplateId.value)
        ? selectedTemplateId.value
        : templateList[0]?.id ?? ''
    selectedTemplateId.value = nextSelectedTemplateId
    if (!templateList.some((template) => template.id === scheduleForm.template_id)) {
      scheduleForm.template_id = nextSelectedTemplateId
    }
    await loadTemplateInstances(nextSelectedTemplateId)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading.value = false
  }
}

async function handleSaveTemplate(): Promise<void> {
  createSubmitting.value = true
  try {
    const payload = {
      code: createForm.code.trim(),
      name: createForm.name.trim(),
      category: createForm.category.trim(),
      description: createForm.description || null,
      steps: buildStepPayloads(true),
    }
    const savedTemplate = isEditingTemplate.value
      ? await updateTaskTemplate(editingTemplateId.value, payload)
      : await createTaskTemplate(payload)
    selectedTemplateId.value = savedTemplate.id
    ElMessage.success(isEditingTemplate.value ? '模板已更新' : '模板已创建')
    createDialogVisible.value = false
    resetCreateForm()
    await loadData()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : getErrorMessage(error))
  } finally {
    createSubmitting.value = false
  }
}

async function handleToggleTemplateActive(): Promise<void> {
  if (!selectedTemplate.value) {
    ElMessage.warning('请先选择模板')
    return
  }

  templateStatusSubmitting.value = true
  try {
    const nextActive = !selectedTemplate.value.is_active
    await updateTaskTemplate(selectedTemplate.value.id, { is_active: nextActive })
    ElMessage.success(nextActive ? '模板已启用' : '模板已停用')
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    templateStatusSubmitting.value = false
  }
}

async function handleDeleteTemplate(): Promise<void> {
  if (!selectedTemplate.value) {
    ElMessage.warning('请先选择模板')
    return
  }

  try {
    await ElMessageBox.confirm('删除后无法恢复；若模板已有实例运行记录将被拒绝。是否继续？', '删除模板', {
      type: 'warning',
    })
    await deleteTaskTemplate(selectedTemplate.value.id)
    ElMessage.success('模板已删除')
    await loadData()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return
    }
    if (error instanceof Error && (error.message === 'cancel' || error.message === 'close')) {
      return
    }
    ElMessage.error(getErrorMessage(error))
  }
}

async function handleInstantiateTemplate(): Promise<void> {
  if (!selectedTemplate.value) {
    ElMessage.warning('请先选择模板')
    return
  }
  instantiateSubmitting.value = true
  try {
    const result = await instantiateTaskTemplate(selectedTemplate.value.id, {
      department_id: instantiateForm.department_id || null,
      payload: instantiateForm.department_id
        ? { department_id: instantiateForm.department_id }
        : {},
    })
    templateInstances.value = [
      result.instance,
      ...templateInstances.value.filter((instance) => instance.id !== result.instance.id),
    ]
    selectedTemplateInstanceId.value = result.instance.id
    ElMessage.success(`模板已实例化，激活 ${result.tasks.length} 条任务`)
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    instantiateSubmitting.value = false
  }
}

async function handleSaveSchedule(): Promise<void> {
  if (!scheduleForm.template_id) {
    ElMessage.warning('请选择模板')
    return
  }
  scheduleSubmitting.value = true
  try {
    const payload = {
      cron_expr: scheduleForm.cron_expr.trim(),
      timezone: scheduleForm.timezone.trim(),
      payload: parseJsonValue(scheduleForm.payloadText, {}),
      is_active: scheduleForm.is_active,
    }
    if (isEditingSchedule.value) {
      await updateTaskSchedule(editingScheduleId.value, payload)
      ElMessage.success('调度已更新')
    } else {
      await createTaskSchedule({
        template_id: scheduleForm.template_id,
        ...payload,
      })
      ElMessage.success('调度已创建')
    }
    resetScheduleForm()
    await loadData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    scheduleSubmitting.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>

<template>
  <div class="page">
    <el-row :gutter="20">
      <el-col :xs="24" :xl="13">
        <el-card shadow="never" v-loading="loading">
          <template #header>
            <div class="page__header">
              <span>任务模板</span>
              <el-button v-if="canManageTemplates" type="primary" @click="openCreateDialog">
                新建模板
              </el-button>
            </div>
          </template>

          <el-table
            :data="templates"
            highlight-current-row
            @row-click="(row: TaskTemplate) => void handleTemplateSelection(row.id)"
          >
            <el-table-column prop="name" label="模板名称" min-width="180" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="步骤数" width="100">
              <template #default="{ row }: { row: TaskTemplate }">
                {{ row.steps.length }}
              </template>
            </el-table-column>
            <el-table-column label="启用" width="100">
              <template #default="{ row }: { row: TaskTemplate }">
                <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
                  {{ row.is_active ? '启用中' : '停用' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>

      <el-col :xs="24" :xl="11">
        <el-card shadow="never" class="page__detail">
          <template #header>
            <div class="page__header">
              <span>模板详情</span>
              <div v-if="canManageTemplates && selectedTemplate" class="page__header-actions">
                <el-button
                  :loading="templateStatusSubmitting"
                  plain
                  @click="handleToggleTemplateActive"
                >
                  {{ selectedTemplate.is_active ? '停用模板' : '启用模板' }}
                </el-button>
                <el-button plain @click="openEditDialog">
                  编辑模板
                </el-button>
                <el-button plain type="danger" @click="handleDeleteTemplate">
                  删除模板
                </el-button>
              </div>
            </div>
          </template>

          <template v-if="selectedTemplate">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="模板编码">{{ selectedTemplate.code }}</el-descriptions-item>
              <el-descriptions-item label="分类">{{ selectedTemplate.category }}</el-descriptions-item>
              <el-descriptions-item label="触发方式">{{ selectedTemplate.trigger_type }}</el-descriptions-item>
              <el-descriptions-item label="说明">
                {{ selectedTemplate.description || '—' }}
              </el-descriptions-item>
            </el-descriptions>

            <el-divider>步骤</el-divider>
            <el-timeline>
              <el-timeline-item
                v-for="step in selectedTemplate.steps"
                :key="step.id"
                :timestamp="`排序 ${step.sort_order}`"
                :type="step.approval_type !== 'none' ? 'warning' : 'primary'"
              >
                <strong>{{ step.title }}</strong>
                <el-tag
                  v-if="step.approval_type !== 'none'"
                  size="small"
                  type="warning"
                  effect="plain"
                  style="margin-left: 6px"
                >
                  {{ step.approval_type === 'approve_reject' ? '审核（可驳回）' : '审核（可退回）' }}
                </el-tag>
                <p>{{ step.step_key }} · {{ formatStepMode(step) }}</p>
                <p>负责人 {{ formatAssigneeRule(step.default_assignee_rule) }}</p>
                <p>依赖 {{ step.depends_on_step_keys.join(', ') || '无' }}</p>
                <p v-if="step.reject_target_step_key">驳回跳转 → {{ step.reject_target_step_key }}</p>
                <p v-if="step.downstream_trigger?.template_code">
                  下游触发 → {{ step.downstream_trigger.template_code }}
                  （{{ step.downstream_trigger.spawn_mode === 'per_step_run' ? '按参与人' : '单实例' }}）
                </p>
              </el-timeline-item>
            </el-timeline>

            <el-divider>实例化</el-divider>
            <el-form label-position="top">
              <el-form-item label="所属部门（可选）">
                <el-select v-model="instantiateForm.department_id" clearable placeholder="默认使用当前用户部门">
                  <el-option
                    v-for="department in instantiateDepartmentOptions"
                    :key="department.id"
                    :label="department.label"
                    :value="department.id"
                  />
                </el-select>
              </el-form-item>
            </el-form>
            <el-button
              v-if="canPublishTask"
              type="primary"
              :loading="instantiateSubmitting"
              @click="handleInstantiateTemplate"
            >
              实例化模板
            </el-button>
            <el-alert
              v-else
              type="info"
              show-icon
              :closable="false"
              title="当前账号没有发布任务权限，可查看模板但不能实例化。"
            />

            <el-divider>实例运行态</el-divider>
            <div class="page__instance-panel" v-loading="instancesLoading">
              <el-empty v-if="templateInstances.length === 0" description="还没有模板实例" />
              <template v-else>
                <div class="page__instance-toolbar">
                  <el-select v-model="selectedTemplateInstanceId" placeholder="请选择实例">
                    <el-option
                      v-for="instance in templateInstances"
                      :key="instance.id"
                      :label="formatTemplateInstanceOptionLabel(instance)"
                      :value="instance.id"
                    />
                  </el-select>
                  <el-tag
                    v-if="selectedTemplateInstance"
                    :type="resolveTemplateInstanceTagType(selectedTemplateInstance.status)"
                    effect="plain"
                  >
                    {{ formatTemplateInstanceStatus(selectedTemplateInstance.status) }}
                  </el-tag>
                </div>

                <template v-if="selectedTemplateInstance">
                  <p class="page__instance-meta">
                    发起人 {{ selectedTemplateInstance.initiator_email || selectedTemplateInstance.initiator_user_id }}
                    · 部门 {{ selectedTemplateInstance.department_name || '—' }}
                    · 创建于 {{ formatDateTime(selectedTemplateInstance.created_at) }}
                  </p>
                  <el-timeline>
                    <el-timeline-item
                      v-for="snapshot in selectedTemplateInstance.step_snapshots"
                      :key="snapshot.step.id"
                      :timestamp="`排序 ${snapshot.step.sort_order}`"
                    >
                      <div class="page__instance-step">
                        <div class="page__instance-step-header">
                          <div>
                            <strong>{{ snapshot.step.title }}</strong>
                            <p>{{ snapshot.step.step_key }} · {{ formatStepMode(snapshot.step) }}</p>
                          </div>
                          <el-tag :type="resolveStepSnapshotTagType(snapshot.status)" effect="plain">
                            {{ formatStepSnapshotStatus(snapshot.status) }}
                          </el-tag>
                        </div>
                        <p class="page__instance-step-meta">
                          负责人 {{ formatAssigneeRule(snapshot.step.default_assignee_rule) }}
                          · {{ formatStepSnapshotProgress(snapshot) }}
                        </p>
                        <p class="page__instance-step-meta">
                          依赖 {{ snapshot.step.depends_on_step_keys.join(', ') || '无' }}
                        </p>
                        <p v-if="snapshot.blocked_dependency_keys.length > 0" class="page__instance-step-meta">
                          等待 {{ snapshot.blocked_dependency_keys.join(', ') }}
                        </p>
                        <div v-if="snapshot.step_runs.length > 0" class="page__instance-run-list">
                          <div v-for="stepRun in snapshot.step_runs" :key="stepRun.id" class="page__instance-run">
                            <div>
                              <strong>{{ stepRun.assignee_email || stepRun.assignee_user_id }}</strong>
                              <p>{{ stepRun.task?.title || '任务生成中' }}</p>
                            </div>
                            <div class="page__instance-run-status">
                              <el-tag size="small" :type="resolveStepRunTagType(stepRun.status)" effect="plain">
                                {{ formatStepRunStatus(stepRun.status) }}
                              </el-tag>
                              <span v-if="stepRun.task">{{ formatTaskStatus(stepRun.task.status) }}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </el-timeline-item>
                  </el-timeline>
                </template>
              </template>
            </div>

            <el-divider>实例任务</el-divider>
            <el-empty v-if="selectedInstanceTasks.length === 0" description="当前实例还没有已激活任务" />
            <el-table v-else :data="selectedInstanceTasks" size="small">
              <el-table-column prop="title" label="任务标题" min-width="180" />
              <el-table-column label="状态" width="100">
                <template #default="{ row }: { row: Task }">
                  {{ formatTaskStatus(row.status) }}
                </template>
              </el-table-column>
            </el-table>
          </template>

          <el-empty v-else description="请选择左侧模板查看详情" />
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="canManageTemplates" shadow="never">
      <template #header>
        <span>周期调度</span>
      </template>

      <el-form label-position="top" class="page__schedule-form">
        <el-form-item label="模板">
          <el-select v-model="scheduleForm.template_id" placeholder="请选择模板">
            <el-option
              v-for="template in templates"
              :key="template.id"
              :label="template.name"
              :value="template.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="Cron 表达式">
          <el-input v-model="scheduleForm.cron_expr" />
        </el-form-item>
        <el-form-item label="时区">
          <el-input v-model="scheduleForm.timezone" />
        </el-form-item>
        <el-form-item label="启用状态">
          <el-switch v-model="scheduleForm.is_active" inline-prompt active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="调度 payload(JSON)">
          <el-input v-model="scheduleForm.payloadText" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <el-button type="primary" :loading="scheduleSubmitting" @click="handleSaveSchedule">
        {{ scheduleSubmitLabel }}
      </el-button>
      <el-button v-if="isEditingSchedule" @click="resetScheduleForm">取消编辑</el-button>

      <el-divider>现有调度</el-divider>
      <el-table :data="schedules" size="small">
        <el-table-column prop="cron_expr" label="Cron" min-width="180" />
        <el-table-column prop="timezone" label="时区" width="120" />
        <el-table-column label="启用" width="100">
          <template #default="{ row }: { row: TaskSchedule }">
            <el-tag :type="row.is_active ? 'success' : 'info'" effect="plain">
              {{ row.is_active ? '启用中' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下次执行" min-width="180">
          <template #default="{ row }: { row: TaskSchedule }">
            {{ formatDateTime(row.next_run_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }: { row: TaskSchedule }">
            <el-button text @click="openEditSchedule(row)">编辑调度</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" :title="templateDialogTitle" width="960px" @closed="resetCreateForm">
      <el-form label-position="top">
        <div class="page__designer-grid">
          <el-form-item label="模板编码">
            <el-input v-model="createForm.code" placeholder="例如：video_sop" />
          </el-form-item>
          <el-form-item label="模板名称">
            <el-input v-model="createForm.name" placeholder="例如：参与选题会" />
          </el-form-item>
          <el-form-item label="分类">
            <el-input v-model="createForm.category" placeholder="例如：media" />
          </el-form-item>
        </div>
        <el-form-item label="模板说明">
          <el-input v-model="createForm.description" type="textarea" :rows="3" />
        </el-form-item>

        <el-divider>结构化步骤设计</el-divider>
        <el-alert
          type="info"
          show-icon
          :closable="false"
          title="首版设计器支持逐步激活、多人扇出/汇聚、负责人规则和步骤依赖。"
        />
        <el-alert
          v-if="userOptions.length === 0"
          class="page__designer-tip"
          type="warning"
          show-icon
          :closable="false"
          title="当前未加载可选用户列表；仍可使用发起人或部门负责人规则。"
        />
        <el-alert
          v-if="templateStructureLocked"
          class="page__designer-tip"
          type="warning"
          show-icon
          :closable="false"
          title="该模板已有实例运行记录。当前只允许更新模板名称、分类和说明，步骤结构不可再编辑。"
        />

        <div class="page__steps-toolbar">
          <span>已配置 {{ createForm.steps.length }} 个步骤</span>
          <div class="page__steps-toolbar-actions">
            <el-button plain :disabled="templateStructureLocked" @click="openImportDialog">导入 JSON</el-button>
            <el-button type="primary" plain :disabled="templateStructureLocked" @click="addStep">添加步骤</el-button>
          </div>
        </div>

        <div class="page__step-list">
          <el-card v-for="(step, index) in createForm.steps" :key="`${step.step_key}-${index}`" shadow="never">
            <template #header>
              <div class="page__step-card-header">
                <div>
                  <strong>步骤 {{ index + 1 }}</strong>
                  <span>{{ step.title || '未命名步骤' }}</span>
                </div>
                <div class="page__step-card-actions">
                  <el-button text :disabled="templateStructureLocked || index === 0" @click="moveStep(index, -1)">上移</el-button>
                  <el-button text :disabled="templateStructureLocked || index === createForm.steps.length - 1" @click="moveStep(index, 1)">下移</el-button>
                  <el-button text :disabled="templateStructureLocked" @click="duplicateStep(index)">复制</el-button>
                  <el-button text type="danger" :disabled="templateStructureLocked" @click="removeStep(index)">删除</el-button>
                </div>
              </div>
            </template>

            <div class="page__designer-grid">
              <el-form-item label="步骤编码">
                <el-input v-model="step.step_key" :disabled="templateStructureLocked" placeholder="例如：collect_assets" />
              </el-form-item>
              <el-form-item label="步骤名称">
                <el-input v-model="step.title" :disabled="templateStructureLocked" placeholder="例如：多人提交素材" />
              </el-form-item>
              <el-form-item label="步骤类型">
                <el-select v-model="step.step_type" :disabled="templateStructureLocked">
                  <el-option label="任务步骤" value="task" />
                </el-select>
              </el-form-item>
              <el-form-item label="审核类型">
                <el-select v-model="step.approval_type" :disabled="templateStructureLocked">
                  <el-option label="普通任务（无审核）" value="none" />
                  <el-option label="审核步骤（可驳回）" value="approve_reject" />
                  <el-option label="审核步骤（可退回）" value="approve_return" />
                </el-select>
              </el-form-item>
              <el-form-item
                v-if="step.approval_type !== 'none'"
                label="驳回目标步骤"
              >
                <el-select
                  v-model="step.reject_target_step_key"
                  :disabled="templateStructureLocked"
                  clearable
                  placeholder="驳回后跳回的步骤"
                >
                  <el-option
                    v-for="option in getDependencyOptions(step.step_key)"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="分配模式">
                <el-select v-model="step.assignment_mode" :disabled="templateStructureLocked" @change="handleAssignmentModeChange(step)">
                  <el-option label="单任务" value="single" />
                  <el-option label="多人扇出" value="fan_out" />
                </el-select>
              </el-form-item>
              <el-form-item label="汇聚规则">
                <el-select v-model="step.join_mode" :disabled="templateStructureLocked || step.assignment_mode === 'single'">
                  <el-option label="全部完成后推进" value="all" />
                  <el-option label="任一完成后推进" value="any" />
                </el-select>
              </el-form-item>
              <el-form-item label="负责人规则">
                <el-select v-model="step.assignee_rule_type" :disabled="templateStructureLocked" @change="handleAssigneeRuleTypeChange(step)">
                  <el-option
                    v-for="option in assigneeRuleOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-if="step.assignee_rule_type === 'user'" label="指定负责人">
                <el-select v-model="step.assignee_user_id" :disabled="templateStructureLocked" filterable placeholder="请选择用户">
                  <el-option
                    v-for="user in userOptions"
                    :key="user.id"
                    :label="user.label"
                    :value="user.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item v-if="step.assignee_rule_type === 'user_ids'" label="指定多人">
                <el-select v-model="step.assignee_user_ids" :disabled="templateStructureLocked" multiple filterable placeholder="请选择用户">
                  <el-option
                    v-for="user in userOptions"
                    :key="user.id"
                    :label="user.label"
                    :value="user.id"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="默认时限（小时，可选）">
                <el-input-number v-model="step.default_due_offset_hours" :disabled="templateStructureLocked" :min="1" controls-position="right" />
              </el-form-item>
              <el-form-item class="page__designer-grid-full" label="前置步骤">
                <el-select v-model="step.depends_on_step_keys" :disabled="templateStructureLocked" multiple clearable placeholder="无前置步骤">
                  <el-option
                    v-for="option in getDependencyOptions(step.step_key)"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
              </el-form-item>
              <el-form-item class="page__designer-grid-full" label="下游触发模板（步骤完成后自动启动，留空则不触发）">
                <el-input
                  v-model="step.downstream_template_code"
                  :disabled="templateStructureLocked"
                  placeholder="例如：COPYWRITING_WF"
                />
              </el-form-item>
              <template v-if="step.downstream_template_code.trim()">
                <el-form-item label="派生模式">
                  <el-select v-model="step.downstream_spawn_mode" :disabled="templateStructureLocked">
                    <el-option label="仅派生一个实例" value="single" />
                    <el-option label="按源步骤参与人各派生一个" value="per_step_run" />
                  </el-select>
                </el-form-item>
                <el-form-item v-if="step.downstream_spawn_mode === 'per_step_run'" label="参考源步骤">
                  <el-select
                    v-model="step.downstream_spawn_source_step_key"
                    :disabled="templateStructureLocked"
                    clearable
                    placeholder="以哪个步骤的参与人为单位"
                  >
                    <el-option
                      v-for="option in getDependencyOptions(step.step_key)"
                      :key="option.value"
                      :label="option.label"
                      :value="option.value"
                    />
                  </el-select>
                </el-form-item>
              </template>
              <el-form-item class="page__designer-grid-full" label="步骤说明">
                <el-input v-model="step.description" :disabled="templateStructureLocked" type="textarea" :rows="3" />
              </el-form-item>
            </div>
          </el-card>
        </div>

        <el-form-item label="步骤 JSON 预览（只读）">
          <el-input :model-value="stepsJsonPreview" type="textarea" :rows="8" readonly />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="createSubmitting" @click="handleSaveTemplate">
          {{ templateDialogSubmitLabel }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="importDialogVisible"
      title="从 JSON 导入步骤"
      width="720px"
      append-to-body
    >
      <el-alert
        type="info"
        show-icon
        :closable="false"
        title="输入 TaskTemplate steps 数组 JSON；导入时会自动映射负责人规则、依赖、单任务与多人扇出字段。"
      />
      <el-input v-model="importStepsText" class="page__import-input" type="textarea" :rows="14" />

      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleImportSteps">导入步骤</el-button>
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

.page__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page__header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page__detail {
  min-height: 100%;
}

.page__instance-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page__instance-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page__instance-toolbar :deep(.el-select) {
  flex: 1;
}

.page__instance-meta {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.page__instance-step {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page__instance-step-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.page__instance-step-header p,
.page__instance-step-meta,
.page__instance-run p {
  margin: 0;
  color: var(--el-text-color-secondary);
}

.page__instance-run-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.page__instance-run {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
}

.page__instance-run-status {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
}

.page__schedule-form,
.page__designer-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.page__designer-grid-full {
  grid-column: 1 / -1;
}

.page__designer-tip {
  margin-top: 12px;
}

.page__steps-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 16px 0;
}

.page__steps-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page__step-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 16px;
}

.page__step-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.page__step-card-header > div:first-child {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.page__step-card-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page__import-input {
  margin-top: 16px;
}

@media (max-width: 768px) {
  .page__instance-toolbar,
  .page__step-card-header,
  .page__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .page__instance-run,
  .page__step-card-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .page__instance-run {
    flex-direction: column;
    align-items: flex-start;
  }

  .page__steps-toolbar {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .page__steps-toolbar-actions {
    width: 100%;
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}
</style>
