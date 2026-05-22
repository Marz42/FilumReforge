<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import {
  createGraphTemplateRun,
  previewWorkflowParticipants,
} from '@/api/workflow-graph'
import type { GraphTemplateSummary } from '@/types/workflowVideo'
import type { User } from '@/types/api'
import { getErrorMessage } from '@/utils/errors'
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

const submitting = ref(false)
const previewLoading = ref(false)
const launchValues = reactive<Record<string, string>>({})
const runLabel = ref('')
const departmentId = ref('')
const participantMode = ref<'all' | 'subset'>('subset')
const selectedParticipantIds = ref<string[]>([])
const previewUsers = ref<Array<{ id: string; email: string; display_name?: string | null }>>([])

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const launchSchema = computed(() => resolveLaunchSchema(props.template?.config as Record<string, unknown> | undefined))
const policyRef = computed(() => resolveParticipantPolicyRefs(props.template?.config as Record<string, unknown> | undefined)[0] ?? 'copywriters')
const templateConfig = computed(() => (props.template?.config ?? {}) as Record<string, unknown>)

const userOptions = computed(() =>
  props.users
    .filter((user) => user.status === 'active')
    .map((user) => ({
      value: user.id,
      label: user.email,
    })),
)

function resetForm(): void {
  runLabel.value = ''
  departmentId.value = props.defaultDepartmentId ?? ''
  participantMode.value = 'subset'
  selectedParticipantIds.value = []
  previewUsers.value = []
  for (const key of Object.keys(launchValues)) {
    delete launchValues[key]
  }
  for (const field of launchSchema.value?.fields ?? []) {
    launchValues[field.key] = ''
  }
}

async function loadParticipantPreview(): Promise<void> {
  if (!props.template) {
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
      void loadParticipantPreview()
    }
  },
)

watch(participantMode, () => {
  if (props.modelValue) {
    void loadParticipantPreview()
  }
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="template ? `实例化：${template.name}` : '图模板实例化'"
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
            v-if="field.type === 'user'"
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
              v-for="option in userOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <p v-if="previewUsers.length" class="workflow-dialog__preview">
          将展开 {{ previewUsers.length }} 个采集任务
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
</style>
