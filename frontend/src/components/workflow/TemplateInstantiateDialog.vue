<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createGraphTemplateRun,
  listManagedDepartmentMemberOptions,
  previewWorkflowParticipants,
} from '@/api/workflow-graph'
import FilumDateTimePicker from '@/components/common/FilumDateTimePicker.vue'
import { useAuthStore } from '@/stores/auth'
import type { GraphTemplateSummary, ParticipantUserPreview } from '@/types/workflowVideo'
import type { User } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
import { formatUserOptionLabel } from '@/utils/userDisplay'
import {
  resolveLaunchSchema,
  resolveParticipantPolicyRefs,
} from '@/utils/workflowVideoSchema'

const props = defineProps<{
  modelValue: boolean
  template: GraphTemplateSummary | null
  users: User[]
  defaultDepartmentId?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: [payload: { instanceId: string; rootTaskId: string }]
}>()

const authStore = useAuthStore()
const submitting = ref(false)
const previewLoading = ref(false)
const managerLoading = ref(false)
const launchValues = reactive<Record<string, string>>({})
const launchDateTimes = reactive<Record<string, Date | null>>({})
const runLabel = ref('')
const departmentId = ref('')
const participantMode = ref<'all' | 'subset'>('subset')
const includeInitiator = ref(false)
const selectedParticipantIds = ref<string[]>([])
const previewUsers = ref<ParticipantUserPreview[]>([])
const candidateUsers = ref<ParticipantUserPreview[]>([])
const managerCandidates = ref<ParticipantUserPreview[]>([])

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const launchSchema = computed(() => resolveLaunchSchema(props.template?.config as Record<string, unknown> | undefined))
const policyRef = computed(() => resolveParticipantPolicyRefs(props.template?.config as Record<string, unknown> | undefined)[0] ?? 'copywriters')

const userOptions = computed(() =>
  props.users
    .filter((user) => user.status === 'active')
    .map((user) => ({
      value: user.id,
      label: formatUserOptionLabel({ email: user.email }),
    })),
)

/** 负责人与「指定成员」同源：管理所负责部门 + 所属部门成员，并与参与人预览合并去重 */
const managerUserOptions = computed(() => {
  const byId = new Map<string, { value: string; label: string }>()
  for (const user of [...managerCandidates.value, ...candidateUsers.value]) {
    byId.set(user.id, { value: user.id, label: formatUserOptionLabel(user) })
  }
  return [...byId.values()]
})

const participantUserOptions = computed(() => {
  const fromCandidates = candidateUsers.value.map((user) => ({
    value: user.id,
    label: formatUserOptionLabel(user),
  }))
  if (fromCandidates.length > 0) {
    return fromCandidates
  }
  return userOptions.value
})

const previewUserSummary = computed(() =>
  effectivePreviewUsers.value.map((user) => formatUserOptionLabel(user)).join('，'),
)

const effectivePreviewUsers = computed(() => {
  const initiatorId = authStore.user?.id
  if (includeInitiator.value || !initiatorId) {
    return previewUsers.value
  }
  return previewUsers.value.filter((user) => user.id !== initiatorId)
})

function isManagerUserField(key: string): boolean {
  return key === 'manager_user_id'
}

function setLaunchDateTime(key: string, value: Date | null): void {
  launchDateTimes[key] = value
  launchValues[key] = value ? value.toISOString() : ''
}

function resetForm(): void {
  runLabel.value = ''
  departmentId.value = props.defaultDepartmentId ?? ''
  participantMode.value = 'subset'
  includeInitiator.value = false
  selectedParticipantIds.value = []
  previewUsers.value = []
  candidateUsers.value = []
  managerCandidates.value = []
  for (const key of Object.keys(launchValues)) {
    delete launchValues[key]
  }
  for (const key of Object.keys(launchDateTimes)) {
    delete launchDateTimes[key]
  }
  for (const field of launchSchema.value?.fields ?? []) {
    launchValues[field.key] = ''
    if (field.type === 'datetime') {
      launchDateTimes[field.key] = null
    }
  }
}

function applyDefaultManager(): void {
  const options = managerUserOptions.value
  const current = launchValues.manager_user_id?.trim()
  if (current && options.some((option) => option.value === current)) {
    return
  }
  const currentId = authStore.user?.id
  if (currentId && options.some((option) => option.value === currentId)) {
    launchValues.manager_user_id = currentId
    return
  }
  launchValues.manager_user_id = ''
}

async function loadManagerOptions(): Promise<void> {
  managerLoading.value = true
  try {
    managerCandidates.value = await listManagedDepartmentMemberOptions()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    managerCandidates.value = []
  } finally {
    managerLoading.value = false
  }
}

async function loadDialogOptions(): Promise<void> {
  await loadCandidateUsers()
  await loadManagerOptions()
  applyDefaultManager()
  await loadParticipantPreview()
}

async function loadCandidateUsers(): Promise<void> {
  if (!props.template) {
    return
  }
  try {
    const response = await previewWorkflowParticipants(props.template.id, policyRef.value, {
      mode: 'all',
      user_ids: [],
      department_id: departmentId.value || null,
    })
    candidateUsers.value = response.users
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
    candidateUsers.value = []
  }
}

