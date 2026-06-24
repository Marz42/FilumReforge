<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createGraphTemplateSchedule,
  listGraphTemplates,
  previewWorkflowParticipants,
  runGraphTemplateScheduleNow,
} from '@/api/workflow-graph'
import { listDepartments } from '@/api/departments'
import type { GraphTemplateSummary } from '@/types/workflowVideo'
import { resolveLaunchSchema, resolveParticipantPolicyRefs } from '@/utils/workflowVideoSchema'
import { formatUserOptionLabel } from '@/utils/userDisplay'
import { getErrorMessage } from '@/utils/errors'

const props = defineProps<{
  departmentOptions: Array<{ id: string; label: string }>
  userOptions: Array<{ user_id: string; label: string }>
}>()

const emit = defineEmits<{
  created: []
}>()

const submitting = ref(false)
const templates = ref<GraphTemplateSummary[]>([])
const allDepartments = ref<Array<{ id: string; label: string }>>([])
const previewUsers = ref<Array<{ id: string; email: string; display_name?: string | null }>>([])

const form = reactive({
  template_id: '',
  name: '',
  scope_department_id: '',
  scope_mode: 'self' as 'self' | 'subtree',
  cron_preset: 'weekly_mon_9',
  cron_expr: '0 9 * * 1',
  timezone: 'Asia/Shanghai',
  theme: '',
  participant_mode: 'all' as 'all' | 'subset',
  participant_user_ids: [] as string[],
  exclude_department_ids: [] as string[],
  exclude_user_ids: [] as string[],
  run_now: false,
})

const selectedTemplate = computed(() =>
  templates.value.find((template) => template.id === form.template_id) ?? null,
)

const policyRef = computed(() => {
  const refs = resolveParticipantPolicyRefs(selectedTemplate.value?.config)
  return refs[0] ?? ''
})

const cronPresets: Record<string, string> = {
  weekly_mon_9: '0 9 * * 1',
  weekly_fri_17: '0 17 * * 5',
  monthly_1_9: '0 9 1 * *',
}

const participantSelectOptions = computed(() =>
  previewUsers.value.map((user) => ({
    value: user.id,
    label: formatUserOptionLabel(user),
  })),
)

async function loadTemplates(): Promise<void> {
  templates.value = await listGraphTemplates({ schedulable: true })
}

async function loadDepartments(): Promise<void> {
  const departments = await listDepartments()
  allDepartments.value = departments.map((department) => ({
    id: department.id,
    label: `${department.name} (${department.code})`,
  }))
}

async function refreshParticipantPreview(): Promise<void> {
  if (!form.template_id || !form.scope_department_id || !policyRef.value) {
    previewUsers.value = []
    return
  }
  try {
    const result = await previewWorkflowParticipants(form.template_id, policyRef.value, {
      mode: 'all',
      department_id: form.scope_department_id,
    })
    previewUsers.value = result.users
  } catch {
    previewUsers.value = []
  }
}

watch(
  () => [form.template_id, form.scope_department_id] as const,
  () => {
    void refreshParticipantPreview()
  },
)

watch(
  () => form.cron_preset,
  (preset) => {
    if (preset !== 'custom' && cronPresets[preset]) {
      form.cron_expr = cronPresets[preset]
    }
  },
)

function applyCronPreset(preset: string): void {
  form.cron_preset = preset
  if (preset !== 'custom' && cronPresets[preset]) {
    form.cron_expr = cronPresets[preset]
  }
}

async function handleSubmit(): Promise<void> {
  if (!form.template_id) {
    ElMessage.warning('请选择 schedulable 模板')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请输入调度名称')
    return
  }
  if (!form.scope_department_id) {
    ElMessage.warning('请选择作用部门')
    return
  }
  if (form.participant_mode === 'subset' && form.participant_user_ids.length === 0) {
    ElMessage.warning('subset 模式至少选择一名参与人')
    return
  }

  const launchSchema = resolveLaunchSchema(selectedTemplate.value?.config)
  const defaultInputs: Record<string, unknown> = {}
  if (form.theme.trim()) {
    const themeField = launchSchema?.fields?.find((field) => field.key === 'theme')
    if (themeField) {
      defaultInputs.theme = form.theme.trim()
    }
  }

  submitting.value = true
  try {
    const schedule = await createGraphTemplateSchedule({
      template_id: form.template_id,
      name: form.name.trim(),
      scope_department_id: form.scope_department_id,
      scope_mode: form.scope_mode,
      cron_expr: form.cron_expr.trim(),
      timezone: form.timezone,
      default_inputs: defaultInputs,
      participant_mode: form.participant_mode,
      participant_user_ids: form.participant_user_ids,
      exclude_department_ids: form.exclude_department_ids,
      exclude_user_ids: form.exclude_user_ids,
      is_active: true,
    })
    if (form.run_now) {
      await runGraphTemplateScheduleNow(schedule.id)
      ElMessage.success('周期任务已创建并已立即执行一次')
    } else {
      ElMessage.success('周期任务已创建')
    }
    emit('created')
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadTemplates(), loadDepartments()])
  if (props.departmentOptions.length === 1) {
    form.scope_department_id = props.departmentOptions[0]!.id
  }
})