async function loadParticipantPreview(): Promise<void> {
  if (!props.template) {
    return
  }
  if (participantMode.value === 'subset' && selectedParticipantIds.value.length === 0) {
    previewUsers.value = []
    return
  }
  previewLoading.value = true
  try {
    const response = await previewWorkflowParticipants(props.template.id, policyRef.value, {
      mode: participantMode.value,
      user_ids: participantMode.value === 'subset' ? selectedParticipantIds.value : [],
      department_id: departmentId.value || null,
    })
    previewUsers.value = response.users
    if (participantMode.value === 'all') {
      selectedParticipantIds.value = response.user_ids
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    previewLoading.value = false
  }
}

async function handleSubmit(): Promise<void> {
  if (!props.template) {
    return
  }
  const fields = launchSchema.value?.fields ?? []
  for (const field of fields) {
    if (field.required && !launchValues[field.key]?.trim()) {
      ElMessage.warning(`请填写${field.label}`)
      return
    }
  }
  if (participantMode.value === 'subset' && selectedParticipantIds.value.length === 0) {
    ElMessage.warning('请至少选择一名参与人')
    return
  }
  if (effectivePreviewUsers.value.length === 0) {
    ElMessage.warning('排除发起人后至少保留一名采集参与人')
    return
  }

  submitting.value = true
  try {
    const inputs: Record<string, unknown> = { ...launchValues }
    const result = await createGraphTemplateRun(props.template.id, {
      inputs,
      participants_snapshot: {
        [policyRef.value]: {
          mode: participantMode.value,
          user_ids:
            participantMode.value === 'all'
              ? previewUsers.value.map((user) => user.id)
              : selectedParticipantIds.value,
          include_initiator: includeInitiator.value,
        },
      },
      department_id: departmentId.value || null,
      run_label: runLabel.value.trim() || null,
    })
    ElMessage.success(`已创建运行实例，激活 ${result.activated_task_count} 条任务`)
    visible.value = false
    emit('created', { instanceId: result.instance_id, rootTaskId: result.root_task_id })
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      resetForm()
      void loadDialogOptions()
    }
  },
)

watch(participantMode, () => {
  if (props.modelValue) {
    void loadParticipantPreview()
  }
})

watch(includeInitiator, () => {
  if (props.modelValue) {
    void loadParticipantPreview()
  }
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="template ? `实例化：${template.name}` : '任务模板实例化'"
    width="640px"
    destroy-on-close
    data-testid="template-instantiate-dialog"
  >
    <template v-if="template">
      <el-alert type="info" :closable="false" show-icon class="workflow-dialog__hint">
        统一入口：选择参与人并填写启动表单，无需单独「发起选题会」按钮。
        <el-tag v-if="template.run_kind" size="small" effect="plain" class="workflow-dialog__badge">
          {{ template.run_kind === 'batch' ? '批次' : template.run_kind }}
        </el-tag>
      </el-alert>

      <el-form label-position="top" @submit.prevent>
        <el-form-item label="运行标题（可选）">
          <el-input v-model="runLabel" placeholder="例如：第 12 周选题会" />
        </el-form-item>
        <el-form-item
          v-for="field in launchSchema?.fields ?? []"
          :key="field.key"
          :label="field.label"
          :required="field.required"
        >
          <el-select
            v-if="field.type === 'user' && isManagerUserField(field.key)"
            v-model="launchValues[field.key]"
            filterable
            clearable
            :loading="managerLoading && managerUserOptions.length === 0"
            :placeholder="
              managerLoading && managerUserOptions.length === 0
                ? '正在加载负责人…'
                : managerUserOptions.length
                  ? '选择负责人'
                  : '暂无可选负责人'
            "
            :disabled="managerUserOptions.length === 0"
            style="width: 100%"
          >
            <el-option
              v-for="option in managerUserOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-select
            v-else-if="field.type === 'user'"
            v-model="launchValues[field.key]"
            filterable
            clearable
            placeholder="选择用户"
            style="width: 100%"
          >
            <el-option
              v-for="option in userOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <FilumDateTimePicker
            v-else-if="field.type === 'datetime'"
            :model-value="launchDateTimes[field.key] ?? null"
            :placeholder="field.label"
            @update:model-value="setLaunchDateTime(field.key, $event)"
          />
          <el-input
            v-else-if="field.type === 'textarea'"
            v-model="launchValues[field.key]"
            type="textarea"
            :rows="3"
          />
          <el-input v-else v-model="launchValues[field.key]" />
        </el-form-item>

        <el-divider>参与人（{{ policyRef }}）</el-divider>
        <el-form-item label="参与范围">
          <el-radio-group v-model="participantMode">
            <el-radio-button value="subset">指定成员</el-radio-button>
            <el-radio-button value="all">部门全员</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="participantMode === 'subset'" label="文案参与人">
          <el-select
            v-model="selectedParticipantIds"
            multiple
            filterable
            placeholder="选择参与人"
            style="width: 100%"
            @change="loadParticipantPreview"
          >
            <el-option
              v-for="option in participantUserOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-checkbox v-model="includeInitiator" data-testid="template-include-initiator">
            发起人参与采集
          </el-checkbox>
        </el-form-item>
        <p v-if="effectivePreviewUsers.length" class="workflow-dialog__preview">
          将展开 {{ effectivePreviewUsers.length }} 个采集任务<span v-if="previewUserSummary">：{{ previewUserSummary }}</span>
        </p>
        <p v-else-if="previewUsers.length && !includeInitiator" class="workflow-dialog__preview workflow-dialog__preview--warn">
          当前选择排除发起人后将无采集任务，请增选参与人或勾选「发起人参与采集」
        </p>
      </el-form>
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" data-testid="template-instantiate-submit" @click="handleSubmit">
        创建运行
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.workflow-dialog__hint {
  margin-bottom: 16px;
}

.workflow-dialog__badge {
  margin-left: 8px;
}

.workflow-dialog__preview {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.workflow-dialog__preview--warn {
  color: var(--el-color-warning);
}
</style>