defineExpose({ submit: handleSubmit, submitting })
</script>

<template>
  <el-form label-position="top" class="scheduled-dispatch-form" data-testid="scheduled-dispatch-form">
    <el-form-item label="schedulable 模板" required>
      <el-select
        v-model="form.template_id"
        filterable
        placeholder="仅显示已启用定时的模板"
        class="scheduled-dispatch-form__full"
        data-testid="scheduled-dispatch-template"
      >
        <el-option
          v-for="template in templates"
          :key="template.id"
          :label="`${template.name} (${template.code})`"
          :value="template.id"
        />
      </el-select>
    </el-form-item>
    <el-form-item label="调度名称" required>
      <el-input v-model="form.name" maxlength="120" placeholder="例如：每周选题会" data-testid="scheduled-dispatch-name" />
    </el-form-item>
    <el-form-item label="作用部门" required>
      <el-select
        v-model="form.scope_department_id"
        filterable
        class="scheduled-dispatch-form__full"
        data-testid="scheduled-dispatch-department"
      >
        <el-option
          v-for="department in departmentOptions"
          :key="department.id"
          :label="department.label"
          :value="department.id"
        />
      </el-select>
    </el-form-item>
    <el-form-item label="作用范围">
      <el-radio-group v-model="form.scope_mode">
        <el-radio value="self">仅本部门</el-radio>
        <el-radio value="subtree">含所有 active 子部门</el-radio>
      </el-radio-group>
    </el-form-item>
    <el-form-item label="周期">
      <el-radio-group v-model="form.cron_preset" @change="applyCronPreset(form.cron_preset)">
        <el-radio value="weekly_mon_9">每周一 09:00</el-radio>
        <el-radio value="weekly_fri_17">每周五 17:00</el-radio>
        <el-radio value="monthly_1_9">每月 1 日 09:00</el-radio>
        <el-radio value="custom">自定义 cron</el-radio>
      </el-radio-group>
      <el-input
        v-if="form.cron_preset === 'custom'"
        v-model="form.cron_expr"
        class="scheduled-dispatch-form__cron"
        placeholder="0 9 * * 1"
        data-testid="scheduled-dispatch-cron"
      />
    </el-form-item>
    <el-form-item v-if="resolveLaunchSchema(selectedTemplate?.config)?.fields?.some((f) => f.key === 'theme')" label="默认主题">
      <el-input v-model="form.theme" placeholder="写入 launch theme（可选）" />
    </el-form-item>
    <el-form-item label="参与人">
      <el-radio-group v-model="form.participant_mode">
        <el-radio value="all">部门全员</el-radio>
        <el-radio value="subset">指定成员</el-radio>
      </el-radio-group>
      <el-select
        v-if="form.participant_mode === 'subset'"
        v-model="form.participant_user_ids"
        multiple
        filterable
        class="scheduled-dispatch-form__full"
        placeholder="从部门成员中选择"
        data-testid="scheduled-dispatch-participants"
      >
        <el-option
          v-for="user in participantSelectOptions"
          :key="user.value"
          :label="user.label"
          :value="user.value"
        />
      </el-select>
    </el-form-item>
    <el-form-item label="排除部门">
      <el-select
        v-model="form.exclude_department_ids"
        multiple
        filterable
        clearable
        class="scheduled-dispatch-form__full"
        placeholder="子树展开时跳过这些部门"
        data-testid="scheduled-dispatch-exclude-departments"
      >
        <el-option
          v-for="department in allDepartments"
          :key="department.id"
          :label="department.label"
          :value="department.id"
        />
      </el-select>
    </el-form-item>
    <el-form-item label="排除人员">
      <el-select
        v-model="form.exclude_user_ids"
        multiple
        filterable
        clearable
        class="scheduled-dispatch-form__full"
        data-testid="scheduled-dispatch-exclude-users"
      >
        <el-option v-for="user in userOptions" :key="user.user_id" :label="user.label" :value="user.user_id" />
      </el-select>
    </el-form-item>
    <el-form-item label="立即执行一次">
      <el-switch v-model="form.run_now" data-testid="scheduled-dispatch-run-now" />
    </el-form-item>
  </el-form>
</template>

<style scoped>
.scheduled-dispatch-form__full {
  width: 100%;
}

.scheduled-dispatch-form__cron {
  margin-top: 8px;
}
</style>
